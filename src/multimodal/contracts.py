"""Point-in-time external data contracts (Post-MVP Milestone 08).

Every external record distinguishes:

- EVENT TIME      — when the economic event occurred
- PUBLICATION TIME— when the information became publicly available
- INGESTION TIME  — when our system received it
- AVAILABILITY TIME — the timestamp that determines model eligibility

The availability timestamp is authoritative for point-in-time joins
(milestone section 5): a model at time T may only use records whose
availability_timestamp <= T. Event time alone is NEVER sufficient
(a fiscal quarter may end 2026-06-30 but be published 2026-08-10; a
prediction on 2026-08-05 must not see it).

All timestamps are normalized to naive UTC (the project's canonical
representation, Milestone 11 timezone audit); the original source timezone
is preserved alongside for auditability. Ambiguous/naive source timestamps
without a declared timezone are marked temporally unreliable and excluded
from point-in-time joins rather than silently interpreted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class TemporalReliability(str, Enum):
    """Whether a record's availability time can be trusted for as-of joins."""

    RELIABLE = "RELIABLE"  # explicit publication timestamp with timezone
    DAY_ONLY = "DAY_ONLY"  # publication date known, intraday time unknown
    INSUFFICIENT = "INSUFFICIENT"  # no trustworthy publication time


class EventType(str, Enum):
    """Controlled event taxonomy (milestone section 13) — deliberately small."""

    EARNINGS = "EARNINGS"
    GUIDANCE = "GUIDANCE"
    MERGER = "MERGER"
    ACQUISITION = "ACQUISITION"
    CONTRACT = "CONTRACT"
    MANAGEMENT_CHANGE = "MANAGEMENT_CHANGE"
    REGULATORY = "REGULATORY"
    PRODUCT = "PRODUCT"
    LEGAL = "LEGAL"
    DIVIDEND = "DIVIDEND"
    BUYBACK = "BUYBACK"
    CREDIT = "CREDIT"
    OTHER = "OTHER"


EVENT_TYPES = frozenset(item.value for item in EventType)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ExternalRecord:
    """Normalized external record (fundamental OR event/news).

    ``availability_timestamp`` is the join key for point-in-time semantics.
    For fundamentals it equals the publication/filing timestamp; for events
    it equals the publication timestamp when known (never the event time).
    """

    record_id: str
    source: str
    source_identifier: str
    instrument: str  # resolved ticker (entity mapping applied)
    event_type: str  # EventType value or FUNDAMENTAL_FILING
    event_timestamp: datetime | None  # when the economic event occurred
    publication_timestamp: datetime | None  # when it became public
    ingestion_timestamp: datetime  # when our system received it
    availability_timestamp: datetime | None
    reliability: TemporalReliability
    original_timestamp: str | None = None
    original_timezone: str | None = None
    payload: dict = field(default_factory=dict)  # source-specific fields
    parse_status: str = "OK"

    def __post_init__(self) -> None:
        if self.event_type not in EVENT_TYPES and self.event_type != "FUNDAMENTAL_FILING":
            raise ValueError(f"unknown event type: {self.event_type!r}")


def availability_of(record: ExternalRecord) -> datetime | None:
    """The timestamp that determines model eligibility (milestone section 5)."""
    return record.availability_timestamp


def normalize_timestamp(
    raw: str | datetime | None,
    *,
    original_timezone: str | None = None,
) -> tuple[datetime | None, str | None, str | None, TemporalReliability]:
    """Normalize an external timestamp to naive UTC without silent guessing.

    Returns ``(normalized_utc, original_timestamp, original_timezone,
    reliability)``. Naive source timestamps are treated as UTC ONLY when the
    source declares UTC; otherwise they are marked DAY_ONLY/INSUFFICIENT —
    never silently interpreted (milestone section 20).
    """
    if raw is None:
        return None, None, original_timezone, TemporalReliability.INSUFFICIENT
    if isinstance(raw, datetime):
        stamp = raw
        original = raw.isoformat()
    else:
        original = str(raw)
        stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if stamp.tzinfo is not None:
        naive_utc = stamp.astimezone(timezone.utc).replace(tzinfo=None)
        return naive_utc, original, original_timezone or "UTC", TemporalReliability.RELIABLE
    # Naive source timestamp: only trustworthy if the source declares UTC.
    if original_timezone and original_timezone.upper() in {"UTC", "GMT", "+00:00"}:
        return stamp, original, original_timezone, TemporalReliability.RELIABLE
    # Timezone declared but unknown offset: the publication DAY is known, the
    # intraday UTC time is not. Return the naive wall-clock stamp with
    # DAY_ONLY reliability; as-of joins push eligibility to the start of the
    # NEXT day so no intraday assumption is ever made (section 19). With no
    # declared timezone at all the stamp is untrustworthy: INSUFFICIENT, None.
    if not original_timezone:
        return None, original, None, TemporalReliability.INSUFFICIENT
    return stamp, original, original_timezone, TemporalReliability.DAY_ONLY
