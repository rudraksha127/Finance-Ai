"""Unit tests for feature computation — mathematical behavior per family."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from src.features.compute import (
    compute_bollinger_features,
    compute_candle_features,
    compute_features,
    compute_momentum_features,
    compute_price_return_features,
    compute_trend_features,
    compute_volatility_features,
    compute_volume_features,
    compute_volume_price_features,
)
from src.features.registry import FEATURE_COLUMNS


def make_frame(n: int = 80, *, start: str = "2025-01-02") -> pd.DataFrame:
    """Deterministic OHLCV frame with a rising close series."""
    idx = pd.date_range(start, periods=n, freq="B")
    close = 100.0 + np.arange(n, dtype=float) * 0.5
    open_ = close - 0.2
    high = close + 1.0
    low = close - 1.0
    volume = 1_000_000 + np.arange(n, dtype=float) * 1_000
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def test_compute_features_shape_and_order():
    frame = make_frame(120)
    out = compute_features(frame)
    assert out.shape == (120, 52)
    assert list(out.columns) == list(FEATURE_COLUMNS)
    assert (out.dtypes == "float64").all()


def test_compute_rejects_missing_columns():
    frame = make_frame().drop(columns=["volume"])
    with pytest.raises(KeyError):
        compute_features(frame)


def test_compute_rejects_duplicate_index():
    frame = make_frame(5)
    frame = pd.concat([frame, frame.iloc[[0]]])
    with pytest.raises(ValueError):
        compute_features(frame)


def test_price_return_math():
    frame = make_frame()
    out = compute_price_return_features(frame)
    close = frame["close"]
    assert out["returns_1d"].iloc[1] == pytest.approx(
        (close.iloc[1] - close.iloc[0]) / close.iloc[0]
    )
    assert out["returns_5d"].iloc[5] == pytest.approx(
        (close.iloc[5] - close.iloc[0]) / close.iloc[0]
    )
    assert out["returns_20d"].iloc[20] == pytest.approx(
        (close.iloc[20] - close.iloc[0]) / close.iloc[0]
    )
    assert out["log_return_1d"].iloc[1] == pytest.approx(math.log(close.iloc[1] / close.iloc[0]))
    assert out["intraday_return"].iloc[3] == pytest.approx(
        (close.iloc[3] - frame["open"].iloc[3]) / frame["open"].iloc[3]
    )
    assert out["overnight_return"].iloc[3] == pytest.approx(
        (frame["open"].iloc[3] - close.iloc[2]) / close.iloc[2]
    )
    assert out["returns_20d"].iloc[:20].isna().all()  # warm-up


def test_trend_math():
    frame = make_frame()
    out = compute_trend_features(frame)
    close = frame["close"]
    assert out["sma_5"].iloc[9] == pytest.approx(close.iloc[5:10].mean())
    assert out["sma_50"].iloc[60] == pytest.approx(close.iloc[11:61].mean())
    assert out["price_to_sma_20"].iloc[40] == pytest.approx(
        close.iloc[40] / close.iloc[21:41].mean() - 1.0
    )
    expected_ema = close.ewm(span=12, adjust=False).mean()
    assert out["ema_12"].iloc[20] == pytest.approx(expected_ema.iloc[20])
    # First valid row is at index lookback-1 (min_periods == window).
    assert out["sma_5"].iloc[:4].isna().all()
    assert not out["sma_5"].iloc[4:].isna().any()


def test_momentum_math_and_rsi_range():
    frame = make_frame(150)
    out = compute_momentum_features(frame)
    close = frame["close"]
    assert out["roc_5"].iloc[10] == pytest.approx(
        (close.iloc[10] - close.iloc[5]) / close.iloc[5] * 100.0
    )
    assert out["momentum_10"].iloc[12] == pytest.approx(close.iloc[12] - close.iloc[2])
    for column in ("rsi_14", "rsi_7"):
        valid = out[column].dropna()
        assert valid.between(0.0, 100.0).all()
    # A monotonically rising series must show strong RSI (near 100).
    assert out["rsi_14"].iloc[-1] > 80.0


def test_rsi_known_wilder_value():
    # Hand-computed Wilder RSI: series with a single large gain then flat.
    # Zero average loss -> RS = inf -> RSI = 100 (Wilder convention).
    # Needs >= 14 rows for the Wilder warm-up to complete.
    close = pd.Series([10.0, 11.0] + [11.0] * 18)
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / 14.0, adjust=False).mean().iloc[-1]
    avg_loss = loss.ewm(alpha=1 / 14.0, adjust=False).mean().iloc[-1]
    expected = 100.0 if avg_loss == 0.0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    frame = pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
            "volume": 1_000_000.0,
        }
    )
    out = compute_momentum_features(frame)
    assert out["rsi_14"].iloc[-1] == pytest.approx(expected)


def test_volatility_math():
    frame = make_frame(120)
    out = compute_volatility_features(frame)
    returns = frame["close"].pct_change()
    assert out["volatility_20d"].iloc[40] == pytest.approx(returns.iloc[21:41].std())
    assert out["realized_vol_20d"].iloc[40] == pytest.approx(
        returns.iloc[21:41].std() * math.sqrt(252)
    )
    assert out["true_range"].iloc[3] == pytest.approx(
        max(
            frame["high"].iloc[3] - frame["low"].iloc[3],
            abs(frame["high"].iloc[3] - frame["close"].iloc[2]),
            abs(frame["low"].iloc[3] - frame["close"].iloc[2]),
        )
    )
    assert out["volatility_ratio"].iloc[40] == pytest.approx(
        out["volatility_5d"].iloc[40] / out["volatility_20d"].iloc[40]
    )
    assert out["volatility_50d"].iloc[:49].isna().all()


def test_volume_math():
    frame = make_frame(120)
    out = compute_volume_features(frame)
    volume = frame["volume"].astype(float)
    assert out["volume_ratio_5d"].iloc[20] == pytest.approx(
        volume.iloc[20] / volume.iloc[16:21].mean()
    )
    assert out["volume_change_1d"].iloc[5] == pytest.approx(
        (volume.iloc[5] - volume.iloc[4]) / volume.iloc[4]
    )
    assert out["volume_trend_5d"].iloc[30] == pytest.approx(
        volume.iloc[26:31].mean() / volume.iloc[11:31].mean()
    )
    mean20, std20 = volume.rolling(20).mean(), volume.rolling(20).std()
    assert out["volume_zscore_20d"].iloc[30] == pytest.approx(
        (volume.iloc[30] - mean20.iloc[30]) / std20.iloc[30]
    )
    # OBV slope on a constant-volume, rising-price series must be positive.
    assert out["obv_slope_10d"].iloc[-1] > 0.0


def test_volume_price_math():
    frame = make_frame(120)
    out = compute_volume_price_features(frame)
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    volume = frame["volume"].astype(float)
    vwap5 = (typical * volume).rolling(5).sum() / volume.rolling(5).sum()
    assert out["vwap_deviation_5d"].iloc[30] == pytest.approx(
        (frame["close"].iloc[30] - vwap5.iloc[30]) / vwap5.iloc[30]
    )
    assert out["volume_price_trend"].iloc[5] == pytest.approx(
        np.sign(frame["close"].pct_change().iloc[5]) * (volume.iloc[5] / volume.iloc[4])
    )
    assert out["accumulation_distribution"].iloc[5] == pytest.approx(
        (
            (frame["close"].iloc[5] - frame["low"].iloc[5])
            - (frame["high"].iloc[5] - frame["close"].iloc[5])
        )
        / (frame["high"].iloc[5] - frame["low"].iloc[5])
        * volume.iloc[5]
    )


def test_bollinger_math():
    frame = make_frame(150)
    out = compute_bollinger_features(frame)
    close = frame["close"]
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    assert out["bb_upper_20d"].iloc[40] == pytest.approx(sma20.iloc[40] + 2 * std20.iloc[40])
    assert out["bb_lower_20d"].iloc[40] == pytest.approx(sma20.iloc[40] - 2 * std20.iloc[40])
    assert out["bb_position_20d"].iloc[40] == pytest.approx(
        (close.iloc[40] - out["bb_lower_20d"].iloc[40])
        / (out["bb_upper_20d"].iloc[40] - out["bb_lower_20d"].iloc[40])
    )
    assert out["bb_bandwidth_20d"].iloc[40] == pytest.approx(
        (out["bb_upper_20d"].iloc[40] - out["bb_lower_20d"].iloc[40]) / sma20.iloc[40]
    )
    assert out["bb_squeeze_20d"].dropna().isin((0.0, 1.0)).all()
    assert out["high_low_range_20d"].iloc[40] == pytest.approx(
        (frame["high"].iloc[21:41].max() - frame["low"].iloc[21:41].min()) / close.iloc[40]
    )
    # bb_squeeze warm-up: bandwidth needs 20 rows, then a 100-row quantile
    # window -> first valid row at index 118 (rows 19..118).
    assert out["bb_squeeze_20d"].iloc[:118].isna().all()
    assert not out["bb_squeeze_20d"].iloc[118:].isna().any()


def test_candle_math_and_partition():
    frame = make_frame()
    out = compute_candle_features(frame)
    rng = frame["high"] - frame["low"]
    assert out["body_ratio"].iloc[5] == pytest.approx(
        abs(frame["close"].iloc[5] - frame["open"].iloc[5]) / rng.iloc[5]
    )
    assert out["upper_wick_ratio"].iloc[5] == pytest.approx(
        (frame["high"].iloc[5] - max(frame["open"].iloc[5], frame["close"].iloc[5])) / rng.iloc[5]
    )
    assert out["lower_wick_ratio"].iloc[5] == pytest.approx(
        (min(frame["open"].iloc[5], frame["close"].iloc[5]) - frame["low"].iloc[5]) / rng.iloc[5]
    )
    assert out["close_position"].iloc[5] == pytest.approx(
        (frame["close"].iloc[5] - frame["low"].iloc[5]) / rng.iloc[5]
    )
    # Partition property: body + upper wick + lower wick == 1.
    combined = out["body_ratio"] + out["upper_wick_ratio"] + out["lower_wick_ratio"]
    assert combined.dropna().apply(lambda value: value == pytest.approx(1.0)).all()
    assert out["is_bullish"].iloc[5] == 1.0  # close > open in fixture
    assert out["gap_pct"].iloc[5] == pytest.approx(
        (frame["open"].iloc[5] - frame["close"].iloc[4]) / frame["close"].iloc[4]
    )
    assert out["gap_pct"].iloc[0] != out["gap_pct"].iloc[0]  # NaN on first row (shift)


def test_warmup_nan_counts_match_lookback():
    frame = make_frame(150)
    out = compute_features(frame)
    # First valid row is at index lookback-1 (0-indexed).
    assert out["sma_50"].iloc[:49].isna().all() and not out["sma_50"].iloc[49:].isna().any()
    assert out["volatility_50d"].iloc[:49].isna().all()
    assert out["atr_14"].iloc[:13].isna().all()
    assert out["bb_squeeze_20d"].iloc[:99].isna().all()
    # Zero-lookback candle features are valid from the first row.
    assert out["body_ratio"].iloc[0] == out["body_ratio"].iloc[0]  # not NaN


def test_zero_range_candle_guard():
    # Doji candles (high == low) must not produce inf/NaN crashes.
    frame = pd.DataFrame(
        {
            "open": [10.0, 10.0, 10.0],
            "high": [10.0, 10.0, 10.0],
            "low": [10.0, 10.0, 10.0],
            "close": [10.0, 10.0, 10.0],
            "volume": [100.0, 100.0, 100.0],
        },
        index=pd.date_range("2025-01-02", periods=3, freq="B"),
    )
    out = compute_candle_features(frame)
    assert out["body_ratio"].iloc[0] == 0.0
    assert out["close_position"].iloc[0] == 0.0
    assert np.isfinite(out["body_ratio"]).all()
