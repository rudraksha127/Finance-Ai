"""Feature computation — the math for all 52 approved MVP features.

Every family function takes a DataFrame with columns ``open``, ``high``,
``low``, ``close``, ``volume`` (indexed by observation timestamp) and
returns a DataFrame of feature columns. Rules (blueprint sections 2/13):

- **No future data:** every computation uses ``rolling`` / ``ewm`` /
  ``shift`` with default backward-looking semantics; centered windows,
  future fills and future-derived values are never used.
- **No mutation:** source data is only read, never modified.
- **Warm-up:** rows with insufficient lookback history are NaN (never
  filled with future information); the Dataset Builder drops them.
- **Determinism:** same input + same version -> identical output.

Reference: FEATURE_CATALOG.md (formulas), FEATURE_ENGINEERING_BLUEPRINT.md
sections 5-7 (definitions). Implementation notes for ambiguous formulas
are documented in docs/FEATURE_ENGINE_IMPLEMENTATION.md.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.features.registry import FEATURE_COLUMNS

_EPISLON = 1e-12  # guard for zero-range denominators (candle ratios)
_ANNUALIZATION = math.sqrt(252)  # trading days per year (VOL-07)


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Divide two series, mapping zero/absent denominators to NaN."""
    safe = denominator.where(denominator.abs() > _EPISLON)
    return numerator / safe


def _rsi(close: pd.Series, period: int) -> pd.Series:
    """Wilder-smoothed Relative Strength Index (0-100), blueprint section 5.3."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    # Wilder smoothing: ewm with alpha = 1/period, seeded from the first
    # ``period`` observations (min_periods -> NaN during warm-up).
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    # Raw division is intentional: zero average loss -> RS = inf -> RSI = 100
    # (Wilder convention); zero gain AND zero loss -> 0/0 -> NaN (flat series).
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """True Range (VOL-06): max of the three standard definitions."""
    previous_close = close.shift(1)
    return pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume (cumulative, blueprint section 5.5)."""
    direction = np.sign(close.diff()).fillna(0.0)
    return (direction * volume).cumsum()


def _rolling_slope(values: pd.Series, window: int) -> pd.Series:
    """Least-squares slope of ``values`` over a trailing ``window``.

    Vectorized via the closed form slope = cov(x, y) / var(x) with
    x = 0..window-1 fixed, using rolling sums (blueprint OBV slope).
    """
    x = np.arange(window, dtype=float)
    x_mean = x.mean()
    denominator = float(((x - x_mean) ** 2).sum())
    rolling_sum_y = values.rolling(window).sum()
    # rolling sum of y*x requires positional weighting; compute via the
    # identity sum(x*y) = sum over window of position*y using shift-stacking.
    weighted = pd.concat([values.shift(i) * (window - 1 - i) for i in range(window)], axis=1).sum(
        axis=1
    )
    numerator = weighted - x_mean * rolling_sum_y
    return numerator / denominator


# ---------------------------------------------------------------------------
# Family functions (each independently testable)
# ---------------------------------------------------------------------------
def compute_price_return_features(df: pd.DataFrame) -> pd.DataFrame:
    """RET-01..RET-08: returns, log returns, intraday/overnight moves."""
    close = df["close"]
    out = pd.DataFrame(index=df.index)
    out["returns_1d"] = close.pct_change(1)
    out["returns_3d"] = close.pct_change(3)
    out["returns_5d"] = close.pct_change(5)
    out["returns_10d"] = close.pct_change(10)
    out["returns_20d"] = close.pct_change(20)
    out["log_return_1d"] = np.log(close / close.shift(1))
    out["intraday_return"] = _safe_divide(close - df["open"], df["open"])
    out["overnight_return"] = _safe_divide(df["open"] - close.shift(1), close.shift(1))
    return out


def compute_trend_features(df: pd.DataFrame) -> pd.DataFrame:
    """TRD-01..TRD-08: SMAs, price-to-SMA distance, EMAs."""
    close = df["close"]
    out = pd.DataFrame(index=df.index)
    out["sma_5"] = close.rolling(5).mean()
    out["sma_10"] = close.rolling(10).mean()
    out["sma_20"] = close.rolling(20).mean()
    out["sma_50"] = close.rolling(50).mean()
    out["price_to_sma_20"] = _safe_divide(close, out["sma_20"]) - 1.0
    out["price_to_sma_50"] = _safe_divide(close, out["sma_50"]) - 1.0
    out["ema_12"] = close.ewm(span=12, adjust=False, min_periods=12).mean()
    out["ema_26"] = close.ewm(span=26, adjust=False, min_periods=26).mean()
    return out


def compute_momentum_features(df: pd.DataFrame) -> pd.DataFrame:
    """MOM-01..MOM-06: RSI, ROC, absolute momentum."""
    close = df["close"]
    out = pd.DataFrame(index=df.index)
    out["rsi_14"] = _rsi(close, 14)
    out["rsi_7"] = _rsi(close, 7)
    out["roc_5"] = close.pct_change(5) * 100.0
    out["roc_10"] = close.pct_change(10) * 100.0
    out["roc_20"] = close.pct_change(20) * 100.0
    out["momentum_10"] = close - close.shift(10)
    return out


def compute_volatility_features(df: pd.DataFrame) -> pd.DataFrame:
    """VOL-01..VOL-08: rolling volatility, ATR, true range, ratios."""
    close = df["close"]
    returns = close.pct_change()
    out = pd.DataFrame(index=df.index)
    out["volatility_5d"] = returns.rolling(5).std()
    out["volatility_10d"] = returns.rolling(10).std()
    out["volatility_20d"] = returns.rolling(20).std()
    out["volatility_50d"] = returns.rolling(50).std()
    tr = _true_range(df["high"], df["low"], close)
    out["atr_14"] = tr.ewm(alpha=1.0 / 14, adjust=False, min_periods=14).mean()
    out["true_range"] = tr
    out["realized_vol_20d"] = returns.rolling(20).std() * _ANNUALIZATION
    out["volatility_ratio"] = _safe_divide(out["volatility_5d"], out["volatility_20d"])
    return out


def compute_volume_features(df: pd.DataFrame) -> pd.DataFrame:
    """VLM-01..VLM-06: volume ratios, change, trend, z-score, OBV slope."""
    volume = df["volume"].astype(float)
    out = pd.DataFrame(index=df.index)
    out["volume_ratio_5d"] = _safe_divide(volume, volume.rolling(5).mean())
    out["volume_ratio_20d"] = _safe_divide(volume, volume.rolling(20).mean())
    out["volume_change_1d"] = _safe_divide(volume - volume.shift(1), volume.shift(1))
    out["volume_trend_5d"] = _safe_divide(volume.rolling(5).mean(), volume.rolling(20).mean())
    vol_mean_20 = volume.rolling(20).mean()
    vol_std_20 = volume.rolling(20).std()
    out["volume_zscore_20d"] = _safe_divide(volume - vol_mean_20, vol_std_20)
    obv = _obv(df["close"], volume)
    out["obv_slope_10d"] = _rolling_slope(obv, 10)
    return out


def compute_volume_price_features(df: pd.DataFrame) -> pd.DataFrame:
    """VP-01..VP-04: VWAP deviation, volume-confirmed move, A/D line."""
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    volume = df["volume"].astype(float)
    out = pd.DataFrame(index=df.index)
    for window, name in ((5, "vwap_deviation_5d"), (20, "vwap_deviation_20d")):
        vwap = (typical * volume).rolling(window).sum() / volume.rolling(window).sum()
        out[name] = _safe_divide(df["close"] - vwap, vwap)
    # VP-03: sign(1-day return) x 1-day volume ratio (lookback 1).
    returns_1d = df["close"].pct_change(1)
    volume_ratio_1d = _safe_divide(volume, volume.shift(1))
    out["volume_price_trend"] = np.sign(returns_1d) * volume_ratio_1d
    # VP-04: accumulation/distribution money flow (zero range -> 0).
    range_hl = df["high"] - df["low"]
    money_flow = _safe_divide(
        (df["close"] - df["low"]) - (df["high"] - df["close"]), range_hl
    ).fillna(0.0)
    out["accumulation_distribution"] = money_flow * volume
    return out


def compute_bollinger_features(df: pd.DataFrame) -> pd.DataFrame:
    """BB-01..BB-06: Bollinger bands, position, bandwidth, squeeze, range."""
    close = df["close"]
    out = pd.DataFrame(index=df.index)
    sma_20 = close.rolling(20).mean()
    std_20 = close.rolling(20).std()
    out["bb_upper_20d"] = sma_20 + 2.0 * std_20
    out["bb_lower_20d"] = sma_20 - 2.0 * std_20
    bandwidth = _safe_divide(out["bb_upper_20d"] - out["bb_lower_20d"], sma_20)
    out["bb_position_20d"] = _safe_divide(
        close - out["bb_lower_20d"], out["bb_upper_20d"] - out["bb_lower_20d"]
    )
    out["bb_bandwidth_20d"] = bandwidth
    # BB-05 squeeze: 1 when bandwidth < its 20th percentile over 100 days.
    # NaN during the 100-day warm-up is preserved (never silently 0).
    squeeze_threshold = bandwidth.rolling(100).quantile(0.2)
    squeeze = (bandwidth < squeeze_threshold).astype(float)
    out["bb_squeeze_20d"] = squeeze.where(squeeze_threshold.notna())
    out["high_low_range_20d"] = _safe_divide(
        df["high"].rolling(20).max() - df["low"].rolling(20).min(), close
    )
    return out


def compute_candle_features(df: pd.DataFrame) -> pd.DataFrame:
    """CS-01..CS-06: body/wick ratios, close position, direction, gap."""
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    rng = (h - l).clip(lower=_EPISLON)
    out = pd.DataFrame(index=df.index)
    out["body_ratio"] = (c - o).abs() / rng
    out["upper_wick_ratio"] = (h - pd.concat([o, c], axis=1).max(axis=1)) / rng
    out["lower_wick_ratio"] = (pd.concat([o, c], axis=1).min(axis=1) - l) / rng
    out["close_position"] = (c - l) / rng
    out["is_bullish"] = (c > o).astype(float)
    out["gap_pct"] = _safe_divide(o - c.shift(1), c.shift(1))
    return out


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all 52 features for a cleaned OHLCV frame.

    Args:
        df: cleaned market data with columns ``open``, ``high``, ``low``,
            ``close``, ``volume`` (``adj_close`` optional) and a timestamp
            index. The frame must be sorted ascending by timestamp and
            free of duplicate timestamps.

    Returns:
        A DataFrame with the same index and exactly the 52 feature
        columns in canonical registry order (:data:`FEATURE_COLUMNS`),
        all float64. Warm-up rows carry NaN.

    Raises:
        KeyError: if any required source column is missing.
        ValueError: if the index is not monotonic or contains duplicates.
    """
    required = ("open", "high", "low", "close", "volume")
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise KeyError(f"missing required source columns: {missing}")
    if not df.index.is_monotonic_increasing:
        raise ValueError("feature computation requires ascending timestamps")
    if df.index.has_duplicates:
        raise ValueError("feature computation requires unique timestamps")

    families = (
        compute_price_return_features(df),
        compute_trend_features(df),
        compute_momentum_features(df),
        compute_volatility_features(df),
        compute_volume_features(df),
        compute_volume_price_features(df),
        compute_bollinger_features(df),
        compute_candle_features(df),
    )
    computed = pd.concat(families, axis=1)
    # Canonical column order + uniform dtype (registry contract).
    computed = computed.reindex(columns=list(FEATURE_COLUMNS)).astype("float64")
    return computed
