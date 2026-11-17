# Prediction Model Research Ledger

**Last consolidated:** 2026-11-17  
**Primary evaluation objective:** out-of-sample market prediction, not a visually convincing dashboard or an assumed trading edge.

## 1. Existing prediction contract

The MVP label engine currently records:

- Target classes: UP / DOWN / HOLD.
- Forward horizon: 5 trading days.
- UP: forward adjusted-close return greater than +1%.
- DOWN: forward adjusted-close return less than -1%.
- HOLD: return inside the fixed threshold band.
- Features are causal and aligned to the prediction timestamp; labels use a future target window and must never leak into features.

This is a documented baseline contract, not necessarily the final target definition for MPFM. The future product intent is UP / DOWN / SIDEWAYS with multiple independently evaluated horizons. The label naming and threshold policy should be formally versioned before a new experiment.

## 2. Model and experiment history

| Experiment/model | Dataset / protocol | Recorded result | Status |
|---|---|---|---|
| Logistic Regression baseline | AAPL daily; versioned feature/label dataset; chronological split | Real-data accuracy roughly 0.32–0.36 in documented run | Implemented; weak baseline |
| Random Forest baseline | Same MVP dataset contract | Validation macro-F1 0.295 on v0.3 in the temporal comparison | Implemented; strongest of recorded v0.3 comparison |
| Temporal LSTM | Same versioned dataset; causal sequences; L=5/10/20 selected on validation | L=10 macro-F1 0.2953; L=5 0.2716; L=20 0.2649 | Candidate only; not promoted |
| LR/RF ensemble + calibration | Chronological out-of-sample validation predictions; validation-only weight/calibrator selection | Ensemble macro-F1 0.186 vs LR 0.240 and RF 0.295 | Candidate only; not promoted |
| Static trading simulation | Existing 0.55 signal threshold | Zero trades in documented static model runs | No trading edge demonstrated |
| Walk-forward LR | 25 folds; 17 trades in documented run | Approximately -7.5% net vs approximately +18.2% buy-and-hold for that period | Negative result; preserve |

The exact run-specific dataset versions and metrics are in the corresponding implementation reports and CURRENT_STATE.md. Do not merge metrics across versions or call the different snapshots one experiment.

## 3. What has actually been implemented

- Logistic Regression and Random Forest baselines.
- Train-only scaling for Logistic Regression.
- Versioned model artifacts and experiment records.
- Chronological validation and test separation.
- Expanding-window walk-forward evaluation with per-fold training and label-overlap purge.
- Long-only close-to-close evaluation engine with explicit transaction-cost assumptions and buy-and-hold / zero-trade benchmarks.
- A temporal LSTM implementation with causal sequence construction and train-only scaler.
- OOS validation ensemble and probability-calibration machinery.
- Model registry with candidate/approval/active states and safe promotion controls.

Implemented machinery is not proof of predictive value. The LSTM and ensemble were registered as candidates and not promoted based on their documented results.

## 4. Target design research — proposed, not yet validated

A prediction contract should be defined separately for each market and horizon. Do not assume one label threshold works across equities, indices, futures, options and different volatility regimes.

Research dimensions to compare:

1. **Direction classification:** UP / DOWN / SIDEWAYS with a neutral band. Compare fixed return bands with volatility-scaled thresholds. Treat this as a proposed study, not an existing feature.
2. **Return regression:** predict a point estimate and compare it with a distributional forecast. Evaluate expected return separately from direction.
3. **Quantile/distribution forecasting:** estimate conditional return quantiles or a predictive distribution so uncertainty is explicit.
4. **Volatility forecasting:** predict future realized volatility or another pre-registered volatility target.
5. **Regime prediction:** classify market conditions using features available at forecast time; test whether regime conditioning adds value beyond a global baseline.
6. **Multi-horizon forecasts:** define each horizon's forecast timestamp, target interval and scoring rule independently. Candidate horizons may include intraday, one-day, five-day and multi-week horizons, but the final set must be chosen based on data rights, data resolution and intended use.

## 5. Model-family comparison roadmap

The existing model families provide the first baselines. The following are candidates for controlled comparison, not claims of implemented capability:

| Family | Role in research | Required comparator / guardrail |
|---|---|---|
| Logistic Regression | Transparent linear baseline | Keep as stable reference |
| Random Forest | Nonlinear tabular baseline | Keep identical point-in-time inputs |
| Gradient-boosted trees (LightGBM / XGBoost; CatBoost if justified) | Strong tabular benchmark | Tune only on train/validation; compare per instrument and pooled |
| Temporal LSTM | Sequence baseline already implemented | Re-run only after valid multi-instrument data and target definition |
| Temporal convolution / transformer-family models | Sequence-model candidates | Must beat simpler baselines on untouched time periods |
| Shared financial-state encoder / MPFM | Main research thesis | Must demonstrate transfer benefit through pre-registered ablations |
| Ensemble / stacking | Combine models only if errors are complementary | Test calibration and economic value; do not assume averaging helps |

No foundation model should be called superior unless it improves over strong, appropriately tuned non-foundation baselines under the same data, target and evaluation contract.

## 6. Experiment register

All experiments below are proposed until a dated run record is added.

| ID | Hypothesis / question | Minimum comparison | Status |
|---|---|---|---|
| PRED-001 | Strong tabular models can improve on LR/RF baselines | LR, RF, boosted trees on same point-in-time dataset | Proposed |
| PRED-002 | Volatility-scaled neutral bands produce more stable direction targets than fixed ±1% | Fixed-band vs volatility-scaled labels; no test tuning | Proposed |
| PRED-003 | Cross-sectional training improves transfer to unseen instruments | Per-instrument models vs pooled model; hold out instruments | Proposed |
| PRED-004 | Market/sector context adds incremental signal | Instrument-only vs instrument + index/sector features | Proposed |
| PRED-005 | Regime conditioning improves conditional forecast quality | Global model vs regime-conditioned model; define regime causally | Proposed |
| PRED-006 | Fundamentals add predictive information beyond price/volume | Market-only vs point-in-time fundamentals ablation | Blocked by licensed historical source |
| PRED-007 | News/event information adds incremental predictive information | Market-only vs as-of news/event features | Blocked by licensed historical source |
| PRED-008 | Foundation pretraining transfers to downstream market tasks | Same downstream tasks; pretrained vs scratch vs strong tabular baseline | Unproven |
| PRED-009 | MPFM generalizes compositionally | Hold out instrument × regime × mandate combinations | Unproven; real-market test pending |
| PRED-010 | Probability/return uncertainty is reliable | Calibration, coverage and proper scoring rules on untouched periods | Proposed |
| PRED-011 | Model gains survive costs and realistic execution | Freeze forecast, signal and costs before test; compare benchmarks | Not demonstrated |

## 7. Evaluation contract

### Prediction quality

For classification, report at minimum class distribution, balanced accuracy, macro precision/recall/F1, confusion matrix, per-class recall, log loss and Brier score where probabilities are available. Report PR-AUC/ROC-AUC only when their class definitions and applicability are explicit.

For return forecasts, report MAE/RMSE and proper scoring rules appropriate to the predicted distribution. For quantile forecasts, report quantile loss and empirical coverage. For volatility forecasts, use a target-specific loss and compare with simple historical-volatility baselines.

### Probability and uncertainty quality

Report reliability diagrams or equivalent calibration diagnostics, Brier score, log loss and expected calibration error with sample counts. Do not use the maximum class probability as a calibrated confidence score without validation.

### Financial utility

Only after prediction quality is reported separately, evaluate net return, benchmark-relative return, Sharpe/Sortino, maximum drawdown, turnover, trade count, win/loss distribution, exposure and costs. Include slippage, fees, spread, liquidity constraints and realistic timing assumptions. No-trade or insufficient-sample results must be reported as such, not hidden.

## 8. Leakage and validation constraints

- Use strict chronological train / validation / test splits.
- Use purge/embargo when forward-label windows overlap evaluation boundaries.
- Fit scalers, imputers, encoders, feature selection and calibration only on training/validation data as appropriate.
- Do not use future-restated fundamentals or information published after the prediction time.
- Do not let final-test results influence labels, feature selection, threshold selection, architecture or model promotion.
- Run multiple chronological windows and instrument-level holdouts; one ticker and one split are not enough to establish generalization.
- Keep the backtest cost model and execution convention fixed before final evaluation.
- Record all runs, including rejected candidates and failed hypotheses.

## 9. Immediate next actions

1. Freeze the intended forecast horizons and target definitions.
2. Establish licensed multi-instrument point-in-time data and a reliable security master.
3. Run PRED-001 before adding model complexity.
4. Run target/threshold sensitivity on validation only (PRED-002).
5. Expand to cross-instrument and regime-held-out evaluation.
6. Only then test the MPFM pretraining and compositional-generalization hypotheses.
