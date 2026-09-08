"""Raw-tier candle store (file-based MVP).

Layout follows DATA_ARCHITECTURE.md section 7.3 /
DATA_INGESTION_BLUEPRINT.md stage 5: one CSV per ``(ticker, interval)``
named ``{TICKER}_{label}.csv`` (``AAPL_daily.csv``) under the raw tier.

File semantics (deduplication logic, blueprint section 3.4):

- Rows are keyed by ``(ticker, timestamp, interval)`` — the approved
  UNIQUE observation key. The file holds one interval, so the row key
  is the timestamp.
- Re-ingesting an identical range is idempotent: existing rows that
  match within a small relative tolerance are counted as duplicates
  and not written again. The tolerance exists because Yahoo Finance
  returns ``adj_close`` values that differ in their last decimals
  (≈1e-7 relative) between otherwise identical responses; without it,
  a safe re-run would be misclassified as a material conflict.
- An incoming row for an existing timestamp with materially different
  values (beyond the relative tolerance, e.g. a provider data
  correction) is a **conflict**: the existing row is kept, the incoming
  row is skipped, and the conflict is counted. Stored rows are never
  silently overwritten (milestone: "do not silently overwrite
  materially different data").
- The file only ever grows; existing rows are byte-stable. The whole
  file is rewritten atomically (temp file + ``os.replace``) so a crash
  never leaves a half-written store.

Timestamps are stored as naive-UTC ISO-8601 (``YYYY-MM-DDTHH:MM:SS``),
per the naive-UTC storage policy (DATA_ARCHITECTURE.md section 4).
"""

from __future__ import annotations

import csv
import hashlib
import math
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.enums import MarketInterval
from src.core.errors import StorageError
from src.core.models import Candle

REQUIRED_COLUMNS = ("ticker", "timestamp", "open", "high", "low", "close", "adj_close", "volume")

_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S"

# File label per interval (blueprint stage 5 naming).
_INTERVAL_LABEL = {
    MarketInterval.DAILY.value: "daily",
    MarketInterval.WEEKLY.value: "weekly",
    MarketInterval.MONTHLY.value: "monthly",
}


@dataclass(frozen=True)
class StoreSummary:
    """Outcome of one store operation for a (ticker, interval) file."""

    path: Path
    added: int = 0
    duplicates: int = 0  # rows already present with identical values
    conflicts: int = 0  # incoming rows for existing timestamps with different values
    checksum: str = ""
    file_size_bytes: int = 0


def raw_file_path(raw_dir: Path, ticker: str, interval: str) -> Path:
    """Return ``{raw_dir}/{TICKER}_{label}.csv`` for a (ticker, interval)."""
    label = _INTERVAL_LABEL.get(interval)
    if label is None:
        raise StorageError(f"unsupported interval {interval!r} for raw storage")
    return raw_dir / f"{ticker}_{label}.csv"


def store_candles(raw_dir: Path, candles: list[Candle] | tuple[Candle, ...]) -> StoreSummary:
    """Merge validated candles into the raw-tier store (concat-dedup).

    Args:
        raw_dir: Raw storage tier directory.
        candles: Validated, normalized candles for one (ticker, interval).

    Returns:
        A :class:`StoreSummary` describing added/duplicate/conflict rows.
    """
    if not candles:
        raise StorageError("store_candles requires at least one candle")

    first = candles[0]
    ticker = first.ticker
    interval = first.interval
    for candle in candles:
        if candle.ticker != ticker or candle.interval != interval:
            raise StorageError("all candles in a store call must share ticker and interval")

    path = raw_file_path(raw_dir, ticker, interval)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise StorageError(f"cannot create raw directory {path.parent}") from error

    existing = _read_file(path) if path.exists() else {}
    incoming = {candle.timestamp: _row_values(candle) for candle in candles}

    added: list[tuple[datetime, tuple[Any, ...]]] = []
    duplicates = 0
    conflicts = 0
    for timestamp, values in sorted(incoming.items()):
        if timestamp not in existing:
            added.append((timestamp, values))
        elif _rows_equal(existing[timestamp], values):
            duplicates += 1
        else:
            conflicts += 1  # existing row wins — never silently overwrite

    if not added and not path.exists():
        raise StorageError(
            "nothing to store and no existing file — refusing to create an empty file"
        )

    merged = sorted(existing.items()) + added  # existing + new, ascending
    content = _serialize(ticker, merged)

    tmp_path = path.with_suffix(".csv.tmp")
    try:
        tmp_path.write_bytes(content)
        os.replace(tmp_path, path)
    except OSError as error:
        raise StorageError(f"failed to write raw store {path}: {error}") from error

    return StoreSummary(
        path=path,
        added=len(added),
        duplicates=duplicates,
        conflicts=conflicts,
        checksum=hashlib.sha256(content).hexdigest(),
        file_size_bytes=len(content),
    )


def read_candles(raw_dir: Path, ticker: str, interval: str) -> tuple[Candle, ...]:
    """Read stored candles back for a (ticker, interval)."""
    path = raw_file_path(raw_dir, ticker, interval)
    if not path.exists():
        return ()
    rows = _read_file(path)
    candles: list[Candle] = []
    for timestamp, (values) in rows.items():
        o, h, l, c, adj, volume = values
        candles.append(
            Candle(
                ticker=ticker,
                timestamp=timestamp,
                open=o,
                high=h,
                low=l,
                close=c,
                adj_close=adj,
                volume=volume,
                interval=interval,
                source="raw_store",
            )
        )
    return tuple(sorted(candles, key=lambda candle: candle.timestamp))


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------
def _read_file(path: Path) -> dict[datetime, tuple[Any, ...]]:
    rows: dict[datetime, tuple[Any, ...]] = {}
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or list(reader.fieldnames) != list(REQUIRED_COLUMNS):
                raise StorageError(f"raw store {path} has unexpected columns")
            for line_number, raw in enumerate(reader, start=2):
                try:
                    timestamp = datetime.fromisoformat(raw["timestamp"])
                    values = (
                        float(raw["open"]),
                        float(raw["high"]),
                        float(raw["low"]),
                        float(raw["close"]),
                        float(raw["adj_close"]) if raw["adj_close"] not in ("", None) else None,
                        int(float(raw["volume"])),
                    )
                except (KeyError, ValueError) as error:
                    raise StorageError(
                        f"raw store {path} has an unreadable row at line {line_number}: {error}"
                    ) from error
                rows[timestamp] = values
    except OSError as error:
        raise StorageError(f"cannot read raw store {path}: {error}") from error
    return rows


def _rows_equal(left: tuple[Any, ...], right: tuple[Any, ...], *, rtol: float = 1e-6) -> bool:
    """Compare two stored rows for dedup/conflict classification.

    Numeric fields are equal within a small relative tolerance (``rtol``)
    so provider float noise (Yahoo ``adj_close`` re-precision ≈1e-7) is
    treated as a duplicate, while real data corrections (well beyond
    ``rtol``) remain conflicts. ``None`` matches only ``None``.
    """
    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        if a is None or b is None:
            if a is not b:
                return False
            continue
        if not math.isclose(float(a), float(b), rel_tol=rtol, abs_tol=0.0):
            return False
    return True


def _row_values(candle: Candle) -> tuple[Any, ...]:
    # Volume is an integer count (PostgreSQL BIGINT in the Phase-2
    # schema); canonicalize to int so the serialized file is byte-stable
    # across idempotent re-stores (the read path parses volume as int).
    return (
        candle.open,
        candle.high,
        candle.low,
        candle.close,
        candle.adj_close,
        int(candle.volume),
    )


def _serialize(ticker: str, rows: list[tuple[datetime, tuple[Any, ...]]]) -> bytes:
    header = ",".join(REQUIRED_COLUMNS)
    lines = [header]
    for timestamp, values in rows:
        o, h, l, c, adj, volume = values
        adj_text = "" if adj is None else repr(float(adj))
        row = (
            f"{ticker},{timestamp.strftime(_TIMESTAMP_FORMAT)},"
            f"{o!r},{h!r},{l!r},{c!r},{adj_text},{volume}"
        )
        lines.append(row)
    return ("\n".join(lines) + "\n").encode("utf-8")
