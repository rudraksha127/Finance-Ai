"""Quality score engine — DATA_CLEANING_VALIDATION.md §6.

Score 0-100 with the approved weights (30/30/20/10/10):

    score = completeness×0.30 + validity×0.30 + consistency×0.20
          + freshness×0.10 + uniqueness×0.10

- completeness: 1 - missing_cells / total_cells (required columns)
- validity: rows passing all ERROR-level rules / total rows
- consistency: rows with correct OHLC relationships / total rows
- freshness: max(0, 100 - 2 × days_since_last) (capped at
  ``freshness_max_days``)
- uniqueness: unique_timestamps / total_timestamps

Ratings (blueprint §6.2): >=90 excellent, >=80 good, >=70 fair,
>=60 poor, <60 failing.
Gate (blueprint §6.5): >=90 PASS, 70-89 PASS_WITH_WARNINGS,
60-69 REVIEW_REQUIRED, <60 FAIL.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.cleaning.validation import ValidationReport

REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")

DIMENSION_ORDER = ("completeness", "validity", "consistency", "freshness", "uniqueness")


@dataclass(frozen=True)
class DataQualityReport:
    """Quality result (§6.4 structure)."""

    ticker: str
    overall_score: float
    rating: str
    dimensions: dict[str, float]
    weights: dict[str, float]
    issues: tuple[str, ...] = ()  # short contributing-issue descriptions
    gate: str = ""
    computed_at: datetime | None = None


def compute_quality(
    records: list[dict[str, Any]],
    validation: ValidationReport,
    *,
    ticker: str,
    weights: dict[str, float] | None = None,
    freshness_max_days: int = 50,
    now: datetime | None = None,
) -> DataQualityReport:
    """Compute the five-dimension quality score for a cleaned batch."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    weights = weights or {
        "completeness": 0.30,
        "validity": 0.30,
        "consistency": 0.20,
        "freshness": 0.10,
        "uniqueness": 0.10,
    }
    total = len(records)
    if total == 0:
        dimensions = {name: 0.0 for name in DIMENSION_ORDER}
    else:
        dimensions = {
            "completeness": _completeness(records),
            "validity": _validity(validation, total),
            "consistency": _consistency(records),
            "freshness": _freshness(records, freshness_max_days=freshness_max_days, now=now),
            "uniqueness": _uniqueness(records),
        }

    score = sum(dimensions[name] * weights[name] for name in DIMENSION_ORDER)
    score = round(min(max(score, 0.0), 100.0), 2)
    issues = _contributing_issues(dimensions, weights)
    report = DataQualityReport(
        ticker=ticker,
        overall_score=score,
        rating=rating_for(score),
        dimensions={name: round(dimensions[name], 2) for name in DIMENSION_ORDER},
        weights={name: float(weights[name]) for name in DIMENSION_ORDER},
        issues=tuple(issues),
        gate=gate_for(score),
        computed_at=now,
    )
    return report


def rating_for(score: float) -> str:
    """Map a 0-100 score to the blueprint rating bands."""
    if score >= 90:
        return "excellent"
    if score >= 80:
        return "good"
    if score >= 70:
        return "fair"
    if score >= 60:
        return "poor"
    return "failing"


def gate_for(score: float) -> str:
    """Map a score to the quality-gate decision (§6.5)."""
    if score >= 90:
        return "PASS"
    if score >= 70:
        return "PASS_WITH_WARNINGS"
    if score >= 60:
        return "REVIEW_REQUIRED"
    return "FAIL"


def _completeness(records: list[dict[str, Any]]) -> float:
    total_cells = len(records) * len(REQUIRED_COLUMNS)
    if total_cells == 0:
        return 0.0
    missing = sum(
        1 for record in records for column in REQUIRED_COLUMNS if record.get(column) is None
    )
    return (1 - missing / total_cells) * 100


def _validity(validation: ValidationReport, total: int) -> float:
    if total == 0:
        return 0.0
    rejected = len(validation.rejected_raw_lines)
    return max(0.0, (1 - rejected / total) * 100)


def _consistency(records: list[dict[str, Any]]) -> float:
    if not records:
        return 0.0
    consistent = 0
    for record in records:
        open_, high, low, close = record["open"], record["high"], record["low"], record["close"]
        if None in (open_, high, low, close):
            continue  # a row with missing prices is not OHLC-consistent
        if high >= max(open_, close) and low <= min(open_, close):
            consistent += 1
    return consistent / len(records) * 100


def _freshness(records: list[dict[str, Any]], *, freshness_max_days: int, now: datetime) -> float:
    if not records:
        return 0.0
    last = max(record["timestamp"].date() for record in records)
    days_since_last = (now.date() - last).days
    days_since_last = max(0, min(days_since_last, freshness_max_days))
    return max(0.0, 100 - days_since_last * 2)


def _uniqueness(records: list[dict[str, Any]]) -> float:
    if not records:
        return 0.0
    unique = len({record["timestamp"] for record in records})
    return unique / len(records) * 100


def _contributing_issues(dimensions: dict[str, float], weights: dict[str, float]) -> list[str]:
    """Describe dimensions dragging the score down (bounded, non-technical)."""
    issues: list[str] = []
    for name in DIMENSION_ORDER:
        score = dimensions[name]
        if score < 90:
            issues.append(f"{name} {score:.1f}/100 (weight {weights[name]:.0%}) below 90")
    return issues[:5]
