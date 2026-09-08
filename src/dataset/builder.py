"""Dataset Builder — aligns versioned features + labels into a training dataset.

Flow (DATASET_BUILDER_BLUEPRINT.md section 1.2):

    per-ticker persisted features (M04) + labels (M05)
        -> version/schema validation (fail loudly on mismatch)
        -> exact (ticker, timestamp) alignment
        -> drop invalid-label rows (recorded)
        -> drop feature warm-up rows (recorded)
        -> optional time-range filter
        -> DVAL frame validation -> chronological TRAIN/VAL/TEST split
           (ratios; purge/embargo config-gated, disabled for static MVP)
        -> split validation + quality score
        -> metadata + manifest + version hash
        -> immutable persistence (dataset_{version}/)

Rows never silently disappear: every drop reason is counted in the build
report and the manifest. X(T) rows carry label Y(T+H) from the label
engine; target timestamps are strictly after observations (DVAL-05).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.config.loader import AppConfig
from src.core.validation import validate_interval, validate_ticker
from src.dataset import quality as dataset_quality
from src.dataset import storage
from src.dataset.errors import (
    DatasetDataNotFoundError,
    DatasetError,
    FeatureVersionMismatchError,
    InvalidTimestampError,
    LabelVersionMismatchError,
    MissingFeatureError,
    MissingLabelError,
    SchemaMismatchError,
)
from src.dataset.metadata import DatasetManifest, DatasetMetadata, compute_dataset_version_hash
from src.dataset.split import split_chronologically
from src.dataset.validation import (
    DatasetValidationReport,
    validate_dataset_frame,
    validate_split,
)
from src.features import storage as feature_storage
from src.features.registry import FEATURE_COLUMNS
from src.labels import storage as label_storage
from src.labels.generator import VALID
from src.logging.logger import get_logger

logger = get_logger("dataset.builder")

VALID_CLASSES = frozenset({"UP", "DOWN", "HOLD"})
# Constant per-row version/metadata columns carried on every split frame.
VERSION_COLUMNS = (
    "dataset_version",
    "feature_set_version",
    "label_set_version",
    "source_data_version",
)
ROW_COLUMNS = (
    "ticker",
    "timestamp",
    *FEATURE_COLUMNS,
    "label",
    "future_return",
    "target_timestamp",
    *VERSION_COLUMNS,
)


@dataclass(frozen=True)
class DatasetBuildResult:
    """Outcome of one dataset build."""

    dataset_version: str
    version_hash: str
    tickers: tuple[str, ...]
    feature_version: str
    label_version: str
    interval: str
    requested_range: tuple[str | None, str | None]
    actual_range: tuple[str | None, str | None]
    input_rows: int
    dropped_warmup: int
    dropped_invalid_label: int
    missing_feature_count: int
    missing_label_count: int
    dropped_unmatched: int
    dropped_out_of_range: int
    total_rows: int
    split_rows: dict[str, int]
    validation: DatasetValidationReport
    quality: dataset_quality.DatasetQuality
    dataset_dir: Path
    duration_ms: float


class DatasetBuilder:
    """Assembles, validates, splits, and persists one dataset version."""

    def __init__(self, config: AppConfig, *, now: datetime | None = None) -> None:
        self.config = config
        # Naive-UTC storage policy (DATA_ARCHITECTURE.md section 4.2).
        self.now = now or datetime.now(timezone.utc).replace(tzinfo=None)

    # ------------------------------------------------------------------
    def run(
        self,
        *,
        tickers: list[str] | None = None,
        feature_version: str | None = None,
        label_version: str | None = None,
        dataset_version: str | None = None,
        interval: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> DatasetBuildResult:
        """Build one dataset version from persisted features + labels.

        Raises:
            DatasetError: subclasses for every explicit failure category —
                version mismatches, missing inputs, schema violations.
        """
        interval = validate_interval(interval or self.config.ingestion.interval)
        fversion = feature_version or self.config.features.version
        lversion = label_version or self.config.dataset.label_version
        dversion = dataset_version or self.config.dataset_builder.dataset_version
        ratios = dict(self.config.dataset.split_ratios)

        started = time.perf_counter()
        dataset_build_id = uuid.uuid4().hex
        requested_start = _parse_optional(start, "start")
        requested_end = _parse_optional(end, "end")
        if (
            requested_start is not None
            and requested_end is not None
            and requested_start > requested_end
        ):
            raise InvalidTimestampError(
                f"start {start} is after end {end}", context={"start": start, "end": end}
            )

        resolved_tickers = self._resolve_tickers(tickers, fversion, lversion)
        logger.info(
            "dataset_build_started",
            dataset_build_id=dataset_build_id,
            dataset_version=dversion,
            feature_version=fversion,
            label_version=lversion,
            interval=interval,
            tickers=list(resolved_tickers),
            requested_range=[start, end],
        )

        source_versions: dict[str, str] = {}
        parts: list[pd.DataFrame] = []
        input_rows = 0
        dropped_warmup = 0
        dropped_invalid_label = 0
        missing_feature_count = 0
        missing_label_count = 0
        dropped_unmatched = 0
        dropped_out_of_range = 0

        for ticker in resolved_tickers:
            loaded = self._load_ticker(ticker, fversion=fversion, lversion=lversion)
            source_versions[ticker] = loaded.source_checksum[:12]
            input_rows += loaded.input_rows
            dropped_warmup += loaded.dropped_warmup
            dropped_invalid_label += loaded.dropped_invalid_label
            missing_feature_count += loaded.missing_feature_count
            missing_label_count += loaded.missing_label_count
            dropped_unmatched += loaded.dropped_unmatched
            part = loaded.frame
            if requested_start is not None:
                dropped_out_of_range += int((part["timestamp"] < requested_start).sum())
                part = part[part["timestamp"] >= requested_start]
            if requested_end is not None:
                dropped_out_of_range += int((part["timestamp"] > requested_end).sum())
                part = part[part["timestamp"] <= requested_end]
            part = part.copy()
            part = part.assign(
                dataset_version=dversion,
                feature_set_version=fversion,
                label_set_version=lversion,
                source_data_version=loaded.source_checksum[:12],
            )
            parts.append(part[list(ROW_COLUMNS)])

        if not parts or not any(len(part) for part in parts):
            raise DatasetDataNotFoundError(
                "no usable dataset rows after feature/label alignment "
                "(check data volume vs feature warm-up and label horizon)",
                context={"tickers": list(resolved_tickers)},
            )

        frame = pd.concat(parts, ignore_index=True)
        frame = frame.sort_values(by=["timestamp", "ticker"]).reset_index(drop=True)

        frame_report = validate_dataset_frame(
            frame,
            expected_features=FEATURE_COLUMNS,
            required_columns=("ticker", "timestamp", *VERSION_COLUMNS),
        )
        if frame_report.errors:
            raise _first_error(frame_report)

        chronological = split_chronologically(
            frame,
            ratios=ratios,
            purging_enabled=self.config.dataset_builder.purging.enabled,
            embargo_enabled=self.config.dataset_builder.embargo.enabled,
            embargo_rows=self.config.dataset_builder.embargo.rows,
        )

        split_report = validate_split(
            (chronological.train, chronological.val, chronological.test),
            min_split_rows=dict(self.config.dataset_builder.min_split_rows),
        )
        if split_report.errors:
            raise _first_error(split_report)

        quality = self._compute_quality(frame, input_rows)
        if quality.score < self.config.dataset_builder.min_quality_score:
            logger.warning(
                "dataset_quality_below_gate",
                dataset_version=dversion,
                score=quality.score,
                min_score=self.config.dataset_builder.min_quality_score,
            )

        nan_total = int(frame[list(FEATURE_COLUMNS)].isna().sum().sum())
        label_distribution = {
            name: int((frame["label"] == name).sum()) for name in ("UP", "DOWN", "HOLD")
        }
        label_total = sum(label_distribution.values())
        label_distribution_pct = {
            name: round(count / label_total * 100.0, 4) if label_total else 0.0
            for name, count in label_distribution.items()
        }
        config_snapshot = self._config_snapshot(dversion, fversion, lversion, ratios, start, end)
        version_hash = compute_dataset_version_hash(
            feature_version=fversion,
            label_version=lversion,
            source_versions=source_versions,
            config=config_snapshot,
            feature_names=FEATURE_COLUMNS,
            split_boundaries=chronological.boundaries.to_dict(),
            record_counts={
                "input_rows": input_rows,
                "total_rows": len(frame),
                "train": len(chronological.train),
                "val": len(chronological.val),
                "test": len(chronological.test),
            },
        )

        metadata = DatasetMetadata(
            version=dversion,
            version_hash=version_hash,
            feature_version=fversion,
            label_version=lversion,
            source_versions=source_versions,
            created_at=self.now.isoformat(),
            created_by="pipeline",
            config_snapshot=config_snapshot,
            feature_names=FEATURE_COLUMNS,
            feature_count=len(FEATURE_COLUMNS),
            total_rows=len(frame),
            train_rows=len(chronological.train),
            val_rows=len(chronological.val),
            test_rows=len(chronological.test),
            **chronological.boundaries.to_dict(),
            nan_count_total=nan_total,
            label_distribution=label_distribution,
            quality_score=quality.score,
            quality_rating=quality.rating,
            input_rows=input_rows,
            dropped_warmup=dropped_warmup,
            dropped_invalid_label=dropped_invalid_label,
            missing_feature_count=missing_feature_count,
            missing_label_count=missing_label_count,
            dropped_out_of_range=dropped_out_of_range,
            dropped_unmatched=dropped_unmatched,
        )
        manifest = DatasetManifest(
            dataset_version=dversion,
            version_hash=version_hash,
            source_versions=source_versions,
            feature_version=fversion,
            label_version=lversion,
            generation_time=self.now.isoformat(),
            generation_code_version="dataset-builder-0.1.0",
            row_counts={"input": input_rows, "final": len(frame)},
            instruments=list(resolved_tickers),
            intervals=[interval],
            date_range=_date_range(frame, start, end),
            split_boundaries=chronological.boundaries.to_dict(),
            split_row_counts={
                "train": len(chronological.train),
                "val": len(chronological.val),
                "test": len(chronological.test),
            },
            feature_count=len(FEATURE_COLUMNS),
            target_definition={
                "label_name": "direction",
                "target_type": "classification",
                "horizon": self.config.dataset.label_window,
                "horizon_unit": "trading_days",
                "threshold_up": self.config.dataset.threshold_up,
                "threshold_down": self.config.dataset.threshold_down,
                "class_distribution": {
                    "counts": label_distribution,
                    "percentages": label_distribution_pct,
                },
            },
            quality_summary={
                "score": quality.score,
                "rating": quality.rating,
                "components": quality.components,
            },
            build_report={
                "input_rows": input_rows,
                "invalid_rows": dropped_invalid_label,
                "dropped_warmup": dropped_warmup,
                "dropped_invalid_label": dropped_invalid_label,
                "missing_feature_count": missing_feature_count,
                "missing_label_count": missing_label_count,
                "dropped_unmatched": dropped_unmatched,
                "dropped_out_of_range": dropped_out_of_range,
            },
        )

        directory = storage.write_dataset(
            self.config.data.processed_dir,
            version=dversion,
            metadata=metadata,
            manifest=manifest,
            feature_names=FEATURE_COLUMNS,
            train=chronological.train,
            val=chronological.val,
            test=chronological.test,
        )

        duration_ms = (time.perf_counter() - started) * 1000.0
        logger.info(
            "dataset_build_completed",
            dataset_build_id=dataset_build_id,
            dataset_version=dversion,
            version_hash=version_hash,
            tickers=list(resolved_tickers),
            input_rows=input_rows,
            total_rows=len(frame),
            dropped_warmup=dropped_warmup,
            dropped_invalid_label=dropped_invalid_label,
            missing_feature_count=missing_feature_count,
            missing_label_count=missing_label_count,
            dropped_unmatched=dropped_unmatched,
            dropped_out_of_range=dropped_out_of_range,
            train_rows=len(chronological.train),
            val_rows=len(chronological.val),
            test_rows=len(chronological.test),
            quality_score=quality.score,
            output_dir=str(directory),
            duration_ms=round(duration_ms, 1),
        )

        ts = pd.to_datetime(frame["timestamp"])
        return DatasetBuildResult(
            dataset_version=dversion,
            version_hash=version_hash,
            tickers=tuple(resolved_tickers),
            feature_version=fversion,
            label_version=lversion,
            interval=interval,
            requested_range=(start, end),
            actual_range=(ts.min().isoformat(), ts.max().isoformat()),
            input_rows=input_rows,
            dropped_warmup=dropped_warmup,
            dropped_invalid_label=dropped_invalid_label,
            missing_feature_count=missing_feature_count,
            missing_label_count=missing_label_count,
            dropped_unmatched=dropped_unmatched,
            dropped_out_of_range=dropped_out_of_range,
            total_rows=len(frame),
            split_rows={
                "train": len(chronological.train),
                "val": len(chronological.val),
                "test": len(chronological.test),
            },
            validation=_merge_reports(frame_report, split_report),
            quality=quality,
            dataset_dir=directory,
            duration_ms=round(duration_ms, 1),
        )

    # ------------------------------------------------------------------
    def _resolve_tickers(
        self, tickers: list[str] | None, fversion: str, lversion: str
    ) -> tuple[str, ...]:
        """Explicit tickers, or discovery from persisted feature+label sets."""
        if tickers:
            return tuple(sorted({validate_ticker(ticker) for ticker in tickers}))
        feature_dir = feature_storage.features_dir(self.config.data.processed_dir)
        found: set[str] = set()
        for path in feature_dir.glob(f"features_{fversion}_*.parquet"):
            ticker = path.stem.rsplit("_", 1)[-1]
            label_path = label_storage.label_file_path(
                self.config.data.processed_dir, lversion, ticker
            )
            if label_path.exists():
                found.add(ticker)
        if not found:
            raise DatasetDataNotFoundError(
                f"no tickers have both feature set {fversion} and label set {lversion}",
                context={"feature_version": fversion, "label_version": lversion},
            )
        return tuple(sorted(found))

    def _load_ticker(self, ticker: str, *, fversion: str, lversion: str) -> _TickerLoad:
        """Load + align one ticker's feature/label sets (exact timestamps)."""
        fpath = feature_storage.feature_file_path(self.config.data.processed_dir, fversion, ticker)
        lpath = label_storage.label_file_path(self.config.data.processed_dir, lversion, ticker)
        if not fpath.exists() or not lpath.exists():
            raise DatasetDataNotFoundError(
                f"missing feature/label artifact for {ticker} "
                f"(features {fversion}: {fpath.exists()}, "
                f"labels {lversion}: {lpath.exists()})",
                context={"ticker": ticker},
            )

        fmeta = feature_storage.read_metadata(
            feature_storage.metadata_file_path(self.config.data.processed_dir, fversion, ticker)
        )
        lmeta = label_storage.read_metadata(
            label_storage.metadata_file_path(self.config.data.processed_dir, lversion, ticker)
        )
        if fmeta.get("feature_set_version") != fversion:
            raise FeatureVersionMismatchError(
                f"persisted feature set for {ticker} is {fmeta.get('feature_set_version')!r}, "
                f"requested {fversion!r}",
                context={"ticker": ticker},
            )
        if lmeta.get("label_version") != lversion:
            raise LabelVersionMismatchError(
                f"persisted label set for {ticker} is {lmeta.get('label_version')!r}, "
                f"requested {lversion!r}",
                context={"ticker": ticker},
            )
        if lmeta.get("target_type") != "classification":
            raise LabelVersionMismatchError(
                f"label set for {ticker} has target_type {lmeta.get('target_type')!r}; "
                "the dataset builder supports classification only",
                context={"ticker": ticker},
            )
        if lmeta.get("horizon") != self.config.dataset.label_window:
            raise LabelVersionMismatchError(
                f"label horizon {lmeta.get('horizon')} does not match configured "
                f"label_window {self.config.dataset.label_window}",
                context={"ticker": ticker, "horizon": lmeta.get("horizon")},
            )
        if fmeta.get("source_checksum") != lmeta.get("source_checksum"):
            raise SchemaMismatchError(
                f"features and labels for {ticker} reference different source data "
                "(checksums differ); rebuild both from the same cleaned data",
                context={"ticker": ticker},
            )

        features = feature_storage.read_features(fpath)
        expected_columns = tuple(fmeta.get("feature_columns") or FEATURE_COLUMNS)
        if set(expected_columns) != set(FEATURE_COLUMNS) or len(expected_columns) != len(
            FEATURE_COLUMNS
        ):
            raise MissingFeatureError(
                f"feature set for {ticker} does not contain the expected 52 columns",
                context={"ticker": ticker, "feature_columns": len(expected_columns)},
            )
        non_numeric = [
            column
            for column in FEATURE_COLUMNS
            if not pd.api.types.is_numeric_dtype(features[column])
        ]
        if non_numeric:
            raise SchemaMismatchError(
                f"feature set for {ticker} contains non-numeric columns {non_numeric}",
                context={"ticker": ticker, "columns": non_numeric},
            )
        features = features.reindex(columns=list(FEATURE_COLUMNS))

        labels = label_storage.read_labels(lpath)
        for column in ("label", "status", "future_return", "target_timestamp"):
            if column not in labels.columns:
                raise MissingLabelError(
                    f"label set for {ticker} missing column {column!r}",
                    context={"ticker": ticker},
                )

        # Exact (ticker, timestamp) alignment via index intersection.
        common = features.index.intersection(labels.index)
        unmatched = (len(features) - len(common)) + (len(labels) - len(common))
        aligned = features.loc[common].copy()
        aligned_labels = labels.loc[common].copy()

        valid_mask = aligned_labels["status"].eq(VALID) & aligned_labels["label"].isin(
            VALID_CLASSES
        )
        future_return = pd.to_numeric(aligned_labels["future_return"], errors="coerce")
        valid_mask &= future_return.notna() & pd.Series(
            np.isfinite(future_return.to_numpy()), index=future_return.index
        )
        valid_mask &= pd.to_datetime(aligned_labels["target_timestamp"], errors="coerce").notna()
        invalid_label_count = int((~valid_mask).sum())

        warmup_mask = aligned.loc[valid_mask, list(FEATURE_COLUMNS)].isna().any(axis=1)
        warmup_count = int(warmup_mask.sum())
        keep = aligned.index[valid_mask][~warmup_mask.values]

        frame = pd.DataFrame(
            {
                "ticker": ticker,
                "timestamp": pd.to_datetime(keep),
                **{
                    column: aligned.loc[keep, column].astype("float64")
                    for column in FEATURE_COLUMNS
                },
                "label": aligned_labels.loc[keep, "label"].astype("object"),
                "future_return": aligned_labels.loc[keep, "future_return"].astype("float64"),
                "target_timestamp": pd.to_datetime(
                    aligned_labels.loc[keep, "target_timestamp"], errors="coerce"
                ),
            }
        )
        return _TickerLoad(
            frame=frame.reset_index(drop=True),
            input_rows=len(features),
            dropped_warmup=warmup_count,
            dropped_invalid_label=invalid_label_count,
            missing_feature_count=warmup_count,
            missing_label_count=invalid_label_count,
            dropped_unmatched=unmatched,
            source_checksum=fmeta["source_checksum"],
        )

    # ------------------------------------------------------------------
    def _compute_quality(
        self, frame: pd.DataFrame, input_rows: int
    ) -> dataset_quality.DatasetQuality:
        feature_nan = int(frame[list(FEATURE_COLUMNS)].isna().sum().sum())
        invalid_labels = int((~frame["label"].isin(VALID_CLASSES)).sum())
        ts = pd.to_datetime(frame["timestamp"])
        return dataset_quality.compute_dataset_quality(
            total_candidate_rows=max(input_rows, 1),
            final_rows=len(frame),
            feature_nan_cells=feature_nan,
            final_feature_cells=len(frame) * len(FEATURE_COLUMNS),
            invalid_label_rows=invalid_labels,
            ordered_ascending=bool(ts.is_monotonic_increasing),
            unique_rows=(int(frame.duplicated(subset=["ticker", "timestamp"]).sum()) == 0),
            schema_exact=set(FEATURE_COLUMNS).issubset(frame.columns),
        )

    def _config_snapshot(
        self, dversion: str, fversion: str, lversion: str, ratios: dict, start, end
    ) -> dict:
        return {
            "dataset_version": dversion,
            "feature_version": fversion,
            "label_version": lversion,
            "split_ratios": {k: ratios[k] for k in ("train", "val", "test")},
            "requested_start": start,
            "requested_end": end,
            "label_window": self.config.dataset.label_window,
            "thresholds": {
                "up": self.config.dataset.threshold_up,
                "down": self.config.dataset.threshold_down,
            },
            "purging_enabled": self.config.dataset_builder.purging.enabled,
            "embargo_enabled": self.config.dataset_builder.embargo.enabled,
            "embargo_rows": self.config.dataset_builder.embargo.rows,
        }


@dataclass(frozen=True)
class _TickerLoad:
    """Aligned, filtered rows for one ticker + drop accounting."""

    frame: pd.DataFrame
    input_rows: int
    dropped_warmup: int
    dropped_invalid_label: int
    missing_feature_count: int
    missing_label_count: int
    dropped_unmatched: int
    source_checksum: str


def _parse_optional(raw: str | None, name: str):
    if raw is None:
        return None
    try:
        return pd.Timestamp(raw)
    except (ValueError, TypeError):
        raise InvalidTimestampError(
            f"invalid {name} date {raw!r}: expected ISO date", context={"value": raw}
        ) from None


def _date_range(frame: pd.DataFrame, start: str | None, end: str | None) -> dict:
    ts = pd.to_datetime(frame["timestamp"])
    return {
        "requested_start": start,
        "requested_end": end,
        "actual_start": ts.min().isoformat() if len(ts) else None,
        "actual_end": ts.max().isoformat() if len(ts) else None,
    }


def _merge_reports(
    a: DatasetValidationReport, b: DatasetValidationReport
) -> DatasetValidationReport:
    return DatasetValidationReport(
        checks_run=a.checks_run + b.checks_run,
        checks_passed=a.checks_passed + b.checks_passed,
        issues=a.issues + b.issues,
    )


def _first_error(report: DatasetValidationReport) -> DatasetError:
    issue = report.errors[0]
    return SchemaMismatchError(
        f"dataset validation failed [{issue.check_id}]: {issue.description}",
        context={"check_id": issue.check_id, "recommendation": issue.recommendation},
    )
