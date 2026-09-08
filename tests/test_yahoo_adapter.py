"""Tests for src/data/sources/yahoo.py — parsing + HTTP error mapping.

All tests are offline: response parsing is exercised with payload
dicts, and the HTTP boundary with scripted fake session responses.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
import requests

from src.data.sources.errors import (
    SourceConnectionError,
    SourceNotFoundError,
    SourceRateLimitError,
    SourceResponseError,
    SourceServerError,
)
from src.data.sources.yahoo import YahooFinanceSource, parse_chart_response

EPOCH_2025_01_02 = 1735776000  # 2025-01-02T00:00:00Z


def _chart_payload(
    *,
    timestamps=None,
    opens=None,
    highs=None,
    lows=None,
    closes=None,
    volumes=None,
    adjcloses=None,
    error=None,
) -> dict:
    n = len(timestamps) if timestamps is not None else 0
    opens = opens if opens is not None else [100.0] * n
    highs = highs if highs is not None else [101.0] * n
    lows = lows if lows is not None else [99.0] * n
    closes = closes if closes is not None else [100.5] * n
    volumes = volumes if volumes is not None else [1_000_000] * n
    quote = {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes}
    indicators: dict = {"quote": [quote]}
    if adjcloses is not None:
        indicators["adjclose"] = [{"adjclose": adjcloses}]
    result = {"timestamp": timestamps, "indicators": indicators}
    return {"chart": {"result": [result] if timestamps is not None else [], "error": error}}


class TestParseChartResponse:
    def test_valid_payload_maps_records(self):
        payload = _chart_payload(
            timestamps=[EPOCH_2025_01_02],
            opens=[100.0],
            highs=[101.5],
            lows=[99.0],
            closes=[101.0],
            volumes=[2_500_000],
            adjcloses=[100.9],
        )
        parsed = parse_chart_response(payload)
        assert parsed["dropped_count"] == 0
        assert len(parsed["records"]) == 1
        record = parsed["records"][0]
        assert record["timestamp"] == "2025-01-02"  # UTC calendar date
        assert record["open"] == 100.0
        assert record["high"] == 101.5
        assert record["low"] == 99.0
        assert record["close"] == 101.0
        assert record["volume"] == 2_500_000
        assert record["adj_close"] == 100.9

    def test_null_ohlc_rows_are_dropped(self):
        payload = _chart_payload(
            timestamps=[EPOCH_2025_01_02, EPOCH_2025_01_02 + 86400],
            opens=[100.0, None],
            highs=[101.0, None],
            lows=[99.0, None],
            closes=[100.5, None],
            volumes=[1_000_000, None],
        )
        parsed = parse_chart_response(payload)
        assert len(parsed["records"]) == 1
        assert parsed["dropped_count"] == 1

    def test_adj_close_absent_becomes_none(self):
        payload = _chart_payload(timestamps=[EPOCH_2025_01_02])
        parsed = parse_chart_response(payload)
        assert parsed["records"][0]["adj_close"] is None

    def test_empty_result_returns_no_records(self):
        assert parse_chart_response({"chart": {"result": [], "error": None}}) == {
            "records": [],
            "dropped_count": 0,
        }

    def test_provider_not_found_error_raises_not_found(self):
        payload = {
            "chart": {"result": None, "error": {"code": "Not Found", "description": "no symbol"}}
        }
        with pytest.raises(SourceNotFoundError):
            parse_chart_response(payload)

    def test_provider_generic_error_raises_response_error(self):
        payload = {
            "chart": {"result": None, "error": {"code": "Bad Request", "description": "boom"}}
        }
        with pytest.raises(SourceResponseError, match="boom"):
            parse_chart_response(payload)

    def test_missing_chart_key_raises(self):
        with pytest.raises(SourceResponseError, match="no 'chart'"):
            parse_chart_response({"other": {}})

    def test_missing_indicators_raises(self):
        with pytest.raises(SourceResponseError, match="missing timestamp or quote"):
            parse_chart_response({"chart": {"result": [{"timestamp": [1]}], "error": None}})

    def test_mismatched_series_lengths_raise(self):
        payload = _chart_payload(timestamps=[EPOCH_2025_01_02, EPOCH_2025_01_02 + 86400])
        payload["chart"]["result"][0]["indicators"]["quote"][0]["open"] = [100.0]
        with pytest.raises(SourceResponseError, match="mismatched series lengths"):
            parse_chart_response(payload)

    def test_invalid_epoch_raises(self):
        payload = _chart_payload(timestamps=["not-an-epoch"])
        with pytest.raises(SourceResponseError, match="invalid epoch"):
            parse_chart_response(payload)


class TestYahooFinanceSourceHttp:
    """Scripted-session tests of the adapter's HTTP boundary."""

    class _FakeResponse:
        def __init__(self, status_code=200, headers=None, url="http://test/yahoo", text="{}"):
            self.status_code = status_code
            self.headers = headers or {}
            self.url = url
            self.text = text

    class _RecordingSession:
        def __init__(self, response, exc=None):
            self.response = response
            self.exc = exc
            self.calls = []

        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            if self.exc is not None:
                raise self.exc
            return self.response

    def _adapter(self, session):
        return YahooFinanceSource(timeout_s=5.0, session=session)

    def test_fetch_builds_request_and_parses(self):
        payload = _chart_payload(
            timestamps=[EPOCH_2025_01_02],
            opens=[100.0],
            highs=[101.0],
            lows=[99.0],
            closes=[100.5],
            volumes=[1_000_000],
        )
        session = self._RecordingSession(
            self._FakeResponse(status_code=200, text=json.dumps(payload))
        )
        fetched = self._adapter(session).fetch(_params())
        assert fetched.source == "yahoo_finance"
        assert fetched.symbol == "AAPL"
        assert len(fetched.records) == 1

    def test_fetch_429_raises_rate_limit_with_retry_after(self):
        session = self._RecordingSession(
            self._FakeResponse(status_code=429, headers={"Retry-After": "7"})
        )
        with pytest.raises(SourceRateLimitError) as exc:
            self._adapter(session).fetch(_params())
        assert exc.value.retryable is True
        assert exc.value.retry_after_s == 7.0

    def test_fetch_404_raises_not_found_not_retryable(self):
        session = self._RecordingSession(self._FakeResponse(status_code=404))
        with pytest.raises(SourceNotFoundError) as exc:
            self._adapter(session).fetch(_params())
        assert exc.value.retryable is False

    def test_fetch_500_raises_server_error_retryable(self):
        session = self._RecordingSession(self._FakeResponse(status_code=503))
        with pytest.raises(SourceServerError) as exc:
            self._adapter(session).fetch(_params())
        assert exc.value.retryable is True

    def test_fetch_401_raises_response_error_not_retryable(self):
        session = self._RecordingSession(self._FakeResponse(status_code=401))
        with pytest.raises(SourceResponseError) as exc:
            self._adapter(session).fetch(_params())
        assert exc.value.retryable is False

    def test_fetch_connection_failure_raises_connection_error(self):
        session = self._RecordingSession(None, exc=requests.Timeout("slow"))
        with pytest.raises(SourceConnectionError) as exc:
            self._adapter(session).fetch(_params())
        assert exc.value.retryable is True

    def test_fetch_invalid_json_body_raises_response_error(self):
        session = self._RecordingSession(
            self._FakeResponse(status_code=200, text="<html>oops</html>")
        )
        with pytest.raises(SourceResponseError, match="invalid JSON"):
            self._adapter(session).fetch(_params())

    def test_fetch_unsupported_interval_raises(self):
        session = self._RecordingSession(self._FakeResponse(status_code=200))
        with pytest.raises(SourceResponseError, match="unsupported interval"):
            self._adapter(session).fetch(_params(interval="5m"))


def _params(interval: str = "1d"):
    from src.data.sources.base import FetchParams

    return FetchParams(
        instrument="AAPL", start=date(2025, 1, 2), end=date(2025, 1, 2), interval=interval
    )
