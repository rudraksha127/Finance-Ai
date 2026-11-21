# MPFM Backend Model Research, Algorithm Design & Benchmark Programme

**Research cut-off:** 2026-11-21  
**Repository:** `rudraksha127/Finance-Ai`  
**Priority:** Backend models, algorithms, reproducible experiments, statistical validation and inference performance  
**Status:** Research synthesis and proposed programme; new algorithms below are hypotheses, not proven improvements  
**Parent product:** Finance AI  
**Research/model architecture:** MPFM  
**Existing development dependency order:** D0 → D1 → D2 → D3 → D4

> This document defines the technical research mission for MPFM's autonomous agents and human engineering work. It distinguishes (1) what the current repository has implemented, (2) findings from published papers/preprints, and (3) new MPFM hypotheses that still require implementation and out-of-sample validation. No performance gain or originality claim is made for the proposed algorithms.

---

## 1. Strategic objective: model quality first

The main mission of the autonomous research system is to improve the backend's ability to produce reliable, calibrated and economically useful forecasts under realistic data and latency constraints.

The agents should spend most of their research and engineering effort on:

1. Reading and tracking current primary papers, benchmark suites, model implementations and relevant open-source repositories.
2. Reproducing strong published baselines on the same data and target contract.
3. Improving point-in-time data, labels, features, model architectures and training objectives.
4. Designing falsifiable algorithm hypotheses based on measurable weaknesses in existing methods.
5. Implementing experiments with reproducible code, versioned data and frozen configurations.
6. Reporting classification, regression, ranking, probabilistic, portfolio, robustness and runtime metrics.
7. Using independent reviewers to detect leakage, benchmark misuse, statistical overclaiming and implementation bugs.
8. Promoting no model unless it beats relevant baselines on untouched data and satisfies calibration, risk, operational and latency gates.

Documentation is an evidence record. It is not the primary output. The primary output must be tested algorithms, reproducible experiments, validated model artifacts and measured improvements.

### Important distinction

- **Forecast quality:** Does the model predict the target better than strong baselines?
- **Decision quality:** Does the forecast support a better decision under a defined policy?
- **Execution quality:** Can the intended transaction be achieved with realistic fills and costs?
- **Economic result:** Does the resulting strategy show robust net outcomes out of sample?
- **Operational quality:** Does the model meet latency, reliability, monitoring and recovery requirements?

A high F1 score does not establish profitable trading. A profitable historical backtest does not establish robust prediction. A low-latency model does not establish alpha.

---

## 2. Existing Finance AI baseline — preserve and improve, do not overwrite

The repository README and research records document the following:

- Historical Yahoo Finance OHLCV adapter; documented intervals are daily, weekly and monthly.
- Cleaning, data quality, immutable raw storage and corporate-action adjustment support.
- A versioned 52-feature MVP feature set.
- UP/DOWN/HOLD labels, five-trading-day horizon and fixed ±1% thresholds.
- Versioned datasets with chronological TRAIN/VALIDATION/TEST splits and purge/embargo support.
- Logistic Regression and Random Forest baselines.
- Walk-forward backtesting.
- Research-only FastAPI inference and React dashboard.
- Temporal LSTM candidate and LR/RF ensemble/calibration experiments.
- Incremental data pipeline, drift detection, retraining controls, model registry and operations monitoring.
- Point-in-time multimodal data contracts, using availability time for external-data joins.

### 2.1 Existing documented empirical results

The September 8, 2026 integration report records an AAPL daily-data workflow. The results below are the historical repository record, not fresh runs in this research session.

| Experiment | Documented result | Interpretation |
|---|---:|---|
| Logistic Regression | ROC-AUC 0.538; PR-AUC 0.380; macro-F1 0.240 | Weak baseline |
| Random Forest | ROC-AUC 0.476; PR-AUC 0.370; macro-F1 0.232 in the M11 run | No strong out-of-sample evidence |
| Logistic Regression walk-forward | 26 folds, 17 trades, −7.5% net, Sharpe −0.214 | Negative result; retain in ledger |
| Static backtest | 0 trades at 0.55 threshold | Current decision threshold yielded no opportunities |
| Temporal LSTM candidate | Validation macro-F1 0.2953 at sequence length 10; 0 trades in documented test run | Candidate, not promoted |
| LR/RF ensemble | Macro-F1 0.186 vs constituent macro-F1 0.240 / 0.295 | Ensemble regressed; not promoted |
| Inference API performance smoke | Median 2.4 ms, p95 3.3 ms, n=50 | Small historical smoke test; not end-to-end feed-to-decision latency |

Sources inside repository:
- `README.md`
- `docs/MVP_INTEGRATION_QA_REPORT.md`
- `docs/CURRENT_STATE.md`
- `docs/ENSEMBLE_CALIBRATION_IMPLEMENTATION.md`
- `docs/TEMPORAL_MODEL_IMPLEMENTATION.md`
- `docs/research/MPFM_RESEARCH_MASTER.md`
- `docs/research/PREDICTION_MODEL_RESEARCH.md`

### 2.2 What this evidence does and does not say

It shows that a reproducible research pipeline exists. It does not show that MPFM predicts Indian markets accurately, that a foundation model improves the baseline, or that any trading strategy is profitable.

A new research agent must not tune against the old test split. New experiments require a newly defined, versioned and untouched evaluation period, a larger instrument universe and a clear target/horizon contract.

---

## 3. Latest research and what MPFM should learn from it

The following papers were checked against their accessible primary paper pages as of 2026-11-21. Results are reported as the authors' results on their stated datasets and protocols; they are not transferable performance guarantees for NSE, BSE or MCX.

### 3.1 FinVerse: Financial Time-Series Benchmark (4 August 2026)

Paper: https://arxiv.org/abs/2608.03259

**Contribution**
- Financial benchmark with 116,897 series and 171.1 million observations in the data artifact.
- Evaluated target set: 60,232 series and 17.4 million observations.
- Evaluates 43 public time-series foundation models.
- Defines 11 metric families and 78 metrics, selected according to economic meaning.
- Separates point-wise forecasting, cross-sectional ranking and realised portfolio outcomes.

**Important findings**
- Reverso Small ranks first overall; TiRex 1.1 leads point-wise forecasting; Chronos-2 Synth leads portfolio evaluation in the study.
- The model ranked best by point-wise performance is not necessarily best by ranking or portfolio outcomes.
- FinVerse reports only moderate correlation between its model ordering and GIFT-Eval overall rankings (Pearson r=0.40).
- Point-wise and cross-sectional ranks are more aligned (r=0.72) than point-wise and portfolio ranks (r=0.37).

**MPFM implication**

Adopt a multi-view benchmark. Do not rank candidate models using accuracy/F1 or MAE alone. Every model needs forecast metrics, ranking metrics and a separate cost-aware portfolio evaluation.

### 3.2 Pretrained Time-Series Foundation Models for Financial Return Forecasting (25 June 2026)

Paper: https://arxiv.org/abs/2606.27100

**Models evaluated**
- TimeGPT / TimeGPT-LH, TimesFM-2.5, Moirai-2.0, Chronos and Chronos-2.
- Scratch-trained comparators: NBEATS, NHITS, PatchTST, iTransformer and KAN.
- Assets: AAPL, AMZN, GOOG, JPM and META.
- Linear and logarithmic returns, equalised context length and rolling-origin evaluation.

**Reported results**
- Pretrained TSFMs account for 8 of 10 task-level wins in the benchmark's aggregate ranking.
- Moirai-2.0 and TimesFM-2.5 have the strongest average ranks in the paper.
- iTransformer wins both META tasks, showing that generic pretraining is not uniformly superior.
- Gains over a zero-return/random-walk baseline are small and sparse.
- A one-sided Diebold–Mariano test finds statistically significant improvement over the random-walk benchmark only for Chronos on AMZN and Moirai-2.0 on GOOG in the reported comparisons.
- The authors warn that raw p-values across many comparisons are exploratory; family-wise correction is more conservative.

**MPFM implication**

Benchmark pretrained models as candidate priors, not assumed alpha engines. Include zero-return/random-walk and local supervised baselines, and require statistical evidence of improvement rather than model leaderboard rank.

### 3.3 Towards Financial World Modeling / TFWM (6 October 2026)

Paper: https://arxiv.org/abs/2610.09048  
Project: https://github.com/fin-ai-lab/tfwm  
Data pipeline: https://github.com/fin-ai-lab/market-1t

**Contribution**
- Market-1T contains nearly one trillion one-second observations across US equities from 2008–2025.
- Studies 18 encoder-training strategies.
- Evaluates representations on future return, volatility change and quoted spread change at a 15-minute horizon.
- Samples 32 evaluation months across multiple regimes.
- Uses Rank IC as the principal reported representation-probe metric.

**Selected reported Rank IC results**

| Training approach | Return Rank IC | Volatility Rank IC | Spread Rank IC |
|---|---:|---:|---:|
| Supervised return specialist | 0.0272 | 0.0695 | 0.1305 |
| Supervised volatility specialist | 0.0197 | 0.0883 | 0.1480 |
| Supervised spread specialist | 0.0178 | 0.0762 | 0.2517 |
| Supervised multihead | 0.0311 | 0.0941 | 0.2455 |

**Important findings**
- Jointly supervised return/volatility heads improve the reported return and volatility representation metrics relative to the specialist entries.
- Spread performance falls slightly from the standalone spread specialist to multihead, suggesting task-specific information and negative transfer.
- Several self-supervised objectives do not beat the random/untrained encoder floor on all targets.
- The paper shows substantial performance variation across evaluation months; a narrow time split can misrepresent generalisation.
- ViT-Tiny can outperform larger models at a fixed compute budget in the tested setting.

**MPFM implication**

Use shared representations for tasks with evidence of common structure, but preserve specialist heads or experts for different market phenomena. Compare supervised, self-supervised and random/untrained controls. Evaluate across many months/regimes, not just random seeds.

### 3.4 TensorLOB: Structure-Preserving Tensor Learning for Limit Order Book Forecasting (2 November 2026)

Paper: https://arxiv.org/abs/2611.02866

**Core idea**

A limit order book naturally has separate dimensions:
- Time.
- Bid/ask side.
- Price level.
- Attributes such as price and volume.

TensorLOB models this as a multiway tensor rather than flattening all dimensions into one vector. It uses mode-wise tensor contractions and a low-rank CP-parameterised classifier.

The paper reports 2,115 classifier parameters versus 14,403 for the corresponding dense classifier configuration (85.3% reduction in that classification layer).

**Experiment**
- FI-2010 dataset.
- Three classes: down, stationary and up.
- Prediction horizons: 10, 20, 50 and 100 future events.
- Most recent 100 LOB events as model input.
- First seven trading days for development and final three for test.
- Three seeds: 7, 42, 123.
- Reported accuracy, weighted precision, weighted recall and weighted F1.

**TensorLOB reported performance**

| Horizon | Accuracy | Weighted precision | Weighted recall | Weighted F1 |
|---|---:|---:|---:|---:|
| 10 events | 83.5 | 83.0 | 83.5 | 82.5 |
| 20 events | 74.0 | 73.2 | 74.0 | 72.2 |
| 50 events | 77.5 | 77.5 | 77.5 | 77.4 |
| 100 events | 79.1 | 79.1 | 79.1 | 79.1 |

Values are percentages, as reported in the paper.

**Caveats**
- This is an arXiv paper and should be treated as a research result until independent replication.
- FI-2010 is a small historical benchmark spanning ten trading days, not a broad modern multi-market validation set.
- Some comparator models collapse toward the majority stationary class at certain horizons; the paper explicitly notes this. Accuracy and weighted scores can therefore hide minority-class weakness.
- The weighted recall is mathematically equal to accuracy for single-label multiclass classification; retaining both columns does not provide two independent signals.
- FI-2010 performance does not predict NSE/MCX performance.

**MPFM implication**

Reproduce the tensor-preserving inductive bias where sufficient market depth data is lawfully available. Add macro-F1, per-class precision/recall, balanced accuracy and calibration. Benchmark against a majority-class baseline and inspect the confusion matrix.

### 3.5 TailDART: Compute-Efficient Foundation Models for Financial Time-Series Forecasting (6 November 2026)

Paper: https://arxiv.org/abs/2611.09176

**Core idea**
- Compact 2.68M parameter time-series model.
- Grouped-query attention (GQA) to reduce key/value memory bandwidth.
- Dense and mixture-of-experts variants.
- Johnson SU probabilistic distribution head.
- Evaluated on the BForTFin financial benchmark, comprising 73 series across eight asset classes, sampled at daily, weekly and monthly frequencies.

**Reported efficiency**
- Dense TailDART latency: 0.668 ms daily, 0.689 ms weekly, 0.912 ms monthly per forecast step in the paper's setup.
- It reports up to 48.1% lower inference latency than Lag-Llama under matched workload conditions.
- The paper reports a 0.912 ms monthly result versus 16.806 ms for Moirai in one comparison.

**Caveats**
- This is an arXiv preprint; do not treat the result as independently reproduced.
- Its pretraining pool is a heterogeneous set of public time-series collections, not a purpose-built high-frequency Indian LOB corpus.
- The reported sub-millisecond measurement is model forecast-step latency, not exchange feed receipt → parsing → feature update → inference → risk → broker acknowledgement end-to-end latency.
- The authors note that instrument-level duplicate/overlap checks against FX and rates were incomplete, so source overlap could not be ruled out in their benchmark audit.
- The model's reported results are largely daily/weekly/monthly; they do not establish a sub-millisecond intraday trading strategy.

**MPFM implication**

Study GQA, compact backbones, distributional heads and accuracy-latency Pareto frontiers. Benchmark on our own hardware and actual input shapes. Keep inference latency separate from full-system latency.

### 3.6 LiT: Limit Order Book Transformer (Frontiers in Artificial Intelligence, 2025)

Paper: https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1616485/full

**Core idea**
- L2 Binance order-book snapshots, top 20 levels on both bid and ask sides.
- Approximately one million reconstructed LOB snapshots across September–December 2024 data.
- Input uses two channels: price and volume.
- Structured patches represent both bid/ask spatial structure and local time windows.
- Transformer layers model spatial/temporal interactions, followed by LSTM layers.

**Reported 300 ms–1,000 ms horizon**

| Model | Precision | Recall | F1 | Accuracy |
|---|---:|---:|---:|---:|
| LSTM | 65.77 | 67.64 | 66.10 | 67.63 |
| DeepLOB | 65.92 | 67.76 | 66.23 | 67.76 |
| TransLOB | 65.83 | 68.25 | 65.68 | 68.25 |
| LiT | 66.20 | 68.34 | 66.40 | 68.34 |

Values are percentages, as reported.

**Distribution-shift result**
- The paper pretrains on September and evaluates later months.
- Zero-shot scores degrade by roughly five percentage points on several November/December metrics in the reported setting.
- Fine-tuning on recent data improves over zero-shot and from-scratch in the paper's experiment.

**Caveats**
- It uses Binance crypto order-book data, not Indian equities.
- The authors selected a threshold of 0.000015 to balance label distribution.
- These results describe classification of short-horizon mid-price movement, not profitable execution after order queue, fees, slippage and market impact.
- Its results must be reproduced on separate, licensed Indian data before reuse claims.

**MPFM implication**

Structured LOB patching and recent-data adaptation deserve a benchmark track. Measure shift and refresh policy rather than deploying a frozen model indefinitely.

### 3.7 Evaluation Integrity in Machine Learning for Finance (20 July 2026 working paper)

Paper: https://papers.ssrn.com/sol3/Delivery.cfm/7007079.pdf?abstractid=7007079&mirid=1

The accessible abstract systematises leakage, backtest overfitting, reproducibility and multiple testing across the finance ML pipeline. It discusses optimism gaps, Deflated Sharpe Ratio, Probability of Backtest Overfitting, purged/combinatorial cross-validation and falsification audits.

**MPFM implication**

The model research system must count and record all tried hypotheses and hyperparameters; it must not select the best among hundreds of experiments and report it as if it were a pre-registered test.

This is a working paper; use it as a review checklist, not as settled consensus.

### 3.8 FinCast: A Foundation Model for Financial Time-Series Forecasting (ACM CIKM 2025)

Paper: https://doi.org/10.1145/3746252.3761261

The paper proposes a financial time-series foundation model intended to address temporal non-stationarity, multi-domain diversity and differing time resolutions. It is a relevant prior-art/model-family candidate for the MPFM foundation-model benchmark. The accessible publication abstract makes broad comparative claims, but no numerical result is adopted here without a fully inspected benchmark table and reproducible code/data conditions.

**MPFM implication**

Add FinCast to the paper inventory and reproduction candidate list; do not copy a headline performance claim into our scorecard.

### 3.9 Literature-level conclusion

The recent literature does not support a strategy of simply selecting the largest foundation model. It points toward:

1. Finance-specific targets and metrics.
2. Strong naive and classical baselines.
3. Asset-, task- and horizon-dependent model selection.
4. Regime and temporal-shift testing.
5. Structured order-book representations when depth data are available.
6. Compact architectures when latency and compute budgets matter.
7. Calibration and abstention rather than forced predictions.
8. Separation of forecast metrics from realised net economic results.

---

## 4. MPFM's unified benchmark contract

All model candidates must use one versioned benchmark contract per problem family.

### 4.1 Prediction targets must be independent by horizon

Do not treat all model tasks as the same target. Define separate contracts for:
- Direction: DOWN / FLAT / UP.
- Forward return: point and distribution forecasts.
- Volatility: future realised volatility or variance.
- Regime: trend/range/high-volatility/liquidity regime (with versioned, non-leaking definitions).
- Liquidity/spread: future quoted spread, realised spread or depth state.
- Cross-sectional ranking: rank instruments by expected return/risk.
- LOB mid-price movement: event/time horizon classes.
- Fill probability / time-to-fill: only when order-level/event data support valid labels.

For every target, store:
- Target formula/version.
- Instrument universe and point-in-time membership.
- Prediction issue time.
- Forecast horizon.
- Label availability time.
- Threshold and class distribution.
- Costs and execution assumptions if applicable.

### 4.2 Classification metrics

Required report:
- Confusion matrix.
- Accuracy.
- Balanced accuracy.
- Per-class precision, recall and F1.
- Macro-F1 (primary balanced summary).
- Weighted-F1 (supplementary).
- Micro-F1 where appropriate.
- Matthews Correlation Coefficient (MCC).
- One-vs-rest ROC-AUC and PR-AUC / Average Precision per class where mathematically valid.
- Class prevalence and majority-class accuracy.
- Threshold-specific precision/recall and coverage.

**Primary interpretation**
- Accuracy alone is not sufficient with imbalanced classes.
- Weighted-F1 can mask poor minority-class detection.
- Macro-F1 averages class-level F1 and is more useful when each class matters.
- For a trading opportunity detector, also report precision/recall at the actual decision threshold and the fraction of observations on which the model abstains.

### 4.3 Regression and directional metrics

Required report:
- MAE.
- RMSE.
- MASE and relative MAE against an explicit no-change/random-walk baseline.
- sMAPE only where its denominator makes sense; do not use it blindly on near-zero returns.
- Directional hit ratio.
- First- and second-order directional hit ratio when economically justified.
- Pearson IC and Spearman Rank IC.
- IC information ratio and time/regime stability.

For returns, calculate errors on returns or economically meaningful changes rather than relying only on non-stationary price-level RMSE.

### 4.4 Probabilistic forecast metrics

Required report:
- Negative log likelihood / log loss.
- Brier score.
- Expected Calibration Error (ECE), with reliability diagram.
- Class-conditional calibration.
- Pinball loss for quantiles.
- Continuous Ranked Probability Score (CRPS) for distribution forecasts.
- Prediction interval coverage and interval width.
- Tail calibration and VaR exceedance diagnostics where relevant.

A model with high confidence and poor calibration is not suitable for decision intelligence.

### 4.5 Volatility and risk forecast metrics

Required where volatility is predicted:
- QLIKE.
- MAE/RMSE of realised volatility or variance.
- Rank IC for cross-sectional volatility forecasts.
- VaR coverage and exceedance clustering.
- Expected Shortfall / CVaR estimation error where labels permit.

### 4.6 Cross-sectional and portfolio metrics

Required:
- Pearson IC / Spearman Rank IC.
- ICIR and rank stability.
- Long-short/top-k spread with explicit universe and rebalance schedule.
- Turnover and concentration.
- Annualised net return and volatility.
- Sharpe and Sortino.
- Calmar ratio.
- Maximum drawdown and drawdown duration.
- Profit factor, win rate, average win/loss and expectancy.
- Exposure, leverage, capacity and concentration.
- Brokerage, taxes, exchange charges, spread, slippage, market impact and borrow/carry assumptions.
- Fill ratio and unfilled quantity if simulated fills are used.
- Net results by instrument, date range, market regime and liquidity bucket.

Portfolio metrics must be computed using a frozen portfolio rule. Do not tune portfolio weights on the final test period.

### 4.7 Statistical evidence and overfitting diagnostics

Required for any model selected from many candidates:
- Diebold–Mariano test for forecast-loss comparisons where assumptions and loss sequence support it.
- Block bootstrap confidence intervals for dependent financial observations.
- Multiple-testing adjustment (e.g. Benjamini–Hochberg or another predeclared correction).
- Deflated Sharpe Ratio for strategy selection bias.
- Probability of Backtest Overfitting / combinatorial purged CV when the experiment design supports it.
- Purged and embargoed chronological folds where label windows overlap.
- Final untouched holdout.
- Full experiment count and model-selection history.

A small p-value in one asset/horizon does not establish a general market edge. Include effect size, uncertainty and the universe of attempted comparisons.

### 4.8 Runtime and engineering performance

Every model report must include:
- CPU and GPU hardware.
- Software/runtime versions.
- Model parameter count and artifact size.
- Cold-start time.
- Warm inference latency P50, P95, P99 and P99.9.
- Throughput at stated batch size and input shape.
- Peak memory and accelerator utilisation.
- Queueing time separately from compute time.
- Data decoding and preprocessing time separately from model inference.
- End-to-end market-event-to-decision latency separately from model-only latency.

The P50/P95/P99 of an offline batch benchmark is not interchangeable with production feed-to-decision latency.

---

## 5. Mandatory benchmark families

Do not force one model family across all frequencies and targets. Use separate leaderboards.

### Track A — Daily/swing return and direction

Baselines:
- Zero-return/random-walk and persistence.
- Historical mean / volatility-scaled naive forecasts.
- AR / ARIMA / ETS where appropriate.
- Logistic Regression and Ridge.
- Random Forest, XGBoost, LightGBM or CatBoost.
- GARCH/HAR-RV for volatility-specific tasks.
- LSTM/GRU, TCN, N-BEATS/N-HiTS.
- PatchTST, iTransformer and other transformer baselines.
- TimesFM, Chronos, Moirai and other TSFMs after input/target compatibility checks.
- MPFM candidate encoders.

### Track B — Intraday bars and event-driven returns

Baselines:
- No-change / recent-return / time-of-day baselines.
- Linear/logistic and regularised statistical baselines.
- Tree models on causally computed technical/volume/volatility features.
- TCN, LSTM/GRU and compact temporal transformers.
- Regime-specific and horizon-specific heads.
- Compact probabilistic model with calibrated distributional output.

### Track C — L2/L3 order-book and microstructure

Baselines:
- Mid-price no-change / majority class.
- Order-flow imbalance and queue/depth imbalance linear/logistic models.
- XGBoost/LightGBM on engineered microstructure features.
- DeepLOB and TransLOB reproduction.
- LiT reproduction.
- TensorLOB reproduction or independent tensor-structured implementation.
- MPFM tensor/temporal specialist candidate.

Only run this track with the correct permitted depth/event data. Daily OHLCV must not be used as a substitute for order-book history.

### Track D — Fundamentals, filings, news and macro

Baselines:
- Price/volume-only model.
- Fundamentals-only model.
- Event/news-only model.
- Macro-only model.
- Late-fusion model.
- Reliability-gated multimodal model.

Each modality must have its own publication, ingestion and availability timestamps. Run ablations to quantify incremental value beyond the price-only baseline. Missing modality must be represented as missing, not fabricated.

### Track E — Financial state representations / foundation models

Compare:
- Random/untrained encoder floor.
- Supervised single-task encoder.
- Supervised multi-task encoder.
- Self-supervised temporal/contrastive/JEPA-style objectives.
- Frozen pretrained TSFM embeddings/probes.
- Fine-tuned pretrained models.
- MPFM candidate representation.

Use common data, split, compute budget, probe and downstream tasks where possible. Measure latent structure as well as downstream predictive utility.

### Track F — Latency and deployment

Compare model-only latency and full event pipeline separately. Include:
- CPU baseline.
- CPU vectorised/compiled inference.
- ONNX or other supported inference runtime only if model parity is verified.
- Quantised variant.
- GPU variant where throughput improves under the actual batch/latency target.
- Rust/C++ hot-path wrapper only after profiling identifies a real bottleneck.

A faster model that loses calibration or predictive quality is not automatically an improvement.

---

## 6. Proposed original MPFM algorithm research

The following are **candidate hypotheses**, inspired by the literature and the current repository gaps. They must not be described as novel or superior until prior-art review and controlled experiments support that conclusion.

### Candidate A — Regime-Conditioned Multi-Task Financial State Model (RC-MTFSM)

**Hypothesis**

Return and volatility may share useful market-state structure, while spread/liquidity can need more specialised representations. A shared backbone with explicit task experts and regime-aware routing may improve transfer without forcing unrelated tasks into one representation.

**Proposed design**
1. Point-in-time input contract with price/volume, cross-sectional context and (when licensed) LOB, fundamentals, events and macro features.
2. Causal temporal encoder.
3. Shared representation for related targets such as return and volatility.
4. Separate liquidity/spread expert.
5. Regime-conditioned gating over specialist heads.
6. Horizon-specific heads for direction, expected return distribution, volatility and liquidity.
7. Calibration layer fitted on chronological validation predictions only.
8. Separate downstream decision/risk layer.

**Ablations**
- Single shared encoder.
- Separate specialist encoders.
- Shared return + volatility heads.
- Shared + separate spread expert.
- Regime gate disabled/enabled.
- Fixed versus learned task weights.
- Different horizons trained jointly versus separately.

**Acceptance**
- Must beat each relevant single-task baseline on predeclared targets.
- Report task-level trade-offs; no averaging away a regression in spread or tail-risk.
- Show cross-regime and cross-instrument transfer.
- Compare equal compute and parameter budgets.

### Candidate B — Structure-Preserving Tensor Order-Book Network (SPT-LOB)

**Hypothesis**

Flattening bid/ask, depth levels, time and price/volume attributes can obscure meaningful order-book geometry. Preserve them as explicit modes and use low-rank interactions to maintain manageable compute.

**Input tensor**

`[time_window, side, price_level, attribute]`

Attributes may include price offset, quantity, event/depth change, spread and other permitted fields. The actual schema depends on the exchange feed; do not invent order IDs or queue semantics where the provider does not supply them.

**Proposed design**
1. Normalize prices relative to a stable reference (e.g. mid-price) without destroying tick-size semantics.
2. Preserve bid and ask as separate modes.
3. Preserve price levels and attributes as explicit dimensions.
4. Use mode-wise contractions or low-rank CP/Tucker blocks.
5. Add a lightweight temporal block (TCN or compact attention).
6. Add explicit OFI, microprice and depth-imbalance skip features.
7. Use class-probability and expected mid-price-change heads.
8. Include a compact distilled version for latency-sensitive inference.

**Ablations**
- Flat vector MLP/XGBoost.
- DeepLOB/TransLOB.
- Tensor-only.
- Temporal-only.
- Tensor + OFI engineered features.
- Tensor + regime conditioning.
- Different depth levels and sequence lengths.
- Model size versus latency/accuracy Pareto curve.

**Acceptance**
- Improve macro-F1 / balanced accuracy and per-class precision/recall on held-out time periods.
- No majority-class collapse.
- Calibration and class-wise error must be reported.
- Demonstrate performance across instruments and sessions, not just one FI-2010 slice.
- Run queue/fill and cost evaluation separately; mid-price classification is not a fill simulator.

### Candidate C — Reliability-Gated Expert Ensemble (RGEE)

**Motivation**

The repository's existing LR/RF ensemble regressed in macro-F1. A simple average or majority vote is therefore not an acceptable default.

**Hypothesis**

The most useful expert may depend on horizon, regime, asset and data reliability. A gated ensemble trained only on chronological out-of-fold (OOF) predictions may exploit complementary expertise without assuming equal competence everywhere.

**Proposed design**
- Independent experts: linear, tree, temporal, microstructure and multimodal.
- Generate OOF validation predictions using time-respecting folds.
- Build gate inputs only from information available at the forecast timestamp: regime estimates, data freshness, missingness, volatility bucket, instrument metadata and calibrated expert disagreement.
- Train a small regularised gate using validation OOF rows, with a separate untouched selection/test period.
- Calibrate the final probabilities on held-out calibration predictions.
- Fall back to a reliable single expert or NO TRADE when required inputs are missing or out of distribution.

**Ablations**
- Best single expert.
- Simple mean.
- Validation-loss weighted mean.
- Regime-gated ensemble.
- Data-reliability-gated ensemble.
- Gate with/without disagreement.
- Gate with/without expert freshness.

**Acceptance**
- Improve on the best single expert, not merely on a weak average.
- Report calibration, macro-F1, expected net utility and turnover.
- No OOF leakage or test-set gate fitting.
- Preserve all cases where the gate loses.

### Candidate D — Calibrated Selective Forecasting and Abstention (CSFA)

**Hypothesis**

When the model is uncertain, data are stale, experts conflict or estimated net edge does not cover costs, the system should abstain rather than force BUY/SELL.

**Proposed design**
1. Train a probabilistic forecast head (class probabilities and/or return distribution).
2. Calibrate using chronological validation predictions.
3. Estimate uncertainty and expert disagreement.
4. Apply a conformal or other statistically defensible set/interval method with time-dependence limitations explicitly tested.
5. Estimate costs and risk separately.
6. Emit a forecast and a coverage/abstention state.
7. A deterministic decision policy may produce NO TRADE when uncertainty, costs or limits dominate.

**Metrics**
- Coverage / abstention rate.
- Selective risk versus coverage curve.
- Macro-F1 and per-class precision at the selected coverage.
- Brier, log loss, ECE and interval coverage.
- Net outcome at each coverage level under frozen costs.

Do not use arbitrary confidence thresholds and call them calibrated.

### Candidate E — Distributional Heavy-Tail Forecast Head (DHT-FH)

**Hypothesis**

A point prediction or softmax class can discard information about asymmetric tails. A distributional head may better express forecast uncertainty and downside risk.

Candidate distributions/losses:
- Quantile regression with pinball loss.
- Student-t likelihood.
- Johnson SU likelihood as an experimental candidate.
- CRPS or other proper scoring rules for distribution forecasts.

Output:
- Conditional return quantiles.
- Expected return.
- Downside quantile / expected shortfall estimate.
- Volatility and uncertainty.

Compare calibration and tail coverage against Gaussian and empirical baselines. The TailDART paper's distribution head is a design reference, not proof that Johnson SU is optimal for Indian returns.

### Candidate F — Drift-Aware Safe Adaptation (DSA)

**Hypothesis**

A forecast model can lose accuracy under changing market conditions. A drift-aware system that detects changes and evaluates recent-data adaptation may outperform a static model without destabilising it.

Design:
- Monitor feature, label, prediction and residual distributions separately.
- Detect drift with minimum-sample and false-alarm controls.
- Trigger a candidate recent-window fine-tune/retrain, not automatic activation.
- Compare candidate and active models on identical future validation windows and costs.
- Require minimum improvement, calibration, stability and latency gates.
- Keep rollback to the previous validated artifact.

A drift alert is not proof that retraining will help. A candidate is not active until independent evaluation passes.

---

## 7. Experiment and benchmark protocol

### 7.1 Freeze the prediction contract first

Every run must declare:
- Universe and instrument identity version.
- Market and exchange calendar.
- Prediction timestamp and data-availability cutoff.
- Target, class thresholds and forecast horizon.
- Input feature set and schema version.
- Data source, data-rights reference and immutable dataset hash.
- Train/validation/calibration/test periods.
- Label overlap/purge/embargo requirements.
- Model code commit, config, seed and artifact hash.
- Model selection rule and experiment count.
- Transaction costs/execution assumptions for portfolio tests.

### 7.2 Chronological, point-in-time evaluation

- Never randomly shuffle time-dependent observations across train/test.
- Fit all scalers, imputers, encoders, feature selection and calibration only on eligible training/validation/calibration data.
- Apply point-in-time universe membership; avoid survivorship bias.
- Enforce availability timestamps for news, filings, fundamentals, macro and corporate-action data.
- Purge/embargo when labels or holding windows overlap.
- Use rolling-origin or expanding-window walk-forward tests.
- Add held-out instruments, sectors and regimes where the intended claim requires generalisation.
- Retain a final untouched holdout.
- Report each fold and regime, not only a pooled average.
- Use bootstrap/statistical tests that respect time dependence.
- Log every attempted model/hyperparameter/feature/threshold experiment.

### 7.3 Strong baseline discipline

For every target include:
- Majority class / constant forecast.
- Zero-return random walk / no-change baseline.
- Historical mean and simple volatility-aware baseline.
- Logistic/Ridge or linear model.
- Tree model such as XGBoost/LightGBM/CatBoost where appropriate.
- One or more suitable deep models.
- A pretrained foundation-model candidate where inputs/targets are compatible.

Never compare a tuned foundation model to an untuned trivial baseline and call it a fair leaderboard. Match training data, context length, compute and tuning budgets as far as feasible.

### 7.4 Multi-instrument generalisation

Use separate evaluations:
- Train/test on the same instruments over future time.
- Train on some instruments, test on unseen instruments.
- Train on some regimes, test on later or held-out regimes.
- NSE/BSE versus MCX only where the target definitions and data are economically comparable.
- Cross-market/global context with separate currency, timezone, session and contract semantics.

Do not pool instruments blindly if units, trading calendars, corporate-action behaviour, session structure or data quality differ.

### 7.5 Reproducibility standard

Every experiment must be rerunnable from:
- Source commit.
- Dataset manifest and checksum.
- Feature/label versions.
- Configuration.
- Model seed.
- Training and inference environment.
- Evaluation split.
- Cost assumptions.
- Output artifact hashes.

A result without a reproducible run record is exploratory, not a validated result.

---

## 8. Agent organisation: backend model research is the primary mission

The autonomous system should prioritise the following research/engineering roles. These can be worker roles rather than 15 separately hosted agent processes.

| Role | Primary responsibility | Required output |
|---|---|---|
| Model Research Director | Owns model backlog, research priorities and acceptance criteria | Ranked research programme |
| Latest Paper Scout | Monitors arXiv, conferences, journals and official code releases | Dated paper/source inventory |
| Paper Methodology Extractor | Extracts datasets, targets, metrics, training details, limitations and code | Reproduction card |
| Benchmark/Data Auditor | Checks data eligibility, point-in-time semantics, leakage and splits | Data/benchmark audit |
| Baseline Reproduction Engineer | Implements published baselines on the same data/contract | Reproducible baseline run |
| Algorithm Researcher | Designs and formalises new algorithm hypotheses from observed gaps | Algorithm spec and falsifiable hypothesis |
| Model Implementation Engineer | Implements models and training/inference code | Tested branch and model artifacts |
| Experiment Scheduler | Executes bounded sweeps and tracks resource limits | Experiment matrix and run IDs |
| Metric/Statistical Evaluator | Recomputes all metrics and performs significance/uncertainty analysis | Independent benchmark report |
| Robustness/Adversarial Reviewer | Tests regime shift, class imbalance, missing data, perturbations and leakage | Robustness verdict |
| Performance Engineer | Profiles memory, throughput and P50/P95/P99 latency | Performance report and optimisation diff |
| Model Promotion Reviewer | Compares candidate with active model and verifies gates | APPROVE / REJECT / NEEDS_MORE_DATA |

### Agent rules

- Literature scout cannot claim a paper's result without inspecting the paper table/protocol.
- Baseline engineer must reproduce the same target and split before proposing improvements.
- Algorithm researcher must state the exact gap, hypothesis, mechanism, baseline and falsifier.
- Experiment scheduler may not tune on the final test split.
- Metric evaluator must recompute metrics from predictions, never trust a report copied from another agent.
- Robustness reviewer can reject an otherwise high-scoring candidate.
- Performance engineer cannot change model numerics without equivalence/quality tests.
- Promotion reviewer cannot promote solely on Accuracy, F1, model size or paper leaderboard position.
- Every result is linked to code commit, dataset hash, experiment ID and metrics artifact.

### Research cadence

- Each working day: check new papers/repos and route only relevant items into triage.
- Before each experiment: validate data rights, target, dataset and acceptance contract.
- At run completion: independent metric recalculation and audit.
- Weekly: consolidate new evidence, rejected approaches, model comparisons and future hypotheses.
- Monthly: evaluate benchmark coverage, drift, model/provider updates and whether the research plan should change.

Do not create endless LLM calls. Use scheduled/event-triggered research workflows and deterministic numeric computation for experiments.

---

## 9. Proposed backend model architecture

The future model system should separate research artifacts from production inference.

### Research/training path

```text
Point-in-time raw data
  -> security/contract master + corporate actions
  -> quality/availability checks
  -> causal feature generation
  -> target/label generation
  -> versioned dataset + split manifest
  -> baseline and candidate training
  -> calibration and evaluation
  -> robustness/statistical audit
  -> model registry as CANDIDATE
  -> independent promotion gate
```

### Inference path

```text
Market event or scheduled snapshot
  -> validated current state
  -> incremental feature update
  -> selected lightweight model(s)
  -> calibrated probability/distribution
  -> uncertainty/reliability check
  -> forecast record
  -> separate strategy/risk decision
```

LLM agents, literature retrieval, fundamental narrative analysis and large-model research must not run synchronously in the tick-critical inference path. They can create validated context/features asynchronously. The hot path uses approved, versioned and bounded artifacts.

### Model interface

A versioned prediction artifact should contain:
- Instrument and target contract.
- Forecast issue timestamp.
- Horizons.
- Class probabilities if classification is used.
- Return quantiles/distribution where available.
- Volatility/liquidity/regime outputs where trained.
- Calibration version.
- Uncertainty/abstention state.
- Feature/schema version.
- Model artifact and training dataset lineage.
- Inference latency metadata.
- Model status and valid-from/retirement metadata.

The forecast interface must not contain broker order commands.

---

## 10. Priority implementation and experiment roadmap

This roadmap preserves the existing D0 → D1 → D2 → D3 → D4 dependency order.

### Priority 0 — Re-establish and strengthen baseline

1. Verify the current repository state and run the documented test suite before code changes.
2. Re-run the existing daily baseline from an immutable dataset manifest.
3. Add an explicit random-walk/zero-return baseline.
4. Recompute confusion matrices, macro/weighted/per-class F1, balanced accuracy, MCC, PR-AUC, ROC-AUC, Brier, log loss and calibration.
5. Re-run walk-forward and cost scenarios.
6. Freeze a new untouched evaluation period; do not recycle the old test set.
7. Resolve the actual multi-instrument historical-data rights and source coverage.

### Priority 1 — Multi-model research benchmark

Run controlled experiments for:
- Linear/logistic and regularised models.
- Random Forest / XGBoost / LightGBM / CatBoost.
- GARCH/HAR-style volatility baselines.
- LSTM/GRU/TCN.
- N-BEATS/N-HiTS.
- PatchTST/iTransformer.
- TimesFM / Chronos / Moirai or other compatible TSFMs.
- Regime-specific and multi-task models.

All candidates use the same data, target and temporal split.

### Priority 2 — Candidate MPFM algorithms

Implement candidates in this order once their data requirements are met:
1. RC-MTFSM: shared return/volatility representation plus specialised liquidity expert.
2. RGEE: chronological OOF reliability/regime-gated ensemble.
3. CSFA: calibrated selective forecasting and abstention.
4. DHT-FH: calibrated heavy-tail distributional head.
5. DSA: drift-aware candidate adaptation.

### Priority 3 — Intraday / LOB research, blocked on licensed depth/event data

1. Validate live/historical event schema, timestamps, sequence gaps and reconstruction.
2. Build simple OFI, depth imbalance, microprice and spread baselines.
3. Reproduce DeepLOB/TransLOB and compare LiT/TensorLOB designs.
4. Test structure-preserving tensor model with the actual India feed depth available.
5. Evaluate time-based and event-based horizons separately.
6. Evaluate fill/queue/execution assumptions in a specialist replay tool; report its no-market-impact limitation.

### Priority 4 — Original financial world-model experiments

Only after the point-in-time base is reliable:
- Shared financial-state representation.
- Self-supervised temporal objectives.
- Task/representation transfer across instruments.
- Multi-task specialist heads.
- Regime-aware augmentation.
- Reliability-gated multimodal fusion.
- Mandate/ontology conditioning as downstream context.
- Held-out instrument/regime compositional generalisation.

### Priority 5 — Inference optimisation

Optimise only after establishing an accurate model:
- Profile model decode, feature calculation, serialization and queueing separately.
- Compare CPU, GPU and compact/quantised inference.
- Consider C++/Rust/ONNX only where parity and latency gains are measured.
- Track the Pareto frontier: accuracy/calibration/net performance versus latency/throughput/memory.
- Do not move an LLM or expensive foundation model into the per-tick path.

---

## 11. Model acceptance and promotion gates

A model can remain a research candidate even when a subset of metrics improves.

### Required gates

1. **Data gate:** rights/entitlement, provenance, point-in-time availability and data-quality tests pass.
2. **Leakage gate:** chronological splits, no future leakage, correct purge/embargo and train-only transforms.
3. **Baseline gate:** beats relevant naive and strong model baselines on a predeclared metric.
4. **Classification/regression gate:** per-class, macro and decision-relevant metrics are acceptable for the specific task.
5. **Calibration gate:** probabilities/distributions are not materially miscalibrated.
6. **Statistical gate:** improvement is stable with uncertainty analysis and multiple-testing control.
7. **Robustness gate:** not dependent on one instrument, month, class, seed or regime.
8. **Economic gate:** any strategy claim survives frozen costs and realistic execution assumptions.
9. **Runtime gate:** meets target latency, throughput, memory and failure behaviour.
10. **Governance gate:** code/data/model lineage is reproducible; independent reviewer approves.

The threshold for each gate must be set before the experiment based on the intended use case. Do not invent universal accuracy/F1 targets.

### Model status vocabulary

- EXPERIMENTAL: exploratory, not fully reproduced.
- REPRODUCED: baseline/paper setup reproduced under stated conditions.
- CANDIDATE: passes initial technical and validation gates.
- APPROVED: passes the predefined promotion protocol for a specific scope.
- ACTIVE: deployed for the specific approved scope.
- DEGRADED: monitoring indicates performance/quality deterioration.
- REJECTED / ARCHIVED: retained for lineage; not eligible for active use.

A model's scope includes its universe, target, horizon, data source, market regime/conditions and model version. Approval on one task does not imply approval on another.

---

## 12. Immediate next experiments

| ID | Experiment | Why first | Deliverable |
|---|---|---|---|
| MBR-00 | Re-run current baseline and integrity checks | Establish the true current code/data state | New verified run manifest |
| MBR-01 | Random-walk + linear + tree model benchmark | Expose whether the current model beats simple alternatives | Unified benchmark table |
| MBR-02 | Reproduce multi-model TSFM comparison where licences and compute permit | Test foundation-model value rather than assume it | Equalised-context report |
| MBR-03 | Add full classification and calibration metrics | Macro-F1/precision alone are insufficient | Metrics artifact + reliability report |
| MBR-04 | Cross-instrument/regime walk-forward experiment | Test generalisation beyond a single ticker | Per-instrument/fold results |
| MBR-05 | RC-MTFSM ablation | Test shared return/volatility plus specialist liquidity hypothesis | Architecture/ablation report |
| MBR-06 | RGEE vs best single expert/simple average | Avoid repeat of prior ensemble regression | OOF gated-ensemble report |
| MBR-07 | CSFA selective prediction | Measure whether abstention improves risk/coverage | Coverage-risk curve |
| MBR-08 | SPT-LOB reproduction | Explore TensorLOB/LiT with appropriate depth data | LOB benchmark and latency report |
| MBR-09 | DHT-FH distributional forecast | Test tail uncertainty/calibration | CRPS, pinball, coverage report |

### First execution rule

Do not start MBR-05 through MBR-09 before MBR-00 and MBR-01 establish reliable baselines and accepted data contracts. Do not start order-book experiments without lawful depth/event data. Do not claim MPFM foundation-model advantage before the pretraining/ablation protocol is controlled.

---

## 13. External paper and project inventory

### Primary papers checked in this review

1. FinVerse (2026): https://arxiv.org/abs/2608.03259
2. Pretrained Time-Series Foundation Models for Financial Return Forecasting (2026): https://arxiv.org/abs/2606.27100
3. Towards Financial World Modeling / TFWM (2026): https://arxiv.org/abs/2610.09048
4. TensorLOB (2026): https://arxiv.org/abs/2611.02866
5. TailDART (2026): https://arxiv.org/abs/2611.09176
6. LiT (2025): https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1616485/full
7. Evaluation Integrity in Machine Learning for Finance (2026 working paper): https://papers.ssrn.com/sol3/Delivery.cfm/7007079.pdf?abstractid=7007079&mirid=1
8. FinCast (ACM CIKM 2025): https://doi.org/10.1145/3746252.3761261
9. Deep Order Flow Imbalance: https://onlinelibrary.wiley.com/doi/full/10.1111/mafi.12413
10. Backtest overfitting comparison (2024): https://doi.org/10.1016/j.knosys.2024.112477

### Useful benchmark/data/model projects to evaluate

- FI-2010 LOB benchmark: https://etsin.fairdata.fi/dataset/9d3ce9cf-0f4c-4d3a-8e23-f4f7f43d5b52
- Market-1T / TFWM: https://github.com/fin-ai-lab/market-1t
- Qlib: https://github.com/microsoft/qlib
- TimesFM: https://github.com/google-research/timesfm
- Chronos: https://github.com/amazon-science/chronos-forecasting
- Moirai: https://github.com/SalesforceAIResearch/uni2ts
- HftBacktest: https://github.com/nkaz001/hftbacktest
- NautilusTrader: https://github.com/nautechsystems/nautilus_trader

Model weights, datasets, market data and source code have separate licence/usage conditions. Verify each before use.

---

## 14. Final strategic direction

MPFM should not chase a single benchmark score or copy the largest published model. It should build a rigorous model research system that can discover which algorithm works for which target, horizon, market and regime, and reliably reject false improvements.

**Near-term priority:** make the current baseline difficult to fool.  
**Mid-term priority:** test strong alternatives and original regime/task-aware algorithms.  
**Long-term priority:** establish whether MPFM's financial-state representation produces incremental, statistically reliable and economically meaningful generalisation.

Top-notch means reproducible evidence, robust performance, calibrated uncertainty, low inference cost and safe operation—not an impressive headline Accuracy number.
