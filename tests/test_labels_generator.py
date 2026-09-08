"""Unit tests for the label generator — return math, classification, horizon."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.labels.generator import (
    INVALID_FUTURE_WINDOW,
    INVALID_PRICE,
    VALID,
    generate_labels,
)


def price_frame(prices: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2025-01-02", periods=len(prices), freq="B")
    return pd.DataFrame({"close": prices, "adj_close": prices}, index=idx)


def test_future_return_math():
    df = price_frame([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0])
    out = generate_labels(
        df, horizon=3, threshold_up=0.01, threshold_down=0.01, price_column="adj_close"
    ).frame
    # Row 0: (103 - 100) / 100 = 3%
    assert out["future_return"].iloc[0] == pytest.approx(0.03)
    # Row 2: (105 - 102) / 102
    assert out["future_return"].iloc[2] == pytest.approx(3.0 / 102.0)
    assert out["future_price"].iloc[0] == pytest.approx(103.0)


def test_classification_thresholds():
    # Future returns: +5%, -5%, 0%, +0.5% (HOLD), -0.5% (HOLD).
    prices = [100.0, 100.0, 100.0, 100.0, 100.0, 105.0, 95.0, 100.0, 100.5, 99.5, 100.0, 100.0]
    out = generate_labels(
        df=price_frame(prices),
        horizon=5,
        threshold_up=0.01,
        threshold_down=0.01,
        price_column="adj_close",
    ).frame
    assert out["label"].iloc[0] == "UP"  # +5%
    assert out["label"].iloc[1] == "DOWN"  # -5%
    assert out["label"].iloc[2] == "HOLD"  # 0%
    assert out["label"].iloc[3] == "HOLD"  # +0.5% < 1%
    assert out["label"].iloc[4] == "HOLD"  # -0.5% > -1%
    # Just under the threshold is HOLD (strict > / <; +0.99% / -0.99%).
    near = price_frame([100.0, 100.99, 99.99, 100.0])
    near_out = generate_labels(
        df=near, horizon=1, threshold_up=0.01, threshold_down=0.01, price_column="adj_close"
    ).frame
    assert near_out["label"].iloc[0] == "HOLD"  # +0.99% < +1%
    assert near_out["label"].iloc[1] == "HOLD"  # -0.99% > -1%


def test_end_of_dataset_rows_invalid():
    df = price_frame([100.0] * 8)
    out = generate_labels(
        df, horizon=5, threshold_up=0.01, threshold_down=0.01, price_column="adj_close"
    ).frame
    assert (out["status"].iloc[:3] == VALID).all()
    assert (out["status"].iloc[3:] == INVALID_FUTURE_WINDOW).all()
    assert out["label"].iloc[5:].isna().all()


def test_invalid_current_price():
    # Row 1 and 2 have invalid current prices (0 / negative) -> INVALID_PRICE.
    # Row 0 has a valid current price but its future (row 1) is invalid ->
    # INVALID_FUTURE_WINDOW. Row 4's future (row 5) is valid -> VALID.
    df = price_frame([100.0, 0.0, -5.0, 100.0, 100.0, 100.0, 100.0])
    df.loc[df.index[1], "adj_close"] = 0.0
    df.loc[df.index[2], "adj_close"] = -5.0
    out = generate_labels(
        df, horizon=1, threshold_up=0.01, threshold_down=0.01, price_column="adj_close"
    ).frame
    assert out["status"].iloc[0] == INVALID_FUTURE_WINDOW
    assert out["status"].iloc[1] == INVALID_PRICE
    assert out["status"].iloc[2] == INVALID_PRICE
    assert out["label"].iloc[1] != out["label"].iloc[1]  # NaN
    assert out["label"].iloc[2] != out["label"].iloc[2]  # NaN
    assert out["status"].iloc[4] == VALID


def test_distribution_counts():
    prices = [100.0, 100.0, 100.0, 100.0, 100.0, 105.0, 95.0, 100.0, 100.0, 100.0, 100.0, 100.0]
    result = generate_labels(
        df=price_frame(prices),
        horizon=5,
        threshold_up=0.01,
        threshold_down=0.01,
        price_column="adj_close",
    )
    dist = result.distribution
    # Rows 0..6 are valid: +5% UP, -5% DOWN, 0/0/0 HOLD, -4.76% DOWN, +5.26% UP.
    assert dist.total_rows == 12
    assert dist.valid_rows == 7
    assert dist.up_count == 2
    assert dist.down_count == 2
    assert dist.hold_count == 3
    assert dist.invalid_count == 5
    assert dist.invalid_future_window == 5
    assert dist.invalid_price == 0
    assert dist.up_pct == pytest.approx(2 / 7 * 100, abs=0.01)
    assert dist.down_pct == pytest.approx(2 / 7 * 100, abs=0.01)
    assert dist.hold_pct == pytest.approx(3 / 7 * 100, abs=0.01)
    assert dist.up_pct + dist.down_pct + dist.hold_pct == pytest.approx(100.0)


def test_input_never_mutated():
    df = price_frame([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0])
    snapshot = df.copy(deep=True)
    generate_labels(df, horizon=5, threshold_up=0.01, threshold_down=0.01, price_column="adj_close")
    pd.testing.assert_frame_equal(df, snapshot)


def test_missing_price_column_rejected():
    df = price_frame([100.0] * 6).drop(columns=["adj_close"])
    with pytest.raises(KeyError):
        generate_labels(
            df, horizon=1, threshold_up=0.01, threshold_down=0.01, price_column="adj_close"
        )


def test_duplicate_and_unsorted_index_rejected():
    df = price_frame([100.0] * 6)
    dup = pd.concat([df, df.iloc[[0]]])
    with pytest.raises(ValueError):
        generate_labels(
            dup, horizon=1, threshold_up=0.01, threshold_down=0.01, price_column="adj_close"
        )
    unsorted = df.sort_index(ascending=False)
    with pytest.raises(ValueError):
        generate_labels(
            unsorted, horizon=1, threshold_up=0.01, threshold_down=0.01, price_column="adj_close"
        )


def test_invalid_horizon_rejected():
    df = price_frame([100.0] * 6)
    with pytest.raises(ValueError):
        generate_labels(
            df, horizon=0, threshold_up=0.01, threshold_down=0.01, price_column="adj_close"
        )


def test_missing_future_candle_never_fabricated():
    # A NaN gap in the middle: rows whose future lands on the gap are invalid.
    prices = [100.0] * 8
    df = price_frame(prices)
    df.loc[df.index[4], "adj_close"] = np.nan
    out = generate_labels(
        df, horizon=3, threshold_up=0.01, threshold_down=0.01, price_column="adj_close"
    ).frame
    # Row 1's future is row 4 (NaN) -> invalid future window.
    assert out["status"].iloc[1] == INVALID_FUTURE_WINDOW
    assert out["label"].iloc[1] != out["label"].iloc[1]
    # Rows whose future is valid stay valid.
    assert out["status"].iloc[0] == VALID
