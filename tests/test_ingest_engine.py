"""Tests for src/data/engine.py — pipeline orchestration.

Covers the milestone acceptance paths: successful runs, transient
failure + bounded retry, permanent failure, partial/all-rejected rows,
material-data conflicts (never silently overwritten), idempotent
re-runs, multi-ticker orchestration, and loud storage failures.
"""

from __future__ import annotations

import random
from datetime import date

import pytest

from src.core.errors import StorageError
from src.data.engine import IngestionEngine
from src.data.enums import IngestionStatus
from src.data.metadata import IngestionJournal
from src.data.sources.base import FetchParams
from src.data.sources.errors import (
    CATEGORY_CONNECTION,
    CATEGORY_DUPLICATE,
    CATEGORY_EMPTY,
    CATEGORY_NOT_FOUND,
    CATEGORY_VALIDATION,
    SourceConnectionError,
    SourceNotFoundError,
    SourceRateLimitError,
)
from src.data.store import read_candles
from tests.data_helpers import FakeSource, candle_records, fetched, make_app_config

START = date(2025, 1, 2)
END = date(2025, 1, 6)


def _params(
    ticker: str = "AAPL", start: date = START, end: date = END, interval: str = "1d"
) -> FetchParams:
    return FetchParams(instrument=ticker, start=start, end=end, interval=interval)


def _engine(source, config, **kwargs) -> IngestionEngine:
    return IngestionEngine(
        source, config, rng=random.Random(42), **{"sleep": lambda _s: None, **kwargs}
    )


class TestSuccessfulRun:
    def test_completed_run_persists_rows_and_journals(self, tmp_path):
        records = candle_records(5, first_day=START)
        config = make_app_config(tmp_path)
        source = FakeSource(fetched("AAPL", START, END, records))
        engine = _engine(source, config)
        journal = IngestionJournal(tmp_path)

        record = engine.run_ticker(_params())

        assert record.ingestion_status == IngestionStatus.COMPLETED.value
        assert record.persisted_record_count == 5
        assert record.fetched_record_count == 5
        assert record.error_count == 0
        assert record.actual_first_timestamp == "2025-01-02"
        assert record.actual_last_timestamp == "2025-01-06"
        assert len(read_candles(tmp_path, "AAPL", "1d")) == 5

        entries = journal.entries_for("AAPL")
        assert len(entries) == 1
        assert entries[0].ingestion_status == IngestionStatus.COMPLETED.value

    def test_instrument_registered_once(self, tmp_path):
        config = make_app_config(tmp_path)
        source = FakeSource(fetched("AAPL", START, END, candle_records(2, first_day=START)))
        engine = _engine(source, config)
        engine.run_ticker(_params())

        registry_path = tmp_path / "metadata" / "instruments.json"
        assert registry_path.exists()
        assert "AAPL" in engine.registry.all()


class TestIdempotency:
    def test_identical_rerun_creates_no_duplicates(self, tmp_path):
        records = candle_records(5, first_day=START)
        config = make_app_config(tmp_path)
        journal = IngestionJournal(tmp_path)

        first = _engine(FakeSource(fetched("AAPL", START, END, records)), config).run_ticker(
            _params()
        )
        second = _engine(FakeSource(fetched("AAPL", START, END, records)), config).run_ticker(
            _params()
        )

        # Second run is a safe no-op: COMPLETED, nothing added, duplicates counted.
        assert first.ingestion_status == IngestionStatus.COMPLETED.value
        assert first.persisted_record_count == 5
        assert second.ingestion_status == IngestionStatus.COMPLETED.value
        assert second.persisted_record_count == 0
        assert second.skipped_duplicate_count == 5
        assert second.error_count == 0
        assert len(read_candles(tmp_path, "AAPL", "1d")) == 5
        assert len(journal.entries_for("AAPL")) == 2

    def test_rerun_with_provider_float_noise_is_safe(self, tmp_path):
        """adj_close re-precision between identical fetches must not fail a re-run."""
        records = list(candle_records(5, first_day=START))
        config = make_app_config(tmp_path)
        _engine(FakeSource(fetched("AAPL", START, END, tuple(records))), config).run_ticker(
            _params()
        )

        noisy = [dict(row, adj_close=float(row["adj_close"]) * (1 + 1e-7)) for row in records]
        record = _engine(FakeSource(fetched("AAPL", START, END, tuple(noisy))), config).run_ticker(
            _params()
        )

        assert record.ingestion_status == IngestionStatus.COMPLETED.value
        assert record.persisted_record_count == 0
        assert record.skipped_duplicate_count == 5
        assert record.conflict_count == 0
        assert len(read_candles(tmp_path, "AAPL", "1d")) == 5

    def test_rerun_with_newer_dates_appends_only_new_rows(self, tmp_path):
        config = make_app_config(tmp_path)
        _engine(
            FakeSource(fetched("AAPL", START, END, candle_records(5, first_day=START))), config
        ).run_ticker(_params())
        later_end = date(2025, 1, 8)
        later = candle_records(7, first_day=START)
        record = _engine(FakeSource(fetched("AAPL", START, later_end, later)), config).run_ticker(
            _params(end=later_end)
        )
        assert record.ingestion_status == IngestionStatus.COMPLETED.value
        assert record.persisted_record_count == 2
        assert record.skipped_duplicate_count == 5
        assert len(read_candles(tmp_path, "AAPL", "1d")) == 7


class TestRetryBehavior:
    def test_transient_errors_retry_then_succeed(self, tmp_path):
        records = candle_records(3, first_day=START)
        config = make_app_config(tmp_path)
        sleeps: list[float] = []
        source = FakeSource(
            SourceConnectionError("network down"),
            SourceConnectionError("network down"),
            fetched("AAPL", START, END, records),
        )
        engine = IngestionEngine(source, config, sleep=sleeps.append, rng=random.Random(1))

        record = engine.run_ticker(_params())

        assert len(source.calls) == 3  # two failures + one success
        assert record.ingestion_status == IngestionStatus.COMPLETED.value
        assert record.retry_attempts == 2
        assert len(sleeps) == 2
        # Exponential backoff with jitter: base 1.0s, then ~2.0s capped by max.
        assert 1.0 <= sleeps[0] <= 1.5
        assert 2.0 <= sleeps[1] <= 3.0

    def test_retries_exhausted_marks_failed_with_attempts(self, tmp_path):
        config = make_app_config(tmp_path, max_retries=2)
        source = FakeSource(
            SourceConnectionError("down"),
            SourceConnectionError("down"),
            SourceConnectionError("down"),
        )
        record = _engine(source, config).run_ticker(_params())

        assert len(source.calls) == 3  # max_retries + 1 attempts
        assert record.ingestion_status == IngestionStatus.FAILED.value
        assert record.error_category == CATEGORY_CONNECTION
        assert record.retry_attempts == 2
        # Nothing persisted, no raw file created.
        assert not (tmp_path / "AAPL_daily.csv").exists()

    def test_permanent_error_is_not_retried(self, tmp_path):
        config = make_app_config(tmp_path, max_retries=5)
        source = FakeSource(SourceNotFoundError("no such symbol"))
        record = _engine(source, config).run_ticker(_params())

        assert len(source.calls) == 1
        assert record.ingestion_status == IngestionStatus.FAILED.value
        assert record.error_category == CATEGORY_NOT_FOUND
        assert record.retry_attempts == 0

    def test_rate_limit_retry_after_is_honored(self, tmp_path):
        records = candle_records(1, first_day=START)
        config = make_app_config(tmp_path)
        sleeps: list[float] = []
        source = FakeSource(
            SourceRateLimitError("slow down", retry_after_s=5.0),
            fetched("AAPL", START, END, records),
        )
        engine = IngestionEngine(source, config, sleep=sleeps.append, rng=random.Random(0))
        record = engine.run_ticker(_params())

        assert record.ingestion_status == IngestionStatus.COMPLETED.value
        assert sleeps == [5.0]  # provider hint wins over backoff
        assert record.retry_attempts == 1


class TestFailurePaths:
    def test_empty_provider_response_fails_with_empty_data(self, tmp_path):
        config = make_app_config(tmp_path)
        source = FakeSource(fetched("AAPL", START, END, ()))
        record = _engine(source, config).run_ticker(_params())

        assert record.ingestion_status == IngestionStatus.FAILED.value
        assert record.error_category == CATEGORY_EMPTY
        assert record.error_count == 1

    def test_all_rows_rejected_fails_with_validation(self, tmp_path):
        bad = tuple({**row, "high": 1.0} for row in candle_records(3, first_day=START))
        config = make_app_config(tmp_path)
        source = FakeSource(fetched("AAPL", START, END, bad))
        record = _engine(source, config).run_ticker(_params())

        assert record.ingestion_status == IngestionStatus.FAILED.value
        assert record.error_category == CATEGORY_VALIDATION
        assert record.rejected_count == 3
        assert record.persisted_record_count == 0
        assert not (tmp_path / "AAPL_daily.csv").exists()

    def test_partial_run_persists_valid_rows(self, tmp_path):
        records = list(candle_records(4, first_day=START))
        records[1]["volume"] = -1  # one invalid row
        config = make_app_config(tmp_path)
        source = FakeSource(fetched("AAPL", START, END, tuple(records)))
        record = _engine(source, config).run_ticker(_params())

        assert record.ingestion_status == IngestionStatus.PARTIAL.value
        assert record.rejected_count == 1
        assert record.persisted_record_count == 3
        assert len(read_candles(tmp_path, "AAPL", "1d")) == 3

    def test_conflicting_data_fails_without_overwriting(self, tmp_path):
        config = make_app_config(tmp_path)
        original = candle_records(2, first_day=START)
        _engine(FakeSource(fetched("AAPL", START, END, original)), config).run_ticker(_params())

        changed = list(candle_records(2, first_day=START))
        changed[0]["close"] = 777.0
        changed[0]["high"] = 800.0  # keep OHLC internally consistent
        record = _engine(
            FakeSource(fetched("AAPL", START, END, tuple(changed))), config
        ).run_ticker(_params())

        assert record.ingestion_status == IngestionStatus.FAILED.value
        assert record.error_category == CATEGORY_DUPLICATE
        assert record.conflict_count == 1  # day 1 changed; day 2 is an identical duplicate
        assert record.skipped_duplicate_count == 1
        assert record.persisted_record_count == 0
        # Stored rows are untouched (original closes, not 777.0).
        stored = read_candles(tmp_path, "AAPL", "1d")
        assert [c.close for c in stored] == [c["close"] for c in original]

    def test_invalid_ticker_fails_cleanly(self, tmp_path):
        config = make_app_config(tmp_path)
        engine = _engine(FakeSource(), config)
        record = engine.run_ticker(_params(ticker="NOT A TICKER!!"))
        assert record.ingestion_status == IngestionStatus.FAILED.value
        assert record.error_category == CATEGORY_VALIDATION


class TestMultiTicker:
    def test_ingest_many_runs_each_ticker(self, tmp_path):
        config = make_app_config(tmp_path)
        source = FakeSource(
            fetched("AAPL", START, END, candle_records(2, first_day=START)),
            fetched("MSFT", START, END, candle_records(3, first_day=START)),
        )
        engine = _engine(source, config)
        report = engine.ingest_many([_params("AAPL"), _params("MSFT")])

        assert report.total == 2
        assert report.completed == 2
        assert report.failed == 0
        assert report.records_persisted_total == 5
        assert len(read_candles(tmp_path, "AAPL", "1d")) == 2
        assert len(read_candles(tmp_path, "MSFT", "1d")) == 3

    def test_ingest_many_applies_pacing_between_tickers(self, tmp_path):
        config = make_app_config(tmp_path, delay_between_requests_ms=100)
        sleeps: list[float] = []
        source = FakeSource(
            fetched("AAPL", START, END, candle_records(1, first_day=START)),
            fetched("MSFT", START, END, candle_records(1, first_day=START)),
        )
        engine = IngestionEngine(source, config, sleep=sleeps.append, rng=random.Random(0))
        engine.ingest_many([_params("AAPL"), _params("MSFT")])
        assert sleeps == [0.1]

    def test_continue_on_failure_true_records_and_continues(self, tmp_path):
        config = make_app_config(tmp_path, continue_on_failure=True)
        source = FakeSource(
            SourceNotFoundError("bad ticker"),
            fetched("MSFT", START, END, candle_records(1, first_day=START)),
        )
        engine = _engine(source, config)
        report = engine.ingest_many([_params("BOGUS"), _params("MSFT")])

        assert len(source.calls) == 2
        assert report.failed == 1
        assert report.completed == 1
        assert report.failures[0][1] == CATEGORY_NOT_FOUND

    def test_continue_on_failure_false_stops_at_first_failure(self, tmp_path):
        config = make_app_config(tmp_path, continue_on_failure=False)
        source = FakeSource(SourceNotFoundError("bad ticker"))
        engine = _engine(source, config)
        report = engine.ingest_many([_params("BOGUS"), _params("MSFT")])

        assert len(source.calls) == 1  # second ticker never attempted
        assert report.failed == 1
        assert report.completed == 0
        assert report.total == 2


class TestLoudFailures:
    def test_storage_error_propagates_loudly(self, tmp_path):
        blocker = tmp_path / "not-a-directory"
        blocker.write_text("file", encoding="utf-8")
        config = make_app_config(blocker)  # raw_dir points at a file
        source = FakeSource(fetched("AAPL", START, END, candle_records(1, first_day=START)))
        engine = _engine(source, config)
        with pytest.raises(StorageError):
            engine.run_ticker(_params())

    def test_failed_runs_are_journaled(self, tmp_path):
        config = make_app_config(tmp_path)
        journal = IngestionJournal(tmp_path)
        source = FakeSource(SourceNotFoundError("nope"))
        engine = _engine(source, config)
        record = engine.run_ticker(_params("BOGUS"))
        assert record.ingestion_status == IngestionStatus.FAILED.value
        entries = journal.entries_for("BOGUS")
        assert len(entries) == 1
        assert entries[0].error_category == CATEGORY_NOT_FOUND
