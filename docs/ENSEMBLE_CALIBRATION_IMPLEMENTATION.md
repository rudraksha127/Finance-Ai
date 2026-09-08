# ENSEMBLE & PROBABILITY CALIBRATION IMPLEMENTATION (Post-MVP Milestone 07)

Status: IMPLEMENTED (research-only). This milestone first ANSWERS whether the
baseline and temporal models are complementary, and only then implements a
controlled ensemble + calibration layer. No new data sources, no live trading,
no LLM agent, no blind model combination.

---

## Measured results (dataset v0.3, AAPL daily)

**Diversity (validation, 119 rows):** the models ARE complementary —
prediction agreement 0.412, mean |ΔP(UP)| 0.153, P(UP) correlation **−0.175**.
An ensemble was therefore justified to evaluate (not forced).

**Weight selection (validation log loss, constrained 0.1-grid):** w = 0.2 →
`P = 0.2·P_logistic + 0.8·P_temporal` (grid minimum 1.0947 at w=0.2 vs 1.0953
at w=0.0 and 1.1039 at w=1.0).

**Calibration:** multinomial-logistic (Platt) on validation rows; Brier and
10-bin ECE recorded raw vs calibrated in the artifact
(`calibration_v0.1`).

**Validation comparison (honest result — the ensemble does NOT improve):**

| Model | Val accuracy | Val f1_macro | Val ROC-AUC (OvR) |
|---|---|---|---|
| logistic_regression_v0.3 | 0.3277 | 0.2399 | — |
| temporal_lstm_v0.1 | 0.3697 | 0.2953 | 0.4569 |
| ensemble_v0.1 | 0.3866 | **0.1859** | 0.4174 |

**Final-test backtests (existing engine, frozen config):** all three models
produce 0 trades at the 0.55 signal threshold → cumulative return 0.0,
max drawdown 0.0 (buy-and-hold +23.0%). No profitability claim is made.

**Decision:** `ensemble_v0.1` registered as **CANDIDATE**; NOT approved for
activation — accuracy improves marginally but f1_macro regresses materially
against both constituents, and the financial metrics are identical (no
trades). Per the promotion policy (section 26 of the milestone), an ensemble
that improves one metric but worsens another stays CANDIDATE.

---

## 1. Do we need an ensemble? (measured, not assumed)

Diversity is measured on **validation** predictions of the two constituents —
both trained on TRAIN only (their validation predictions are therefore
out-of-sample w.r.t. their own training; no fold ever saw its own target rows):

- prediction agreement rate (same argmax class)
- probability disagreement (mean absolute difference of P(UP))
- probability correlation (Pearson, P(UP) vs P(UP))

The measured result for dataset v0.3 / AAPL is recorded in
`data/ensemble/experiments/` and summarised in CURRENT_STATE.md. If the models
are highly redundant, the honest answer is "no ensemble" — documented, not forced.

## 2. Out-of-fold methodology

The project's chronological split IS the fold structure: TRAIN → fit; VAL →
out-of-sample predictions. Both constituents' `val_predictions.csv` are
collected and timestamp-aligned. No random K-fold is used. The final TEST
period is never touched during weight selection or calibration fitting
(final-test protection, milestone section 8).

## 3. Model output contract

Both constituents are normalized to probability vectors in the canonical
class order `("UP", "DOWN", "HOLD")`. sklearn estimators expose
`classes_` in alphabetical order (`DOWN, HOLD, UP`); the ensemble wrapper
reorders **explicitly** using each constituent's `classes_` — class ordering is
never inferred from column position or dictionary order (milestone section 21).

Alignment validation before combining (section 20): identical timestamps,
identical row counts, valid probability vectors (each row sums to 1, all
finite), same class order after explicit reordering. Any mismatch FAILS loudly.

## 4. Calibration

- **Method**: multinomial logistic regression (Platt-style) fitted on the
  ensemble's validation probability vector (3 features) → label. Simplest
  defensible method; no isotonic (too few validation rows for reliable
  step-fitting at this dataset size).
- **Data policy**: fitted on VALIDATION only; frozen before any final-test
  evaluation; never fitted on test/live outcomes.
- **Versioning**: `calibration_v0.1` artifact with method, constituent
  versions, dataset/feature/label versions, coefficients, creation timestamp.
- **Evaluation**: multiclass Brier score + expected calibration error (ECE,
  10 confidence bins) — raw vs calibrated, on validation.

## 5. Ensemble strategies evaluated

A. **Simple average**: `P = (P_A + P_B) / 2` — evaluated first (section 15).
B. **Validation-derived weighted average**: `P = w·P_A + (1−w)·P_B`, weight
   selected by constrained grid search (w ∈ {0.0, 0.1, …, 1.0}) minimizing
   validation log loss. No unrestricted optimization; weights never touch the
   final test.

The selected configuration is frozen BEFORE the final test evaluation.

## 6. Artifact and registry

- `models/ensemble_v0.1/{model.joblib, metadata.json}` — same layout as every
  other model, so the existing backtest engine, API resolver, and registry work
  unchanged.
- `model.joblib` contains a torch-free `EnsemblePredictor` wrapper embedding
  both constituent wrappers (the temporal wrapper is numpy-only; the logistic
  constituent carries its own scaler), the explicit class-order mapping, the
  weight, and the calibration coefficients.
- Registered as **CANDIDATE** via the existing registry lifecycle; never
  auto-activated.

## 7. Evaluation protocol

Same target, horizon, dataset period, feature/label versions, cost model, and
slippage as every other model. Final out-of-sample comparison runs all three
models through the EXISTING backtest engine on the frozen test split:

| Model | Predictive (val) | Financial (test backtest) |
|---|---|---|
| logistic_regression_v0.3 | validation metrics | static backtest |
| temporal_lstm_v0.1 | validation metrics | static backtest |
| ensemble_v0.1 | validation metrics | static backtest |

No single-metric promotion: the ensemble is rejected or kept as CANDIDATE
based on the full picture (predictive + financial + risk), per the existing
promotion gates.

## 8. Reproducibility

Same constituents + dataset + calibration + ensemble config → identical
weights, identical calibration coefficients, identical probabilities
(deterministic grid search; no randomness in the ensemble path).

## 9. Failure handling

Explicit failures with context: missing constituent artifact, version
mismatch, class-order mismatch, timestamp misalignment, invalid probabilities
(NaN/Inf, not summing to 1), missing calibration artifact, invalid weights.
Never substitute missing predictions with zeros.

## 10. Compatibility

- **Drift monitoring**: the ensemble exposes prediction distributions and
  model identity like any other model; the existing drift engine can monitor
  it as another model (no separate system).
- **Inference API**: the artifact layout is identical to baseline models, so
  the existing resolver can resolve `ensemble_v0.1` by version — no API
  redesign, no automatic activation.
- **Retraining**: metadata records constituent versions, weights, and
  calibration version so a future retraining run can reproduce the ensemble.

## 11. Known limitations

- Two constituents only; no stacking, no regime switching.
- Calibration fitted on ~119 validation rows — small; documented, not hidden.
- Ensemble value depends on measured diversity; with highly redundant
  constituents the honest result may be "keep the simpler model".
- Research-only. No live trading, no automatic promotion.
