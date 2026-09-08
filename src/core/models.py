"""Foundational domain types for the data layer.

Two small, frozen, validated models — one per responsibility:

- :class:`Instrument` — a security/ticker identity
- :class:`Candle` — one market observation (OHLCV at a timestamp)

These mirror the approved database entities (DATA_ARCHITECTURE.md
sections 3.1/3.2) but are **file-based domain types**: identity is
the ticker, not a database primary key (ADR-0005 — the MVP stores
data as files; PostgreSQL arrives in Phase 2). Database ``id`` and
``ingested_at`` bookkeeping belong to the storage layer of a later
milestone, not to these pure types.

Validation runs in ``__post_init__`` using the shared primitives so a
Candle can never be constructed in an invalid state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.core.errors import ValidationError
from src.core.validation import (
    to_naive_utc,
    validate_interval,
    validate_nonnegative_volume,
    validate_optional_positive_price,
    validate_positive_price,
    validate_ticker,
)


@dataclass(frozen=True)
class Instrument:
    """A tradeable instrument identity (file-based, ticker-keyed)."""

    ticker: str
    name: str | None = None
    exchange: str | None = None
    sector: str | None = None
    industry: str | None = None
    is_active: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", validate_ticker(self.ticker))
        for attribute, label in (
            ("name", "name"),
            ("exchange", "exchange"),
            ("sector", "sector"),
            ("industry", "industry"),
        ):
            value = getattr(self, attribute)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValidationError(
                    f"{label} must be a non-empty string or None", context={label: value}
                )
        if not isinstance(self.is_active, bool):
            raise ValidationError(
                "is_active must be a boolean", context={"is_active": self.is_active}
            )


@dataclass(frozen=True)
class Candle:
    """One OHLCV market observation.

    Field types follow DATA_ARCHITECTURE.md section 3.2. ``timestamp``
    is a naive-UTC datetime (the storage policy from section 4.2).
    Uniqueness of observations is ``(ticker, timestamp, interval)`` —
    the exact key of the market_candles UNIQUE constraint (section 3.2).
    """

    ticker: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    interval: str = "1d"
    adj_close: float | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", validate_ticker(self.ticker))
        object.__setattr__(self, "timestamp", to_naive_utc(self.timestamp))
        object.__setattr__(self, "interval", validate_interval(self.interval))

        open_ = validate_positive_price(self.open, "open")
        high = validate_positive_price(self.high, "high")
        low = validate_positive_price(self.low, "low")
        close = validate_positive_price(self.close, "close")
        volume = validate_nonnegative_volume(self.volume, "volume")

        if high < max(open_, close):
            raise ValidationError(
                "high must be >= max(open, close) (VAL-010)", context={"candle": str(self)}
            )
        if low > min(open_, close):
            raise ValidationError(
                "low must be <= min(open, close) (VAL-011)", context={"candle": str(self)}
            )

        object.__setattr__(self, "open", open_)
        object.__setattr__(self, "high", high)
        object.__setattr__(self, "low", low)
        object.__setattr__(self, "close", close)
        object.__setattr__(self, "volume", volume)
        object.__setattr__(
            self, "adj_close", validate_optional_positive_price(self.adj_close, "adj_close")
        )

        if self.source is not None and (
            not isinstance(self.source, str) or not self.source.strip()
        ):
            raise ValidationError(
                "source must be a non-empty string or None", context={"source": self.source}
            )


def candle_observation_key(candle: Candle) -> tuple[str, datetime, str]:
    """Return the unique observation key ``(ticker, timestamp, interval)``.

    Matches the ``market_candles`` UNIQUE constraint so duplicates can
    be rejected before they reach storage.
    """
    return (candle.ticker, candle.timestamp, candle.interval)
