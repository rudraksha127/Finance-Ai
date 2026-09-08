"""Mandatory feature leakage tests (milestone section 21 / blueprint 13.2).

- Test A — Future mutation: mutating only observations after T must not
  change any feature value at or before T.
- Test B — Truncation: features computed on a series ending at T must be
  identical to features through T computed on the longer series.
- Test C — Timestamp: no feature value at T may depend on timestamps > T
  (verified per feature column).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.compute import compute_features
from src.features.registry import FEATURE_COLUMNS


def make_frame(n: int = 160, *, start: str = "2025-01-02") -> pd.DataFrame:
    rng = np.random.default_rng(7)
    idx = pd.date_range(start, periods=n, freq="B")
    close = 100 + np.cumsum(rng.normal(0, 1.0, n))
    return pd.DataFrame(
        {
            "open": close + rng.normal(0, 0.1, n),
            "high": close + np.abs(rng.normal(0.5, 0.3, n)),
            "low": close - np.abs(rng.normal(0.5, 0.3, n)),
            "close": close,
            "volume": rng.integers(500_000, 2_000_000, n).astype(float),
        },
        index=idx,
    )


def test_a_future_mutation_does_not_change_past_features():
    frame = make_frame()
    cutoff = 90
    baseline = compute_features(frame)

    mutated = frame.copy()
    # Mutate ONLY rows after the cutoff (prices and volume).
    tail = mutated.index[cutoff + 1 :]
    mutated.loc[tail, ["open", "high", "low", "close"]] *= 1.5
    mutated.loc[tail, "volume"] *= 10.0

    recomputed = compute_features(mutated)
    pd.testing.assert_frame_equal(baseline.iloc[: cutoff + 1], recomputed.iloc[: cutoff + 1])


def test_b_truncation_historical_invariance():
    frame = make_frame()
    cutoff = 90
    truncated = compute_features(frame.iloc[: cutoff + 1])
    full = compute_features(frame)
    pd.testing.assert_frame_equal(truncated, full.iloc[: cutoff + 1])


def test_c_no_feature_depends_on_future_timestamps():
    frame = make_frame()
    full = compute_features(frame)
    for cutoff in (50, 100):
        partial = compute_features(frame.iloc[: cutoff + 1])
        # Every feature value at T must be identical whether or not data
        # after T exists (covers every column, incl. 100-day lookbacks).
        pd.testing.assert_series_equal(partial.iloc[cutoff], full.iloc[cutoff], check_names=False)


def test_each_column_passes_truncation_check():
    frame = make_frame()
    full = compute_features(frame)
    for column in FEATURE_COLUMNS:
        partial = compute_features(frame.iloc[:101])
        pd.testing.assert_series_equal(
            partial[column],
            full[column].iloc[:101],
            check_names=False,
            obj=f"column {column} leaks future data",
        )


def test_shift_consistency():
    # F(T) must equal the value computed with data only through T.
    frame = make_frame()
    full = compute_features(frame)
    for t in (60, 120):
        prefix = compute_features(frame.iloc[: t + 1])
        pd.testing.assert_series_equal(
            prefix.iloc[t], full.iloc[t], check_names=False, obj=f"row {t}"
        )


def test_volume_ratio_leakage_specific():
    # volume_ratio_5d at T uses only volume through T: mutating the volume
    # at T+1 must not change it.
    frame = make_frame()
    baseline = compute_features(frame)
    mutated = frame.copy()
    mutated.loc[mutated.index[61:], "volume"] *= 3.0
    recomputed = compute_features(mutated)
    pd.testing.assert_series_equal(
        baseline["volume_ratio_5d"].iloc[:61],
        recomputed["volume_ratio_5d"].iloc[:61],
        check_names=False,
    )


def test_rsi_leakage_specific():
    frame = make_frame()
    baseline = compute_features(frame)
    mutated = frame.copy()
    mutated.loc[mutated.index[30:], "close"] *= 1.7  # future-only price shock
    recomputed = compute_features(mutated)
    pd.testing.assert_series_equal(
        baseline["rsi_14"].iloc[:30],
        recomputed["rsi_14"].iloc[:30],
        check_names=False,
    )


@pytest.mark.parametrize("column", ["sma_5", "sma_20", "sma_50"])
def test_rolling_feature_uses_only_historical_rows(column: str):
    # A rolling feature at row T is a pure function of rows [0..T]:
    # removing any single row BEFORE T changes it; removing rows AFTER T never does.
    frame = make_frame()
    full = compute_features(frame)
    t = 90
    timestamp_t = frame.index[t]
    removed = compute_features(frame.drop(frame.index[t - 2]))
    assert removed[column].loc[timestamp_t] != pytest.approx(full[column].loc[timestamp_t])
    extended = compute_features(frame.iloc[: t + 1])
    pd.testing.assert_series_equal(full[column].iloc[: t + 1], extended[column], check_names=False)
