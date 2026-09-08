"""Feature engine — orchestrates computation, validation, and persistence.

Flow (FEATURE_ENGINEERING_BLUEPRINT.md section 19.3):

    cleaned interim CSV
        -> load + timestamp alignment
        -> compute all 52 features (backward-looking only)
        -> FVAL validation (errors fail the run, never silent zeros)
        -> feature-set metadata + version hash
        -> persist Parquet + metadata + hash (conflict-protected)

Input is the interim-tier cleaned output of Milestone 03 (cleaned data
is never modified here). Output is a versioned, immutable feature
dataset under ``data/processed/features/``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.cleaning.io import find_latest_cleaned, load_cleaned_csv
from src.config.loader import AppConfig, FeatureConfig
from src.core.errors import ValidationError
from src.core.validation import validate_interval, validate_ticker
from src.features import compute, storage
from src.features import metadata as feature_metadata
from src.features.registry import FEATURE_COLUMNS, feature_count, max_lookback
from src.features.validation import FeatureValidationReport, validate_features
from src.logging.logger import get_logger

logger = get_logger("features.engine")

__all__ = ["FeatureEngine", "FeatureRunResult", "find_latest_cleaned"]


@dataclass(frozen=True)
class FeatureRunResult:
    """Outcome of one feature-generation run."""

    ticker: str
    interval: str
    feature_set_version: str
    version_hash: str
    source_file: Path
    source_checksum: str
    row_count: int
    feature_count: int
    max_lookback: int
    warmup_rows: int  # rows with any NaN (insufficient lookback)
    validation: FeatureValidationReport
    output_file: Path
    duration_ms: float


class FeatureEngine:
    """Computes, validates, and persists one feature dataset."""

    def __init__(self, config: AppConfig, *, now: datetime | None = None) -> None:
        self.config = config
        self.features: FeatureConfig = config.features
        # Naive-UTC storage policy (DATA_ARCHITECTURE.md section 4.2).
        self.now = now or datetime.now(timezone.utc).replace(tzinfo=None)

    # ------------------------------------------------------------------
    def run(
        self,
        ticker: str,
        interval: str,
        *,
        source: Path | None = None,
        feature_version: str | None = None,
    ) -> FeatureRunResult:
        """Generate the feature dataset for one (ticker, interval).

        Args:
            ticker: canonical ticker (e.g. ``AAPL``).
            interval: approved candle interval (``1d``).
            source: cleaned interim CSV; when omitted, the latest
                cleaned file for the ticker is used.
            feature_version: feature-set version; defaults to config.

        Raises:
            ValidationError: on invalid inputs or failing FVAL checks
                (never persist obviously corrupt features).
            StorageError: when inputs are missing or a persisted dataset
                conflicts with a re-generation.
        """
        ticker = validate_ticker(ticker)
        interval = validate_interval(interval)
        version = feature_version or self.features.version

        started = time.perf_counter()
        source_path = source or find_latest_cleaned(self.config.data.interim_dir, ticker, interval)
        source_checksum = storage.sha256_of(source_path)
        frame = self._load_cleaned(source_path)

        logger.info(
            "feature_generation_started",
            ticker=ticker,
            interval=interval,
            feature_set_version=version,
            source_file=str(source_path),
            source_checksum=source_checksum,
            input_rows=len(frame),
        )

        features = compute.compute_features(frame)
        report = validate_features(
            features,
            max_nan_ratio=self.features.validation.max_nan_ratio,
            max_infinite=self.features.validation.max_infinite,
            check_bounded_ranges=self.features.validation.check_bounded_ranges,
            outlier_zscore_threshold=self.features.validation.outlier_zscore_threshold,
        )
        if report.errors:
            raise ValidationError(
                "feature validation failed; generation aborted (no partial output)",
                context={
                    "errors": [
                        {
                            "check_id": issue.check_id,
                            "feature": issue.feature,
                            "message": issue.message,
                        }
                        for issue in report.errors
                    ]
                },
            )

        version_hash = feature_metadata.compute_feature_version_hash(FEATURE_COLUMNS)
        metadata = feature_metadata.feature_set_metadata(
            version=version,
            version_hash=version_hash,
            ticker=ticker,
            source_file=str(source_path),
            source_checksum=source_checksum,
            row_count=len(features),
            now=self.now,
        )
        output_file = storage.write_features(
            self.config.data.processed_dir,
            features,
            version=version,
            ticker=ticker,
            metadata=metadata,
            output_format=self.features.output_format,
        )

        warmup_rows = int(features.isna().any(axis=1).sum())
        duration_ms = (time.perf_counter() - started) * 1000.0
        logger.info(
            "feature_generation_completed",
            ticker=ticker,
            feature_set_version=version,
            version_hash=version_hash,
            row_count=len(features),
            feature_count=feature_count(),
            warmup_rows=warmup_rows,
            output_file=str(output_file),
            duration_ms=round(duration_ms, 1),
            validation_warnings=len(report.warnings),
        )

        return FeatureRunResult(
            ticker=ticker,
            interval=interval,
            feature_set_version=version,
            version_hash=version_hash,
            source_file=source_path,
            source_checksum=source_checksum,
            row_count=len(features),
            feature_count=feature_count(),
            max_lookback=max_lookback(),
            warmup_rows=warmup_rows,
            validation=report,
            output_file=output_file,
            duration_ms=round(duration_ms, 1),
        )

    # ------------------------------------------------------------------
    def _load_cleaned(self, path: Path):
        """Load a cleaned interim CSV via the shared cleaned-tier reader."""
        return load_cleaned_csv(path)
