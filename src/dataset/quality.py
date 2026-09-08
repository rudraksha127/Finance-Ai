"""Dataset quality score (milestone section 23; blueprint section 8/9).

Weighted 0-100 score computed AFTER alignment/dropping, following the
project's quality conventions (weights sum to 1.0, same style as the
Milestone-03 quality engine):

- retention     0.30  — usable rows / total candidate rows (completeness)
- feature_gap   0.20  — 1 - (feature-NaN cells / total cells) after warm-up drop
- label_gap     0.20  — 1 - (invalid-label rows / final rows)
- ordering      0.15  — 1.0 when timestamps are ascending and unique
- schema        0.15  — 1.0 when the schema matches exactly

A final dataset that passed DVAL-01 (no NaN) scores high on feature_gap
and label_gap; the score mainly reflects how much raw material survived
alignment (warm-up + label-window losses).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetQuality:
    """Dataset quality report."""

    score: float
    rating: str  # "excellent" | "good" | "fair" | "poor"
    components: dict[str, float]


def _rating(score: float) -> str:
    if score >= 90:
        return "excellent"
    if score >= 80:
        return "good"
    if score >= 70:
        return "fair"
    return "poor"


def compute_dataset_quality(
    *,
    total_candidate_rows: int,
    final_rows: int,
    feature_nan_cells: int,
    final_feature_cells: int,
    invalid_label_rows: int,
    ordered_ascending: bool,
    unique_rows: bool,
    schema_exact: bool,
    weights: dict[str, float] | None = None,
) -> DatasetQuality:
    """Compute the dataset quality score (0-100)."""
    w = weights or {
        "retention": 0.30,
        "feature_gap": 0.20,
        "label_gap": 0.20,
        "ordering": 0.15,
        "schema": 0.15,
    }

    retention = final_rows / total_candidate_rows if total_candidate_rows else 0.0
    feature_gap = 1.0 - feature_nan_cells / final_feature_cells if final_feature_cells else 0.0
    label_gap = 1.0 - invalid_label_rows / final_rows if final_rows else 0.0
    ordering = 1.0 if (ordered_ascending and unique_rows) else 0.0
    schema = 1.0 if schema_exact else 0.0

    components = {
        "retention": round(retention, 4),
        "feature_gap": round(feature_gap, 4),
        "label_gap": round(label_gap, 4),
        "ordering": ordering,
        "schema": schema,
    }
    score = 100.0 * (
        w["retention"] * retention
        + w["feature_gap"] * feature_gap
        + w["label_gap"] * label_gap
        + w["ordering"] * ordering
        + w["schema"] * schema
    )
    score = round(min(100.0, max(0.0, score)), 2)
    return DatasetQuality(score=score, rating=_rating(score), components=components)
