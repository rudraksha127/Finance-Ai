"""Cleaning-engine I/O: tolerant raw-CSV reading, interim writing, hashing.

The raw tier is the immutable source of truth (DATA_ARCHITECTURE §7.1):
this module only ever *reads* it. Cleaned output goes to the interim
tier as ``cleaned_{YYYYMMDD}_{TICKER}_{interval}.csv`` — regenerated per
run, never colliding with raw files, with a SHA-256 recorded in the
audit record.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.core.enums import MarketInterval, values_of
from src.core.errors import StorageError, ValidationError

RAW_COLUMNS = ("ticker", "timestamp", "open", "high", "low", "close", "adj_close", "volume")
# Columns guaranteed by the Milestone-03 cleaned-interim writer.
CLEANED_COLUMNS = (*RAW_COLUMNS, "raw_line")
INTERVALS = values_of(MarketInterval)

_INTERVAL_LABEL = {"1d": "daily", "1wk": "weekly", "1mo": "monthly"}


def interval_label(interval: str) -> str:
    """Filename label for an approved interval (matches raw-tier naming)."""
    try:
        return _INTERVAL_LABEL[interval]
    except KeyError:
        raise StorageError(f"unsupported interval {interval!r} for cleaned storage") from None


def read_raw_csv(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read a raw-tier CSV into records, capturing per-row parse issues.

    Returns ``(records, issues)``. ``records`` carries ``raw_line`` (the
    1-based CSV line number) so every cleaned record can be traced back
    to its raw source row (audit traceability). Rows that cannot be
    parsed at all are skipped and reported as ``{"rule_id": "VAL-S04",
    "message", "raw_line"}`` issues with the offending line.
    """
    if not path.exists():
        raise StorageError(f"raw file not found: {path}")
    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise StorageError(f"raw file {path} is empty")
            columns = [name.strip() for name in reader.fieldnames]
            if columns[: len(RAW_COLUMNS)] != list(RAW_COLUMNS):
                issues.append(
                    {
                        "rule_id": "VAL-S01",
                        "severity": "error",
                        "category": "schema",
                        "message": f"unexpected columns {columns!r}; expected {list(RAW_COLUMNS)!r}",
                        "count": 1,
                    }
                )
            for line_number, raw in enumerate(reader, start=2):
                try:
                    timestamp = datetime.fromisoformat(raw["timestamp"])
                    record = {
                        "ticker": str(raw["ticker"]).strip(),
                        "timestamp": timestamp,
                        "open": _float(raw["open"], "open"),
                        "high": _float(raw["high"], "high"),
                        "low": _float(raw["low"], "low"),
                        "close": _float(raw["close"], "close"),
                        "adj_close": _optional_float(raw["adj_close"], "adj_close"),
                        "volume": _volume(raw["volume"]),
                        "raw_line": line_number,
                    }
                    records.append(record)
                except (KeyError, ValueError) as error:
                    issues.append(
                        {
                            "rule_id": "VAL-S04",
                            "severity": "error",
                            "category": "schema",
                            "message": f"unparseable row at line {line_number}: {error}",
                            "count": 1,
                            "raw_line": line_number,
                        }
                    )
    except OSError as error:
        raise StorageError(f"cannot read raw file {path}: {error}") from error
    return records, issues


def find_latest_cleaned(interim_dir: Path, ticker: str, interval: str) -> Path:
    """Locate the most recent cleaned interim file for (ticker, interval).

    Cleaned files are named ``cleaned_{YYYYMMDD}_{TICKER}_{label}.csv``
    (Milestone-03 convention). Raises :class:`StorageError` when none
    exists. Shared by the feature and label engines.
    """
    label = _INTERVAL_LABEL.get(interval, interval)
    candidates = sorted(
        interim_dir.glob(f"cleaned_*_{ticker}_{label}.csv"),
        key=lambda path: path.name,
    )
    if not candidates:
        raise StorageError(
            f"no cleaned interim file found for {ticker} ({interval}) under {interim_dir}"
        )
    return candidates[-1]


def load_cleaned_csv(path: Path) -> pd.DataFrame:
    """Load a cleaned interim CSV into a timestamp-indexed DataFrame.

    Shared by the feature and label engines (Milestones 04/05). Validates
    the Milestone-03 cleaned-file contract: required columns present,
    ascending unique timestamps (naive-UTC storage policy).

    Raises:
        StorageError: if the file cannot be read.
        ValidationError: if required columns are missing or timestamps
            are duplicated / unsorted.
    """
    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError) as error:
        raise StorageError(f"cannot read cleaned file {path}: {error}") from error
    missing = [column for column in CLEANED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValidationError(
            f"cleaned file {path} missing required columns: {missing}",
            context={"path": str(path), "missing": missing},
        )
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=False)
    frame = frame.set_index("timestamp").sort_index()
    if frame.index.has_duplicates:
        raise ValidationError(
            f"cleaned file {path} contains duplicate timestamps",
            context={"path": str(path)},
        )
    return frame


def sha256_of(path: Path) -> str:
    """Return the SHA-256 of a file's bytes (audit / reproducibility)."""
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as error:
        raise StorageError(f"cannot hash {path}: {error}") from error


def write_interim_csv(
    interim_dir: Path, records: list[dict[str, Any]], ticker: str, interval: str, *, run_date: date
) -> Path:
    """Write cleaned records to the interim tier (overwritable by design).

    Returns the written path. Rows are serialized deterministically
    (sorted by timestamp) with stable float formatting so identical
    input produces identical bytes.
    """
    label = interval_label(interval)
    path = interim_dir / f"cleaned_{run_date:%Y%m%d}_{ticker}_{label}.csv"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = sorted(records, key=lambda record: record["timestamp"])
        lines = [",".join(RAW_COLUMNS + ("raw_line",))]  # raw_line appended for traceability
        for record in rows:
            adj = "" if record["adj_close"] is None else repr(float(record["adj_close"]))
            line = (
                f"{record['ticker']},{record['timestamp']:%Y-%m-%dT%H:%M:%S},"
                f"{record['open']!r},{record['high']!r},{record['low']!r},{record['close']!r},"
                f"{adj},{int(record['volume'])},{record['raw_line']}"
            )
            lines.append(line)
        tmp = path.with_suffix(".csv.tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError as error:
        raise StorageError(f"cannot write cleaned file {path}: {error}") from error
    return path


def load_holidays(config_relative: str | None, external_dir: Path) -> frozenset[date]:
    """Load an optional holiday calendar (JSON list of ISO dates) from
    ``data/external/``. Empty when not configured (weekend checks only)."""
    if not config_relative:
        return frozenset()
    path = Path(config_relative)
    if not path.is_absolute():
        path = external_dir / path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise StorageError(f"cannot read holidays file {path}: {error}") from error
    if not isinstance(payload, list):
        raise StorageError(f"holidays file {path} must be a JSON list of ISO dates")
    holidays: set[date] = set()
    for raw in payload:
        if not isinstance(raw, str):
            raise StorageError(f"holidays file {path} must contain only ISO date strings")
        holidays.add(date.fromisoformat(raw))
    return frozenset(holidays)


def _float(value: str, field: str) -> float:
    if value is None or value.strip() == "":
        raise ValueError(f"{field} is blank")
    return float(value)


def _optional_float(value: str, field: str) -> float | None:
    if value is None or value.strip() == "":
        return None
    return float(value)


def _volume(value: str) -> float:
    if value is None or value.strip() == "":
        raise ValueError("volume is blank")
    return float(value)
