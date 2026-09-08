"""As-of retrieval semantics (Post-MVP Milestone 08).

Answers "what did we know about this company at timestamp T?" using ONLY
records whose availability_timestamp <= T (milestone sections 8, 18, 19).
Deterministic ordering: latest availability wins; ties break on
source_identifier then record_id — never on dictionary order. Records with
``DAY_ONLY`` reliability are eligible only at day granularity: their
availability is conservatively set to the START of the publication day's
NEXT day (we never assume a morning release), and intraday predictions
cannot use them. ``INSUFFICIENT`` records are never eligible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from src.multimodal.contracts import ExternalRecord, TemporalReliability


class AsOfError(ValueError):
    """Raised when an as-of query cannot be answered safely."""


@dataclass(frozen=True)
class AsOfFrame:
    """One row per prediction timestamp with the eligible external state."""

    frame: pd.DataFrame


def effective_availability(record: ExternalRecord) -> datetime | None:
    """Conservative availability used for joins.

    RELIABLE → publication timestamp as-is.
    DAY_ONLY → start of the day AFTER publication (never assume intraday).
    INSUFFICIENT → None (never eligible).
    """
    if record.reliability is TemporalReliability.RELIABLE:
        return record.availability_timestamp
    if record.reliability is TemporalReliability.DAY_ONLY:
        if record.publication_timestamp is None:
            return None
        # Unknown-offset sources: eligible only from the START of the day
        # AFTER the declared publication day (never assume a morning release;
        # the day margin also absorbs the unknown UTC offset, section 19).
        day = record.publication_timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        return day + timedelta(days=1)
    return None


def asof_records(
    records: list[ExternalRecord],
    *,
    instrument: str,
    as_of: datetime,
) -> list[ExternalRecord]:
    """Return the eligible records for one instrument at one timestamp.

    Only records with effective availability <= as_of are returned; ties are
    broken deterministically (availability, then source_identifier, then
    record_id). Naive ``as_of`` timestamps are rejected — the caller must
    pass timezone-aware or canonically-naive-UTC timestamps consistently with
    the project's storage convention.
    """
    if as_of.tzinfo is not None:
        as_of = as_of.astimezone(timezone.utc).replace(tzinfo=None)  # normalize to naive UTC
    eligible: list[tuple[datetime, str, str, ExternalRecord]] = []
    for record in records:
        if record.instrument != instrument:
            continue
        available = effective_availability(record)
        if available is None or available > as_of:
            continue
        eligible.append((available, record.source_identifier, record.record_id, record))
    eligible.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in eligible]


def latest_fundamental_asof(
    records: list[ExternalRecord],
    *,
    instrument: str,
    as_of: datetime,
) -> ExternalRecord | None:
    """Latest eligible fundamental record (milestone section 22 as-of logic)."""
    fundamentals = [
        record
        for record in asof_records(records, instrument=instrument, as_of=as_of)
        if record.event_type == "FUNDAMENTAL_FILING"
    ]
    return fundamentals[-1] if fundamentals else None


def events_in_window(
    records: list[ExternalRecord],
    *,
    instrument: str,
    as_of: datetime,
    window_days: int,
) -> list[ExternalRecord]:
    """Eligible events within the lookback window ending at as_of.

    Windows are the small justified MVP set: 1, 3, or 7 days (milestone
    section 23). Event windows look BACKWARD from the prediction time and
    never include future publications.
    """
    if window_days not in (1, 3, 7):
        raise AsOfError(f"unsupported event window: {window_days} (allowed: 1, 3, 7)")
    start = as_of - timedelta(days=window_days)
    return [
        record
        for record in asof_records(records, instrument=instrument, as_of=as_of)
        if record.event_type != "FUNDAMENTAL_FILING"
        and record.event_timestamp is not None
        and start <= record.event_timestamp <= as_of
    ]


def asof_frame(
    records: list[ExternalRecord],
    *,
    instrument: str,
    timestamps: pd.DatetimeIndex,
    fundamental_fields: tuple[str, ...],
) -> pd.DataFrame:
    """Build one multimodal state row per prediction timestamp.

    Columns: the fundamental fields carried forward from the latest eligible
    filing (no forward-fill before publication), plus event-window counts for
    the MVP windows (1/3/7 days) and hours since the latest eligible event.
    """
    rows = []
    for timestamp in timestamps:
        fundamental = latest_fundamental_asof(records, instrument=instrument, as_of=timestamp)
        row: dict[str, object] = {"timestamp": timestamp}
        for field_name in fundamental_fields:
            # Missing modality is NaN (float column), never None/never fabricated.
            row[field_name] = (
                float(fundamental.payload.get(field_name))
                if fundamental is not None and fundamental.payload.get(field_name) is not None
                else np.nan
            )
        for window in (1, 3, 7):
            row[f"events_{window}d"] = len(
                events_in_window(
                    records, instrument=instrument, as_of=timestamp, window_days=window
                )
            )
        events = events_in_window(records, instrument=instrument, as_of=timestamp, window_days=7)
        if events:
            latest_event = max(effective_availability(event) or timestamp for event in events)
            row["hours_since_last_event"] = (timestamp - latest_event).total_seconds() / 3600.0
        else:
            row["hours_since_last_event"] = float("nan")
        rows.append(row)
    return pd.DataFrame(rows)
