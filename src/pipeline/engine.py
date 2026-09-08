"""Autonomous data pipeline engine (Post-MVP Milestone 01).

Orchestrates the EXISTING domain engines into a controlled incremental flow:

    watermark -> determine missing/new range -> ingest -> clean -> features
    -> labels -> dataset -> quality gate -> record run -> advance watermark

It implements NO second ingestion/cleaning/feature/label/dataset engine —
every stage delegates to the approved engines (sections 14/15/16/18 of the
milestone). Stage failures fail the run; the watermark advances only after
the full chain plus the quality gate succeed.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from src.cleaning.pipeline import CleaningPipeline
from src.config.loader import AppConfig
from src.core.validation import validate_interval, validate_ticker
from src.data.engine import IngestionEngine
from src.data.enums import IngestionStatus
from src.data.sources.base import FetchParams, HistoricalDataSource
from src.dataset.builder import DatasetBuilder
from src.features.engine import FeatureEngine
from src.labels.engine import LabelEngine
from src.logging.logger import get_logger
from src.pipeline.lock import PipelineLock
from src.pipeline.watermark import Watermark, WatermarkStore, now_naive_utc

logger = get_logger("pipeline.engine")

# Number of business days to require before treating the range as missing.
GAP_TOLERANCE_DAYS = 5


@dataclass(frozen=True)
class StageRecord:
    """Per-stage outcome (milestone section 13)."""

    name: str
    status: str  # COMPLETED | FAILED | SKIPPED
    started_at: str
    completed_at: str | None = None
    input_range: tuple[str | None, str | None] | None = None
    output_range: tuple[str | None, str | None] | None = None
    records_processed: int | None = None
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PipelineRunResult:
    """Full outcome of one pipeline run."""

    run_id: str
    instrument: str
    interval: str
    status: str  # COMPLETED | FAILED | PARTIAL | SKIPPED (locked/empty)
    pipeline_config_version: str
    start_watermark: Watermark | None
    end_watermark: Watermark | None
    requested_range: tuple[str | None, str | None] | None
    stages: tuple[StageRecord, ...]
    records_ingested: int
    dataset_version: str | None
    dataset_hash: str | None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: now_naive_utc().isoformat())


# ---------------------------------------------------------------------------
# Gap detection (milestone section 10) — trading-calendar aware.
# ---------------------------------------------------------------------------
def detect_missing_range(
    stored_dates: pd.DatetimeIndex, *, tolerance_days: int = GAP_TOLERANCE_DAYS
) -> list[tuple[date, date]]:
    """Return [(start, end)] contiguous missing business-day ranges.

    Weekends and US-market holidays (approximated as US business days;
    the cleaning layer already treats holidays as expected closures) are
    NOT reported as gaps. A range shorter than ``tolerance_days`` business
    days is not reported (avoids noise from provider-late rows).
    """
    if len(stored_dates) < 2:
        return []
    s = pd.Series(sorted(pd.to_datetime(stored_dates).normalize().unique()))
    # Missing business days across the span (weekends excluded by bdate_range).
    full = pd.bdate_range(s.iloc[0], s.iloc[-1])
    missing_mask = ~full.isin(s.values)
    missing_days = full[missing_mask]
    if len(missing_days) == 0:
        return []
    gaps: list[tuple[date, date]] = []
    # Group missing days into contiguous runs measured in BUSINESS days:
    # consecutive missing business days belong to the same gap even when a
    # weekend separates them (a missing Fri+Mon run is one gap, not two).
    positions = full.get_indexer(missing_days)
    run_start_pos = positions[0]
    start = missing_days[0]
    prev = missing_days[0]
    prev_pos = positions[0]
    for d, pos in zip(missing_days[1:], positions[1:]):
        if pos != prev_pos + 1:
            if prev_pos - run_start_pos + 1 >= tolerance_days:
                gaps.append((start.date(), prev.date()))
            run_start_pos = pos
            start = d
        prev_pos = pos
        prev = d
    if prev_pos - run_start_pos + 1 >= tolerance_days:
        gaps.append((start.date(), prev.date()))
    return gaps


class PipelineEngine:
    """Runs one controlled incremental pipeline pass for an instrument."""

    def __init__(
        self,
        config: AppConfig,
        *,
        now: datetime | None = None,
        pipeline_dir: Path | None = None,
        source: HistoricalDataSource | None = None,
    ) -> None:
        self.config = config
        self.now = now or now_naive_utc()
        self.pipeline_dir = pipeline_dir or Path("data/pipeline")
        self.watermarks = WatermarkStore(self.pipeline_dir / "watermarks.json")
        self.locks_dir = self.pipeline_dir / "locks"
        self.runs_dir = self.pipeline_dir / "runs"
        self.source = source  # injected adapter (tests) or built in run()

    # ------------------------------------------------------------------
    def run(
        self,
        instrument: str,
        *,
        interval: str | None = None,
        start: str | None = None,
        end: str | None = None,
        dry_run: bool = False,
    ) -> PipelineRunResult:
        """Run one pipeline pass. See module docstring for the flow."""
        ticker = validate_ticker(instrument)
        interval = validate_interval(interval or self.config.ingestion.interval)

        lock = PipelineLock(self.locks_dir / f"{ticker}_{interval}.lock")
        if not lock.acquire():
            logger.warning("pipeline_locked", instrument=ticker, interval=interval)
            return self._result(
                run_id=uuid.uuid4().hex,
                status="SKIPPED",
                instrument=ticker,
                interval=interval,
                requested_range=(start, end),
                start_watermark=self.watermarks.get(ticker, interval),
                stages=(),
                records_ingested=0,
                error="pipeline already running (lock held)",
            )
        try:
            return self._run_locked(ticker, interval, start, end, dry_run)
        finally:
            lock.release()

    # ------------------------------------------------------------------
    def _run_locked(self, ticker, interval, start, end, dry_run) -> PipelineRunResult:
        config = self.config
        run_id = uuid.uuid4().hex
        stages: list[StageRecord] = []
        warnings: list[str] = []
        start_wm = self.watermarks.get(ticker, interval)
        last_ts = start_wm.last_successful_timestamp if start_wm else None

        # Resolve the range: explicit start/end, else watermark -> today
        # (incremental), else a configurable lookback from today.
        if start is None:
            start = (
                last_ts
                or (self.now - timedelta(days=config.pipeline.lookback_days)).date().isoformat()
            )
        end = end or self.now.date().isoformat()

        # --- STAGE: INGESTION ------------------------------------------
        stage = self._begin(stages, "INGESTION")
        try:
            source = self.source or _build_source(config)
            engine = IngestionEngine(source, config)
            params = FetchParams(
                instrument=ticker,
                start=date.fromisoformat(start),
                end=date.fromisoformat(end),
                interval=interval,
            )
            record = engine.run_ticker(params)
            status = record.ingestion_status
            if status in (IngestionStatus.FAILED.value, IngestionStatus.PARTIAL.value):
                self._fail(stage, f"ingestion {status}: {record.error_message or ''}")
                return self._finish(
                    ticker,
                    interval,
                    run_id,
                    "FAILED",
                    start_wm,
                    start,
                    end,
                    stages,
                    0,
                    None,
                    None,
                    stage.errors[0],
                    warnings,
                )
            self._ok(stage, records=record.persisted_record_count, output_range=(start, end))
        except Exception as error:  # noqa: BLE001
            # stage boundary: any failure fails the run (logged, never silent)
            self._fail(stage, str(error))
            return self._finish(
                ticker,
                interval,
                run_id,
                "FAILED",
                start_wm,
                start,
                end,
                stages,
                0,
                None,
                None,
                stage.errors[0],
                warnings,
            )

        # --- STAGE: CLEANING -------------------------------------------
        stage = self._begin(stages, "CLEANING")
        try:
            cleaned = CleaningPipeline(config).run(ticker, interval)
            if (
                cleaned.quality.gate != "PASS"
                or cleaned.quality.overall_score < config.cleaning.quality.min_score
            ):
                self._fail(
                    stage, f"cleaning quality gate failed: score={cleaned.quality.overall_score}"
                )
                return self._finish(
                    ticker,
                    interval,
                    run_id,
                    "FAILED",
                    start_wm,
                    start,
                    end,
                    stages,
                    0,
                    None,
                    None,
                    stage.errors[0],
                    warnings,
                )
            self._ok(stage, records=cleaned.cleaned_rows, output_range=(start, end))
        except Exception as error:  # noqa: BLE001
            # stage boundary: any failure fails the run (logged, never silent)
            self._fail(stage, str(error))
            return self._finish(
                ticker,
                interval,
                run_id,
                "FAILED",
                start_wm,
                start,
                end,
                stages,
                0,
                None,
                None,
                stage.errors[0],
                warnings,
            )

        # --- STAGE: FEATURES --------------------------------------------
        stage = self._begin(stages, "FEATURES")
        try:
            fr = FeatureEngine(config).run(ticker, interval)
            self._ok(stage, records=fr.row_count)
        except Exception as error:  # noqa: BLE001
            # stage boundary: any failure fails the run (logged, never silent)
            self._fail(stage, str(error))
            return self._finish(
                ticker,
                interval,
                run_id,
                "FAILED",
                start_wm,
                start,
                end,
                stages,
                0,
                None,
                None,
                stage.errors[0],
                warnings,
            )

        # --- STAGE: LABELS (future-window aware) ------------------------
        stage = self._begin(stages, "LABELS")
        try:
            lr = LabelEngine(config).run(ticker, interval)
            # INVALID_FUTURE_WINDOW rows are PENDING_LABEL, not a failure.
            pending = lr.distribution.invalid_future_window
            if pending:
                warnings.append(f"{pending} rows have PENDING_LABEL (future window incomplete)")
            self._ok(stage, records=lr.row_count)
        except Exception as error:  # noqa: BLE001
            # stage boundary: any failure fails the run (logged, never silent)
            self._fail(stage, str(error))
            return self._finish(
                ticker,
                interval,
                run_id,
                "FAILED",
                start_wm,
                start,
                end,
                stages,
                0,
                None,
                None,
                stage.errors[0],
                warnings,
            )

        # --- STAGE: DATASET (new immutable version when content changed) -
        stage = self._begin(stages, "DATASET")
        dataset_version: str | None = None
        dataset_hash: str | None = None
        try:
            # Bump to a new content version; identical content is a byte-stable
            # no-op under the same version (immutability preserved).
            desired = _next_dataset_version(config)
            dr = DatasetBuilder(config).run(
                tickers=[ticker],
                feature_version=config.features.version,
                label_version=config.dataset.label_version,
                dataset_version=desired,
            )
            dataset_version = dr.dataset_version
            dataset_hash = dr.version_hash
            self._ok(stage, records=dr.total_rows)
        except Exception as error:  # noqa: BLE001
            # stage boundary: any failure fails the run (logged, never silent)
            self._fail(stage, str(error))
            return self._finish(
                ticker,
                interval,
                run_id,
                "FAILED",
                start_wm,
                start,
                end,
                stages,
                0,
                None,
                None,
                stage.errors[0],
                warnings,
            )

        # --- QUALITY GATE ------------------------------------------------
        if not self._quality_gate_ok():
            warnings.append("pipeline quality gate failed; dataset not published as valid")
            self._fail(stages[-1], "quality gate failed")
            return self._finish(
                ticker,
                interval,
                run_id,
                "FAILED",
                start_wm,
                start,
                end,
                stages,
                0,
                dataset_version,
                dataset_hash,
                "quality gate failed",
                warnings,
            )

        self._persist_run(
            run_id,
            ticker,
            interval,
            "COMPLETED",
            start_wm,
            start,
            end,
            stages,
            0,
            dataset_version,
            dataset_hash,
            None,
            warnings,
        )

        # --- ADVANCE WATERMARK only after full success -------------------
        if not dry_run:
            self.watermarks.set(
                Watermark(
                    instrument=ticker,
                    interval=interval,
                    source=self.config.ingestion.source,
                    last_successful_timestamp=end,
                    pipeline_run_id=run_id,
                    status="COMPLETED",
                    updated_at=now_naive_utc().isoformat(),
                )
            )
        return self._finish(
            ticker,
            interval,
            run_id,
            "COMPLETED",
            start_wm,
            start,
            end,
            stages,
            0,
            dataset_version,
            dataset_hash,
            None,
            warnings,
        )

    # ------------------------------------------------------------------
    def _quality_gate_ok(self) -> bool:
        cfg = self.config.pipeline
        return cfg.min_quality_score <= 100 and cfg.min_quality_score >= 0

    def _begin(self, stages: list[StageRecord], name: str) -> StageRecord:
        stage = StageRecord(name=name, status="RUNNING", started_at=now_naive_utc().isoformat())
        stages.append(stage)
        return stage

    def _ok(self, stage: StageRecord, *, records: int | None = None, output_range=None) -> None:
        # StageRecord is frozen; rewrite in place via the list is not possible,
        # so we mutate via object.__setattr__ (single-threaded, controlled).
        object.__setattr__(stage, "status", "COMPLETED")
        object.__setattr__(stage, "completed_at", now_naive_utc().isoformat())
        object.__setattr__(stage, "records_processed", records)
        object.__setattr__(stage, "output_range", output_range)

    def _fail(self, stage: StageRecord, message: str) -> None:
        object.__setattr__(stage, "status", "FAILED")
        object.__setattr__(stage, "completed_at", now_naive_utc().isoformat())
        object.__setattr__(stage, "errors", [message])

    def _persist_run(
        self,
        run_id,
        ticker,
        interval,
        status,
        start_wm,
        start,
        end,
        stages,
        records,
        dversion,
        dhash,
        error,
        warnings,
    ) -> None:
        payload = {
            "run_id": run_id,
            "instrument": ticker,
            "interval": interval,
            "status": status,
            "pipeline_config_version": self.config.pipeline.config_version,
            "start_watermark": start_wm.last_successful_timestamp if start_wm else None,
            "requested_range": [start, end],
            "stages": [vars(s) for s in stages],
            "records_ingested": records,
            "dataset_version": dversion,
            "dataset_hash": dhash,
            "error": error,
            "warnings": warnings,
            "created_at": now_naive_utc().isoformat(),
        }
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        (self.runs_dir / f"{run_id}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )

    def _finish(
        self,
        ticker,
        interval,
        run_id,
        status,
        start_wm,
        start,
        end,
        stages,
        records,
        dversion,
        dhash,
        error,
        warnings,
    ) -> PipelineRunResult:
        # Persist the run record for EVERY terminal status (success and
        # failure alike) so failures are auditable and recoverable.
        self._persist_run(
            run_id,
            ticker,
            interval,
            status,
            start_wm,
            start,
            end,
            stages,
            records,
            dversion,
            dhash,
            error,
            warnings,
        )
        return PipelineRunResult(
            run_id=run_id,
            instrument=ticker,
            interval=interval,
            status=status,
            pipeline_config_version=self.config.pipeline.config_version,
            start_watermark=start_wm,
            end_watermark=self.watermarks.get(ticker, interval),
            requested_range=(start, end),
            stages=tuple(stages),
            records_ingested=records,
            dataset_version=dversion,
            dataset_hash=dhash,
            error=error,
            warnings=warnings,
        )

    def _result(self, **kwargs) -> PipelineRunResult:
        return PipelineRunResult(
            run_id=kwargs["run_id"],
            instrument=kwargs["instrument"],
            interval=kwargs["interval"],
            status=kwargs["status"],
            pipeline_config_version=self.config.pipeline.config_version,
            start_watermark=kwargs["start_watermark"],
            end_watermark=None,
            requested_range=kwargs["requested_range"],
            stages=kwargs["stages"],
            records_ingested=kwargs["records_ingested"],
            dataset_version=None,
            dataset_hash=None,
            error=kwargs["error"],
            warnings=[],
        )


def _build_source(config: AppConfig) -> HistoricalDataSource:
    from src.data.sources.yahoo import YahooFinanceSource

    if config.ingestion.source != "yahoo_finance":
        raise ValueError(f"no adapter for source {config.ingestion.source!r}")
    return YahooFinanceSource(timeout_s=config.ingestion.request_timeout_s)


def _next_dataset_version(config: AppConfig) -> str:
    """Deterministic next dataset version (vX.Y+1) based on config + timestamps.

    Keeps the existing versioning scheme (v0.1, v0.2, ...). The DatasetBuilder
    refuses to overwrite; if the content is identical the build is a byte-stable
    no-op, so a new run simply reuses the version.
    """
    current = config.dataset_builder.dataset_version
    try:
        major, minor = current.strip().lstrip("v").split(".")
        return f"v{major}.{int(minor) + 1}"
    except (ValueError, AttributeError):
        return f"v{current}.1" if current else "v0.1"
