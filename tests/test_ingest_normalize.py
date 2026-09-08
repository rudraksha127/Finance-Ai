"""Tests for src/data/normalize.py — normalization + row-level rejection."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from src.core.errors import ValidationError
from src.data.normalize import normalize_fetched_to_candles
from tests.data_helpers import candle_records, fetched


def _start() -> date:
    return date(2025, 1, 2)


class TestMappingAndConversion:
    def test_records_map_to_domain_candles(self):
        records = candle_records(2)
        batch = normalize_fetched_to_candles(fetched("AAPL", _start(), _start(), records))
        assert batch.rejected_rows == 0
        assert len(batch.candles) == 2
        candle = batch.candles[0]
        assert candle.ticker == "AAPL"
        assert candle.interval == "1d"
        assert candle.source == "fake_source"
        assert candle.timestamp == datetime(2025, 1, 2)
        assert candle.open == 100.0
        assert candle.adj_close == candle.close
        assert candle.volume == 1_000_000

    def test_numeric_strings_are_converted(self):
        records = (
            {
                "timestamp": "2025-01-02",
                "open": "100.0",
                "high": "101.5",
                "low": "99.5",
                "close": "101.0",
                "volume": "2500000",
            },
        )
        batch = normalize_fetched_to_candles(fetched("AAPL", _start(), _start(), records))
        candle = batch.candles[0]
        assert candle.open == 100.0
        assert candle.volume == 2_500_000
        assert candle.adj_close is None

    def test_output_is_sorted_ascending_by_timestamp(self):
        records = candle_records(3)
        shuffled = (records[2], records[0], records[1])
        batch = normalize_fetched_to_candles(fetched("AAPL", _start(), _start(), shuffled))
        timestamps = [c.timestamp for c in batch.candles]
        assert timestamps == sorted(timestamps)
        assert timestamps[0] == datetime(2025, 1, 2)
        assert timestamps[-1] == datetime(2025, 1, 4)

    def test_invalid_ticker_is_rejected(self):
        records = candle_records(1)
        with pytest.raises(ValidationError, match="ticker"):
            normalize_fetched_to_candles(fetched("NOT A TICKER!!", _start(), _start(), records))


class TestRowLevelRejection:
    def test_invalid_ohlc_row_is_rejected_not_fatal(self):
        records = list(candle_records(2))
        records[0]["high"] = 50.0  # high < close → invalid candle
        batch = normalize_fetched_to_candles(fetched("AAPL", _start(), _start(), tuple(records)))
        assert len(batch.candles) == 1
        assert batch.rejected_rows == 1
        assert batch.reasons

    def test_negative_volume_row_is_rejected(self):
        records = list(candle_records(1))
        records[0]["volume"] = -5
        batch = normalize_fetched_to_candles(fetched("AAPL", _start(), _start(), tuple(records)))
        assert batch.candles == ()
        assert batch.rejected_rows == 1

    def test_non_iso_timestamp_row_is_rejected(self):
        records = list(candle_records(1))
        records[0]["timestamp"] = "2025/01/02"
        batch = normalize_fetched_to_candles(fetched("AAPL", _start(), _start(), tuple(records)))
        assert batch.rejected_rows == 1
        assert batch.candles == ()

    def test_missing_timestamp_field_is_rejected(self):
        records = list(candle_records(1))
        del records[0]["timestamp"]
        batch = normalize_fetched_to_candles(fetched("AAPL", _start(), _start(), tuple(records)))
        assert batch.rejected_rows == 1

    def test_missing_price_field_is_rejected(self):
        records = list(candle_records(1))
        records[0]["open"] = None
        batch = normalize_fetched_to_candles(fetched("AAPL", _start(), _start(), tuple(records)))
        assert batch.rejected_rows == 1

    def test_reason_samples_are_bounded(self):
        records = candle_records(15)
        bad = tuple({**row, "open": None} for row in records)
        batch = normalize_fetched_to_candles(fetched("AAPL", _start(), _start(), bad))
        assert batch.rejected_rows == 15
        assert len(batch.reasons) <= 10


class TestWithinFetchDuplicates:
    def test_duplicate_timestamps_keep_first_and_count(self):
        records = list(candle_records(2))
        duplicate = dict(records[1])
        duplicate["volume"] = 5  # valid row, different values
        fetched_records = (records[0], records[1], duplicate)
        batch = normalize_fetched_to_candles(
            fetched("AAPL", _start(), _start(), tuple(fetched_records))
        )
        assert len(batch.candles) == 2
        assert batch.duplicates == 1
        assert batch.candles[1].volume == records[1]["volume"]  # original kept, not 5

    def test_duplicate_with_invalid_second_row(self):
        records = list(candle_records(1))
        duplicate = dict(records[0])
        duplicate["high"] = 1.0  # invalid
        batch = normalize_fetched_to_candles(
            fetched("AAPL", _start(), _start(), (records[0], duplicate))
        )
        # The invalid duplicate is rejected first, so the valid row survives.
        assert len(batch.candles) == 1
        assert batch.rejected_rows == 1
        assert batch.duplicates == 0
