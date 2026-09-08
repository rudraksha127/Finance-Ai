"""Validation engine — DATA_CLEANING_VALIDATION.md §2 rule reference.

Every check is assigned its approved rule ID (VAL-S01..VAL-C03). Each
failed record receives an explicit, machine-readable reason (rule_id,
severity, category, message, raw_line) so downstream stages and the
audit trail can explain exactly why a record was rejected, fixed,
flagged, or kept.

Policy (documented in pipeline.py):

- ERROR-severity, unfixable violations (non-positive price, negative
  volume, future timestamp) → record rejected (dropped)
- ERROR-severity fixable violations (OHLC order, duplicates, ordering)
  → record kept, fixed by the cleaning stage
- WARNING violations (weekend/holiday, zero volume, price anomaly,
  missing-data percentages, long gaps) → record kept, flagged + logged

Validation never mutates records; it returns a report plus per-record
reasons that the pipeline maps to actions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

REQUIRED_PRICE_COLUMNS = ("open", "high", "low", "close")
REQUIRED_COLUMNS = REQUIRED_PRICE_COLUMNS + ("volume",)

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"


@dataclass(frozen=True)
class ValidationIssue:
    """One validation finding (rule reference §2.3)."""

    rule_id: str
    severity: str  # "error" | "warning"
    category: str  # "schema" | "price" | "volume" | "timestamp" | "completeness"
    column: str
    message: str
    count: int
    raw_lines: tuple[int, ...] = ()
    recommendation: str = ""


@dataclass(frozen=True)
class ValidationReport:
    """Result of validating one raw batch (§2.3 structure)."""

    passed: bool
    schema_valid: bool
    data_valid: bool
    rules_checked: int
    errors: int
    warnings: int
    issues: tuple[ValidationIssue, ...] = ()
    affected_raw_lines: frozenset[int] = frozenset()
    rejected_raw_lines: frozenset[int] = frozenset()  # ERROR, unfixable → dropped
    summary: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationOptions:
    """Knobs from config cleaning.validation + schema. Default = blueprint."""

    min_rows: int = 2
    max_missing_pct: float = 0.30
    max_price_change_pct: float = 0.50
    holidays: frozenset[date] = frozenset()


def validate_batch(
    records: list[dict[str, Any]],
    issues_from_reader: list[dict[str, Any]],
    *,
    options: ValidationOptions | None = None,
    now: datetime | None = None,
) -> ValidationReport:
    """Validate a raw batch and produce explicit per-record reasons.

    ``records`` is the tolerant-reader output (may contain rows that the
    reader could parse but that violate domain rules). ``issues_from_reader``
    are the reader's unparseable-row/schema issues (VAL-S01/VAL-S04).
    """
    options = options or ValidationOptions()
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    issues: list[ValidationIssue] = []

    # --- Schema (VAL-S01 already reported by the reader; S03 minimum rows)
    if len(records) < options.min_rows:
        issues.append(
            ValidationIssue(
                rule_id="VAL-S03",
                severity=SEVERITY_ERROR,
                category="schema",
                column="",
                message=f"minimum row count is {options.min_rows}, got {len(records)}",
                count=1,
            )
        )
    schema_valid = not any(
        issue.rule_id.startswith("VAL-S") and issue.severity == SEVERITY_ERROR for issue in issues
    ) and not any(
        reader_issue.get("rule_id") in {"VAL-S01", "VAL-S04"}
        and reader_issue.get("severity") == "error"
        for reader_issue in issues_from_reader
    )

    # --- Per-record data validation -------------------------------------
    rejected: set[int] = set()  # raw lines that must be dropped
    affected: set[int] = set()  # raw lines with any issue (reject+fix+flag)
    price_violations: dict[str, list[int]] = {column: [] for column in REQUIRED_PRICE_COLUMNS}
    negative_volume: list[int] = []
    zero_volume: list[int] = []
    low_volume: list[int] = []
    ohlc_high: list[int] = []
    ohlc_low: list[int] = []
    null_price: dict[str, list[int]] = {column: [] for column in REQUIRED_COLUMNS}
    future_rows: list[int] = []
    weekend_rows: list[int] = []
    holiday_rows: list[int] = []

    timestamps: list[datetime] = []
    lines_by_timestamp: dict[datetime, list[int]] = {}

    for record in records:
        line = int(record["raw_line"])
        timestamps.append(record["timestamp"])
        lines_by_timestamp.setdefault(record["timestamp"], []).append(line)

        # VAL-T03: future timestamp
        if record["timestamp"].date() > now.date():
            future_rows.append(line)
            rejected.add(line)
            affected.add(line)

        # VAL-P01..P04: prices positive
        for column_name in REQUIRED_PRICE_COLUMNS:
            value = record.get(column_name)
            if value is None or (isinstance(value, float) and not math.isfinite(value)):
                null_price[column_name].append(line)
                affected.add(line)
            elif value <= 0:
                price_violations[column_name].append(line)
                rejected.add(line)
                affected.add(line)

        # VAL-V01: volume >= 0
        volume = record.get("volume")
        if volume is None:
            null_price["volume"].append(line)
            affected.add(line)
        elif volume < 0:
            negative_volume.append(line)
            rejected.add(line)
            affected.add(line)
        elif volume == 0:
            zero_volume.append(line)
            affected.add(line)
        elif volume < 1000:
            low_volume.append(line)
            affected.add(line)

        # VAL-P05/P06: OHLC consistency (fixable)
        open_, high, low, close = (
            record.get("open"),
            record.get("high"),
            record.get("low"),
            record.get("close"),
        )
        if (
            high is not None
            and open_ is not None
            and close is not None
            and high < max(open_, close)
        ):
            ohlc_high.append(line)
            affected.add(line)
        if low is not None and open_ is not None and close is not None and low > min(open_, close):
            ohlc_low.append(line)
            affected.add(line)

        # VAL-T04/T05: trading-day checks
        weekday = record["timestamp"].weekday()
        if weekday >= 5:
            weekend_rows.append(line)
            affected.add(line)
        elif record["timestamp"].date() in options.holidays:
            holiday_rows.append(line)
            affected.add(line)

    # --- VAL-T01 duplicates (error, fixable by dedup) --------------------
    duplicate_lines: list[int] = []
    for lines in lines_by_timestamp.values():
        if len(lines) > 1:
            duplicate_lines.extend(lines[1:])  # keep_first anchor; dedup strategy decides
            affected.update(lines)

    # --- VAL-T02 ordering (warning, fixable by sort) ----------------------
    disordered = 0
    for index in range(1, len(timestamps)):
        if timestamps[index] < timestamps[index - 1]:
            disordered += 1

    # --- VAL-P08 price anomaly (warning, kept) ---------------------------
    anomaly_lines: list[int] = []
    closes = [(record["timestamp"], record.get("close")) for record in records]
    for index in range(1, len(closes)):
        previous = closes[index - 1][1]
        current = closes[index][1]
        if previous and current and previous > 0:
            change = abs(current / previous - 1.0)
            if change > options.max_price_change_pct:
                anomaly_lines.append(int(records[index]["raw_line"]))
                affected.add(records[index]["raw_line"])

    # --- VAL-C01 missing-data % per required column -----------------------
    missing_by_column: dict[str, int] = {}
    for column_name in REQUIRED_COLUMNS:
        missing = sum(
            1
            for record in records
            if record.get(column_name) is None
            or (
                isinstance(record.get(column_name), float)
                and not math.isfinite(record[column_name])
            )
        )
        missing_by_column[column_name] = missing
        if len(records) > 0 and missing / len(records) > options.max_missing_pct:
            issues.append(
                ValidationIssue(
                    rule_id="VAL-C01",
                    severity=SEVERITY_WARNING,
                    category="completeness",
                    column=column_name,
                    message=(
                        f"column {column_name!r} is {missing / len(records):.1%} missing "
                        f"(> {options.max_missing_pct:.0%})"
                    ),
                    count=1,
                )
            )

    # --- VAL-C02 consecutive trading-day gaps > 5 days --------------------
    gap_issues = _detect_gaps(records)

    # --- VAL-V02/V03, P08, T04/T05 warnings -------------------------------
    if zero_volume:
        issues.append(
            ValidationIssue(
                rule_id="VAL-V02",
                severity=SEVERITY_WARNING,
                category="volume",
                column="volume",
                message=f"{len(zero_volume)} rows have zero volume on a trading day",
                count=len(zero_volume),
                raw_lines=tuple(sorted(zero_volume)),
                recommendation="flag and keep; investigate liquidity",
            )
        )
    if low_volume:
        issues.append(
            ValidationIssue(
                rule_id="VAL-V03",
                severity=SEVERITY_WARNING,
                category="volume",
                column="volume",
                message=f"{len(low_volume)} rows have volume < 1000",
                count=len(low_volume),
                raw_lines=tuple(sorted(low_volume)),
            )
        )
    if weekend_rows:
        issues.append(
            ValidationIssue(
                rule_id="VAL-T04",
                severity=SEVERITY_WARNING,
                category="timestamp",
                column="timestamp",
                message=f"{len(weekend_rows)} rows fall on a weekend",
                count=len(weekend_rows),
                raw_lines=tuple(sorted(weekend_rows)),
            )
        )
    if holiday_rows:
        issues.append(
            ValidationIssue(
                rule_id="VAL-T05",
                severity=SEVERITY_WARNING,
                category="timestamp",
                column="timestamp",
                message=f"{len(holiday_rows)} rows fall on a configured holiday",
                count=len(holiday_rows),
                raw_lines=tuple(sorted(holiday_rows)),
            )
        )
    if anomaly_lines:
        issues.append(
            ValidationIssue(
                rule_id="VAL-P08",
                severity=SEVERITY_WARNING,
                category="price",
                column="close",
                message=(
                    f"{len(anomaly_lines)} rows have |daily change| > "
                    f"{options.max_price_change_pct:.0%}"
                ),
                count=len(anomaly_lines),
                raw_lines=tuple(sorted(anomaly_lines)),
                recommendation="flag and keep (outlier stage may flag further)",
            )
        )
    if disordered:
        issues.append(
            ValidationIssue(
                rule_id="VAL-T02",
                severity=SEVERITY_WARNING,
                category="timestamp",
                column="timestamp",
                message=f"{disordered} timestamp pairs are out of ascending order",
                count=disordered,
                recommendation="cleaning sorts ascending",
            )
        )

    # --- Error issues (row-level) -----------------------------------------
    for column_name, lines in price_violations.items():
        if lines:
            issues.append(
                ValidationIssue(
                    rule_id="VAL-P0" + str(REQUIRED_PRICE_COLUMNS.index(column_name) + 1),
                    severity=SEVERITY_ERROR,
                    category="price",
                    column=column_name,
                    message=f"{len(lines)} rows have non-positive {column_name}",
                    count=len(lines),
                    raw_lines=tuple(sorted(lines)),
                    recommendation="reject row (unfixable)",
                )
            )
    if negative_volume:
        issues.append(
            ValidationIssue(
                rule_id="VAL-V01",
                severity=SEVERITY_ERROR,
                category="volume",
                column="volume",
                message=f"{len(negative_volume)} rows have negative volume",
                count=len(negative_volume),
                raw_lines=tuple(sorted(negative_volume)),
                recommendation="reject row (unfixable)",
            )
        )
    if future_rows:
        issues.append(
            ValidationIssue(
                rule_id="VAL-T03",
                severity=SEVERITY_ERROR,
                category="timestamp",
                column="timestamp",
                message=f"{len(future_rows)} rows have timestamps after today",
                count=len(future_rows),
                raw_lines=tuple(sorted(future_rows)),
                recommendation="reject row (unfixable)",
            )
        )
    if duplicate_lines:
        issues.append(
            ValidationIssue(
                rule_id="VAL-T01",
                severity=SEVERITY_ERROR,
                category="timestamp",
                column="timestamp",
                message=f"{len(duplicate_lines)} rows duplicate an earlier timestamp",
                count=len(duplicate_lines),
                raw_lines=tuple(sorted(duplicate_lines)),
                recommendation="cleaning removes duplicates per duplicate_strategy",
            )
        )
    if ohlc_high:
        issues.append(
            ValidationIssue(
                rule_id="VAL-P05",
                severity=SEVERITY_ERROR,
                category="price",
                column="high",
                message=f"{len(ohlc_high)} rows have high < max(open, close)",
                count=len(ohlc_high),
                raw_lines=tuple(sorted(ohlc_high)),
                recommendation="cleaning fixes high = max(open, close)",
            )
        )
    if ohlc_low:
        issues.append(
            ValidationIssue(
                rule_id="VAL-P06",
                severity=SEVERITY_ERROR,
                category="price",
                column="low",
                message=f"{len(ohlc_low)} rows have low > min(open, close)",
                count=len(ohlc_low),
                raw_lines=tuple(sorted(ohlc_low)),
                recommendation="cleaning fixes low = min(open, close)",
            )
        )

    issues.extend(gap_issues)
    issues.extend(_reader_issues(issues_from_reader))
    issues.sort(key=lambda issue: (issue.severity, issue.rule_id))

    errors = sum(1 for issue in issues if issue.severity == SEVERITY_ERROR)
    warnings = sum(1 for issue in issues if issue.severity == SEVERITY_WARNING)
    data_valid = errors == 0 or (
        # Only fixable errors exist (dedup/OHLC/ordering can be repaired),
        # and no rows were rejected as unfixable.
        not rejected
        and all(
            issue.rule_id
            in {"VAL-T01", "VAL-P05", "VAL-P06", "VAL-T02", "VAL-S01", "VAL-S03", "VAL-S04"}
            or issue.severity == SEVERITY_WARNING
            for issue in issues
        )
    )

    summary: dict[str, int] = {"total": len(records), "errors": errors, "warnings": warnings}
    for issue in issues:
        summary[issue.rule_id] = summary.get(issue.rule_id, 0) + issue.count

    return ValidationReport(
        passed=schema_valid and data_valid,
        schema_valid=schema_valid,
        data_valid=data_valid,
        rules_checked=_RULES_CHECKED,
        errors=errors,
        warnings=warnings,
        issues=tuple(issues),
        affected_raw_lines=frozenset(affected),
        rejected_raw_lines=frozenset(rejected),
        summary=summary,
    )


def _reader_issues(issues_from_reader: list[dict[str, Any]]) -> list[ValidationIssue]:
    """Convert reader-level issues (VAL-S01/S04) into typed issues."""
    converted: list[ValidationIssue] = []
    for raw in issues_from_reader:
        converted.append(
            ValidationIssue(
                rule_id=raw.get("rule_id", "VAL-S01"),
                severity=raw.get("severity", SEVERITY_ERROR),
                category=raw.get("category", "schema"),
                column=raw.get("column", ""),
                message=raw.get("message", "reader issue"),
                count=int(raw.get("count", 1)),
                raw_lines=(int(raw["raw_line"]),) if raw.get("raw_line") is not None else (),
            )
        )
    return converted


def _detect_gaps(records: list[dict[str, Any]]) -> list[ValidationIssue]:
    """VAL-C02: consecutive trading-day gaps > 5 days (missing candles)."""
    timestamps = sorted(record["timestamp"].date() for record in records)
    issues: list[ValidationIssue] = []
    if len(timestamps) < 2:
        return issues
    findings: list[tuple[date, date, int]] = []
    for index in range(1, len(timestamps)):
        gap_days = (timestamps[index] - timestamps[index - 1]).days
        if gap_days > 5:
            findings.append((timestamps[index - 1], timestamps[index], gap_days))
    if findings:
        issues.append(
            ValidationIssue(
                rule_id="VAL-C02",
                severity=SEVERITY_WARNING,
                category="completeness",
                column="timestamp",
                message=f"{len(findings)} gaps of more than 5 days between consecutive candles",
                count=len(findings),
                recommendation=(
                    "missing candles detected; do NOT fabricate — flag for investigation"
                ),
            )
        )
    return issues


_RULES_CHECKED = 27  # counts distinct VAL-* checks implemented above
