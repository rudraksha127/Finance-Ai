"""Tests for src/data/store.py (raw-tier CSV store) and metadata journal."""

from __future__ import annotations

from datetime import date

import pytest

from src.core.errors import StorageError
from src.data.metadata import IngestionJournal, IngestionMetadata
from src.data.normalize import normalize_fetched_to_candles
from src.data.store import raw_file_path, read_candles, store_candles
from tests.data_helpers import candle_records, fetched


def _store_batch(raw_dir, records, *, ticker="AAPL"):
    """Normalize + store one fetch, mirroring the engine's store call."""
    records = tuple(records)
    start = end = date(2025, 1, 2)
    batch = normalize_fetched_to_candles(fetched(ticker, start, end, records))
    assert batch.rejected_rows == 0
    return store_candles(raw_dir, list(batch.candles))


class TestStoreCandles:
    def test_valid_insertion_writes_sorted_file(self, tmp_path):
        summary = _store_batch(tmp_path, candle_records(3))
        assert summary.added == 3
        assert summary.duplicates == 0
        assert summary.conflicts == 0
        assert summary.path.exists()
        assert summary.checksum
        assert summary.file_size_bytes > 0

        stored = read_candles(tmp_path, "AAPL", "1d")
        assert [c.timestamp.day for c in stored] == [2, 3, 4]
        assert all(c.ticker == "AAPL" for c in stored)

    def test_no_temporary_files_left_behind(self, tmp_path):
        _store_batch(tmp_path, candle_records(2))
        leftovers = list(tmp_path.glob("*.tmp"))
        assert leftovers == []

    def test_identical_reingest_is_idempotent(self, tmp_path):
        records = candle_records(3)
        first = _store_batch(tmp_path, records)
        second = _store_batch(tmp_path, records)

        assert second.added == 0
        assert second.duplicates == 3
        assert second.conflicts == 0
        assert second.checksum == first.checksum  # file byte-stable
        assert second.path.read_bytes() == first.path.read_bytes()
        assert len(read_candles(tmp_path, "AAPL", "1d")) == 3

    def test_float_noise_within_tolerance_is_duplicate(self, tmp_path):
        """Yahoo adj_close re-precision (±1e-7) must not fail a re-run."""
        records = list(candle_records(2))
        first = _store_batch(tmp_path, records)

        noisy = []
        for row in records:
            row = dict(row)
            row["adj_close"] = float(row["adj_close"]) * (1 + 1e-7)
            noisy.append(row)
        second = _store_batch(tmp_path, noisy)

        assert second.added == 0
        assert second.duplicates == 2  # within rtol → safe re-run
        assert second.conflicts == 0
        assert second.checksum == first.checksum  # stored bytes unchanged

    def test_correction_beyond_tolerance_is_conflict(self, tmp_path):
        """A real provider correction (≫1e-6) must still conflict."""
        _store_batch(tmp_path, candle_records(1))
        corrected = list(candle_records(1))
        corrected[0]["adj_close"] = float(corrected[0]["adj_close"]) * 1.05  # 5% adjustment
        summary = _store_batch(tmp_path, corrected)

        assert summary.added == 0
        assert summary.duplicates == 0
        assert summary.conflicts == 1

    def test_missing_adj_close_vs_present_is_conflict(self, tmp_path):
        """A row gaining/losing adj_close is materially different."""
        records = list(candle_records(1))
        _store_batch(tmp_path, records)

        without_adj = [{k: v for k, v in records[0].items() if k != "adj_close"}]
        summary = _store_batch(tmp_path, without_adj)
        assert summary.conflicts == 1

    def test_conflicting_values_keep_existing_row(self, tmp_path):
        _store_batch(tmp_path, candle_records(2))
        changed = list(candle_records(2))
        changed[0]["close"] = 999.0  # materially different for day 1
        changed[0]["high"] = 1000.0  # keep OHLC internally consistent

        summary = _store_batch(tmp_path, changed)
        assert summary.added == 0
        assert summary.conflicts == 1
        assert summary.duplicates == 1

        stored = read_candles(tmp_path, "AAPL", "1d")
        assert stored[0].close == candle_records(2)[0]["close"]  # existing wins

    def test_mixed_new_duplicate_and_conflict_rows(self, tmp_path):
        _store_batch(tmp_path, candle_records(2))
        batch = list(candle_records(4))  # days 2..5
        batch[0]["close"] = 999.0  # day 2 conflicts with stored
        batch[0]["high"] = 1000.0  # keep OHLC internally consistent
        summary = _store_batch(tmp_path, batch)

        assert summary.added == 2  # days 4, 5
        assert summary.duplicates == 1  # day 3 unchanged
        assert summary.conflicts == 1  # day 2 changed
        assert len(read_candles(tmp_path, "AAPL", "1d")) == 4  # 2 original + 2 new

    def test_mixed_tickers_are_rejected(self, tmp_path):
        records = candle_records(2)
        batch = normalize_fetched_to_candles(
            fetched("AAPL", date(2025, 1, 2), date(2025, 1, 2), records)
        )
        other = normalize_fetched_to_candles(
            fetched("MSFT", date(2025, 1, 2), date(2025, 1, 2), candle_records(1))
        )
        with pytest.raises(StorageError, match="share ticker"):
            store_candles(tmp_path, [batch.candles[0], other.candles[0]])

    def test_empty_candle_list_is_rejected(self, tmp_path):
        with pytest.raises(StorageError, match="at least one candle"):
            store_candles(tmp_path, [])

    def test_unsupported_interval_is_rejected(self, tmp_path):
        with pytest.raises(StorageError, match="unsupported interval"):
            raw_file_path(tmp_path, "AAPL", "5m")

    def test_corrupt_existing_file_is_rejected(self, tmp_path):
        raw = tmp_path / "AAPL_daily.csv"
        raw.write_text("ticker,timestamp,open\nAAPL,2025-01-02T00:00:00,1.0\n", encoding="utf-8")
        records = candle_records(1)
        batch = normalize_fetched_to_candles(
            fetched("AAPL", date(2025, 1, 2), date(2025, 1, 2), records)
        )
        with pytest.raises(StorageError, match="unexpected columns"):
            store_candles(tmp_path, list(batch.candles))

    def test_read_missing_file_returns_empty(self, tmp_path):
        assert read_candles(tmp_path, "AAPL", "1d") == ()


class TestReadCandlesRoundTrip:
    def test_adj_close_none_survives_round_trip(self, tmp_path):
        batch = normalize_fetched_to_candles(
            fetched(
                "AAPL",
                date(2025, 1, 2),
                date(2025, 1, 2),
                (
                    {
                        "timestamp": "2025-01-02",
                        "open": 1.0,
                        "high": 2.0,
                        "low": 0.5,
                        "close": 1.5,
                        "volume": 10,
                    },
                ),
            )
        )
        store_candles(tmp_path, list(batch.candles))
        stored = read_candles(tmp_path, "AAPL", "1d")
        assert stored[0].adj_close is None


class TestIngestionJournal:
    def _record(self, ticker: str = "AAPL", status: str = "COMPLETED") -> IngestionMetadata:
        return IngestionMetadata(
            ingestion_id="id-1",
            ticker=ticker,
            interval="1d",
            source="fake_source",
            requested_start="2025-01-02",
            requested_end="2025-01-03",
            started_at="2025-01-05T00:00:00",
            completed_at="2025-01-05T00:00:01",
            duration_ms=1000.0,
            fetched_record_count=2,
            persisted_record_count=2,
            ingestion_status=status,
            pipeline_version="0.2.0",
            environment="testing",
        )

    def test_append_and_read_back(self, tmp_path):
        journal = IngestionJournal(tmp_path)
        journal.append(self._record())
        entries = list(journal.read_all())
        assert len(entries) == 1
        assert entries[0].ticker == "AAPL"
        assert entries[0].ingestion_status == "COMPLETED"

    def test_journal_is_append_only(self, tmp_path):
        journal = IngestionJournal(tmp_path)
        journal.append(self._record("AAPL"))
        journal.append(self._record("MSFT"))
        entries = list(journal.read_all())
        assert [e.ticker for e in entries] == ["AAPL", "MSFT"]

    def test_entries_for_filters_by_ticker(self, tmp_path):
        journal = IngestionJournal(tmp_path)
        journal.append(self._record("AAPL"))
        journal.append(self._record("MSFT"))
        journal.append(self._record("AAPL"))
        assert len(journal.entries_for("AAPL")) == 2
        assert len(journal.entries_for("MSFT")) == 1

    def test_missing_journal_reads_empty(self, tmp_path):
        assert list(IngestionJournal(tmp_path).read_all()) == []

    def test_unreadable_line_raises_storage_error(self, tmp_path):
        path = tmp_path / "metadata" / "ingestion_log.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text("not json\n", encoding="utf-8")
        with pytest.raises(StorageError, match="unreadable"):
            list(IngestionJournal(tmp_path).read_all())
