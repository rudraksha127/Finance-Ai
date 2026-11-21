# MPFM Research Master

**Last research consolidation:** 2026-11-21  
**Research priority:** market prediction first  
**Parent product:** Finance AI  
**Research/model architecture:** Multi-Philosophy Financial Model (MPFM)

## 1. Project objective

Finance AI is the user-facing financial intelligence product. MPFM is the proposed intelligence architecture intended to power deeper market understanding and prediction. The research platform is the internal environment for ingesting data, training models, running controlled experiments, comparing forecasts and validating whether the research has genuine out-of-sample value.

The central objective is not merely to display indicators, summarize financial information or generate trading suggestions. It is to build a system that can forecast future market behaviour with measurable reliability.

The prediction product should ultimately support:

- Direction: UP, DOWN or SIDEWAYS.
- Multiple forecast horizons, with each horizon independently defined and evaluated.
- Expected return or movement distribution, not only a class label.
- Volatility and market-regime estimates.
- Calibrated probabilities, uncertainty and forecast confidence.
- A timestamped prediction record that can later be compared with the realized outcome.

These are target product capabilities. The current MVP label contract is narrower: a five-trading-day UP/DOWN/HOLD classification with fixed thresholds. Do not confuse the proposed product scope with current implementation.

## 2. System boundaries

| Layer | Responsibility | Evidence/status |
|---|---|---|
| Finance AI product | User-facing market intelligence, forecasts, research and portfolio/broker workflows | Product direction/design; not all modules are implemented |
| Research platform | Data ingestion, point-in-time datasets, experiments, model evaluation, registry and reproducibility | Significant pipeline components documented in repository |
| MPFM | Shared financial representation plus task, philosophy and mandate conditioning | Research architecture / hypothesis; real-market advantage not proven |
| Broker integrations | User-authorized account, portfolio and execution connectivity | Six broker names shown in product UI concept; do not treat as implemented |
| Independent market-data layer | Licensed historical and real-time information for research and prediction | Current gating work; rights and provider approval required |

Broker connectivity is not a substitute for exchange-wide data licensing. An account API may allow the connected user to access certain market/account capabilities, but that does not automatically grant redistribution or commercial research rights for all users.

## 3. Existing repository foundation

The repository documents the following implemented components:

- Typed engineering foundation, configuration, logging, validation and domain models.
- Historical Yahoo Finance adapter and immutable raw storage.
- Cleaning, data-quality scoring and corporate-action adjustment support.
- A 52-feature leak-aware MVP feature set.
- UP/DOWN/HOLD label generation and versioned dataset construction.
- Logistic Regression and Random Forest baseline training.
- Chronological evaluation and walk-forward backtesting with purge logic.
- Research-only FastAPI inference; live mode and order execution are intentionally absent.
- Incremental data pipeline, drift detection, autonomous retraining workflow, model registry and observability.
- Temporal LSTM experiment, ensemble/probability-calibration experiment and point-in-time multimodal data abstraction.

See the implementation reports linked from [the research index](README.md). The authoritative technical status remains in ../CURRENT_STATE.md and the milestone-specific reports.

## 4. Current empirical evidence — do not overstate it

The first real-data workflow used AAPL daily data from Yahoo Finance. The repository records weak baseline classification performance, roughly 0.32–0.36 accuracy on a documented real-data run. A walk-forward Logistic Regression run recorded 25 folds and 17 trades with approximately -7.5% net return, while buy-and-hold on that same documented period was approximately +18.2%. Static runs at the 0.55 signal threshold produced zero trades in the documented experiments.

The temporal LSTM used the same versioned data/features/labels as the baseline. Sequence-length validation selected L=10 with macro-F1 0.2953 (L=5: 0.2716; L=20: 0.2649). The candidate was registered but not promoted, and the test-split backtest produced zero trades at the 0.55 threshold.

The LR/RF ensemble measured constituent diversity (agreement 0.412; P(UP) correlation -0.175), but the selected ensemble's macro-F1 was 0.186 versus 0.240 for Logistic Regression and 0.295 for Random Forest. The ensemble remained a candidate and was not promoted.

These results establish that the research pipeline can run controlled experiments. They do **not** establish a dependable trading signal, a profitable strategy, foundation-model superiority or generalization across instruments and market regimes.

## 5. MPFM research thesis

**Hypothesis:** a shared financial-state representation, trained on broad point-in-time financial observations and evaluated across multiple prediction tasks and investment mandates, may learn transferable market structure that improves downstream forecasts compared with strong task-specific baselines.

This is a hypothesis to falsify, not an established result. A large model, extensive pretraining or a philosophy-conditioned architecture is not evidence of predictive advantage by itself.

### Proposed architecture

1. **Point-in-Time Financial State Encoder:** transforms market, instrument, corporate-action, fundamental and (only when properly licensed and timestamped) external information into a causal state representation.
2. **Prediction/task heads:** estimate direction, return distribution, volatility, regime and other explicitly defined targets at separately evaluated horizons.
3. **Philosophy ontology/encoder:** represents investment philosophies as structured principles, constraints, time horizons and evidence preferences.
4. **Mandate encoder:** represents the actual objective, constraints, liquidity needs, risk budget and permitted universe for a mandate.
5. **Risk and decision layer:** turns calibrated forecasts into risk-aware decisions. It must not contaminate the evaluation of the raw forecast.
6. **Optional disentanglement research:** Financial State–Mandate Disentanglement (FSMD) is a candidate experiment for separating reusable market-state information from mandate-specific preferences. It is not yet proven novel or effective.

### Important design decision

The base UP/DOWN/SIDEWAYS market forecast must exist independently of any one investment philosophy. Philosophy and mandate conditioning should be evaluated as optional variants or downstream decision context. Otherwise, a model that predicts what a philosophy prefers could be mistaken for a model that predicts what the market will do.

Philosophical references discussed in the project (including Buffett, Harshad Mehta and Ravi Bhaskar) are inspiration for ontology research, not validated algorithms or evidence of those individuals' exact methods.

## 6. Main unresolved research questions

| Question | Why it matters | Current status |
|---|---|---|
| Does Candidate B provide genuine methodological novelty? | Novelty must be established against prior art and strong baselines | Unproven; requires precise formal definition and literature comparison |
| Does foundation pretraining improve market prediction? | MPFM's central value proposition depends on measurable transfer | Unproven; requires controlled pretraining/ablation study |
| Does compositional generalization work on actual markets? | New combinations of instruments, regimes and mandates must generalize | Unproven; no valid real-market evidence recorded |
| Does the model generalize across instruments? | Single-ticker evidence is insufficient | Multi-instrument research required |
| Does the model survive regime changes? | Market distributions are non-stationary | Requires regime-stratified walk-forward testing |
| Do external modalities add incremental predictive value? | Fundamentals/news may help, but can also introduce leakage and noise | Integration abstraction exists; real licensed source and market experiment pending |
| Are probability estimates reliable? | A directional score must be calibrated before decision use | Calibration machinery exists; current ensemble result was not a model improvement |
| Does any predictive gain survive costs and execution assumptions? | Classification quality is not profitability | Existing evidence is weak; more robust market-level tests required |

The project previously tracked gaps G01–G13. Their exact original definitions are not reproduced here because the authoritative wording was not present in the repository material reviewed for this consolidation. Preserve those IDs when the source gap list is brought back; do not invent replacement titles or silently renumber them.

## 7. Required experimental discipline

Every model-family comparison must use a common, versioned research contract:

- Same point-in-time universe and source eligibility rules.
- Same prediction timestamp and forecast horizon.
- Same target/label definition.
- Same chronological train/validation/test boundaries.
- Purge/embargo where labels overlap.
- Transformations fitted on training data only.
- Hyperparameter and threshold selection restricted to training/validation.
- A final untouched test period, followed by walk-forward confirmation.
- Explicit missing-data and source-availability handling.
- Separate prediction metrics from trading/portfolio metrics.
- Transaction costs, slippage, liquidity and execution assumptions frozen before test evaluation.
- Multiple-testing awareness and preservation of all attempted experiments, including failures.
- Reproducibility metadata: code commit, data version, feature version, target version, model/config version, random seeds, split boundaries and source entitlements.

A synthetic fixture can validate software behaviour and time semantics. It cannot establish real-market predictive performance.

## 8. Data and legal dependencies

The point-in-time multimodal layer already defines event time, publication time, ingestion time and availability time, and uses availability time for joins. It also deliberately refuses to invent missing modality values.

However, the repository records that no licensed fundamentals/news source was approved for the multimodal experiment. Experiments A–D were deliberately not run on fixtures, because doing so would fabricate empirical findings. Sentiment and embedding features were deferred.

Historical data rights, real-source ingestion permissions, retention and redistribution permissions therefore remain dependencies for real-market validation. Patent/FTO questions require review by a qualified external legal specialist; this document is not a legal opinion.

## 9. Immediate research priorities

1. Lock the prediction contract: universe, forecast issue-time, target horizons, direction labels and return-distribution targets.
2. Establish reliable point-in-time historical data and data-rights evidence.
3. Build a multi-instrument, multi-regime baseline comparison before adding foundation-model complexity.
4. Quantify the incremental value of each modality through ablation on licensed, as-of data.
5. Formalize MPFM and Candidate B precisely enough to compare with prior work and simple alternatives.
6. Test foundation pretraining and compositional generalization with controlled out-of-sample experiments.
7. Promote no model until the prediction and downstream risk gates are both satisfied.

## 10. References inside this repository

- ../CURRENT_STATE.md
- ../DATA_INGESTION_BLUEPRINT.md
- ../DATA_ARCHITECTURE.md
- ../FEATURE_ENGINEERING_BLUEPRINT.md
- ../EVALUATION_BACKTESTING_IMPLEMENTATION.md
- ../TEMPORAL_MODEL_IMPLEMENTATION.md
- ../ENSEMBLE_CALIBRATION_IMPLEMENTATION.md
- ../MULTIMODAL_FINANCE_DATA_IMPLEMENTATION.md
- [Market data and broker source review](MARKET_DATA_AND_BROKER_INTEGRATION.md)
- [Prediction-model experiment ledger](PREDICTION_MODEL_RESEARCH.md)


## 11. Project chat source

The conversation **Finance AI Research Planning** (project context timestamp 2026-11-16 14:47) is analyzed in [FINANCE_AI_CHAT_ANALYSIS.md](FINANCE_AI_CHAT_ANALYSIS.md). Its preserved direction is to research distinct trader/investor philosophies, formalize principles into model/algorithm research and investigate MPFM. It also records D0–D4 sequencing, parallel ontology/licensing/baseline work, the point-in-time prerequisite for multimodal learning, external data/legal dependencies and the unproven Candidate B / foundation-pretraining / compositional-generalization claims.

The exact G01–G13 wording and full D0–D4 task-to-subsystem mapping remain to be recovered from the complete source transcript. Do not infer them from this summary.


## 12. Phase 1 extension: financial world modeling

The user supplied a detailed Phase 1 research note (sections 61–66) that sharpens MPFM's architecture from a foundation encoder into a three-part programme:

1. State representation / encoder.
2. Market-dynamics model that predicts distributions over future states.
3. Independent decision, risk and execution evaluation.

The distinction is material: a state encoder is not itself a world model. A market dynamics predictor without action conditioning is not yet an action-conditioned simulator. A more complete world-model claim requires valid action-conditioned rollouts or counterfactuals and a defensible way to validate them.

The TFWM paper is a relevant state-representation benchmark, not proof that an MPFM financial world model already exists. It reports 15-minute cross-sectional Rank IC for return, volatility change and spread change, averaged over 32 evaluation months. The supervised multihead result improves return and volatility Rank IC relative to the individual supervised rows, while the spread result is slightly below the standalone spread specialist. The paper also reports substantial month-to-month performance variation. These results motivate task-selective shared learning and multi-regime evaluation; they are not Indian-market UP/DOWN accuracy or realized trading returns.

**New architecture decisions proposed for research:**
- Begin with a price-taker market-evolution model and a separate execution-cost/fill model.
- Keep market-impact dynamics as a separate HFT branch that requires licensed depth/order-event data and credible counterfactual evaluation.
- Test shared return/volatility learning with specialist spread/liquidity capacity.
- Build a financially constrained augmentation registry rather than applying generic random time-series transformations.
- Test hybrid reliability-gated multimodal fusion only when inputs are point-in-time and approved.
- Keep base market forecasts philosophy-independent; evaluate mandate conditioning as an adapter, head or decision preference.

Full analysis, source limitations, experiment matrices and references: [FINANCIAL_WORLD_MODELING_PHASE1.md](FINANCIAL_WORLD_MODELING_PHASE1.md).


## 13. HFT systems and open-source execution research

The public-source study is recorded in [HFT Systems and Open-Source Ecosystem Research](HFT_SYSTEMS_AND_OPEN_SOURCE_ECOSYSTEM_RESEARCH.md).

Key conclusions:

- Public HFT firm material repeatedly emphasizes integrated data, pricing/alpha, risk, execution, infrastructure, operations and research feedback—not a single predictive model.
- Finance AI remains prediction-first. HFT microstructure and execution are separate lanes.
- NautilusTrader is the leading event-driven execution architecture candidate to evaluate; HftBacktest is the specialist L2/L3 replay, latency and queue-model candidate; ABIDES is the agent-based simulation reference.
- LEAN, Hummingbot, FinRL-X and Qlib provide narrower references for event-driven trading, connector/order lifecycle, portfolio composition and quant research workflows.
- These are research candidates, not adopted dependencies or evidence of Indian venue integration.
- HftBacktest and NautilusTrader both document limits around replaying an immutable historical market; simulated fill assumptions and market-impact boundaries must be explicit.
- NSE market-data levels, multicast/leased-line delivery and usage policy make licensed non-display depth data a separate gating dependency.
- D0 → D1 → D2 → D3 → D4 remains unchanged. No undocumented D-code mapping has been inferred.


## 14. Execution-engine and HFT replay compatibility audit

The component-level compatibility and experiment plan is documented in [NautilusTrader Compatibility & HftBacktest POC](NAUTILUS_COMPATIBILITY_AND_HFTBACKTEST_POC.md).

The key decisions are:

- Preserve Finance AI as the authority for canonical instrument identity, point-in-time data, forecast lineage, model/experiment registry and predictive research.
- Evaluate NautilusTrader only as an isolated, optional event-driven execution subsystem; custom Python adapters are documented, but Indian exchange/broker adapters are not in the official adapter list reviewed.
- Evaluate HftBacktest only after a permitted event dataset carries valid exchange and local receive timestamps and suitable depth/order semantics.
- Do not map the current daily OHLCV data source or BUY/SELL output directly to a live execution command.
- Preserve the current close-to-close research backtest as a separately versioned baseline.
- Keep D0 → D1 → D2 → D3 → D4 unchanged.


## 12. Backend model research and benchmark programme — 2026-11-21

The user's clarified technical priority is backend-first model and algorithm development: read current research papers, reproduce strong baselines, design candidate algorithms, and assess them across accuracy, precision, recall, F1, calibration, statistical significance, economic performance and runtime.

The new [MPFM Model Research & Benchmark Roadmap](MPFM_MODEL_RESEARCH_AND_BENCHMARK_ROADMAP.md) records:
- A current evidence-based review of FinVerse (2026), pretrained TSFMs for financial returns (2026), TFWM/Market-1T (2026), TensorLOB (2026), TailDART (2026), LiT (2025), financial ML evaluation integrity (2026 working paper) and FinCast (2025).
- A multi-view benchmark contract covering classification, regression, probabilistic forecasts, volatility, cross-sectional ranking, portfolio outcomes, statistical evidence and inference latency.
- Candidate algorithms RC-MTFSM, SPT-LOB, RGEE, CSFA, DHT-FH and DSA. These are proposed hypotheses only; no novelty or performance claim is made.
- A model-research agent organisation and the MBR-00 to MBR-09 experiment sequence.

### New research conclusions

1. A single Accuracy/F1 leaderboard is insufficient. Financial model selection needs point-wise, ranking and realised portfolio views.
2. Pretrained time-series foundation models can be useful priors, but recent return-forecasting evidence shows that statistically reliable gains over random-walk baselines are sparse and asset-dependent.
3. Shared representations may help return and volatility tasks, while spread/liquidity can need specialist capacity.
4. Structure-preserving tensor architectures are a promising LOB research direction, but FI-2010 and crypto/US datasets do not prove Indian-market transfer.
5. Compact inference and low latency should be measured after predictive quality and calibration; model-only sub-millisecond results do not represent feed-to-decision latency.
6. The previous LR/RF ensemble regression means that simple averaging or majority voting must not be assumed to improve performance.
7. First execution should re-establish current baselines, add naive/random-walk comparisons, complete classification/calibration metrics and expand out-of-sample evaluation before attempting the new MPFM candidates.

The existing D0 → D1 → D2 → D3 → D4 sequence remains unchanged. The model research programme supports that sequence and does not bypass the point-in-time financial foundation or data-rights dependencies.


## 13. Modular system architecture and engineering disciplines — 2026-11-21

The user clarified that MPFM research, open-source reviews and model benchmarks must directly inform the actual system design. The system must be modular and use computer-science/software-engineering fundamentals to remain correct, performant, maintainable and reliable in real-world operation.

Added [MPFM Modular System Architecture & Engineering Blueprint](MPFM_MODULAR_SYSTEM_ARCHITECTURE_AND_ENGINEERING_BLUEPRINT.md).

### Architecture decisions proposed

1. Use a modular monolith with DDD bounded contexts and ports/adapters as the initial code architecture; extract independently deployable services only when performance, isolation, scaling or operational requirements justify them.
2. Separate product/control, real-time market-data/decision, research/model, autonomous-agent and platform-engineering planes.
3. Preserve Python-first MVP and existing accepted ADRs. Any Rust/C++ hot path, new database, cloud service or external broker/market-data integration needs measured evidence and an explicit new/superseding ADR.
4. Define independent module ownership for source entitlements, reference/security master, market data, market state, corporate actions, point-in-time data, features, datasets, model research/registry, inference, decision/risk, backtesting, future execution, agent orchestration and application API.
5. Apply DSA structures from actual event workloads (bounded ring buffers, hash maps, monotonic deques, heaps, ordered price-level structures and bounded queues); benchmark and property-test before optimisation.
6. Apply OOP/OOPM/OOAD with domain entities/value objects, immutable events, application services, ports/adapters, explicit state machines, SOLID and C4/UML artefacts; avoid unnecessary class and service proliferation.
7. Apply CN/OS/DBMS/distributed-systems principles: timestamp/sequence correctness, reconnect and gap recovery, async I/O vs CPU-bound workers, process/resource isolation, bounded queues/backpressure, idempotency, transactional outbox where needed, replay, transactions and recovery.
8. Keep training, inference, decision/risk and any future execution separate. LLM agents do not sit on the per-tick market hot path.
9. Add SLOs, fault-injection, contract/property/soak/performance/security tests, telemetry, backups and incident/recovery procedures before claiming production readiness.
10. Preserve the D0 → D1 → D2 → D3 → D4 priority sequence.

### Evidence boundary

The existing SYSTEM_ARCHITECTURE.md describes the MVP; ARCHITECTURE_PRINCIPLES.md and accepted ADRs record existing layer and dependency decisions. The new modular blueprint is a proposed target state. It does not claim a new architecture, database, broker adapter, hot path or production infrastructure has been implemented.
