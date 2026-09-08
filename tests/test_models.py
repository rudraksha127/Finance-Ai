"""Tests for src/core/models.py — foundational domain types."""

from datetime import datetime, timezone

import pytest

from src.core.errors import ValidationError
from src.core.models import Candle, Instrument, candle_observation_key
from src.core.validation import find_duplicates

UTC = timezone.utc


def _valid_candle(**overrides):
    values = {
        "ticker": "AAPL",
        "timestamp": datetime(2026, 1, 2),
        "open": 100.0,
        "high": 105.0,
        "low": 99.0,
        "close": 104.0,
        "volume": 1_000_000,
        "interval": "1d",
    }
    values.update(overrides)
    return Candle(**values)


class TestInstrument:
    def test_valid_instrument(self):
        instrument = Instrument(ticker="AAPL", name="Apple Inc.", exchange="NASDAQ")
        assert instrument.ticker == "AAPL"
        assert instrument.name == "Apple Inc."
        assert instrument.is_active is True

    def test_ticker_is_normalized(self):
        assert Instrument(ticker=" aapl ").ticker == "AAPL"

    def test_invalid_ticker_raises(self):
        with pytest.raises(ValidationError):
            Instrument(ticker="not a ticker")

    def test_empty_optional_field_raises(self):
        with pytest.raises(ValidationError):
            Instrument(ticker="AAPL", exchange="  ")

    def test_non_bool_is_active_raises(self):
        with pytest.raises(ValidationError):
            Instrument(ticker="AAPL", is_active="yes")  # type: ignore[arg-type]


class TestCandle:
    def test_valid_candle(self):
        candle = _valid_candle()
        assert candle.ticker == "AAPL"
        assert candle.close == 104.0
        assert candle.adj_close is None
        assert candle.interval == "1d"

    def test_fields_are_normalized(self):
        # Ticker is uppercased/stripped at the boundary; canonical
        # interval values pass through unchanged.
        candle = _valid_candle(ticker=" aapl ")
        assert candle.ticker == "AAPL"
        assert candle.interval == "1d"

    def test_non_canonical_interval_is_rejected(self):
        with pytest.raises(ValidationError):
            _valid_candle(interval="1WK")

    def test_utc_aware_timestamp_is_normalized_to_naive(self):
        candle = _valid_candle(timestamp=datetime(2026, 1, 2, tzinfo=UTC))
        assert candle.timestamp == datetime(2026, 1, 2)
        assert candle.timestamp.tzinfo is None

    def test_non_utc_aware_timestamp_raises(self):
        from datetime import timedelta

        eastern = timezone(timedelta(hours=-5))
        with pytest.raises(ValidationError, match="must be UTC"):
            _valid_candle(timestamp=datetime(2026, 1, 2, tzinfo=eastern))

    @pytest.mark.parametrize(
        "bad",
        [
            {"open": 0.0},
            {"high": -1.0},
            {"close": float("nan")},
            {"volume": -100},
            {"adj_close": 0.0},
        ],
    )
    def test_invalid_market_values_raise(self, bad):
        with pytest.raises(ValidationError):
            _valid_candle(**bad)

    def test_high_below_ohlc_extreme_raises(self):
        # high must be >= max(open, close)
        with pytest.raises(ValidationError, match="high"):
            _valid_candle(open=100.0, close=104.0, high=103.0)

    def test_low_above_ohlc_extreme_raises(self):
        # low must be <= min(open, close)
        with pytest.raises(ValidationError, match="low"):
            _valid_candle(open=100.0, close=99.0, low=99.5)

    def test_invalid_ticker_or_interval_raise(self):
        with pytest.raises(ValidationError):
            _valid_candle(ticker="bad ticker")
        with pytest.raises(ValidationError):
            _valid_candle(interval="1h")


class TestObservationUniqueness:
    def test_observation_key_shape(self):
        candle = _valid_candle()
        key = candle_observation_key(candle)
        assert key == ("AAPL", datetime(2026, 1, 2), "1d")

    def test_duplicate_observations_detected(self):
        duplicate = _valid_candle()  # same (ticker, timestamp, interval)
        # Same observation key but a different (still OHLC-consistent) close.
        different_close = _valid_candle(close=110.0, high=111.0)
        other_day = _valid_candle(timestamp=datetime(2026, 1, 3))
        other_interval = _valid_candle(interval="1wk")
        other_ticker = _valid_candle(ticker="MSFT")

        keys = [
            candle_observation_key(c)
            for c in [duplicate, different_close, other_day, other_interval, other_ticker]
        ]
        # Two candles collide on the same observation key → one duplicate.
        assert find_duplicates(keys) == [("AAPL", datetime(2026, 1, 2), "1d")]
