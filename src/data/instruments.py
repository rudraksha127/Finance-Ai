"""File-backed instrument registry.

The approved DATA_ARCHITECTURE models ``instruments`` as a database
table (Phase 2). In the file-based MVP this registry provides the same
identity guarantee: a canonical, validated ticker can be resolved or
registered exactly once, and duplicate registration is impossible.

Storage is a JSON document under the raw-tier metadata directory.
Registration is idempotent by ticker; an existing entry is never
duplicated or overwritten.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.errors import StorageError
from src.core.validation import validate_ticker

REGISTRY_FILENAME = "instruments.json"


@dataclass(frozen=True)
class InstrumentRecord:
    """Minimal instrument identity (fields subset of DATA_ARCHITECTURE 3.1)."""

    ticker: str
    is_active: bool = True
    exchange: str | None = None
    first_seen: str = ""  # ISO naive-UTC datetime


class InstrumentRegistry:
    """Ticker identity registry backed by a JSON file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def ensure(self, ticker: str, *, exchange: str | None = None) -> InstrumentRecord:
        """Register ``ticker`` if unknown; otherwise return the existing record.

        Raises:
            StorageError: if the registry file is corrupt.
        """
        canonical = validate_ticker(ticker)
        records = self._load()
        if canonical in records:
            return records[canonical]
        record = InstrumentRecord(
            ticker=canonical,
            exchange=exchange,
            # Naive-UTC storage policy (DATA_ARCHITECTURE.md section 4.2).
            first_seen=datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0).isoformat(),
        )
        records[canonical] = record
        self._save(records)
        return record

    def lookup(self, ticker: str) -> InstrumentRecord | None:
        canonical = validate_ticker(ticker)
        return self._load().get(canonical)

    def all(self) -> dict[str, InstrumentRecord]:
        return dict(self._load())

    # ------------------------------------------------------------------
    def _load(self) -> dict[str, InstrumentRecord]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise StorageError(f"cannot read instrument registry {self.path}: {error}") from error
        records: dict[str, InstrumentRecord] = {}
        for ticker, raw in data.items():
            if not isinstance(raw, dict):
                raise StorageError(f"instrument registry {self.path} is corrupt")
            records[ticker] = InstrumentRecord(**raw)
        return records

    def _save(self, records: dict[str, InstrumentRecord]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload: dict[str, dict[str, Any]] = {
                ticker: asdict(record) for ticker, record in sorted(records.items())
            }
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            tmp.replace(self.path)
        except OSError as error:
            raise StorageError(f"cannot write instrument registry {self.path}: {error}") from error
