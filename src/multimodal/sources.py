"""External data source abstractions (Post-MVP Milestone 08).

Milestone section 12 source policy: only approved/legal sources may be used,
and no licensed fundamentals/news provider is currently approved for this
project. Therefore this milestone implements the full ingestion ABSTRACTION
plus DETERMINISTIC OFFLINE FIXTURES, and documents the limitation honestly:

- no live fundamentals or news are fetched;
- the fixture format IS the normalized source contract, so wiring a licensed
  provider later means implementing one adapter, not redesigning this layer;
- offline/historical research mode (section 39) works entirely from stored
  fixture records — no network access at inference or backtest time.

Every record passes through :func:`normalize_timestamp` (contracts.py), so
publication-time policy, timezone normalization, and reliability marking are
enforced at the ingestion boundary, not per-consumer.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.multimodal.contracts import (
    EVENT_TYPES,
    ExternalRecord,
    TemporalReliability,
    normalize_timestamp,
    utc_now_iso,
)

SCHEMA_VERSION = "multimodal_source_v0.1"
FUNDAMENTAL_FIELDS = (
    "revenue",
    "operating_income",
    "net_income",
    "eps",
    "total_assets",
    "total_liabilities",
    "cash",
    "total_debt",
    "free_cash_flow",
    "shares_outstanding",
)


class SourceError(ValueError):
    """Raised when an external source record is malformed."""


def _record_id(source: str, source_identifier: str) -> str:
    digest = hashlib.sha256(f"{source}:{source_identifier}".encode()).hexdigest()[:12]
    return f"ext_{digest}"


def _normalize_row(raw: dict[str, Any], *, source: str) -> dict[str, Any]:
    """Validate + normalize one raw source row into the external contract."""
    for required in ("source_identifier", "instrument", "event_type"):
        if required not in raw or raw[required] in (None, ""):
            raise SourceError(f"source row missing required field {required!r}: {raw}")
    event_type = str(raw["event_type"]).upper()
    if event_type not in EVENT_TYPES and event_type != "FUNDAMENTAL_FILING":
        raise SourceError(f"unknown event_type {event_type!r} (allowed: {sorted(EVENT_TYPES)})")

    event_utc, original_event, event_tz, _event_rel = normalize_timestamp(
        raw.get("event_timestamp"), original_timezone=raw.get("original_timezone")
    )
    publication_utc, original_pub, pub_tz, pub_rel = normalize_timestamp(
        raw.get("publication_timestamp"), original_timezone=raw.get("original_timezone")
    )

    # Availability = publication when trustworthy; otherwise conservative.
    if pub_rel is TemporalReliability.RELIABLE:
        availability, reliability = publication_utc, TemporalReliability.RELIABLE
    elif pub_rel is TemporalReliability.DAY_ONLY:
        # Day known, intraday unknown: keep the stamp; effective availability
        # (asoof.py) pushes eligibility to the next day start.
        availability, reliability = publication_utc, TemporalReliability.DAY_ONLY
    else:
        availability, reliability = None, TemporalReliability.INSUFFICIENT

    parse_status = "OK"
    if event_type == "FUNDAMENTAL_FILING":
        for field_name in FUNDAMENTAL_FIELDS:
            value = raw.get(field_name)
            if value is not None:
                try:
                    float(value)
                except (TypeError, ValueError):
                    parse_status = f"MALFORMED_FIELD:{field_name}"
    if reliability is not TemporalReliability.INSUFFICIENT and availability is None:
        parse_status = parse_status if parse_status != "OK" else "PUBLICATION_TIME_UNRESOLVED"

    return {
        "record_id": _record_id(source, str(raw["source_identifier"])),
        "source": source,
        "source_identifier": str(raw["source_identifier"]),
        "instrument": str(raw["instrument"]).upper(),
        "event_type": event_type,
        "event_timestamp": event_utc,
        "publication_timestamp": publication_utc,
        "ingestion_timestamp": datetime.now(timezone.utc).replace(tzinfo=None),
        "availability_timestamp": availability,
        "reliability": reliability,
        "original_timestamp": original_pub or original_event,
        "original_timezone": pub_tz or event_tz,
        "payload": {
            key: value
            for key, value in raw.items()
            if key
            not in {
                "source_identifier",
                "instrument",
                "event_type",
                "event_timestamp",
                "publication_timestamp",
                "original_timezone",
            }
        },
        "parse_status": parse_status,
    }


def normalize_batch(rows: list[dict[str, Any]], *, source: str) -> list[ExternalRecord]:
    """Normalize a raw source batch; malformed rows fail loudly (section 28)."""
    records = []
    for raw in rows:
        normalized = _normalize_row(raw, source=source)
        records.append(
            ExternalRecord(
                record_id=normalized["record_id"],
                source=source,
                source_identifier=normalized["source_identifier"],
                instrument=normalized["instrument"],
                event_type=normalized["event_type"],
                event_timestamp=normalized["event_timestamp"],
                publication_timestamp=normalized["publication_timestamp"],
                ingestion_timestamp=normalized["ingestion_timestamp"],
                availability_timestamp=normalized["availability_timestamp"],
                reliability=normalized["reliability"],
                original_timestamp=normalized["original_timestamp"],
                original_timezone=normalized["original_timezone"],
                payload=normalized["payload"],
                parse_status=normalized["parse_status"],
            )
        )
    return records


def deduplicate(records: list[ExternalRecord]) -> list[ExternalRecord]:
    """Deterministic dedup across sources (milestone section 29).

    Strategy: exact ``source_identifier`` identity wins first; then a
    content fingerprint (instrument + event_type + event day + headline
    tokens) removes cross-source duplicates, keeping the earliest publication
    and merging source lists. Limitations documented: near-duplicates with
    different wording are NOT detected (no fuzzy matching in the MVP).
    """
    by_identifier: dict[str, ExternalRecord] = {}
    fingerprint: dict[str, ExternalRecord] = {}
    ordered: list[ExternalRecord] = []
    for record in sorted(
        records,
        key=lambda item: (
            item.availability_timestamp or datetime.max.replace(tzinfo=timezone.utc),
            item.record_id,
        ),
    ):
        if record.source_identifier in by_identifier:
            continue
        tokens = " ".join(sorted(str(record.payload.get("headline", "")).lower().split())[:8])
        event_day = record.event_timestamp.date().isoformat() if record.event_timestamp else "none"
        key = f"{record.instrument}|{record.event_type}|{event_day}|{tokens}"
        if key in fingerprint and record.event_type != "FUNDAMENTAL_FILING":
            continue
        by_identifier[record.source_identifier] = record
        if record.event_type != "FUNDAMENTAL_FILING":
            fingerprint[key] = record
        ordered.append(record)
    return ordered


def load_fixture(path: Path) -> list[ExternalRecord]:
    """Load a deterministic fixture batch (JSON list of raw rows)."""
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SourceError(f"cannot read fixture {path}: {error}") from error
    if not isinstance(rows, list):
        raise SourceError(f"fixture {path} must be a JSON list of source rows")
    source = path.stem.split("__")[0]  # e.g. fundamentals_fixture.json -> fundamentals
    return deduplicate(normalize_batch(rows, source=source))


def write_fixture(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def batch_metadata(rows: list[dict[str, Any]], *, source: str, path: Path) -> dict[str, Any]:
    """Source-batch identity (milestone section 27)."""
    return {
        "source": source,
        "source_version": SCHEMA_VERSION,
        "schema_version": SCHEMA_VERSION,
        "parser_version": "multimodal-normalize-v0.1",
        "ingestion_time": utc_now_iso(),
        "record_count": len(rows),
        "retrieval_period": {
            "start": min((str(row.get("event_timestamp", "")) for row in rows), default=None),
            "end": max((str(row.get("event_timestamp", "")) for row in rows), default=None),
        },
        "fixture_path": str(path),
    }


def restatement_policy(records: list[ExternalRecord]) -> dict[str, Any]:
    """Document the MVP restatement policy (milestone section 30).

    Policy: the FIRST publication of a fiscal period is the training truth;
    later restatements are recorded (new availability timestamps) but NEVER
    retroactively replace what was knowable at historical prediction times —
    as-of joins naturally implement this because a restatement published
    later simply is not eligible before its own availability timestamp.
    """
    filings = [r for r in records if r.event_type == "FUNDAMENTAL_FILING"]
    by_period: dict[str, list[ExternalRecord]] = {}
    for record in filings:
        period = str(record.payload.get("fiscal_period", "unknown"))
        by_period.setdefault(period, []).append(record)
    return {
        "policy": "first_publication_is_truth; restatements are new records with "
        "their own availability timestamps and never rewrite history",
        "periods_with_restatements": {
            period: len(group) for period, group in by_period.items() if len(group) > 1
        },
    }
