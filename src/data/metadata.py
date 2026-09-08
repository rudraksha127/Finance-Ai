"""Per-run ingestion metadata and journal.

Every ingestion run appends one machine-readable record to an
append-only JSONL journal under ``{raw_dir}/metadata/ingestion_log.jsonl``
(DATA_INGESTION_BLUEPRINT.md section 8). The journal is the audit
trail: it answers *which source produced this record, when it was
ingested, for which requested range, under which ingestion run*
(milestone: raw-source traceability).

The record carries the milestone-required fields (ingestion id,
source, instrument, interval, requested range, actual first/last
timestamp, fetched/persisted/skipped/error counts, status, start and
completion time) plus storage facts (file path, size, SHA-256
checksum) used for idempotency checks.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

from src.core.errors import StorageError
from src.data.enums import IngestionStatus

JOURNAL_FILENAME = "ingestion_log.jsonl"
METADATA_DIRNAME = "metadata"


@dataclass(frozen=True)
class IngestionMetadata:
    """Structured record of one ingestion run (per ticker)."""

    ingestion_id: str
    ticker: str
    interval: str
    source: str
    requested_start: str  # ISO date
    requested_end: str  # ISO date
    started_at: str  # ISO naive-UTC datetime
    completed_at: str  # ISO naive-UTC datetime
    duration_ms: float
    fetched_record_count: int = 0
    persisted_record_count: int = 0  # new rows added to the raw store
    skipped_duplicate_count: int = 0
    rejected_count: int = 0
    conflict_count: int = 0
    error_count: int = 0
    actual_first_timestamp: str | None = None  # ISO date
    actual_last_timestamp: str | None = None  # ISO date
    ingestion_status: str = IngestionStatus.CREATED.value
    error_category: str | None = None
    error_message: str | None = None
    file_path: str | None = None
    file_size_bytes: int | None = None
    file_format: str = "csv"
    checksum: str | None = None
    retry_attempts: int = 0
    pipeline_version: str = ""
    environment: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, line: str) -> IngestionMetadata:
        try:
            data = json.loads(line)
            return cls(**{key: data[key] for key in data if key in cls.__dataclass_fields__})
        except (ValueError, TypeError, KeyError) as error:
            raise StorageError(f"unreadable ingestion metadata line: {error}") from error


def new_ingestion_id() -> str:
    return str(uuid.uuid4())


def metadata_directory(raw_dir: Path) -> Path:
    return raw_dir / METADATA_DIRNAME


class IngestionJournal:
    """Append-only JSONL journal of ingestion runs."""

    def __init__(self, raw_dir: Path) -> None:
        self.path = metadata_directory(raw_dir) / JOURNAL_FILENAME

    def append(self, record: IngestionMetadata) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(record.to_json() + "\n")
        except OSError as error:
            raise StorageError(
                f"cannot append to ingestion journal {self.path}: {error}"
            ) from error

    def read_all(self) -> Iterator[IngestionMetadata]:
        """Yield every recorded ingestion run in journal order."""
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        yield IngestionMetadata.from_json(line)
        except OSError as error:
            raise StorageError(f"cannot read ingestion journal {self.path}: {error}") from error

    def entries_for(self, ticker: str) -> list[IngestionMetadata]:
        return [entry for entry in self.read_all() if entry.ticker == ticker]
