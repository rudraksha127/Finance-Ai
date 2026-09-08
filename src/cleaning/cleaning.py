"""Cleaning engine — DATA_CLEANING_VALIDATION.md §4/§5 strategies.

Deterministic transformations applied to validated raw records. Every
step returns stats so the audit trail records exactly what changed.
Cleaned records keep their ``raw_line`` so traceability to the raw file
is preserved; the raw tier is never written to.

Strategies implemented (blueprint §4.2):

- Duplicates: ``keep_last`` (default) or ``keep_first`` by timestamp.
- OHLC order (VAL-P05/P06): high = max(high, open, close);
  low = min(low, open, close).
- Missing prices: gap of 1 → forward fill; 2..interpolate_max_gap →
  linear interpolation (with a ±20% sanity guard, else forward fill);
  longer than missing_fill_limit but <= 10 → marked incomplete (kept);
  > 10 → row dropped. Leading/trailing gaps are never extrapolated.
- Missing volume: zero fill.
- Outliers: z-score of daily close returns, |z| > threshold → flagged
  (kept, per blueprint §5.3 "flag" strategy).

Gaps *between* candles are not fabricated — validation detects them
(VAL-C02); this stage only fills null values inside existing rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import fmean, pstdev
from typing import Any

PRICE_COLUMNS = ("open", "high", "low", "close")
MAX_INCOMPLETE_RUN = 10  # gaps 6-10 → mark incomplete (kept); > 10 → drop
INTERPOLATION_SANITY_PCT = 0.20


@dataclass(frozen=True)
class CleaningStats:
    """Counts of every cleaning action (audit + reporting)."""

    input_rows: int
    duplicates_removed: int
    rejected_dropped: int
    ohlc_fixed: int
    forward_filled: int
    interpolated: int
    volume_zero_filled: int
    marked_incomplete: int
    dropped_missing: int
    outliers_flagged: int
    output_rows: int


@dataclass
class _FillCounters:
    """Mutable counters shared by the missing-value fill pass."""

    forward_filled: int = 0
    interpolated: int = 0
    marked: int = 0
    volume_zero_filled: int = 0


def clean_batch(
    records: list[dict[str, Any]],
    *,
    duplicate_strategy: str = "keep_last",
    missing_fill_limit: int = 3,
    interpolate_max_gap: int = 3,
    outlier_zscore_threshold: float = 3.0,
    rejected_raw_lines: frozenset[int] = frozenset(),
) -> tuple[list[dict[str, Any]], CleaningStats]:
    """Apply the deterministic cleaning pipeline to one batch.

    Args:
        records: Validated raw records (each carrying ``raw_line``).
        duplicate_strategy: ``keep_last`` keeps the most recent row for a
            timestamp, ``keep_first`` keeps the oldest.
        rejected_raw_lines: Raw lines to drop (unfixable validation errors).
        Missing/outlier knobs: see cleaning config section.

    Returns:
        ``(cleaned_records, stats)``. Rows retain their ``raw_line``;
        the pipeline later normalizes (sorts, reindexes) them.
    """
    input_rows = len(records)
    records = [dict(record) for record in records]  # defensive copies

    # 1. Remove rejected (unfixable) rows — raw never mutated.
    rejected_lines = set(rejected_raw_lines)
    kept = [record for record in records if record["raw_line"] not in rejected_lines]
    rejected_dropped = input_rows - len(kept)

    # 2. Duplicate removal by timestamp.
    kept, duplicates_removed = _deduplicate(kept, strategy=duplicate_strategy)

    # 3. Fix OHLC order (VAL-P05/P06). Skip rows with missing prices —
    #   those are resolved by the missing-data stage, not fabricated here.
    ohlc_fixed = 0
    for record in kept:
        open_, high, low, close = record["open"], record["high"], record["low"], record["close"]
        if None in (open_, high, low, close):
            continue
        fixed = False
        if high < max(open_, close):
            record["high"] = max(open_, close)
            fixed = True
        if low > min(open_, close):
            record["low"] = min(open_, close)
            fixed = True
        if fixed:
            ohlc_fixed += 1

    # 4. Missing-data strategies per column.
    counters = _FillCounters()
    dropped_lines: set[int] = set()
    for column in PRICE_COLUMNS:
        _fill_price_column(
            kept, column, counters, missing_fill_limit, interpolate_max_gap, dropped_lines
        )
    _fill_volume(kept, counters)
    _fill_adj_close(kept, counters)
    if dropped_lines:
        kept = [record for record in kept if record["raw_line"] not in dropped_lines]

    # 5. Outlier flagging (kept; never dropped).
    outliers_flagged = _flag_outliers(kept, threshold=outlier_zscore_threshold)

    stats = CleaningStats(
        input_rows=input_rows,
        duplicates_removed=duplicates_removed,
        rejected_dropped=rejected_dropped,
        ohlc_fixed=ohlc_fixed,
        forward_filled=counters.forward_filled,
        interpolated=counters.interpolated,
        volume_zero_filled=counters.volume_zero_filled,
        marked_incomplete=counters.marked,
        dropped_missing=len(dropped_lines),
        outliers_flagged=outliers_flagged,
        output_rows=len(kept),
    )
    return kept, stats


# ---------------------------------------------------------------------------
# Per-transformation internals
# ---------------------------------------------------------------------------
def _deduplicate(
    records: list[dict[str, Any]], *, strategy: str
) -> tuple[list[dict[str, Any]], int]:
    """Collapse duplicate timestamps to a single row per strategy.

    Rows are processed in file order; ``keep_first``/``keep_last`` pick
    the first/last occurrence for each timestamp. Output stays in file
    order (the pipeline normalizes to ascending later).
    """
    seen: dict[datetime, dict[str, Any]] = {}
    duplicates_removed = 0
    for record in records:
        timestamp = record["timestamp"]
        if timestamp not in seen:
            seen[timestamp] = record
        else:
            duplicates_removed += 1
            if strategy == "keep_last":
                seen[timestamp] = record
    result = list(seen.values())
    return result, duplicates_removed


def _fill_price_column(
    records: list[dict[str, Any]],
    column: str,
    counters: _FillCounters,
    missing_fill_limit: int,
    interpolate_max_gap: int,
    dropped_lines: set[int],
) -> None:
    """Fill one price column using run-length gap logic (in place)."""
    index = 0
    while index < len(records):
        value = records[index].get(column)
        if value is not None:
            index += 1
            continue

        run_start = index
        while index < len(records) and records[index].get(column) is None:
            index += 1
        run_len = index - run_start
        previous = records[run_start - 1].get(column) if run_start > 0 else None
        next_value = records[index].get(column) if index < len(records) else None

        if previous is None:
            # Leading gap: never extrapolate.
            if next_value is None and run_len > MAX_INCOMPLETE_RUN:
                for offset in range(run_start, index):
                    dropped_lines.add(records[offset]["raw_line"])
            else:
                counters.marked += run_len
                _mark_incomplete(records, run_start, index)
        elif next_value is None:
            # Trailing gap: cannot interpolate forward — mark incomplete.
            counters.marked += run_len
            _mark_incomplete(records, run_start, index)
        elif run_len == 1:
            records[run_start][column] = previous
            counters.forward_filled += 1
        elif run_len <= interpolate_max_gap:
            interpolated_value = _interpolate(previous, next_value, run_len)
            if _within_sanity(interpolated_value, previous, next_value):
                for offset in range(run_start, index):
                    records[offset][column] = interpolated_value
                counters.interpolated += run_len
            else:
                for offset in range(run_start, index):
                    records[offset][column] = previous
                counters.forward_filled += run_len
        elif run_len <= missing_fill_limit:
            for offset in range(run_start, index):
                records[offset][column] = previous
            counters.forward_filled += run_len
        elif run_len <= MAX_INCOMPLETE_RUN:
            counters.marked += run_len
            _mark_incomplete(records, run_start, index)
        else:
            for offset in range(run_start, index):
                dropped_lines.add(records[offset]["raw_line"])


def _interpolate(previous: float, next_value: float, run_len: int) -> float:
    """Linear interpolation filling ``run_len`` missing cells."""
    if run_len == 1:
        return (previous + next_value) / 2.0
    step = (next_value - previous) / (run_len + 1)
    mid = previous + step * ((run_len + 1) / 2.0)
    return mid


def _within_sanity(value: float, previous: float, next_value: float) -> bool:
    """Interpolated value must lie within ±20% of BOTH neighbors (§4.4).

    Checking the band around each neighbor individually (not just the
    min/max envelope) makes the guard meaningful: a linear midpoint far
    from either endpoint fails and the strategy falls back to forward
    fill, per the blueprint's "if outside range → use forward fill".
    """
    near_previous = (
        previous * (1 - INTERPOLATION_SANITY_PCT)
        <= value
        <= previous * (1 + INTERPOLATION_SANITY_PCT)
    )
    near_next = (
        next_value * (1 - INTERPOLATION_SANITY_PCT)
        <= value
        <= next_value * (1 + INTERPOLATION_SANITY_PCT)
    )
    return near_previous and near_next


def _mark_incomplete(records: list[dict[str, Any]], start: int, end: int) -> None:
    for offset in range(start, end):
        records[offset]["incomplete"] = True


def _fill_volume(records: list[dict[str, Any]], counters: _FillCounters) -> None:
    """Volume missing → 0 (zero fill per blueprint §4.2, never a price)."""
    for record in records:
        if record.get("volume") is None:
            record["volume"] = 0.0
            counters.volume_zero_filled += 1


def _fill_adj_close(records: list[dict[str, Any]], counters: _FillCounters) -> None:
    """Adj close: forward fill like close (never interpolate adjustment gaps)."""
    last_adj: float | None = None
    for record in records:
        if record.get("adj_close") is None:
            if last_adj is not None:
                record["adj_close"] = last_adj
                counters.forward_filled += 1
            else:
                counters.marked += 1
        else:
            last_adj = float(record["adj_close"])


def _flag_outliers(records: list[dict[str, Any]], *, threshold: float) -> int:
    """Flag |z| > threshold on daily close returns (kept, blueprint §5.3).

    Rows whose close is still missing (never filled) are skipped — we
    never fabricate an outlier judgement for a null price.
    """
    valid = [
        (raw_line, float(close))
        for raw_line, close in ((r["raw_line"], r["close"]) for r in records)
        if close is not None
    ]
    if len(valid) < 2:
        return 0
    values = [close for _, close in valid]
    returns: list[float] = []
    flagged = 0
    for index in range(1, len(values)):
        if values[index - 1] > 0:
            returns.append(values[index] / values[index - 1] - 1.0)
    if not returns:
        return 0
    mean = fmean(returns)
    deviation = pstdev(returns)
    if deviation == 0:
        return 0
    # Map returns back to record indices: return[i] corresponds to record i+1.
    for return_index, value in enumerate(returns):
        z = (value - mean) / deviation
        if abs(z) > threshold:
            row_line = valid[return_index + 1][0]
            for record in records:
                if record["raw_line"] == row_line:
                    record["outlier_flagged"] = True
                    flagged += 1
                    break
    return flagged
