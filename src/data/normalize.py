"""Normalization: provider-neutral records → domain candles.

Follows DATA_INGESTION_BLUEPRINT.md section 6. Rows are normalized
deterministically:

- timestamps: ISO date strings → naive-UTC ``datetime`` at midnight
  (DATA_ARCHITECTURE.md section 4: storage is naive UTC; the adapter
  has already pinned provider epochs to UTC calendar dates — no
  timezone guessing happens here)
- numerics: prices → ``float``, volume → ``int``
- identity: ticker/interval validated through the domain layer
- ordering: candles are sorted ascending (documented normalization rule)

Row-level violations (bad OHLC, non-numeric fields, parse failures,
duplicate timestamps within one fetch) reject the individual row;
they do not abort the whole fetch. The engine decides the run status
from the resulting counts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from numbers import Number
from typing import Any

from src.core.errors import ValidationError
from src.core.models import Candle
from src.core.validation import to_naive_utc, validate_ticker
from src.data.sources.base import FetchedData


@dataclass(frozen=True)
class CandleBatch:
    """Result of normalizing one fetch into domain candles."""

    candles: tuple[Candle, ...]
    rejected_rows: int = 0  # rows that failed normalization/domain validation
    duplicates: int = 0  # duplicate timestamps within this fetch (dropped)
    reasons: tuple[str, ...] = ()  # short rejection reasons (bounded)


_MAX_REASON_SAMPLES = 10


def normalize_fetched_to_candles(fetched: FetchedData) -> CandleBatch:
    """Convert a provider-neutral fetch into validated, sorted candles.

    Args:
        fetched: Output of a :class:`HistoricalDataSource` adapter.

    Returns:
        A :class:`CandleBatch`; invalid rows never abort the batch.
    """
    ticker = validate_ticker(fetched.symbol)
    reasons: list[str] = []
    rejected = 0
    candles: list[Candle] = []

    for index, record in enumerate(fetched.records):
        try:
            row = _parse_record(record, index)
            candles.append(
                Candle(
                    ticker=ticker,
                    timestamp=row["timestamp"],
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"],
                    interval=fetched.interval,
                    adj_close=row["adj_close"],
                    source=fetched.source,
                )
            )
        except ValidationError as error:
            rejected += 1
            _record_reason(reasons, f"row {index}: {error.message}")

    # Deterministic ordering (normalization rule 6.2) before dedup so
    # "first occurrence wins" is stable.
    candles.sort(key=lambda candle: candle.timestamp)

    unique: list[Candle] = []
    seen: set[datetime] = set()
    duplicates = 0
    for candle in candles:
        if candle.timestamp in seen:
            duplicates += 1
            _record_reason(
                reasons, f"duplicate timestamp {candle.timestamp.isoformat()} within fetch"
            )
            continue
        seen.add(candle.timestamp)
        unique.append(candle)

    return CandleBatch(
        candles=tuple(unique),
        rejected_rows=rejected,
        duplicates=duplicates,
        reasons=tuple(reasons[:_MAX_REASON_SAMPLES]),
    )


def _parse_record(record: Mapping[str, Any], index: int) -> dict[str, Any]:
    """Parse one provider-neutral record into primitive fields."""
    try:
        timestamp_raw = record["timestamp"]
    except KeyError:
        raise ValidationError("record has no 'timestamp' field") from None

    if not isinstance(timestamp_raw, str):
        raise ValidationError(f"timestamp must be a string, got {type(timestamp_raw).__name__}")

    try:
        # ISO date string → naive-UTC midnight (the storage policy for
        # daily candles; the adapter pinned provider epochs to UTC dates).
        timestamp = datetime.fromisoformat(timestamp_raw)
    except ValueError:
        raise ValidationError(
            f"timestamp {timestamp_raw!r} is not an ISO date (YYYY-MM-DD)"
        ) from None

    open_ = _as_price(record.get("open"), "open")
    high = _as_price(record.get("high"), "high")
    low = _as_price(record.get("low"), "low")
    close = _as_price(record.get("close"), "close")
    volume = _as_volume(record.get("volume"))

    adj_close_raw = record.get("adj_close")
    adj_close = None
    if adj_close_raw is not None and not _blank(adj_close_raw):
        adj_close = _as_price(adj_close_raw, "adj_close")

    # Candle-level validation (OHLC relationships, positivity, interval)
    # runs in the domain model; parse-level checks end here.
    return {
        "timestamp": to_naive_utc(timestamp),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "adj_close": adj_close,
    }


def _as_price(value: Any, field: str) -> float:
    if _blank(value):
        raise ValidationError(f"{field} is missing/null")
    if isinstance(value, bool) or not isinstance(value, Number):
        try:
            return float(value)  # tolerate numeric strings from providers
        except (TypeError, ValueError):
            raise ValidationError(f"{field} is not numeric: {value!r}") from None
    return float(value)


def _as_volume(value: Any) -> int:
    if _blank(value):
        raise ValidationError("volume is missing/null")
    if isinstance(value, bool):
        raise ValidationError("volume is not numeric")
    try:
        return int(float(value))
    except (TypeError, ValueError):
        raise ValidationError(f"volume is not numeric: {value!r}") from None


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _record_reason(reasons: list[str], message: str) -> None:
    if len(reasons) < _MAX_REASON_SAMPLES:
        reasons.append(message)
