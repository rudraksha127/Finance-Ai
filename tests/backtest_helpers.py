"""Shared deterministic fixtures for Milestone 08 (backtest) tests.

Builds a versioned dataset (via the real Dataset Builder storage API)
plus a matching cleaned price source whose SHA-256 prefix equals the
dataset's recorded ``source_versions`` entry — the same traceability
contract the backtest engine enforces in production.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from src.cleaning.io import sha256_of
from src.config.loader import AppConfig, BacktestConfig, ModelConfig
from src.dataset.metadata import DatasetManifest, DatasetMetadata, compute_dataset_version_hash
from src.dataset.storage import write_dataset
from src.features.registry import FEATURE_COLUMNS
from tests.data_helpers import make_app_config

TICKER = "AAPL"
VERSION = "v0.1"


def _oscillator(rows: int, period: int = 9) -> np.ndarray:
    """Stationary deterministic signal in [-1, 1] used for labels + features."""
    return np.sin(2.0 * np.pi * np.arange(rows) / period)


def _labels_from_signal(h: np.ndarray) -> list[str]:
    margin = np.sin(2.0 * np.pi * (1.0 / 9.0)) * 0.5  # ~0.34: confident bands only
    return ["UP" if value > margin else "DOWN" if value < -margin else "HOLD" for value in h]


def _frame(timestamps: pd.DatetimeIndex, h: np.ndarray) -> pd.DataFrame:
    """Rows whose features encode ``h`` and whose labels derive from ``h``.

    Features are stationary (bounded oscillators with per-column phase
    offsets) so models trained on the train period can generalize to the
    out-of-sample test period — unlike monotonic row-index features.
    """
    rows = len(timestamps)
    labels = _labels_from_signal(h)
    features = {
        name: [float(h[index] + 0.05 * ((column % 4) + 1)) for index in range(rows)]
        for column, name in enumerate(FEATURE_COLUMNS)
    }
    return pd.DataFrame(
        {
            "ticker": [TICKER] * rows,
            "timestamp": timestamps,
            **features,
            "label": labels[:rows],
            "future_return": [
                0.02 if label == "UP" else -0.02 if label == "DOWN" else 0.0 for label in labels
            ],
            "target_timestamp": timestamps + pd.offsets.BDay(5),
            "dataset_version": [VERSION] * rows,
            "feature_set_version": [VERSION] * rows,
            "label_set_version": [VERSION] * rows,
            "source_data_version": ["source-fixme"] * rows,
        }
    )


def build_backtest_fixture(
    tmp_path: Path | None = None,
    *,
    n_train: int = 80,
    n_val: int = 30,
    n_test: int = 25,
    seed: int = 7,
    root_config: AppConfig | None = None,
) -> AppConfig:
    """Write a deterministic dataset + price source; return a rooted config.

    ``root_config`` roots the fixture at real configuration data paths
    (used by the live CLI demo); otherwise a tmp_path sandbox is used.
    """
    if root_config is not None:
        config = replace(
            root_config,
            model=ModelConfig(artifact_dir=root_config.data.processed_dir / "models"),
            backtest=BacktestConfig(output_dir=Path.cwd() / "backtests"),
        )
    else:
        assert tmp_path is not None
        config = make_app_config(tmp_path / "raw")
        config = replace(
            config,
            model=ModelConfig(artifact_dir=tmp_path / "models"),
            backtest=BacktestConfig(output_dir=tmp_path / "backtests"),
        )
    interim = config.data.interim_dir
    processed = config.data.processed_dir
    interim.mkdir(parents=True, exist_ok=True)

    total = n_train + n_val + n_test
    all_timestamps = pd.date_range("2024-01-02", periods=total + 5, freq="B")
    row_timestamps = all_timestamps[:total]
    h = _oscillator(total)

    train = _frame(row_timestamps[:n_train], h[:n_train])
    val = _frame(row_timestamps[n_train : n_train + n_val], h[n_train : n_train + n_val])
    test = _frame(row_timestamps[n_train + n_val :], h[n_train + n_val :])
    labels = list(train["label"]) + list(val["label"]) + list(test["label"])
    train["source_data_version"] = "real-source-hash"
    val["source_data_version"] = "real-source-hash"
    test["source_data_version"] = "real-source-hash"

    # Deterministic price series spanning every timestamp and target_timestamp.
    rng = np.random.default_rng(seed)
    closes = 100.0 + np.cumsum(rng.normal(0.05, 1.0, size=len(all_timestamps)))
    closes = np.maximum(closes, 10.0)
    price_records = []
    for ts, close in zip(all_timestamps, closes):
        price_records.append(
            {
                "ticker": TICKER,
                "timestamp": ts.isoformat(),
                "open": round(float(close - 0.1), 4),
                "high": round(float(close + 0.6), 4),
                "low": round(float(close - 0.6), 4),
                "close": round(float(close), 4),
                "adj_close": round(float(close), 4),
                "volume": 1_000_000,
            }
        )
    price_path = interim / f"cleaned_20240101_{TICKER}_daily.csv"
    pd.DataFrame(price_records).to_csv(price_path, index=False)
    checksum = sha256_of(price_path)[:12]

    for frame in (train, val, test):
        frame["source_data_version"] = checksum

    config_snapshot = {
        "dataset_version": VERSION,
        "feature_version": VERSION,
        "label_version": VERSION,
    }
    boundaries = {
        "train_start": train["timestamp"].min().isoformat(),
        "train_end": train["timestamp"].max().isoformat(),
        "val_start": val["timestamp"].min().isoformat(),
        "val_end": val["timestamp"].max().isoformat(),
        "test_start": test["timestamp"].min().isoformat(),
        "test_end": test["timestamp"].max().isoformat(),
    }
    record_counts = {
        "input_rows": total,
        "total_rows": total,
        "train": n_train,
        "val": n_val,
        "test": n_test,
    }
    version_hash = compute_dataset_version_hash(
        feature_version=VERSION,
        label_version=VERSION,
        source_versions={TICKER: checksum},
        config=config_snapshot,
        feature_names=FEATURE_COLUMNS,
        split_boundaries=boundaries,
        record_counts=record_counts,
    )
    metadata = DatasetMetadata(
        version=VERSION,
        version_hash=version_hash,
        feature_version=VERSION,
        label_version=VERSION,
        source_versions={TICKER: checksum},
        created_at="2026-01-01T00:00:00",
        created_by="backtest-test",
        config_snapshot=config_snapshot,
        feature_names=FEATURE_COLUMNS,
        feature_count=len(FEATURE_COLUMNS),
        total_rows=total,
        train_rows=n_train,
        val_rows=n_val,
        test_rows=n_test,
        **boundaries,
        nan_count_total=0,
        label_distribution={
            "UP": labels.count("UP"),
            "DOWN": labels.count("DOWN"),
            "HOLD": labels.count("HOLD"),
        },
        quality_score=100.0,
        quality_rating="excellent",
        input_rows=total,
        dropped_warmup=0,
        dropped_invalid_label=0,
        dropped_out_of_range=0,
    )
    manifest = DatasetManifest(
        dataset_version=VERSION,
        version_hash=version_hash,
        source_versions={TICKER: checksum},
        feature_version=VERSION,
        label_version=VERSION,
        generation_time="2026-01-01T00:00:00",
        generation_code_version="backtest-test",
        row_counts={"input": total, "final": total},
        instruments=[TICKER],
        intervals=["1d"],
        date_range={
            "actual_start": boundaries["train_start"],
            "actual_end": boundaries["test_end"],
        },
        split_boundaries=boundaries,
        split_row_counts={"train": n_train, "val": n_val, "test": n_test},
        feature_count=len(FEATURE_COLUMNS),
        target_definition={"target_type": "classification"},
        quality_summary={"score": 100.0},
        build_report={"input_rows": total, "invalid_rows": 0},
    )
    write_dataset(
        processed,
        version=VERSION,
        metadata=metadata,
        manifest=manifest,
        feature_names=FEATURE_COLUMNS,
        train=train,
        val=val,
        test=test,
    )
    return config
