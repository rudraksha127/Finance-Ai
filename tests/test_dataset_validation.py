"""Dataset validation (DVAL-*) and quality-score tests (blueprint section 9)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.dataset.quality import compute_dataset_quality
from src.dataset.validation import (
    validate_dataset_frame,
    validate_split,
)
from src.features.registry import FEATURE_COLUMNS

REQUIRED = (
    "ticker",
    "timestamp",
    "dataset_version",
    "feature_set_version",
    "label_set_version",
    "source_data_version",
)


def _feature_row(timestamp, ticker: str = "AAPL", value: float = 1.0) -> dict:
    row = {"ticker": ticker, "timestamp": timestamp}
    row.update({column: value for column in FEATURE_COLUMNS})
    row.update(
        {
            "label": "HOLD",
            "future_return": 0.0,
            "target_timestamp": pd.Timestamp(timestamp) + pd.Timedelta(days=7),
        }
    )
    row.update(
        {
            name: "v0.1"
            for name in (
                "dataset_version",
                "feature_set_version",
                "label_set_version",
                "source_data_version",
            )
        }
    )
    return row


def _good_frame(rows: int = 40, ticker: str = "AAPL") -> pd.DataFrame:
    timestamps = pd.date_range("2025-01-02", periods=rows, freq="B")
    frame = pd.DataFrame([_feature_row(ts, ticker=ticker) for ts in timestamps])
    # Balanced label mix (each class < 50%) so DVAL-08 stays quiet for
    # fixtures that are meant to exercise other checks.
    cycle = ["UP", "DOWN", "HOLD", "HOLD"] * (rows // 4 + 1)
    frame["label"] = cycle[:rows]
    return frame


# ---------------------------------------------------------------------------
# validate_dataset_frame
# ---------------------------------------------------------------------------
def test_good_frame_passes():
    report = validate_dataset_frame(_good_frame(), required_columns=REQUIRED)
    assert report.passed
    assert report.errors == ()
    assert report.checks_passed == report.checks_run


def test_missing_feature_column_reported():
    frame = _good_frame().drop(columns=[FEATURE_COLUMNS[0]])
    report = validate_dataset_frame(frame, required_columns=REQUIRED)
    assert not report.passed
    assert any(issue.check_id == "DVAL-09" for issue in report.errors)


def test_unexpected_column_reported():
    frame = _good_frame()
    frame["secret_shifted_close"] = 1.0
    frame["leaked_future_close"] = 1.0
    report = validate_dataset_frame(frame, required_columns=REQUIRED)
    assert not report.passed
    dval09 = [issue for issue in report.errors if issue.check_id == "DVAL-09"]
    assert any("leaked_future_close" in issue.description for issue in dval09)


def test_nan_features_rejected():
    frame = _good_frame()
    frame.loc[3, FEATURE_COLUMNS[0]] = np.nan
    report = validate_dataset_frame(frame, required_columns=REQUIRED)
    assert not report.passed
    assert any(issue.check_id == "DVAL-01" for issue in report.errors)


def test_infinite_features_and_targets_rejected():
    frame = _good_frame()
    frame.loc[3, FEATURE_COLUMNS[0]] = np.inf
    frame.loc[4, "future_return"] = -np.inf
    report = validate_dataset_frame(frame, required_columns=REQUIRED)
    assert not report.passed
    assert any(issue.check_id == "DVAL-01" for issue in report.errors)


def test_invalid_observation_timestamp_rejected():
    frame = _good_frame()
    frame["timestamp"] = frame["timestamp"].astype(object)
    frame.loc[3, "timestamp"] = "not-a-timestamp"
    report = validate_dataset_frame(frame, required_columns=REQUIRED)
    assert not report.passed
    assert any(issue.check_id == "DVAL-03" for issue in report.errors)


def test_nan_label_rejected():
    frame = _good_frame()
    frame.loc[5, "label"] = np.nan
    report = validate_dataset_frame(frame, required_columns=REQUIRED)
    assert not report.passed
    assert any(issue.check_id == "DVAL-01" for issue in report.errors)


def test_missing_target_timestamp_rejected():
    frame = _good_frame()
    frame.loc[5, "target_timestamp"] = pd.NaT
    report = validate_dataset_frame(frame, required_columns=REQUIRED)
    assert not report.passed
    assert any(issue.check_id == "DVAL-05" for issue in report.errors)


def test_duplicate_rows_rejected():
    frame = _good_frame()
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    report = validate_dataset_frame(frame, required_columns=REQUIRED)
    assert not report.passed
    assert any(issue.check_id == "DVAL-02" for issue in report.errors)


def test_unsorted_timestamps_rejected():
    frame = _good_frame().iloc[::-1].reset_index(drop=True)
    report = validate_dataset_frame(frame, required_columns=REQUIRED)
    assert not report.passed
    assert any(issue.check_id == "DVAL-03" for issue in report.errors)


def test_target_not_after_observation_rejected():
    frame = _good_frame()
    # Target at the same instant as the observation -> leakage (DVAL-05).
    frame["target_timestamp"] = pd.to_datetime(frame["timestamp"])
    report = validate_dataset_frame(frame, required_columns=REQUIRED)
    assert not report.passed
    assert any(issue.check_id == "DVAL-05" for issue in report.errors)


def test_missing_mandatory_column_rejected():
    frame = _good_frame().drop(columns=["ticker"])
    report = validate_dataset_frame(frame, required_columns=REQUIRED)
    assert not report.passed
    assert any(issue.check_id == "DVAL-01" for issue in report.errors)


# ---------------------------------------------------------------------------
# validate_split
# ---------------------------------------------------------------------------
def _split_frames(rows: int = 300) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # Distinct date ranges per split so the fixture itself is chronologically
    # isolated (DVAL-06 inspects actual timestamps, not row positions).
    train = _good_frame(rows)
    val_start = train["timestamp"].max() + pd.Timedelta(days=1)
    val = _good_frame(rows // 2)
    val["timestamp"] = pd.date_range(val_start, periods=len(val), freq="B")
    test_start = val["timestamp"].max() + pd.Timedelta(days=1)
    test = _good_frame(rows // 2)
    test["timestamp"] = pd.date_range(test_start, periods=len(test), freq="B")
    return train, val, test


def test_good_split_passes():
    report = validate_split(_split_frames())
    assert report.errors == ()


def test_overlapping_splits_rejected():
    train, val, test = _split_frames()
    # Force overlap: append the last train row to validation.
    val = pd.concat([train.iloc[[-1]], val], ignore_index=True)
    report = validate_split((train, val, test))
    assert any(issue.check_id == "DVAL-06" for issue in report.errors)


def test_small_splits_warn_not_error():
    train = _good_frame(10)
    val = _good_frame(5)
    val["timestamp"] = pd.date_range(
        train["timestamp"].max() + pd.Timedelta(days=1), periods=5, freq="B"
    )
    test = _good_frame(5)
    test["timestamp"] = pd.date_range(
        val["timestamp"].max() + pd.Timedelta(days=1), periods=5, freq="B"
    )
    report = validate_split((train, val, test))
    assert report.passed  # warnings only
    dval07 = [issue for issue in report.warnings if issue.check_id == "DVAL-07"]
    assert len(dval07) == 3


def test_invalid_label_class_rejected():
    train, val, test = _split_frames()
    train.loc[0, "label"] = "MOON"
    report = validate_split((train, val, test))
    assert not report.passed
    assert any(issue.check_id == "DVAL-04" for issue in report.errors)


def test_imbalanced_class_warns():
    train, val, test = _split_frames()
    train["label"] = "UP"  # 100% UP in train
    report = validate_split((train, val, test))
    assert report.passed
    assert any(issue.check_id == "DVAL-08" for issue in report.warnings)


def test_dval08_checks_each_split_separately():
    train, val, test = _split_frames()
    train["label"] = "UP"  # imbalanced train only
    report = validate_split((train, val, test))
    warnings = [issue for issue in report.warnings if issue.check_id == "DVAL-08"]
    assert len(warnings) == 1
    assert "train split" in warnings[0].description


# ---------------------------------------------------------------------------
# compute_dataset_quality
# ---------------------------------------------------------------------------
def test_quality_perfect_dataset_scores_100():
    quality = compute_dataset_quality(
        total_candidate_rows=1000,
        final_rows=1000,
        feature_nan_cells=0,
        final_feature_cells=1000 * len(FEATURE_COLUMNS),
        invalid_label_rows=0,
        ordered_ascending=True,
        unique_rows=True,
        schema_exact=True,
    )
    assert quality.score == 100.0
    assert quality.rating == "excellent"


def test_quality_retention_penalty():
    quality = compute_dataset_quality(
        total_candidate_rows=1000,
        final_rows=500,  # half the raw material survives alignment
        feature_nan_cells=0,
        final_feature_cells=500 * len(FEATURE_COLUMNS),
        invalid_label_rows=0,
        ordered_ascending=True,
        unique_rows=True,
        schema_exact=True,
    )
    # Only the retention component (0.30 weight) halves -> 85.0.
    assert quality.score == pytest.approx(85.0)
    assert quality.rating == "good"


def test_quality_disorder_penalty():
    quality = compute_dataset_quality(
        total_candidate_rows=100,
        final_rows=100,
        feature_nan_cells=0,
        final_feature_cells=100 * len(FEATURE_COLUMNS),
        invalid_label_rows=0,
        ordered_ascending=False,
        unique_rows=True,
        schema_exact=True,
    )
    assert quality.score == pytest.approx(85.0)  # 0.15 ordering weight lost


def test_quality_schema_penalty():
    quality = compute_dataset_quality(
        total_candidate_rows=100,
        final_rows=100,
        feature_nan_cells=0,
        final_feature_cells=100 * len(FEATURE_COLUMNS),
        invalid_label_rows=0,
        ordered_ascending=True,
        unique_rows=True,
        schema_exact=False,
    )
    assert quality.score == pytest.approx(85.0)
    assert quality.rating == "good"


def test_quality_empty_input_is_zero_not_division_error():
    quality = compute_dataset_quality(
        total_candidate_rows=0,
        final_rows=0,
        feature_nan_cells=0,
        final_feature_cells=0,
        invalid_label_rows=0,
        ordered_ascending=True,
        unique_rows=True,
        schema_exact=False,
    )
    assert 0.0 <= quality.score <= 100.0
