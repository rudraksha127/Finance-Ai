# ARCHITECTURE PRINCIPLES — Finance AI

> Architectural boundaries and contracts for each layer.
> These layers are NOT implemented yet — this defines what they WILL be.

---

## System Layers

```
┌─────────────────────────────────────────────────────┐
│                    UI Layer                          │
│              (Dashboard / Reports)                   │
├─────────────────────────────────────────────────────┤
│                    API Layer                         │
│            (Prediction Serving)                      │
├─────────────────────────────────────────────────────┤
│                 Evaluation Layer                     │
│         (Backtesting / Metrics / Reports)            │
├─────────────────────────────────────────────────────┤
│                   Model Layer                        │
│        (Training / Inference / Selection)            │
├─────────────────────────────────────────────────────┤
│                  Dataset Layer                       │
│        (Assembly / Splitting / Versioning)           │
├─────────────────────────────────────────────────────┤
│                 Feature Layer                        │
│       (Engineering / Transformation / Store)         │
├─────────────────────────────────────────────────────┤
│                Processing Layer                      │
│         (Cleaning / Validation / Imputation)         │
├─────────────────────────────────────────────────────┤
│                  Data Layer                          │
│         (Ingestion / Storage / Retrieval)            │
└─────────────────────────────────────────────────────┘
```

---

## Layer Definitions

### 1. Data Layer
**Responsibility:** Ingest, store, and retrieve raw financial data.
**Inputs:** External data sources (CSV files, APIs)
**Outputs:** Raw, immutable data records with timestamps

**Rules:**
- Raw data is never modified after ingestion
- Every record has an explicit timestamp and timezone
- Data lineage is recorded: source → ingestion time → record count
- Failed ingestions are logged, not silently dropped

### 2. Processing Layer
**Responsibility:** Clean, validate, and prepare raw data for feature engineering.
**Inputs:** Raw data from Data Layer
**Outputs:** Clean, validated data ready for feature computation

**Rules:**
- Missing data handling is explicit and configurable
- Outlier detection is logged, not silently applied
- Data type conversions are validated
- Processing steps are logged: input rows → output rows

### 3. Feature Layer
**Responsibility:** Compute features from clean data using only past information.
**Inputs:** Clean data from Processing Layer
**Outputs:** Feature matrices with explicit timestamps

**Rules:**
- **CRITICAL:** Features are computed using ONLY past data
- Feature definitions are versioned and reproducible
- Feature calculations are deterministic (same input → same output)
- Feature metadata: name, computation method, lookback window, timestamp
- No feature uses future information — ZERO tolerance

### 4. Dataset Layer
**Responsibility:** Assemble features and labels into train/val/test datasets.
**Inputs:** Features from Feature Layer, Labels from Label Generation
**Outputs:** Versioned, chronologically-split datasets

**Rules:**
- Splits are ALWAYS chronological: train < val < test in time
- No random splitting unless explicitly justified and documented
- Dataset versioning tracks: features used, split dates, record counts
- Label generation uses future windows without contaminating features

### 5. Model Layer
**Responsibility:** Train models, make predictions, manage model artifacts.
**Inputs:** Datasets from Dataset Layer
**Outputs:** Trained models, predictions, model metadata

**Rules:**
- Training configuration is fully externalized
- Random seeds are set explicitly
- Model artifacts saved with: config, metrics, training data hash
- No model is promoted without walk-forward validation
- Simple baselines before complex models

### 6. Evaluation Layer
**Responsibility:** Backtest predictions, compute performance metrics, generate reports.
**Inputs:** Predictions from Model Layer, market data
**Outputs:** Performance metrics, backtest reports, evaluation artifacts

**Rules:**
- Walk-forward backtesting only (no in-sample evaluation)
- Transaction costs and slippage accounted for
- Statistical significance tested (not just accuracy)
- Multiple metrics: Sharpe, max drawdown, win rate, profit factor
- No profitability claims without out-of-sample evidence

### 7. API Layer
**Responsibility:** Serve predictions via a simple HTTP interface.
**Inputs:** Trained models from Model Layer
**Outputs:** JSON predictions, health checks

**Rules:**
- RESTful API with clear request/response contracts
- Input validation on all endpoints
- Model version included in responses
- Health check endpoint for monitoring
- No authentication required (MVP — local only)

### 8. UI Layer
**Responsibility:** Visualize predictions, performance, and pipeline status.
**Inputs:** API Layer responses, evaluation reports
**Outputs:** Dashboards, charts, status displays

**Rules:**
- Dashboard reads from API, not directly from models
- Visualizations update on data refresh
- Performance metrics prominently displayed
- Data quality status visible
- Simple, functional — not beautiful (MVP)

---

## Cross-Cutting Concerns

### Configuration
- All layers read from `config/` directory
- Environment-specific overrides via `config/{env}.yaml`
- Secrets via environment variables only

### Logging
- Structured logging via `structlog`
- Every layer logs entry, parameters, exit
- Pipeline orchestrator logs stage transitions

### Data Flow
```
Data → Processing → Feature → Dataset → Model → Evaluation → API → UI
  │         │           │         │        │          │        │
  └─logs───┘───logs────┘───logs──┘──logs──┘───logs───┘──logs─┘
```
