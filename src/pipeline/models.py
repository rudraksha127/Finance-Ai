"""Pipeline run, stage, and watermark models for the autonomous data-growth pipeline.

Design notes
------------
- A *pipeline run* is one scheduled or manual execution for one instrument/interval.
- A *stage* is one pipeline step with its own start/complete/status/records.
- Watermarks advance only after a stage is COMPLETED; a failed run preserves the prior
  successful watermark so recovery is safe.
- Pipeline run identity is separate from dataset version identity. Dataset growth still
  produces new immutable dataset versions when material changes occur.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

from src.config.loader import AppConfig
from src.core.enums import StorageTier


class PipelineRunState:
    """Explicit pipeline run lifecycle for scheduled/autonomous execution."""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"

    VALID_TRANSITIONS: dict[str, tuple[str, ...]] = {
        CREATED: (RUNNING, FAILED),
        RUNNING: (PARTIAL, COMPLETED, FAILED, RETRYING),
        PARTIAL: (RUNNING, FAILED, COMPLETED),
        FAILED: (RETRYING, FAILED),
        RETRYING: (RUNNING, FAILED),
        COMPLETED: (),
    }


@dataclass(slots=True)
class StageTracking:
    """One pipeline stage execution record."""

    name: str
    status: str = PipelineRunState.CREATED
    started_at: str | None = None
    completed_at: str | None = None
    input_range: str | None = None
    output_range: str | None = None
    records_processed: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def completed(self) -> bool:
        return self.status in {PipelineRunState.COMPLETED, PipelineRunState.FAILED}

    def snapshot(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "input_range": self.input_range,
            "output_range": self.output_range,
            "records_processed": self.records_processed,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(slots=True)
class PipelineWatermark:
    """Last successfully finalized watermark for one instrument/interval."""

    instrument: str
    interval: str
    source: str
    last_successful_timestamp: str | None
    pipeline_config_version: str
    status: str
    updated_at: str


@dataclass(slots=True)
class PipelineRunRecord:
    """Full observability record for one pipeline run."""

    run_id: str
    schedule_trigger: str | None
    instrument: str
    interval: str
    source: str
    config_version: str
    pipeline_config_version: str
    start_at: str
    end_at: str | None = None
    duration_ms: float | None = None
    requested_range: str | None = None
    input_range: str | None = None
    output_range: str | None = None
    state: str = PipelineRunState.CREATED
    stages: dict[str, dict] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    final_status: str | None = None
    storage_tier: str = StorageTier.RAW.value

    def to_public_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "schedule_trigger": self.schedule_trigger,
            "instrument": self.instrument,
            "interval": self.interval,
            "source": self.source,
            "config_version": self.config_version,
            "pipeline_config_version": self.pipeline_config_version,
            "start_at": self.start_at,
            "end_at": self.end_at,
            "duration_ms": self.duration_ms,
            "requested_range": self.requested_range,
            "input_range": self.input_range,
            "output_range": self.output_range,
            "state": self.state,
            "final_status": self.final_status,
            "storage_tier": self.storage_tier,
            "stages": dict(self.stages),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


def pipeline_config_version_from_config(config: AppConfig) -> str:
    """Return a simple pipeline configuration version identifier for run records."""
    return str(getattr(config, "pipeline", None) or "pipeline-config-unknown")
