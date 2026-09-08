# RISK MANAGEMENT & DECISION ENGINE BLUEPRINT — Finance AI MVP

> Deterministic decision layer that converts model outputs into research signals while applying explicit risk controls.
> Prediction → Decision → Backtest/Paper Simulation. Execution is OUT OF SCOPE for MVP.

---

## Table of Contents

1. [Primary Objective](#1-primary-objective)
2. [Create Document](#2-create-document)
3. [Core Principle](#3-core-principle)
4. [Input Contract](#4-input-contract)
5. [Output Contract](#5-output-contract)
6. [Signal Generation](#6-signal-generation)
7. [Cost-Aware Decision](#7-cost-aware-decision)
8. [Risk Filters](#8-risk-filters)
9. [Market Regime Filter](#9-market-regime-filter)
10. [Confidence Handling](#10-confidence-handling)
11. [Position Sizing](#11-position-sizing)
12. [Risk Budget](#12-risk-budget)
13. [Stop-Loss / Take-Profit](#13-stop-loss--take-profit)
14. [Holding Period](#14-holding-period)
15. [Signal Expiry](#15-signal-expiry)
16. [Position State](#16-position-state)
17. [Conflicting Signals](#17-conflicting-signals)
18. [Model Quality Gate](#18-model-quality-gate)
19. [Data Quality Gate](#19-data-quality-gate)
20. [Risk Score](#20-risk-score)
21. [Decision Explanation](#21-decision-explanation)
22. [Decision Log](#22-decision-log)
23. [Backtest Integration](#23-backtest-integration)
24. [Research Safety](#24-research-safety)
25. [Threshold Research](#25-threshold-research)
26. [Sensitivity Analysis](#26-sensitivity-analysis)
27. [Abstention / No-Trade Policy](#27-abstention--no-trade-policy)
28. [Acceptance Criteria](#28-acceptance-criteria)
29. [Future Extensions](#29-future-extensions)
30. [Consistency Check](#30-consistency-check)
31. [Deliverables](#31-deliverables)
32. [Stop Condition](#32-stop-condition)

---

## 1. Primary Objective

Design a deterministic decision layer that converts model outputs into research signals while applying explicit risk controls.

**Core flow:**

```
Model Prediction
      ↓
Prediction Validation
      ↓
Probability / Expected Return
      ↓
Signal Logic
      ↓
Risk Filters
      ↓
Position Decision
      ↓
Research Backtest / Paper Simulation
```

**The Decision Engine must NEVER bypass risk controls.**

---

## 2. Create Document

**Create:** `docs/RISK_DECISION_ENGINE_BLUEPRINT.md`

---

## 3. Core Principle

### 3.1 Strict Separation

```
┌─────────────────────────────────────────────────────────────────┐
│              PREDICTION / DECISION / EXECUTION                   │
│                                                                  │
│  PREDICTION                                                       │
│    ── What the model says about future price movement             │
│    ── Probabilities, expected returns, uncertainty                 │
│    ── Output: P(UP), P(DOWN), P(HOLD), expected_return           │
│                                                                  │
│  DECISION                                                         │
│    ── What the system should DO based on the prediction           │
│    ── Applies risk controls, thresholds, filters                  │
│    ── Output: BUY, SELL, HOLD, NO_TRADE                          │
│                                                                  │
│  EXECUTION                                                        │
│    ── How the decision is carried out in the market               │
│    ── Order placement, timing, position management                │
│    ── OUT OF SCOPE FOR MVP                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 MVP Scope

**MVP supports only:**

```
Prediction → Decision → Backtest/Paper Simulation
```

**Execution must remain OUT OF SCOPE.**

The Decision Engine produces research signals, not live orders. All decisions are evaluated through backtesting or paper simulation only.

### 3.3 Why Separation Matters

| Violation | Consequence |
|-----------|-------------|
| Prediction and decision mixed | Cannot test decision rules independently |
| Decision and execution mixed | Cannot backtest without broker connection |
| Risk filters bypassed | False confidence in signal quality |
| No separation of concerns | Cannot debug whether bad result is model or decision |

---

## 4. Input Contract

### 4.1 Required Inputs

| Input | Type | Source | MVP? | Future? |
|-------|------|--------|-------|---------|
| **model_probability** | Dict[str, float] | Model prediction (P(UP), P(DOWN), P(HOLD)) | ✅ Yes | — |
| **predicted_return** | float | Model expected return estimate | ⚠️ Optional (if model supports) | — |
| **predicted_volatility** | float | Model volatility estimate | ❌ No | ✅ Future (risk-adjusted decisions) |
| **current_price** | float | Latest close price | ✅ Yes | — |
| **recent_volatility** | float | Realized volatility (e.g., 20-day) | ✅ Yes | — |
| **market_regime** | str | Regime classification (TRENDING, RANGE_BOUND, HIGH_VOL, LOW_VOL) | ⚠️ Optional (if available) | — |
| **liquidity_proxy** | float | Volume or spread proxy | ❌ No | ✅ Future (liquidity-based filters) |
| **transaction_cost** | float | Estimated round-trip cost (bps) | ✅ Yes (from config) | — |
| **slippage** | float | Estimated slippage (bps per side) | ✅ Yes (from config) | — |
| **instrument_metadata** | Dict | Ticker, exchange, trading hours, etc. | ⚠️ Optional | — |
| **model_version** | str | Model version identifier | ✅ Yes | — |
| **feature_version** | str | Feature set version | ✅ Yes | — |
| **strategy_version** | str | Decision strategy version | ✅ Yes | — |
| **timestamp** | datetime | Decision timestamp | ✅ Yes | — |
| **data_timestamp** | datetime | Timestamp of data used for prediction | ✅ Yes | — |

### 4.2 MVP Input Set

For MVP, the Decision Engine requires:

```yaml
decision_input:
  model_probability: {UP: 0.62, DOWN: 0.23, HOLD: 0.15}
  current_price: 185.60
  recent_volatility: 0.25          # 20-day annualized volatility
  transaction_cost_bps: 10         # round-trip
  slippage_bps_per_side: 5
  model_version: "v1.0.0-20260904"
  feature_version: "v0.1"
  strategy_version: "stg_v0.1"
  timestamp: "2026-09-04T10:00:00Z"
  data_timestamp: "2026-09-04T09:30:00Z"
  prediction_horizon_days: 5
```

### 4.3 Missing Input Handling

| Missing Input | Action |
|--------------|--------|
| model_probability | NO_TRADE — cannot decide without prediction |
| current_price | NO_TRADE — cannot compute expected return |
| recent_volatility | Use default/rolling estimate or NO_TRADE |
| market_regime | Not required for MVP — proceed without regime filter |
| transaction_cost | Use configured default |

---

## 5. Output Contract

### 5.1 Decision Object Structure

```python
@dataclass
class Decision:
    # Signal
    signal: str                     # "BUY" | "SELL" | "HOLD" | "NO_TRADE"

    # Confidence
    confidence: float               # 0.00–1.00 (model probability for chosen class)

    # Expected return
    expected_return: Optional[float]  # Numeric estimate (if model provides)

    # Risk score
    risk_score: float               # 0.00–1.00 (normalized research risk)

    # Position
    position_size: Optional[float]  # Numeric (units or notional) or None for NO_TRADE

    # Explanation
    reason_codes: List[str]         # Machine-readable codes (see Section 21)

    # Metadata
    timestamp: str                  # Decision timestamp
    model_version: str              # Model that produced prediction
    strategy_version: str           # Decision strategy version
    instrument: str                 # Ticker symbol
    data_version: str               # Dataset/feature version used
```

### 5.2 Example Decision Objects

**BUY decision:**

```json
{
  "signal": "BUY",
  "confidence": 0.62,
  "expected_return": 0.012,
  "risk_score": 0.35,
  "position_size": 1.0,
  "reason_codes": ["MODEL_SIGNAL_BUY", "EDGE_ABOVE_COST"],
  "timestamp": "2026-09-04T10:00:00Z",
  "model_version": "v1.0.0-20260904",
  "strategy_version": "stg_v0.1",
  "instrument": "AAPL",
  "data_version": "v0.1"
}
```

**NO_TRADE decision:**

```json
{
  "signal": "NO_TRADE",
  "confidence": 0.42,
  "expected_return": null,
  "risk_score": 0.72,
  "position_size": null,
  "reason_codes": ["CONFIDENCE_BELOW_THRESHOLD", "EDGE_BELOW_COST"],
  "timestamp": "2026-09-04T10:00:00Z",
  "model_version": "v1.0.0-20260904",
  "strategy_version": "stg_v0.1",
  "instrument": "AAPL",
  "data_version": "v0.1"
}
```

---

## 6. Signal Generation

### 6.1 Signal Types

| Signal | Meaning | Action |
|--------|---------|--------|
| **BUY** | Model predicts upward movement with sufficient confidence | Enter LONG (research) |
| **SELL** | Model predicts downward movement with sufficient confidence | Enter SHORT or avoid (research) |
| **HOLD** | Model prediction is uncertain or edge is insufficient | Remain in current position or avoid |
| **NO_TRADE** | No actionable signal — abstain | Do nothing |

### 6.2 Signal Generation Rules

```
Signal Generation Algorithm:

1. Get model probabilities: P(UP), P(DOWN), P(HOLD)
2. Identify predicted class: argmax(P)
3. Get confidence: P(predicted_class)

4. Apply signal thresholds (configurable, research parameters):
   - BUY threshold: P(UP) >= buy_threshold
   - SELL threshold: P(DOWN) >= sell_threshold
   - HOLD zone: neither threshold met, but model has moderate confidence
   - NO_TRADE zone: confidence below minimum, or edge below cost

5. Apply cost-awareness filter (Section 7)
6. Apply risk filters (Section 8)
7. Apply regime filter (Section 9) if enabled
8. Apply confidence filter (Section 10)

9. Output final signal
```

### 6.3 Threshold Evaluation

| Approach | Description | MVP? |
|----------|-------------|------|
| **Probability threshold** | P(UP) >= 0.55 for BUY | ✅ Primary MVP method |
| **Expected return threshold** | predicted_return >= return_threshold | ⚠️ Optional if model provides returns |
| **Minimum edge over costs** | (P(UP) × expected_return - costs) > minimum_edge | ✅ Integrated in cost-aware filter |
| **Confidence threshold** | P(predicted_class) >= min_confidence | ✅ Yes |

### 6.4 MVP Threshold Defaults

```
MVP Signal Thresholds (configurable research parameters):

buy_threshold: 0.55      # P(UP) must be >= 55%
sell_threshold: 0.55     # P(DOWN) must be >= 55%
min_confidence: 0.50     # Below this → NO_TRADE
minimum_edge_bps: 15     # Expected edge must exceed 15 bps after costs
```

**Why these values:**
- 55% probability threshold: modest edge over random (33% for 3-class), acknowledges model imperfection
- 50% minimum confidence: below random guessing for binary — no trade
- 15 bps minimum edge: exceeds typical round-trip cost (10 bps) with small buffer

**These are research parameters, not claims of optimality.**

---

## 7. Cost-Aware Decision

### 7.1 Core Concept

A signal should not be considered actionable when the expected edge is smaller than estimated trading friction.

```
Expected Net Edge = Expected Gross Return - Transaction Costs - Estimated Slippage
```

### 7.2 Cost-Aware Decision Logic

```
For BUY signal:
  expected_gross_return = model_expected_return (or P(UP) × historical_avg_return)
  estimated_costs = transaction_cost_bps + (2 × slippage_bps_per_side)
  expected_net_edge = expected_gross_return - estimated_costs

  If expected_net_edge < minimum_edge_bps:
    → NO_TRADE (reason: EDGE_BELOW_COST)
  Else:
    → Proceed to signal logic

For SELL signal:
  Same logic, using expected downward return

For HOLD:
  If |expected_net_edge| < minimum_edge_bps:
    → HOLD/NO_TRADE (reason: EDGE_BELOW_COST)
```

### 7.3 Minimum Required Net Edge

| Scenario | Minimum Net Edge | Rationale |
|----------|-----------------|-----------|
| **MVP default** | 15 bps | Exceeds 10 bps round-trip cost with small buffer |
| **Conservative** | 25 bps | Larger buffer for uncertainty |
| **Aggressive** | 10 bps | Barely above costs — higher false signal risk |

**MVP default: 15 bps minimum net edge.**

### 7.4 Cost Components

```
Total Estimated Cost per Trade:
  Entry:  brokerage_entry + spread_entry + slippage_entry
  Exit:   brokerage_exit + spread_exit + slippage_exit
  Total:  sum of all components

MVP simplification:
  Total cost = transaction_cost_bps + (2 × slippage_bps_per_side)
  Default:  10 + (2 × 5) = 20 bps round-trip
```

### 7.5 Important Disclaimer

> **Do NOT claim profitability from this rule.** The cost-aware filter prevents obviously unprofitable signals from being acted upon, but it does not guarantee that signals passing the filter will be profitable. Expected returns are estimates; actual returns may differ.

---

## 8. Risk Filters

### 8.1 Filter Design

Risk filters are mandatory checks that can veto a signal even if the model prediction is strong.

```
Signal Flow:
  Model Prediction → Signal Logic → Cost Filter → Risk Filters → Final Decision

If ANY risk filter fails:
  signal = NO_TRADE
```

### 8.2 Risk Filter Catalog

| Filter | Condition | Failure Action | MVP? |
|--------|-----------|---------------|------|
| **Extreme Volatility** | recent_volatility > volatility_threshold | NO_TRADE (HIGH_VOLATILITY) | ✅ Yes |
| **Insufficient Volume** | volume < volume_threshold (if available) | NO_TRADE (LOW_VOLUME) | ⚠️ Optional |
| **Abnormal Data Quality** | NaN, Inf, null in required inputs | NO_TRADE (DATA_QUALITY_FAILURE) | ✅ Yes |
| **Market Closure** | Current time outside trading hours (if known) | NO_TRADE (MARKET_CLOSED) | ⚠️ Optional |
| **Stale Prediction** | data_timestamp + max_age < current_time | NO_TRADE (STALE_PREDICTION) | ✅ Yes |
| **Stale Market Data** | current_price_timestamp + max_age < current_time | NO_TRADE (STALE_DATA) | ✅ Yes |
| **Model Uncertainty** | max_probability < uncertainty_threshold | NO_TRADE (MODEL_UNCERTAINTY) | ✅ Yes |
| **Excessive Spread/Slippage** | estimated_costs > cost_threshold | NO_TRADE (HIGH_COST) | ⚠️ Optional |
| **Invalid Prediction** | probability does not sum to 1, or values out of range | NO_TRADE (INVALID_PREDICTION) | ✅ Yes |

### 8.3 Filter Thresholds (MVP Defaults)

```
Risk Filter Defaults:

extreme_volatility_threshold: 0.60      # Above 60% annualized → filter
stale_prediction_max_age: 600           # seconds (10 minutes)
stale_data_max_age: 300                 # seconds (5 minutes)
model_uncertainty_threshold: 0.45       # Max probability below this → filter
invalid_prediction_check: true          # Always validate probability values
```

### 8.4 Risk Filter Precedence

All risk filters are evaluated. If any filter fails, the signal becomes NO_TRADE regardless of model prediction strength.

```
Priority order (for logging, not for logic — all filters must pass):

1. Data Quality (INVALID_PREDICTION, DATA_QUALITY_FAILURE)
2. Staleness (STALE_PREDICTION, STALE_DATA)
3. Market State (HIGH_VOLATILITY, MARKET_CLOSED)
4. Model Quality (MODEL_UNCERTAINTY)
5. Cost (HIGH_COST)
6. Liquidity (LOW_VOLUME)
```

---

## 9. Market Regime Filter

### 9.1 MVP Regime Representation

From the feature architecture (FEATURE_ENGINEERING_BLUEPRINT.md), MVP regime is derived from:

| Regime | Conceptual Definition |
|--------|----------------------|
| **TRENDING** | Price clearly moving in one direction (e.g., price far from moving average) |
| **RANGE_BOUND** | Price oscillating within a range (e.g., near moving average, Bollinger squeeze) |
| **HIGH_VOLATILITY** | Volatility significantly above normal (e.g., volatility > 80th percentile) |
| **LOW_VOLATILITY** | Volatility significantly below normal (e.g., volatility < 20th percentile) |

### 9.2 Regime Filter Options

| Option | Description | MVP? |
|--------|-------------|------|
| **A. Block signals in selected regimes** | No trades during HIGH_VOLATILITY, for example | ⚠️ Possible |
| **B. Modify thresholds by regime** | Stricter thresholds in high-vol, looser in low-vol | ❌ No — adds complexity |
| **C. Modify position size by regime** | Smaller positions in high-vol | ❌ No — future |
| **D. Do nothing** | Regime information available but not used in MVP | ✅ **RECOMMENDED** |

### 9.3 MVP Recommendation: Option D (No regime filter in MVP)

**Rationale:**
- Regime detection is noisy at daily frequency with limited data
- Adding regime-based rules introduces additional parameters to tune
- Regime filter can be added in future phases without architecture change
- Current feature architecture provides regime as information, not as decision input

**Implementation:** The Decision Engine receives `market_regime` as optional input. If provided, it is logged but does not affect the signal. Future versions can enable regime-based filtering via configuration.

---

## 10. Confidence Handling

### 10.1 The Problem

Raw model probability should not be interpreted as the true probability of the event. A model reporting P(UP) = 0.70 may actually be right only 55% of the time if the model is poorly calibrated.

### 10.2 Confidence Zones

```
Confidence Zones:

High Confidence (P >= 0.65):
  → Potentially actionable (subject to other filters)
  → Higher expected reliability

Medium Confidence (0.50 <= P < 0.65):
  → HOLD / NO_TRADE
  → Insufficient confidence for action

Low Confidence (P < 0.50):
  → NO_TRADE
  → Below or near random guessing for binary decision
```

### 10.3 MVP Confidence Thresholds

```
Confidence Thresholds:

min_confidence_for_signal: 0.55    # Must exceed this for BUY/SELL
uncertain_zone_lower: 0.50         # Below this → low confidence
uncertain_zone_upper: 0.65         # Above this → high confidence
no_trade_zone: < 0.50              # Definitely no trade
```

**Important:** These thresholds should be validated against calibration data. If the model is poorly calibrated, even higher confidence thresholds may be warranted.

### 10.4 Calibration Requirement

> **Do NOT assume probability = true probability unless calibration has been validated.**

Before trusting confidence values:
1. Compute calibration curve on validation data
2. Assess Brier score
3. If model is poorly calibrated, consider:
   - Higher confidence thresholds
   - Probability calibration ( Platt scaling, isotonic regression — future)
   - Using model ranking (ROC-AUC) rather than absolute probability

---

## 11. Position Sizing

### 11.1 MVP Position Sizing Options

| Option | Description | Complexity | Risk |
|--------|-------------|------------|-------|
| **A. Fixed quantity** | Always 1 unit per signal | Low | Simple, but no risk adjustment |
| **B. Fixed notional** | Always $X per signal | Low | Simple, notional risk control |
| **C. Volatility-adjusted sizing** | Size inversely proportional to volatility | Medium | Risk-adjusted, but more parameters |
| **D. Risk-budget sizing** | Size to limit dollar risk per trade | Medium | Most sophisticated, more parameters |

### 11.2 MVP Recommendation: Option A (Fixed quantity)

**Rationale:**
- Simplest approach — 1 unit per trade
- No additional parameters to tune
- Sufficient for evaluating whether signal has value
- Position sizing is a separate research question for future phases
- Avoids introducing parameters that can be overfitting vectors

**Alternative (if notional is preferred):** Option B (Fixed notional) — e.g., $10,000 per trade. Also simple, provides notional context.

**Not recommended for MVP:** Options C and D — too many parameters for initial research, risk of overfitting to backtest.

### 11.3 Position Size Configuration

```yaml
position_sizing:
  method: "fixed_quantity"    # or "fixed_notional"
  fixed_quantity: 1.0         # units per trade
  # OR
  # fixed_notional: 10000.0   # dollars per trade
```

---

## 12. Risk Budget

### 12.1 Research/Paper-Trading Controls

The risk budget defines limits that the Decision Engine enforces during research and paper simulation. These are NOT live-trading controls — they are research safeguards.

### 12.2 MVP Risk Budget Limits

| Limit | Value | Description |
|-------|-------|-------------|
| **Maximum risk per position** | N/A (fixed quantity) | Not applicable with fixed quantity sizing |
| **Maximum aggregate exposure** | 1 position | Only one position at a time in MVP |
| **Maximum simultaneous research positions** | 1 | No simultaneous positions |
| **Maximum daily loss threshold** | Configurable (e.g., -2% of notional) | Daily loss limit for paper simulation |
| **Maximum drawdown guard** | Configurable (e.g., -10% from peak) | Stop paper simulation if drawdown exceeds limit |

### 12.3 Risk Budget Configuration

```yaml
risk_budget:
  max_simultaneous_positions: 1
  daily_loss_limit_pct: -0.02       # -2% of notional per day
  max_drawdown_guard_pct: -0.10     # -10% from peak equity
  # Note: These are PAPER SIMULATION limits only
```

### 12.4 Enforcement

When a limit is reached during paper simulation:
- No new positions entered
- Existing positions may be exited (depending on rules)
- Decision recorded as NO_TRADE with reason_code RISK_LIMIT_REACHED
- Simulation may continue (logging only) or stop (configurable)

**These limits exist for research safety. They do not execute live orders.**

---

## 13. Stop-Loss / Take-Profit

### 13.1 Evaluation

| Option | Description | Risk |
|--------|-------------|------|
| **Fixed stop-loss** | Exit if loss exceeds X% from entry | Adds parameter, can be overfitting vector |
| **Volatility-based stop** | Exit if loss exceeds N × volatility | More adaptive, but more complex |
| **Take-profit** | Exit if gain exceeds Y% from entry | Adds parameter, may exit winners early |
| **No explicit stop** | Position exits only on signal change or max holding period | Simplest, no additional parameters |

### 13.2 MVP Recommendation: No explicit stop-loss/take-profit in MVP

**Rationale:**
- Adding stop-loss and take-profit levels introduces additional parameters
- These parameters can be tuned to improve historical backtest results without genuine predictive value
- The max holding period (Section 14) provides a natural exit mechanism
- Signal-based exits (BUY → SELL signal) provide another exit path
- Stop-loss research is a separate question for future phases

**If included in future:**
- Must define deterministic rules
- Must be fixed before backtesting (not optimized on test set)
- Must document the overfitting risk explicitly

### 13.3 Natural Exit Mechanisms in MVP

| Exit Trigger | Description |
|-------------|-------------|
| **Max holding period expired** | Position automatically exits after max_holding_period days |
| **Opposite signal received** | BUY position exits on SELL signal |
| **NO_TRADE after holding period** | If model says HOLD after holding period, exit |

---

## 14. Holding Period

### 14.1 Maximum Holding Duration

| Parameter | MVP Default | Description |
|-----------|-------------|-------------|
| **max_holding_period** | 5 trading days | Maximum days to hold a position |

**Why 5 days:** Matches the prediction horizon (5-day label window). If the model predicted a 5-day move, holding beyond that period relies on a different prediction (the next day's model output).

### 14.2 Signal Expiry

A prediction must not remain valid indefinitely. After the prediction horizon passes, the signal expires.

| Event | Action |
|-------|--------|
| prediction_time + validity_window < current_time | Signal expires — treat as NO_TRADE for new decisions |
| Position still open after max_holding_period | Exit position (regardless of current signal) |

### 14.3 Holding Period Configuration

```yaml
holding_period:
  max_trading_days: 5
  # Signal is valid for this many days after prediction
  # After this, position should be exited
```

---

## 15. Signal Expiry

### 15.1 Expiry Logic

```
Signal Expiry Check:

1. Get prediction_timestamp (when model made prediction)
2. Get validity_window (e.g., 5 trading days)
3. Compute expiry_timestamp = prediction_timestamp + validity_window

4. If current_time > expiry_timestamp:
     → Signal is EXPIRED
     → Output: NO_TRADE / EXPIRED
     → Reason code: STALE_PREDICTION

5. If position is still open after expiry:
     → Exit position
     → Reason code: MAX_HOLDING_PERIOD_EXPIRED
```

### 15.2 Stale Prediction Handling

| Condition | Definition | Action |
|-----------|-------------|--------|
| **Stale prediction** | prediction_time + validity_window < current_time | NO_TRADE |
| **Stale market data** | current_price_timestamp + max_age < current_time | NO_TRADE |
| **Stale model** | model_version is outdated (beyond max_age) | NO_TRADE (MODEL_VERSION_INVALID) |

### 15.3 Maximum Ages (MVP Defaults)

```yaml
staleness:
  prediction_max_age_seconds: 600    # 10 minutes
  data_max_age_seconds: 300          # 5 minutes
  model_max_age_days: 30             # Model version older than 30 days → flag
```

---

## 16. Position State

### 16.1 Research State Definitions

| State | Meaning |
|-------|---------|
| **FLAT** | No open position — sitting in cash |
| **LONG** | Holding a long position (bought instrument) |
| **SHORT** | Holding a short position (sold instrument) — NOT in MVP |
| **EXIT** | Transitioning from LONG to FLAT (position being closed) |

### 16.2 MVP State Model: LONG and FLAT only

```
MVP Position States:
  FLAT → No position
  LONG → Holding long position

SHORT is NOT supported in MVP (simplification).
```

### 16.3 State Transitions

```
State Diagram:

    ┌─────────────────────────────────────────┐
    │                                         │
    │  FLAT                                   │
    │    │                                    │
    │    │ BUY signal + all filters pass      │
    │    ▼                                    │
    │  LONG                                   │
    │    │                                    │
    │    │ SELL signal                        │
    │    │ OR max holding period expired      │
    │    │ OR opposite signal received        │
    │    ▼                                    │
    │  FLAT                                   │
    │                                         │
    └─────────────────────────────────────────┘
```

### 16.4 Transition Rules

| Current State | Event | New State | Action |
|---------------|-------|-----------|--------|
| FLAT | BUY signal + filters pass | LONG | Enter position |
| FLAT | SELL signal + filters pass | FLAT | No action (no short in MVP) |
| FLAT | NO_TRADE | FLAT | No action |
| LONG | SELL signal + filters pass | FLAT | Exit position |
| LONG | BUY signal + filters pass | LONG | No action (already long) |
| LONG | NO_TRADE | LONG (if within holding period) or FLAT (if expired) | Hold or exit |
| LONG | Max holding period expired | FLAT | Exit position |

---

## 17. Conflicting Signals

### 17.1 Conflict Scenarios

| Scenario | Description |
|----------|-------------|
| **Previous BUY, new SELL** | Position is long, new signal says sell |
| **Previous SELL, new BUY** | Position is short (if supported), new signal says buy |
| **Model A says BUY, Model B says SELL** | Ensemble conflict — not in MVP |

### 17.2 MVP Conflict Resolution: Deterministic Rules

```
Conflict Resolution Rules:

Scenario 1: LONG position, new SELL signal
  → Exit position (transition to FLAT)
  → Reason: OPPOSITE_SIGNAL

Scenario 2: LONG position, new BUY signal
  → Remain LONG (no change)
  → Reason: ALREADY_IN_POSITION

Scenario 3: FLAT position, BUY signal
  → Enter LONG position
  → Reason: NEW_BUY_SIGNAL

Scenario 4: Multiple models (future)
  → Not applicable in MVP (single model only)
```

### 17.3 State-Aware Decision Logic

```
Decision depends on current state:

If FLAT:
  BUY → Enter LONG
  SELL → No action (no short in MVP)
  HOLD/NO_TRADE → Remain FLAT

If LONG:
  BUY → No action (already long)
  SELL → Exit to FLAT
  HOLD/NO_TRADE → Hold (if within holding period) or Exit (if expired)
```

---

## 18. Model Quality Gate

### 18.1 Model Validation Requirements

Before a model's predictions can be used by the Decision Engine, the model must pass quality gates:

| Gate | Check | Failure Action |
|------|-------|---------------|
| **Valid model version** | model_version exists and is registered | NO_TRADE (MODEL_VERSION_INVALID) |
| **Model passed validation** | Model training completed successfully (status = COMPLETED) | NO_TRADE (MODEL_VALIDATION_FAILED) |
| **Model is not outdated** | model_version is within max_age | Flag but may proceed (MODEL_VERSION_OLD) |
| **Compatible feature version** | feature_version used by model matches current feature_version | NO_TRADE (FEATURE_VERSION_MISMATCH) |
| **Model above quality threshold** | Model metrics meet minimum standards (e.g., accuracy > random baseline) | NO_TRADE (MODEL_BELOW_QUALITY) |

### 18.2 Model Quality Thresholds (MVP)

```
Model Quality Gates:

Required for Decision Engine to use model:
  - Model status = COMPLETED
  - Model version is registered
  - Feature version matches

Quality thresholds (research parameters):
  - Validation accuracy > random baseline (33% for 3-class)
  - Model trained within max_age_days

If thresholds not met:
  → Predictions can still be generated (for research)
  → But Decision Engine should flag and potentially abstain
  → Reason codes: MODEL_BELOW_QUALITY, MODEL_VERSION_OLD
```

### 18.3 Model Quality Gate Logic

```
Model Quality Check:

1. Load model metadata
2. Verify status == COMPLETED
3. Verify version is registered
4. Verify feature_version matches
5. Verify model_version is not too old
6. If all pass → proceed with prediction
7. If any fail → NO_TRADE with appropriate reason code
```

---

## 19. Data Quality Gate

### 19.1 Pre-Signal Data Verification

Before producing a signal, verify that the data is valid:

| Check | Condition | Failure Action |
|-------|-----------|---------------|
| **Latest data is valid** | current_price > 0, volume >= 0 | NO_TRADE (DATA_QUALITY_FAILURE) |
| **Timestamps are correct** | data_timestamp <= decision_timestamp | NO_TRADE (TIMESTAMP_MISMATCH) |
| **Required features exist** | All required features present and non-NaN | NO_TRADE (MISSING_FEATURES) |
| **No NaN/Inf** | No NaN or Inf in required inputs | NO_TRADE (DATA_QUALITY_FAILURE) |
| **Prediction aligned with data** | prediction uses data from data_timestamp | NO_TRADE (ALIGNMENT_FAILURE) |
| **Instrument is tradable** | Within research assumptions (trading hours, etc.) | NO_TRADE (INSTRUMENT_NOT_TRADABLE) |

### 19.2 Data Quality Gate Logic

```
Data Quality Check:

1. Validate current_price: > 0, not NaN, not Inf
2. Validate data_timestamp: not in future, not too old
3. Validate required features: present, non-NaN, non-Inf
4. Validate prediction alignment: prediction data_timestamp matches
5. Validate instrument: within research assumptions

If all pass → proceed to signal generation
If any fail → NO_TRADE with appropriate reason code
```

### 19.3 Integration with Backtest Engine

The data quality gate should be the same in:
- **Research/Decision Engine:** Before generating signals
- **Backtest Engine:** Before evaluating predictions (see EVALUATION_BACKTESTING_BLUEPRINT.md Section 3)

This ensures consistency between research signals and backtest evaluation.

---

## 20. Risk Score

### 20.1 Conceptual Design

A normalized research risk score (0.00–1.00) that summarizes the overall risk of taking a position at a given time.

### 20.2 Risk Score Components

| Component | Weight (conceptual) | Description |
|-----------|--------------------|-------------|
| **Volatility** | 0.25 | Higher recent volatility → higher risk |
| **Prediction Uncertainty** | 0.25 | Lower max_probability → higher risk |
| **Liquidity** | 0.15 | Lower volume / wider spread → higher risk (if available) |
| **Market Regime** | 0.15 | HIGH_VOLATILITY regime → higher risk (if available) |
| **Drawdown State** | 0.10 | Closer to max drawdown → higher risk |
| **Model Confidence** | 0.10 | Lower model quality metrics → higher risk |

### 20.3 Normalization Approach

Each component normalized to 0.00–1.00:

| Component | Normalization |
|-----------|---------------|
| Volatility | vol / max_vol (capped at 1.0) |
| Prediction Uncertainty | 1 - max_probability |
| Liquidity | (1 - volume_percentile) or spread-based |
| Market Regime | HIGH_VOL=0.8, TRENDING=0.3, RANGE=0.4, LOW_VOL=0.2 (conceptual) |
| Drawdown State | current_drawdown / max_drawdown_limit (capped at 1.0) |
| Model Confidence | 1 - model_validation_accuracy (relative to max) |

### 20.4 Risk Score Formula (Conceptual)

```
risk_score = (
    0.25 × normalized_volatility +
    0.25 × normalized_uncertainty +
    0.15 × normalized_liquidity +
    0.15 × normalized_regime +
    0.10 × normalized_drawdown +
    0.10 × normalized_model_confidence
)

Where all components are normalized to [0, 1].
```

### 20.5 Risk Score Interpretation

| Risk Score | Interpretation | Suggested Action |
|------------|----------------|-----------------|
| 0.00–0.30 | Low risk | May proceed with signal |
| 0.30–0.60 | Medium risk | Proceed with caution; consider smaller position |
| 0.60–0.80 | High risk | Be conservative; may abstain |
| 0.80–1.00 | Very high risk | Strongly consider NO_TRADE |

**Note:** Risk score thresholds are research parameters. The risk score is informational — it does not automatically veto signals (that's what risk filters are for).

---

## 21. Decision Explanation

### 21.1 Reason Codes

Every decision includes machine-readable reason codes for research and debugging.

| Code | Meaning | When Applied |
|------|---------|--------------|
| **MODEL_SIGNAL_BUY** | Model predicted BUY with sufficient confidence | BUY signal generated |
| **MODEL_SIGNAL_SELL** | Model predicted SELL with sufficient confidence | SELL signal generated |
| **MODEL_CONFIDENCE_LOW** | Model confidence below threshold | NO_TRADE |
| **HIGH_VOLATILITY** | Volatility exceeded threshold | NO_TRADE (risk filter) |
| **EXPECTED_EDGE_TOO_LOW** | Expected net edge below minimum | NO_TRADE (cost filter) |
| **STALE_PREDICTION** | Prediction expired | NO_TRADE |
| **STALE_DATA** | Market data too old | NO_TRADE |
| **DATA_QUALITY_FAILURE** | NaN, Inf, invalid values | NO_TRADE |
| **MODEL_VERSION_INVALID** | Model version not recognized | NO_TRADE |
| **MODEL_VERSION_OLD** | Model version outdated | Flag, may still proceed |
| **FEATURE_VERSION_MISMATCH** | Feature version incompatible | NO_TRADE |
| **REGIME_BLOCK** | Regime filter blocked signal | NO_TRADE (if regime filter enabled) |
| **RISK_LIMIT_REACHED** | Risk budget limit reached | NO_TRADE |
| **ALREADY_IN_POSITION** | Already long, new BUY ignored | HOLD (info only) |
| **OPPOSITE_SIGNAL** | Opposite signal received, exiting | SELL/EXIT |
| **MAX_HOLDING_EXPIRED** | Holding period expired | Exit position |
| **MODEL_BELOW_QUALITY** | Model metrics below threshold | NO_TRADE (or flag) |
| **CALIBRATION_UNVALIDATED** | Model calibration not validated | Flag, use caution with probabilities |

### 21.2 Multiple Reason Codes

A decision can have multiple reason codes:

**BUY with multiple passing checks:**
```json
{
  "signal": "BUY",
  "reason_codes": [
    "MODEL_SIGNAL_BUY",
    "EDGE_ABOVE_COST",
    "VOLATILITY_OK",
    "DATA_QUALITY_OK"
  ]
}
```

**NO_TRADE with blocking reason:**
```json
{
  "signal": "NO_TRADE",
  "reason_codes": [
    "MODEL_CONFIDENCE_LOW",
    "EDGE_BELOW_COST"
  ]
}
```

---

## 22. Decision Log

### 22.1 Decision Record Structure

Every decision must be logged with full context for reproducibility.

```python
@dataclass
class DecisionLog:
    # Identity
    decision_id: str                    # Unique decision identifier
    timestamp: str                      # When decision was made

    # Instrument
    instrument: str                     # Ticker symbol

    # Model context
    model_version: str                  # Model version used
    feature_version: str                # Feature version used
    strategy_version: str               # Decision strategy version

    # Prediction
    prediction: str                     # Model predicted class (UP/DOWN/HOLD)
    probability: float                  # Probability of predicted class
    probabilities: Dict[str, float]    # Full probability distribution
    expected_return: Optional[float]   # Expected return estimate (if available)

    # Market context
    current_price: float                # Price at decision time
    recent_volatility: float            # Recent volatility estimate
    market_regime: Optional[str]        # Regime (if available)
    data_timestamp: str                 # Timestamp of data used

    # Decision
    signal: str                         # BUY/SELL/HOLD/NO_TRADE
    confidence: float                   # Model confidence for chosen class
    position_size: Optional[float]      # Position size (if any)
    risk_score: float                   # Normalized risk score

    # Explanation
    reason_codes: List[str]             # Machine-readable reason codes
    cost_assumptions: Dict[str, float]  # Costs used in decision

    # Risk budget state
    current_exposure: int               # Number of open positions
    daily_pnl: float                    # Running daily P&L
    drawdown: float                     # Current drawdown from peak

    # Data versions
    data_version: str                   # Dataset version
```

### 22.2 Decision Log Storage

```
decisions/
├── {year}/{month}/{day}/
│   └── decisions_{date}.jsonl      # One JSON line per decision
├── metadata/
│   └── decision_schema.json        # Schema definition
```

### 22.3 Reproducibility Requirement

Every decision must be reproducible. Given the same:
- Model version
- Feature version
- Input data (price, volatility, etc.)
- Configuration (thresholds, filters, position sizing)
- Timestamp

The Decision Engine must produce the same decision.

---

## 23. Backtest Integration

### 23.1 Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    BACKTEST INTEGRATION                           │
│                                                                  │
│  Prediction Engine                                                │
│    ↓  (generates model probabilities for each timestamp)         │
│  Decision Engine                                                  │
│    ↓  (applies signal logic, risk filters, position sizing)       │
│  Backtest Engine                                                  │
│    ↓  (simulates execution with costs, computes metrics)          │
│  Evaluation Report                                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 23.2 Critical Requirement: Single Decision Logic

> **The Backtest Engine must use the exact same decision rules as the research signal generator.**

**Do NOT have separate "backtest logic" and "production logic."**

| Violation | Consequence |
|-----------|-------------|
| Different thresholds in backtest vs research | Backtest results don't reflect research signals |
| Different risk filters in backtest | Backtest may show better results than research |
| Hardcoded rules in backtest only | Cannot reproduce research decisions |

### 23.3 Integration Design

```
Shared Decision Engine Module:
  - Contains all decision logic (signal generation, risk filters, position sizing)
  - Used by both Research Decision Engine and Backtest Engine
  - Configuration-driven (same config for both)
  - Deterministic (same input → same output)

Research Flow:
  Live data → Prediction → Decision Engine → Signal for research

Backtest Flow:
  Historical data → Prediction (from stored model) → Decision Engine → Backtest Engine → Metrics
```

### 23.4 Decision Engine as Shared Module

```python
# Conceptual — NOT implementation code

class DecisionEngine:
    """Shared decision logic used by research and backtesting."""

    def __init__(self, config: DecisionConfig):
        self.config = config

    def make_decision(self, input: DecisionInput) -> Decision:
        """Apply full decision logic to produce signal."""
        self._validate_input(input)          # Data quality gate
        self._check_model_quality(input)     # Model quality gate
        self._check_staleness(input)         # Signal expiry
        signal = self._generate_signal(input) # Signal logic
        signal = self._apply_cost_filter(signal, input)  # Cost-aware
        signal = self._apply_risk_filters(signal, input)   # Risk filters
        decision = self._build_decision(signal, input)
        return decision
```

---

## 24. Research Safety

### 24.1 Mandatory Disclaimers

This MVP is NOT a financial advisory or live-trading system. The following must be clearly stated in all research outputs:

```
RESEARCH SAFETY STATEMENT:

1. Predictions are probabilistic, not deterministic.
   - Model outputs are estimates with uncertainty
   - Past accuracy does not guarantee future accuracy

2. Historical backtests do not guarantee future performance.
   - Market conditions change
   - Past patterns may not repeat
   - Backtest results are retrospective, not prospective

3. Simulated execution may differ from real execution.
   - Slippage assumptions are estimates
   - Real spreads may be wider
   - Real liquidity may be lower

4. Costs and market impact may be underestimated.
   - Transaction cost model is simplified
   - Real trading has additional frictions
   - Large positions may move markets

5. Model behavior can degrade over time.
   - Regime changes may break patterns
   - Model drift is expected
   - Continuous monitoring would be required for live use
```

### 24.2 Prohibited Claims

| Prohibited Claim | Why Prohibited |
|-----------------|----------------|
| "This strategy is profitable" | Requires live trading evidence; backtests are simulated |
| "The model predicts the market" | Overstates model capability; predictions are probabilistic |
| "Expected return of X%" | Based on historical simulation only; not a forecast |
| "Safe to trade" | No live trading evaluation; risks unknown |
| "Beats the market" | Requires proper benchmark comparison and statistical validation |

### 24.3 Research-Only Labeling

All outputs from the Decision Engine must be labeled as research:

| Output | Label |
|--------|-------|
| Decision signals | "Research signal — not a trading recommendation" |
| Backtest results | "Historical simulation — not a guarantee of future performance" |
| Risk scores | "Research risk estimate — not financial advice" |
| Position recommendations | "Paper simulation only — no live orders" |

---

## 25. Threshold Research

### 25.1 Threshold Research Rules

Thresholds are research parameters. They must be researched responsibly:

| Rule | Description |
|------|-------------|
| **Fit on training/validation only** | Thresholds must be tuned on training or validation data, never on the final test set |
| **Final test data untouched** | The final test set remains pristine for out-of-sample evaluation |
| **Threshold changes require new strategy version** | Each threshold configuration gets a new strategy_version |
| **Every threshold experiment logged** | All threshold experiments recorded with parameters and results |

### 25.2 Threshold Categories

| Threshold Type | Description | Research Method |
|---------------|-------------|-----------------|
| **Signal threshold** | P(UP) or P(DOWN) required for action | Grid search on validation data |
| **Confidence threshold** | Minimum probability for signal | Calibration analysis + validation |
| **Cost threshold** | Minimum edge over costs | Cost sensitivity analysis |
| **Risk threshold** | Risk score limit for action | Risk analysis on validation |
| **Volatility threshold** | Volatility limit for filter | Volatility analysis on validation |

### 25.3 Threshold Research Process

```
Threshold Research Process:

1. Define threshold candidate ranges
   Example: P(UP) threshold from 0.50 to 0.70 in steps of 0.05

2. For each candidate:
   a. Apply to validation data
   b. Compute metrics (signal accuracy, signal frequency, net edge)
   c. Record results

3. Select threshold based on validation performance
   - Document selection criteria
   - Record selected threshold and strategy_version

4. Freeze threshold before final test
   - Record in experiment metadata
   - Apply to test set ONCE

5. If threshold needs to change:
   → Increment strategy_version
   → Document change
   → New experiment required
```

---

## 26. Sensitivity Analysis

### 26.1 Required Sensitivity Experiments

Define experiments for:

| Parameter | Experiment | Purpose |
|-----------|-----------|---------|
| **Probability threshold** | Vary P(UP) threshold from 0.50 to 0.70 | Understand signal sensitivity to threshold |
| **Expected-return threshold** | Vary minimum edge from 5 bps to 30 bps | Understand cost sensitivity |
| **Risk threshold** | Vary risk_score limit from 0.3 to 0.7 | Understand risk sensitivity |
| **Position-size cap** | Vary fixed quantity from 0.5 to 2.0 units | Understand size sensitivity |

### 26.2 Sensitivity Analysis Protocol

```
Sensitivity Analysis Protocol:

For each parameter:
1. Define range of values to test
2. Apply each value to validation data
3. Record metrics for each value
4. Report full range — do NOT select only the best

Example: Probability Threshold Sensitivity

Threshold   | Signal Freq | Signal Acc | Net Edge | Sharpe
0.50        |   45%       |   52%      |  12 bps  |  1.15
0.55        |   32%       |   55%      |  15 bps  |  1.32
0.60        |   22%       |   58%      |  14 bps  |  1.28
0.65        |   15%       |   61%      |  11 bps  |  1.10
0.70        |    8%       |   64%      |   8 bps  |  0.92

Report all values. Do not cherry-pick the best Sharpe.
```

### 26.3 Sensitivity Reporting

Every sensitivity analysis must:
- Report the full range of values tested
- Show metrics for each value
- Not select the best result from the final test period
- Be documented in the experiment record

---

## 27. Abstention / No-Trade Policy

### 27.1 Mandatory No-Trade Capability

The system MUST be allowed to say "NO TRADE."

### 27.2 Why Abstention Matters

| Reason | Explanation |
|--------|-------------|
| **Weak evidence** | When model confidence is low, forcing a trade adds noise, not signal |
| **Cost exceedance** | When expected edge doesn't cover costs, trading loses money on average |
| **High risk** | When risk score is high, the downside may outweigh the upside |
| **Stale data** | When data is stale, predictions are unreliable |
| **Model uncertainty** | When model is uncertain, the best action may be inaction |

### 27.3 Benefits of No-Trade

| Benefit | Explanation |
|---------|-------------|
| **Reduces false signals** | Abstaining when uncertain reduces noise in the strategy |
| **Saves transaction costs** | Not trading when edge is insufficient preserves capital |
| **Reduces risk exposure** | Avoiding trades in high-risk conditions reduces drawdown risk |
| **Improves signal quality** | The signals that ARE acted upon are higher quality |
| **Honest evaluation** | Allows the system to admit when it doesn't know |

### 27.4 No-Trade as a Feature, Not a Bug

> Abstention is a feature of a responsible decision system, not a failure.

A system that trades constantly will have many low-quality signals. A system that abstains when evidence is weak will have fewer but higher-quality signals. The latter is generally preferable for risk-adjusted returns.

**The Decision Engine must be designed to prefer NO_TRADE when evidence is insufficient. This is a deliberate design choice, not an oversight.**

---

## 28. Acceptance Criteria

The blueprint is complete when:

| Criterion | Status |
|-----------|--------|
| Prediction/decision/execution separation exists | ✅ |
| Input contract exists (MVP and future inputs defined) | ✅ |
| Output contract exists (Decision object structure) | ✅ |
| Signal rules exist (BUY/SELL/HOLD/NO_TRADE logic) | ✅ |
| Cost-aware filtering exists (expected net edge calculation) | ✅ |
| Risk filters exist (8 filter types with thresholds) | ✅ |
| Stale-data protection exists (staleness checks) | ✅ |
| Model-quality gate exists (version, validation, compatibility checks) | ✅ |
| Position-sizing strategy exists (fixed quantity MVP) | ✅ |
| Exposure limits exist (risk budget with daily loss, drawdown guard) | ✅ |
| Signal expiry exists (validity window, stale prediction handling) | ✅ |
| Decision logging exists (full DecisionLog structure) | ✅ |
| No-trade behavior exists (mandatory abstention policy) | ✅ |
| Backtest integration exists (shared decision logic requirement) | ✅ |
| Research safety statements exist (disclaimers, prohibited claims) | ✅ |
| Threshold research methodology exists (validation-only, versioned) | ✅ |
| Sensitivity analysis design exists (4 parameter types) | ✅ |
| Future extensions reserved (8 areas) | ✅ |
| Consistency check completed (cross-referenced with 11 documents) | ✅ |

---

## 29. Future Extensions

### 29.1 Reserved Architecture

The following capabilities are reserved for future phases. The current architecture provides extension points but does NOT implement them.

| Extension | Description | Current State |
|-----------|-------------|---------------|
| **Portfolio optimization** | Optimize allocation across multiple instruments | Single-instrument only (MVP) |
| **Advanced risk models** | VaR, CVaR, factor risk models | Simple risk score only (MVP) |
| **VaR / CVaR** | Value at Risk, Conditional Value at Risk | Not implemented (future) |
| **Factor exposure** | Control for factor exposures (value, momentum, etc.) | Not implemented (future) |
| **Options risk** | Delta, gamma, vega risk for options positions | Not applicable (MVP — no options) |
| **Order-book liquidity** | Liquidity assessment from L2 data | Not applicable (MVP — L1 data only) |
| **Market impact** | Model slippage based on order size and liquidity | Fixed slippage only (MVP) |
| **Portfolio-level constraints** | Risk limits across portfolio, not per position | Single-position only (MVP) |
| **Dynamic risk allocation** | Adjust risk budget based on market conditions | Fixed risk budget (MVP) |
| **Autonomous risk adaptation** | System adjusts risk parameters automatically | Manual configuration only (MVP) |

### 29.2 Extension Points

| Extension | What Changes | What Stays |
|-----------|-------------|------------|
| **Portfolio backtesting** | Position manager handles multiple instruments, correlation awareness | Decision logic, risk filters, signal generation |
| **VaR/CVaR** | Risk score replaced with distributional risk metrics | Risk budget concept, decision logging |
| **Dynamic position sizing** | Position size becomes a function of volatility, conviction, risk budget | Fixed quantity as baseline fallback |
| **Regime-based filtering** | Regime filter enabled with configurable rules per regime | Decision flow, risk filter architecture |
| **Multi-model ensemble** | Multiple model predictions aggregated before decision | Single-model path remains as baseline |

---

## 30. Consistency Check

### 30.1 Cross-Reference with Previous Documents

| Document | Check | Status | Notes |
|----------|-------|--------|-------|
| **PRD_MVP.md** | FR-PM-01: Generate prediction probabilities | ✅ Consistent | Decision Engine consumes probabilities |
| **PRD_MVP.md** | FR-PM-02: Point predictions | ✅ Consistent | Signal generation uses point predictions |
| **PRD_MVP.md** | FR-BT-01: Walk-forward backtesting | ✅ Consistent | Decision Engine integrates with backtest |
| **PRD_MVP.md** | FR-BT-03: Transaction costs | ✅ Consistent | Cost-aware decision uses same cost model |
| **PRD_MVP.md** | FR-BT-07: No profitability claims | ✅ Consistent | Research safety section enforces this |
| **SYSTEM_ARCHITECTURE.md** | Decision Engine / Risk Engine placeholder | ✅ Consistent | This blueprint defines the placeholder |
| **TRAINING_PIPELINE_BLUEPRINT.md** | Experiment types | ✅ Consistent | Decision strategy version aligns with experiment tracking |
| **TRAINING_PIPELINE_BLUEPRINT.md** | Metric policy (ML vs financial separation) | ✅ Consistent | Decision Engine produces signals, not financial metrics |
| **EVALUATION_BACKTESTING_BLUEPRINT.md** | Position model (LONG/FLAT) | ✅ Consistent | Both use LONG/FLAT only for MVP |
| **EVALUATION_BACKTESTING_BLUEPRINT.md** | Trading rules (entry/exit conditions) | ✅ Consistent | Decision Engine defines rules, Backtest Engine applies them |
| **EVALUATION_BACKTESTING_BLUEPRINT.md** | Execution timing (close-to-close) | ✅ Consistent | Decision Engine uses same execution assumptions |
| **EVALUATION_BACKTESTING_BLUEPRINT.md** | Transaction cost model | ✅ Consistent | Same cost assumptions used |
| **EVALUATION_BACKTESTING_BLUEPRINT.md** | Backtest engine architecture (8 modules) | ✅ Consistent | Decision Engine feeds into Backtest Engine |
| **EVALUATION_BACKTESTING_BLUEPRINT.md** | Failure conditions | ✅ Consistent | Data quality gate aligns with backtest failure conditions |
| **LABEL_GENERATION_BLUEPRINT.md** | 5-day prediction horizon | ✅ Consistent | Max holding period matches horizon |
| **LABEL_GENERATION_BLUEPRINT.md** | Classification target (UP/DOWN/HOLD) | ✅ Consistent | Decision Engine operates on classification probabilities |
| **LABEL_GENERATION_BLUEPRINT.md** | Threshold research methodology | ✅ Consistent | Threshold research rules align |
| **BASELINE_MODEL_BLUEPRINT.md** | Model versioning | ✅ Consistent | Model version format matches |
| **BASELINE_MODEL_BLUEPRINT.md** | LogisticRegression + RandomForest | ✅ Consistent | Decision Engine works with both model types |
| **DATASET_BUILDER_BLUEPRINT.md** | Dataset versioning | ✅ Consistent | Data version tracking aligns |
| **FEATURE_ENGINEERING_BLUEPRINT.md** | Regime features (future) | ✅ Consistent | Regime as optional input, not MVP filter |

### 30.2 Key Reconciliations

**Decision Engine vs Backtest Engine:**

| Aspect | Decision Engine (this doc) | Backtest Engine (EVALUATION_BACKTESTING_BLUEPRINT.md) |
|--------|---------------------------|--------------------------------------------------------|
| **Role** | Produce research signals from model predictions | Simulate trading and compute financial metrics |
| **Output** | Decision (BUY/SELL/HOLD/NO_TRADE) + reason codes | Trade ledger, equity curve, financial metrics |
| **Risk controls** | Risk filters, risk budget, position sizing | Execution simulation, cost application |
| **Relationship** | Upstream — produces signals | Downstream — consumes signals, simulates execution |

**The Decision Engine defines WHAT to do. The Backtest Engine defines HOW to evaluate what was done.**

### 30.3 Conflicts Found

**None.** All documents are consistent. This blueprint adds the Decision Engine layer that was implicitly required but not yet documented.

### 30.4 Required Changes

**None.** No changes to previous architecture required.

---

## 31. Deliverables

| Deliverable | Status | Description |
|-------------|--------|-------------|
| `docs/RISK_DECISION_ENGINE_BLUEPRINT.md` | ✅ This document | Complete risk management and decision engine design |
| `docs/CURRENT_STATE.md` | ⏳ To update | Add new blueprint to documentation list |
| `docs/DECISIONS.md` | ⏳ To update | Add ADR if new architectural decision introduced |

---

## 32. Stop Condition

**This document is research and architecture specification only.**

**DO NOT:**
- Write implementation code
- Connect broker APIs
- Execute trades
- Train models
- Run optimization
- Implement live risk controls
- Build LLM agents

**STOP after documentation is complete.**

---

## Final Report

### A. Recommended MVP Decision Flow

```
Model Prediction (P(UP), P(DOWN), P(HOLD))
    ↓
Data Quality Gate (validate inputs, check for NaN/Inf, timestamps)
    ↓
Model Quality Gate (verify model version, status, feature compatibility)
    ↓
Signal Logic (determine predicted class, check confidence thresholds)
    ↓
Cost-Aware Filter (compute expected net edge, compare to minimum)
    ↓
Risk Filters (volatility, staleness, uncertainty, data quality)
    ↓
Position State Logic (FLAT → BUY, LONG → SELL/hold)
    ↓
Final Decision (BUY/SELL/HOLD/NO_TRADE + reason codes + risk score)
```

### B. Primary Signal Methodology

**Probability threshold-based signal generation:**
- BUY: P(UP) >= 0.55
- SELL: P(DOWN) >= 0.55
- HOLD: Neither threshold met, but moderate confidence
- NO_TRADE: Confidence below 0.50, or edge below cost, or risk filter triggered

Thresholds are research parameters — tuned on validation data only, frozen before final test.

### C. No-Trade Rules

**Mandatory NO_TRADE conditions (any one triggers abstention):**

1. Model confidence below minimum threshold (P < 0.50)
2. Expected net edge below minimum (less than 15 bps after costs)
3. Risk filter triggered (high volatility, stale data, data quality failure, etc.)
4. Model quality gate failed (invalid version, mismatched features)
5. Risk budget limit reached (daily loss, max drawdown)
6. Signal expired (past validity window)
7. Data quality gate failed (NaN, Inf, invalid values)

**The system prefers NO_TRADE when evidence is weak. This is a feature, not a failure.**

### D. Risk-Filter Strategy

**8 risk filters (any one failing → NO_TRADE):**

1. Extreme volatility (> 60% annualized)
2. Data quality failure (NaN, Inf, invalid values)
3. Stale prediction (older than 10 minutes)
4. Stale market data (older than 5 minutes)
5. Model uncertainty (max probability < 0.45)
6. Invalid prediction (probabilities out of range)
7. Market closure (outside trading hours — optional)
8. Excessive spread/slippage (optional)

Risk filters are mandatory — they cannot be bypassed by strong model predictions.

### E. Position-Sizing Recommendation

**Fixed quantity: 1 unit per trade.**

Simplest approach with no additional parameters. Alternative: fixed notional ($X per trade). More sophisticated approaches (volatility-adjusted, risk-budget sizing) are future research questions.

### F. Signal-Expiry Methodology

**Validity window = prediction horizon = 5 trading days.**

After prediction_time + 5 days, signal expires. Expired signals → NO_TRADE. Positions still open after max holding period → exit regardless of current signal.

Stale data check: market data older than 5 minutes → NO_TRADE.

### G. Model/Data Quality Gates

**Model Quality Gate:**
- Model status = COMPLETED
- Model version registered
- Feature version matches
- Model not too old (within 30 days)

**Data Quality Gate:**
- current_price > 0, not NaN/Inf
- data_timestamp not in future, not too old
- Required features present, non-NaN, non-Inf
- Prediction aligned with data timestamp
- Instrument within research assumptions

Failure of either gate → NO_TRADE with appropriate reason code.

### H. Key Risks

| Risk | Mitigation |
|------|------------|
| Probabilities not calibrated | Calibration validation required; use higher thresholds if uncalibrated |
| Regime detection noisy at daily frequency | Regime filter not enabled in MVP; future enhancement |
| Fixed position sizing not risk-adjusted | Simple baseline; future volatility-adjusted sizing |
| Stop-loss absence may increase drawdown | Max holding period provides natural exit; future stop-loss research |
| Single-instrument focus may not generalize | Document as limitation; future multi-instrument research |
| Threshold overfitting to validation data | Threshold research rules: validation only, frozen before test |
| No live execution evaluation | Research safety disclaimers; paper simulation only |

### I. Contradictions with Previous Documents

**None found.** Cross-checked against 11 previous documents (PRD_MVP.md, SYSTEM_ARCHITECTURE.md, TRAINING_PIPELINE_BLUEPRINT.md, EVALUATION_BACKTESTING_BLUEPRINT.md, DATASET_BUILDER_BLUEPRINT.md, LABEL_GENERATION_BLUEPRINT.md, BASELINE_MODEL_BLUEPRINT.md, and others). All consistent.

### J. Exact Next Recommended Task

1. **Update CURRENT_STATE.md** — Add RISK_DECISION_ENGINE_BLUEPRINT.md to the documentation list (17 docs total)
2. **Add ADR-0018 to DECISIONS.md** — Record the Risk Management & Decision Engine architecture decision
3. **Continue with remaining pre-implementation tasks:**
   - Fix config inconsistency (`label_type: regression` → `classification` in config/default.yaml)
   - Add model configuration to config/default.yaml per BASELINE_MODEL_BLUEPRINT.md Appendix A