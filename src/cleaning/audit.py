"""Audit trail — DATA_CLEANING_VALIDATION.md §7.

Every cleaned record references its raw source line (``raw_line``), and
every run produces:

- an :class:`AuditRecord` persisted as JSON under
  ``data/interim/audit/audit_{run_date}_{TICKER}_{interval}_{run_id}.json``
- a line appended to ``data/interim/audit/audit_log.jsonl``

The record carries the raw file hash, every transformation step, the
output hash, and the quality score — the traceability chain maps the
cleaned output back to the exact raw bytes that produced it.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.core.errors import StorageError

AUDIT_DIRNAME = "audit"
AUDIT_LOG_FILENAME = "audit_log.jsonl"


@dataclass(frozen=True)
class TransformationStep:
    """One step in the audit transformation log (§7.3)."""

    step: int
    name: str
    rule_id: str
    input_rows: int
    output_rows: int
    rows_affected: int
    strategy: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditRecord:
    """Full audit record for one cleaning run (§7.3 schema)."""

    audit_id: str
    ticker: str
    interval: str
    raw_file_path: str
    raw_file_hash: str
    raw_row_count: int
    transformations: tuple[TransformationStep, ...]
    output_file_path: str
    output_file_hash: str
    output_row_count: int
    quality_score: float
    quality_rating: str
    validation_errors: int
    validation_warnings: int
    started_at: str
    completed_at: str
    duration_ms: float
    pipeline_version: str
    config_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["transformations"] = [asdict(step) for step in self.transformations]
        return payload


def new_audit_id() -> str:
    return f"audit-{uuid.uuid4().hex[:12]}"


def audit_directory(interim_dir: Path) -> Path:
    return interim_dir / AUDIT_DIRNAME


def write_audit_record(interim_dir: Path, record: AuditRecord) -> Path:
    """Persist the per-run audit JSON and append to the JSONL log."""
    directory = audit_directory(interim_dir)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        date_part = record.started_at[:10].replace("-", "")
        filename = f"audit_{date_part}_{record.ticker}_{record.interval}_{record.audit_id}.json"
        path = directory / filename
        payload = json.dumps(record.to_json(), indent=2, sort_keys=True, default=str)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(payload + "\n", encoding="utf-8")
        tmp.replace(path)

        log_path = directory / AUDIT_LOG_FILENAME
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_json(), default=str) + "\n")
    except OSError as error:
        raise StorageError(f"cannot write audit record: {error}") from error
    return path
