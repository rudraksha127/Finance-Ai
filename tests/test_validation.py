"""Tests for src/core/validation.py — reusable validation primitives."""

from datetime import datetime, timedelta, timezone

import pytest

from src.core.errors import ValidationError
from src.core.validation import (
    find_duplicates,
    normalize_ticker,
    to_naive_utc,
    validate_chronological,
    validate_interval,
    validate_market_timestamp,
    validate_market_timestamps,
    validate_nonnegative_volume,
    validate_positive_price,
    validate_ticker,
    validate_unique,
)

UTC = timezone.utc
EASTERN = timezone(timedelta(hours=-5))


class TestTicker:
    @pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "BRK.B", "V", "ABC", "GOOGL"])
    def test_valid_tickers(self, ticker):
        assert validate_ticker(ticker) == ticker

    @pytest.mark.parametrize(
        "ticker", ["", "A1", "AAPL@", "AAPL.PHIL", "ABCDEFGHIJKL", " ", "APL O"]
    )
    def test_invalid_tickers_raise(self, ticker):
        with pytest.raises(ValidationError):
            validate_ticker(ticker)

    def test_normalize_ticker_strips_and_uppercases(self):
        assert normalize_ticker("  brk.b ") == "BRK.B"

    def test_lowercase_ticker_is_normalized_at_boundary(self):
        # Validation uppercases at the boundary (documented normalization),
        # so a lowercase ticker becomes its canonical uppercase form.
        assert validate_ticker("aapl") == "AAPL"

    def test_validate_ticker_returns_normalized(self):
        assert validate_ticker(" aapl ") == "AAPL"

    def test_non_string_ticker_raises(self):
        with pytest.raises(ValidationError):
            normalize_ticker(123)


class TestTimestamps:
    def test_naive_timestamp_passes_unchanged(self):
        naive = datetime(2026, 1, 2, 0, 0, 0)
        assert to_naive_utc(naive) == naive

    def test_utc_aware_timestamp_converts_to_naive(self):
        aware = datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC)
        result = to_naive_utc(aware)
        assert result == datetime(2026, 1, 2, 0, 0, 0)
        assert result.tzinfo is None

    def test_non_utc_aware_timestamp_raises(self):
        aware = datetime(2026, 1, 2, 12, 0, 0, tzinfo=EASTERN)
        with pytest.raises(ValidationError, match="must be UTC"):
            to_naive_utc(aware)

    def test_non_datetime_raises(self):
        with pytest.raises(ValidationError):
            to_naive_utc("2026-01-02")  # type: ignore[arg-type]

    def test_market_timestamp_validation(self):
        result = validate_market_timestamp(datetime(2026, 1, 2, tzinfo=UTC))
        assert result == datetime(2026, 1, 2)


class TestPricesAndVolume:
    @pytest.mark.parametrize("bad", [0, -1, float("inf"), float("nan")])
    def test_non_positive_price_raises(self, bad):
        with pytest.raises(ValidationError):
            validate_positive_price(bad)

    def test_positive_price_passes(self):
        assert validate_positive_price(185.6, "close") == 185.6

    def test_optional_positive_price_allows_none(self):
        from src.core.validation import validate_optional_positive_price

        assert validate_optional_positive_price(None, "adj_close") is None
        assert validate_optional_positive_price(42.0, "adj_close") == 42.0

    def test_negative_volume_raises(self):
        with pytest.raises(ValidationError):
            validate_nonnegative_volume(-5)

    def test_zero_volume_is_valid(self):
        assert validate_nonnegative_volume(0) == 0

    def test_text_price_raises(self):
        with pytest.raises(ValidationError):
            validate_positive_price("not a number")  # type: ignore[arg-type]


class TestInterval:
    @pytest.mark.parametrize("interval", ["1d", "1wk", "1mo"])
    def test_valid_intervals(self, interval):
        assert validate_interval(interval) == interval

    @pytest.mark.parametrize("interval", ["1h", "D", "1m", 1])
    def test_invalid_intervals_raise(self, interval):
        with pytest.raises(ValidationError):
            validate_interval(interval)  # type: ignore[arg-type]


class TestTimeSeriesIntegrity:
    def test_unique_sequence_passes(self):
        values = ["a", "b", "c"]
        validate_unique(values)
        assert find_duplicates(values) == []

    def test_duplicate_sequence_raises(self):
        values = ["a", "b", "a", "c", "b"]
        assert find_duplicates(values) == ["a", "b"]
        with pytest.raises(ValidationError, match="duplicates"):
            validate_unique(values)

    def test_chronological_sequence_passes(self):
        t1 = datetime(2026, 1, 1)
        t2 = datetime(2026, 1, 2)
        t3 = datetime(2026, 1, 3)
        validate_chronological([t1, t2, t3])

    def test_out_of_order_sequence_raises(self):
        t1 = datetime(2026, 1, 2)
        t2 = datetime(2026, 1, 1)
        with pytest.raises(ValidationError, match="strictly ascending"):
            validate_chronological([t1, t2])

    def test_market_timestamps_normalize_and_check(self):
        naive = datetime(2026, 1, 1)
        aware = datetime(2026, 1, 2, tzinfo=UTC)
        normalized = validate_market_timestamps([naive, aware])
        assert normalized == [naive, datetime(2026, 1, 2)]
        assert all(ts.tzinfo is None for ts in normalized)

    def test_duplicate_market_timestamps_raise(self):
        same = datetime(2026, 1, 1)
        with pytest.raises(ValidationError):
            validate_market_timestamps([same, same])

    def test_non_utc_aware_market_timestamps_raise(self):
        aware = datetime(2026, 1, 2, tzinfo=EASTERN)
        with pytest.raises(ValidationError, match="must be UTC"):
            validate_market_timestamps([datetime(2026, 1, 1), aware])
