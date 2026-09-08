"""Prediction audit trail for the inference API (M09).

Implements INFERENCE_API_BLUEPRINT section 19: every prediction is
recorded once, append-only, never mutated, as one JSON line per day
under ``predictions/audit/{YYYY}/{MM}/{DD}/predictions_{date}.jsonl``.
The record carries exactly the fields the blueprint lists in section
19.1 plus the request/inference timing context. Failures are explicit
(``AuditError``) — the orchestrator decides fail-closed behavior per
milestone section 27 (audit persistence failure means the prediction is
marked unverified, never silently reported as audited).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.logging.logger import get_logger

logger = get_logger("api.audit")


class AuditError(RuntimeError):
    """The prediction audit record could not be persisted."""


def audit_path(audit_dir: Path, *, inference_timestamp: datetime) -> Path:
    """Daily JSONL path for an inference timestamp (section 19.2 layout)."""
    day = inference_timestamp.astimezone(timezone.utc).date()
    return (
        audit_dir
        / f"{day.year}"
        / f"{day.month:02d}"
        / f"{day.day:02d}"
        / (f"predictions_{day.isoformat()}.jsonl")
    )


def write_prediction_record(audit_dir: Path, record: dict[str, Any]) -> Path:
    """Append one immutable prediction record; returns the written path."""
    path = audit_path(audit_dir, inference_timestamp=parse_utc(record["inference_timestamp"]))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
    except OSError as error:
        raise AuditError(f"cannot persist prediction audit record: {error}") from error
    logger.info(
        "prediction_audit_written",
        prediction_id=record.get("prediction_id"),
        path=str(path),
        status="COMPLETED",
    )
    return path


def parse_utc(value: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp (Z or offset) into an aware datetime."""
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
