"""Feature validation — FVAL-* checks (FEATURE_ENGINEERING_BLUEPRINT.md section 14).

Checks implemented:

- FVAL-01 NaN ratio per feature        -> WARNING above ``max_nan_ratio``
- FVAL-02 infinite values              -> ERROR (feature rejected)
- FVAL-03 documented-range violations  -> ERROR for bounded features
- FVAL-04 constant features            -> WARNING (zero variance)
- FVAL-05 duplicate features (>0.99)   -> WARNING (correlation pair)
- FVAL-06 extreme outliers (|z| > k)   -> WARNING if > 1% of non-NaN values
- FVAL-08 timestamp alignment          -> ERROR on non-monotonic/duplicate index

ERROR-level issues fail generation (never persist obviously corrupt
features); WARNINGs are reported to the log and metadata for researcher
review (blueprint section 14.2/15: log, don't delete).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.features.registry import FEATURES, FeatureSpec


@dataclass(frozen=True)
class FeatureIssue:
    """A single validation finding for one feature."""

    check_id: str  # FVAL-01 .. FVAL-08
    severity: str  # "warning" | "error"
    feature: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeatureValidationReport:
    """Outcome of validating a computed feature frame."""

    total_features: int
    valid_features: int
    invalid_features: int
    nan_ratios: dict[str, float]
    infinite_counts: dict[str, int]
    constant_features: tuple[str, ...]
    duplicate_pairs: tuple[tuple[str, str, float], ...]
    outlier_counts: dict[str, int]
    issues: tuple[FeatureIssue, ...] = field(default_factory=tuple)

    @property
    def errors(self) -> tuple[FeatureIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[FeatureIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")


def _range_violation_count(series: pd.Series, spec: FeatureSpec) -> int:
    """Count non-NaN values outside the documented range of a bounded feature."""
    expected = spec.expected_range
    if expected == "(-inf, inf)":
        return 0
    values = series.dropna()
    if expected == "[0, 1]":
        return int(((values < 0.0) | (values > 1.0)).sum())
    if expected == "{0, 1}":
        return int((~values.isin((0.0, 1.0))).sum())
    if expected == "[0, 100]":
        return int(((values < 0.0) | (values > 100.0)).sum())
    if expected == "[0, inf)":
        return int((values < 0.0).sum())
    return 0


def validate_features(
    frame: pd.DataFrame,
    *,
    specs: tuple[FeatureSpec, ...] = FEATURES,
    max_nan_ratio: float = 0.30,
    max_infinite: int = 0,
    check_bounded_ranges: bool = True,
    outlier_zscore_threshold: float = 5.0,
    duplicate_correlation: float = 0.99,
) -> FeatureValidationReport:
    """Validate a computed feature frame against FVAL-01..08.

    Raises:
        ValueError: if the frame is missing registered feature columns.
    """
    expected = {spec.name for spec in specs}
    missing = expected - set(frame.columns)
    if missing:
        raise ValueError(f"feature frame missing registered columns: {sorted(missing)}")

    issues: list[FeatureIssue] = []
    nan_ratios: dict[str, float] = {}
    infinite_counts: dict[str, int] = {}
    constant_features: list[str] = []
    outlier_counts: dict[str, int] = {}

    # FVAL-08: timestamp alignment (index must be ordered + unique).
    if not frame.index.is_monotonic_increasing:
        issues.append(
            FeatureIssue(
                "FVAL-08",
                "error",
                "_index_",
                "feature index is not strictly ascending",
                {},
            )
        )
    if frame.index.has_duplicates:
        issues.append(
            FeatureIssue(
                "FVAL-08",
                "error",
                "_index_",
                "feature index contains duplicate timestamps",
                {},
            )
        )

    for spec in specs:
        series = frame[spec.name]
        total = len(series)
        nan_count = int(series.isna().sum())
        nan_ratio = nan_count / total if total else 0.0
        nan_ratios[spec.name] = round(nan_ratio, 4)

        # FVAL-01: NaN ratio.
        if nan_ratio > max_nan_ratio:
            issues.append(
                FeatureIssue(
                    "FVAL-01",
                    "warning",
                    spec.name,
                    f"NaN ratio {nan_ratio:.2%} exceeds {max_nan_ratio:.0%}",
                    {"nan_ratio": nan_ratio, "max_nan_ratio": max_nan_ratio},
                )
            )

        # FVAL-02: infinite values (reject).
        inf_count = int((~np.isfinite(series)).sum() - series.isna().sum())
        infinite_counts[spec.name] = inf_count
        if inf_count > max_infinite:
            issues.append(
                FeatureIssue(
                    "FVAL-02",
                    "error",
                    spec.name,
                    f"{inf_count} infinite values exceed allowed {max_infinite}",
                    {"infinite": inf_count, "max_infinite": max_infinite},
                )
            )

        # FVAL-03: documented range violations (reject).
        if check_bounded_ranges:
            violations = _range_violation_count(series, spec)
            if violations:
                issues.append(
                    FeatureIssue(
                        "FVAL-03",
                        "error",
                        spec.name,
                        f"{violations} values outside documented range {spec.expected_range}",
                        {"violations": violations, "expected_range": spec.expected_range},
                    )
                )  # FVAL-04: constant features (zero variance over finite values).
        finite_values = series[np.isfinite(series)]
        if len(finite_values) > 1 and float(finite_values.std()) == 0.0:
            constant_features.append(spec.name)
            issues.append(
                FeatureIssue(
                    "FVAL-04",
                    "warning",
                    spec.name,
                    "feature is constant (zero variance)",
                    {"std": 0.0},
                )
            )

        # FVAL-06: extreme outliers (|z| > threshold, > 1% of finite values).
        # Computed over finite values only — inf is already an FVAL-02 error.
        if len(finite_values) > 2 and float(finite_values.std()) > 0.0:
            z = (finite_values - finite_values.mean()).abs() / finite_values.std()
            outlier_count = int((z > outlier_zscore_threshold).sum())
            outlier_counts[spec.name] = outlier_count
            if outlier_count / len(finite_values) > 0.01:
                issues.append(
                    FeatureIssue(
                        "FVAL-06",
                        "warning",
                        spec.name,
                        f"{outlier_count} values with |z| > {outlier_zscore_threshold}",
                        {"outliers": outlier_count, "threshold": outlier_zscore_threshold},
                    )
                )
        else:
            outlier_counts[spec.name] = 0

    # FVAL-05: duplicate feature pairs (|correlation| > threshold).
    duplicate_pairs: list[tuple[str, str, float]] = []
    correlation = frame.corr(numeric_only=True)
    names = sorted(expected)
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            value = correlation.loc[left, right]
            if pd.notna(value) and abs(value) > duplicate_correlation:
                duplicate_pairs.append((left, right, round(float(value), 4)))
                issues.append(
                    FeatureIssue(
                        "FVAL-05",
                        "warning",
                        left,
                        f"correlation {value:.4f} with {right} exceeds {duplicate_correlation}",
                        {"pair": (left, right), "correlation": float(value)},
                    )
                )

    error_features = {issue.feature for issue in issues if issue.severity == "error"}
    valid = len(expected) - len(error_features)

    return FeatureValidationReport(
        total_features=len(expected),
        valid_features=valid,
        invalid_features=len(error_features),
        nan_ratios=nan_ratios,
        infinite_counts=infinite_counts,
        constant_features=tuple(constant_features),
        duplicate_pairs=tuple(duplicate_pairs),
        outlier_counts=outlier_counts,
        issues=tuple(issues),
    )
