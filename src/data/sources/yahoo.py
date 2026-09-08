"""Yahoo Finance historical data adapter (MVP source).

The approved ingestion blueprint (DATA_INGESTION_BLUEPRINT.md section
1.2) names the ``yfinance`` library. That SDK is not on the
Engineering Constitution's allowed-dependency list, which explicitly
permits ``requests`` for HTTP data fetching; this adapter therefore
implements the same source (the Yahoo Finance chart API) directly over
``requests``. The deviation is recorded in ADR-0024; provider-specific
logic is fully isolated here so swapping in ``yfinance`` or a second
source later does not touch the pipeline.

Requested range maps to the ``period1``/``period2`` epoch parameters
(inclusive start, exclusive end + 1 day). Daily/weekly/monthly
intervals are passed through verbatim (``1d``/``1wk``/``1mo``).

Timezone semantics (DATA_ARCHITECTURE.md section 4): Yahoo chart
timestamps are epoch seconds; for US daily data the UTC date of the
epoch equals the session date, so each record is emitted with its
UTC calendar date (``YYYY-MM-DD``). No timezone guessing occurs.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime, timezone
from typing import Any

import requests

from src.core.validation import validate_ticker
from src.data.sources.base import FetchedData, FetchParams
from src.data.sources.errors import (
    SourceConnectionError,
    SourceNotFoundError,
    SourceRateLimitError,
    SourceResponseError,
    SourceServerError,
)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{quote}"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (finance-ai-mvp research ingestion; " f"requests/{requests.__version__})"
)

_INTERVAL_MAP = {"1d": "1d", "1wk": "1wk", "1mo": "1mo"}


class YahooFinanceSource:
    """Fetch historical OHLCV candles from the Yahoo Finance chart API."""

    name = "yahoo_finance"

    def __init__(
        self,
        *,
        timeout_s: float = 30.0,
        session: requests.Session | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.timeout_s = timeout_s
        self._session = session or requests.Session()
        self._user_agent = user_agent or DEFAULT_USER_AGENT

    # ------------------------------------------------------------------
    # Public contract
    # ------------------------------------------------------------------
    def fetch(self, params: FetchParams) -> FetchedData:
        ticker = validate_ticker(params.instrument)
        interval = _interval(params.interval)

        url = CHART_URL.format(quote=ticker)
        query = {
            "period1": _to_epoch(params.start),
            "period2": _to_epoch(_day_after(params.end)),
            "interval": interval,
            "includeAdjustedClose": "true",
        }
        headers = {"User-Agent": self._user_agent}

        response = self._http_get(url, params=query, headers=headers)
        self._raise_for_status(response)

        try:
            payload = json.loads(response.text) if isinstance(response.text, str) else response.text
        except ValueError as error:
            raise SourceResponseError(
                f"provider returned invalid JSON from {response.url}",
                context={"url": response.url},
            ) from error
        parsed = parse_chart_response(payload)
        return FetchedData(
            source=self.name,
            symbol=ticker,
            interval=interval,
            start=params.start,
            end=params.end,
            records=tuple(parsed["records"]),
            dropped_count=parsed["dropped_count"],
        )

    # ------------------------------------------------------------------
    # HTTP boundary (overridable in tests)
    # ------------------------------------------------------------------
    def _http_get(self, url: str, *, params: dict[str, Any], headers: dict[str, str]) -> Any:
        try:
            return self._session.get(url, params=params, headers=headers, timeout=self.timeout_s)
        except requests.RequestException as error:
            raise SourceConnectionError(
                f"connection to {url} failed: {error}", context={"url": url}
            ) from error

    @staticmethod
    def _raise_for_status(response: Any) -> None:
        status = response.status_code
        if 200 <= status < 300:
            return
        if status == 429:
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            raise SourceRateLimitError(
                f"HTTP 429 (Too Many Requests) from {response.url}",
                retry_after_s=retry_after,
                context={"url": response.url},
            )
        if status == 404:
            raise SourceNotFoundError(
                f"HTTP 404 (Not Found) for {response.url}",
                context={"url": response.url},
            )
        if status in (401, 403):
            raise SourceResponseError(
                f"HTTP {status} (auth/permission) for {response.url} — not retryable",
                context={"url": response.url},
            )
        if 500 <= status < 600:
            raise SourceServerError(
                f"HTTP {status} (server error) from {response.url}",
                context={"url": response.url},
            )
        raise SourceResponseError(
            f"unexpected HTTP {status} from {response.url}",
            context={"url": response.url},
        )


# ---------------------------------------------------------------------------
# Pure response parsing (unit-tested without network)
# ---------------------------------------------------------------------------
def parse_chart_response(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Parse a Yahoo chart-API payload into provider-neutral records.

    Expected shape::

        {"chart": {"result": [{"timestamp": [...], "indicators": {
            "quote": [{"open": [...], "high": [...], "low": [...],
                       "close": [...], "volume": [...], "adjclose": [...]}]}}],
            "error": null}}

    Returns:
        ``{"records": [...], "dropped_count": int}`` where each record is
        ``{"timestamp": "YYYY-MM-DD", "open": float, "high": float,
        "low": float, "close": float, "adj_close": float|None,
        "volume": int}``.

    Raises:
        SourceResponseError: on malformed shapes and provider errors.
        SourceNotFoundError: when the provider reports the symbol missing.
    """
    try:
        chart = payload["chart"]
    except (KeyError, TypeError) as error:
        raise SourceResponseError("chart payload has no 'chart' object") from error

    chart_error = chart.get("error") if isinstance(chart, dict) else None
    result = chart.get("result") if isinstance(chart, dict) else None

    if chart_error is not None:
        message = str(chart_error.get("description") or chart_error)
        if str(chart_error.get("code", "")).lower() == "not found":
            raise SourceNotFoundError(f"provider reports symbol not found: {message}")
        raise SourceResponseError(f"provider chart error: {message}")

    if not isinstance(result, list) or len(result) == 0:
        return {"records": [], "dropped_count": 0}

    try:
        block = result[0]
        timestamps: list[Any] = block["timestamp"]
        quote = block["indicators"]["quote"][0]
    except (KeyError, TypeError, IndexError) as error:
        raise SourceResponseError(
            "chart result is missing timestamp or quote indicators"
        ) from error

    open_series = quote.get("open")
    high_series = quote.get("high")
    low_series = quote.get("low")
    close_series = quote.get("close")
    volume_series = quote.get("volume")
    adjclose_series = _adjclose_series(block)

    series = [timestamps, open_series, high_series, low_series, close_series, volume_series]
    if not all(isinstance(s, list) for s in series):
        raise SourceResponseError("chart indicators contain non-list series")

    lengths = {len(s) for s in series}  # type: ignore[arg-type]
    if adjclose_series is not None:
        lengths.add(len(adjclose_series))
    if len(lengths) != 1:
        raise SourceResponseError(f"mismatched series lengths in chart payload: {sorted(lengths)}")

    records: list[dict[str, Any]] = []
    dropped = 0
    for index, epoch in enumerate(timestamps):
        ohlc = [
            open_series[index],
            high_series[index],
            low_series[index],
            close_series[index],
            volume_series[index],
        ]
        if _missing(epoch) or any(_missing(value) for value in ohlc[:4]):
            dropped += 1
            continue

        volume = int(float(volume_series[index]) or 0)
        adj_close = None
        if adjclose_series is not None and not _missing(adjclose_series[index]):
            adj_close = float(adjclose_series[index])

        records.append(
            {
                "timestamp": _utc_date(epoch),
                "open": float(open_series[index]),
                "high": float(high_series[index]),
                "low": float(low_series[index]),
                "close": float(close_series[index]),
                "adj_close": adj_close,
                "volume": volume,
            }
        )
    return {"records": records, "dropped_count": dropped}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _interval(value: str) -> str:
    try:
        return _INTERVAL_MAP[value]
    except KeyError:
        raise SourceResponseError(f"unsupported interval {value!r} for Yahoo Finance") from None


def _to_epoch(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())


def _day_after(day: date) -> date:
    from datetime import timedelta

    return day + timedelta(days=1)


def _utc_date(epoch: Any) -> str:
    try:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError) as error:
        raise SourceResponseError(f"invalid epoch timestamp {epoch!r}") from error


def _missing(value: Any) -> bool:
    return value is None


def _adjclose_series(block: Mapping[str, Any]) -> list[Any] | None:
    indicators = block.get("indicators")
    if not isinstance(indicators, dict):
        return None
    adjclose = indicators.get("adjclose")
    if isinstance(adjclose, list) and adjclose and isinstance(adjclose[0], dict):
        return adjclose[0].get("adjclose")
    return None


def _parse_retry_after(header: str | None) -> float | None:
    if not header:
        return None
    try:
        return float(header)
    except ValueError:
        return None
