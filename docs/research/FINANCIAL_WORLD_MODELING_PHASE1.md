
# MPFM Phase 1 — Financial World Modeling, Representation Learning and Architecture

**Research consolidation:** 2026-11-17  
**Source material:** User-supplied MPFM Phase 1 research notes (sections 61–66)  
**External primary references checked:** *Towards Financial World Modeling* (arXiv:2610.09048; TFWM / Market-1T repositories), and the September 2026 multimodal-finance survey (DOI: 10.1016/j.inffus.2026.104249).  
**Status:** Research synthesis and proposed experiments; none of the new MPFM experiments below is claimed to have run.

---

## 1. Executive conclusion

The Phase 1 notes suggest an important evolution of the MPFM thesis:

**Do not stop at a financial foundation encoder. Research a layered system that represents the current financial state, predicts how that state evolves, and evaluates decisions against the resulting uncertainty.**

However, three different capabilities must remain separate:

1. **Financial foundation representation:** learns reusable representations from broad financial observations.
2. **Financial dynamics / world model:** learns a conditional distribution over future financial states and, for a genuine action-conditioned model, how actions can change those states.
3. **Decision and execution model:** evaluates a candidate portfolio/order against forecasts, risk constraints, liquidity and execution outcomes.

A model that maps today's market observations to a latent vector is only a state encoder. A model that predicts the future state without conditioning on actions is a market-dynamics predictor. A more complete financial world model must support action-conditioned rollouts or counterfactuals, with credible evaluation of those counterfactuals.

The TFWM paper itself is careful on this point: its contribution is a systematic representation-learning benchmark and a candidate financial state-representation layer for broader world models; the paper does not claim to have solved the complete financial world-model problem. [Paper](https://arxiv.org/abs/2610.09048).

## 2. Proposed three-part MPFM architecture

~~~mermaid
flowchart TD
    X["Historical Financial Observations"] --> E["MPFM State Encoder"]
    E --> Z["Current Financial State Representation"]
    Z --> D["Market Dynamics Model"]
    A["Hypothetical Strategy / Order Action"] --> D
    C["Market Context"] --> D
    D --> P["Future State Distribution"]
    P --> F["Forecast Heads"]
    P --> S["Scenario and Counterfactual Engine"]
    F --> R["Independent Risk and Portfolio Evaluation"]
    S --> R
    R --> O["Validated Decision Proposal"]
    Z --> M["Modality / State Diagnostics"]
~~~

The diagram is a proposed MPFM design. The risk/portfolio layer should be separately evaluated and should not alter the scoring of the underlying market forecast.

### 2.1 State encoder

Define the causal observation history as:

\[
z_t = f_\theta(x_{\leq t})
\]

where:

- \(x_{\leq t}\) is the set of observations demonstrably available to the system at or before prediction time \(t\);
- \(z_t\) is the learned financial-state representation;
- \(f_\theta\) is the state encoder.

For multimodal records, event time alone is not enough. Use the existing point-in-time contract: event time, publication time, ingestion time and availability time. The model may only consume information available by \(t\).

### 2.2 Dynamics model

A general candidate formulation is:

\[
p_\phi(z_{t+H}, y_{t+H}\mid z_t, a_t, c_t)
\]

where \(H\) is the forecast horizon, \(a_t\) is a hypothetical action and \(c_t\) is market context. The output should be a distribution or calibrated set of possible futures, not a guaranteed future price.

The architecture must not force the same action assumption on a small price-taking investor and a market-making/HFT strategy. See Section 3.

### 2.3 Forecast heads and decision layer

Forecast heads should retain separate targets and evaluation contracts:

- Future return / return distribution.
- Direction or cross-sectional ranking.
- Future realized volatility and volatility change.
- Spread / liquidity change.
- Market regime and cross-asset context.
- Where the data supports it, execution and fill outcomes.

A risk/portfolio evaluator can use those distributions to assess exposure, expected utility, drawdown, concentration, liquidity, turnover and mandate constraints. A decision output is not itself proof that the market forecast is accurate.

## 3. Critical distinction: price-taker dynamics vs market-impact dynamics

The Phase 1 notes correctly identify that personal trade size and market-making/HFT activity should not be represented by the same action-conditioned market model.

### 3.1 Price-taker regime

Assumption: our own orders are too small to materially change the market state.

Use two separate models:

**Market evolution**
\[
p(z_{t+H}\mid z_t,c_t)
\]

This forecasts the market environment independently of our own small order.

**Execution**
\[
p(\text{fills},\text{slippage},\text{costs}\mid z_{t:t+H},\text{order},\text{venue})
\]

The execution model evaluates how our own order interacts with the forecast market path. Position sizing and portfolio state change because of our action, but the market transition is treated as exogenous to the small order.

This is the right initial assumption for a small personal trade in a sufficiently liquid instrument, subject to validation of size, instrument and market conditions.

### 3.2 Market-impact regime

Assumption: our orders may affect available liquidity, queue position, short-term price formation, other participants' responses or fill probability.

A candidate transition is:

\[
p(z_{t+H}\mid z_t,a_t,c_t,\mathcal{M}_t)
\]

where \(\mathcal{M}_t\) contains relevant market microstructure state and possibly the interaction of other agents. This needs more than OHLCV: depending on the task it may require timestamped order-book depth, order events, trades, cancellations, queue/venue information and the strategy's own action/execution records.

A top-of-book NBBO snapshot is not full L2/L3 order-book history. A model trained only on consolidated best bid/ask and trades cannot claim to reconstruct queue priority, participant identity or full depth.

### 3.3 Why this split matters for HFT

For HFT, the action can change the data-generating process. There is also a counterfactual identification problem: observational market data records what happened under the historical order flow, not necessarily what would have happened under a different hypothetical action.

Therefore, an action-conditioned impact model must state its identification assumptions and be validated using an appropriate mix of:
- historical message/order data with the strategy's own actions logged;
- replay or agent-based simulation with known limitations;
- controlled paper/small-size experiments where permitted;
- out-of-sample execution outcomes.

A scenario engine that simply changes a forecast after inserting a hypothetical action is not yet a validated counterfactual model.

**Research decision:** begin with the price-taker market-state dynamics and separate execution model. Develop a distinct market-impact branch only after licensed depth/event data and an appropriate validation environment are available.

## 4. What the TFWM paper actually establishes

Primary source: Humzah Merchant, Alec Guthrie, Simon Mahns, Randall Balestriero and Bradford Levy, *Towards Financial World Modeling*, arXiv:2610.09048 (posted 6 October 2026; listed as NeurIPS 2026 in the project repositories).

- [Paper on arXiv](https://arxiv.org/abs/2610.09048)
- [TFWM code and released results](https://github.com/fin-ai-lab/tfwm)
- [Market-1T data-construction code](https://github.com/fin-ai-lab/market-1t)
- [Paper result tables and figures](https://fin-ai-lab.github.io/tfwm_market1t/)

### 4.1 Benchmark scope

The paper compares 18 encoder-training strategies under a common architecture and evaluation protocol. It studies representations for three 15-minute-ahead cross-sectional tasks:
- future return;
- change in realized volatility;
- change in quoted bid–ask spread, used as a proxy for trading costs.

The primary metric in the table below is **Rank Information Coefficient (Rank IC)** averaged over 32 evaluation months. It measures cross-sectional ranking information in the forecast; it is not directional accuracy, price-level RMSE or realized strategy return.

### 4.2 Selected supervised and representation results

| Training approach | Return Rank IC | Volatility Rank IC | Spread Rank IC |
|---|---:|---:|---:|
| Supervised return specialist | 0.0272 | 0.0695 | 0.1305 |
| Supervised volatility specialist | 0.0197 | 0.0883 | 0.1480 |
| Supervised spread specialist | 0.0178 | 0.0762 | 0.2517 |
| Supervised multihead | **0.0311** | **0.0941** | 0.2455 |
| LeJEPA time-warping | 0.0204 | 0.0721 | 0.1691 |
| TS2Vec | 0.0205 | 0.0719 | 0.1500 |
| CPC | 0.0184 | 0.0697 | 0.1519 |
| Random, untrained ViT floor | 0.0170 | 0.0694 | 0.1692 |

Source: TFWM paper, Table 2, 15-minute Rank IC averaged over 32 evaluation months. [Primary source](https://arxiv.org/abs/2610.09048).

### 4.3 Interpretation for MPFM

**Finding A — shared multi-task learning is promising for related prediction targets.** The supervised multihead representation improved the return and volatility Rank IC values relative to the respective standalone specialist rows in this table.

**Finding B — parameter sharing can create task spillover.** Spread Rank IC was 0.2455 for multihead versus 0.2517 for the standalone spread specialist. The authors discuss this as evidence that spread prediction may require more specialized information.

**Finding C — self-supervision is not automatically better.** In this benchmark, several self-supervised methods are close to or below the untrained Random ViT floor on individual targets. The result argues for strong random/untrained and supervised controls, not for abandoning self-supervision universally.

**Finding D — market period dominates random-seed variation in this evaluation.** The paper reports month contributions of 97.2%, 98.9% and 99.9% of the observed variation for return, volatility and spread tasks respectively. This is the paper's variance decomposition, not a universal law for every market or dataset. It strongly motivates evaluation across many different months/regimes rather than repeated seeds on one narrow period.

**Finding E — bigger is not automatically better.** At the compute scales studied, the paper reports the smaller ViT-Tiny beating ViT-Base trained with up to 10× the FLOPs on the three prediction tasks. MPFM should establish a useful-data/compute baseline before scaling parameters.

**Finding F — representation age may differ by task.** The paper's relative temporal-decay analysis finds return representations comparatively persistent, while volatility and spread representations degrade more with training/evaluation time separation. The reported degradation over five years is approximately 20% of base IC for volatility and 10% for spread in the described comparison. Recheck this by task and market; do not assume a single retraining cadence is optimal for all heads.

### 4.4 What these results do not prove

They do not prove:
- UP/DOWN accuracy for Indian stocks;
- profitability after brokerage, taxes, impact and slippage;
- full L2/L3 microstructure understanding;
- action-conditioned market-impact modelling;
- a complete financial world model;
- that MPFM will outperform the repository's current LR/RF/LSTM baselines.

The authors explicitly position this as a first step toward broader financial world modeling: a benchmark and state-representation layer on which temporal and eventually action-conditioned dynamics could be developed.

## 5. Market-1T: data representation and transfer limits

### 5.1 What is in the dataset

Market-1T is described as nearly one trillion one-second aggregates across U.S.-traded equities from 2008–2025. It is built from consolidated U.S. Securities Information Processor quote and trade data, including CTA/UTP feeds, with NBBO quote state and consolidated trade reports aggregated into synchronous one-second observations.

The 11 feature fields are:

| Category | Fields |
|---|---|
| Best bid state | Best bid price, best bid size |
| Best ask state | Best ask price, best ask size |
| Price summary | Open, high, low, close |
| Price summary | VWAP |
| Activity | Traded volume, trade count |

The construction uses the last valid quote state by the end of the interval and eligible trades within the interval. It is a consolidated best-bid/best-ask representation, **not** a full depth-of-book or participant-identity dataset.

### 5.2 Important access and reproducibility qualification

The TFWM repository README states that a sample of Market-1T on Hugging Face covers July 2019–December 2020 (230,025 ticker-days), provides code to assemble the full dataset, and says full open hosting was being worked on with Massive when that README was reviewed. The Market-1T pipeline also documents access to Massive flat files and corresponding S3 credentials/plan requirements.

Therefore, do not assume that all one trillion observations or all pre-trained weights are freely downloadable merely because the paper describes the dataset as public/permissively licensed. The code repository's MIT license is not the data or weights license. Verify the exact dataset card, model card, hosting status and permitted-use terms before budgeting for a reproduction.

- [TFWM README and data note](https://github.com/fin-ai-lab/tfwm/blob/main/README.md)
- [Market-1T pipeline](https://github.com/fin-ai-lab/market-1t)

### 5.3 Transfer to India

Market-1T is a U.S.-equity research benchmark. Its consolidated NBBO and SIP reporting conventions do not make it an Indian exchange dataset. NSE/BSE market sessions, tick sizes, price bands, market lots, auction/session rules, derivatives structure, feed formats and corporate-action conventions need their own schema and validation.

A TFWM-style Indian pilot is reasonable, but it must be designed as a local data engineering and transfer experiment—not a claim that an American model will automatically transfer.

### 5.4 Proposed Indian market-state schema

The user's proposed NSE-oriented schema is a useful first specification:

| Group | Fields |
|---|---|
| Instrument identity | Instrument ID, exchange, segment, symbol/contract, expiry/strike where relevant |
| Session / time | Trading session, exchange event timestamp, provider timestamp, receive timestamp |
| Price | Open, high, low, close, VWAP |
| Activity | Traded volume, trade count, turnover |
| Top-of-book liquidity | Best bid, best ask, bid size, ask size, spread |
| Context | Relative volume, realized volatility, market regime, sector context |
| Governance | Data quality, source provenance, entitlement/rights, missingness and freshness |

For deeper intraday/HFT experiments, maintain a separate event/depth schema for licensed order-book levels, order updates, cancellations, trades, venue/sequence IDs and market-by-order fields where the provider actually supplies them. Do not flatten unavailable depth into fabricated zeros.

## 6. Task-selective shared learning

### 6.1 Research proposal

Use one shared market-state backbone, but do not force every target and modality to use an identical representation.

| Component | Initial architecture hypothesis | Why |
|---|---|---|
| Market-state encoder | Shared | Reuse broad causal market structure |
| Return representation | Shared family of heads | Related to volatility and cross-sectional market state |
| Volatility representation | Partially shared with return | TFWM multihead result supports testing this |
| Liquidity / spread | Specialist branch or adapter | TFWM reports negative task spillover vs specialist |
| Fundamentals | Separate point-in-time encoder | Different temporal cadence, entity semantics and release process |
| Macro | Separate encoder | Low-frequency release/calendar and cross-asset context |
| Philosophy / mandate | Adapters or downstream conditioning | Avoid changing the definition of the base market forecast |
| Risk constraints | External deterministic engine | Keep hard constraints auditable and independent |

This is not a final allocation of layers. Compare shared, partially shared and specialist capacity empirically.

### 6.2 Experiments

- **SHARE-0:** independent specialists, one per task.
- **SHARE-1:** one fully shared backbone with all supervised heads.
- **SHARE-2:** shared return/volatility trunk plus specialist spread/liquidity head.
- **SHARE-3:** shared market encoder with independent fundamental and macro encoders.
- **SHARE-4:** task-specific adapters over a shared encoder.
- **SHARE-5:** dynamic task routing / gating, only if sample size supports it.

Measure each head against its specialist baseline and the random/untrained representation floor. Check negative transfer, not just aggregate loss.

## 7. Financially valid augmentation engine

Financial time-series augmentation must preserve the economic information required by the target. A generic vision-style transformation can change the meaning of a price path, a market session, a corporate event or a liquidity state.

The TFWM study tested five LeJEPA view pairings: same-stock/different-view, time warping, Gaussian noising, cross-stock and cross-stock-within-industry. It reports that these choices lead to materially different latent organization. In particular, same-stock/different-view can encourage firm-identity structure through bid/ask-size patterns, while cross-stock and same-industry pairings can emphasize broader market movement. [Paper](https://arxiv.org/abs/2610.09048).

### 7.1 Proposed augmentation registry

| Augmentation | Candidate transformation | Required semantic checks |
|---|---|---|
| Price-scale transform | Apply a common scale to all compatible price fields | Preserve OHLC ordering, bid/ask ordering, returns and relative spread; account for tick-size and price-band effects |
| Volume/activity scale | Transform volume/size/count in a controlled experiment | Must not silently preserve false liquidity or impact semantics; size, volume and trade count are not interchangeable |
| Temporal crop | Select a causal contiguous sub-window | Preserve event order, target horizon, session boundaries and corporate-event timing |
| Calendar-aware masking | Mask selected observed timestamps | Preserve exchange session semantics; distinguish missing feed from no trading |
| Multi-resolution view | Re-aggregate ticks to coarser intervals | Use consistent OHLC, last-valid quote, VWAP, volume and count rules |
| Same-instrument multi-view | Construct two valid views of same instrument/time region | Measure whether representation learns firm identity instead of market state |
| Cross-instrument contrastive view | Pair instruments based on a defined factor/sector relation | Avoid treating same-industry firms as identical; preserve idiosyncratic risk |
| Time warping | Controlled resampling of elapsed market time | Do not distort overnight gaps, event timing, session clocks or target labels |
| Noise injection | Noise within measured feed/measurement error bounds | Do not erase tick structure, create crossed books or synthetic impossible prices |

Do not enable every augmentation by default. Each transformation must have a registered semantic contract, valid data-type scope, target compatibility and unit tests.

### 7.2 Regime-Preserving Contrastive Learning hypothesis

**Hypothesis:** representations may transfer better if the objective learns both (a) invariants that persist across market environments and (b) state variables whose meaning is regime-conditional.

A candidate objective can combine:
- supervised forecasting losses for pre-registered future targets;
- latent predictive/dynamics loss;
- contrastive consistency for carefully selected valid views;
- auxiliary probes for instrument identity, regime and market/sector factors to detect what information is retained or discarded.

The system should not automatically label two same-sector stocks as positive pairs. Sector membership is a weak relation; oil sensitivity, interest-rate exposure, balance-sheet structure and company-specific events may differ substantially.

### 7.3 Augmentation ablation

Compare:
1. No augmentation.
2. Standard time-series augmentation.
3. TFWM-style time-warping.
4. Same-instrument multi-view pairing.
5. Cross-instrument pairing.
6. Same-industry pairing.
7. Financially constrained augmentation registry.
8. Regime-aware contrastive objective.

Evaluate downstream Rank IC/forecast quality, regime/instrument probes, latent collapse, calibration, and cross-instrument transfer.

## 8. Multimodal fusion research

The September 2026 survey *Learning across modalities: a systematic survey of multimodal models for financial analysis* reviews 35 representative works (2018–2025) and identifies temporal misalignment, modality imbalance, missing/noisy inputs and limited cross-market generalization as persistent issues. It highlights adaptive fusion, incomplete-modality learning and temporal graph neural networks as relevant directions. [DOI: 10.1016/j.inffus.2026.104249](https://doi.org/10.1016/j.inffus.2026.104249).

### 8.1 Fusion strategies to compare

| Strategy | Architecture | Principal benefit | Principal risk |
|---|---|---|---|
| Early fusion | Concatenate aligned inputs before/near encoder input | Early cross-modal interaction | Bad or missing input can contaminate shared representation |
| Intermediate fusion | Separate encoders followed by cross-attention/gating/message passing | Context-aware interaction while preserving modality-specific processing | Alignment and training complexity |
| Late fusion | Separate modality predictions combined downstream | Fault isolation and modularity | May miss detailed cross-modal interactions |
| Hybrid reliability-gated fusion | Separate encoders, intermediate fusion when reliable, late fallback when missing/unreliable | Robustness and observability | More components and gate calibration required |

### 8.2 Recommended MPFM candidate

Use separate encoders for:
- market time series / microstructure;
- fundamentals and corporate events;
- news/text;
- macroeconomic state;
- cross-asset / sector relationships.

Use an intermediate fusion layer only when point-in-time availability and reliability tests pass. Retain independent modality outputs for audit, and preserve late-fusion fallback when a modality is missing, delayed, stale or low quality.

This fits the current repository's point-in-time multimodal contract: availability-time joins, reliability classes and missing modality as NaN rather than fabricated values. The new research idea is to add a learned reliability gate and compare it to simple late fusion; it is not yet implemented or validated.

### 8.3 Proposed F0–F7 experiment matrix

| ID | Input / architecture | Status |
|---|---|---|
| F0 | Price and volume only | Baseline to establish |
| F1 | Price, volume and licensed point-in-time fundamentals | Blocked on approved historical source |
| F2 | Price, volume and licensed as-of news/events | Blocked on approved historical source |
| F3 | Price, volume and macro releases with publication/availability timestamps | Requires licensed/approved source and point-in-time vintage handling |
| F4 | All available modalities with simple concatenation | Proposed |
| F5 | Separate encoders plus cross-attention | Proposed |
| F6 | Cross-attention with reliability gating and missing-modality fallback | Proposed |
| F7 | F6 plus philosophy/mandate conditioning | Proposed after unconditioned baseline |

Run target- and horizon-specific ablations. A news feature can be useful around events without improving a long-horizon valuation task. More modalities do not automatically mean more information.

## 9. Philosophy and mandate-conditioned representation learning

The Phase 1 notes propose moving away from seven agent-like philosophical personalities that vote on a trade. That is the right research distinction: a language-agent vote is not automatically a financial foundation model.

### 9.1 Mandate as a structured condition

Represent a mandate using explicit parameters rather than only a label:

- objective (value, growth, macro, quantitative, momentum, expectations or capital preservation);
- forecast/holding horizon;
- permitted instruments and investment universe;
- benchmark and tracking constraints;
- drawdown/risk budget and exposure limits;
- liquidity/market-impact constraints;
- turnover and transaction-cost budget;
- evidence/valuation preferences;
- abstention and eligibility conditions.

The names of mandates are shorthand for structured objectives, not claims about any real investor's exact proprietary strategy.

### 9.2 Recommended boundary

The base market forecast remains philosophy-independent. Test mandate conditioning as:
- a representation adapter;
- a task-specific downstream head;
- or a decision-layer preference.

Do not feed mandate preferences into the base forecast in a way that makes forecast truth depend on the strategy being evaluated.

### 9.3 Mandate experiment

Use the same instrument snapshots and same time boundaries:

- M0: shared market encoder, no mandate.
- M1: shared encoder plus value mandate.
- M2: shared encoder plus growth mandate.
- M3: shared encoder plus momentum mandate.
- M4: shared encoder plus macro mandate.
- M5: shared encoder plus capital-preservation mandate.
- M6: independently trained specialist models.

Measure the task-specific objective, cross-task interference, stability, instrument transfer and performance on unseen instruments. Add held-out combinations of instruments × regimes × mandates to test compositional generalization. Do not reward a model for merely producing different-looking outputs for different mandate labels.

## 10. Proposed MPFM Phase 1 experiment programme

All items below are proposed, not completed experiments.

| Workstream | Core question | First controlled experiment | Gate |
|---|---|---|---|
| WM-01 State representation | What financial information does the encoder preserve? | LR/RF/tabular, random encoder, supervised encoder, SSL encoder under common data | Out-of-sample representation utility and latent diagnostics |
| WM-02 Task-selective sharing | Which tasks benefit from shared parameters? | Specialist vs full multihead vs partial sharing | No material negative transfer on specialist tasks |
| WM-03 Augmentation | Which transformations preserve financial semantics? | No augmentation vs TFWM views vs constrained registry | Invariant checks, target compatibility and regime-held-out tests |
| WM-04 Market dynamics | Can latent transitions forecast a distribution of future states? | One-step and multi-horizon state prediction with probabilistic losses | Calibration, temporal generalization and baseline improvement |
| WM-05 Price-taker execution | Can execution outcomes be modelled separately from market evolution? | Order-size × spread × volatility × liquidity-conditioned fill/cost model | Realistic costs and timestamp correctness |
| WM-06 Market impact | Can actions alter transition predictions usefully? | Impact model using depth/order-event data, with replay/simulation comparison | Licensed data, action logs and credible counterfactual validation |
| WM-07 Multimodal fusion | Do extra modalities add incremental information? | F0–F7 ablation with availability-time gating | Improvement on untouched periods and missing-modality robustness |
| WM-08 Mandate conditioning | Does mandate conditioning help appropriate downstream tasks? | M0–M6 controlled comparison | Task gains without cross-task harm or leakage |
| WM-09 Compositional transfer | Does MPFM generalize to unseen combinations? | Hold out instruments × regimes × mandates | Robust held-out performance vs specialist baselines |

### 10.1 Metrics

Do not evaluate every layer with one metric.

**Representation / ranking:** Rank IC, cross-sectional rank stability, sample-size sensitivity and latent probes.

**Return / direction:** target-specific MAE/RMSE, balanced accuracy/macro-F1, log loss and proper scoring rules; define labels and thresholds before test.

**Distribution forecasts:** quantile loss, interval coverage, calibration and proper scoring rules.

**Volatility:** realized-volatility forecast loss and comparison with historical-volatility baselines.

**Liquidity / execution:** spread-change prediction, fill probability, implementation shortfall, slippage, queue/fill metrics where data permits.

**Decision utility:** net returns, benchmark-relative performance, risk, drawdown, turnover, cost and exposure under frozen constraints.

Rank IC is a useful prediction diagnostic independent of portfolio construction, but it is not the final measure of financial utility.

### 10.2 Regime-aware protocol

TFWM's month variance result suggests that a single short validation window is especially dangerous. For MPFM:

- Preserve chronological walk-forward evaluation.
- Sample or report multiple disjoint evaluation months across distinct regimes.
- Add instrument-held-out and sector-held-out tests.
- Report per-period and pooled results; do not hide regime-specific failures in an average.
- Separate representation age from evaluation-regime difficulty when measuring decay.
- Keep at least one final untouched period.
- Select hyperparameters and gates only on training/validation periods.
- Record uncertainty intervals and number of months/instruments contributing to every metric.

## 11. Recommended implementation order for our project

This work must respect the already agreed dependency order D0 → D1 → D2 → D3 → D4. The mapping below is a research sequencing overlay, **not** a redefinition of the original D0–D4 task cards.

1. **Before model complexity:** reliable security master, corporate actions, exchange calendar, point-in-time historical market state, data-quality and source-rights controls.
2. **Prediction baseline:** multi-instrument baseline on the approved target/horizon contract.
3. **State representation:** compare supervised multihead, specialists, SSL, untrained encoder and TFWM-inspired view generation.
4. **Market dynamics:** add future-state distribution modelling; first under price-taker assumption.
5. **Execution:** evaluate orders separately against predicted market paths.
6. **Specialist extensions:** liquidity/spread, fundamentals and macro branches as data quality and permissions allow.
7. **Mandate/philosophy conditioning:** compare after an independent base forecast is established.
8. **Market-impact/HFT:** only after depth/order-event data and suitable validation are available.
9. **Integrated MPFM:** run the held-out instrument/regime/mandate programme before claiming world-model capability.

Philosophy ontology and licensing can continue in parallel. Real-market multimodal learning must wait for approved, point-in-time data.

## 12. Risks and unresolved questions

- **Counterfactual validity:** how will the model validate futures under actions that were not taken in the historical data?
- **Non-stationarity:** market-state representations and individual task heads may decay at different rates.
- **Data representativeness:** U.S. SIP/NBBO market structure does not equal NSE/BSE market structure.
- **Data entitlement:** training, storage, derivatives and display rights must be checked separately.
- **Augmentation validity:** invariance can remove price, liquidity or event information that the task actually needs.
- **Negative transfer:** multihead sharing can help return/volatility and harm spread/liquidity.
- **Mandate leakage:** a mandate-conditioned model can learn the mandate label rather than generalizable financial structure.
- **Compute efficiency:** larger encoders may not improve the relevant prediction objective.
- **Evaluation overfitting:** trying many architectures and augmentations on the same months can create false discoveries.

## 13. Decisions proposed for Phase 1

1. Adopt the encoder → dynamics → decision decomposition as the research architecture.
2. Keep the base forecast independent of philosophy/mandate labels.
3. Build separate price-taker market evolution and execution models first.
4. Treat market-impact dynamics as a separate HFT research branch.
5. Test shared return/volatility learning with a specialist spread/liquidity branch.
6. Build a financially constrained augmentation registry; never assume a generic transform is valid.
7. Test hybrid reliability-gated fusion only with point-in-time licensed modalities.
8. Require regime-, instrument- and mandate-held-out evaluation before claiming transfer or compositional generalization.

These are proposed research decisions for review; they do not claim implementation or experimental success.

## 14. References

1. Merchant et al., [Towards Financial World Modeling](https://arxiv.org/abs/2610.09048), 2026.
2. [TFWM research code, result tables, README and data notice](https://github.com/fin-ai-lab/tfwm).
3. [Market-1T construction pipeline](https://github.com/fin-ai-lab/market-1t).
4. D'Amico et al., [Learning across modalities: a systematic survey of multimodal models for financial analysis](https://doi.org/10.1016/j.inffus.2026.104249), *Information Fusion*, Volume 133, September 2026, article 104249.
5. Existing Finance AI point-in-time implementation: [MULTIMODAL_FINANCE_DATA_IMPLEMENTATION.md](../MULTIMODAL_FINANCE_DATA_IMPLEMENTATION.md).
6. Existing prediction baseline/evaluation: [PREDICTION_MODEL_RESEARCH.md](PREDICTION_MODEL_RESEARCH.md).
