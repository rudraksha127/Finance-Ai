"""Controlled autonomous data pipeline orchestrator.

It composes the existing domain engines instead of duplicating them:

1. Determine execution scope from watermark + policy
2. Optionally acquire an instrument/interval lock
3. Ingest only the missing/new range where the source supports it
4. Clean the newly ingested data with required lookback
5. Generate features for the extended series
6. Finalize labels whose future window is now complete
7. Build a new immutable dataset version if material changes occurred
8. Advance the watermark only on successful finalization
9. Record the pipeline run

This orchestrator is intentionally NOT a second feature/label/dataset engine.
It delegates to existing scripts/modules where practical.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config.loader import load_config
from src.pipeline.config import (
    PipelineConfig,
    load_pipeline_config,
    pipeline_storage_directory,
)
from src.pipeline.lock import pipeline_lock_path_for_run, pipeline_lock
from src.pipeline.models import (
    PipelineRunRecord,
    PipelineRunState,
    PipelineWatermark,
    StageTracking,
    pipeline_config_version_from_config,
)
from src.pipeline.watermark import (
    PipelineWatermarkStore,
    watermark_store_from_config,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bump_minor_version(version: str) -> str:
    """Best-effort bump for dataset version strings like v0.1 -> v0.2."""
    parts = version.lstrip("v").split(".")
    if len(parts) < 2:
        return version
    try:
        major = int(parts[0])
        minor = int(parts[1]) + 1
    except ValueError:
        return version + ".1"
    return f"v{major}.{minor}"


class PipelineOrchestrator:
    """Minimal autonomous/data-growth orchestrator for the local MVP."""

    def __init__(
        self,
        config: AppConfig | None = None,
        pipeline_config: PipelineConfig | None = None,
        work_dir: Path | None = None,
    ) -> None:
        self.app_config = config or load_config()
        self.pipeline_config = pipeline_config or load_pipeline_config(self.app_config)
        self._pipeline_config_version = pipeline_config_version_from_config(self.app_config)
        self.work_dir = work_dir or Path.cwd()
        self.watermark_store = watermark_store_from_config(self.app_config)
        self.run_id = str(uuid.uuid4())

    def run_for_instrument(
        self,
        instrument: str,
        interval: str = "1d",
        *,
        requested_start: str | None = None,
        requested_end: str | None = None,
        force_full: bool = False,
    ) -> PipelineRunRecord:
        tickers_last_ts = None
        stage_ingestion: StageTracking | None = None
        stage_cleaning: StageTracking | None = None
        stage_features: StageTracking | None = None
        stage_labels: StageTracking | None = None
        stage_dataset: StageTracking | None = None

        try:
            record = self._begin_run(
                instrument=instrument,
                interval=interval,
                requested_start=requested_start,
                requested_end=requested_end,
            )

            with pipeline_lock(
                pipeline_lock_path_for_run(self.work_dir / "data" / "pipeline", instrument, interval),
                timeout_seconds=self.pipeline_config.lock_timeout_seconds,
            ):
                state = PipelineRunState.RUNNING
                record.state = state

                if force_full:
                    start_ts, end_ts = requested_start, requested_end
                else:
                    start_ts, end_ts, skip = self._resolve_range(record, instrument, interval)                if skip:
                record.state = PipelineRunState.COMPLETED
                record.final_status = "SKIPPED_UP_TO_DATE"
                record.end_at = _now_iso()
                record.duration_ms = 0.0
                current = self.watermark_store.last(instrument, interval)
                record.output_range = current.last_successful_timestamp if current else None
                record.stages["skip"] = StageTracking(name="SKIP").snapshot()
                return self._finalize(record)

                stage_ingestion = self._run_ingestion(
                    instrument=instrument,
                    interval=interval,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    record=record,
                    stage=StageTracking(name="INGESTION"),
                )
                record.stages["ingestion"] = stage_ingestion.snapshot()

                if stage_ingestion.status == PipelineRunState.FAILED:
                    record.state = PipelineRunState.FAILED
                    record.final_status = "INGESTION_FAILED"
                    return self._finalize(record)

                stage_cleaning = self._run_cleaning(
                    instrument=instrument,
                    interval=interval,
                    record=record,
                    stage=StageTracking(name="CLEANING"),
                )
                record.stages["cleaning"] = stage_cleaning.snapshot()

                if stage_cleaning.status == PipelineRunState.FAILED:
                    record.state = PipelineRunState.FAILED
                    record.final_status = "CLEANING_FAILED"
                    return self._finalize(record)

                stage_features = self._run_features(
                    instrument=instrument,
                    interval=interval,
                    record=record,
                    stage=StageTracking(name="FEATURES"),
                )
                record.stages["features"] = stage_features.snapshot()

                if stage_features.status == PipelineRunState.FAILED:
                    record.state = PipelineRunState.FAILED
                    record.final_status = "FEATURES_FAILED"
                    return self._finalize(record)

                if self.pipeline_config.run_label_finalization:
                    stage_labels = self._run_label_finalization(
                        instrument=instrument,
                        interval=interval,
                        record=record,
                        stage=StageTracking(name="LABELS"),
                    )
                    record.stages["labels"] = stage_labels.snapshot()

                    if stage_labels.status == PipelineRunState.FAILED:
                        record.state = PipelineRunState.FAILED
                        record.final_status = "LABELS_FAILED"
                        return self._finalize(record)

                stage_dataset = self._run_dataset_build(
                    instrument=instrument,
                    interval=interval,
                    record=record,
                    stage=StageTracking(name="DATASET"),
                )
                record.stages["dataset"] = stage_dataset.snapshot()

                if stage_dataset.status == PipelineRunState.FAILED:
                    record.state = PipelineRunState.FAILED
                    record.final_status = "DATASET_FAILED"
                    return self._finalize(record)

                record.state = PipelineRunState.COMPLETED
                record.final_status = "COMPLETED"
                record.output_range = stage_dataset.output_range or record.output_range
                self.watermark_store.advance(
                    instrument=instrument,
                    interval=interval,
                    source=self.app_config.ingestion.source if hasattr(self.app_config, "ingestion") else "manual",
                    last_successful_timestamp=record.output_range or _now_iso(),
                    pipeline_config_version=self.pipeline_config_version,
                )
                return self._finalize(record)

        except Exception as exc:  # noqa: BLE001 - orchestrator must fail loudly
            record.state = PipelineRunState.FAILED
            record.final_status = "ORCHESTRATOR_ERROR"
            record.errors.append(str(exc))
            return self._finalize(record)

    def _begin_run(self, instrument: str, interval: str, *, requested_start: str | None, requested_end: str | None) -> PipelineRunRecord:
        start_at = _now_iso()
        requested_range = f"{requested_start or ''}:{requested_end or ''}" if (requested_start or requested_end) else None
        return PipelineRunRecord(
            run_id=self.run_id,
            schedule_trigger=self.pipeline_config.schedule.kind or "manual",
            instrument=instrument,
            interval=interval,
            source=self.app_config.ingestion.source if hasattr(self.app_config, "ingestion") and getattr(self.app_config.ingestion, "source", None) else "unknown",
            config_version=getattr(self.app_config, "project", None) and getattr(self.app_config.project, "version", None) or "unknown",
            pipeline_config_version=self.pipeline_config_version,
            start_at=start_at,
            requested_range=requested_range,
        )

    def _resolve_range(
        self, record: PipelineRunRecord, instrument: str, interval: str
    ) -> tuple[str | None, str | None, bool]:
        watermark = self.watermark_store.last(instrument, interval)
        if watermark is None:
            start_ts = record.requested_range.split(":")[0] if record.requested_range else None
            end_ts = None
            return start_ts, end_ts, False

        if self.pipeline_config.incremental.skip_if_up_to_date and watermark.status == "COMPLETED":
            record.warnings.append(f"watermark already completed for {instrument}/{interval}")
            record.output_range = watermark.last_successful_timestamp
            return None, None, True

        start_ts = watermark.last_successful_timestamp
        end_ts = record.requested_end
        if start_ts is not None and end_ts is not None and start_ts >= end_ts:
            record.warnings.append("requested range is already covered")
            record.output_range = watermark.last_successful_timestamp
            return None, None, True

        return start_ts, end_ts, False

    @property
    def pipeline_config_version(self) -> str:
        return self._pipeline_config_version

    def _finalize(self, record: PipelineRunRecord) -> PipelineRunRecord:
        now = _now_iso()
        record.end_at = now
        record.state = record.state or PipelineRunState.FAILED
        record.final_status = record.final_status or record.state
        return record

    # Stage adapters ---------------------------------------------------------
    def _run_ingestion(
        self,
        instrument: str,
        interval: str,
        start_ts: str | None,
        end_ts: str | None,
        record: PipelineRunRecord,
        stage: StageTracking,
    ) -> StageTracking:
        stage.status = PipelineRunState.RUNNING
        stage.started_at = _now_iso()
        stage.input_range = f"{start_ts or ''}:{end_ts or ''}"
        try:
            from scripts.run_ingest import main as ingest_main

            args = ["--ticker", instrument, "--interval", interval]
            if start_ts:
                args += ["--start", start_ts]
            if end_ts:
                args += ["--end", end_ts]
            exit_code = ingest_main(args)
            if exit_code == 0:
                stage.status = PipelineRunState.COMPLETED
                stage.completed_at = _now_iso()
                stage.output_range = end_ts or start_ts or "unknown"
                stage.records_processed = 1
            else:
                stage.status = PipelineRunState.FAILED
                stage.completed_at = _now_iso()
                stage.errors.append(f"ingestion exited with code {exit_code}")
        except Exception as exc:
            stage.status = PipelineRunState.FAILED
            stage.completed_at = _now_iso()
            stage.errors.append(str(exc))
        return stage

    def _run_cleaning(
        self,
        instrument: str,
        interval: str,
        record: PipelineRunRecord,
        stage: StageTracking,
    ) -> StageTracking:
        stage.status = PipelineRunState.RUNNING
        stage.started_at = _now_iso()
        try:
            from src.cleaning.pipeline import CleaningPipeline

            # CleaningPipeline is the approved cleaning engine; reuse it.
            pipeline = CleaningPipeline(pipeline_version="0.1.0")
            result = pipeline.run(ticker=instrument, interval=interval)
            stage.status = PipelineRunState.COMPLETED
            stage.completed_at = _now_iso()
            stage.records_processed = int(getattr(result, "cleaned_rows", 0) or 0)
            stage.output_range = result.cleaned_path.as_posix() if getattr(result, "cleaned_path", None) else None
        except Exception as exc:
            stage.status = PipelineRunState.FAILED
            stage.completed_at = _now_iso()
            stage.errors.append(str(exc))
        return stage

    def _run_features(
        self,
        instrument: str,
        interval: str,
        record: PipelineRunRecord,
        stage: StageTracking,
    ) -> StageTracking:
        stage.status = PipelineRunState.RUNNING
        stage.started_at = _now_iso()
        try:
            from scripts.run_features import main as features_main

            args = ["--ticker", instrument]
            exit_code = features_main(args)
            if exit_code == 0:
                stage.status = PipelineRunState.COMPLETED
                stage.completed_at = _now_iso()
                stage.records_processed = 1
            else:
                stage.status = PipelineRunState.FAILED
                stage.completed_at = _now_iso()
                stage.errors.append(f"features exited with code {exit_code}")
        except Exception as exc:
            stage.status = PipelineRunState.FAILED
            stage.completed_at = _now_iso()
            stage.errors.append(str(exc))
        return stage

    def _run_label_finalization(
        self,
        instrument: str,
        interval: str,
        record: PipelineRunRecord,
        stage: StageTracking,
    ) -> StageTracking:
        stage.status = PipelineRunState.RUNNING
        stage.started_at = _now_iso()
        try:
            from scripts.run_labels import main as labels_main

            args = ["--ticker", instrument]
            exit_code = labels_main(args)
            if exit_code == 0:
                stage.status = PipelineRunState.COMPLETED
                stage.completed_at = _now_iso()
                stage.records_processed = 1
            else:
                stage.status = PipelineRunState.FAILED
                stage.completed_at = _now_iso()
                stage.errors.append(f"labels exited with code {exit_code}")
        except Exception as exc:
            stage.status = PipelineRunState.FAILED
            stage.completed_at = _now_iso()
            stage.errors.append(str(exc))
        return stage

    def _run_dataset_build(
        self,
        instrument: str,
        interval: str,
        record: PipelineRunRecord,
        stage: StageTracking,
    ) -> StageTracking:
        stage.status = PipelineRunState.RUNNING
        stage.started_at = _now_iso()
        try:
            from scripts.run_dataset import main as dataset_main

            args = ["--ticker", instrument]
            existing = self.app_config.dataset_builder.dataset_version if hasattr(self.app_config, "dataset_builder") else None
            if existing:
                args += ["--output-version", existing]
            exit_code = dataset_main(args)
            if exit_code == 0:
                stage.status = PipelineRunState.COMPLETED
                stage.completed_at = _now_iso()
                stage.records_processed = 1
                # advance watermark only now that downstream is finalized
                self.watermark_store.advance(
                    instrument=instrument,
                    interval=interval,
                    source=self.app_config.ingestion.source if hasattr(self.app_config, "ingestion") else "manual",
                    last_successful_timestamp=record.output_range or stage.output_range or _now_iso(),                    pipeline_config_version=self.pipeline_config_version,
                    )
                record.output_range = stage.output_range or record.output_range
            else:
                stage.status = PipelineRunState.FAILED
                stage.completed_at = _now_iso()
                stage.errors.append(f"dataset build exited with code {exit_code}")
        except Exception as exc:
            stage.status = PipelineRunState.FAILED
            stage.completed_at = _now_iso()
            stage.errors.append(str(exc))
        return stage

    def status_index(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "watermarks": self.watermark_store.snapshot(),
            "pipeline_config": {
                "schedule_kind": self.pipeline_config.schedule.kind,
                "instruments": self.pipeline_config.effective_instruments,
                "intervals": self.pipeline_config.effective_intervals,
                "incremental": {
                    "enabled": self.pipeline_config.incremental.enabled,
                    "overlap_window_business_days": self.pipeline_config.incremental.overlap_window_business_days,
                },
                "dry_run": self.pipeline_config.dry_run,
            },
        }
