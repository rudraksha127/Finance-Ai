"""Configuration types and loading for the autonomous data-growth pipeline.

The autonomous layer adds one new configuration section:
`pipeline:` with scheduler, watermark, incremental, retry, quality, and
dataset-policy knobs. This module intentionally does not duplicate the
existing ingestion/cleaning/features/labels/dataset configuration; it composes
them into a scheduled/autonomous run policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from pathlib import Path
from typing import TypedDict

from src.config.loader import AppConfig


class PipelineScheduleKind(TypedDict, total=False):
    cron: str | None
    interval_minutes: int | None


@dataclass(slots=True)
class PipelineSchedule:
    kind: str = "manual"  # manual | cron | interval
    cron: str | None = None
    interval_minutes: int | None = None
    timezone: str = "UTC"


@dataclass(slots=True)
class PipelineIncrementalPolicy:
    enabled: bool = True
    overlap_window_business_days: int = 0
    gap_allowed_max_consecutive_days: int = 0  # 0 = do not auto-fill gaps, just report
    skip_if_up_to_date: bool = True
    skip_if_no_new_trading_days: bool = True


@dataclass(slots=True)
class PipelineRetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    retry_transient_only: bool = True


@dataclass(slots=True)
class PipelineQualityPolicy:
    enabled: bool = True
    min_quality_score: float = 70.0


@dataclass(slots=True)
class PipelineDatasetPolicy:
    # How dataset growth is versioned during autonomous runs.
    version_mode: str = "bump_on_material_change"
    min_new_rows_to_bump: int = 1
    preserve_prior_versions: bool = True


@dataclass(slots=True)
class PipelineConfig:
    schedule: PipelineSchedule = field(default_factory=PipelineSchedule)
    instruments: list[str] = field(default_factory=list)
    intervals: list[str] = field(default_factory=lambda: ["1d"])
    incremental: PipelineIncrementalPolicy = field(default_factory=PipelineIncrementalPolicy)
    retry: PipelineRetryPolicy = field(default_factory=PipelineRetryPolicy)
    quality: PipelineQualityPolicy = field(default_factory=PipelineQualityPolicy)
    dataset: PipelineDatasetPolicy = field(default_factory=PipelineDatasetPolicy)
    dry_run: bool = False
    run_label_finalization: bool = True
    lock_timeout_seconds: int = 60

    @property
    def effective_instruments(self) -> list[str]:
        if self.instruments:
            return list(self.instruments)
        return []

    @property
    def effective_intervals(self) -> list[str]:
        return list(self.intervals) or ["1d"]


def parse_pipeline_schedule(raw: dict | None) -> PipelineSchedule:
    if not raw:
        return PipelineSchedule()
    return PipelineSchedule(
        kind=str(raw.get("kind", "manual")),
        cron=raw.get("cron"),
        interval_minutes=int(raw.get("interval_minutes") or 0) or None,
        timezone=str(raw.get("timezone", "UTC")),
    )


def parse_pipeline_incremental(raw: dict | None) -> PipelineIncrementalPolicy:
    if not raw:
        return PipelineIncrementalPolicy()
    return PipelineIncrementalPolicy(
        enabled=bool(raw.get("enabled", True)),
        overlap_window_business_days=int(raw.get("overlap_window_business_days", 0)),
        gap_allowed_max_consecutive_days=int(raw.get("gap_allowed_max_consecutive_days", 0)),
        skip_if_up_to_date=bool(raw.get("skip_if_up_to_date", True)),
        skip_if_no_new_trading_days=bool(raw.get("skip_if_no_new_trading_days", True)),
    )


def parse_pipeline_retry(raw: dict | None) -> PipelineRetryPolicy:
    if not raw:
        return PipelineRetryPolicy()
    return PipelineRetryPolicy(
        max_attempts=int(raw.get("max_attempts", 3)),
        base_delay_seconds=float(raw.get("base_delay_seconds", 1.0)),
        max_delay_seconds=float(raw.get("max_delay_seconds", 60.0)),
        retry_transient_only=bool(raw.get("retry_transient_only", True)),
    )


def parse_pipeline_quality(raw: dict | None) -> PipelineQualityPolicy:
    if not raw:
        return PipelineQualityPolicy()
    return PipelineQualityPolicy(
        enabled=bool(raw.get("enabled", True)),
        min_quality_score=float(raw.get("min_quality_score", 70.0)),
    )


def parse_pipeline_dataset(raw: dict | None) -> PipelineDatasetPolicy:
    if not raw:
        return PipelineDatasetPolicy()
    return PipelineDatasetPolicy(
        version_mode=str(raw.get("version_mode", "bump_on_material_change")),
        min_new_rows_to_bump=int(raw.get("min_new_rows_to_bump", 1)),
        preserve_prior_versions=bool(raw.get("preserve_prior_versions", True)),
    )


def load_pipeline_config(config: AppConfig) -> PipelineConfig:
    section = getattr(config, "pipeline", None)
    if section is None:
        return PipelineConfig()

    raw = getattr(section, "to_dict", lambda: {})() if hasattr(section, "to_dict") else {}
    if not isinstance(raw, dict):
        raw = {}

    return PipelineConfig(
        schedule=parse_pipeline_schedule(raw.get("schedule")),
        instruments=list(raw.get("instruments", []) or []),
        intervals=list(raw.get("intervals", ["1d"]) or ["1d"]),
        incremental=parse_pipeline_incremental(raw.get("incremental")),
        retry=parse_pipeline_retry(raw.get("retry")),
        quality=parse_pipeline_quality(raw.get("quality")),
        dataset=parse_pipeline_dataset(raw.get("dataset")),
        dry_run=bool(raw.get("dry_run", False)),
        run_label_finalization=bool(raw.get("run_label_finalization", True)),
        lock_timeout_seconds=int(raw.get("lock_timeout_seconds", 60)),
    )


def pipeline_storage_directory(config: AppConfig) -> Path:
    """Return the storage location for pipeline-run metadata."""
    base = getattr(config, "data", None)
    if base is None:
        return Path("data/pipeline")
    raw = base.raw_dir if hasattr(base, "raw_dir") else "data/raw"
    return Path(raw).parent / "pipeline"
