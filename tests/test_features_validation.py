"""Feature validation tests — FVAL-01..08 behavior."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.registry import FEATURES
from src.features.validation import FeatureIssue, validate_features


def valid_frame(n: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    idx = pd.date_range("2025-01-02", periods=n, freq="B")
    frame = pd.DataFrame({spec.name: rng.normal(0, 1, n) for spec in FEATURES}, index=idx)
    # Respect documented bounded ranges for the candle/ratio columns.
    frame["rsi_14"] = frame["rsi_14"].clip(0, 100)
    frame["rsi_7"] = frame["rsi_7"].clip(0, 100)
    for column in ("body_ratio", "upper_wick_ratio", "lower_wick_ratio", "close_position"):
        frame[column] = frame[column].clip(0, 1)
    frame["is_bullish"] = (frame["is_bullish"] > 0).astype(float)
    frame["bb_squeeze_20d"] = (frame["bb_squeeze_20d"] > 0).astype(float)
    for column in (
        "volatility_5d",
        "volatility_10d",
        "volatility_20d",
        "volatility_50d",
        "atr_14",
        "true_range",
        "realized_vol_20d",
        "volatility_ratio",
        "volume_ratio_5d",
        "volume_ratio_20d",
        "volume_trend_5d",
        "bb_bandwidth_20d",
        "high_low_range_20d",
    ):
        frame[column] = frame[column].abs()
    return frame


def test_valid_frame_passes():
    report = validate_features(valid_frame())
    assert report.total_features == 52
    assert report.valid_features == 52
    assert report.invalid_features == 0
    assert report.errors == ()


def test_infinite_values_are_errors():
    frame = valid_frame()
    frame["returns_1d"] = np.inf
    report = validate_features(frame)
    assert any(
        issue.check_id == "FVAL-02" and issue.feature == "returns_1d" for issue in report.errors
    )


def test_range_violation_is_error():
    frame = valid_frame()
    frame["rsi_14"] = 150.0  # outside [0, 100]
    report = validate_features(frame)
    assert any(issue.check_id == "FVAL-03" and issue.feature == "rsi_14" for issue in report.errors)


def test_range_violation_for_binary_features():
    frame = valid_frame()
    frame["is_bullish"] = 0.5  # not in {0, 1}
    report = validate_features(frame)
    assert any(
        issue.check_id == "FVAL-03" and issue.feature == "is_bullish" for issue in report.errors
    )


def test_nan_ratio_warning():
    frame = valid_frame()
    frame["sma_50"] = np.nan
    frame.loc[frame.index[:50], "sma_50"] = 1.0  # 70/120 NaN = 58% > 30%
    report = validate_features(frame, max_nan_ratio=0.30)
    assert any(
        issue.check_id == "FVAL-01" and issue.feature == "sma_50" for issue in report.warnings
    )
    assert report.nan_ratios["sma_50"] > 0.30


def test_constant_feature_warning():
    frame = valid_frame()
    frame["momentum_10"] = 42.0
    report = validate_features(frame)
    assert "momentum_10" in report.constant_features
    assert any(
        issue.check_id == "FVAL-04" and issue.feature == "momentum_10" for issue in report.warnings
    )


def test_duplicate_feature_pair_warning():
    frame = valid_frame()
    frame["log_return_1d"] = frame["returns_1d"].copy()  # perfect duplicate
    report = validate_features(frame, duplicate_correlation=0.99)
    # Pairs are reported in sorted column order.
    assert any(
        {left, right} == {"returns_1d", "log_return_1d"}
        for left, right, _ in report.duplicate_pairs
    )
    assert any(issue.check_id == "FVAL-05" for issue in report.warnings)


def test_outlier_warning():
    frame = valid_frame()
    frame.loc[frame.index[:3], "returns_1d"] = 100.0  # extreme z-scores
    report = validate_features(frame, outlier_zscore_threshold=5.0)
    assert any(
        issue.check_id == "FVAL-06" and issue.feature == "returns_1d" for issue in report.warnings
    )


def test_timestamp_alignment_errors():
    frame = valid_frame()
    frame = frame.sort_index(ascending=False)
    report = validate_features(frame)
    assert any(
        issue.check_id == "FVAL-08" and "ascending" in issue.message for issue in report.errors
    )

    frame2 = valid_frame()
    frame2 = pd.concat([frame2, frame2.iloc[[0]]])
    report2 = validate_features(frame2)
    assert any(
        issue.check_id == "FVAL-08" and "duplicate" in issue.message for issue in report2.errors
    )


def test_missing_columns_rejected():
    frame = valid_frame().drop(columns=["returns_1d"])
    with pytest.raises(ValueError):
        validate_features(frame)


def test_report_counts_and_properties():
    frame = valid_frame()
    frame["returns_1d"] = np.inf
    report = validate_features(frame)
    assert report.invalid_features == 1
    assert report.valid_features == 51
    assert isinstance(report.issues[0], FeatureIssue)
    assert report.infinite_counts["returns_1d"] >= 1
    assert report.nan_ratios["returns_1d"] == 0.0
