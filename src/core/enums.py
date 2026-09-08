"""Typed domain vocabulary fixed by the approved architecture.

These enums exist so the codebase never repeats magic string literals.
Each value set is taken verbatim from the architecture documents:

- ``MarketInterval`` — DATA_ARCHITECTURE.md section 4.3 (``1d``/``1wk``/``1mo``)
- ``LabelValue`` — LABEL_GENERATION_BLUEPRINT.md (UP/DOWN/HOLD)
- ``CorporateActionType`` — DATA_ARCHITECTURE.md section 3.3
- ``TradingSessionType`` — DATA_ARCHITECTURE.md section 3.4
- ``AppEnvironment`` — ENGINEERING_CONSTITUTION.md config policy
- ``StorageTier`` — DATA_ARCHITECTURE.md section 7.1

``str``-mixin enums keep Python 3.10 compatibility (ADR-0002) and can
be used directly as configuration/string values.
"""

from __future__ import annotations

from enum import Enum


def values_of(enum_type: type[Enum]) -> frozenset[str]:
    """Return the set of string values declared by a ``str``-mixin enum."""
    return frozenset(member.value for member in enum_type)  # type: ignore[attr-defined]


class MarketInterval(str, Enum):
    """Candle interval identifiers (DATA_ARCHITECTURE.md section 4.3)."""

    DAILY = "1d"
    WEEKLY = "1wk"
    MONTHLY = "1mo"


class LabelValue(str, Enum):
    """Directional classification labels (LABEL_GENERATION_BLUEPRINT.md)."""

    UP = "UP"
    DOWN = "DOWN"
    HOLD = "HOLD"


class CorporateActionType(str, Enum):
    """Corporate action types (DATA_ARCHITECTURE.md section 3.3)."""

    SPLIT = "split"
    DIVIDEND = "dividend"
    TICKER_CHANGE = "ticker_change"
    MERGER = "merger"
    DELISTING = "delisting"


class TradingSessionType(str, Enum):
    """Trading calendar session types (DATA_ARCHITECTURE.md section 3.4)."""

    REGULAR = "regular"
    EARLY_CLOSE = "early_close"
    HOLIDAY = "holiday"


class AppEnvironment(str, Enum):
    """Application environments (ENGINEERING_CONSTITUTION.md section 5)."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class StorageTier(str, Enum):
    """Three-tier data storage lifecycle (DATA_ARCHITECTURE.md section 7.1)."""

    RAW = "raw"
    INTERIM = "interim"
    PROCESSED = "processed"
