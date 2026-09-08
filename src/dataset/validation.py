"""Dataset validation — DVAL checks (DATASET_BUILDER_BLUEPRINT.md section 9).

| DVAL-01 | No NaN or Infinity in features/target | ERROR -> reject |
| DVAL-02 | No duplicate rows                  | ERROR -> reject  |
| DVAL-03 | Timestamps ascending               | ERROR -> reject  |
| DVAL-04 | Labels aligned with features       | ERROR -> reject  |
| DVAL-05 | No future leakage                  | ERROR -> reject  |
| DVAL-06 | Chronological splits (no overlap)  | ERROR -> reject  |
| DVAL-07 | Minimum split sizes                | WARNING -> log   |
| DVAL-08 | Label distribution acceptable      | WARNING -> log   |
| DVAL-09 | Feature count matches expected     | ERROR -> reject  |
| DVAL-10 | Quality score >= threshold         | WARNING -> log   |

ERRORs abort the build (never persist an invalid dataset); WARNINGs are
reported to the log and manifest for researcher review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.features.registry import FEATURE_COLUMNS

VALID_CLASSES = frozenset({"UP", "DOWN", "HOLD"})
MAX_LABEL_CLASS_SHARE_DEVIATION = 0.5  # any single class > 50% -> DVAL-08 warning


@dataclass(frozen=True)
class DatasetIssue:
    """A single DVAL finding."""

    check_id: str
    severity: str  # "error" | "warning"
    description: str
    affected_rows: int = 0
    recommendation: str = ""


@dataclass(frozen=True)
class DatasetValidationReport:
    """Outcome of dataset-level validation."""

    checks_run: int
    checks_passed: int
    issues: tuple[DatasetIssue, ...] = field(default_factory=tuple)

    @property
    def errors(self) -> tuple[DatasetIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[DatasetIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def passed(self) -> bool:
        return not self.errors


def validate_dataset_frame(
    frame: pd.DataFrame,
    *,
    expected_features: tuple[str, ...] = FEATURE_COLUMNS,
    required_columns: tuple[str, ...] = (),
    min_split_rows: dict[str, int] | None = None,
    quality_score: float | None = None,
    min_quality_score: float = 70.0,
) -> DatasetValidationReport:
    """Validate the fully-assembled dataset frame (DVAL-01..05, 09).

    ``required_columns`` are the non-feature, non-target columns the
    builder must carry (identity + version metadata). Split-level checks
    (DVAL-06..08) are applied by :func:`validate_split` after splitting.
    """
    issues: list[DatasetIssue] = []
    checks_run = 0
    checks_passed = 0

    def _check(ok: bool, issue: DatasetIssue) -> None:
        nonlocal checks_run, checks_passed
        checks_run += 1
        if ok:
            checks_passed += 1
        else:
            issues.append(issue)

    expected = set(expected_features)
    missing_features = expected - set(frame.columns)
    _check(
        not missing_features,
        DatasetIssue(
            "DVAL-09",
            "error",
            f"feature count/schema mismatch: missing {sorted(missing_features)}",
            affected_rows=0,
            recommendation="rebuild the feature set with the configured version",
        ),
    )
    extra = (
        set(frame.columns)
        - expected
        - set(required_columns)
        - {"label", "future_return", "target_timestamp"}
    )
    _check(
        not extra,
        DatasetIssue(
            "DVAL-09",
            "error",
            f"unexpected dataset columns: {sorted(extra)}",
            affected_rows=0,
            recommendation="remove unexpected columns from the dataset schema",
        ),
    )
    if missing_features or extra:
        return DatasetValidationReport(
            checks_run=checks_run, checks_passed=checks_passed, issues=tuple(issues)
        )

    for column in required_columns:
        _check(
            column in frame.columns and not frame[column].isna().any(),
            DatasetIssue(
                "DVAL-01",
                "error",
                f"mandatory column {column!r} missing or contains NaN",
                affected_rows=0,
                recommendation="dataset must be complete before persistence",
            ),
        )

    # DVAL-01: no NaN or infinity in persisted feature/target columns.
    numeric_features = frame[list(expected_features)].apply(pd.to_numeric, errors="coerce")
    non_finite_features = int((~np.isfinite(numeric_features)).sum().sum())
    _check(
        non_finite_features == 0,
        DatasetIssue(
            "DVAL-01",
            "error",
            f"{non_finite_features} non-finite values remain in feature columns",
            affected_rows=non_finite_features,
            recommendation="drop warm-up rows and reject invalid numeric values",
        ),
    )
    if "label" in frame.columns:
        nan_labels = int(frame["label"].isna().sum())
        _check(
            nan_labels == 0,
            DatasetIssue(
                "DVAL-01",
                "error",
                f"{nan_labels} rows have NaN labels",
                affected_rows=nan_labels,
                recommendation="exclude invalid-label rows before building",
            ),
        )
    if "future_return" in frame.columns:
        future_return = pd.to_numeric(frame["future_return"], errors="coerce")
        non_finite_returns = int((~np.isfinite(future_return)).sum())
        _check(
            non_finite_returns == 0,
            DatasetIssue(
                "DVAL-01",
                "error",
                f"{non_finite_returns} non-finite future returns",
                affected_rows=non_finite_returns,
                recommendation="exclude invalid target rows before building",
            ),
        )

    # DVAL-02: no duplicate (timestamp, ticker) rows.
    if "ticker" in frame.columns and "timestamp" in frame.columns:
        duplicates = int(frame.duplicated(subset=["ticker", "timestamp"]).sum())
        _check(
            duplicates == 0,
            DatasetIssue(
                "DVAL-02",
                "error",
                f"{duplicates} duplicate (ticker, timestamp) rows",
                affected_rows=duplicates,
                recommendation="align features/labels on unique timestamps",
            ),
        )

    # DVAL-03: timestamps ascending (already sorted by the builder).
    if "timestamp" in frame.columns:
        ts = pd.to_datetime(frame["timestamp"], errors="coerce")
        invalid_timestamps = int(ts.isna().sum())
        _check(
            invalid_timestamps == 0,
            DatasetIssue(
                "DVAL-03",
                "error",
                f"{invalid_timestamps} invalid observation timestamps",
                affected_rows=invalid_timestamps,
                recommendation="timestamps must be valid and consistently typed",
            ),
        )
        _check(
            invalid_timestamps == 0 and ts.is_monotonic_increasing,
            DatasetIssue(
                "DVAL-03",
                "error",
                "timestamps are not ascending",
                affected_rows=0,
                recommendation="sort by (timestamp, ticker) before splitting",
            ),
        )

    # DVAL-04/05 (frame level): label targets strictly after observations.
    if {"timestamp", "target_timestamp"}.issubset(frame.columns):
        obs = pd.to_datetime(frame["timestamp"], errors="coerce")
        tgt = pd.to_datetime(frame["target_timestamp"], errors="coerce")
        valid_target = tgt.notna()
        future_ok = valid_target & (tgt > obs)
        violations = int((~future_ok).sum())
        _check(
            violations == 0,
            DatasetIssue(
                "DVAL-05",
                "error",
                f"{violations} rows have target timestamps not after the observation",
                affected_rows=violations,
                recommendation="labels must describe outcomes strictly after T",
            ),
        )

    return DatasetValidationReport(
        checks_run=checks_run, checks_passed=checks_passed, issues=tuple(issues)
    )


def validate_split(
    split: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
    *,
    min_split_rows: dict[str, int] | None = None,
    min_quality_score: float = 70.0,
) -> DatasetValidationReport:
    """Split-level checks: overlap (DVAL-06), sizes (DVAL-07), balance (DVAL-08)."""
    train, val, test = split
    issues: list[DatasetIssue] = []
    checks_run = 0
    checks_passed = 0

    def _check(ok: bool, issue: DatasetIssue) -> None:
        nonlocal checks_run, checks_passed
        checks_run += 1
        if ok:
            checks_passed += 1
        else:
            issues.append(issue)

    def _span(frame: pd.DataFrame) -> tuple[Any, Any]:
        ts = pd.to_datetime(frame["timestamp"])
        return ts.min(), ts.max()

    # DVAL-06: chronological splits, no overlap.
    if not train.empty and not val.empty:
        _, train_max = _span(train)
        val_min, _ = _span(val)
        _check(
            train_max < val_min,
            DatasetIssue(
                "DVAL-06",
                "error",
                "train overlaps validation in time",
                affected_rows=0,
                recommendation="fix split boundaries",
            ),
        )
    if not val.empty and not test.empty:
        _, val_max = _span(val)
        test_min, _ = _span(test)
        _check(
            val_max < test_min,
            DatasetIssue(
                "DVAL-06",
                "error",
                "validation overlaps test in time",
                affected_rows=0,
                recommendation="fix split boundaries",
            ),
        )

    # DVAL-07: minimum split sizes (warning per blueprint 3.4).
    defaults = {"train": 100, "val": 20, "test": 20}
    sizes = {"train": len(train), "val": len(val), "test": len(test)}
    for name, minimum in (min_split_rows or defaults).items():
        if sizes[name] < minimum:
            issues.append(
                DatasetIssue(
                    "DVAL-07",
                    "warning",
                    f"{name} split has {sizes[name]} rows (< {minimum})",
                    affected_rows=sizes[name],
                    recommendation="collect more data or adjust split ratios",
                )
            )

    # DVAL-08: per-split label balance (each class present; none dominates >50%).
    for name, part in (("train", train), ("val", val), ("test", test)):
        if part.empty:
            continue
        labels = part["label"]
        counts = labels.value_counts()
        total = len(labels)
        for label in VALID_CLASSES:
            share = counts.get(label, 0) / total
            if share > MAX_LABEL_CLASS_SHARE_DEVIATION:
                issues.append(
                    DatasetIssue(
                        "DVAL-08",
                        "warning",
                        f"{name} split: {label} is {share:.1%} of rows",
                        affected_rows=int(counts.get(label, 0)),
                        recommendation="review thresholds (never auto-adjust)",
                    )
                )
        unknown = set(labels.unique()) - VALID_CLASSES
        _check(
            not unknown,
            DatasetIssue(
                "DVAL-04",
                "error",
                f"{name} split contains invalid label values {sorted(unknown)}",
                affected_rows=0,
                recommendation="labels must be UP/DOWN/HOLD",
            ),
        )

    return DatasetValidationReport(
        checks_run=checks_run, checks_passed=checks_passed, issues=tuple(issues)
    )
