"""Reusable data validation primitives.

These primitives encode the fixed validation rules from the approved
architecture that the *foundation* needs:

- ticker format (DATA_ARCHITECTURE.md section 3.1 CHECK constraint)
- timestamps: naive-UTC storage policy (DATA_ARCHITECTURE.md section 4.1/4.2)
- OHLC prices and volume (section 3.2 CHECK constraints)
- candle intervals (section 4.3)
- time-series integrity: chronological order and uniqueness
  (section 6.1 VAL-003 / VAL-004)

This is NOT the market-data cleaning engine (a later milestone);
these are small, pure, independently testable building blocks.

Every function raises :class:`ValidationError` on failure and never
silently coerces or alters data.
"""

from __future__ import annotations

import math
import re
from collections.abc import Hashable, Iterable, Sequence
from datetime import datetime, timedelta
from numbers import Number

from src.core.enums import MarketInterval, values_of
from src.core.errors import ValidationError

# Ticker format from DATA_ARCHITECTURE.md section 3.1 instruments CHECK.
TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")

INTERVALS = values_of(MarketInterval)


# ---------------------------------------------------------------------------
# Ticker
# ---------------------------------------------------------------------------
def normalize_ticker(ticker: str) -> str:
    """Normalize a ticker for boundary validation (strip + uppercase).

    Raises:
        ValidationError: if ``ticker`` is not a non-empty string.
    """
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValidationError("ticker must be a non-empty string", context={"value": ticker})
    return ticker.strip().upper()


def validate_ticker(ticker: str) -> str:
    """Validate a ticker and return its normalized form.

    Matches the ``instruments.ticker`` CHECK constraint
    ``^[A-Z]{1,5}(\\.[A-Z])?$`` (DATA_ARCHITECTURE.md section 3.1),
    e.g. ``AAPL`` or ``BRK.B``.

    Raises:
        ValidationError: if the ticker does not match the approved format.
    """
    normalized = normalize_ticker(ticker)
    if not TICKER_PATTERN.match(normalized):
        raise ValidationError(
            f"invalid ticker {normalized!r}: expected format like 'AAPL' or 'BRK.B'",
            context={"ticker": normalized},
        )
    return normalized


# ---------------------------------------------------------------------------
# Timestamps (naive-UTC storage policy, DATA_ARCHITECTURE.md section 4)
# ---------------------------------------------------------------------------
def to_naive_utc(value: datetime) -> datetime:
    """Return ``value`` as a naive datetime representing UTC.

    Policy (DATA_ARCHITECTURE.md section 4.2): all timestamps are stored
    as naive UTC (``TIMESTAMP`` without timezone). Naive inputs are
    assumed UTC and returned unchanged. UTC-aware inputs are converted
    explicitly. Non-UTC aware inputs are rejected — timestamps are never
    silently altered or re-interpreted.

    Raises:
        ValidationError: if ``value`` is not a datetime or is aware in a
            non-UTC timezone.
    """
    if not isinstance(value, datetime):
        raise ValidationError(
            f"expected datetime, got {type(value).__name__}", context={"value": value}
        )
    if value.tzinfo is None:
        return value
    if value.utcoffset() != timedelta(0):
        raise ValidationError(
            "timezone-aware timestamp must be UTC (naive-UTC storage policy)",
            context={"value": value.isoformat()},
        )
    return value.replace(tzinfo=None)


def validate_market_timestamp(value: datetime) -> datetime:
    """Validate a single market timestamp and return naive-UTC form."""
    return to_naive_utc(value)


# ---------------------------------------------------------------------------
# Numeric market values
# ---------------------------------------------------------------------------
def _as_finite_float(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Number):
        raise ValidationError(f"{field} must be numeric", context={field: value})
    number = float(value)  # type: ignore[arg-type]
    if not math.isfinite(number):
        raise ValidationError(f"{field} must be finite", context={field: value})
    return number


def validate_positive_price(value: object, field: str = "price") -> float:
    """Validate a price is a finite number strictly greater than zero."""
    number = _as_finite_float(value, field)
    if number <= 0:
        raise ValidationError(f"{field} must be > 0", context={field: value})
    return number


def validate_optional_positive_price(value: object | None, field: str) -> float | None:
    """Validate an optional positive price (``None`` is allowed)."""
    if value is None:
        return None
    return validate_positive_price(value, field)


def validate_nonnegative_volume(value: object, field: str = "volume") -> float:
    """Validate volume is a finite number >= 0.

    Volume is kept numeric (int or float); the PostgreSQL ``BIGINT``
    target is a Phase-2 concern (DATA_ARCHITECTURE.md section 3.2).
    """
    number = _as_finite_float(value, field)
    if number < 0:
        raise ValidationError(f"{field} must be >= 0", context={field: value})
    return number


def validate_interval(value: object) -> str:
    """Validate a candle interval is one of the approved values."""
    if not isinstance(value, str) or value not in INTERVALS:
        raise ValidationError(
            f"invalid interval {value!r}: expected one of {sorted(INTERVALS)}",
            context={"interval": value},
        )
    return value


# ---------------------------------------------------------------------------
# Time-series integrity (DATA_ARCHITECTURE.md section 6.1 VAL-003 / VAL-004)
# ---------------------------------------------------------------------------
def find_duplicates(items: Iterable[Hashable]) -> list[Hashable]:
    """Return values that occur more than once, in first-occurrence order."""
    seen: set[Hashable] = set()
    duplicates: set[Hashable] = set()
    ordered: list[Hashable] = []
    for item in items:
        if item in seen and item not in duplicates:
            duplicates.add(item)
            ordered.append(item)
        seen.add(item)
    return ordered


def validate_unique(items: Sequence[Hashable], *, label: str = "item") -> None:
    """Reject sequences containing duplicate values (VAL-004 analog)."""
    duplicates = find_duplicates(items)
    if duplicates:
        raise ValidationError(
            f"{label} values must be unique; duplicates: {duplicates!r}",
            context={"duplicates": [str(d) for d in duplicates]},
        )


def validate_chronological(items: Sequence[object], *, label: str = "timestamp") -> None:
    """Reject sequences that are not strictly ascending (VAL-003 analog).

    Raises:
        ValidationError: on the first out-of-order pair, reporting both
            the position and the offending values for debugging.
    """
    for index in range(1, len(items)):
        previous, current = items[index - 1], items[index]
        if not (previous < current):  # type: ignore[operator]
            raise ValidationError(
                f"{label} values must be strictly ascending; violation at "
                f"position {index}: {previous!r} followed by {current!r}",
                context={"position": index, "previous": str(previous), "current": str(current)},
            )


def validate_market_timestamps(values: Sequence[datetime]) -> list[datetime]:
    """Validate a sequence of market timestamps.

    Converts every value to naive-UTC (rejecting non-UTC aware input),
    then enforces strict chronological order and uniqueness.

    Returns:
        The normalized (naive-UTC) timestamp list.
    """
    normalized = [to_naive_utc(value) for value in values]
    validate_chronological(normalized, label="timestamp")
    validate_unique(normalized, label="timestamp")
    return normalized
