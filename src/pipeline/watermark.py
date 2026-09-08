"""Watermark / checkpoint store for the autonomous data pipeline (P01).

A watermark records the last *successfully completed* pipeline position per
(instrument, interval). It advances only after the full stage chain and the
quality gate succeed; a failed or partial run leaves it untouched, so the
next run resumes from the same known-good position (milestone sections 8, 11).

Storage is a single JSON file under ``data/pipeline/watermarks.json``
(file-based MVP per ADR-0005). Writes are atomic (temp file + rename).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.logging.logger import get_logger

logger = get_logger("pipeline.watermark")


@dataclass(frozen=True)
class Watermark:
    """Last successful pipeline position for one (instrument, interval)."""

    instrument: str
    interval: str
    source: str
    last_successful_timestamp: str  # ISO date (naive UTC), inclusive
    pipeline_run_id: str
    status: str
    updated_at: str  # ISO datetime (naive UTC)

    @classmethod
    def from_dict(cls, raw: dict) -> "Watermark":
        return cls(
            instrument=raw["instrument"],
            interval=raw["interval"],
            source=raw.get("source", "yahoo_finance"),
            last_successful_timestamp=raw["last_successful_timestamp"],
            pipeline_run_id=raw.get("pipeline_run_id", ""),
            status=raw.get("status", "COMPLETED"),
            updated_at=raw.get("updated_at", ""),
        )


class WatermarkStore:
    """Atomic JSON watermark store keyed by (instrument, interval)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self, instrument: str, interval: str) -> Watermark | None:
        if not self.path.exists():
            return None
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        entry = raw.get(instrument, {}).get(interval)
        return Watermark.from_dict(entry) if entry else None

    def set(self, watermark: Watermark) -> None:
        raw: dict = {}
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        raw.setdefault(watermark.instrument, {})[watermark.interval] = asdict(watermark)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)
        logger.info(
            "watermark_advanced",
            instrument=watermark.instrument,
            interval=watermark.interval,
            last_successful_timestamp=watermark.last_successful_timestamp,
            pipeline_run_id=watermark.pipeline_run_id,
        )


def now_naive_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)