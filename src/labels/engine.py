"""Label engine — orchestrates generation, validation, and persistence.

Flow (LABEL_GENERATION_BLUEPRINT.md section 11):

    cleaned interim CSV
        -> load + timestamp alignment
        -> generate direction labels (future return over horizon H)
        -> distribution check (class balance logged, never auto-tuned)
        -> label metadata + version hash
        -> persist Parquet + metadata + hash (conflict-protected)

Input is the interim-tier cleaned output of Milestone 03 — the label
engine only *reads* it and never touches feature values (mandatory
leakage TEST A). Output is a versioned label set under
``data/processed/labels/``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.cleaning.io import find_latest_cleaned, load_cleaned_csv
from src.config.loader import AppConfig, LabelConfig
from src.core.errors import ValidationError
from src.core.validation import validate_interval, validate_ticker
from src.labels import metadata as label_metadata
from src.labels import storage
from src.labels.generator import LabelDistribution, LabelResult, generate_labels
from src.logging.logger import get_logger

logger = get_logger("labels.engine")

# Acceptable class-balance ranges (blueprint section 7.3 / 14).
ACCEPTABLE_UP_RANGE = (25.0, 45.0)
ACCEPTABLE_DOWN_RANGE = (25.0, 45.0)
ACCEPTABLE_HOLD_RANGE = (20.0, 50.0)


@dataclass(frozen=True)
class LabelRunResult:
    """Outcome of one label-generation run."""

    ticker: str
    interval: str
    label_version: str
    version_hash: str
    horizon: int
    threshold_up: float
    threshold_down: float
    source_file: Path
    source_checksum: str
    row_count: int
    distribution: LabelDistribution
    output_file: Path
    balance_warnings: tuple[str, ...] = field(default_factory=tuple)
    duration_ms: float = 0.0


class LabelEngine:
    """Generates, validates, and persists one direction label set."""

    def __init__(self, config: AppConfig, *, now: datetime | None = None) -> None:
        self.config = config
        self.labels: LabelConfig = config.dataset
        # Naive-UTC storage policy (DATA_ARCHITECTURE.md section 4.2).
        self.now = now or datetime.now(timezone.utc).replace(tzinfo=None)

    # ------------------------------------------------------------------
    def run(
        self,
        ticker: str,
        interval: str,
        *,
        source: Path | None = None,
        label_version: str | None = None,
        horizon: int | None = None,
    ) -> LabelRunResult:
        """Generate the label set for one (ticker, interval).

        Args:
            ticker: canonical ticker (e.g. ``AAPL``).
            interval: approved candle interval (``1d``).
            source: cleaned interim CSV; defaults to the latest cleaned
                file for the ticker.
            label_version: label-set version; defaults to config.
            horizon: prediction horizon in trading days; defaults to
                config ``dataset.label_window`` (5).

        Raises:
            ValidationError: on invalid inputs or a price column that
                cannot produce labels.
            StorageError: when inputs are missing or a persisted label
                set conflicts with a re-generation.
        """
        ticker = validate_ticker(ticker)
        interval = validate_interval(interval)
        version = label_version or self.labels.label_version
        horizon = horizon if horizon is not None else self.labels.label_window
        if horizon <= 0:
            raise ValidationError("label horizon must be > 0", context={"horizon": horizon})

        started = time.perf_counter()
        source_path = source or self._latest_cleaned(ticker, interval)
        source_checksum = storage.sha256_of(source_path)
        frame = load_cleaned_csv(source_path)

        price_column = self.labels.price_column
        if price_column not in frame.columns:
            raise ValidationError(
                f"price column {price_column!r} not present in {source_path}",
                context={"path": str(source_path), "price_column": price_column},
            )

        logger.info(
            "label_generation_started",
            ticker=ticker,
            interval=interval,
            label_version=version,
            horizon=horizon,
            threshold_up=self.labels.threshold_up,
            threshold_down=self.labels.threshold_down,
            source_file=str(source_path),
            input_rows=len(frame),
        )

        result: LabelResult = generate_labels(
            frame,
            horizon=horizon,
            threshold_up=self.labels.threshold_up,
            threshold_down=self.labels.threshold_down,
            price_column=price_column,
        )

        balance_warnings = self._check_balance(result.distribution)

        version_hash = label_metadata.compute_label_version_hash(
            horizon=horizon,
            threshold_up=self.labels.threshold_up,
            threshold_down=self.labels.threshold_down,
            price_column=price_column,
        )
        metadata = label_metadata.label_metadata(
            version=version,
            version_hash=version_hash,
            ticker=ticker,
            horizon=horizon,
            threshold_up=self.labels.threshold_up,
            threshold_down=self.labels.threshold_down,
            source_column=price_column,
            source_file=str(source_path),
            source_checksum=source_checksum,
            distribution=result.distribution,
            now=self.now,
        )

        # Persisted frame: identity + target columns only (never features).
        persisted = self._build_persist_frame(frame, result, horizon)

        output_file = storage.write_labels(
            self.config.data.processed_dir,
            persisted,
            version=version,
            ticker=ticker,
            metadata=metadata,
            output_format="parquet",
        )

        duration_ms = (time.perf_counter() - started) * 1000.0
        dist = result.distribution
        logger.info(
            "label_generation_completed",
            ticker=ticker,
            label_version=version,
            version_hash=version_hash,
            horizon=horizon,
            row_count=dist.total_rows,
            valid_rows=dist.valid_rows,
            up_count=dist.up_count,
            down_count=dist.down_count,
            hold_count=dist.hold_count,
            invalid_count=dist.invalid_count,
            invalid_future_window=dist.invalid_future_window,
            invalid_price=dist.invalid_price,
            output_file=str(output_file),
            duration_ms=round(duration_ms, 1),
        )
        for warning in balance_warnings:
            logger.warning("label_class_balance", ticker=ticker, message=warning)

        return LabelRunResult(
            ticker=ticker,
            interval=interval,
            label_version=version,
            version_hash=version_hash,
            horizon=horizon,
            threshold_up=self.labels.threshold_up,
            threshold_down=self.labels.threshold_down,
            source_file=source_path,
            source_checksum=source_checksum,
            row_count=dist.total_rows,
            distribution=dist,
            output_file=output_file,
            balance_warnings=tuple(balance_warnings),
            duration_ms=round(duration_ms, 1),
        )

    # ------------------------------------------------------------------
    def _latest_cleaned(self, ticker: str, interval: str) -> Path:
        return find_latest_cleaned(self.config.data.interim_dir, ticker, interval)

    @staticmethod
    def _build_persist_frame(
        frame: pd.DataFrame, result: LabelResult, horizon: int
    ) -> pd.DataFrame:
        """Compose the persisted label frame (timestamp index + target data).

        Columns: ``target_timestamp`` (the observation at T+H), the raw
        future price, the future return, the class label, and the row
        status. No source OHLCV or feature columns are included (leakage
        TEST E: target data never contaminates feature storage).
        """
        out = result.frame.copy()
        target_ts = pd.Series(frame.index, index=frame.index).shift(-horizon)
        out["target_timestamp"] = target_ts
        return out

    @staticmethod
    def _check_balance(distribution: LabelDistribution) -> list[str]:
        """Flag class distributions outside acceptable ranges (never auto-tune)."""
        warnings: list[str] = []
        if distribution.valid_rows == 0:
            return ["no valid labels generated; check horizon vs data length"]
        up, down, hold = distribution.up_pct, distribution.down_pct, distribution.hold_pct
        if not ACCEPTABLE_UP_RANGE[0] <= up <= ACCEPTABLE_UP_RANGE[1]:
            warnings.append(
                f"UP share {up:.1f}% outside acceptable {ACCEPTABLE_UP_RANGE}; "
                "consider horizon/threshold review (never auto-tuned)"
            )
        if not ACCEPTABLE_DOWN_RANGE[0] <= down <= ACCEPTABLE_DOWN_RANGE[1]:
            warnings.append(
                f"DOWN share {down:.1f}% outside acceptable {ACCEPTABLE_DOWN_RANGE}; "
                "consider horizon/threshold review (never auto-tuned)"
            )
        if not ACCEPTABLE_HOLD_RANGE[0] <= hold <= ACCEPTABLE_HOLD_RANGE[1]:
            warnings.append(
                f"HOLD share {hold:.1f}% outside acceptable {ACCEPTABLE_HOLD_RANGE}; "
                "consider horizon/threshold review (never auto-tuned)"
            )
        return warnings
