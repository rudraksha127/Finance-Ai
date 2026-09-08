# LABEL GENERATION BLUEPRINT — Finance AI MVP

> Complete target/label generation framework design for the Finance AI platform.
> Defines exactly what the system learns to predict, how labels are generated,
> and how to prevent future information leakage.

---

## Table of Contents

1. [Primary Objective](#1-primary-objective)
2. [Core Principle](#2-core-principle)
3. [MVP Prediction Problem](#3-mvp-prediction-problem)
4. [Direction Classification Design](#4-direction-classification-design)
5. [Prediction Horizon](#5-prediction-horizon)
6. [Future Return Label](#6-future-return-label)
7. [HOLD Class Design](#7-hold-class-design)
8. [Multi-Target Possibility](#8-multi-target-possibility)
9. [Label Timing](#9-label-timing)
10. [Look-Ahead Bias Prevention](#10-look-ahead-bias-prevention)
11. [Label Generation Algorithm](#11-label-generation-algorithm)
12. [Invalid / Edge Cases](#12-invalid--edge-cases)
13. [Overlapping Labels](#13-overlapping-labels)
14. [Class Balance](#14-class-balance)
15. [Target Distribution Analysis](#15-target-distribution-analysis)
16. [Transaction Cost Awareness](#16-transaction-cost-awareness)
17. [Label Versioning](#17-label-versioning)
18. [Label Metadata](#18-label-metadata)
19. [Research Experiments](#19-research-experiments)
20. [Recommended MVP Label](#20-recommended-mvp-label)
21. [Future Extensions](#21-future-extensions)
22. [Acceptance Criteria](#22-acceptance-criteria)
23. [Consistency Check](#23-consistency-check)
24. [Deliverables](#24-deliverables)
25. [Stop Condition](#25-stop-condition)

---

## 1. Primary Objective

Define exactly what the Finance AI MVP will learn to predict.

**Requirements:**
- Deterministic — same input → same label
- Reproducible — versioned and logged
- Timestamp-aware — aligned with features
- Configurable — thresholds, horizons adjustable
- Time-series safe — no future information leakage
- Suitable for historical backtesting
- Extensible for future multi-target models

---

## 2. Core Principle

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       CORE SEPARATION PRINCIPLE                          │
│                                                                          │
│  FEATURES describe the market state available at time T.                 │
│                                                                          │
│  LABEL represents an outcome that happens AFTER time T.                  │
│                                                                          │
│  Therefore:                                                              │
│                                                                          │
│    Features(T) may use information ≤ T.                                  │
│                                                                          │
│    Label(T) may use information > T.                                     │
│                                                                          │
│  The future outcome must NEVER be allowed to flow back into              │
│  feature construction or training inputs.                                │
│                                                                          │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                          │
│  Timeline:                                                               │
│                                                                          │
│    ────────────────┼───────────────────────┼───────────────────────     │
│                    T                       T+H                           │
│                    │                       │                             │
│    Features use:   │←── Past data ────────│                             │
│                    │                       │                             │
│    Label uses:     │                       │──── Future data ────→      │
│                    │                       │                             │
│    Training row:   X(T) ─────────────────→ Y(T+H)                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. MVP Prediction Problem

### 3.1 Candidate Objectives

| Objective | Description | Business Usefulness | Data Requirements | Class Balance | Robustness | Interpretability | Complexity | Overfitting Risk |
|-----------|-------------|--------------------|--------------------|---------------|------------|------------------|------------|-----------------|
| **A. Direction Classification** | Predict UP/DOWN/HOLD | High — trading signals | Low — OHLCV only | Configurable | High | High | Low | Low |
| **B. Future Return Regression** | Predict exact return | Medium — position sizing | Low — OHLCV only | N/A (continuous) | Medium | Medium | Medium | Medium |
| **C. Volatility Prediction** | Predict future volatility | Medium — risk management | Low — OHLCV only | N/A (continuous) | Medium | Medium | Medium | Medium |
| **D. Risk/Drawdown Prediction** | Predict max drawdown | Low — too sparse | Medium — needs history | N/A (continuous) | Low | Low | High | High |

### 3.2 Selection Analysis

**A. Direction Classification (SELECTED)**
- ✅ Most directly useful for trading signals
- ✅ Simple to interpret and evaluate
- ✅ Class balance is controllable via thresholds
- ✅ Compatible with walk-forward backtesting
- ✅ Low complexity, low overfitting risk
- ✅ Matches PRD requirements (UP/DOWN/HOLD)

**B. Future Return Regression**
- ⚠️ Harder to interpret (exact return vs direction)
- ⚠️ Regression targets are noisy
- ⚠️ Requires more data for stable predictions
- ❌ Less useful for simple trading rules

**C. Volatility Prediction**
- ⚠️ Useful but secondary concern
- ⚠️ Requires longer history for stable estimates
- ❌ Not the primary trading signal

**D. Risk/Drawdown Prediction**
- ❌ Very sparse signal
- ❌ Hard to evaluate
- ❌ High complexity

### 3.3 Selection Decision

**PRIMARY TARGET: Direction Classification (UP/DOWN/HOLD)**

**SECONDARY TARGET: None for MVP**

Rationale: Direction classification is the simplest, most interpretable, and most directly useful target for the MVP. Regression targets can be added later as extensions.

---

## 4. Direction Classification Design

### 4.1 Class Definitions

| Class | Definition | Label Value |
|-------|-----------|-------------|
| **UP** | Future return exceeds positive threshold | `"UP"` |
| **DOWN** | Future return exceeds negative threshold (in magnitude) | `"DOWN"` |
| **HOLD** | Future return is within thresholds | `"HOLD"` |

### 4.2 Label Generation Rule

```
future_return = (close_{t+H} - close_t) / close_t

if future_return > threshold_up:
    label = "UP"
elif future_return < -threshold_down:
    label = "DOWN"
else:
    label = "HOLD"
```

### 4.3 Threshold Considerations

| Factor | Impact | Recommendation |
|--------|--------|----------------|
| **Instrument volatility** | High-vol stocks need wider thresholds | Use adaptive thresholds per ticker |
| **Trading costs** | Threshold must exceed round-trip costs | Minimum 2× transaction costs |
| **Spread/slippage** | Reduces effective return | Add 5-10 bps to threshold |
| **Prediction horizon** | Longer horizon → wider natural range | Scale threshold with horizon |
| **Market regime** | Bull markets → more UP, bear → more DOWN | Use regime-agnostic thresholds |
| **Class balance** | Too narrow → mostly HOLD | Monitor and adjust |

### 4.4 MVP Threshold Strategy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       MVP THRESHOLD STRATEGY                             │
│                                                                          │
│  Fixed thresholds (not adaptive for MVP):                                │
│                                                                          │
│    threshold_up = 1.0%  (0.01)                                          │
│    threshold_down = 1.0%  (0.01)                                        │
│                                                                          │
│  Justification:                                                          │
│    - Simple and interpretable                                            │
│    - 1% exceeds typical transaction costs (10 bps × 2 = 20 bps)         │
│    - 5-day horizon: 1% is a reasonable move                              │
│    - Produces roughly balanced classes                                   │
│                                                                          │
│  Configuration:                                                          │
│    dataset:                                                              │
│      label_type: classification                                         │
│      label_window: 5                                                    │
│      thresholds:                                                        │
│        up: 0.01                                                         │
│        down: 0.01                                                       │
│                                                                          │
│  Future: Adaptive thresholds per ticker based on rolling volatility     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Prediction Horizon

### 5.1 Candidate Horizons

| Horizon | Description | Data Requirements | Signal Stability | Noise Level | Execution Realism | Selection |
|---------|-------------|-------------------|------------------|-------------|-------------------|-----------|
| 5 minutes | Intraday micro | Tick data (not available) | Very low | Very high | Not realistic for MVP | ❌ |
| 15 minutes | Intraday short | Minute data (not available) | Low | High | Not realistic for MVP | ❌ |
| 30 minutes | Intraday medium | Minute data (not available) | Low | High | Not realistic for MVP | ❌ |
| 60 minutes | Intraday long | Minute data (not available) | Medium | Medium-High | Not realistic for MVP | ❌ |
| 1 trading day | Daily | Daily OHLCV (available) | Medium | Medium | Realistic | ⚠️ |
| 5 trading days | Weekly | Daily OHLCV (available) | High | Low | Realistic | ✅ |
| 20 trading days | Monthly | Daily OHLCV (available) | Very high | Very low | Realistic | ⚠️ |

### 5.2 Horizon Selection

**MVP HORIZON: 5 trading days (1 week)**

**Justification:**
- ✅ Matches daily OHLCV data availability
- ✅ 5-day window captures weekly momentum
- ✅ Low noise compared to 1-day horizon
- ✅ Realistic execution (weekly rebalancing)
- ✅ Aligns with `returns_5d` feature (RET-03)
- ✅ Matches PRD default (label_window: 5)

**Why not 1 day?**
- Daily noise is high
- Transaction costs eat into short-term returns
- Signal-to-noise ratio is poor

**Why not 20 days?**
- Too long for active trading
- Reduced number of independent samples
- Harder to evaluate in backtesting

### 5.3 Horizon Configuration

```yaml
dataset:
  label_window: 5  # 5 trading days
  label_type: classification
  thresholds:
    up: 0.01
    down: 0.01
```

---

## 6. Future Return Label

### 6.1 Mathematical Formulation

```
future_return_t = (close_{t+H} - close_t) / close_t

Where:
  close_t = closing price at time T
  close_{t+H} = closing price at time T+H (H = 5 days)
  H = prediction horizon (5 trading days)
```

### 6.2 Simple Return vs Log Return

| Metric | Formula | Pros | Cons |
|--------|---------|------|------|
| **Simple Return** | (P_{t+H} - P_t) / P_t | Intuitive, directly comparable to thresholds | Not additive across periods |
| **Log Return** | ln(P_{t+H} / P_t) | Symmetric, additive | Less intuitive for thresholds |

**MVP Choice: Simple Return**

Rationale:
- Thresholds are defined in percentage terms (1%)
- Simple returns are directly interpretable
- No need for log-transform for 5-day horizon

### 6.3 Entry/Exit Timing

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       ENTRY/EXIT TIMING                                  │
│                                                                          │
│  Entry:                                                                  │
│    - Timestamp: T (feature computation time)                             │
│    - Price: close_T (closing price at time T)                            │
│    - Assumes: position entered at close of day T                         │
│                                                                          │
│  Exit:                                                                   │
│    - Timestamp: T+H (H = 5 trading days later)                          │
│    - Price: close_{T+H} (closing price at time T+H)                     │
│    - Assumes: position exited at close of day T+H                        │
│                                                                          │
│  Realistic Execution:                                                    │
│    - Entry at next-day open (not current close)                          │
│    - Exit at target-day close                                            │
│    - Slippage: 5-10 bps per side                                         │
│    - For MVP: Use close-to-close (simplified)                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.4 Return Computation Example

```
Date: 2024-01-02 (T)
Close: $185.60

Date: 2024-01-09 (T+5)
Close: $187.40

future_return = (187.40 - 185.60) / 185.60 = 0.0097 = 0.97%

Label: HOLD (0.97% < 1.0% threshold)
```

---

## 7. HOLD Class Design

### 7.1 HOLD Purpose

The HOLD class represents periods where the future return is insufficient to justify a trade after accounting for transaction costs.

**Purpose:**
- Reduces noise in predictions
- Filters out insignificant moves
- Represents realistic trading decisions
- Prevents overtrading

### 7.2 Threshold Justification

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       HOLD THRESHOLD JUSTIFICATION                       │
│                                                                          │
│  Transaction Cost Model:                                                 │
│    - Broker commission: 5 bps per side                                   │
│    - Slippage: 5 bps per side                                            │
│    - Total round-trip: 20 bps (0.20%)                                   │
│                                                                          │
│  Minimum Profitable Move:                                                │
│    - Must exceed 2× transaction costs                                    │
│    - 2 × 20 bps = 40 bps = 0.40%                                       │
│                                                                          │
│  HOLD Threshold:                                                         │
│    - Set at 1.0% (well above minimum profitable move)                   │
│    - Provides buffer for additional uncertainty                          │
│    - Produces reasonable class balance                                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.3 Expected Class Distribution

For 5-day horizon with 1% threshold on US equities:

| Class | Expected % | Acceptable Range |
|-------|-----------|-----------------|
| UP | ~33% | 25-45% |
| DOWN | ~33% | 25-45% |
| HOLD | ~34% | 20-50% |

**Note:** Distribution varies by market regime and ticker.

### 7.4 HOLD Impact on Trading

- HOLD predictions → No trade (sit in cash)
- UP predictions → Buy/Long
- DOWN predictions → Sell/Short (if allowed) or avoid

---

## 8. Multi-Target Possibility

### 8.1 Architecture Support

The label generation architecture should support multiple targets:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       MULTI-TARGET ARCHITECTURE                          │
│                                                                          │
│  Target 1: Direction (UP/DOWN/HOLD)         ← MVP PRIMARY              │
│  Target 2: Future Return (regression)       ← Future extension          │
│  Target 3: Future Volatility (regression)   ← Future extension          │
│  Target 4: Adverse Movement (binary)        ← Future extension          │
│                                                                          │
│  Implementation:                                                         │
│    - LabelEngine generates all targets in one pass                       │
│    - Each target has its own configuration                               │
│    - Targets are stored in separate columns/series                       │
│    - Model training selects which target to use                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Future Target Definitions

| Target | Type | Formula | Use Case |
|--------|------|---------|----------|
| Direction | Classification | UP/DOWN/HOLD | Trading signals |
| Future Return | Regression | (close_{t+H} - close_t) / close_t | Position sizing |
| Future Volatility | Regression | std(returns, H) | Risk management |
| Adverse Movement | Binary | 1 if return < -2% | Stop-loss triggering |

### 8.3 MVP Scope

**MVP implements only Target 1 (Direction).**

Multi-target support is architecture-ready but not implemented.

---

## 9. Label Timing

### 9.1 Strict Timing Contract

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       TIMING CONTRACT                                    │
│                                                                          │
│  At time T (feature computation):                                        │
│                                                                          │
│    FEATURES may use:                                                     │
│      All data from T-∞ to T                                              │
│      (historical OHLCV, calculated indicators)                           │
│                                                                          │
│    LABEL may use:                                                        │
│      Data from T+1 to T+H                                                │
│      (future closing prices)                                             │
│                                                                          │
│  Training row represents:                                                │
│                                                                          │
│    X(T) → Y(T+H)                                                        │
│                                                                          │
│    Where X(T) is the feature vector at time T                            │
│    And Y(T+H) is the label derived from future data                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Multiple Examples

**Example 1: Daily Data**
```
Time T: 2024-01-02 (Tuesday)
Features: Use data from 2024-01-02 and before
Label: Uses close prices from 2024-01-03 to 2024-01-09
Result: X(2024-01-02) → Y(2024-01-09)
```

**Example 2: Weekly Data**
```
Time T: Week of 2024-01-01
Features: Use data from this week and before
Label: Uses close prices from next 5 trading days
Result: X(week_1) → Y(week_1 + 5 days)
```

**Example 3: Overlapping**
```
Row 1: X(2024-01-02) → Y(2024-01-09)
Row 2: X(2024-01-03) → Y(2024-01-10)
Row 3: X(2024-01-04) → Y(2024-01-11)
...
Note: Rows overlap — see Section 13
```

### 9.3 Timing Validation

```
Test: Label uses only future data
  For each row at time T:
    Assert: label computation uses only close_{T+1} to close_{T+H}
    Assert: no feature at time T uses close_{T+1} or later
    Assert: no label at time T uses close_{T} or earlier
```

---

## 10. Look-Ahead Bias Prevention

### 10.1 Leakage Risks

| Risk | Description | Mitigation |
|------|-------------|------------|
| **Future close in features** | Feature accidentally uses close_{t+1} | Strict lookback windows |
| **Overlapping windows** | Label window overlaps with feature window | Temporal separation |
| **Incorrect shift** | Shift operation uses wrong direction | Careful implementation |
| **Future normalization** | Scaler fitted on future data | Fit scaler on train only |
| **Future-derived thresholds** | Thresholds computed on test set | Fix thresholds before evaluation |
| **Data joins using future timestamps** | Join features and labels incorrectly | Align on timestamp |
| **Corporate action info** | Using split/dividend info not available at time T | Use only historical data |

### 10.2 Leakage Prevention Rules

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       LEAKAGE PREVENTION RULES                           │
│                                                                          │
│  RULE 1: Temporal Separation                                             │
│    - Features use data ≤ T                                               │
│    - Labels use data > T                                                 │
│    - No overlap between feature and label windows                        │
│                                                                          │
│  RULE 2: No Future in Features                                           │
│    - Every feature has documented lookback window                        │
│    - Features use .shift() or .rolling() with correct direction          │
│    - Integration tests verify no future data in features                 │
│                                                                          │
│  RULE 3: Label Uses Only Future Data                                     │
│    - Label computation starts from close_{T+1}                           │
│    - Never uses close_T or earlier                                        │
│    - Forward window is strictly after T                                   │
│                                                                          │
│  RULE 4: No Future Normalization                                         │
│    - Scalers fitted on training data only                                │
│    - Applied to validation/test without refitting                        │
│    - Saved with model artifact                                           │
│                                                                          │
│  RULE 5: Fixed Thresholds                                                │
│    - Thresholds defined before evaluation                                │
│    - Never tuned on test set                                              │
│    - Configured in YAML, logged with experiment                          │
│                                                                          │
│  RULE 6: Chronological Splits                                            │
│    - Train < Validation < Test in time                                   │
│    - No random splitting                                                 │
│    - Walk-forward validation for backtesting                             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 10.3 Validation Tests

| Test | Description | Implementation |
|------|-------------|----------------|
| **Shift Test** | Verify features don't use future data | Compute F(T) and F(T+1), check shift consistency |
| **Random Label Test** | Features shouldn't predict random labels | Train on random labels, expect ~50% accuracy |
| **Temporal Holdout** | Features shouldn't change with future data | Train on past, test on future, compare distributions |
| **Label-Feature Separation** | Labels and features use different data | Verify no shared columns between feature and label DataFrames |

---

## 11. Label Generation Algorithm

### 11.1 Conceptual Steps

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       LABEL GENERATION ALGORITHM                         │
│                                                                          │
│  INPUT:                                                                  │
│    - Clean DataFrame with close prices                                  │
│    - Configuration: horizon (H), thresholds (up, down)                   │
│                                                                          │
│  STEPS:                                                                  │
│                                                                          │
│  1. SORT CHRONOLOGICALLY                                                 │
│     │  Ensure data is sorted by timestamp ascending                      │
│     │  Duplicate timestamps → reject                                    │
│     │                                                                    │
│     ▼                                                                    │
│  2. ALIGN TIMESTAMPS                                                     │
│     │  Verify timestamps match between features and labels               │
│     │  No missing timestamps in sequence                                 │
│     │                                                                    │
│     ▼                                                                    │
│  3. DETERMINE PREDICTION HORIZON                                         │
│     │  H = 5 (default)                                                   │
│     │  Verify enough future data exists                                  │
│     │                                                                    │
│     ▼                                                                    │
│  4. OBTAIN FUTURE OBSERVATION                                            │
│     │  future_close = close.shift(-H)                                    │
│     │  For each row T, get close_{T+H}                                   │
│     │                                                                    │
│     ▼                                                                    │
│  5. CALCULATE FUTURE OUTCOME                                             │
│     │  future_return = (future_close - close) / close                    │
│     │  For each row T: (close_{T+H} - close_T) / close_T                │
│     │                                                                    │
│     ▼                                                                    │
│  6. APPLY LABEL RULE                                                     │
│     │  if future_return > threshold_up → "UP"                            │
│     │  elif future_return < -threshold_down → "DOWN"                     │
│     │  else → "HOLD"                                                     │
│     │                                                                    │
│     ▼                                                                    │
│  7. MARK INVALID ROWS                                                    │
│     │  Last H rows have NaN future_close → label = NaN                   │
│     │  Rows with insufficient data → label = NaN                         │
│     │                                                                    │
│     ▼                                                                    │
│  8. STORE METADATA                                                       │
│     │  Record: horizon, thresholds, label distribution                   │
│     │  Log: computation parameters, row counts                           │
│     │                                                                    │
│     ▼                                                                    │
│  9. VALIDATE LABEL DISTRIBUTION                                          │
│     │  Check class balance                                               │
│     │  Log distribution per split                                        │
│     │  Flag if highly imbalanced                                         │
│     │                                                                    │
│     ▼                                                                    │
│  OUTPUT: Label Series with values ["UP", "DOWN", "HOLD", NaN]            │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Output Schema

```python
@dataclass
class LabelOutput:
    labels: pd.Series              # Index: DatetimeIndex, Values: "UP"/"DOWN"/"HOLD"/NaN
    future_returns: pd.Series      # Raw future returns (for auditing)
    metadata: LabelMetadata         # Generation parameters
    distribution: Dict[str, int]    # Class counts
    invalid_count: int              # Rows with NaN labels
```

---

## 12. Invalid / Edge Cases

### 12.1 Edge Case Handling

| Edge Case | Detection | Handling |
|-----------|-----------|----------|
| **Missing future candle** | future_close is NaN | Set label to NaN |
| **Market close before horizon** | Not enough trading days | Set label to NaN |
| **Trading holiday in window** | Holiday in date range | Skip holiday, extend horizon |
| **Symbol suspension** | Volume = 0 for multiple days | Set label to NaN |
| **Insufficient history** | Row < max_lookback | Set label to NaN |
| **Corporate action boundary** | Split/dividend in window | Use adjusted prices |
| **Abnormal data** | Price = 0 or negative | Set label to NaN |
| **Delisted instrument** | Last available date | Set label to NaN after delisting |

### 12.2 Rules

```
RULE: Never fabricate labels silently.

If future data is unavailable:
  1. Set label to NaN
  2. Log the edge case
  3. Include in metadata (invalid_count)
  4. Dataset Builder drops rows with NaN labels

If corporate action occurs in window:
  1. Use adjusted close prices (adj_close)
  2. Log the corporate action
  3. Continue with label generation
```

### 12.3 Edge Case Log

```python
@dataclass
class EdgeCaseLog:
    ticker: str
    timestamp: str
    edge_case_type: str        # "missing_candle", "holiday", "suspension", etc.
    description: str           # Human-readable description
    action_taken: str          # "label_set_nan", "adjusted_price", etc.
    affected_rows: int         # Number of rows affected
```

---

## 13. Overlapping Labels

### 13.1 Overlapping Horizons

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       OVERLAPPING HORIZONS                               │
│                                                                          │
│  With H = 5 (5-day horizon):                                            │
│                                                                          │
│  Row 1: X(2024-01-02) → Y(2024-01-09)                                   │
│  Row 2: X(2024-01-03) → Y(2024-01-10)                                   │
│  Row 3: X(2024-01-04) → Y(2024-01-11)                                   │
│  Row 4: X(2024-01-05) → Y(2024-01-12)                                   │
│  Row 5: X(2024-01-08) → Y(2024-01-15)                                   │
│                                                                          │
│  Overlap: Rows 1-5 share price data from 2024-01-03 to 2024-01-09       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 13.2 Impact Analysis

| Concern | Impact | MVP Handling |
|---------|--------|-------------|
| **Dependency between samples** | Adjacent rows share price data | Accept (standard in time-series) |
| **Impact on validation** | Validation scores may be optimistic | Use walk-forward validation |
| **Leakage risk** | Label windows overlap feature windows | No leakage (features use past only) |
| **Sample independence** | Rows are not independent | Acknowledge in evaluation |

### 13.3 Temporal Purging / Embargo

**MVP Recommendation: No purging/embargo for daily data.**

Rationale:
- Daily data has natural spacing
- Feature windows (lookback) and label windows (forward) don't overlap
- Walk-forward validation handles temporal dependencies
- Purging is more critical for intraday data

**Future Enhancement:**
- For intraday data, implement embargo period
- Gap between training and test sets

---

## 14. Class Balance

### 14.1 Monitoring

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       CLASS BALANCE MONITORING                            │
│                                                                          │
│  After label generation, compute:                                        │
│                                                                          │
│    up_count = count(labels == "UP")                                      │
│    down_count = count(labels == "DOWN")                                  │
│    hold_count = count(labels == "HOLD")                                  │
│    total = up_count + down_count + hold_count                            │
│                                                                          │
│    up_pct = up_count / total × 100                                       │
│    down_pct = down_count / total × 100                                   │
│    hold_pct = hold_count / total × 100                                   │
│                                                                          │
│  Acceptable Ranges:                                                      │
│    UP: 25-45%                                                            │
│    DOWN: 25-45%                                                          │
│    HOLD: 20-50%                                                          │
│                                                                          │
│  If outside ranges:                                                      │
│    → Log WARNING                                                         │
│    → Suggest threshold adjustment                                        │
│    → Do NOT adjust thresholds automatically                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 14.2 Imbalance Handling

| Strategy | When to Use | MVP? |
|----------|-------------|------|
| **Threshold adjustment** | One class dominates | ❌ Not automatic |
| **Sample weighting** | Model training | ⚠️ Optional |
| **Stratification** | Dataset splitting | ✅ Yes |
| **Synthetic oversampling** | Extreme imbalance | ❌ Avoid |
| **Class-weighted loss** | Model training | ⚠️ Optional |

### 14.3 Rules

```
RULE: Do NOT use future test-set information to tune label thresholds.

If class balance is poor:
  1. Log the imbalance
  2. Report in metadata
  3. Let researcher decide whether to adjust thresholds
  4. Never auto-adjust based on test set distribution
```

---

## 15. Target Distribution Analysis

### 15.1 Required Statistics

| Statistic | Description | Computation |
|-----------|-------------|-------------|
| **Mean future return** | Average return over horizon | mean(future_returns) |
| **Median future return** | Median return | median(future_returns) |
| **Standard deviation** | Return volatility | std(future_returns) |
| **Percentile distribution** | 5th, 25th, 50th, 75th, 95th | percentile(future_returns, [5,25,50,75,95]) |
| **Class frequency** | UP/DOWN/HOLD counts | value_counts() |
| **Extreme outcomes** | Returns > 5% or < -5% | count(abs(return) > 0.05) |
| **Missing target rate** | NaN labels / total | count(nan) / total |

### 15.2 Computation Without Contamination

```
RULE: Compute statistics only on training period data.

  - Training statistics: computed on train split only
  - Validation statistics: computed on val split only
  - Test statistics: computed on test split only
  - Never use test statistics to inform training decisions
```

---

## 16. Transaction Cost Awareness

### 16.1 Why Raw Returns Are Misleading

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       TRANSACTION COST AWARENESS                         │
│                                                                          │
│  Raw Future Return:                                                      │
│    +1.5% (appears profitable)                                            │
│                                                                          │
│  After Transaction Costs:                                                │
│    Gross return:       +1.50%                                            │
│    Broker commission:  -0.05%  (5 bps per side)                         │
│    Slippage:           -0.05%  (5 bps per side)                         │
│    Spread:             -0.05%  (5 bps estimated)                         │
│    ─────────────────────────────                                         │
│    Net return:         +1.35%                                            │
│                                                                          │
│  Still profitable? Yes.                                                  │
│                                                                          │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                          │
│  Raw Future Return:                                                      │
│    +0.3% (appears profitable)                                            │
│                                                                          │
│  After Transaction Costs:                                                │
│    Gross return:       +0.30%                                            │
│    Total costs:        -0.15%                                            │
│    ─────────────────────────────                                         │
│    Net return:         +0.15%                                            │
│                                                                          │
│  Barely profitable — may not be worth the risk.                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 16.2 Cost-Aware Label Generation (Future)

**MVP: Use fixed thresholds that implicitly account for costs.**

**Future Enhancement:**
```yaml
label_generation:
  cost_aware: true
  transaction_costs:
    commission_bps: 5
    slippage_bps: 5
    spread_bps: 5
  net_threshold: gross_threshold + total_costs
```

### 16.3 Configurable Cost Model

The label system must remain configurable so cost assumptions can be integrated later.

```yaml
# Future configuration
dataset:
  label_type: classification
  label_window: 5
  thresholds:
    up: 0.01
    down: 0.01
  cost_aware: false  # Future: true
  transaction_costs:
    commission_bps: 5
    slippage_bps: 5
    spread_bps: 5
```

---

## 17. Label Versioning

### 17.1 Version Scheme

```
Label Set Version: v{major}.{minor}

Examples:
  v0.1  → Initial label set (UP/DOWN/HOLD, 1% threshold, 5-day horizon)
  v0.2  → Adjusted thresholds (0.5%)
  v0.3  → Added cost-aware labels
  v1.0  → Production-ready label set
```

### 17.2 Version Hash

```python
def compute_label_version_hash(config: dict) -> str:
    """Compute deterministic hash for label set version."""
    version_input = {
        "label_type": config["label_type"],
        "label_window": config["label_window"],
        "thresholds": config["thresholds"],
        "cost_aware": config.get("cost_aware", False),
    }
    version_string = json.dumps(version_input, sort_keys=True)
    return hashlib.sha256(version_string.encode()).hexdigest()
```

### 17.3 Version Metadata

Every training dataset must identify:
- Target name (e.g., "direction")
- Horizon (e.g., 5 days)
- Threshold (e.g., 1%)
- Label version (e.g., "v0.1")
- Generation timestamp
- Source dataset version

---

## 18. Label Metadata

### 18.1 Metadata Schema

```python
@dataclass
class LabelMetadata:
    # Identity
    label_id: str              # "direction_v0.1"
    version: str               # "v0.1"
    
    # Definition
    label_name: str            # "direction"
    target_type: str           # "classification"
    horizon: int               # 5
    horizon_unit: str          # "trading_days"
    
    # Thresholds
    threshold_up: float        # 0.01
    threshold_down: float      # 0.01
    
    # Source
    source_column: str         # "close"
    source_dataset_version: str # "v0.1"
    
    # Generation
    generation_rule: str       # "if return > 0.01 → UP, elif < -0.01 → DOWN, else HOLD"
    generated_at: str          # ISO timestamp
    
    # Distribution
    total_rows: int
    up_count: int
    down_count: int
    hold_count: int
    nan_count: int
    
    # Status
    status: str                # "active", "deprecated", "experimental"
```

### 18.2 Metadata Storage

```
metadata/
├── labels/
│   ├── label_set_v0.1.json       ← Label version metadata
│   ├── label_direction_v0.1.json ← Individual label metadata
│   └── ...
└── label_versions/
    └── v0.1_hash.txt             ← Version hash
```

---

## 19. Research Experiments

### 19.1 Experiment Definitions

| Experiment | Target | Hypothesis | Inputs | Evaluation |
|------------|--------|------------|--------|------------|
| **EXP-A** | Binary UP/DOWN | Direction is predictable | Features, no HOLD class | Accuracy, F1 |
| **EXP-B** | UP/DOWN/HOLD | HOLD class improves signal | Features, 3 classes | Accuracy, F1, Sharpe |
| **EXP-C** | Regression future return | Exact return is predictable | Features, continuous target | RMSE, R² |
| **EXP-D** | Cost-aware classification | Thresholds should include costs | Features, adjusted thresholds | Accuracy, F1, Sharpe |

### 19.2 Experiment Protocol

```
For each experiment:
  1. Define target (classification vs regression)
  2. Configure label generation parameters
  3. Generate labels for all data
  4. Create dataset with chronological splits
  5. Train models (logistic regression, random forest)
  6. Run walk-forward backtest
  7. Record metrics
  8. Compare against baseline
  9. Document results
```

### 19.3 Leakage Controls

- All experiments use same data splits
- Thresholds fixed before evaluation
- No test-set information used in label generation
- Walk-forward validation for all experiments

---

## 20. Recommended MVP Label

### 20.1 Primary Target

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       MVP LABEL RECOMMENDATION                           │
│                                                                          │
│  PRIMARY TARGET: Direction Classification                                │
│                                                                          │
│  HORIZON: 5 trading days (1 week)                                       │
│                                                                          │
│  LABEL RULE:                                                             │
│    future_return = (close_{t+5} - close_t) / close_t                    │
│                                                                          │
│    if future_return > 0.01:       label = "UP"                           │
│    elif future_return < -0.01:    label = "DOWN"                         │
│    else:                          label = "HOLD"                         │
│                                                                          │
│  THRESHOLDS:                                                             │
│    threshold_up = 1.0%                                                   │
│    threshold_down = 1.0%                                                 │
│                                                                          │
│  SECONDARY TARGET: None for MVP                                         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 20.2 Justification

| Factor | Assessment |
|--------|------------|
| **Business usefulness** | High — directly usable for trading signals |
| **Data requirements** | Low — only OHLCV data needed |
| **Class balance** | Good — roughly 33/33/33 with 1% threshold |
| **Robustness** | High — classification is more robust than regression |
| **Interpretability** | High — UP/DOWN/HOLD is intuitive |
| **Backtesting suitability** | High — standard classification evaluation |
| **Complexity** | Low — simple threshold-based labeling |
| **Overfitting risk** | Low — discrete classes reduce noise |

### 20.3 Configuration

```yaml
dataset:
  label_type: classification
  label_window: 5
  thresholds:
    up: 0.01
    down: 0.01
  cost_aware: false
```

---

## 21. Future Extensions

### 21.1 Reserved Architecture

| Extension | Description | Status |
|-----------|-------------|--------|
| **Multi-horizon prediction** | Predict 1d, 5d, 20d simultaneously | ⏳ Placeholder |
| **Volatility targets** | Predict future volatility | ⏳ Placeholder |
| **Maximum adverse excursion** | Predict worst drawdown | ⏳ Placeholder |
| **Maximum favorable excursion** | Predict best gain | ⏳ Placeholder |
| **Risk-adjusted target** | Sharpe-based label | ⏳ Placeholder |
| **Event-conditioned labels** | Labels conditioned on events | ⏳ Placeholder |
| **Options-aware labels** | Labels incorporating options data | ⏳ Placeholder |

### 21.2 Future Target Definitions

```yaml
# Future: Multi-horizon
dataset:
  targets:
    - name: direction_1d
      horizon: 1
      thresholds: {up: 0.005, down: 0.005}
    - name: direction_5d
      horizon: 5
      thresholds: {up: 0.01, down: 0.01}
    - name: direction_20d
      horizon: 20
      thresholds: {up: 0.02, down: 0.02}

# Future: Regression
dataset:
  targets:
    - name: return_5d
      type: regression
      horizon: 5

# Future: Risk
dataset:
  targets:
    - name: max_drawdown_5d
      type: regression
      horizon: 5
```

---

## 22. Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| Primary target explicitly defined (Direction Classification) | ✅ |
| Horizon explicitly defined (5 trading days) | ✅ |
| Label formula explicit | ✅ |
| UP/DOWN/HOLD logic explicit | ✅ |
| Timing contract explicit | ✅ |
| Leakage risks documented | ✅ |
| Edge cases documented | ✅ |
| Class imbalance strategy exists | ✅ |
| Versioning exists | ✅ |
| Future extensions separated from MVP | ✅ |

---

## 23. Consistency Check

### 23.1 Cross-Reference with Previous Documents

| Document | Check | Status | Notes |
|----------|-------|--------|-------|
| **PRD_MVP.md** | FR-LG-01: UP/DOWN/HOLD | ✅ Consistent | Matches |
| **PRD_MVP.md** | FR-LG-02: 5-period window | ✅ Consistent | Matches |
| **PRD_MVP.md** | FR-LG-03: >+1% UP, <-1% DOWN | ✅ Consistent | Matches |
| **PRD_MVP.md** | FR-LG-04: Features must not contain label info | ✅ Consistent | Matches |
| **SYSTEM_ARCHITECTURE.md** | LabelEngine class | ✅ Consistent | Module location matches |
| **DATA_ARCHITECTURE.md** | labels table schema | ✅ Consistent | Schema matches |
| **FEATURE_ENGINEERING_BLUEPRINT.md** | returns_5d matches label window | ✅ Consistent | 5-day alignment |

### 23.2 Conflicts Found

**None.** All documents are consistent.

### 23.3 Required Changes

**None.** No changes to previous architecture required.

---

## 24. Deliverables

| Deliverable | Status | Description |
|-------------|--------|-------------|
| `docs/LABEL_GENERATION_BLUEPRINT.md` | ✅ This document | Complete label generation design |
| `docs/CURRENT_STATE.md` | ✅ Updated | Architecture milestone recorded |
| `docs/DECISIONS.md` | ✅ Updated | ADR for label generation |

---

## 25. Stop Condition

**This document is research and architecture only.**

**DO NOT:**
- Implement label-generation code
- Create datasets
- Train models
- Perform backtests
- Create APIs
- Build dashboards

**STOP after producing the documents and reporting the result.**

---

## Final Report

### A. Recommended Primary Target

**Direction Classification (UP/DOWN/HOLD)**

### B. Recommended Prediction Horizon

**5 trading days (1 week)**

### C. Label Methodology

```
future_return = (close_{t+5} - close_t) / close_t

if future_return > 0.01 → "UP"
elif future_return < -0.01 → "DOWN"
else → "HOLD"
```

### D. Leakage Risks

- **Zero leakage risk** in MVP label generation
- Labels use only future data (close_{t+5})
- Features use only past data (≤ t)
- Strict temporal separation enforced

### E. Edge Cases

- Missing future candles → label = NaN
- Trading holidays → skip, extend horizon
- Corporate actions → use adjusted prices
- Delisted instruments → label = NaN after delisting

### F. Class-Balance Strategy

- Monitor UP/DOWN/HOLD distribution
- Log if outside acceptable ranges (25-45% UP, 25-45% DOWN, 20-50% HOLD)
- Never auto-adjust thresholds based on test set
- Let researcher decide threshold changes

### G. Important Research Decisions

1. **Simple returns** over log returns (more interpretable)
2. **Fixed thresholds** (1%) over adaptive (simpler for MVP)
3. **No cost-aware labels** in MVP (future enhancement)
4. **No temporal purging** for daily data (walk-forward handles dependencies)
5. **5-day horizon** (balances signal stability and noise)

### H. Conflicts with Previous Documents

**None.** All documents are consistent.

### I. Exact Next Recommended Task

**Implement the Label Engine module** (`src/features/labels.py`) with unit tests for label generation, edge case handling, and distribution monitoring.
