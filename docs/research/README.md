# Finance AI / MPFM — Research Workspace

**Research record started:** 2026-11-17  
**Repository:** [rudraksha127/Finance-Ai](https://github.com/rudraksha127/Finance-Ai)  
**Primary objective:** reliable, evidence-backed financial-market prediction.

This folder is the living research layer for the Finance AI project. It records research questions, data-source due diligence, model hypotheses, experimental results, dependencies, decisions and development priorities. Update it as research progresses; do not leave important conclusions only in chat.

## Start here

| Document | Purpose |
|---|---|
| [MPFM Research Master](MPFM_RESEARCH_MASTER.md) | Product objective, MPFM thesis, architecture, known research gaps and evidence rules |
| [Prediction Model Research](PREDICTION_MODEL_RESEARCH.md) | Existing model results, target design, model comparisons and proposed experiments |
| [Market Data & Broker Integration](MARKET_DATA_AND_BROKER_INTEGRATION.md) | Historical/live data sources, six broker APIs, source rights and integration boundaries |
| [NautilusTrader Compatibility & HftBacktest POC](NAUTILUS_COMPATIBILITY_AND_HFTBACKTEST_POC.md) | Exact Finance AI interface mapping, custom adapter feasibility, event schema and HFT data requirements, POC experiments and go/no-go gates |
| [HFT Systems and Open-Source Ecosystem Research](HFT_SYSTEMS_AND_OPEN_SOURCE_ECOSYSTEM_RESEARCH.md) | Public HFT firm operating models, source-level open-source reviews, event-driven architecture, market-microstructure data requirements, tool strategy and staged integration recommendations |
| [Personal Multi-Market Trading System Design](FINANCE_AI_TRADING_SYSTEM_DESIGN.md) | Clarified personal trading-intelligence vision, HFT-vs-retail-algo boundary, multi-model signal engine, risk/execution, adapters and roadmap |
| [Development Backlog](DEVELOPMENT_BACKLOG.md) | D0 → D1 → D2 → D3 → D4 order, workstreams and dependencies |
| [Research Log](RESEARCH_LOG.md) | Dated record of discoveries, decisions, experiments and next actions |
| [Finance AI Project Chat Analysis](FINANCE_AI_CHAT_ANALYSIS.md) | Analysis of the Finance AI Research Planning conversation and its preserved decisions |
| [Financial World Modeling — Phase 1](FINANCIAL_WORLD_MODELING_PHASE1.md) | TFWM paper analysis, Market-1T data, dynamics-vs-decisions architecture, task sharing, augmentation, fusion and mandate experiments |

## Existing implementation documentation

The research workspace supplements — and does not replace — the existing engineering records:

- [Repository status](../CURRENT_STATE.md)
- [Data ingestion blueprint](../DATA_INGESTION_BLUEPRINT.md)
- [Data architecture](../DATA_ARCHITECTURE.md)
- [Feature engineering blueprint](../FEATURE_ENGINEERING_BLUEPRINT.md)
- [Baseline model implementation](../BASELINE_MODEL_IMPLEMENTATION.md)
- [Evaluation and backtesting implementation](../EVALUATION_BACKTESTING_IMPLEMENTATION.md)
- [Temporal LSTM implementation](../TEMPORAL_MODEL_IMPLEMENTATION.md)
- [Ensemble and calibration implementation](../ENSEMBLE_CALIBRATION_IMPLEMENTATION.md)
- [Point-in-time multimodal data implementation](../MULTIMODAL_FINANCE_DATA_IMPLEMENTATION.md)
- [Model registry implementation](../MODEL_REGISTRY_IMPLEMENTATION.md)
- [Architecture decisions](../DECISIONS.md)

## Status vocabulary

Use these labels consistently:

- **Implemented:** code exists in this repository and is documented.
- **Tested:** the documented test or experiment was actually run; include its dataset, split and date.
- **Measured:** an empirical result exists; report the metric and baseline.
- **Designed:** an architecture or interface has been specified but is not necessarily implemented.
- **Proposed:** a research hypothesis or future candidate.
- **Blocked:** work cannot be validly completed until a named dependency is resolved.
- **Not run:** no experiment was executed. Never write a result for an experiment that was not run.

## Research integrity rules

1. Prediction quality is the primary objective. A market-direction forecast and a profitable trading strategy are related but separate outcomes.
2. Never describe a planned source, mock integration, fixture or UI element as a production integration.
3. Preserve negative results and failed experiments. A model is not promoted merely because it is newer or more complex.
4. Every empirical claim must identify the dataset/version, instrument universe, prediction horizon, time split, transaction-cost assumptions and evaluation date where applicable.
5. Use point-in-time availability. Event time, publication time, ingestion time and actual availability time must not be conflated.
6. Do not use synthetic fixtures to claim real-market predictive advantage.
7. Keep licensing, permitted use, retention and redistribution rights attached to every data source.
8. Add new findings to the relevant research document and append a dated entry to the research log.

## Current research snapshot

As of 2026-11-17, the repository records a completed research-grade single-instrument MVP and post-MVP infrastructure/model experiments. The documented AAPL experiments are weak and do **not** establish a reliable profitable prediction model. MPFM's foundation-model advantage, Candidate B novelty and compositional generalization on real markets remain unproven. Real historical data rights and approval of point-in-time fundamental/news sources remain gating dependencies.

The repository's engineering implementation records were last updated in September 2026. This research snapshot does not imply that the full test suite or every integration has been re-executed on 2026-11-17.
