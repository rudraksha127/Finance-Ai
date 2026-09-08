# EVALUATION & WALK-FORWARD BACKTESTING BLUEPRINT — Finance AI MVP

> Rigorous evaluation framework that determines whether a trained prediction model has genuine out-of-sample predictive value under realistic market assumptions.
> Distinguishes ML performance, signal quality, strategy performance, risk characteristics, and robustness.

---

## Table of Contents

1. [Primary Objective](#1-primary-objective)
2. [Evaluation Layers](#2-evaluation-layers)
3. [Data Quality Gate](#3-data-quality-gate)
4. [Prediction Metrics (Classification)](#4-prediction-metrics-classification)
5. [Prediction Metrics (Probability Outputs)](#5-prediction-metrics-probability-outputs)
6. [Regression Metrics](#6-regression-metrics)
7. [Signal Evaluation](#7-signal-evaluation)
8. [Walk-Forward Validation](#8-walk-forward-validation)
9. [Temporal Leakage Controls](#9-temporal-leakage-controls)
10. [Execution Timing](#10-execution-timing)
11. [Transaction Cost Model](#11-transaction-cost-model)
12. [Slippage Model](#12-slippage-model)
13. [Position Model](#13-position-model)
14. [Trading Rules](#14-trading-rules)
15. [Core Financial Metrics](#15-core-financial-metrics)
16. [Equity Curve](#16-equity-curve)
17. [Benchmarks](#17-benchmarks)
18. [Ablation Testing](#18-ablation-testing)
19. [Robustness Testing](#19-robustness-testing)
20. [Cost Sensitivity](#20-cost-sensitivity)
21. [Slippage Sensitivity](#21-slippage-sensitivity)
22. [Threshold Sensitivity](#22-threshold-sensitivity)
23. [Model Comparison](#23-model-comparison)
24. [Statistical Significance](#24-statistical-significance)
25. [Overfitting / Backtest Overfitting](#25-overfitting--backtest-overfitting)
26. [Final Test Protocol](#26-final-test-protocol)
27. [Backtest Outputs](#27-backtest-outputs)
28. [Trade Ledger](#28-trade-ledger)
29. [Reproducibility](#29-reproducibility)
30. [Backtest Engine Architecture](#30-backtest-engine-architecture)
31. [Failure Conditions](#31-failure-conditions)
32. [Report Structure](#32-report-structure)
33. [MVP Acceptance Criteria](#33-mvp-acceptance-criteria)
34. [Future Extensions](#34-future-extensions)
35. [Consistency Check](#35-consistency-check)
36. [Deliverables](#36-deliverables)
37. [Stop Condition](#37-stop-condition)

---

## 1. Primary Objective

Design an evaluation system that determines whether a trained prediction model has genuine out-of-sample predictive value under realistic market assumptions.

**Core principle:**

> A model with good classification metrics is NOT automatically a profitable trading strategy.

The framework must distinguish and evaluate separately:

| Layer | What It Evaluates | Key Question |
|-------|-------------------|--------------|
| **ML Predictive Performance** | Classification/regression accuracy | Does the model predict better than random? |
| **Signal Quality** | How probabilities become actionable signals | Do predicted probabilities translate to useful directional bias? |
| **Strategy Performance** | Simulated trading with costs | Would this signal generate positive risk-adjusted returns after costs? |
| **Risk Characteristics** | Drawdown, volatility, tail risk | What is the worst-case behavior? |
| **Robustness** | Performance across regimes and assumptions | Does performance hold up under stress? |

---

## 2. Evaluation Layers

### 2.1 Five-Layer Evaluation Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       EVALUATION LAYERS                                  │
│                                                                          │
│  Layer 5: Robustness / Stress Testing                                    │
│    ↑                                                                    │
│  Layer 4: Strategy / Backtest Performance                                │
│    ↑                                                                    │
│  Layer 3: Signal Quality                                                 │
│    ↑                                                                    │
│  Layer 2: Prediction Quality                                             │
│    ↑                                                                    │
│  Layer 1: Data Quality                                                   │
│    │                                                                    │
│  Every layer depends on the layer below. Fail at any layer = stop.       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Layer Responsibilities

| Layer | Responsibility | Input | Output | Pass/Fail |
|-------|---------------|-------|--------|-----------|
| **Layer 1: Data Quality** | Verify dataset integrity, versions, splits, alignment | Dataset files + metadata | Quality report, pass/fail flag | HARD GATE |
| **Layer 2: Prediction Quality** | Evaluate model predictions against actuals | Model predictions + true labels | ML metrics (accuracy, precision, recall, F1, ROC-AUC, calibration) | SOFT GATE |
| **Layer 3: Signal Quality** | Convert probabilities to signals, evaluate signal characteristics | Prediction probabilities + thresholds | Signal accuracy, signal frequency, signal purity | INFORMATIONAL |
| **Layer 4: Strategy / Backtest Performance** | Simulate trading with costs, compute financial metrics | Signals + execution model + cost model | Equity curve, financial metrics, trade ledger | PRIMARY EVALUATION |
| **Layer 5: Robustness / Stress Testing** | Test across regimes, cost assumptions, slippage, thresholds | Strategy results + variants | Robustness report, sensitivity tables | CONTEXTUAL |

### 2.3 Layer Boundaries

| Boundary | Rule |
|----------|------|
| Layer 1 → Layer 2 | Data quality must pass before any prediction evaluation |
| Layer 2 → Layer 3 | Predictions must be evaluated before signals are derived |
| Layer 3 → Layer 4 | Signals must be defined before strategy simulation |
| Layer 4 → Layer 5 | Strategy results must exist before robustness testing |
| Within Layer 4 | ML metrics and financial metrics are computed separately and reported separately |

---

## 3. Data Quality Gate

### 3.1 Gate Purpose

Before any evaluation begins, verify that the data is trustworthy. A failed data-quality gate MUST stop evaluation. No partial results. No silent corrections.

### 3.2 Required Checks

| Check ID | Check | Severity | Fail Action |
|-----------|-------|----------|-------------|
| DQ-01 | Dataset file exists and is readable | ERROR | Abort |
| DQ-02 | Dataset SHA-256 hash matches recorded hash | ERROR | Abort — dataset may be corrupted |
| DQ-03 | Timestamps in ascending chronological order | ERROR | Abort |
| DQ-04 | No duplicate timestamps | ERROR | Abort |
| DQ-05 | No null values in required columns (open, high, low, close, volume) | ERROR | Abort |
| DQ-06 | Price values valid (open > 0, high > 0, low > 0, close > 0, volume >= 0) | ERROR | Abort |
| DQ-07 | Feature version matches expected | ERROR | Abort — version mismatch |
| DQ-08 | Label version matches expected | ERROR | Abort — version mismatch |
| DQ-09 | Dataset version matches expected | ERROR | Abort — version mismatch |
| DQ-10 | Train/validation/test splits are chronological (train_end < val_start < test_start) | ERROR | Abort |
| DQ-11 | No temporal overlap between splits | ERROR | Abort |
| DQ-12 | Timestamps align between features and labels | ERROR | Abort |
| DQ-13 | Record count matches metadata | ERROR | Abort — dataset may be corrupted |
| DQ-14 | Feature count matches expected | ERROR | Abort |
| DQ-15 | Minimum rows in each split (train >= 100, val >= 20, test >= 20) | WARNING | Log warning, may proceed with caution |

### 3.3 Data Quality Report

Every backtest starts with a data quality report:

```json
{
  "data_quality_gate": {
    "passed": true,
    "checks_run": 15,
    "checks_passed": 15,
    "checks_failed": 0,
    "checks_warned": 0,
    "dataset_version": "v0.1",
    "feature_version": "v0.1",
    "label_version": "v0.1",
    "train_rows": 1725,
    "val_rows": 370,
    "test_rows": 370,
    "train_period": {"start": "2016-03-15", "end": "2022-12-31"},
    "val_period": {"start": "2023-01-01", "end": "2023-12-31"},
    "test_period": {"start": "2024-01-01", "end": "2025-12-31"},
    "issues": []
  }
}
```

---

## 4. Prediction Metrics (Classification)

### 4.1 Required Metrics

For classification models (UP/DOWN/HOLD):

| Metric | Formula | Description | When to Use |
|--------|---------|-------------|-------------|
| **Accuracy** | correct / total | Overall correct prediction rate | General overview (but don't optimize solely for this) |
| **Precision (UP)** | TP_UP / (TP_UP + FP_UP) | Of predicted UP, how many were actually UP | When false UP signals are costly |
| **Precision (DOWN)** | TP_DOWN / (TP_DOWN + FP_DOWN) | Of predicted DOWN, how many were actually DOWN | When false DOWN signals are costly |
| **Precision (HOLD)** | TP_HOLD / (TP_HOLD + FP_HOLD) | Of predicted HOLD, how many were actually HOLD (small move) | When avoiding false trading signals matters |
| **Recall (UP)** | TP_UP / (TP_UP + FN_UP) | Of actual UP moves, how many were predicted UP | When missing UP moves is costly |
| **Recall (DOWN)** | TP_DOWN / (TP_DOWN + FN_DOWN) | Of actual DOWN moves, how many were predicted DOWN | When missing DOWN moves is costly |
| **Recall (HOLD)** | TP_HOLD / (TP_HOLD + FN_HOLD) | Of actual small moves, how many were predicted HOLD | When correctly identifying non-tradable moves matters |
| **F1 (per class)** | 2 × P × R / (P + R) | Harmonic mean of precision and recall per class | Balanced view of per-class performance |
| **Macro F1** | mean(F1_UP, F1_DOWN, F1_HOLD) | Average F1 across all classes | Overall performance when classes may be imbalanced |
| **Weighted F1** | mean(F1_i, weights=class_freq_i) | F1 weighted by class frequency | When class imbalance is significant |
| **Confusion Matrix** | 3×3 matrix | Full breakdown of predictions vs actuals | Detailed error analysis |

### 4.2 ROC-AUC (3-Class)

For 3-class classification, compute one-vs-rest ROC-AUC:

| Metric | Description |
|--------|-------------|
| **ROC-AUC (UP vs rest)** | Can model distinguish UP from non-UP? |
| **ROC-AUC (DOWN vs rest)** | Can model distinguish DOWN from non-DOWN? |
| **ROC-AUC (HOLD vs rest)** | Can model distinguish HOLD from non-HOLD? |
| **Macro ROC-AUC** | Mean of the three one-vs-rest AUCs |

**Note:** ROC-AUC is valid for classification but should not be the sole optimization target. A model can have high AUC but poor calibration or poor precision at actionable thresholds.

### 4.3 PR-AUC

| Metric | Description | When Useful |
|--------|-------------|------------|
| **PR-AUC (UP vs rest)** | Area under precision-recall curve for UP class | When UP class is rare (imbalanced) |
| **PR-AUC (DOWN vs rest)** | Area under precision-recall curve for DOWN class | When DOWN class is rare |
| **PR-AUC (HOLD vs rest)** | Area under precision-recall curve for HOLD class | When HOLD class is rare |

**Note:** PR-AUC is more informative than ROC-AUC when classes are imbalanced. For MVP with roughly balanced classes (33/33/33), ROC-AUC is sufficient but PR-AUC provides additional context.

### 4.4 Class-wise Performance Table

Every evaluation reports per-class performance:

```
Per-Class Performance (Validation Set):
┌─────────┬──────────┬──────────┬──────────┬──────────┐
│ Class   │ Precision│ Recall   │ F1       │ Support  │
├─────────┼──────────┼──────────┼──────────┼──────────┤
│ UP      │  0.55    │  0.50    │  0.52    │   123    │
│ DOWN    │  0.50    │  0.48    │  0.49    │   118    │
│ HOLD    │  0.52    │  0.55    │  0.53    │   129    │
├─────────┼──────────┼──────────┼──────────┼──────────┤
│ Macro   │  0.52    │  0.51    │  0.51    │   370    │
│ Weighted│  0.52    │  0.51    │  0.52    │   370    │
└─────────┴──────────┴──────────┴──────────┴──────────┘
```

---

## 5. Prediction Metrics (Probability Outputs)

### 5.1 When Applicable

When the model produces probability outputs (P(UP), P(DOWN), P(HOLD)) rather than just point predictions, additionally evaluate:

| Metric | Formula | Description |
|--------|---------|-------------|
| **Calibration** | See calibration curves below | Do predicted probabilities match observed frequencies? |
| **Brier Score** | mean((p_i - y_i)^2) | Mean squared error of probability predictions (lower is better) |
| **Brier Skill Score** | 1 - Brier / Brier_climatology | Improvement over predicting base rate |

### 5.2 Calibration Evaluation

**Calibration Curve (Reliability Diagram):**

```
┌─────────────────────────────────────────────────────────────────┐
│                    CALIBRATION CURVE                             │
│                                                                  │
│  Observed Frequency                                               │
│    ^                                                              │
│  1.0 │           ●                                                 │
│      │        ●                                                      │
│  0.8 │     ●                                                         │
│      │  ●                                                            │
│  0.6 │●                                                              │
│      │_____________________________________________________________  │
│      0.0   0.2   0.4   0.6   0.8   1.0                             │
│                   Predicted Probability                            │
│                                                                  │
│  Perfect calibration: points lie on diagonal                      │
│  Overconfident: points below diagonal (predicted too high)        │
│  Underconfident: points above diagonal (predicted too low)        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Procedure:**
1. Bin predictions by probability (e.g., 10 bins: 0-0.1, 0.1-0.2, ..., 0.9-1.0)
2. For each bin, compute observed frequency of the predicted class
3. Plot observed frequency vs mean predicted probability
4. Compute expected calibration error (ECE): weighted average of |observed - predicted| across bins

### 5.3 Probability Reliability

| Question | Metric | Good Value |
|----------|--------|------------|
| Are probabilities calibrated? | Calibration curve closeness to diagonal | Points near diagonal |
| Are probabilities informative? | Brier score | Lower than climatology (base rate) |
| Is the model better than guessing base rate? | Brier Skill Score | Positive (> 0) |
| What is the entropy of predictions? | Mean prediction entropy | Lower = more confident, but check calibration |

---

## 6. Regression Metrics

### 6.1 Applicability

These metrics apply when the system supports future-return regression (as a future extension, not MVP classification). Document when each is appropriate.

| Metric | Formula | Appropriate When | Not Appropriate When |
|--------|---------|-----------------|---------------------|
| **MAE** | mean(\|y_pred - y_true\|) | General-purpose error magnitude | When large errors should be penalized more |
| **RMSE** | sqrt(mean((y_pred - y_true)^2)) | When large errors are particularly costly | When outliers dominate interpretation |
| **MAPE** | mean(\|(y_pred - y_true) / y_true\|) × 100 | When percentage errors are interpretable | When y_true can be near zero (division instability) |
| **Correlation (Pearson)** | corr(y_pred, y_true) | When ranking matters more than exact value | When absolute accuracy matters |
| **Rank Correlation (Spearman)** | corr(rank(y_pred), rank(y_true)) | When relative ordering matters (e.g., ranking stocks) | When exact return magnitudes matter |
| **Directional Accuracy** | mean(sign(y_pred) == sign(y_true)) | When sign prediction is the goal | When magnitude prediction is also needed |

### 6.2 Directional Accuracy from Regression

Even for regression models, evaluate the derived classification performance:

```
directional_accuracy = mean(sign(y_pred) == sign(y_true))

Where:
  y_true = actual future return
  y_pred = predicted future return
  sign(x) = +1 if x > 0, -1 if x < 0, 0 if x == 0
```

This bridges regression predictions to the classification framework used for signal generation.

---

## 7. Signal Evaluation

### 7.1 Signal Definition

Raw model probabilities must be converted to actionable signals through a defined threshold methodology.

```
Probability Output
    ↓
Threshold Application
    ↓
Signal
```

### 7.2 Signal Types

| Signal | Definition | Action |
|--------|-----------|--------|
| **BUY / UP** | P(UP) > threshold_buy | Enter long position |
| **SELL / DOWN** | P(DOWN) > threshold_sell | Enter short position (if supported) or avoid |
| **HOLD / NO-TRADE** | Neither threshold met | Sit in cash / no position |

### 7.3 Threshold Selection Methodology

**CRITICAL RULE: Thresholds must be selected using validation data only. The final test set must NOT be used to optimize thresholds.**

**Methodology:**

```
1. Define threshold candidate range
   Example: P(UP) threshold from 0.30 to 0.70 in steps of 0.05

2. For each candidate threshold:
   a. Apply to validation set
   b. Compute signal metrics (signal accuracy, signal frequency, precision)
   c. Record results

3. Select threshold based on validation performance
   Options:
   - Maximize F1 at threshold
   - Maximize precision at acceptable recall
   - Maximize information coefficient
   - Choose simplest threshold near optimal (e.g., round number)

4. Freeze threshold before final test evaluation
   Record: threshold_value, selection_method, validation_performance

5. Apply frozen threshold to test set ONCE
   Do NOT revisit or adjust after seeing test results
```

### 7.4 Threshold Sensitivity Documentation

Before final test, report threshold sensitivity on validation data:

```
Threshold Sensitivity (Validation Set):
┌─────────────────┬──────────┬──────────┬──────────┬─────────────┐
│ Threshold       │  Signal  │  Signal  │  Signal  │  Precision  │
│ (P(UP) > thresh)│  Count   │  Accuracy│  Frequency│  (of signal)│
├─────────────────┼──────────┼──────────┼──────────┼─────────────┤
│ 0.30            │   250    │  0.42    │  0.68    │  0.48       │
│ 0.40            │   180    │  0.48    │  0.49    │  0.53       │
│ 0.50 (default)  │   120    │  0.55    │  0.32    │  0.61       │
│ 0.60            │    75    │  0.58    │  0.20    │  0.64       │
│ 0.70            │    40    │  0.61    │  0.11    │  0.67       │
└─────────────────┴──────────┴──────────┴──────────┴─────────────┘
```

---

## 8. Walk-Forward Validation

### 8.1 Purpose

Walk-forward validation simulates realistic out-of-sample evaluation by training on historical data, testing on subsequent data, then rolling forward.

### 8.2 Two Approaches

#### Expanding Window

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXPANDING WINDOW                               │
│                                                                  │
│  Fold 1:                                                         │
│    Train: [t0 ────────────────► t1]   (growing)                  │
│    Test:  [t1 ──► t2]                                        │
│                                                                  │
│  Fold 2:                                                         │
│    Train: [t0 ────────────────► t2]   (growing)                  │
│    Test:  [t2 ──► t3]                                        │
│                                                                  │
│  Fold N:                                                         │
│    Train: [t0 ────────────────► tN]   (full history)             │
│    Test:  [tN ──► tN+1]                                     │
│                                                                  │
│  Characteristics:                                                │
│    + Uses all available history                                  │
│    + Mimics real-world "train once, test on new data"           │
│    - Training set grows over time                                │
│    - Old data may become less relevant                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Rolling Window

```
┌─────────────────────────────────────────────────────────────────┐
│                    ROLLING WINDOW                                 │
│                                                                  │
│  Fold 1:                                                         │
│    Train: [t0 ──► t1]   (fixed size)                            │
│    Test:  [t1 ──► t2]                                       │
│                                                                  │
│  Fold 2:                                                         │
│    Train: [t1 ──► t2]   (fixed size, slid forward)              │
│    Test:  [t2 ──► t3]                                       │
│                                                                  │
│  Fold N:                                                         │
│    Train: [tN-1 ──► tN]   (most recent window)                  │
│    Test:  [tN ──► tN+1]                                    │
│                                                                  │
│  Characteristics:                                                │
│    + Training set size constant                                  │
│    + Focuses on recent market conditions                         │
│    - Discards older data (may lose important history)           │
│    - More computationally intensive if many folds                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 8.3 MVP Recommendation

**MVP Approach: Expanding window walk-forward.**

**Justification:**

| Factor | Expanding Window | Rolling Window |
|--------|-----------------|---------------|
| **Data efficiency** | ✅ Uses all available history | ⚠️ Discards old data |
| **Realism** | ✅ Mimics accumulating historical data | ⚠️ Artificially limits history |
| **Simplicity** | ✅ Easier to implement and understand | ⚠️ More parameters (window size) |
| **Computational cost** | ✅ Fewer folds for same period | ⚠️ More folds possible |
| **MVP appropriateness** | ✅ Recommended | ⚠️ Future enhancement |

**Default parameters (per PRD_MVP.md FR-BT-02):**

| Parameter | Default Value | Description |
|-----------|---------------|-------------|
| Train window | 252 periods | ~1 year of trading data |
| Test window | 21 periods | ~1 month of trading data |
| Step size | 21 periods | Slide forward by ~1 month |

**Fold generation:**

```
Fold 1:
  Train: 2020-01-01 to 2020-12-31 (252 periods)
  Test:  2021-01-01 to 2021-01-31 (21 periods)

Fold 2:
  Train: 2020-01-01 to 2021-01-31 (252 + 21 = 273 periods, expanding)
  Test:  2021-02-01 to 2021-03-01 (21 periods)

Fold 3:
  Train: 2020-01-01 to 2021-03-01 (expanding further)
  Test:  2021-03-02 to 2021-04-01

... continue until test window reaches end of data
```

### 8.4 Comparison: Expanding vs Rolling for MVP

| Criterion | Expanding (MVP) | Rolling (Future) |
|-----------|-----------------|-----------------|
| Historical data usage | All data | Fixed window |
| Regime adaptation | Implicit (more recent data has more weight due to recency in test) | Explicit (window can be tuned) |
| Implementation complexity | Lower | Higher |
| Number of folds | Fewer | More possible |
| Recommended for MVP | ✅ Yes | ❌ Not for MVP |

---

## 9. Temporal Leakage Controls

### 9.1 Leakage Risks in Backtesting

| Risk | Description | Prevention |
|------|-------------|------------|
| **Look-ahead bias** | Using future information in features or predictions | Strict temporal separation; features only from ≤ T |
| **Overlapping-label contamination** | Adjacent test periods share label information due to forward-looking labels | Purge training rows whose labels overlap with test period |
| **Future feature leakage** | Features accidentally computed with future data | Feature engineering blueprint enforces past-only features |
| **Future scaling** | Scaler fitted on all data including test period | Fit scaler on training fold only; apply to test fold |
| **Threshold leakage** | Thresholds optimized on test set | Select thresholds on validation only; freeze before test |
| **Feature-selection leakage** | Features selected based on test performance | Feature selection on training/validation only |
| **Hyperparameter leakage** | Hyperparameters tuned on test set | Hyperparameter selection on validation only |

### 9.2 Purge Windows

**Purpose:** Remove training rows whose forward-looking labels overlap with the test period.

```
Example:
  Label window = 5 days
  Test starts: 2021-01-15

  Training row at 2021-01-10 has label using close at 2021-01-15
  This label overlaps with test period!

  Purge rule:
    Remove training rows where: train_timestamp + label_window >= test_start

  Example calculation:
    Test starts: 2021-01-15
    Label window: 5 days
    Purge training rows after: 2021-01-15 - 5 = 2021-01-10
    Keep training rows up to: 2021-01-09
```

**When required:**
- ALWAYS required for walk-forward backtesting with forward-looking labels
- NOT required for static split evaluation (no overlap by construction)

### 9.3 Embargo Periods

**Purpose:** Add a gap between training and test to prevent any residual information leakage.

```
Timeline with Embargo:

  ├───────────────┤    gap    ├──────────┤
  │     TRAIN     │ ◄─embargo─▶│   TEST   │
  ├───────────────┤            ├──────────┤

  Embargo period: 0 for MVP daily data
  Embargo period: label_window for intraday data (future)
```

**MVP recommendation: Embargo = 0 for daily data.**

Rationale:
- Daily data has natural spacing (no intraday leakage risk)
- Purge windows handle the label overlap issue
- Embargo is more critical for intraday data with overlapping windows
- Document as future enhancement for intraday backtesting

### 9.4 Leakage Verification Checks

Before accepting backtest results, verify:

| Check | Method | Pass Criteria |
|-------|--------|---------------|
| **Temporal ordering** | Verify all timestamps in train < all timestamps in test | TRUE |
| **No feature leakage** | Verify features at time T don't use data from > T | Verified by feature engineering blueprint |
| **No label leakage in features** | Verify feature columns don't contain label-derived information | Integration test from feature engineering blueprint |
| **Scaler fitted on train only** | Verify scaler parameters computed from train fold only | Code review / test |
| **Thresholds frozen before test** | Verify threshold selection uses validation only | Audit trail in experiment record |
| **Purge applied** | Verify training rows with overlapping labels removed | Check row counts before/after purge |

---

## 10. Execution Timing

### 10.1 Critical Principle

> A signal generated using close(T) cannot be traded at close(T) — that price is only known after the market closes.

**Do NOT allow:** Signal generated using close(T) and trade executed at the same unknowable close(T).

### 10.2 MVP Execution Convention

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXECUTION CONVENTION                           │
│                                                                  │
│  Feature timestamp (T):   2024-01-02 close                      │
│  Model prediction time:   2024-01-02 after close                │
│  Earliest valid execution: 2024-01-03 open                      │
│                                                                  │
│  Label target (T+H):       2024-01-09 close (5 trading days)    │
│  Trade exit:               2024-01-09 close                      │
│                                                                  │
│  Entry price:  open of 2024-01-03 (next available price)        │
│  Exit price:   close of 2024-01-09 (as per label definition)    │
│                                                                  │
│  Simplified MVP convention: close-to-close                      │
│    - Entry: close_T   (simplified, assumes execution at close)   │
│    - Exit: close_{T+5}                                          │
│    - Acknowledged simplification for MVP                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**MVP convention: close-to-close (simplified).**

For MVP, use the same convention as label definition:
- Entry: close_T (the price at prediction time)
- Exit: close_{T+5} (the price 5 days later)

This is a **known simplification**. Real execution would use next-day open or next available price. Document this limitation clearly. Future phases can implement more realistic execution modeling.

### 10.3 Realistic Execution Timing (Future)

| Scenario | Entry | Exit | Notes |
|----------|-------|------|-------|
| **MVP (simplified)** | close_T | close_{T+5} | Matches label definition; known simplification |
| **Next-day open** | open_{T+1} | close_{T+5} | More realistic — avoids same-day close issue |
| **Next available** | first_tick_after_T | last_tick_before_{T+5} | Most realistic — requires intraday data |
| **Volume-weighted entry** | VWAP over first 30 min of T+1 | close_{T+5} | Accounts for execution during market open |

---

## 11. Transaction Cost Model

### 11.1 Configurable Cost Components

```
Total Cost = Brokerage + Exchange Fees + Spread + Slippage + Other
```

| Component | Description | MVP Default | Configurable |
|-----------|-------------|-------------|--------------|
| **Brokerage** | Commission charged by broker | 5 bps per side | Yes |
| **Exchange fees** | Exchange transaction fees | 0 bps (consolidated into brokerage for MVP) | Yes |
| **Taxes** | Capital gains tax, stamp duty (where relevant) | 0% (not applicable for MVP — paper trading) | Yes |
| **Spread** | Bid-ask spread cost (estimated) | 5 bps (estimated half-spread) | Yes |
| **Slippage** | Difference between expected and actual execution price | See Section 12 | Yes |
| **Other** | Custody fees, platform fees, etc. | 0 bps | Yes |

### 11.2 MVP Cost Model

```
Round-trip cost (enter + exit):
  Entry cost:   5 bps (brokerage) + 5 bps (spread/slippage) = 10 bps
  Exit cost:    5 bps (brokerage) + 5 bps (spread/slippage) = 10 bps
  Total:        20 bps per round trip (0.20%)

Per-trade cost (one side):
  10 bps (0.10%)
```

**Default cost assumption: 10 bps per side, 20 bps round-trip.**

This matches PRD_MVP.md FR-BT-03 (transaction_cost_bps: 10).

### 11.3 Gross vs Net Return

```
Gross Return = (Exit Price - Entry Price) / Entry Price

Net Return = Gross Return - Total Costs

Where:
  Total Costs = Entry Cost + Exit Cost
  Entry Cost = brokerage_entry + spread_entry + slippage_entry
  Exit Cost = brokerage_exit + spread_exit + slippage_exit
```

**CRITICAL: Never report only gross returns in final strategy evaluation.**

Every strategy result must be reported as:
1. Gross return (for reference)
2. Net return after costs (primary metric)
3. Cost decomposition (for transparency)

---

## 12. Slippage Model

### 12.1 MVP Slippage Approach

**MVP: Fixed percentage slippage model.**

```
Slippage per trade = slippage_bps × entry_price  (or exit_price)

Default: 5 bps per side
```

**Why fixed percentage for MVP:**
- Simple to implement and understand
- Reasonable approximation for liquid large-cap stocks
- Sufficient for MVP backtesting purposes
- Configurable for sensitivity testing

### 12.2 Slippage Variants

| Variant | Description | MVP? |
|---------|-------------|------|
| **A. Fixed slippage (bps)** | Fixed percentage applied to every trade | ✅ MVP default |
| **B. Percentage slippage (volatility-adjusted)** | Slippage proportional to expected volatility | ⚠️ Future |
| **C. Volume-dependent slippage** | Slippage increases for low-volume instruments | ⚠️ Future |
| **D. Spread-aware execution** | Use bid-ask spread data if available | ❌ Future (requires L2 data) |
| **E. Market-impact model** | Slippage based on order size relative to volume | ❌ Future (requires order sizing) |

### 12.3 Slippage Sensitivity Testing

Test multiple slippage assumptions to determine strategy robustness:

```
Slippage Sensitivity Table:
┌─────────────────┬──────────┬──────────┬──────────┬──────────┐
│ Slippage (bps)  │  Net     │  Sharpe  │  Max DD  │  Win Rate │
│ per side        │  Return  │  Ratio   │          │           │
├─────────────────┼──────────┼──────────┼──────────┼──────────┤
│ 0 (gross)       │  12.5%   │  1.85    │  -8.2%   │  57%      │
│ 5 (base)        │   9.8%   │  1.42    │  -9.1%   │  55%      │
│ 10              │   7.1%   │  1.05    │  -10.3%  │  53%      │
│ 20              │   1.6%   │  0.28    │  -12.8%  │  51%      │
│ 30              │  -3.9%   │ -0.42    │  -15.1%  │  48%      │
└─────────────────┴──────────┴──────────┴──────────┴──────────┘
```

---

## 13. Position Model

### 13.1 MVP Position Representation

```
Position States:
  LONG  → 1 unit of the instrument
  FLAT  → 0 units (cash)
  SHORT → -1 unit (if supported by data/execution assumptions)
```

**MVP: LONG and FLAT only.**

Short positions are NOT included in MVP unless:
- Data supports short pricing (easy shortable stocks)
- Execution assumptions are documented for shorting
- Short selling costs are modeled

**MVP decision: Long-only for simplicity.**

### 13.2 Position Sizing

```
MVP Position Sizing:
  - Fixed fractional: 1 unit per signal (simplified)
  - No dynamic sizing based on conviction
  - No Kelly criterion (future research)
  - No volatility targeting (future research)
```

**Why fixed sizing for MVP:**
- Simple and reproducible
- Avoids introducing additional parameters that can be optimized
- Sufficient to evaluate whether signal has value
- Position sizing is a separate research question

### 13.3 Entry, Exit, Holding Period

| Event | Condition | Action |
|-------|-----------|--------|
| **Entry** | Signal = BUY, currently FLAT | Enter LONG at entry_price |
| **Exit** | Signal = SELL (or HOLD after holding period) | Exit LONG at exit_price |
| **No-Trade** | Signal = HOLD, or no signal | Remain in current position |
| **Max Holding Period** | Position held for max_holding_period days | Force exit regardless of signal |

**MVP defaults:**
- Max holding period: 5 days (matches label horizon; exit after label period regardless)
- Position size: 1 unit (fixed)

### 13.4 Overlapping Positions

| Scenario | MVP Handling |
|----------|-------------|
| Signal to enter while already LONG | Ignore entry signal (no pyramiding in MVP) |
| Signal to exit while FLAT | Ignore (nothing to exit) |
| Multiple consecutive BUY signals | Stay LONG; do not add to position |

**Rule: One position at a time. No pyramiding. No hedging.**

---

## 14. Trading Rules

### 14.1 Deterministic Strategy Wrapper

The trading strategy is a deterministic wrapper around the prediction model. It must be fully specified BEFORE backtesting. No retroactive rule changes.

```
Strategy = Model Predictions + Trading Rules + Execution Model + Cost Model
```

### 14.2 Required Trading Rules

| Rule | Definition | MVP Default |
|------|-----------|-------------|
| **Entry Condition** | When to enter a position | Signal = BUY and currently FLAT |
| **Exit Condition** | When to exit a position | Signal = SELL/HOLD, or max holding period reached |
| **No-Trade Condition** | When to stay flat | Signal = HOLD, or already in position with no exit signal |
| **Position Size** | How much to buy/sell | 1 unit (fixed) |
| **Maximum Holding Period** | Longest to hold a position | 5 trading days (matches label horizon) |
| **Stop-Loss Policy** | Loss limit to exit early | NONE for MVP (simplification) |
| **Take-Profit Policy** | Gain target to exit early | NONE for MVP (simplification) |

### 14.3 Stop-Loss and Take-Profit (Future)

```
Future consideration:
  - Stop-loss: Exit if loss exceeds X% from entry
  - Take-profit: Exit if gain exceeds Y% from entry
  - Trailing stop: Exit if price drops Z% from peak

These are NOT in MVP. They introduce additional parameters that can be overfitting vectors.
Document as future research extensions.
```

### 14.4 Rule Freeze Requirement

**Before backtesting:**
1. Document all trading rules explicitly
2. Record in experiment configuration
3. Freeze rules — no changes during backtesting
4. If rules need to change, create new experiment with new configuration

**During backtesting:**
- No rule changes, no parameter tuning
- Any "improvement" discovered during backtesting must be tested in a NEW experiment with a fresh test period

---

## 15. Core Financial Metrics

### 15.1 Mathematical Definitions

| Metric | Formula | Description |
|--------|---------|-------------|
| **Cumulative Return** | Π(1 + r_i) - 1 | Total return over backtest period |
| **Annualized Return** | (1 + cumulative_return)^(252 / n_days) - 1 | Geometric mean return annualized |
| **Daily Return** | (equity_t - equity_{t-1}) / equity_{t-1} | Return on day t |
| **Strategy Volatility** | std(daily_returns) × sqrt(252) | Annualized standard deviation of returns |
| **Sharpe Ratio** | (annualized_return - risk_free_rate) / annualized_volatility | Risk-adjusted return (default rf = 0 for MVP) |
| **Sortino Ratio** | (annualized_return - risk_free_rate) / downside_deviation_annualized | Risk-adjusted return using only downside volatility |
| **Downside Deviation** | std(min(0, daily_returns)) × sqrt(252) | Volatility of negative returns only |
| **Maximum Drawdown** | min((equity_t / running_max_equity_t) - 1) | Largest peak-to-trough decline |
| **Calmar Ratio** | annualized_return / abs(max_drawdown) | Return relative to worst drawdown |
| **Win Rate** | winning_trades / total_trades | Percentage of profitable trades |
| **Average Win** | mean(profit_of_winning_trades) | Average profit per winning trade |
| **Average Loss** | mean(loss_of_losing_trades) | Average loss per losing trade (positive number) |
| **Profit Factor** | gross_profit / gross_loss | Ratio of total wins to total losses |
| **Expectancy** | win_rate × avg_win - (1 - win_rate) × avg_loss | Expected value per trade |
| **Turnover** | sum(abs(position_change)) / n_days | Average position changes per day |
| **Number of Trades** | count(of entries) | Total number of position entries |
| **Avg Holding Period** | mean(exit_date - entry_date) | Average duration of positions |

### 15.2 Metric Computation Notes

| Metric | Notes |
|--------|-------|
| **Sharpe Ratio** | Use risk_free_rate = 0 for MVP (no risk-free rate data). Document this. |
| **Annualization** | Use 252 trading days per year for daily data. |
| **Drawdown** | Compute from equity curve, not from cumulative return. |
| **Trade P&L** | Net of transaction costs (entry + exit). |
| **Win/Loss** | Based on net P&L per trade (after costs). |
| **Missing data** | If no trades executed, report 0 trades, N/A for trade-based metrics. |

### 15.3 Required Metrics Report

```
Performance Metrics:
┌─────────────────────────┬──────────┐
│ Metric                  │  Value   │
├─────────────────────────┼──────────┤
│ Cumulative Return       │  9.8%    │
│ Annualized Return       │  4.9%    │
│ Annualized Volatility   │  8.2%    │
│ Sharpe Ratio            │  1.42    │
│ Sortino Ratio           │  1.68    │
│ Maximum Drawdown        │  -9.1%   │
│ Calmar Ratio            │  0.54    │
│ Win Rate                │  55.0%   │
│ Average Win             │  2.3%    │
│ Average Loss            │  1.8%    │
│ Profit Factor           │  1.28    │
│ Expectancy              │  0.003   │
│ Number of Trades        │  120     │
│ Turnover                │  0.85    │
│ Avg Holding Period      │  3.2 days│
└─────────────────────────┴──────────┘
```

---

## 16. Equity Curve

### 16.1 Strategy Equity Timeline

The strategy equity curve represents the value of a hypothetical $1.00 investment over time.

```
Equity at time t = Π(1 + daily_return_i) for i = 1 to t

Where:
  daily_return_i = net return on day i (including costs)
  equity_0 = 1.00 (starting value)
```

### 16.2 Required Curves

| Curve | Description | Derivation |
|-------|-------------|-----------|
| **Equity Curve** | Strategy value over time | Cumulative product of (1 + daily returns) |
| **Drawdown Curve** | Percentage below running peak | (equity_t / running_max_equity_t) - 1 |
| **Rolling Returns** | Return over rolling window (e.g., 21-day) | Equity_t / equity_{t-21} - 1 |
| **Rolling Sharpe** | Sharpe ratio over rolling window | Mean(rolling_returns) / std(rolling_returns) × sqrt(252) |
| **Rolling Volatility** | Volatility over rolling window | std(daily_returns in window) × sqrt(252) |

### 16.3 Visualization Requirements

```
Equity Curve Chart:
  X-axis: Time (dates)
  Y-axis: Equity (log scale recommended for percentage returns)
  Line: Strategy equity
  Line: Benchmark equity (buy-and-hold) for comparison
  Shaded area: Drawdown (below peak)

Drawdown Chart:
  X-axis: Time
  Y-axis: Drawdown (negative percentage)
  Line: Current drawdown from peak
  Line: Maximum drawdown (horizontal reference)
```

---

## 17. Benchmarks

### 17.1 Required MVP Benchmarks

| Benchmark | Description | Purpose |
|-----------|-------------|---------|
| **Buy-and-Hold** | Hold the instrument from start to end of test period | Baseline: does the strategy beat simply holding? |
| **Zero-Trade (Cash)** | Never enter a position, stay in cash | Baseline: does the strategy do better than doing nothing? |
| **Random Classifier** | Random UP/DOWN/HOLD predictions (33% each) | Baseline: is the model better than random? |

**MVP benchmarks: Buy-and-Hold and Zero-Trade.**

### 17.2 Benchmark Selection Rationale

| Benchmark | Required for MVP? | Justification |
|-----------|-------------------|---------------|
| **Buy-and-Hold** | ✅ Yes | Most fundamental comparison — does trading add value over holding? |
| **Zero-Trade (Cash)** | ✅ Yes | Tests whether any trading activity is worthwhile vs sitting in cash |
| **Random Classifier** | ⚠️ Optional | Useful for ML evaluation but less relevant for strategy comparison |
| **Naive previous-direction model** | ❌ No | Not clearly defined for MVP; adds complexity |
| **Simple technical-rule strategy** | ❌ No | Adds another model to develop; future comparison |
| **Market index benchmark** | ❌ No | Requires index data; future multi-asset work |

### 17.3 Benchmark Comparison Table

```
Benchmark Comparison:
┌─────────────────────┬──────────┬───────────┬───────────┬─────────────┐
│ Strategy            │  Cum Ret │  Ann Ret  │  Sharpe   │  Max DD     │
├─────────────────────┼──────────┼───────────┼───────────┼─────────────┤
│ Strategy (LR Model) │  9.8%    │  4.9%     │  1.42     │  -9.1%      │
│ Buy-and-Hold        │  8.2%    │  4.1%     │  0.65     │  -14.3%     │
│ Zero-Trade (Cash)   │  0.0%    │  0.0%     │  N/A      │  0.0%       │
└─────────────────────┴──────────┴───────────┴───────────┴─────────────┘
```

---

## 18. Ablation Testing

### 18.1 Purpose

Determine which components of the system actually contribute predictive value. Remove components one at a time and measure the impact.

### 18.2 Ablation Experiment Design

```
Experiment 1: Baseline (all features)
  - All 52 features
  - Full model
  - Record performance

Experiment 2: Without technical features
  - Remove: returns, trend, momentum, Bollinger, candle structure
  - Keep: volatility, volume, volume-price
  - Record performance

Experiment 3: Without volume features
  - Remove: volume, volume-price
  - Keep: all price-based features
  - Record performance

Experiment 4: Without volatility features
  - Remove: volatility
  - Keep: all other features
  - Record performance

Experiment 5: Minimal feature set
  - Keep: only returns_1d, returns_5d, volatility_20d
  - Record performance
```

### 18.3 Ablation Analysis Table

```
Ablation Study Results:
┌────────────────────────────────────┬──────────┬───────────┬───────────┐
│ Configuration                      │  Accuracy│  Sharpe   │  Max DD   │
├────────────────────────────────────┼──────────┼───────────┼───────────┤
│ Baseline (all 52 features)        │  0.52    │  1.42     │  -9.1%    │
│ - Technical features              │  0.50    │  1.18     │  -10.2%   │
│ - Volume features                 │  0.51    │  1.35     │  -9.5%    │
│ - Volatility features             │  0.50    │  1.22     │  -9.8%    │
│ Minimal (3 features)              │  0.49    │  1.05     │  -11.1%   │
└────────────────────────────────────┴──────────┴───────────┴───────────┘
```

**Interpretation:** If removing a feature group causes significant performance degradation, that group contributes value. If performance is unchanged, the features may be redundant.

---

## 19. Robustness Testing

### 19.1 Market Regime Testing

Test performance across different market regimes:

| Regime | Identification | Test Question |
|--------|---------------|---------------|
| **Bull market** | Period where buy-and-hold return > 0 and above median | Does strategy perform well in rising markets? |
| **Bear market** | Period where buy-and-hold return < 0 and below median | Does strategy lose less than buy-and-hold in falling markets? |
| **Sideways/choppy** | Period where buy-and-hold return near 0 (within ±5%) | Does strategy generate signal in non-trending markets? |
| **High volatility** | Period where realized volatility > 75th percentile | Does strategy handle volatile conditions? |
| **Low volatility** | Period where realized volatility < 25th percentile | Does strategy perform in calm markets? |

### 19.2 Regime Performance Table

```
Regime Analysis:
┌───────────────────┬──────────┬───────────┬───────────┬──────────┬──────────┐
│ Regime            │  Days    │  Strategy │  B&H      │  Sharpe  │  Win Rate│
├───────────────────┼──────────┼───────────┼───────────┼──────────┼──────────┤
│ Bull (2023)       │   252    │  12.5%    │  15.2%    │  1.28    │  58%     │
│ Bear (2022)       │   252    │  -2.1%    │  -9.8%    │  0.15    │  48%     │
│ Sideways (2024 Q1)│   63     │   1.8%    │   0.5%    │  0.42    │  52%     │
│ High Vol (2020)   │   180    │  -5.2%    │  -12.1%   │ -0.35    │  45%     │
│ Low Vol (2023 Q2) │   63     │   4.2%    │   3.8%    │  1.15    │  61%     │
└───────────────────┴──────────┴───────────┴───────────┴──────────┴──────────┘
```

**Key insight:** A model must not be considered robust based on performance in a single favorable regime.

---

## 20. Cost Sensitivity

### 20.1 Purpose

Test whether the strategy remains viable as transaction costs increase. A strategy that only works at unrealistically low costs is not robust.

### 20.2 Cost Scenarios

| Scenario | Cost Assumption | Description |
|----------|----------------|-------------|
| **Low-cost** | 5 bps per side (10 bps round-trip) | Optimistic — highly liquid instruments, low-commission broker |
| **Base-cost** | 10 bps per side (20 bps round-trip) | Realistic default for MVP |
| **High-cost** | 25 bps per side (50 bps round-trip) | Pessimistic — includes higher spreads, less liquid instruments |

### 20.3 Cost Sensitivity Table

```
Cost Sensitivity Analysis:
┌─────────────────────┬──────────┬───────────┬───────────┬──────────┐
│ Cost Scenario       │  Net Ret │  Sharpe   │  Max DD   │  Viable? │
├─────────────────────┼──────────┼───────────┼───────────┼──────────┤
│ Low-cost (5 bps)    │  12.1%   │  1.75     │  -8.5%    │  Yes     │
│ Base-cost (10 bps)  │   9.8%   │  1.42     │  -9.1%    │  Yes     │
│ High-cost (25 bps)  │   3.2%   │  0.48     │  -11.2%   │  Marginal│
└─────────────────────┴──────────┴───────────┴───────────┴──────────┘
```

**Decision rule:** If strategy becomes unprofitable or near-zero Sharpe at realistic cost levels, it is not robust.

---

## 21. Slippage Sensitivity

### 21.1 Purpose

Similar to cost sensitivity, but specifically for slippage — the difference between expected and actual execution price.

### 21.2 Slippage Stress Test

```
Slippage Stress Test:
┌─────────────────────┬──────────┬───────────┬───────────┬──────────┐
│ Slippage (bps/side) │  Net Ret │  Sharpe   │  Max DD   │  Viable? │
├─────────────────────┼──────────┼───────────┼───────────┼──────────┤
│ 0                   │  14.2%   │  2.10     │  -7.8%    │  Yes     │
│ 5 (base)            │   9.8%   │  1.42     │  -9.1%    │  Yes     │
│ 10                  │   5.4%   │  0.78     │  -10.5%   │  Marginal│
│ 20                  │  -0.8%   │ -0.12     │  -12.3%   │  No      │
│ 30                  │  -5.1%   │ -0.71     │  -14.1%   │  No      │
└─────────────────────┴──────────┴───────────┴───────────┴──────────┘
```

**Interpretation:** Strategy is sensitive to slippage assumptions. Performance degrades quickly as slippage increases. This should be reported transparently.

---

## 22. Threshold Sensitivity

### 22.1 Purpose

Evaluate how strategy performance changes with different signal thresholds. Do NOT report only the best threshold.

### 22.2 Threshold Range Evaluation

```
Threshold Sensitivity (using validation data for selection):
┌─────────────────────┬──────────┬───────────┬───────────┬──────────┐
│ P(UP) Threshold     │  Signal  │  Net Ret  │  Sharpe   │  Max DD  │
│                     │  Freq    │           │           │          │
├─────────────────────┼──────────┼───────────┼───────────┼──────────┤
│ 0.30                │  68%     │  7.2%     │  1.05     │  -10.8%  │
│ 0.40                │  52%     │  8.9%     │  1.28     │  -9.5%   │
│ 0.50 (selected)     │  32%     │  9.8%     │  1.42     │  -9.1%   │
│ 0.60                │  20%     │  8.5%     │  1.31     │  -8.2%   │
│ 0.70                │  11%     │  7.1%     │  1.18     │  -7.5%   │
└─────────────────────┴──────────┴───────────┴───────────┴──────────┘
```

### 22.3 Threshold Freeze Requirement

**BEFORE final test:**
1. Evaluate threshold range on validation data
2. Select threshold based on validation performance
3. Freeze threshold — record value and selection rationale
4. Apply frozen threshold to test set ONCE

**AFTER final test:**
- Do NOT adjust threshold based on test results
- If threshold needs to change, create new experiment with new validation period

---

## 23. Model Comparison

### 23.1 Fair Comparison Requirements

When comparing two models, ensure:

| Requirement | Why |
|------------|-----|
| Same dataset version | Different data = different problem |
| Same feature version | Different features = different input |
| Same label version | Different labels = different target |
| Same evaluation periods | Different periods = different market conditions |
| Same execution assumptions | Different execution = different returns |
| Same cost model | Different costs = different net returns |
| Same metric definitions | Different formulas = incomparable numbers |
| Same benchmark | Different baseline = different comparison |

### 23.2 Model Comparison Table

```
Model Comparison (same dataset, same periods, same costs):
┌─────────────────────┬──────────┬───────────┬───────────┬──────────┬──────────┐
│ Model               │  Accuracy│  Precision│  Sharpe   │  Max DD  │  Win Rate│
├─────────────────────┼──────────┼───────────┼───────────┼──────────┼──────────┤
│ Logistic Regression │  0.52    │  0.52     │  1.42     │  -9.1%   │  55%     │
│ Random Forest       │  0.54    │  0.54     │  1.58     │  -8.5%   │  57%     │
└─────────────────────┴──────────┴───────────┴───────────┴──────────┴──────────┘
```

**Note:** Differences must be evaluated for statistical significance (see Section 24). A 2-percentage-point accuracy difference may not be meaningful.

### 23.3 Invalid Comparisons

| Scenario | Why Invalid | What to Do |
|----------|-------------|------------|
| Different test periods | Different market conditions | Use same test period or acknowledge difference |
| Different cost assumptions | Different net returns | Align costs or report separately |
| One model optimized on test set | Test set contamination | Reject comparison — test set compromised |
| Different label definitions | Different prediction problems | Compare only with same labels |
| Different feature sets (when comparing models, not features) | Confounding variable | Use same features for model comparison; use ablation for feature comparison |

---

## 24. Statistical Significance

### 24.1 Framework for Assessing Meaningfulness

Observed performance differences may be due to noise rather than genuine skill. Statistical significance assessment helps distinguish signal from noise.

### 24.2 Methods

| Method | Description | Applicability |
|--------|-------------|---------------|
| **Confidence Intervals** | Compute CI around performance metrics (e.g., 95% CI for accuracy) | General purpose |
| **Bootstrap Analysis** | Resample trades/observations with replacement, recompute metric distribution | Trade-level metrics |
| **Repeated Walk-Forward** | Run walk-forward with different seeds or slight variations, observe distribution of results | Walk-forward metrics |
| **Binomial Test** | Test if accuracy is significantly better than random chance (33% for 3-class, 50% for 2-class) | Classification accuracy |
| **Permutation Test** | Shuffle labels, recompute metric, compare to actual | General purpose |

### 24.3 Number of Trades Consideration

| Trade Count | Statistical Confidence | Interpretation |
|-------------|----------------------|----------------|
| < 20 trades | Very low | Results are essentially anecdotal |
| 20-50 trades | Low | Directionally interesting but not statistically robust |
| 50-100 trades | Moderate | Some confidence, but wide confidence intervals |
| 100-200 trades | Reasonable | Can assess whether performance differs from random |
| 200+ trades | Good | More reliable inference possible |

**Critical note:** Financial time series data is not i.i.d. (independent and identically distributed). Observations are dependent (overlapping returns, market regimes). Standard statistical tests assume independence and may overstate significance. Acknowledge this limitation.

### 24.4 Confidence Interval Example

```
Accuracy: 52% (120 predictions)
95% Confidence Interval (binomial approximation): [43%, 61%]

Interpretation: We cannot reject that true accuracy is 33% (random chance for 3-class)
at the 95% confidence level. More data needed for statistical confidence.
```

---

## 25. Overfitting / Backtest Overfitting

### 25.1 Types of Overfitting in Backtesting

| Type | Description | Detection |
|------|-------------|------------|
| **Parameter overfitting** | Tuning strategy parameters (thresholds, holding periods, stop-loss levels) to optimize backtest results | Multiple parameter combinations tested, best selected |
| **Threshold overfitting** | Selecting threshold that maximizes test set performance | Threshold chosen based on test results |
| **Feature overfitting** | Selecting features based on test set performance | Feature selection uses test data |
| **Strategy overfitting** | Adding arbitrary rules that improve backtest but have no economic rationale | Too many rules, rules added post-hoc |
| **Repeated testing on same test set** | Testing many model variants on the same test set until one "works" | Multiple attempts on same test data |

### 25.2 Safeguards

| Safeguard | Implementation |
|-----------|---------------|
| **Freeze before test** | All parameters, thresholds, rules frozen before test evaluation |
| **Validation-only tuning** | All optimization uses validation data, not test data |
| **Single final test** | Test set evaluated ONCE per experiment |
| **New test period for new experiments** | If test set is used, it's "consumed" — new experiments need new test data |
| **Record all attempts** | Log all parameter combinations tested (on validation), not just the best |
| **Economic rationale** | Every rule should have an economic justification, not just "it improved the backtest" |
| **Simplicity preference** | Prefer simpler strategies; complexity must be justified by significant improvement |

### 25.3 Deflated Sharpe Ratio (Concept)

The Deflated Sharpe Ratio (DSR) accounts for the number of trials performed when assessing whether a Sharpe ratio is significant. The more parameter combinations tested, the higher the chance of finding a seemingly good result by random chance.

```
Concept (NOT required for MVP, but document the risk):

DSR = Phi((SR - SR0) / sigma_SR) / (1 - gamma + 1)

Where the adjustment accounts for:
  - Number of parameter combinations tested
  - Non-normality of returns
  - Sample size

For MVP: Acknowledge the risk of multiple testing. Document number of experiments run.
```

### 25.4 Test Set Protection Summary

```
TEST SET PROTECTION RULES:
  1. Test set created once by DatasetBuilder — immutable
  2. Test set NOT used for: feature selection, threshold tuning, hyperparameter optimization, model selection
  3. Test set evaluated ONCE per experiment
  4. If test set metrics examined and model changed, test set is compromised — need new test period
  5. All tuning documented as using validation data only
  6. Final test protocol (Section 26) must be followed
```

---

## 26. Final Test Protocol

### 26.1 Required Process

```
FINAL TEST PROTOCOL:

1. FREEZE MODEL
   - Select model version (e.g., v1.0.0-20260904)
   - Record model artifact path
   - Do NOT retrain or modify model after this point

2. FREEZE FEATURE SET
   - Record feature_version (e.g., v0.1)
   - Record feature names and count
   - Do NOT add/remove features after this point

3. FREEZE LABELS
   - Record label_version (e.g., v0.1)
   - Record label type, window, thresholds
   - Do NOT change label definition after this point

4. FREEZE THRESHOLD
   - Record selected threshold (e.g., P(UP) > 0.50)
   - Record selection method and validation performance
   - Do NOT adjust threshold after this point

5. FREEZE STRATEGY RULES
   - Record all trading rules (entry, exit, position size, max holding, etc.)
   - Do NOT add/modify rules after this point

6. FREEZE COST ASSUMPTIONS
   - Record cost model: brokerage, spread, slippage
   - Record total round-trip cost
   - Do NOT change costs after this point

7. RUN FINAL OUT-OF-SAMPLE TEST ONCE
   - Load frozen model, features, labels, dataset
   - Apply frozen thresholds and strategy rules
   - Simulate trading on test set with frozen cost model
   - Record ALL results (metrics, equity curve, trade ledger)
   - Do NOT re-run with different parameters

8. PRODUCE IMMUTABLE FINAL REPORT
   - Generate final backtest report (Section 32)
   - Mark report as FINAL — not to be revised
   - Archive all artifacts with timestamp
```

### 26.2 When a New Research Cycle Requires a New Test Period

| Trigger | Action |
|---------|--------|
| Model changed (retrained, different version) | New experiment, need new test period or use validation only |
| Feature set changed (added/removed features) | New experiment, need new test period |
| Label definition changed (different window, thresholds) | New experiment, need new test period |
| Strategy rules changed | New experiment, need new test period |
| Cost assumptions changed | New experiment, document difference explicitly |
| Threshold changed | New experiment, need new test period |
| Test set metrics examined and then model changed | Test set compromised — need new test period |

**Rule:** Once a test set has been used for final evaluation, it cannot be reused for a different model/configuration without acknowledging the comparison limitation.

---

## 27. Backtest Outputs

### 27.1 Required Outputs

Every backtest run must produce:

| Output | Format | Description |
|--------|--------|-------------|
| **Prediction file** | CSV/Parquet | Model predictions for test period (timestamp, predicted_class, probabilities) |
| **Trade ledger** | CSV/Parquet | All trades executed during backtest (see Section 28) |
| **Equity curve** | CSV | Daily equity values over backtest period |
| **Drawdown curve** | CSV | Daily drawdown values over backtest period |
| **Performance metrics** | JSON | All financial metrics (Section 15) |
| **Cost-adjusted results** | JSON | Results with cost decomposition (gross vs net) |
| **Experiment metadata** | JSON | Full experiment record (versions, config, timestamps) |
| **Configuration snapshot** | JSON | Exact configuration used for this backtest |
| **Evaluation report** | Markdown/PDF | Human-readable backtest report (Section 32) |

### 27.2 Output Directory Structure

```
backtests/
├── {backtest_id}/
│   ├── data_quality/
│   │   └── quality_report.json
│   ├── predictions/
│   │   └── test_predictions.csv
│   ├── trades/
│   │   └── trade_ledger.csv
│   ├── curves/
│   │   ├── equity_curve.csv
│   │   └── drawdown_curve.csv
│   ├── metrics/
│   │   ├── financial_metrics.json
│   │   └── prediction_metrics.json
│   ├── config/
│   │   └── config_snapshot.json
│   ├── metadata/
│   │   └── experiment_record.json
│   └── report/
│       └── backtest_report.md
```

---

## 28. Trade Ledger

### 28.1 Required Fields

Every trade in the ledger must record:

| Field | Type | Description |
|-------|------|-------------|
| **trade_id** | string | Unique trade identifier |
| **instrument** | string | Ticker symbol |
| **signal_timestamp** | datetime | When the signal was generated |
| **execution_timestamp** | datetime | When the trade was executed (entry) |
| **signal** | string | BUY, SELL, or HOLD (signal that triggered entry) |
| **probability** | float | Model probability for the predicted class |
| **entry_price** | float | Price at entry execution |
| **exit_timestamp** | datetime | When the position was closed |
| **exit_price** | float | Price at exit execution |
| **quantity** | float | Number of units (1.0 for MVP) |
| **gross_pnl** | float | (exit_price - entry_price) × quantity (for long) |
| **costs** | float | Total transaction costs for the trade (entry + exit) |
| **net_pnl** | float | gross_pnl - costs |
| **holding_duration** | float | Number of days held (exit_date - entry_date) |
| **reason** | string | Why the trade was taken (e.g., "signal_buy", "max_holding_period_expired") |
| **signal_version** | string | Model version that generated the signal |
| **trade_number** | integer | Sequential trade number in this backtest |

### 28.2 Trade Ledger Example

```csv
trade_id,instrument,signal_timestamp,execution_timestamp,signal,probability,entry_price,exit_timestamp,exit_price,quantity,gross_pnl,costs,net_pnl,holding_duration,reason,signal_version,trade_number
T001,AAPL,2024-01-02,2024-01-03,BUY,0.62,185.60,2024-01-09,187.40,1.0,1.80,0.37,1.43,6,signal_buy,v1.0.0-20260904,1
T002,AAPL,2024-01-15,2024-01-16,BUY,0.58,190.20,2024-01-23,188.50,1.0,-1.70,0.38,-2.08,7,signal_buy,v1.0.0-20260904,2
T003,AAPL,2024-01-24,2024-01-25,HOLD,0.45,0.00,0.00,0.00,0.0,0.00,0.00,0.00,0,no_trade,v1.0.0-20260904,0
```

**Note:** Trade ledger is a research artifact, not a live trading system. It records what WOULD have happened under the simulated assumptions.

---

## 29. Reproducibility

### 29.1 Required Record for Every Backtest

| Item | Example | Required |
|------|---------|----------|
| **Backtest ID** | bt_20260904_140000 | Yes |
| **Model version** | v1.0.0-20260904 | Yes |
| **Dataset version** | v0.1 | Yes |
| **Feature version** | v0.1 | Yes |
| **Label version** | v0.1 | Yes |
| **Strategy version** | stg_v0.1 (strategy rules version) | Yes |
| **Configuration** | Full config snapshot (YAML/JSON) | Yes |
| **Code version** | Git commit hash (or "unversioned") | Yes |
| **Cost model version** | cost_v0.1 | Yes |
| **Timestamp** | 2026-09-04T14:00:00Z | Yes |
| **Random seed** | 42 (if any randomness in backtest) | Yes |
| **Walk-forward parameters** | train_window=252, test_window=21, step=21 | Yes |
| **Purge/embargo settings** | purge_enabled=true, embargo_period=0 | Yes |

### 29.2 Reproducing a Historical Backtest

To reproduce a backtest:

1. Locate backtest directory: `backtests/bt_20260904_140000/`
2. Read `metadata/experiment_record.json` → get all versions, config, parameters
3. Read `config/config_snapshot.json` → exact configuration
4. Load dataset: `data/processed/datasets/dataset_v0.1/` (from metadata)
5. Load model: `models/.../model_v1.0.0-20260904.joblib` (from metadata)
6. Run backtest engine with exact configuration
7. Compare new results to recorded results

### 29.3 Reproducibility Limitations

| Limitation | Impact | Mitigation |
|-----------|--------|------------|
| **Floating point** | Tiny differences across hardware/BLAS | Accept "functionally equivalent" results |
| **Unversioned code** | Code changes not tracked | Mark as "unversioned" in metadata |
| **Non-deterministic operations** | If any randomness used in backtest | Set seed, use n_jobs=1 |
| **Platform differences** | Different OS, Python version | Record environment metadata |

---

## 30. Backtest Engine Architecture

### 30.1 Module Boundaries

```
┌──────────────────────────────────────────────────────────────────────┐
│                    BACKTEST ENGINE ARCHITECTURE                      │
│                                                                      │
│  Data Adapter                                                         │
│    ↓  (loads dataset, features, labels, metadata)                   │
│  Prediction Adapter                                                   │
│    ↓  (loads model, generates predictions for test period)          │
│  Signal Generator                                                     │
│    ↓  (converts probabilities to signals using thresholds)          │
│  Execution Simulator                                                  │
│    ↓  (simulates trade execution with timing assumptions)           │
│  Position Manager                                                     │
│    ↓  (tracks positions, entry/exit, holding periods)               │
│  P&L Calculator                                                       │
│    ↓  (computes gross P&L, applies costs, computes net P&L)         │
│  Metrics Engine                                                       │
│    ↓  (computes all financial and prediction metrics)               │
│  Report Generator                                                     │
│    ↓  (produces trade ledger, equity curve, report)                 │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 30.2 Module Responsibilities

| Module | Responsibility | Input | Output |
|--------|---------------|-------|--------|
| **Data Adapter** | Load and validate dataset, features, labels, metadata | Dataset path, versions | Clean DataFrames, metadata |
| **Prediction Adapter** | Load trained model, generate predictions for test period | Model path, feature DataFrame | Prediction Series (class + probabilities) |
| **Signal Generator** | Convert probabilities to signals using thresholds | Prediction probabilities, thresholds | Signal Series (BUY/SELL/HOLD) |
| **Execution Simulator** | Simulate trade execution with timing model | Signals, price data, execution convention | Executed trades (with execution prices) |
| **Position Manager** | Track positions, manage entry/exit, enforce max holding | Executed trades, trading rules | Position series, trade events |
| **P&L Calculator** | Compute gross P&L, apply costs, compute net P&L | Trade events, cost model, prices | Trade ledger with P&L |
| **Metrics Engine** | Compute all financial and prediction metrics | Trade ledger, equity curve, predictions, true labels | Metrics dictionary |
| **Report Generator** | Produce all output files and human-readable report | All above outputs | Output directory with all artifacts |

### 30.3 Data Flow

```
Dataset (test period)
    ↓
Data Adapter → Features + Labels + Prices + Metadata
    ↓
Prediction Adapter → Predictions (class + probabilities)
    ↓
Signal Generator → Signals (BUY/SELL/HOLD)
    ↓
Execution Simulator → Executed Trades (entry/exit prices, timestamps)
    ↓
Position Manager → Position History + Trade Events
    ↓
P&L Calculator → Trade Ledger (with gross/net P&L)
    ↓
Metrics Engine → Financial Metrics + Prediction Metrics
    ↓
Report Generator → All Output Files + Backtest Report
```

### 30.4 Architectural Principles

| Principle | Enforcement |
|-----------|-------------|
| **Modular** | Each module has single responsibility, testable in isolation |
| **Configurable** | All parameters passed via configuration, not hardcoded |
| **Auditable** | Every module produces intermediate outputs for inspection |
| **Fail-fast** | Data quality gate fails immediately if data is invalid |
| **No leakage** | Strict temporal separation enforced at every stage |
| **Reproducible** | All versions, seeds, configs recorded |

---

## 31. Failure Conditions

### 31.1 Backtest Must Fail Loudly When:

| Condition | Detection | Fail Action |
|-----------|-----------|-------------|
| **Future timestamps used** | Any timestamp in features/prices after current evaluation time | Abort with error |
| **Data is unsorted** | Timestamps not in ascending order | Abort with error |
| **Missing execution price** | Entry or exit price is NaN or missing | Abort with error |
| **Invalid position size** | Quantity <= 0, NaN, or unreasonably large | Abort with error |
| **Negative/invalid price** | Price <= 0 at any point | Abort with error |
| **Dataset version mismatch** | Loaded dataset version != expected version | Abort with error |
| **Feature version mismatch** | Loaded feature version != expected version | Abort with error |
| **Label version mismatch** | Loaded label version != expected version | Abort with error |
| **Model version missing** | Model artifact not found at specified path | Abort with error |
| **Cost assumptions missing** | Cost configuration not provided or invalid | Abort with error |
| **Data quality gate failed** | Any DQ check failed (Section 3) | Abort — do not proceed to evaluation |
| **Empty test set** | No data in test period after filtering | Abort with error |
| **No trades executed** | Strategy never triggered a trade | Warning — report 0 trades, N/A for trade metrics |

### 31.2 No Silent Corrections

| Scenario | WRONG (silent correction) | RIGHT (fail loudly) |
|----------|--------------------------|---------------------|
| Missing price at a timestamp | Skip that day, continue | Abort — missing data is a problem |
| Negative price | Take absolute value | Abort — data integrity issue |
| Unsorted timestamps | Sort silently | Abort — sorting may introduce leakage |
| Version mismatch | Use whatever version is there | Abort — version mismatch is a configuration error |

---

## 32. Report Structure

### 32.1 Standard Backtest Report Sections

Every backtest report must contain:

| # | Section | Content |
|---|---------|---------|
| 1 | **Experiment Identity** | Backtest ID, timestamp, researcher, experiment type |
| 2 | **Model** | Model type, model version, training date, training config summary |
| 3 | **Dataset** | Dataset version, feature version, label version, date ranges, record counts |
| 4 | **Evaluation Period** | Test period start/end, walk-forward folds (if applicable), purge/embargo settings |
| 5 | **Strategy Rules** | Entry/exit conditions, position size, max holding period, stop-loss/take-profit (if any), signal threshold |
| 6 | **Cost Assumptions** | Brokerage, spread, slippage, total round-trip cost, cost model version |
| 7 | **Prediction Metrics** | Accuracy, precision, recall, F1, ROC-AUC, confusion matrix, per-class breakdown, calibration (if applicable) |
| 8 | **Trading Metrics** | Number of trades, win rate, avg win, avg loss, profit factor, expectancy, turnover |
| 9 | **Risk Metrics** | Cumulative return, annualized return, volatility, Sharpe, Sortino, max drawdown, Calmar ratio |
| 10 | **Benchmark Comparison** | Strategy vs buy-and-hold vs zero-trade (same period, same costs) |
| 11 | **Sensitivity Analysis** | Cost sensitivity, slippage sensitivity, threshold sensitivity (if performed) |
| 12 | **Robustness Analysis** | Regime performance, walk-forward fold consistency (if applicable) |
| 13 | **Limitations** | Known limitations: close-to-close execution simplification, no shorting, no stop-loss, single instrument, limited data, etc. |
| 14 | **Conclusion** | Summary of findings, whether strategy shows promise, what would be needed to validate further |

### 32.2 Report Must NOT Contain

| Prohibited | Why |
|------------|-----|
| "The strategy is profitable" without cost adjustment | Must report net of costs |
| "Beats the market" without benchmark comparison | Need explicit benchmark |
| "Statistically significant" without statistical analysis | Need CI, bootstrap, or other analysis |
| "Ready for live trading" | MVP is research only; no live trading |
| "Optimal threshold is X" based on test data | Threshold must be frozen before test |
| "Best model is X" without comparison methodology | Need fair comparison framework |

### 32.3 Example Report Excerpt

```markdown
# Backtest Report: bt_20260904_140000

## 1. Experiment Identity
- Backtest ID: bt_20260904_140000
- Timestamp: 2026-09-04T14:00:00Z
- Researcher: [name]
- Experiment Type: FINAL_TEST

## 2. Model
- Model Type: Random Forest
- Model Version: v1.0.0-20260904
- Training Date: 2026-09-04
- Training Config: n_estimators=100, max_depth=10, class_weight=balanced

## 3. Dataset
- Dataset Version: v0.1
- Feature Version: v0.1 (52 features)
- Label Version: v0.1 (classification, 5-day horizon, ±1% thresholds)
- Train Period: 2016-03-15 to 2022-12-31 (1,725 rows)
- Validation Period: 2023-01-01 to 2023-12-31 (370 rows)
- Test Period: 2024-01-01 to 2025-12-31 (370 rows)

## 4. Evaluation Period
- Test Period: 2024-01-01 to 2025-12-31
- Walk-Forward: Expanding window (252 train / 21 test / 21 step) — NOT used for final test
- Final Test: Single evaluation on held-out test set
- Purge: Enabled (label_window = 5 days)
- Embargo: 0 days

## 5. Strategy Rules
- Entry: Signal = BUY and currently FLAT
- Exit: Signal = SELL/HOLD, or max holding period (5 days) reached
- Position Size: 1 unit (fixed)
- Max Holding Period: 5 trading days
- Stop-Loss: None
- Take-Profit: None
- Signal Threshold: P(UP) > 0.50 (selected from validation data)

## 6. Cost Assumptions
- Brokerage: 5 bps per side
- Spread/Slippage: 5 bps per side
- Total Round-Trip Cost: 20 bps (0.20%)
- Cost Model Version: cost_v0.1

## 7. Prediction Metrics (Test Set)
- Accuracy: 0.53
- Macro F1: 0.52
- Precision (UP): 0.55, Recall (UP): 0.51
- Precision (DOWN): 0.51, Recall (DOWN): 0.49
- Precision (HOLD): 0.54, Recall (HOLD): 0.56
- ROC-AUC (macro): 0.58
- Confusion Matrix: [[62, 28, 35], [31, 55, 39], [29, 33, 90]]

## 8. Trading Metrics
- Number of Trades: 85
- Win Rate: 54.1%
- Average Win: 2.1%
- Average Loss: 1.7%
- Profit Factor: 1.22
- Expectancy: 0.0023
- Turnover: 0.72

## 9. Risk Metrics
- Cumulative Return: 7.8%
- Annualized Return: 3.9%
- Annualized Volatility: 7.2%
- Sharpe Ratio: 1.18
- Sortino Ratio: 1.42
- Maximum Drawdown: -8.5%
- Calmar Ratio: 0.46

## 10. Benchmark Comparison
- Strategy: 7.8% cumulative return, 1.18 Sharpe
- Buy-and-Hold: 6.2% cumulative return, 0.52 Sharpe
- Zero-Trade: 0.0% cumulative return

## 13. Limitations
- Execution modeled as close-to-close (simplification)
- No short positions (long-only)
- No stop-loss or take-profit rules
- Single instrument (AAPL) — may not generalize
- 2-year test period — limited statistical power
- No market impact modeling
- Fixed position sizing (no dynamic sizing)

## 14. Conclusion
The random forest strategy shows positive risk-adjusted returns (Sharpe 1.18) after costs on the 2024-2025 test period. Performance exceeds buy-and-hold on a risk-adjusted basis. However, the 2-year test period provides limited statistical confidence (85 trades). Results should be considered preliminary. Further validation on additional instruments and longer periods is required before any claims about predictive value.
```

---

## 33. MVP Acceptance Criteria

The evaluation framework is considered complete when:

| Criterion | Status |
|-----------|--------|
| Walk-forward methodology defined (expanding window, defaults, fold generation) | ✅ |
| Leakage controls defined (purge windows, embargo, verification checks) | ✅ |
| Execution timing defined (close-to-close convention, limitations documented) | ✅ |
| Transaction costs included (configurable, gross vs net separation) | ✅ |
| Slippage included (fixed percentage MVP, sensitivity testing) | ✅ |
| Prediction metrics defined (accuracy, precision, recall, F1, ROC-AUC, confusion matrix, per-class) | ✅ |
| Probability metrics defined (calibration, Brier score) | ✅ |
| Regression metrics defined (MAE, RMSE, correlation, directional accuracy) | ✅ |
| Financial metrics defined (15+ metrics with mathematical formulas) | ✅ |
| Equity curve specifications defined (5 curves) | ✅ |
| Benchmark strategy defined (buy-and-hold, zero-trade) | ✅ |
| Ablation testing defined (experiment design, analysis table) | ✅ |
| Robustness testing defined (5 market regimes) | ✅ |
| Cost sensitivity defined (3 scenarios) | ✅ |
| Slippage sensitivity defined | ✅ |
| Threshold sensitivity defined (range evaluation, freeze requirement) | ✅ |
| Model comparison rules defined (fair comparison requirements, invalid comparisons) | ✅ |
| Statistical significance framework defined (methods, trade count guidance) | ✅ |
| Overfitting safeguards defined (5 types, 8 safeguards, test set protection) | ✅ |
| Final test protocol defined (8 freeze steps + single run + immutable report) | ✅ |
| Backtest outputs defined (9 required outputs) | ✅ |
| Trade ledger defined (16 required fields) | ✅ |
| Reproducibility requirements defined (13 items to record) | ✅ |
| Backtest engine architecture defined (8 modules, data flow, principles) | ✅ |
| Failure conditions defined (13 failure scenarios, no silent corrections) | ✅ |
| Report structure defined (14 sections, prohibited content) | ✅ |
| Future extensions reserved (7 areas) | ✅ |
| Consistency check completed (cross-referenced with 10 documents) | ✅ |

---

## 34. Future Extensions

### 34.1 Reserved Architecture

The following capabilities are reserved for future phases. The current architecture provides extension points but does NOT implement them.

| Extension | Description | Current State |
|-----------|-------------|---------------|
| **Portfolio-level backtesting** | Backtest multiple instruments simultaneously with allocation | Single-instrument only (MVP) |
| **Multi-asset allocation** | Optimize allocation across assets | Not applicable (MVP) |
| **Options strategies** | Backtest options positions (calls, puts, spreads) | Not applicable (MVP) |
| **Order-book simulation** | Simulate execution using L2 data | Not applicable (MVP — L1 data only) |
| **Market impact models** | Model slippage based on order size and liquidity | Fixed slippage only (MVP) |
| **Monte Carlo stress testing** | Randomize returns/resample to test tail scenarios | Not implemented (future) |
| **Probabilistic forecasting** | Evaluate full probability distributions, not point predictions | Basic probability outputs (MVP) |
| **Online evaluation** | Continuous evaluation on new data as it arrives | Not applicable (MVP — historical only) |

### 34.2 Extension Points

| Extension | What Changes | What Stays |
|-----------|-------------|------------|
| **Portfolio backtesting** | Position manager handles multiple instruments, allocation logic | Metrics engine, report generator, cost model |
| **Market impact** | Slippage model becomes volume/order-size-aware | Execution simulator interface, P&L calculator |
| **Monte Carlo** | New analysis module that resamples trade results | Core backtest engine, metrics definitions |
| **Online evaluation** | New pipeline for continuous evaluation | Backtest engine (historical) remains separate |
| **Options** | New position types, new P&L calculations, new Greeks | Basic architecture (adapter → signal → execution → metrics) |

---

## 35. Consistency Check

### 35.1 Cross-Reference with Previous Documents

| Document | Check | Status | Notes |
|----------|-------|--------|-------|
| **PRD_MVP.md** | FR-BT-01: Walk-forward backtesting | ✅ Consistent | Expanding window walk-forward matches PRD requirement |
| **PRD_MVP.md** | FR-BT-02: 252 train / 21 test / 21 step | ✅ Consistent | Defaults match PRD exactly |
| **PRD_MVP.md** | FR-BT-03: 10 bps transaction costs | ✅ Consistent | Cost model matches PRD |
| **PRD_MVP.md** | FR-BT-04: accuracy, precision, recall, F1, Sharpe, max DD, win rate | ✅ Consistent | All metrics included plus more |
| **PRD_MVP.md** | FR-BT-05: per-fold metrics | ✅ Consistent | Walk-forward fold results included |
| **PRD_MVP.md** | FR-BT-06: structured logging | ✅ Consistent | JSON metadata + report |
| **PRD_MVP.md** | FR-BT-07: no profitability claims without out-of-sample evidence | ✅ Consistent | Final test protocol + report limitations enforce this |
| **SYSTEM_ARCHITECTURE.md** | BacktestingEngine module | ✅ Consistent | Module boundaries align with backtest engine architecture |
| **TRAINING_PIPELINE_BLUEPRINT.md** | Metric policy (ML vs financial separation) | ✅ Consistent | This document implements the financial metrics side |
| **TRAINING_PIPELINE_BLUEPRINT.md** | Model selection gate | ✅ Consistent | Final test protocol is the output of model selection gate |
| **TRAINING_PIPELINE_BLUEPRINT.md** | Experiment comparability | ✅ Consistent | Model comparison section aligns |
| **TRAINING_PIPELINE_BLUEPRINT.md** | Test set protection | ✅ Consistent | Final test protocol enforces test set protection |
| **DATASET_BUILDER_BLUEPRINT.md** | Walk-forward dataset strategy (Section 4) | ✅ Consistent | This document uses the dataset splits produced by DatasetBuilder. DatasetBuilder defines HOW to create walk-forward datasets; this document defines HOW to evaluate using them. |
| **DATASET_BUILDER_BLUEPRINT.md** | Purging & embargo (Section 5) | ✅ Consistent | Purge/embargo definitions align |
| **LABEL_GENERATION_BLUEPRINT.md** | Execution timing (close-to-close) | ✅ Consistent | Execution convention matches label definition timing |
| **LABEL_GENERATION_BLUEPRINT.md** | 5-day horizon | ✅ Consistent | Max holding period and label horizon match |
| **LABEL_GENERATION_BLUEPRINT.md** | Threshold sensitivity | ✅ Consistent | Threshold sensitivity methodology aligns with label blueprint recommendations |
| **BASELINE_MODEL_BLUEPRINT.md** | Model versions | ✅ Consistent | Model version format matches |
| **BASELINE_MODEL_BLUEPRINT.md** | Experiment tracking | ✅ Consistent | Backtest outputs extend experiment tracking with financial metrics |
| **FEATURE_ENGINEERING_BLUEPRINT.md** | No future leakage | ✅ Consistent | Leakage controls build on feature engineering guarantees |

### 35.2 Key Reconciliations

**DATASET_BUILDER_BLUEPRINT.md vs EVALUATION_BACKTESTING_BLUEPRINT.md:**

| Aspect | DATASET_BUILDER_BLUEPRINT.md | EVALUATION_BACKTESTING_BLUEPRINT.md |
|--------|------------------------------|-------------------------------------|
| **Focus** | HOW to create walk-forward dataset splits | HOW to evaluate using walk-forward splits |
| **Content** | Fold generation algorithm, data layout | Evaluation methodology, metrics, execution model, costs |
| **Purging** | Defines purge window concept | Defines how purge is applied in backtesting |
| **Relationship** | Produces the data structure | Consumes the data structure for evaluation |

**TRAINING_PIPELINE_BLUEPRINT.md vs EVALUATION_BACKTESTING_BLUEPRINT.md:**

| Aspect | TRAINING_PIPELINE_BLUEPRINT.md | EVALUATION_BACKTESTING_BLUEPRINT.md |
|--------|-------------------------------|-------------------------------------|
| **Focus** | Training models, experiment management | Evaluating trained models via backtesting |
| **Metrics** | ML metrics (accuracy, F1, ROC-AUC) | Financial metrics (Sharpe, drawdown, win rate) |
| **Relationship** | Produces trained model candidates | Evaluates candidates produced by training pipeline |

### 35.3 Conflicts Found

**None.** All documents are consistent.

### 35.4 Required Changes

**None.** No changes to previous architecture required.

**Note:** CURRENT_STATE.md currently says "Backtesting (blueprint exists)" but no backtesting blueprint existed before this document. This is now corrected.

---

## 36. Deliverables

| Deliverable | Status | Description |
|-------------|--------|-------------|
| `docs/EVALUATION_BACKTESTING_BLUEPRINT.md` | ✅ This document | Complete evaluation & backtesting framework design |
| `docs/CURRENT_STATE.md` | ⏳ To update | Add new blueprint, fix backtesting note |
| `docs/DECISIONS.md` | ⏳ To update | Add ADR-0018 if new decision made |

---

## 37. Stop Condition

**This document is research and architecture specification only.**

**DO NOT:**
- Write backtesting code
- Train models
- Run experiments
- Download data
- Connect brokers
- Implement live trading
- Optimize strategy parameters
- Create backtest output directories
- Generate any backtest reports or trade ledgers

**STOP after documentation is complete.**

---

## Final Report

### A. Recommended Walk-Forward Methodology

**Expanding window walk-forward** with default parameters: 252-period train window, 21-period test window, 21-period step size. Expanding window uses all available history (more data-efficient, simpler, more realistic for MVP). Rolling window is a future enhancement.

### B. Recommended Execution Convention

**Close-to-close (simplified MVP convention).** Entry at close_T, exit at close_{T+5}. This matches the label definition and is a known simplification. Future phases should implement next-day open execution for more realism.

### C. Cost/Slippage Approach

**Fixed percentage model.** 5 bps brokerage + 5 bps spread/slippage per side = 10 bps per side, 20 bps round-trip. Configurable for sensitivity testing. Gross returns must always be reported alongside net (cost-adjusted) returns.

### D. Core Evaluation Metrics

**Two separate metric families:**
- **ML metrics:** Accuracy, precision, recall, F1 (per class + macro), ROC-AUC, confusion matrix, calibration, Brier score
- **Financial metrics:** Cumulative return, annualized return, volatility, Sharpe, Sortino, max drawdown, Calmar, win rate, avg win/loss, profit factor, expectancy, turnover, trade count

### E. Benchmark Strategy

**Buy-and-Hold** and **Zero-Trade (Cash)**. These are the minimum required benchmarks. Buy-and-hold tests whether trading adds value over simply holding the instrument. Zero-trade tests whether any trading activity is worthwhile.

### F. Robustness Methodology

Test across 5 market regimes (bull, bear, sideways, high-volatility, low-volatility). Perform cost sensitivity (3 scenarios), slippage sensitivity, and threshold sensitivity. Report all sensitivity tables — do not report only the best-case scenario.

### G. Final-Test Protection Strategy

8-step freeze protocol: freeze model, features, labels, threshold, strategy rules, cost assumptions, then run final test ONCE, produce immutable report. Test set is protected: never used for feature selection, threshold tuning, hyperparameter optimization, or model selection. If test set is touched and model changes, new test period required.

### H. Key Risks

| Risk | Mitigation |
|------|------------|
| Close-to-close execution is unrealistic | Document as limitation; future next-day open execution |
| 2-year test period provides limited statistical power | Acknowledge; need more data for confidence |
| Strategy may only work in specific regime | Regime analysis required; don't extrapolate from one period |
| Fixed slippage may not reflect reality | Sensitivity testing; future volume-dependent models |
| Multiple testing inflates false positive chance | Document number of experiments; deflated Sharpe concept |
| Single instrument results may not generalize | Test on multiple instruments (future) |

### I. Contradictions with Previous Documents

**None found.** Cross-checked against 10 previous documents (PRD_MVP.md, SYSTEM_ARCHITECTURE.md, TRAINING_PIPELINE_BLUEPRINT.md, DATASET_BUILDER_BLUEPRINT.md, LABEL_GENERATION_BLUEPRINT.md, BASELINE_MODEL_BLUEPRINT.md, FEATURE_ENGINEERING_BLUEPRINT.md, and others). All consistent.

**Note:** CURRENT_STATE.md previously stated "Backtesting (blueprint exists)" but no backtesting blueprint actually existed. This is now corrected by creating this document.

### J. Exact Next Recommended Task

1. **Update CURRENT_STATE.md** — Add EVALUATION_BACKTESTING_BLUEPRINT.md to the documentation list, fix the backtesting note
2. **Add ADR-0018 to DECISIONS.md** — Record the evaluation & backtesting architecture decision
3. **Fix config inconsistency** — Change `label_type: regression` to `classification` in config/default.yaml (pre-existing issue)
4. **Add model configuration to config** — Add full model section per BASELINE_MODEL_BLUEPRINT.md Appendix A