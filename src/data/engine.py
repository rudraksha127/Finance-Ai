"""Ingestion engine — orchestration of one historical data pipeline run.

Pipeline per ticker (DATA_INGESTION_BLUEPRINT.md section 2):

    register instrument → fetch (bounded retries) → normalize →
    domain validation → persist (raw store, concat-dedup) → metadata

Failure policy:

- transient source failures (network, 5xx, rate limit) are retried
  with bounded exponential backoff; after ``max_retries`` the run is
  FAILED
- permanent source failures (not found, malformed response) fail
  immediately with the typed category
- row-level validation failures never abort the run — they are
  counted and produce PARTIAL (some rows persisted) or FAILED
  (nothing persisted)
- storage/journal errors propagate loudly (never swallowed)
- an empty provider response is FAILED with category ``EMPTY_DATA``
- statuses: CREATED/RUNNING internal → COMPLETED | PARTIAL | FAILED
  final; COMPLETED is never reported when critical persistence failed
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from src.config.loader import AppConfig, IngestionConfig
from src.core.errors import ValidationError
from src.core.models import Candle
from src.data.enums import IngestionStatus
from src.data.instruments import InstrumentRegistry
from src.data.metadata import (
    IngestionJournal,
    IngestionMetadata,
    metadata_directory,
    new_ingestion_id,
)
from src.data.normalize import normalize_fetched_to_candles
from src.data.sources.base import FetchedData, FetchParams, HistoricalDataSource
from src.data.sources.errors import (
    CATEGORY_DUPLICATE,
    CATEGORY_EMPTY,
    CATEGORY_UNKNOWN,
    CATEGORY_VALIDATION,
    SourceError,
)
from src.data.store import StoreSummary, raw_file_path, store_candles

_PIPELINE_VERSION = "0.2.0"


def _now_naive_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def backoff_delay_s(
    attempt: int, config: IngestionConfig, retry_after_s: float | None, rng: random.Random
) -> float:
    """Compute the sleep before retry ``attempt`` (1-based).

    Honors an explicit provider ``Retry-After`` hint; otherwise applies
    exponential backoff with jitter (blueprint section 7.2).
    """
    if retry_after_s is not None:
        return max(0.0, retry_after_s)
    base = config.retry.base_delay_s
    delay = min(base * (2 ** (attempt - 1)), config.retry.max_delay_s)
    return delay + rng.uniform(0.0, 0.5) * delay


@dataclass(frozen=True)
class IngestionReport:
    """Aggregate result of a multi-ticker ingestion run."""

    total: int
    completed: int
    partial: int
    failed: int
    records_persisted_total: int
    duration_s: float
    failures: tuple[tuple[str, str, str], ...]  # (ticker, category, message)


class IngestionEngine:
    """Runs the historical ingestion pipeline for one or more tickers."""

    def __init__(
        self,
        source: HistoricalDataSource,
        config: AppConfig,
        *,
        sleep: Callable[[float], None] = time.sleep,
        rng: random.Random | None = None,
        journal: IngestionJournal | None = None,
        registry: InstrumentRegistry | None = None,
        logger=None,
    ) -> None:
        self.source = source
        self.config = config
        self.sleep = sleep
        self.rng = rng or random.Random()
        self.journal = journal or IngestionJournal(config.data.raw_dir)
        self.registry = registry or InstrumentRegistry(
            metadata_directory(config.data.raw_dir) / "instruments.json"
        )
        self.logger = logger

    # ------------------------------------------------------------------
    # Single-ticker pipeline
    # ------------------------------------------------------------------
    def run_ticker(self, params: FetchParams) -> IngestionMetadata:
        """Run the full pipeline for one (ticker, range) and journal it.

        Returns the final metadata record (status COMPLETED / PARTIAL /
        FAILED). Typed source failures are captured into a FAILED record;
        storage/journal failures propagate loudly.
        """
        started = _now_naive_utc()
        ingestion_id = new_ingestion_id()
        self._log("ingestion_started", ingestion_id, params, status=IngestionStatus.RUNNING.value)

        base = IngestionMetadata(
            ingestion_id=ingestion_id,
            ticker=params.instrument,
            interval=params.interval,
            source=self.source.name,
            requested_start=params.start.isoformat(),
            requested_end=params.end.isoformat(),
            started_at=_iso(started),
            completed_at="",
            duration_ms=0.0,
            ingestion_status=IngestionStatus.CREATED.value,
            pipeline_version=_PIPELINE_VERSION,
            environment=self.config.environment.value,
        )

        try:
            self.registry.ensure(params.instrument)
        except ValidationError as error:
            return self._finalize(
                base, started, IngestionStatus.FAILED, CATEGORY_VALIDATION, str(error)
            )

        # --- Fetch with bounded retries ---------------------------------
        fetched: FetchedData | None = None
        retry_attempts = 0
        while True:
            try:
                fetched = self.source.fetch(params)
                break
            except SourceError as error:
                retryable = (
                    error.retryable and retry_attempts < self.config.ingestion.retry.max_retries
                )
                if not retryable:
                    return self._finalize(
                        base,
                        started,
                        IngestionStatus.FAILED,
                        error.category,
                        error.message,
                        retry_attempts=retry_attempts,
                    )
                retry_attempts += 1
                delay = backoff_delay_s(
                    retry_attempts, self.config.ingestion, error.retry_after_s, self.rng
                )
                self._log(
                    "ingestion_retry",
                    base.ingestion_id,
                    params,
                    attempt=retry_attempts,
                    delay_s=round(delay, 3),
                    category=error.category,
                    error=error.message,
                )
                self.sleep(delay)

        if fetched is None:  # pragma: no cover — defensive; loop always returns
            raise RuntimeError("unreachable: fetch loop always returns")

        # --- Normalize + domain validation ------------------------------
        batch = normalize_fetched_to_candles(fetched)

        if not fetched.records:
            return self._finalize(
                base,
                started,
                IngestionStatus.FAILED,
                CATEGORY_EMPTY,
                f"source returned no records for {params.instrument}",
                retry_attempts=retry_attempts,
            )

        # --- Persist (concat-dedup raw store) ---------------------------
        summary = StoreSummary(
            path=raw_file_path(self.config.data.raw_dir, params.instrument, params.interval)
        )
        if batch.candles:
            summary = store_candles(self.config.data.raw_dir, list(batch.candles))

        persisted = summary.added
        no_failures = batch.rejected_rows == 0 and summary.conflicts == 0
        if no_failures:
            # Every fetched row was added OR is already stored with
            # identical values (idempotent re-run) — a safe outcome.
            status = IngestionStatus.COMPLETED
        elif persisted > 0:
            status = IngestionStatus.PARTIAL
        else:
            # Nothing persisted: all rows rejected, or every timestamp
            # conflicts with materially different stored data.
            status = IngestionStatus.FAILED
            if batch.rejected_rows:
                category = CATEGORY_VALIDATION
                message = "no rows could be persisted: all fetched rows failed validation"
                if batch.reasons:
                    message += f" (e.g. {batch.reasons[0]})"
            elif summary.conflicts:
                category = CATEGORY_DUPLICATE
                message = (
                    "no rows could be persisted: fetched data conflicts with "
                    "materially different stored data; existing rows kept"
                )
            else:
                category = CATEGORY_EMPTY
                message = "no rows could be persisted"
            return self._finalize(
                base,
                started,
                status,
                category,
                message,
                retry_attempts=retry_attempts,
                fetched_record_count=len(fetched.records),
                batch=batch,
                summary=summary,
            )

        first, last = _range(batch.candles)
        final = IngestionMetadata(
            ingestion_id=base.ingestion_id,
            ticker=base.ticker,
            interval=base.interval,
            source=base.source,
            requested_start=base.requested_start,
            requested_end=base.requested_end,
            started_at=base.started_at,
            completed_at=_iso(_now_naive_utc()),
            duration_ms=_duration_ms(started),
            fetched_record_count=len(fetched.records),
            persisted_record_count=persisted,
            skipped_duplicate_count=batch.duplicates + summary.duplicates,
            rejected_count=batch.rejected_rows,
            conflict_count=summary.conflicts,
            error_count=0,
            actual_first_timestamp=first,
            actual_last_timestamp=last,
            ingestion_status=status.value,
            file_path=str(summary.path),
            file_size_bytes=summary.file_size_bytes,
            file_format="csv",
            checksum=summary.checksum,
            retry_attempts=retry_attempts,
            pipeline_version=base.pipeline_version,
            environment=base.environment,
        )
        return self._finalize_ok(final, started)

    # ------------------------------------------------------------------
    # Multi-ticker orchestration
    # ------------------------------------------------------------------
    def ingest_many(self, params_list: Sequence[FetchParams]) -> IngestionReport:
        """Run the pipeline for several tickers (sequential, per blueprint).

        When ``ingestion.continue_on_failure`` is enabled each ticker is
        independent: failures are recorded and the run continues.
        """
        started = _now_naive_utc()
        completed = partial = failed = 0
        persisted_total = 0
        failures: list[tuple[str, str, str]] = []

        for index, params in enumerate(params_list):
            # Provider rate-limit courtesy between independent requests.
            if index > 0:
                delay = self.config.ingestion.delay_between_requests_ms / 1000.0
                if delay > 0:
                    self.sleep(delay)
            record = self.run_ticker(params)
            persisted_total += record.persisted_record_count
            if record.ingestion_status == IngestionStatus.COMPLETED.value:
                completed += 1
            elif record.ingestion_status == IngestionStatus.PARTIAL.value:
                partial += 1
            else:
                failed += 1
                failures.append(
                    (
                        record.ticker,
                        record.error_category or CATEGORY_UNKNOWN,
                        record.error_message or "",
                    )
                )
                if not self.config.ingestion.continue_on_failure:
                    break

        return IngestionReport(
            total=len(params_list),
            completed=completed,
            partial=partial,
            failed=failed,
            records_persisted_total=persisted_total,
            duration_s=round(_duration_ms(started) / 1000.0, 3),
            failures=tuple(failures),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _finalize(
        self,
        base: IngestionMetadata,
        started: datetime,
        status: IngestionStatus,
        category: str,
        message: str,
        *,
        retry_attempts: int = 0,
        fetched_record_count: int | None = None,
        batch=None,
        summary: StoreSummary | None = None,
    ) -> IngestionMetadata:
        """Build a FAILED/PARTIAL metadata record and journal it."""
        # Rebuild cleanly instead of mutating the frozen base.
        kwargs = _with(
            base,
            completed_at=_iso(_now_naive_utc()),
            duration_ms=_duration_ms(started),
            ingestion_status=status.value,
            error_category=category,
            error_message=message,
            error_count=1,
            retry_attempts=retry_attempts,
        )
        if fetched_record_count is not None:
            kwargs = _with(kwargs, fetched_record_count=fetched_record_count)
        if batch is not None:
            kwargs = _with(
                kwargs,
                skipped_duplicate_count=batch.duplicates,
                rejected_count=batch.rejected_rows,
            )
        if summary is not None:
            kwargs = _with(
                kwargs,
                skipped_duplicate_count=kwargs.skipped_duplicate_count + summary.duplicates,
                conflict_count=summary.conflicts,
            )
            if summary.path.exists():
                kwargs = _with(
                    kwargs,
                    file_path=str(summary.path),
                    file_size_bytes=summary.file_size_bytes,
                    checksum=summary.checksum,
                )
        return self._finalize_ok(kwargs, started)

    def _finalize_ok(self, record: IngestionMetadata, started: datetime) -> IngestionMetadata:
        self.journal.append(record)  # StorageError propagates loudly — never swallowed
        self._log(
            "ingestion_completed",
            record.ingestion_id,
            None,
            status=record.ingestion_status,
            ticker=record.ticker,
            persisted=record.persisted_record_count,
            skipped=record.skipped_duplicate_count,
            rejected=record.rejected_count,
            conflicts=record.conflict_count,
            duration_ms=round(record.duration_ms, 1),
        )
        return record

    def _log(self, event: str, ingestion_id: str, params: FetchParams | None, **context) -> None:
        if self.logger is None:
            return
        payload = {"event": event, "ingestion_id": ingestion_id}
        if params is not None:
            payload.update(
                {
                    "ticker": params.instrument,
                    "start": params.start.isoformat(),
                    "end": params.end.isoformat(),
                    "interval": params.interval,
                }
            )
        payload.update(context)
        self.logger.info(event, **{key: value for key, value in payload.items() if key != "event"})


def _range(candles: Sequence[Candle]) -> tuple[str | None, str | None]:
    if not candles:
        return None, None
    return candles[0].timestamp.date().isoformat(), candles[-1].timestamp.date().isoformat()


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _duration_ms(started: datetime) -> float:
    return round((_now_naive_utc() - started).total_seconds() * 1000.0, 1)


def _with(base: IngestionMetadata, **overrides) -> IngestionMetadata:
    values = dict(base.__dict__)
    values.update(overrides)
    return IngestionMetadata(**values)
