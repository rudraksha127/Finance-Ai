"""Cleaning pipeline orchestrator — DATA_CLEANING_VALIDATION.md §1.3.

Stage state machine: LOADING → SCHEMA_VALIDATE → DATA_VALIDATE →
CLEANING → NORMALIZE → QUALITY_SCORE → STORING → COMPLETED (any stage
may transition to FAILED, which raises loudly).

Input is a raw-tier CSV (Milestone 02 output). The raw file is never
written to; cleaned, normalized rows are written to the interim tier
with a SHA-256 and a full audit record.

Normalization (§1.2 stage 5): standard column set, naive-UTC timestamps
(already naive from the raw store), ascending sort, float prices, int
volume, uppercased validated ticker, interval label.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.cleaning import audit, io
from src.cleaning.actions import AdjustmentSummary, apply_actions, load_actions
from src.cleaning.cleaning import CleaningStats, clean_batch
from src.cleaning.quality import compute_quality
from src.cleaning.validation import ValidationOptions, ValidationReport, validate_batch
from src.config.loader import AppConfig, CleaningConfig
from src.core.errors import StorageError, ValidationError
from src.core.validation import validate_interval, validate_ticker
from src.data.store import raw_file_path

CLEANING_STAGES = (
    "LOADING",
    "SCHEMA_VALIDATE",
    "DATA_VALIDATE",
    "CLEANING",
    "NORMALIZE",
    "QUALITY_SCORE",
    "STORING",
    "COMPLETED",
)


@dataclass(frozen=True)
class PipelineResult:
    """Outcome of a cleaning run (fed to the audit record + CLI)."""

    ticker: str
    interval: str
    raw_file: Path
    raw_hash: str
    raw_rows: int
    cleaned_rows: int
    validation: ValidationReport
    cleaning_stats: CleaningStats
    quality: Any  # DataQualityReport
    adjustment: AdjustmentSummary
    output_file: Path
    output_hash: str
    audit_id: str
    audit_file: Path
    duration_ms: float
    stages: tuple[str, ...] = field(default_factory=tuple)


class CleaningPipeline:
    """Runs the cleaning + quality pipeline for one (ticker, interval)."""

    def __init__(self, config: AppConfig, *, now: datetime | None = None) -> None:
        self.config = config
        self.cleaning: CleaningConfig = config.cleaning
        # Naive-UTC storage policy (DATA_ARCHITECTURE.md section 4.2).
        self.now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        self.stages: list[str] = []

    # ------------------------------------------------------------------
    def run(self, ticker: str, interval: str) -> PipelineResult:
        """Clean one (ticker, interval) from the raw tier to the interim tier."""
        try:
            ticker = validate_ticker(ticker)
            interval = validate_interval(interval)
        except ValidationError as error:
            raise StorageError(f"invalid cleaning request: {error.message}") from error

        started = time.perf_counter()
        self._enter("LOADING")

        raw_path = raw_file_path(self.config.data.raw_dir, ticker, interval)
        raw_hash = io.sha256_of(raw_path)
        records, reader_issues = io.read_raw_csv(raw_path)
        raw_rows = len(records) + sum(
            1 for issue in reader_issues if issue.get("rule_id") == "VAL-S04"
        )

        self._enter("SCHEMA_VALIDATE")
        options = ValidationOptions(
            min_rows=self.cleaning.min_rows,
            max_missing_pct=self.cleaning.validation.max_missing_pct,
            max_price_change_pct=self.cleaning.validation.max_price_change_pct,
            holidays=io.load_holidays(self.cleaning.holidays_file, self.config.data.external_dir),
        )

        self._enter("DATA_VALIDATE")
        validation = validate_batch(records, reader_issues, options=options, now=self.now)

        self._enter("CLEANING")
        cleaned, stats = clean_batch(
            records,
            duplicate_strategy=self.cleaning.cleaning.duplicate_strategy,
            missing_fill_limit=self.cleaning.cleaning.missing_fill_limit,
            interpolate_max_gap=self.cleaning.cleaning.interpolate_max_gap,
            outlier_zscore_threshold=self.cleaning.cleaning.outlier_zscore_threshold,
            rejected_raw_lines=validation.rejected_raw_lines,
        )

        # Corporate-action backward adjustment (raw never modified).
        # Optional conventional file: data/external/corporate_actions/{TICKER}.json
        actions_path = (
            self.config.data.external_dir / "corporate_actions" / f"{ticker}.json"
            if self.cleaning.cleaning.apply_corporate_actions
            else None
        )
        actions = load_actions(actions_path)
        cleaned, adjustment = apply_actions(cleaned, actions, now=self.now)

        self._enter("NORMALIZE")
        normalized = _normalize(cleaned, ticker, interval)

        self._enter("QUALITY_SCORE")
        weights = dict(self.cleaning.quality.weights)
        quality = compute_quality(
            normalized,
            validation,
            ticker=ticker,
            weights=weights,
            freshness_max_days=self.cleaning.quality.freshness_max_days,
            now=self.now,
        )

        self._enter("STORING")
        output_file = io.write_interim_csv(
            self.config.data.interim_dir,
            normalized,
            ticker,
            interval,
            run_date=self.now.date(),
        )
        output_hash = io.sha256_of(output_file)

        duration_ms = (time.perf_counter() - started) * 1000.0
        audit_id = audit.new_audit_id()
        audit_file = audit.write_audit_record(
            self.config.data.interim_dir,
            self._build_audit(
                audit_id,
                ticker,
                interval,
                raw_path,
                raw_hash,
                raw_rows,
                output_file,
                output_hash,
                len(normalized),
                quality.overall_score,
                quality.rating,
                validation,
                stats,
                adjustment,
                duration_ms,
            ),
        )
        self._enter("COMPLETED")

        return PipelineResult(
            ticker=ticker,
            interval=interval,
            raw_file=raw_path,
            raw_hash=raw_hash,
            raw_rows=raw_rows,
            cleaned_rows=len(normalized),
            validation=validation,
            cleaning_stats=stats,
            quality=quality,
            adjustment=adjustment,
            output_file=output_file,
            output_hash=output_hash,
            audit_id=audit_id,
            audit_file=audit_file,
            duration_ms=round(duration_ms, 1),
            stages=tuple(self.stages),
        )

    # ------------------------------------------------------------------
    def _enter(self, stage: str) -> None:
        self.stages.append(stage)

    def _build_audit(
        self,
        audit_id: str,
        ticker: str,
        interval: str,
        raw_path: Path,
        raw_hash: str,
        raw_rows: int,
        output_file: Path,
        output_hash: str,
        output_rows: int,
        quality_score: float,
        quality_rating: str,
        validation: ValidationReport,
        stats: CleaningStats,
        adjustment: AdjustmentSummary,
        duration_ms: float,
    ) -> audit.AuditRecord:
        transformations = [
            audit.TransformationStep(
                step=1,
                name="schema_validation",
                rule_id="VAL-S01..S04",
                input_rows=raw_rows,
                output_rows=raw_rows,
                rows_affected=0,
                strategy="reject_file",
                details={"issues": validation.errors},
            ),
            audit.TransformationStep(
                step=2,
                name="data_validation",
                rule_id="VAL-P/V/T/C",
                input_rows=raw_rows,
                output_rows=stats.output_rows,
                rows_affected=stats.rejected_dropped,
                strategy="reject_row",
                details={
                    "errors": validation.errors,
                    "warnings": validation.warnings,
                    "rejected_raw_lines": sorted(validation.rejected_raw_lines),
                },
            ),
            audit.TransformationStep(
                step=3,
                name="duplicate_removal",
                rule_id="VAL-T01",
                input_rows=stats.input_rows,
                output_rows=stats.input_rows - stats.duplicates_removed,
                rows_affected=stats.duplicates_removed,
                strategy=self.cleaning.cleaning.duplicate_strategy,
            ),
            audit.TransformationStep(
                step=4,
                name="ohlc_fix",
                rule_id="VAL-P05/P06",
                input_rows=stats.input_rows,
                output_rows=stats.input_rows,
                rows_affected=stats.ohlc_fixed,
                strategy="repair",
            ),
            audit.TransformationStep(
                step=5,
                name="missing_data",
                rule_id="CLEAN-FF/CLEAN-IP",
                input_rows=stats.input_rows,
                output_rows=stats.input_rows - stats.dropped_missing,
                rows_affected=stats.forward_filled
                + stats.interpolated
                + stats.volume_zero_filled
                + stats.dropped_missing,
                strategy="forward_fill+interpolate+zero_fill",
                details={
                    "forward_filled": stats.forward_filled,
                    "interpolated": stats.interpolated,
                    "volume_zero_filled": stats.volume_zero_filled,
                    "marked_incomplete": stats.marked_incomplete,
                    "dropped_missing": stats.dropped_missing,
                },
            ),
            audit.TransformationStep(
                step=6,
                name="corporate_actions",
                rule_id="CA-SPLIT/CA-DIV",
                input_rows=stats.output_rows,
                output_rows=stats.output_rows,
                rows_affected=adjustment.total_rows_adjusted,
                strategy="backward_adjust",
                details={
                    "actions_applied": adjustment.actions_applied,
                    "outcomes": [
                        {
                            "type": outcome.action["type"],
                            "effective_date": str(outcome.action["effective_date"]),
                            "rows_affected": outcome.rows_affected,
                            "factor": outcome.factor,
                        }
                        for outcome in adjustment.outcomes
                    ],
                },
            ),
            audit.TransformationStep(
                step=7,
                name="outlier_flag",
                rule_id="CLEAN-OUTLIER",
                input_rows=stats.output_rows,
                output_rows=stats.output_rows,
                rows_affected=stats.outliers_flagged,
                strategy="flag_kept",
            ),
            audit.TransformationStep(
                step=8,
                name="normalization",
                rule_id="NORM",
                input_rows=stats.output_rows,
                output_rows=output_rows,
                rows_affected=0,
                strategy="sort+cast+validate",
            ),
        ]
        return audit.AuditRecord(
            audit_id=audit_id,
            ticker=ticker,
            interval=interval,
            raw_file_path=str(raw_path),
            raw_file_hash=raw_hash,
            raw_row_count=raw_rows,
            transformations=tuple(transformations),
            output_file_path=str(output_file),
            output_file_hash=output_hash,
            output_row_count=output_rows,
            quality_score=quality_score,
            quality_rating=quality_rating,
            validation_errors=validation.errors,
            validation_warnings=validation.warnings,
            started_at=self.now.isoformat(),
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            duration_ms=round(duration_ms, 1),
            pipeline_version=self.cleaning.pipeline_version,
            config_snapshot={
                "duplicate_strategy": self.cleaning.cleaning.duplicate_strategy,
                "missing_fill_limit": self.cleaning.cleaning.missing_fill_limit,
                "interpolate_max_gap": self.cleaning.cleaning.interpolate_max_gap,
                "outlier_zscore_threshold": self.cleaning.cleaning.outlier_zscore_threshold,
                "apply_corporate_actions": self.cleaning.cleaning.apply_corporate_actions,
                "quality_weights": dict(self.cleaning.quality.weights),
                "quality_min_score": self.cleaning.quality.min_score,
            },
        )


def _normalize(records: list[dict[str, Any]], ticker: str, interval: str) -> list[dict[str, Any]]:
    """Normalization §1.2 stage 5: standard columns, sort, casts, identity."""
    normalized: list[dict[str, Any]] = []
    for record in records:
        normalized.append(
            {
                "ticker": ticker,
                "timestamp": record["timestamp"],
                "open": float(record["open"]),
                "high": float(record["high"]),
                "low": float(record["low"]),
                "close": float(record["close"]),
                "adj_close": (
                    float(record["adj_close"]) if record.get("adj_close") is not None else None
                ),
                "volume": int(float(record["volume"])),
                "raw_line": record["raw_line"],
                "incomplete": record.get("incomplete", False),
                "outlier_flagged": record.get("outlier_flagged", False),
                "adjustments": record.get("adjustments", []),
            }
        )
    normalized.sort(key=lambda record: record["timestamp"])
    return normalized
