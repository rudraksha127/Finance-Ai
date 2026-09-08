# PROJECT BIBLE — Finance AI

> Canonical source of truth for the Finance AI project.
> Every agent, developer, and stakeholder must read this before making changes.

---

## Project Name

**Finance AI — MVP**

## Vision

Build a research-grade, reproducible ML system that generates predictions from historical financial data using a clean, auditable pipeline — from raw data ingestion to walk-forward backtested predictions.

## Problem Statement

Financial markets produce vast amounts of structured historical data. The challenge is not data availability but building a **correct, leak-free, reproducible** pipeline that transforms raw market data into validated predictions without introducing look-ahead bias, overfitting, or false confidence.

## MVP Objective

Deliver a **minimum viable prediction pipeline** that:

1. Ingests historical financial data (OHLCV)
2. Cleans and validates the data
3. Engineers features using only past information
4. Generates labels from future windows (without contaminating features)
5. Creates chronologically-split datasets
6. Trains models with walk-forward validation
7. Produces backtested predictions with realistic assumptions
8. Exposes predictions via a simple API

## Long-Term Objective

Evolve toward a production-grade system with automated data ingestion, continuous dataset growth, data quality monitoring, model retraining, drift detection, safe model promotion, and controlled autonomous learning.

## Scope (MVP)

- Historical data ingestion (CSV/API)
- Data cleaning pipeline
- Feature engineering (deterministic, timestamped)
- Label generation (forward-looking windows)
- Chronological dataset creation
- Model training (simple baselines: linear, tree-based)
- Walk-forward backtesting
- Prediction output
- Simple dashboard for results visualization
- Configuration-driven experiments

## Non-Scope (MVP)

- Live trading
- Broker integration
- Auto-trading
- HFT infrastructure
- Reinforcement learning
- LLM agents
- Autonomous retraining
- Model registry
- Distributed computing
- Kubernetes / cloud deployment
- Production streaming systems
- Deep learning architectures
- Options trading engine
- Order-book prediction
- News intelligence / sentiment
- Multi-asset correlation networks

## Core Architecture Concept

```
Raw Data → Clean Data → Features → Labels → Dataset → Model → Backtest → Predictions
```

Each stage is:
- Independently testable
- Configurable via YAML
- Logged and auditable
- Stateless where possible

## Engineering Principles

1. **Simplicity before complexity** — one engineer must understand the full system
2. **Reproducibility over convenience** — every experiment must be re-runnable
3. **Explicit contracts over hidden assumptions** — interfaces are documented
4. **Time-series correctness over generic ML conventions** — no random splits
5. **Data integrity over model complexity** — clean data > fancy model
6. **Testability over clever code** — if it can't be tested, it can't be shipped
7. **Modular architecture over monolithic scripts** — components are isolated
8. **Configuration over hard-coded values** — nothing is magic
9. **Deterministic experiments wherever possible** — seeds, versions, locks
10. **Never introduce future architecture prematurely** — build what's needed now

## ML Principles

1. **No future information leakage** — features never see future data
2. **Chronological ordering always** — train < validation < test in time
3. **Labels use future windows, features use past windows** — strict separation
4. **Walk-forward validation** — no random train/test splits
5. **Explicit timestamps** — every observation is time-stamped
6. **Reproducible transformations** — same input → same output
7. **No claims without out-of-sample evidence** — in-sample accuracy is meaningless

## Data Principles

1. Raw data is immutable — never modify source files
2. All transformations are logged and versioned
3. Data lineage is traceable from prediction back to raw source
4. Missing data handling is explicit, not implicit
5. Timezone handling is consistent and documented
6. Data quality checks run before every pipeline stage

## Repository Rules

1. No secrets in source code — ever
2. No hard-coded file paths
3. No `pip install` without updating requirements
4. Every new module has at least one test
5. Configuration changes are documented in DECISIONS.md
6. No binary files (models, data) in git — use .gitignore
7. All experiments are logged with parameters and results

## Development Workflow

1. Read PROJECT_BIBLE.md before starting work
2. Check CURRENT_STATE.md for what exists
3. Create a feature branch
4. Implement with tests
5. Run full test suite
6. Update CURRENT_STATE.md if architecture changed
7. Add ADR to DECISIONS.md if architectural decision was made
8. Submit PR with clear description

## Definition of Done

- [ ] Feature works as described
- [ ] Tests pass (unit + integration)
- [ ] No future information leakage
- [ ] Configuration is externalized
- [ ] Documentation is updated
- [ ] Code review completed
- [ ] No regressions in existing functionality

## Future Evolution Roadmap

```
Phase 1 (MVP)          Phase 2 (Production)     Phase 3 (Autonomous)
─────────────          ────────────────────     ────────────────────
Historical Data        Automated Ingestion      Drift Detection
Data Cleaning          Continuous Growth         Safe Model Promotion
Feature Engineering    Quality Monitoring        Controlled Learning
Label Generation       Model Retraining
Dataset Creation       Model Evaluation
Model Training         Model Registry
Walk-Forward Backtest  Promotion Pipeline
Prediction API         Monitoring & Alerts
Dashboard              Production Dashboard
```
