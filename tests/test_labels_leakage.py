"""Mandatory label leakage tests (milestone section 13 / blueprint 10.3).

- TEST A — Feature independence: label generation never modifies feature values.
- TEST B — Historical invariance: labels through T are unchanged when data
  after T is added.
- TEST C — Horizon test: the label at T uses exactly the price at T+H.
- TEST D — Shift integrity: future values are shifted exactly H rows.
- TEST E — No target contamination: target columns never appear in feature
  storage.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.labels.generator import VALID, generate_labels


def make_df(n: int = 30) -> pd.DataFrame:
    rng = np.random.default_rng(11)
    idx = pd.date_range("2025-01-02", periods=n, freq="B")
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    return pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "adj_close": close,
            "volume": rng.integers(1_000_000, 2_000_000, n).astype(float),
        },
        index=idx,
    )


HORIZON = 5
THRESH = 0.01


def test_a_feature_independence():
    # Labels may use future data for the target, but must never touch the
    # feature inputs (blueprint section 13.1/13.3, milestone TEST A).
    df = make_df()
    snapshot = df.copy(deep=True)
    result = generate_labels(
        df,
        horizon=HORIZON,
        threshold_up=THRESH,
        threshold_down=THRESH,
        price_column="adj_close",
    )
    # Input OHLCV frame is byte-for-byte identical after generation.
    pd.testing.assert_frame_equal(df, snapshot)
    # The label output carries no source/feature columns.
    assert not {"open", "high", "low", "close", "volume"} & set(result.frame.columns)


def test_b_historical_invariance():
    # Labels on a dataset ending at T must match labels on a longer dataset
    # for every row whose future window lies within T (TEST B).
    df = make_df(30)
    truncated = df.iloc[:25]  # ends at T (0-indexed row 24)
    long_result = generate_labels(
        df,
        horizon=HORIZON,
        threshold_up=THRESH,
        threshold_down=THRESH,
        price_column="adj_close",
    )
    short_result = generate_labels(
        truncated,
        horizon=HORIZON,
        threshold_up=THRESH,
        threshold_down=THRESH,
        price_column="adj_close",
    )
    # Rows 0..19 have their T+H within the truncated range.
    pd.testing.assert_series_equal(
        short_result.frame["label"].iloc[:20],
        long_result.frame["label"].iloc[:20],
        check_names=False,
    )
    pd.testing.assert_series_equal(
        short_result.frame["future_return"].iloc[:20],
        long_result.frame["future_return"].iloc[:20],
        check_names=False,
    )


def test_c_horizon_uses_exact_future_timestamp():
    # The label at T is computed from the price at exactly T+H (TEST C).
    df = make_df(30)
    result = generate_labels(
        df,
        horizon=HORIZON,
        threshold_up=THRESH,
        threshold_down=THRESH,
        price_column="adj_close",
    ).frame
    for i in (0, 3, 7, 20):
        assert result["future_price"].iloc[i] == pytest.approx(df["adj_close"].iloc[i + HORIZON])
    # Row i's target timestamp is the index at position i+H.
    index = df.index
    assert index[0] < index[HORIZON]
    assert (result["future_price"].iloc[0:][result["status"] == VALID].notna()).all()


def test_d_shift_integrity():
    # future_price must be exactly price.shift(-H): every row shifted H forward.
    df = make_df(30)
    result = generate_labels(
        df,
        horizon=HORIZON,
        threshold_up=THRESH,
        threshold_down=THRESH,
        price_column="adj_close",
    ).frame
    expected = df["adj_close"].shift(-HORIZON)
    pd.testing.assert_series_equal(result["future_price"], expected, check_names=False)
    # And future_return = future_price / price - 1 (aligned series).
    recomputed = result["future_price"] / df["adj_close"] - 1.0
    pd.testing.assert_series_equal(result["future_return"], recomputed, check_names=False)


def test_e_no_target_contamination():
    # Target/label columns must never appear in the feature column set
    # (milestone TEST E). Simulates the M04 feature frame + M05 label frame.
    from src.features.registry import FEATURE_COLUMNS

    label_columns = {"future_price", "future_return", "label", "status", "target_timestamp"}
    assert label_columns.isdisjoint(set(FEATURE_COLUMNS))


def test_future_mutation_does_not_change_past_labels():
    # Extending the dataset by mutating rows after a cutoff may change labels
    # whose horizon reaches the mutation — but labels fully resolved before
    # the cutoff are invariant.
    df = make_df(30)
    cutoff = 20
    baseline = generate_labels(
        df,
        horizon=HORIZON,
        threshold_up=THRESH,
        threshold_down=THRESH,
        price_column="adj_close",
    ).frame
    mutated = df.copy()
    mutated.loc[mutated.index[cutoff:], ["close", "adj_close"]] *= 1.5
    after = generate_labels(
        mutated,
        horizon=HORIZON,
        threshold_up=THRESH,
        threshold_down=THRESH,
        price_column="adj_close",
    ).frame
    # Rows <= cutoff - horizon resolved before any mutation.
    pd.testing.assert_series_equal(
        baseline["label"].iloc[: cutoff - HORIZON],
        after["label"].iloc[: cutoff - HORIZON],
        check_names=False,
    )
