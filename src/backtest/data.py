"""Data adapter for the backtest engine (M08).

Loads a validated, versioned training dataset (reusing
``src.model.loader.load_training_dataset``) and attaches the exact
close prices needed for close-to-close P&L simulation. Prices come from
the cleaned interim tier and are matched to the dataset's recorded
``source_versions`` checksum so every simulated dollar is traceable to
the same source data that produced the features and labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.backtest.errors import DataQualityError
from src.cleaning.io import read_raw_csv, sha256_of
from src.logging.logger import get_logger
from src.model.loader import load_training_dataset

logger = get_logger("backtest.data")

PRICE_COLUMN = "adj_close"  # same price basis used by the label engine (LABEL_GENERATION_BLUEPRINT)


@dataclass(frozen=True)
class BacktestData:
    """One ticker's evaluation rows with prices and full provenance."""

    ticker: str
    rows: (
        pd.DataFrame
    )  # timestamp, label, future_return, target_timestamp, features, prediction cols, close, exit_close
    prices: pd.DataFrame  # timestamp (index) -> close
    dataset_version: str
    feature_version: str
    label_version: str
    price_source: Path
    source_checksum: str

    @property
    def test_period(self) -> dict[str, str | None]:
        if self.rows.empty:
            return {"start": None, "end": None}
        timestamps = pd.to_datetime(self.rows["timestamp"])
        return {"start": timestamps.min().isoformat(), "end": timestamps.max().isoformat()}


def _find_price_source(interim_dir: Path, ticker: str, expected_checksum: str) -> Path:
    """Locate the cleaned CSV whose SHA-256 prefix matches the dataset record."""
    candidates: list[Path] = []
    for path in sorted(interim_dir.glob(f"cleaned_*_{ticker}_*.csv")):
        try:
            checksum = sha256_of(path)
        except OSError:
            continue
        if checksum[:12] == expected_checksum:
            return path
        candidates.append((path, checksum[:12]))
    available = ", ".join(f"{path.name} ({prefix})" for path, prefix in candidates)
    raise DataQualityError(
        f"no cleaned price source for {ticker} matches dataset source_versions={expected_checksum!r}",
        context={
            "ticker": ticker,
            "expected_checksum_prefix": expected_checksum,
            "available": available or "none",
        },
    )


def _load_price_series(path: Path) -> pd.DataFrame:
    """Read a cleaned interim CSV into an ascending, deduplicated close series."""
    records, errors = read_raw_csv(path)
    if errors:
        raise DataQualityError(
            f"cleaned price source contains unreadable rows: {path.name}",
            context={"path": str(path), "rejected_rows": len(errors)},
        )
    frame = pd.DataFrame(records)
    required = {"ticker", "timestamp", PRICE_COLUMN}
    missing = required - set(frame.columns)
    if missing:
        raise DataQualityError(
            f"cleaned price source missing columns: {sorted(missing)}",
            context={"path": str(path), "columns": sorted(frame.columns)},
        )
    frame = frame.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    frame[PRICE_COLUMN] = pd.to_numeric(frame[PRICE_COLUMN], errors="coerce")
    frame = frame.dropna(subset=["timestamp", PRICE_COLUMN]).drop_duplicates(
        subset="timestamp", keep="first"
    )
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    if frame.empty:
        raise DataQualityError("cleaned price source contains no usable rows")
    if not (frame[PRICE_COLUMN] > 0).all():
        raise DataQualityError(
            "cleaned price source contains non-positive prices (blueprint section 31)"
        )
    if not frame["timestamp"].is_monotonic_increasing:
        raise DataQualityError("cleaned price source timestamps are not ascending")
    return frame


def load_backtest_data(
    processed_dir: Path,
    interim_dir: Path,
    *,
    ticker: str,
    dataset_version: str,
    feature_version: str,
    label_version: str,
    split: str | None = "test",
) -> BacktestData:
    """Load and validate evaluation rows plus their price series.

    ``split`` selects one frozen split (default ``test``); ``None`` loads
    the full history (train + val + test concatenated) for walk-forward
    fold generation.

    Raises:
        DataQualityError: if the price source is missing, prices are
            invalid, or any evaluation row lacks an entry/exit price
            (fail-loud policy, blueprint section 31).
    """
    dataset = load_training_dataset(
        processed_dir,
        dataset_version=dataset_version,
        feature_version=feature_version,
        label_version=label_version,
    )
    source_versions: dict = dataset.metadata.get("source_versions", {})
    expected_checksum = source_versions.get(ticker)
    if not expected_checksum:
        raise DataQualityError(
            f"dataset {dataset_version} has no recorded source for {ticker}",
            context={"ticker": ticker, "source_versions": source_versions},
        )
    price_path = _find_price_source(interim_dir, ticker, str(expected_checksum))
    prices = _load_price_series(price_path)
    prices_by_ts = prices.set_index("timestamp")[PRICE_COLUMN]

    splits = {"train": dataset.train, "val": dataset.val, "test": dataset.test}
    if split is None:
        rows = (
            pd.concat([dataset.train, dataset.val, dataset.test], ignore_index=True)
            .sort_values("timestamp")
            .reset_index(drop=True)
        )
    elif split in splits:
        rows = splits[split].copy()
    else:
        raise DataQualityError(f"unknown dataset split {split!r}", context={"split": split})
    if rows.empty:
        raise DataQualityError(
            f"dataset {dataset_version} {split} split is empty",
            context={"split": split, "dataset_version": dataset_version},
        )
    if rows["ticker"].nunique() != 1 or rows["ticker"].iloc[0] != ticker:
        raise DataQualityError(
            f"{split} split does not contain exactly instrument {ticker}",
            context={"tickers": sorted(rows["ticker"].unique())},
        )
    rows["timestamp"] = pd.to_datetime(rows["timestamp"], errors="coerce")
    rows["target_timestamp"] = pd.to_datetime(rows["target_timestamp"], errors="coerce")
    if rows["timestamp"].isna().any() or rows["target_timestamp"].isna().any():
        raise DataQualityError(f"{split} split contains invalid timestamps")
    if not rows["timestamp"].is_monotonic_increasing:
        raise DataQualityError(f"{split} split timestamps are not ascending (blueprint section 31)")
    if not (rows["target_timestamp"] > rows["timestamp"]).all():
        raise DataQualityError("target timestamps must be strictly after observation timestamps")

    entry_close = rows["timestamp"].map(prices_by_ts)
    exit_close = rows["target_timestamp"].map(prices_by_ts)
    missing_entry = rows["timestamp"][entry_close.isna()]
    missing_exit = rows["target_timestamp"][exit_close.isna()]
    if not missing_entry.empty or not missing_exit.empty:
        raise DataQualityError(
            "evaluation rows missing entry/exit prices — aborting (no silent skip)",
            context={
                "missing_entry_count": int(missing_entry.shape[0]),
                "missing_exit_count": int(missing_exit.shape[0]),
                "missing_entry_sample": [str(x) for x in missing_entry.head(5)],
                "missing_exit_sample": [str(x) for x in missing_exit.head(5)],
            },
        )
    rows["close"] = entry_close.to_numpy()
    rows["exit_close"] = exit_close.to_numpy()
    if not (rows["close"] > 0).all() or not (rows["exit_close"] > 0).all():
        raise DataQualityError("evaluation rows contain non-positive entry/exit prices")
    rows = rows.reset_index(drop=True)

    logger.info(
        "backtest_data_loaded",
        ticker=ticker,
        dataset_version=dataset_version,
        feature_version=feature_version,
        label_version=label_version,
        split=split,
        rows=len(rows),
        price_source=price_path.name,
        source_checksum=expected_checksum,
        period=rows["timestamp"].min().isoformat() if not rows.empty else None,
        status="READY",
    )
    return BacktestData(
        ticker=ticker,
        rows=rows,
        prices=prices,
        dataset_version=dataset_version,
        feature_version=feature_version,
        label_version=label_version,
        price_source=price_path,
        source_checksum=str(expected_checksum),
    )
