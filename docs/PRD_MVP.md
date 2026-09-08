# PRD — Finance AI MVP

> **Single source of truth** for every coding task in the MVP.
> This document is prescriptive. If it is not in this PRD, it is not in the MVP.

---

## Table of Contents

1. [Product Vision](#1-product-vision)
2. [Problem Statement](#2-problem-statement)
3. [Target Users](#3-target-users)
4. [Functional Requirements](#4-functional-requirements)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [User Stories](#6-user-stories)
7. [Input/Output Contracts](#7-inputoutput-contracts)
8. [Success Metrics](#8-success-metrics)
9. [Risks & Assumptions](#9-risks--assumptions)
10. [Out of Scope Features](#10-out-of-scope-features)
11. [MVP Milestones](#11-mvp-milestones)
12. [Acceptance Criteria](#12-acceptance-criteria)

---

## 1. Product Vision

Finance AI is a research-grade, reproducible machine learning system that transforms historical financial data into validated predictions. The system generates probabilities of stock movement (UP / DOWN / HOLD) using a clean, auditable pipeline — from raw data ingestion through walk-forward backtested evaluation — with zero tolerance for future information leakage.

**MVP Goal:** Deliver a minimum viable prediction pipeline that ingests historical OHLCV data, engineers features, trains models, backtests performance, and serves predictions through a simple API with a results dashboard.

**Guiding Principle:** Correctness over complexity. A reproducible pipeline that produces honest out-of-sample results is infinitely more valuable than a complex system that produces misleading accuracy numbers.

---

## 2. Problem Statement

Financial markets generate vast amounts of structured historical data — open, high, low, close, volume (OHLCV) — across thousands of securities. The raw data is readily available. The challenge is not data availability but building a **correct, leak-free, reproducible** pipeline that transforms this data into validated predictions without introducing:

- **Look-ahead bias** — using future information in features
- **Overfitting** — memorizing noise rather than learning patterns
- **False confidence** — reporting in-sample accuracy as if it were predictive
- **Irreproducibility** — results that cannot be re-run from scratch

Existing approaches often skip rigorous time-series methodology, use random train/test splits (invalid for financial data), or lack the engineering discipline needed to trust any single result. The result is a graveyard of backtests that look profitable on paper but fail immediately in practice.

**This MVP solves the pipeline problem:** build a system where every stage is independently testable, every transformation is logged, and every evaluation metric reflects realistic out-of-sample performance.

---

## 3. Target Users

### 3.1 Quantitative Researchers

- Need reproducible feature engineering and backtesting
- Want to iterate quickly on hypothesis testing
- Require transparent methodology to trust results
- **Primary concern:** Can I trust this number?

### 3.2 Individual Traders

- Want to understand stock movement probabilities
- Need a tool that does not claim unrealistic returns
- Value simplicity and honesty over complexity
- **Primary concern:** What does this model actually predict?

### 3.3 Software Engineers Building Financial Systems

- Need a reference architecture for ML pipelines
- Want clean interfaces between components
- Require configuration-driven experiments
- **Primary concern:** Can I extend this without breaking it?

---

## 4. Functional Requirements

### 4.1 Historical Data Input

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-DI-01 | Accept OHLCV data in CSV format | P0 |
| FR-DI-02 | Accept OHLCV data in Parquet format | P1 |
| FR-DI-03 | Validate required columns: timestamp, open, high, low, close, volume | P0 |
| FR-DI-04 | Validate timestamp ordering (ascending chronological) | P0 |
| FR-DI-05 | Reject data with duplicate timestamps | P0 |
| FR-DI-06 | Log ingestion metadata: source file, record count, date range | P0 |
| FR-DI-07 | Support single-ticker and multi-ticker datasets | P0 |

### 4.2 Dataset Creation

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-DS-01 | Create chronologically-split datasets (train / validation / test) | P0 |
| FR-DS-02 | Default split ratios: 70% train / 15% validation / 15% test | P0 |
| FR-DS-03 | Splits are always time-ordered: train end < validation start, validation end < test start | P0 |
| FR-DS-04 | No overlap between splits | P0 |
| FR-DS-05 | Log split boundaries (timestamps) and record counts per split | P0 |
| FR-DS-06 | Dataset versioning via metadata hash | P1 |

### 4.3 Feature Engineering Module

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-FE-01 | Compute price return features (1-day, 5-day, 10-day, 20-day) | P0 |
| FR-FE-02 | Compute volatility features (rolling std over configurable windows) | P0 |
| FR-FE-03 | Compute volume features (volume ratio, VWAP deviation) | P0 |
| FR-FE-04 | Compute momentum features (RSI, rate of change) | P0 |
| FR-FE-05 | Compute mean-reversion features (distance from moving average, Bollinger band position) | P0 |
| FR-FE-06 | Configurable lookback windows (default: 5, 10, 20, 50, 100, 200 periods) | P0 |
| FR-FE-07 | All features use ONLY past information — no future leakage | P0 |
| FR-FE-08 | Feature definitions are deterministic (same input → same output) | P0 |
| FR-FE-09 | Feature metadata logged: name, computation method, lookback window | P0 |
| FR-FE-10 | NaN values after feature computation are explicitly handled (dropped or flagged) | P0 |

### 4.4 Label Generation Module

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-LG-01 | Generate classification labels: UP / DOWN / HOLD | P0 |
| FR-LG-02 | Labels derived from forward-looking price change over configurable window (default: 5 periods) | P0 |
| FR-LG-03 | Classification thresholds configurable (default: >+1% = UP, <-1% = DOWN, else HOLD) | P0 |
| FR-LG-04 | Labels use future windows — features must NOT contain label information | P0 |
| FR-LG-05 | Label distribution logged per dataset split | P0 |

### 4.5 Training Module

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-TM-01 | Train logistic regression baseline | P0 |
| FR-TM-02 | Train random forest classifier | P0 |
| FR-TM-03 | Train gradient boosting classifier (if time permits, P1) | P1 |
| FR-TM-04 | All training configuration externalized to YAML | P0 |
| FR-TM-05 | Random seeds set explicitly for reproducibility | P0 |
| FR-TM-06 | Model artifacts saved with: config snapshot, metrics, training data hash | P0 |
| FR-TM-07 | Training logs: parameters, duration, final metrics | P0 |
| FR-TM-08 | No model promoted without walk-forward validation | P0 |

### 4.6 Prediction Module

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-PM-01 | Generate prediction probabilities for each class (P(UP), P(DOWN), P(HOLD)) | P0 |
| FR-PM-02 | Generate point predictions (argmax of probabilities) | P0 |
| FR-PM-03 | Include confidence scores with predictions | P0 |
| FR-PM-04 | Predictions include model version and timestamp | P0 |
| FR-PM-05 | Predictions output as structured data (DataFrame / JSON) | P0 |

### 4.7 Backtesting Module

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-BT-01 | Walk-forward backtesting with configurable train/test windows | P0 |
| FR-BT-02 | Default walk-forward: 252-period train window, 21-period test window, 21-period step | P0 |
| FR-BT-03 | Account for transaction costs (configurable, default: 10 bps) | P0 |
| FR-BT-04 | Compute: accuracy, precision, recall, F1, Sharpe ratio, max drawdown, win rate | P0 |
| FR-BT-05 | Generate backtest report with per-fold metrics | P0 |
| FR-BT-06 | Log backtest configuration and results as structured data | P0 |
| FR-BT-07 | No profitability claims without out-of-sample evidence | P0 |

### 4.8 API

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-API-01 | RESTful API for prediction serving | P0 |
| FR-API-02 | POST /predict endpoint: accepts feature data, returns predictions | P0 |
| FR-API-03 | GET /health endpoint: returns system status | P0 |
| FR-API-04 | GET /model/info endpoint: returns current model metadata | P1 |
| FR-API-05 | Input validation on all endpoints | P0 |
| FR-API-06 | Model version included in all prediction responses | P0 |
| FR-API-07 | No authentication required (MVP — local only) | P0 |
| FR-API-08 | API framework: FastAPI or Flask (project will choose) | P0 |

### 4.9 Dashboard

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-DB-01 | Display prediction results with confidence scores | P0 |
| FR-DB-02 | Display backtest performance metrics | P0 |
| FR-DB-03 | Display cumulative returns chart over backtest period | P0 |
| FR-DB-04 | Display model information (type, training date, metrics) | P1 |
| FR-DB-05 | Dashboard reads from API, not directly from models | P0 |
| FR-DB-06 | Simple, functional interface (not beautiful) | P0 |

---

## 5. Non-Functional Requirements

### 5.1 Scalability

| ID | Requirement |
|----|-------------|
| NFR-SC-01 | System must handle datasets up to 10 years of daily data (~2,500 rows per ticker) |
| NFR-SC-02 | Feature computation must handle up to 100 tickers without architecture changes |
| NFR-SC-03 | Single-machine execution (no distributed computing in MVP) |

### 5.2 Reliability

| ID | Requirement |
|----|-------------|
| NFR-RL-01 | Pipeline stages must fail loudly — no silent error swallowing |
| NFR-RL-02 | Failed pipeline stages logged with full context |
| NFR-RL-03 | Partial results must not be served as complete predictions |

### 5.3 Reproducibility

| ID | Requirement |
|----|-------------|
| NFR-RP-01 | Same input data + same configuration → same output (deterministic) |
| NFR-RP-02 | Random seeds set for all stochastic operations |
| NFR-RP-03 | Package versions pinned in requirements.txt |
| NFR-RP-04 | Configuration snapshots logged with every experiment |
| NFR-RP-05 | Data transformations are pure functions where possible |

### 5.4 Performance

| ID | Requirement |
|----|-------------|
| NFR-PF-01 | Single prediction request served in < 100ms |
| NFR-PF-02 | Walk-forward backtest over 5 years of data completes in < 5 minutes |
| NFR-PF-03 | Feature computation for 1 ticker over 10 years completes in < 30 seconds |

### 5.5 Security

| ID | Requirement |
|----|-------------|
| NFR-SE-01 | No API keys or secrets in source code |
| NFR-SE-02 | No credentials in configuration files |
| NFR-SE-03 | .env files always in .gitignore |
| NFR-SE-04 | API runs locally only (no public exposure) |
| NFR-SE-05 | No eval() or exec() on untrusted input |

### 5.6 Logging

| ID | Requirement |
|----|-------------|
| NFR-LO-01 | Structured logging via structlog (JSON format) |
| NFR-LO-02 | Every pipeline stage logs: start, parameters, duration, outcome |
| NFR-LO-03 | Log levels: DEBUG (dev), INFO (progress), WARNING (data issues), ERROR (failures) |
| NFR-LO-04 | No print() statements in production code |
| NFR-LO-05 | Data quality issues logged as WARNING with counts |

### 5.7 Testing

| ID | Requirement |
|----|-------------|
| NFR-TE-01 | Minimum 80% line coverage for src/ |
| NFR-TE-02 | Unit tests for all utility functions |
| NFR-TE-03 | Integration tests for pipeline stages |
| NFR-TE-04 | No tests that depend on external services |
| NFR-TE-05 | Test data fixtures in tests/fixtures/ |
| NFR-TE-06 | Full test suite passes before any merge |

### 5.8 Configuration

| ID | Requirement |
|----|-------------|
| NFR-CF-01 | All configuration in YAML files under config/ |
| NFR-CF-02 | Environment-specific overrides via config/{env}.yaml |
| NFR-CF-03 | Secrets via environment variables only |
| NFR-CF-04 | Config schema validation at startup |
| NFR-CF-05 | Default values documented in YAML comments |

---

## 6. User Stories

### US-01: Data Ingestion

**As a** researcher,
**I want to** load historical OHLCV data from CSV files into the pipeline,
**so that** I can begin feature engineering and model training.

**Acceptance Criteria:**
- [ ] CSV loader accepts files with columns: timestamp, open, high, low, close, volume
- [ ] Loader validates column presence and data types
- [ ] Loader rejects files with duplicate timestamps
- [ ] Loader logs: source file path, record count, date range
- [ ] Loader outputs a validated DataFrame with proper datetime index

---

### US-02: Feature Engineering

**As a** researcher,
**I want to** automatically compute technical features from historical data using only past information,
**so that** I can build prediction models without manual feature creation.

**Acceptance Criteria:**
- [ ] Feature categories: returns, volatility, volume, momentum, mean-reversion
- [ ] Lookback windows configurable (default: 5, 10, 20, 50, 100, 200)
- [ ] Zero future information in any feature
- [ ] Feature computation is deterministic
- [ ] NaN values after computation are flagged and logged

---

### US-03: Label Generation

**As a** researcher,
**I want to** generate classification labels (UP/DOWN/HOLD) from future price movements,
**so that** I can train supervised models for stock direction prediction.

**Acceptance Criteria:**
- [ ] Labels derived from forward window (default: 5 periods)
- [ ] Thresholds configurable (default: >+1% = UP, <-1% = DOWN)
- [ ] Label distribution logged per split
- [ ] Labels and features never share information

---

### US-04: Model Training

**As a** researcher,
**I want to** train baseline models with walk-forward validation,
**so that** I can evaluate predictive performance honestly.

**Acceptance Criteria:**
- [ ] At least 2 models trained: logistic regression, random forest
- [ ] Training configuration fully externalized to YAML
- [ ] Random seeds set explicitly
- [ ] Model artifacts saved with config, metrics, data hash
- [ ] Training duration logged

---

### US-05: Walk-Forward Backtesting

**As a** trader,
**I want to** run walk-forward backtests that simulate realistic trading conditions,
**so that** I can trust the reported performance metrics.

**Acceptance Criteria:**
- [ ] Walk-forward windows configurable (default: 252 train / 21 test / 21 step)
- [ ] Transaction costs applied (default: 10 bps)
- [ ] Metrics: accuracy, precision, recall, F1, Sharpe, max drawdown, win rate
- [ ] Per-fold results reported
- [ ] No in-sample evaluation results presented as out-of-sample

---

### US-06: Prediction Serving

**As a** developer,
**I want to** get predictions through a simple API endpoint,
**so that** I can integrate the model into other systems or tools.

**Acceptance Criteria:**
- [ ] POST /predict accepts feature data, returns predictions with probabilities
- [ ] GET /health returns system status
- [ ] Input validation on all endpoints
- [ ] Model version included in responses
- [ ] Response time < 100ms

---

### US-07: Results Dashboard

**As a** trader,
**I want to** see prediction results and backtest performance in a simple dashboard,
**so that** I can quickly assess model quality without reading raw data.

**Acceptance Criteria:**
- [ ] Dashboard shows latest predictions with confidence scores
- [ ] Dashboard shows cumulative returns chart from backtest
- [ ] Dashboard shows key metrics (Sharpe, drawdown, win rate)
- [ ] Dashboard reads from API, not directly from models
- [ ] Dashboard loads without errors

---

### US-08: Configuration-Driven Experiments

**As a** researcher,
**I want to** change experiment parameters via YAML configuration,
**so that** I can run multiple experiments without modifying code.

**Acceptance Criteria:**
- [ ] All pipeline parameters configurable via config/default.yaml
- [ ] Environment-specific overrides supported
- [ ] Config validation at startup
- [ ] Config snapshot logged with every experiment

---

## 7. Input/Output Contracts

### 7.1 Data Input Contract

**Input:** OHLCV CSV/Parquet files

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| timestamp | datetime | Yes | ISO 8601 format, ascending order, no duplicates |
| open | float | Yes | > 0 |
| high | float | Yes | >= open, >= close |
| low | float | Yes | <= open, <= close |
| close | float | Yes | > 0 |
| volume | int/float | Yes | >= 0 |
| ticker | string | No | If present, used for multi-ticker datasets |

**Validation Rules:**
- No null values in required columns
- Timestamps must be in ascending chronological order
- No duplicate timestamps within a ticker
- high >= max(open, close)
- low <= min(open, close)

### 7.2 Feature Output Contract

**Output:** Feature DataFrame

| Property | Description |
|----------|-------------|
| Index | DatetimeIndex (same as input timestamp) |
| Columns | Engineered feature columns (returns_1d, returns_5d, volatility_20d, etc.) |
| Values | Float64, NaN for insufficient lookback periods |
| Metadata | Feature definitions, computation timestamps, lookback windows |

### 7.3 Label Output Contract

**Output:** Label Series

| Property | Description |
|----------|-------------|
| Index | DatetimeIndex (aligned with feature index) |
| Values | Categorical: "UP", "DOWN", "HOLD" |
| Metadata | Forward window length, threshold values, label distribution |

### 7.4 Prediction Output Contract

**Output:** JSON Response

```json
{
  "model_version": "v1.0.0-20260904",
  "timestamp": "2026-09-04T12:00:00Z",
  "ticker": "AAPL",
  "predictions": {
    "label": "UP",
    "probabilities": {
      "UP": 0.72,
      "DOWN": 0.15,
      "HOLD": 0.13
    },
    "confidence": 0.72
  },
  "features_used": ["returns_1d", "returns_5d", "volatility_20d", "..."],
  "inference_time_ms": 12
}
```

### 7.5 Backtest Output Contract

**Output:** JSON Report

```json
{
  "backtest_config": {
    "train_window": 252,
    "test_window": 21,
    "step_size": 21,
    "transaction_cost_bps": 10
  },
  "model": "random_forest",
  "total_folds": 10,
  "metrics": {
    "accuracy": 0.54,
    "precision": 0.56,
    "recall": 0.52,
    "f1": 0.54,
    "sharpe_ratio": 1.23,
    "max_drawdown": -0.08,
    "win_rate": 0.57
  },
  "per_fold": [
    {
      "fold": 1,
      "train_start": "2020-01-01",
      "train_end": "2020-12-31",
      "test_start": "2021-01-01",
      "test_end": "2021-01-31",
      "accuracy": 0.53,
      "sharpe_ratio": 1.15
    }
  ]
}
```

---

## 8. Success Metrics

### 8.1 Model Performance Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Accuracy | > 52% | Correct predictions / total predictions |
| Precision (UP) | > 55% | True UP / (True UP + False UP) |
| Recall (UP) | > 50% | True UP / (True UP + Missed UP) |
| F1 Score | > 0.52 | Harmonic mean of precision and recall |
| Sharpe Ratio | > 1.0 | Risk-adjusted return (annualized) |
| Max Drawdown | < 15% | Largest peak-to-trough decline |
| Win Rate | > 53% | Winning trades / total trades |

**Note:** These are conservative targets for a baseline system. The goal is honest evaluation, not unrealistic claims.

### 8.2 System Performance Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Prediction Latency | < 100ms | Time from request to response |
| Backtest Duration | < 5 min | 5-year walk-forward backtest |
| Feature Computation | < 30s | 1 ticker, 10 years of data |
| Pipeline Completion | < 10 min | End-to-end: raw data → predictions |
| Test Coverage | ≥ 80% | Line coverage for src/ |

### 8.3 Quality Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Reproducibility | 100% | Same input + config → same output |
| Data Validation | 100% | All ingestion passes validation checks |
| Documentation Coverage | 100% | All public functions have docstrings |

---

## 9. Risks & Assumptions

### 9.1 Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Insufficient historical data for training | High | Medium | Support multiple data sources; document minimum data requirements |
| Feature engineering introduces leakage | Critical | Medium | Strict separation of feature/label windows; integration tests verify no leakage |
| Overfitting to specific market regime | High | High | Walk-forward validation; conservative model complexity; multiple market conditions |
| Transaction costs erode predicted returns | Medium | High | Configurable cost model; report metrics with and without costs |
| Model performance degrades over time | Medium | High | Document as known limitation; Phase 2 addresses retraining |
| Single-ticker prediction generalizes poorly | Medium | Medium | Train on diverse tickers; report per-ticker metrics |
| Pipeline configuration drift | Low | Low | YAML validation; config snapshots with experiments |

### 9.2 Assumptions

| Assumption | Impact if Wrong | Validation |
|------------|-----------------|------------|
| Historical OHLCV data is available and accessible | Blocks entire pipeline | Provide sample data for testing |
| At least one simple model captures signal above random | MVP produces no value | Test against random baseline |
| Daily frequency is sufficient for MVP | May miss intraday patterns | Document as future enhancement |
| Single-machine computation is adequate | Performance bottleneck | Benchmark against NFR targets |
| Python ML ecosystem remains stable | Dependency issues | Pin versions; minimal dependencies |
| Transaction costs at 10 bps are realistic | Misleading backtest results | Research typical retail costs |

---

## 10. Out of Scope Features

The following are **explicitly excluded** from the MVP. They may be addressed in future phases.

| Category | Excluded Feature | Rationale |
|----------|-----------------|-----------|
| **Trading** | Live trading execution | MVP is prediction-only |
| **Trading** | Broker API integration | No real-money operations |
| **Trading** | Order management system | Out of scope for MVP |
| **Trading** | Portfolio optimization | Future phase |
| **AI/ML** | Reinforcement learning trading | Too complex for MVP |
| **AI/ML** | Deep learning models (LSTM, Transformer) | Simple baselines first |
| **AI/ML** | LLM agent integration | No NLP in MVP |
| **AI/ML** | Autonomous model retraining | Manual retraining for MVP |
| **Data** | Real-time streaming data | Historical only for MVP |
| **Data** | News sentiment / alternative data | Structured OHLCV only |
| **Data** | Order book data | Level 1 price data sufficient |
| **Infrastructure** | Cloud deployment | Local execution for MVP |
| **Infrastructure** | Kubernetes / container orchestration | Not needed for MVP |
| **Infrastructure** | Distributed computing | Single-machine sufficient |
| **Infrastructure** | Database storage | File-based storage for MVP |
| **HFT** | High-frequency trading engine | Not applicable at daily frequency |
| **HFT** | Sub-second latency optimization | Not applicable at daily frequency |
| **Options** | Options pricing model | Not applicable |
| **Options** | Options trading strategy | Not applicable |

---

## 11. MVP Milestones

### Milestone 1: Foundation ✅ (Complete)

- [x] Project documentation (PROJECT_BIBLE, ENGINEERING_CONSTITUTION, ARCHITECTURE_PRINCIPLES)
- [x] Directory structure
- [x] Configuration files
- [x] Requirements and dependencies
- [x] Foundation tests

### Milestone 2: Data Layer

- [ ] Data ingestion module (CSV/Parquet loader)
- [ ] Data validation (schema, types, ordering)
- [ ] Data cleaning (missing values, outliers)
- [ ] Data quality checks and logging
- [ ] Unit tests for data layer
- [ ] Sample data fixtures for testing

**Exit Criteria:** Can load a CSV file, validate it, and produce a clean DataFrame.

### Milestone 3: Feature & Label Layer

- [ ] Feature engineering module (returns, volatility, volume, momentum, mean-reversion)
- [ ] Label generation module (UP/DOWN/HOLD from forward window)
- [ ] Feature-label separation verification (no leakage)
- [ ] Unit tests for feature computation
- [ ] Integration tests verifying no future information leakage

**Exit Criteria:** Can produce a feature matrix and label vector with zero leakage.

### Milestone 4: Dataset & Model Layer

- [ ] Dataset assembly with chronological splits
- [ ] Model training (logistic regression, random forest)
- [ ] Model artifact saving with metadata
- [ ] Walk-forward validation framework
- [ ] Unit tests for training and splitting

**Exit Criteria:** Can train models and produce predictions with walk-forward validation.

### Milestone 5: Evaluation & API Layer

- [ ] Walk-forward backtesting with transaction costs
- [ ] Performance metrics computation
- [ ] Backtest report generation
- [ ] REST API for prediction serving
- [ ] API input validation
- [ ] Unit and integration tests for API

**Exit Criteria:** Can serve predictions via API and generate backtest reports.

### Milestone 6: Dashboard & Integration

- [ ] Results dashboard
- [ ] Prediction visualization
- [ ] Performance metrics display
- [ ] End-to-end pipeline integration test
- [ ] Documentation updates

**Exit Criteria:** Full pipeline works end-to-end: data → features → model → prediction → dashboard.

---

## 12. Acceptance Criteria

### 12.1 Data Layer Acceptance

- [ ] Can load OHLCV CSV files with validation
- [ ] Rejects files with missing required columns
- [ ] Rejects files with duplicate timestamps
- [ ] Rejects files with non-chronological timestamps
- [ ] Logs ingestion metadata (source, count, date range)
- [ ] All validation tests pass

### 12.2 Feature Layer Acceptance

- [ ] Computes all feature categories: returns, volatility, volume, momentum, mean-reversion
- [ ] Configurable lookback windows
- [ ] Zero NaN propagation from feature computation (handled explicitly)
- [ ] Feature computation is deterministic (same input → same output)
- [ ] Integration test confirms no future information in features

### 12.3 Label Layer Acceptance

- [ ] Generates UP/DOWN/HOLD labels from forward window
- [ ] Thresholds configurable and logged
- [ ] Label distribution logged per split
- [ ] Labels do not contaminate features

### 12.4 Dataset Layer Acceptance

- [ ] Chronological splits: train < validation < test in time
- [ ] No overlap between splits
- [ ] Split boundaries logged (timestamps, counts)
- [ ] Default ratios: 70/15/15

### 12.5 Model Layer Acceptance

- [ ] At least 2 models trained successfully
- [ ] Training configuration externalized to YAML
- [ ] Random seeds set and logged
- [ ] Model artifacts saved with metadata
- [ ] Training metrics logged

### 12.6 Backtesting Acceptance

- [ ] Walk-forward backtesting with configurable windows
- [ ] Transaction costs applied
- [ ] All metrics computed: accuracy, precision, recall, F1, Sharpe, max drawdown, win rate
- [ ] Per-fold results reported
- [ ] No in-sample results presented as out-of-sample

### 12.7 API Acceptance

- [ ] POST /predict returns valid predictions with probabilities
- [ ] GET /health returns 200 OK
- [ ] Input validation rejects malformed requests
- [ ] Model version included in responses
- [ ] Response time < 100ms

### 12.8 Dashboard Acceptance

- [ ] Displays latest predictions
- [ ] Displays backtest metrics
- [ ] Displays cumulative returns chart
- [ ] Loads without errors

### 12.9 End-to-End Acceptance

- [ ] Full pipeline runs: raw data → features → model → predictions → backtest
- [ ] All tests pass (unit + integration)
- [ ] Coverage ≥ 80% for src/
- [ ] No future information leakage in any stage
- [ ] Results reproducible from configuration
- [ ] Documentation complete and accurate

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| OHLCV | Open, High, Low, Close, Volume — standard price data format |
| Walk-Forward | Validation method where training window slides forward in time |
| Look-Ahead Bias | Using future information in a model that would not be available at prediction time |
| Overfitting | Model memorizes training data noise rather than learning generalizable patterns |
| Sharpe Ratio | Risk-adjusted return: (return - risk_free_rate) / standard_deviation |
| Max Drawdown | Largest peak-to-trough decline in cumulative returns |
| BPS | Basis points — 1 bps = 0.01% (10 bps = 0.10%) |

---

## Appendix B: Reference Documents

| Document | Purpose |
|----------|---------|
| `docs/PROJECT_BIBLE.md` | Canonical project document |
| `docs/ENGINEERING_CONSTITUTION.md` | Engineering standards |
| `docs/ARCHITECTURE_PRINCIPLES.md` | Layer definitions and contracts |
| `docs/DECISIONS.md` | Architecture decision records |
| `docs/CURRENT_STATE.md` | Current repository status |
| `config/default.yaml` | Default configuration |
