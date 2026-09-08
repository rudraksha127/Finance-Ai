# FEATURE CATALOG — Finance AI MVP

> Complete specification table for all 52 MVP features.
> Reference document for implementation and validation.

---

## Feature Specification Table

| # | Feature ID | Name | Category | Formula | Inputs | Lookback | Normalization | Leakage Risk | Description |
|---|-----------|------|----------|---------|--------|----------|---------------|--------------|-------------|
| 1 | RET-01 | returns_1d | Price/Return | (close_t - close_{t-1}) / close_{t-1} | close | 1 | None | None | Daily percentage return |
| 2 | RET-02 | returns_3d | Price/Return | (close_t - close_{t-3}) / close_{t-3} | close | 3 | None | None | 3-day percentage return |
| 3 | RET-03 | returns_5d | Price/Return | (close_t - close_{t-5}) / close_{t-5} | close | 5 | None | None | 5-day percentage return |
| 4 | RET-04 | returns_10d | Price/Return | (close_t - close_{t-10}) / close_{t-10} | close | 10 | None | None | 10-day percentage return |
| 5 | RET-05 | returns_20d | Price/Return | (close_t - close_{t-20}) / close_{t-20} | close | 20 | None | None | 20-day percentage return |
| 6 | RET-06 | log_return_1d | Price/Return | ln(close_t / close_{t-1}) | close | 1 | None | None | Daily log return (symmetric) |
| 7 | RET-07 | intraday_return | Price/Return | (close_t - open_t) / open_t | open, close | 0 | None | None | Intra-candle return |
| 8 | RET-08 | overnight_return | Price/Return | (open_t - close_{t-1}) / close_{t-1} | open, close | 1 | None | None | Gap/overnight movement |
| 9 | TRD-01 | sma_5 | Trend | mean(close, 5) | close | 5 | None | None | 5-day simple moving average |
| 10 | TRD-02 | sma_10 | Trend | mean(close, 10) | close | 10 | None | None | 10-day simple moving average |
| 11 | TRD-03 | sma_20 | Trend | mean(close, 20) | close | 20 | None | None | 20-day simple moving average |
| 12 | TRD-04 | sma_50 | Trend | mean(close, 50) | close | 50 | None | None | 50-day simple moving average |
| 13 | TRD-05 | price_to_sma_20 | Trend | close / sma_20 - 1 | close | 20 | None | None | Distance from 20-day SMA |
| 14 | TRD-06 | price_to_sma_50 | Trend | close / sma_50 - 1 | close | 50 | None | None | Distance from 50-day SMA |
| 15 | TRD-07 | ema_12 | Trend | ewm(close, span=12) | close | 12 | None | None | 12-day exponential MA |
| 16 | TRD-08 | ema_26 | Trend | ewm(close, span=26) | close | 26 | None | None | 26-day exponential MA |
| 17 | MOM-01 | rsi_14 | Momentum | RSI(close, 14) | close | 14 | None | None | 14-period Relative Strength Index |
| 18 | MOM-02 | rsi_7 | Momentum | RSI(close, 7) | close | 7 | None | None | 7-period Relative Strength Index |
| 19 | MOM-03 | roc_5 | Momentum | (close_t - close_{t-5}) / close_{t-5} × 100 | close | 5 | None | None | 5-day rate of change |
| 20 | MOM-04 | roc_10 | Momentum | (close_t - close_{t-10}) / close_{t-10} × 100 | close | 10 | None | None | 10-day rate of change |
| 21 | MOM-05 | roc_20 | Momentum | (close_t - close_{t-20}) / close_{t-20} × 100 | close | 20 | None | None | 20-day rate of change |
| 22 | MOM-06 | momentum_10 | Momentum | close_t - close_{t-10} | close | 10 | None | None | 10-day absolute momentum |
| 23 | VOL-01 | volatility_5d | Volatility | std(returns, 5) | close | 5 | None | None | 5-day rolling volatility |
| 24 | VOL-02 | volatility_10d | Volatility | std(returns, 10) | close | 10 | None | None | 10-day rolling volatility |
| 25 | VOL-03 | volatility_20d | Volatility | std(returns, 20) | close | 20 | None | None | 20-day rolling volatility |
| 26 | VOL-04 | volatility_50d | Volatility | std(returns, 50) | close | 50 | None | None | 50-day rolling volatility |
| 27 | VOL-05 | atr_14 | Volatility | EMA(TR, 14) | high, low, close | 14 | None | None | 14-day Average True Range |
| 28 | VOL-06 | true_range | Volatility | max(high-low, abs(high-prev_close), abs(low-prev_close)) | high, low, close | 1 | None | None | True Range (intra-candle) |
| 29 | VOL-07 | realized_vol_20d | Volatility | std(returns, 20) × sqrt(252) | close | 20 | None | None | Annualized 20-day volatility |
| 30 | VOL-08 | volatility_ratio | Volatility | volatility_5d / volatility_20d | close | 20 | None | None | Volatility expansion/contraction |
| 31 | VLM-01 | volume_ratio_5d | Volume | volume / sma(volume, 5) | volume | 5 | None | None | 5-day volume surge |
| 32 | VLM-02 | volume_ratio_20d | Volume | volume / sma(volume, 20) | volume | 20 | None | None | 20-day volume context |
| 33 | VLM-03 | volume_change_1d | Volume | (volume_t - volume_{t-1}) / volume_{t-1} | volume | 1 | None | None | Daily volume change |
| 34 | VLM-04 | volume_trend_5d | Volume | sma(volume, 5) / sma(volume, 20) | volume | 20 | None | None | Volume trend (short vs long) |
| 35 | VLM-05 | volume_zscore_20d | Volume | (volume - mean(volume,20)) / std(volume,20) | volume | 20 | None | None | Volume z-score (anomaly) |
| 36 | VLM-06 | obv_slope_10d | Volume | slope(OBV, 10) | close, volume | 10 | None | None | On-Balance Volume trend |
| 37 | VP-01 | vwap_deviation_5d | Volume-Price | (close - vwap_5d) / vwap_5d | high, low, close, volume | 5 | None | None | Price vs 5-day VWAP |
| 38 | VP-02 | vwap_deviation_20d | Volume-Price | (close - vwap_20d) / vwap_20d | high, low, close, volume | 20 | None | None | Price vs 20-day VWAP |
| 39 | VP-03 | volume_price_trend | Volume-Price | sign(returns) × volume_ratio | close, volume | 1 | None | None | Volume-confirmed price move |
| 40 | VP-04 | accumulation_distribution | Volume-Price | ((close - low) - (high - close)) / (high - low) × volume | high, low, close, volume | 0 | None | None | Money flow indicator |
| 41 | BB-01 | bb_upper_20d | Bollinger | sma(close, 20) + 2 × std(close, 20) | close | 20 | None | None | Upper Bollinger Band |
| 42 | BB-02 | bb_lower_20d | Bollinger | sma(close, 20) - 2 × std(close, 20) | close | 20 | None | None | Lower Bollinger Band |
| 43 | BB-03 | bb_position_20d | Bollinger | (close - bb_lower) / (bb_upper - bb_lower) | close | 20 | None | None | Position within Bollinger Bands |
| 44 | BB-04 | bb_bandwidth_20d | Bollinger | (bb_upper - bb_lower) / sma(close, 20) | close | 20 | None | None | Bollinger Band width |
| 45 | BB-05 | bb_squeeze_20d | Bollinger | bandwidth < percentile(bandwidth, 100) | close | 100 | None | None | Bollinger squeeze detection |
| 46 | BB-06 | high_low_range_20d | Bollinger | (max(high,20) - min(low,20)) / close | high, low, close | 20 | None | None | 20-day price range |
| 47 | CS-01 | body_ratio | Candle | abs(close - open) / (high - low) | open, high, low, close | 0 | None | None | Candle body size relative to range |
| 48 | CS-02 | upper_wick_ratio | Candle | (high - max(open, close)) / (high - low) | open, high, low, close | 0 | None | None | Upper shadow ratio |
| 49 | CS-03 | lower_wick_ratio | Candle | (min(open, close) - low) / (high - low) | open, high, low, close | 0 | None | None | Lower shadow ratio |
| 50 | CS-04 | close_position | Candle | (close - low) / (high - low) | high, low, close | 0 | None | None | Close position within range |
| 51 | CS-05 | is_bullish | Candle | 1 if close > open else 0 | open, close | 0 | None | None | Bullish candle flag |
| 52 | CS-06 | gap_pct | Candle | (open - prev_close) / prev_close | open, close | 1 | None | None | Gap from previous close |

---

## Feature Summary by Category

| Category | Count | Lookback Range | Key Features |
|----------|-------|----------------|--------------|
| Price/Return | 8 | 0-20 | returns_1d, returns_5d, log_return_1d |
| Trend | 8 | 5-50 | sma_20, sma_50, price_to_sma_20 |
| Momentum | 6 | 5-20 | rsi_14, roc_5, momentum_10 |
| Volatility | 8 | 1-50 | volatility_20d, atr_14, realized_vol_20d |
| Volume | 6 | 1-20 | volume_ratio_5d, volume_zscore_20d |
| Volume-Price | 4 | 0-20 | vwap_deviation_20d, accumulation_distribution |
| Bollinger | 6 | 20-100 | bb_position_20d, bb_squeeze_20d |
| Candle | 6 | 0-1 | body_ratio, close_position, gap_pct |
| **Total** | **52** | **0-100** | |

---

## Feature Dependencies

```
Close Price
├── returns_1d (RET-01)
├── returns_3d (RET-02)
├── returns_5d (RET-03)
├── returns_10d (RET-04)
├── returns_20d (RET-05)
├── log_return_1d (RET-06)
├── sma_5 (TRD-01)
├── sma_10 (TRD-02)
├── sma_20 (TRD-03)
├── sma_50 (TRD-04)
├── price_to_sma_20 (TRD-05)
├── price_to_sma_50 (TRD-06)
├── ema_12 (TRD-07)
├── ema_26 (TRD-08)
├── rsi_14 (MOM-01)
├── rsi_7 (MOM-02)
├── roc_5 (MOM-03)
├── roc_10 (MOM-04)
├── roc_20 (MOM-05)
├── momentum_10 (MOM-06)
├── volatility_5d (VOL-01)
├── volatility_10d (VOL-02)
├── volatility_20d (VOL-03)
├── volatility_50d (VOL-04)
├── realized_vol_20d (VOL-07)
├── volatility_ratio (VOL-08)
├── bb_upper_20d (BB-01)
├── bb_lower_20d (BB-02)
├── bb_position_20d (BB-03)
├── bb_bandwidth_20d (BB-04)
├── bb_squeeze_20d (BB-05)
├── high_low_range_20d (BB-06)
├── overnight_return (RET-08)
└── gap_pct (CS-06)

Open + High + Low + Close
├── intraday_return (RET-07)
├── atr_14 (VOL-05)
├── true_range (VOL-06)
├── vwap_deviation_5d (VP-01)
├── vwap_deviation_20d (VP-02)
├── accumulation_distribution (VP-04)
├── body_ratio (CS-01)
├── upper_wick_ratio (CS-02)
├── lower_wick_ratio (CS-03)
├── close_position (CS-04)
└── is_bullish (CS-05)

Volume
├── volume_ratio_5d (VLM-01)
├── volume_ratio_20d (VLM-02)
├── volume_change_1d (VLM-03)
├── volume_trend_5d (VLM-04)
├── volume_zscore_20d (VLM-05)
├── obv_slope_10d (VLM-06)
├── volume_price_trend (VP-03)
└── accumulation_distribution (VP-04)
```

---

## Feature Computation Order

1. **Base prices:** open, high, low, close, volume
2. **Returns:** RET-01 to RET-08
3. **Trend:** TRD-01 to TRD-08
4. **Momentum:** MOM-01 to MOM-06
5. **Volatility:** VOL-01 to VOL-08
6. **Volume:** VLM-01 to VLM-06
7. **Volume-Price:** VP-01 to VP-04
8. **Bollinger:** BB-01 to BB-06
9. **Candle:** CS-01 to CS-06
