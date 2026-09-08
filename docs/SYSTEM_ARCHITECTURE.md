# SYSTEM ARCHITECTURE — Finance AI MVP

> Technical architecture blueprint for the Finance AI MVP.
> Every implementation task must comply with this architecture.
> This document is **descriptive** — it defines what exists, not what to build.

---

## Table of Contents

1. [High-Level Architecture Diagram](#1-high-level-architecture-diagram)
2. [Module Breakdown](#2-module-breakdown)
3. [Data Flow](#3-data-flow)
4. [Folder Structure](#4-folder-structure)
5. [API Boundaries](#5-api-boundaries)
6. [Database Boundaries](#6-database-boundaries)
7. [Configuration Architecture](#7-configuration-architecture)
8. [Logging Architecture](#8-logging-architecture)
9. [Testing Architecture](#9-testing-architecture)
10. [Future Extension Points](#10-future-extension-points)

---

## 1. High-Level Architecture Diagram

### 1.1 System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Finance AI — MVP                                │
│                                                                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────────────┐ │
│  │ Raw Data │──▶│ Ingestion│──▶│Validation│──▶│    Processing        │ │
│  │ (CSV/    │   │          │   │          │   │ (Clean / Impute)     │ │
│  │  Parquet)│   └──────────┘   └──────────┘   └──────────┬───────────┘ │
│  └──────────┘                                             │             │
│                                                            ▼             │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                        Feature Engine                            │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │   │
│  │  │ Returns  │  │Volatility│  │  Volume  │  │  Momentum    │    │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────┘    │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │              Mean-Reversion / Technical                  │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────┬────────────────────────────────────┘   │
│                                │                                        │
│                                ▼                                        │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────────────────────┐ │
│  │    Label     │   │   Dataset    │   │                             │ │
│  │   Engine     │──▶│   Builder    │──▶│      Training Engine        │ │
│  │(UP/DN/HOLD) │   │(Chronological│   │  ┌──────────┐ ┌──────────┐ │ │
│  └──────────────┘   │   Splits)    │   │  │ Logistic │ │ Random   │ │ │
│                     └──────────────┘   │  │Regression│ │ Forest   │ │ │
│                                        │  └──────────┘ └──────────┘ │ │
│                                        └──────────────┬──────────────┘ │
│                                                       │                │
│                          ┌────────────────────────────┤                │
│                          ▼                            ▼                │
│                ┌──────────────────┐      ┌──────────────────────────┐  │
│                │    Backtesting   │      │   Model Registry         │  │
│                │     Engine       │      │   (Placeholder)          │  │
│                │  ┌────────────┐  │      │  ┌──────────────────┐   │  │
│                │  │Walk-Forward│  │      │  │ Artifact Store   │   │  │
│                │  └────────────┘  │      │  │ Metadata / Hash  │   │  │
│                │  ┌────────────┐  │      │  └──────────────────┘   │  │
│                │  │  Metrics   │  │      └──────────────────────────┘  │
│                │  └────────────┘  │                                    │
│                │  ┌────────────┐  │                                    │
│                │  │  Reports   │  │                                    │
│                │  └────────────┘  │                                    │
│                └────────┬─────────┘                                    │
│                         │                                              │
│                         ▼                                              │
│                ┌──────────────────┐      ┌──────────────────────────┐  │
│                │   Prediction     │      │      Dashboard           │  │
│                │    Service       │      │  (Results / Charts)      │  │
│                │  ┌────────────┐  │      │                          │  │
│                │  │  REST API  │──┼─────▶│  Reads from API          │  │
│                │  └────────────┘  │      │                          │  │
│                └──────────────────┘      └──────────────────────────┘  │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Cross-Cutting Concerns                       │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │   │
│  │  │  Config  │  │  Logger  │  │ Pipeline │  │   Metrics    │   │   │
│  │  │  (YAML)  │  │(structlog│  │  (CLI)   │  │  (Collector) │   │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Dependency Graph

```
                    ┌──────────┐
                    │  Config  │ ◄── (read by all modules)
                    └────┬─────┘
                         │
         ┌───────────────┼───────────────────────────────┐
         ▼               ▼                               ▼
    ┌─────────┐   ┌──────────────┐              ┌──────────────┐
    │ Ingestion│   │  Validation  │              │   Logging    │
    └────┬─────┘   └──────┬───────┘              └──────────────┘
         │                │
         ▼                ▼
    ┌─────────────────────────┐
    │     Processing          │
    └────────────┬────────────┘
                 │
    ┌────────────┼────────────┐
    ▼            ▼            ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│ Feature │ │ Label   │ │         │
│ Engine  │ │ Engine  │ │         │
└────┬────┘ └────┬────┘ │         │
     │           │       │         │
     └─────┬─────┘       │         │
           ▼             │         │
    ┌─────────────┐      │         │
    │  Dataset    │      │         │
    │  Builder    │      │         │
    └──────┬──────┘      │         │
           │             │         │
           ▼             ▼         │
    ┌─────────────────────────┐    │
    │    Training Engine      │    │
    └──────────┬──────────────┘    │
               │                   │
       ┌───────┼───────┐          │
       ▼       ▼       ▼          ▼
┌──────────┐ ┌───────┐ ┌────────────────┐
│Backtesting│ │Model  │ │  Prediction    │
│  Engine   │ │Registry│ │  Service       │
└──────────┘ └───────┘ └────────┬───────┘
                                │
                                ▼
                        ┌──────────────┐
                        │  Dashboard   │
                        └──────────────┘
```

### 1.3 Architectural Principles

| Principle | Rule | Enforcement |
|-----------|------|-------------|
| **Loose Coupling** | Modules communicate through interfaces, not implementations | Abstract base classes / Protocol types |
| **High Cohesion** | Each module does one thing well | Single-responsibility principle |
| **No Circular Dependencies** | Dependency graph is a DAG | Import checks in tests |
| **Time-Series Safe** | No random splits, no future leakage | Integration tests verify |
| **Reproducible** | Same input + config → same output | Deterministic transforms, seeds |
| **Independently Testable** | Every module testable in isolation | Fixtures, mocks, no external deps |

---

## 2. Module Breakdown

### 2.1 Data Ingestion

| Property | Value |
|----------|-------|
| **Module** | `src/data/ingestion.py` |
| **Class** | `DataIngestion` |
| **Responsibility** | Load raw OHLCV data from files (CSV, Parquet) into pandas DataFrames |
| **Inputs** | File path, file format, ticker filter |
| **Outputs** | Raw DataFrame with DatetimeIndex |
| **Dependencies** | `pandas`, `pathlib`, `structlog` |
| **Config Section** | `data.raw_dir`, `data.default_format` |

**Key Methods:**
- `load(path: Path, format: str) -> pd.DataFrame`
- `load_directory(dir_path: Path, format: str) -> pd.DataFrame`

**Rules:**
- Does NOT modify data — read-only
- Logs: source path, record count, date range, column list
- Rejects files with missing required columns
- Supports single-file and directory-level ingestion

---

### 2.2 Data Validation

| Property | Value |
|----------|-------|
| **Module** | `src/data/validation.py` |
| **Class** | `DataValidator` |
| **Responsibility** | Validate schema, types, ordering, and data quality of ingested data |
| **Inputs** | Raw DataFrame from Data Ingestion |
| **Outputs** | Validated DataFrame or ValidationReport (success/failure + details) |
| **Dependencies** | `pandas`, `numpy`, `structlog` |
| **Config Section** | `processing.missing_strategy`, `processing.max_missing_pct` |

**Key Methods:**
- `validate(df: pd.DataFrame) -> ValidationResult`
- `_validate_columns(df: pd.DataFrame) -> List[Issue]`
- `_validate_types(df: pd.DataFrame) -> List[Issue]`
- `_validate_ordering(df: pd.DataFrame) -> List[Issue]`
- `_validate_duplicates(df: pd.DataFrame) -> List[Issue]`
- `_validate_ranges(df: pd.DataFrame) -> List[Issue]`
- `_validate_missing(df: pd.DataFrame) -> List[Issue]`

**Validation Rules:**
- Required columns: `timestamp`, `open`, `high`, `low`, `close`, `volume`
- No null values in required columns
- Timestamps ascending, no duplicates within ticker
- `high >= max(open, close)`, `low <= min(open, close)`
- Missing data percentage logged per column
- OHLCV ranges: `open > 0`, `high > 0`, `low > 0`, `close > 0`, `volume >= 0`

---

### 2.3 Processing (Cleaning)

| Property | Value |
|----------|-------|
| **Module** | `src/data/processing.py` |
| **Class** | `DataProcessor` |
| **Responsibility** | Clean validated data: handle missing values, apply outlier treatment |
| **Inputs** | Validated DataFrame from Data Validation |
| **Outputs** | Clean DataFrame ready for feature engineering |
| **Dependencies** | `pandas`, `numpy`, `structlog` |
| **Config Section** | `processing.missing_strategy`, `processing.outlier_method` |

**Key Methods:**
- `process(df: pd.DataFrame) -> pd.DataFrame`
- `_handle_missing(df: pd.DataFrame) -> pd.DataFrame`
- `_handle_outliers(df: pd.DataFrame) -> pd.DataFrame`

**Rules:**
- Missing data strategy: configurable (drop, fill_mean, fill_median, fill_forward, interpolate)
- Outlier detection: configurable (none, zscore, iqr)
- Logs: input rows → output rows, rows dropped/filled, outliers detected
- Never modifies raw data — operates on validated copy

---

### 2.4 Feature Engine

| Property | Value |
|----------|-------|
| **Module** | `src/features/engine.py` |
| **Class** | `FeatureEngine` |
| **Responsibility** | Compute all technical features from clean data using only past information |
| **Inputs** | Clean DataFrame from Processing |
| **Outputs** | Feature DataFrame with DatetimeIndex |
| **Dependencies** | `pandas`, `numpy`, `structlog` |
| **Config Section** | `features.lookback_windows`, `features.categories` |

**Key Methods:**
- `compute(df: pd.DataFrame) -> pd.DataFrame`
- `_compute_returns(df: pd.DataFrame, windows: List[int]) -> pd.DataFrame`
- `_compute_volatility(df: pd.DataFrame, windows: List[int]) -> pd.DataFrame`
- `_compute_volume(df: pd.DataFrame) -> pd.DataFrame`
- `_compute_momentum(df: pd.DataFrame, windows: List[int]) -> pd.DataFrame`
- `_compute_mean_reversion(df: pd.DataFrame, windows: List[int]) -> pd.DataFrame`

**Feature Categories:**

| Category | Features | Lookback | Formula |
|----------|----------|----------|---------|
| Returns | `returns_{n}d` | 5, 10, 20, 50, 100, 200 | `(close_t - close_{t-n}) / close_{t-n}` |
| Volatility | `volatility_{n}d` | 5, 10, 20, 50, 100, 200 | `rolling_std(returns, n)` |
| Volume | `volume_ratio_{n}d` | 5, 20 | `volume_t / rolling_mean(volume, n)` |
| Volume | `vwap_deviation_{n}d` | 5, 20 | `(close - vwap) / vwap` |
| Momentum | `rsi_{n}d` | 14 | Relative Strength Index |
| Momentum | `roc_{n}d` | 5, 10, 20 | Rate of Change |
| Mean Reversion | `ma_distance_{n}d` | 20, 50, 100, 200 | `(close - ma_n) / ma_n` |
| Mean Reversion | `bb_position_{n}d` | 20, 50 | Bollinger Band Position |

**Rules:**
- **ZERO TOLERANCE** for future information leakage
- All computations use only past data (shifted windows)
- Deterministic: same input → same output
- NaN values after computation logged and flagged
- Feature metadata logged: name, category, lookback window, formula

---

### 2.5 Label Engine

| Property | Value |
|----------|-------|
| **Module** | `src/features/labels.py` |
| **Class** | `LabelEngine` |
| **Responsibility** | Generate classification labels from forward-looking price movements |
| **Inputs** | Clean DataFrame (for close prices) + feature DataFrame index |
| **Outputs** | Label Series with categorical values (UP / DOWN / HOLD) |
| **Dependencies** | `pandas`, `numpy`, `structlog` |
| **Config Section** | `dataset.label_type`, `dataset.label_window` |

**Key Methods:**
- `generate(df: pd.DataFrame) -> pd.Series`
- `_compute_forward_return(df: pd.DataFrame, window: int) -> pd.Series`
- `_classify(returns: pd.Series, thresholds: Dict) -> pd.Series`

**Label Logic:**
```
forward_return = (close_{t+n} - close_t) / close_t

if forward_return > threshold_up   → "UP"
if forward_return < -threshold_down → "DOWN"
else                               → "HOLD"
```

**Default Thresholds:**
- UP: > +1.0%
- DOWN: < -1.0%
- HOLD: between -1.0% and +1.0%

**Rules:**
- Labels use future windows — features must NOT contain label information
- Label distribution logged per split
- Labels aligned with feature index (no temporal misalignment)
- Forward window configurable (default: 5 periods)

---

### 2.6 Dataset Builder

| Property | Value |
|----------|-------|
| **Module** | `src/dataset/builder.py` |
| **Class** | `DatasetBuilder` |
| **Responsibility** | Assemble features + labels into chronologically-split datasets |
| **Inputs** | Feature DataFrame + Label Series |
| **Outputs** | `DatasetSplit` object with train/val/test DataFrames |
| **Dependencies** | `pandas`, `structlog` |
| **Config Section** | `dataset.split_ratios`, `dataset.label_type` |

**Key Methods:**
- `build(features: pd.DataFrame, labels: pd.Series) -> DatasetSplit`
- `_compute_split_boundaries(index: pd.DatetimeIndex, ratios: Dict) -> Tuple`
- `_validate_chronological(splits: DatasetSplit) -> bool`

**DatasetSplit Object:**
```python
@dataclass
class DatasetSplit:
    train: Tuple[pd.DataFrame, pd.Series]  # (X_train, y_train)
    val: Tuple[pd.DataFrame, pd.Series]    # (X_val, y_val)
    test: Tuple[pd.DataFrame, pd.Series]   # (X_test, y_test)
    metadata: Dict  # split boundaries, record counts, feature list
```

**Rules:**
- Splits are ALWAYS chronological: train end < val start, val end < test start
- Default ratios: 70% / 15% / 15%
- No overlap between splits
- Split boundaries logged: timestamps, record counts per split
- Dataset versioning via metadata hash

---

### 2.7 Training Engine

| Property | Value |
|----------|-------|
| **Module** | `src/model/training.py` |
| **Class** | `TrainingEngine` |
| **Responsibility** | Train ML models, save artifacts with metadata |
| **Inputs** | `DatasetSplit` object from Dataset Builder |
| **Outputs** | `TrainedModel` object (model + metadata) |
| **Dependencies** | `scikit-learn`, `joblib`, `structlog` |
| **Config Section** | `model.random_seed`, `model.models` |

**Key Methods:**
- `train(split: DatasetSplit, model_config: Dict) -> TrainedModel`
- `_instantiate_model(model_type: str, params: Dict) -> estimator`
- `_save_artifact(model, metrics: Dict, config: Dict, data_hash: str) -> Path`

**Supported Models (MVP):**

| Model | Class | Priority |
|-------|-------|----------|
| Logistic Regression | `sklearn.linear_model.LogisticRegression` | P0 |
| Random Forest | `sklearn.ensemble.RandomForestClassifier` | P0 |
| Gradient Boosting | `sklearn.ensemble.GradientBoostingClassifier` | P1 |

**TrainedModel Object:**
```python
@dataclass
class TrainedModel:
    model: Any                          # sklearn estimator
    model_type: str                     # "logistic_regression", "random_forest"
    model_version: str                  # "v1.0.0-{date}"
    metrics: Dict[str, float]           # train/val metrics
    config: Dict                        # full training config snapshot
    data_hash: str                      # SHA256 of training data
    feature_names: List[str]            # ordered feature names
    trained_at: datetime                # training timestamp
    artifact_path: Path                 # path to saved model file
```

**Rules:**
- Random seeds set explicitly for all stochastic operations
- Model artifacts saved with: config snapshot, metrics, training data hash
- Training logs: parameters, duration, final metrics
- No model promoted without walk-forward validation

---

### 2.8 Model Registry (Placeholder)

| Property | Value |
|----------|-------|
| **Module** | `src/model/registry.py` |
| **Class** | `ModelRegistry` |
| **Responsibility** | Store, retrieve, and manage model artifacts and metadata |
| **Inputs** | `TrainedModel` objects |
| **Outputs** | Loaded models, model metadata, model listings |
| **Dependencies** | `joblib`, `json`, `pathlib`, `structlog` |
| **Config Section** | `model.artifact_dir` |

**Key Methods:**
- `save(model: TrainedModel) -> Path`
- `load(model_version: str) -> TrainedModel`
- `list_models() -> List[Dict]`
- `get_latest() -> TrainedModel`

**Rules:**
- MVP: file-based storage in `models/` directory
- Each model artifact saved as `.joblib` with companion `.json` metadata
- Model version is unique identifier
- No model overwrite — version increments

**Future Extensions (Placeholder):**
- Database-backed registry
- Model promotion/demotion workflow
- A/B testing support

---

### 2.9 Prediction Service

| Property | Value |
|----------|-------|
| **Module** | `src/api/prediction.py` |
| **Class** | `PredictionService` |
| **Responsibility** | Serve predictions via REST API |
| **Inputs** | Feature data (from request) + trained model (from registry) |
| **Outputs** | JSON prediction response |
| **Dependencies** | `FastAPI`, `pydantic`, `structlog` |
| **Config Section** | `api.host`, `api.port` |

**Key Methods:**
- `predict(features: Dict) -> PredictionResponse`
- `health() -> HealthResponse`
- `model_info() -> ModelInfoResponse`

**Endpoints:**

| Method | Path | Description | Input | Output |
|--------|------|-------------|-------|--------|
| POST | `/predict` | Get prediction for features | Feature dict | Prediction JSON |
| GET | `/health` | System health check | None | Health status |
| GET | `/model/info` | Current model metadata | None | Model info JSON |

**Rules:**
- Input validation on all endpoints
- Model version included in all responses
- No authentication (MVP — local only)
- Response time < 100ms
- Graceful error handling with structured error responses

---

### 2.10 Backtesting Engine

| Property | Value |
|----------|-------|
| **Module** | `src/evaluation/backtesting.py` |
| **Class** | `BacktestEngine` |
| **Responsibility** | Run walk-forward backtests and compute performance metrics |
| **Inputs** | Feature DataFrame + Label Series + Training config |
| **Outputs** | `BacktestReport` with per-fold and aggregate metrics |
| **Dependencies** | `pandas`, `numpy`, `scikit-learn`, `structlog` |
| **Config Section** | `evaluation.walk_forward`, `evaluation.transaction_cost_bps`, `evaluation.metrics` |

**Key Methods:**
- `run(features: pd.DataFrame, labels: pd.Series, model_config: Dict) -> BacktestReport`
- `_generate_folds(index: pd.DatetimeIndex, config: Dict) -> List[Fold]`
- `_evaluate_fold(fold: Fold, model_class, params: Dict) -> FoldResult`
- `_compute_aggregate_metrics(fold_results: List[FoldResult]) -> Dict`
- `_compute_sharpe(returns: pd.Series, risk_free_rate: float) -> float`
- `_compute_max_drawdown(cumulative_returns: pd.Series) -> float`

**Walk-Forward Logic:**
```
for each fold:
    train_start = fold_start
    train_end   = fold_start + train_window
    test_start  = train_end
    test_end    = test_start + test_window

    model = train(data[train_start:train_end])
    predictions = model.predict(data[test_start:test_end])
    fold_metrics = evaluate(predictions, actuals[test_start:test_end])

    slide forward by step_size
```

**Metrics Computed:**

| Metric | Formula | Category |
|--------|---------|----------|
| Accuracy | correct / total | Classification |
| Precision | TP / (TP + FP) | Classification |
| Recall | TP / (TP + FN) | Classification |
| F1 | 2 * (P * R) / (P + R) | Classification |
| Sharpe Ratio | mean(excess_return) / std(excess_return) * sqrt(252) | Financial |
| Max Drawdown | min((cummax - cumval) / cummax) | Financial |
| Win Rate | winning_trades / total_trades | Financial |

**Rules:**
- Walk-forward only — no in-sample evaluation
- Transaction costs applied (default: 10 bps)
- Per-fold results reported
- Aggregate metrics computed across all folds
- Backtest config and results logged as structured data

---

### 2.11 Dashboard

| Property | Value |
|----------|-------|
| **Module** | `src/dashboard/app.py` |
| **Class** | `DashboardApp` |
| **Responsibility** | Visualize predictions, backtest results, and model info |
| **Inputs** | API responses from Prediction Service |
| **Outputs** | HTML pages with charts and tables |
| **Dependencies** | `Streamlit` or `Dash` (to be chosen) |
| **Config Section** | `dashboard.port` |

**Key Methods:**
- `run()` — start dashboard server
- `_render_predictions()` — show latest predictions
- `_render_backtest()` — show backtest performance
- `_render_model_info()` — show model metadata

**Dashboard Pages:**

| Page | Content |
|------|---------|
| Predictions | Latest predictions with confidence scores, ticker selector |
| Backtest | Cumulative returns chart, metrics table, per-fold breakdown |
| Model Info | Current model type, training date, metrics summary |

**Rules:**
- Dashboard reads from API — never directly from models or files
- Simple, functional interface (not beautiful)
- Charts use appropriate financial visualization patterns
- Auto-refresh on data updates

---

### 2.12 Config Module

| Property | Value |
|----------|-------|
| **Module** | `src/config/loader.py` |
| **Class** | `ConfigLoader` |
| **Responsibility** | Load, validate, and provide access to YAML configuration |
| **Inputs** | YAML files from `config/` directory |
| **Outputs** | Typed configuration object |
| **Dependencies** | `pyyaml`, `pydantic` (for schema validation) |

**Key Methods:**
- `load(config_path: str = "config/default.yaml") -> Config`
- `validate(config: Config) -> bool`
- `snapshot(config: Config) -> Dict`

**Rules:**
- Default config loaded first, environment overrides applied on top
- Config schema validated at startup
- Config snapshot logged with every experiment
- Secrets via environment variables only — never in YAML

---

### 2.13 Logger Module

| Property | Value |
|----------|-------|
| **Module** | `src/logging/logger.py` |
| **Class** | `PipelineLogger` |
| **Responsibility** | Provide structured logging across all modules |
| **Inputs** | Log messages, context, exceptions |
| **Outputs** | Structured log entries (JSON format) |
| **Dependencies** | `structlog` |
| **Config Section** | `logging.level`, `logging.format` |

**Key Methods:**
- `get_logger(name: str) -> structlog.BoundLogger`
- `log_stage_start(stage: str, params: Dict) -> None`
- `log_stage_end(stage: str, duration: float, result: Dict) -> None`
- `log_data_quality(stage: str, issues: List[Issue]) -> None`

**Rules:**
- Every pipeline stage logs: start, parameters, duration, outcome
- Log levels: DEBUG (dev), INFO (progress), WARNING (data issues), ERROR (failures)
- No `print()` statements in production code
- Data quality issues logged as WARNING with counts
- Contextual logging: module name, stage, operation

---

## 3. Data Flow

### 3.1 Pipeline Data Flow (Detailed)

```
STAGE 1: INGESTION
─────────────────
Input:   File path (CSV/Parquet)
Output:  pd.DataFrame (raw, unmodified)
Shape:   (N rows × 7 columns) [timestamp, open, high, low, close, volume, ticker?]
Storage: In-memory only (not persisted intermediate)
Logging: Source path, record count, date range, column list

STAGE 2: VALIDATION
───────────────────
Input:   pd.DataFrame (raw)
Output:  ValidationResult { df: pd.DataFrame, issues: List[Issue], passed: bool }
Shape:   (N rows × 7 columns) — same or rejected
Storage: In-memory only
Logging: Validation checks run, issues found, pass/fail

STAGE 3: PROCESSING
───────────────────
Input:   pd.DataFrame (validated)
Output:  pd.DataFrame (clean)
Shape:   (M rows × 7 columns) where M ≤ N (rows with issues may be dropped)
Storage: In-memory only
Logging: Input rows → output rows, missing values handled, outliers treated

STAGE 4: FEATURE ENGINEERING
────────────────────────────
Input:   pd.DataFrame (clean)
Output:  pd.DataFrame (features)
Shape:   (M rows × F columns) where F = number of computed features
Storage: In-memory only
Logging: Feature count, NaN count per feature, computation time

STAGE 5: LABEL GENERATION
─────────────────────────
Input:   pd.DataFrame (clean — for close prices)
Output:  pd.Series (labels)
Shape:   (M rows,) with values ["UP", "DOWN", "HOLD"]
Storage: In-memory only
Logging: Label distribution, forward window, thresholds

STAGE 6: DATASET ASSEMBLY
─────────────────────────
Input:   pd.DataFrame (features) + pd.Series (labels)
Output:  DatasetSplit { train, val, test }
Shape:   train (T×F, T labels), val (V×F, V labels), test (E×F, E labels)
Storage: In-memory only
Logging: Split boundaries, record counts per split, feature count

STAGE 7: TRAINING
─────────────────
Input:   DatasetSplit
Output:  TrainedModel { model, metrics, metadata }
Shape:   Serialized model artifact (.joblib) + metadata (.json)
Storage: models/ directory (file-based)
Logging: Model type, config, duration, metrics

STAGE 8: BACKTESTING
────────────────────
Input:   pd.DataFrame (features) + pd.Series (labels) + model config
Output:  BacktestReport { metrics, per_fold, config }
Shape:   Aggregate metrics dict + list of per-fold results
Storage: reports/ directory (JSON)
Logging: Backtest config, per-fold results, aggregate metrics

STAGE 9: PREDICTION
───────────────────
Input:   Feature dict (from API request)
Output:  PredictionResponse { label, probabilities, confidence, metadata }
Shape:   JSON response
Storage: Stateless (computed on demand)
Logging: Request features, prediction result, latency

STAGE 10: DASHBOARD
───────────────────
Input:   API responses (from Prediction Service)
Output:  HTML pages with charts and tables
Shape:   Rendered web pages
Storage: Stateless (rendered on demand)
Logging: Page loads, data fetches
```

### 3.2 Data Format Transitions

```
Raw File (CSV/Parquet)
    │
    ▼
pd.DataFrame (raw)          ← DataIngestion
    │
    ▼
pd.DataFrame (validated)    ← DataValidator
    │
    ▼
pd.DataFrame (clean)        ← DataProcessor
    │
    ├──▶ pd.DataFrame (features)  ← FeatureEngine
    │        │
    │        ▼
    │    pd.DataFrame (features) + pd.Series (labels)
    │        │
    │        ▼
    │    DatasetSplit { train, val, test }
    │        │
    │        ├──▶ TrainedModel → ModelRegistry
    │        │
    │        └──▶ BacktestReport
    │
    └──▶ pd.Series (labels)  ← LabelEngine
```

### 3.3 Error Flow

```
Module detects error
    │
    ├──▶ Log error with context (structlog)
    │
    ├──▶ Raise specific exception (DataValidationError, FeatureComputationError, etc.)
    │
    ├──▶ Pipeline orchestrator catches exception
    │
    ├──▶ Logs pipeline failure with stage, config, exception
    │
    └──▶ Exits with non-zero code (no partial results served)
```

---

## 4. Folder Structure

### 4.1 Production Layout

```
finance-ai-mvp/
│
├── docs/                           ← Documentation
│   ├── PRD_MVP.md                  ← Product Requirements Document
│   ├── PROJECT_BIBLE.md            ← Canonical project document
│   ├── ENGINEERING_CONSTITUTION.md ← Engineering standards
│   ├── ARCHITECTURE_PRINCIPLES.md  ← Layer definitions
│   ├── SYSTEM_ARCHITECTURE.md      ← This document
│   ├── DECISIONS.md                ← Architecture decision records
│   └── CURRENT_STATE.md            ← Current repository status
│
├── config/                         ← Configuration
│   ├── default.yaml                ← Default configuration
│   ├── development.yaml            ← Development overrides
│   ├── testing.yaml                ← Testing overrides
│   └── production.yaml             ← Production overrides (future)
│
├── src/                            ← Source code
│   ├── __init__.py
│   │
│   ├── data/                       ← Data Layer
│   │   ├── __init__.py
│   │   ├── ingestion.py            ← DataIngestion class
│   │   ├── validation.py           ← DataValidator class
│   │   └── processing.py           ← DataProcessor class
│   │
│   ├── features/                   ← Feature Layer
│   │   ├── __init__.py
│   │   ├── engine.py               ← FeatureEngine class
│   │   └── labels.py               ← LabelEngine class
│   │
│   ├── dataset/                    ← Dataset Layer
│   │   ├── __init__.py
│   │   └── builder.py              ← DatasetBuilder class
│   │
│   ├── model/                      ← Model Layer
│   │   ├── __init__.py
│   │   ├── training.py             ← TrainingEngine class
│   │   ├── registry.py             ← ModelRegistry class
│   │   └── prediction.py           ← PredictionService class
│   │
│   ├── evaluation/                 ← Evaluation Layer
│   │   ├── __init__.py
│   │   ├── backtesting.py          ← BacktestEngine class
│   │   └── metrics.py              ← Metrics computation
│   │
│   ├── api/                        ← API Layer
│   │   ├── __init__.py
│   │   ├── app.py                  ← FastAPI application
│   │   ├── routes.py               ← API route definitions
│   │   └── schemas.py              ← Request/response Pydantic models
│   │
│   ├── dashboard/                  ← Dashboard Layer
│   │   ├── __init__.py
│   │   ├── app.py                  ← Dashboard application
│   │   └── components.py           ← Reusable UI components
│   │
│   ├── config/                     ← Configuration Layer
│   │   ├── __init__.py
│   │   └── loader.py               ← ConfigLoader class
│   │
│   ├── logging/                    ← Logging Layer
│   │   ├── __init__.py
│   │   └── logger.py               ← PipelineLogger class
│   │
│   └── pipeline/                   ← Pipeline Orchestrator
│       ├── __init__.py
│       └── orchestrator.py         ← PipelineOrchestrator class
│
├── tests/                          ← Test suite
│   ├── __init__.py
│   ├── fixtures/                   ← Test data fixtures
│   │   ├── sample_data.csv
│   │   └── expected_features.csv
│   ├── unit/                       ← Unit tests (per module)
│   │   ├── test_data_ingestion.py
│   │   ├── test_data_validation.py
│   │   ├── test_data_processing.py
│   │   ├── test_feature_engine.py
│   │   ├── test_label_engine.py
│   │   ├── test_dataset_builder.py
│   │   ├── test_training_engine.py
│   │   ├── test_backtesting.py
│   │   └── test_config_loader.py
│   ├── integration/                ← Integration tests
│   │   ├── test_pipeline.py        ← End-to-end pipeline test
│   │   ├── test_no_leakage.py      ← Feature-label separation test
│   │   └── test_api_endpoints.py   ← API contract tests
│   └── test_foundation.py          ← Project structure tests
│
├── data/                           ← Data directories
│   ├── raw/                        ← Immutable raw data
│   ├── interim/                    ← Intermediate processing results
│   ├── processed/                  ← Final processed data
│   └── external/                   ← External/third-party data
│
├── models/                         ← Model artifacts (gitignored)
│   └── .gitkeep
│
├── reports/                        ← Generated reports (gitignored)
│   └── .gitkeep
│
├── experiments/                    ← Experiment logs (gitignored)
│   └── .gitkeep
│
├── notebooks/                      ← Exploration notebooks
│   └── .gitkeep
│
├── scripts/                        ← Utility scripts
│   └── run_pipeline.py             ← CLI pipeline runner
│
├── README.md
├── requirements.txt
├── .gitignore
└── .env.example
```

### 4.2 Module Dependency Rules

```
src/data/       → (no internal dependencies)
src/features/   → src/data/ (for data types only)
src/dataset/    → src/features/ (for feature/label types)
src/model/      → src/dataset/ (for DatasetSplit type)
src/evaluation/ → src/model/, src/dataset/
src/api/        → src/model/, src/features/, src/config/
src/dashboard/  → src/api/ (via HTTP, not direct import)
src/config/     → (no internal dependencies)
src/logging/    → (no internal dependencies)
src/pipeline/   → all modules (orchestrator)
```

**Rule:** Dependency arrows point DOWN only. No upward imports. No circular dependencies.

---

## 5. API Boundaries

### 5.1 Internal Module Interfaces

Each module exposes a public interface. Internal implementation details are private (leading underscore).

#### Data Ingestion → Data Validation

```python
# Input
raw_df: pd.DataFrame          # Raw data from file

# Output
validation_result: ValidationResult
    .df: pd.DataFrame          # Validated data (or None if failed)
    .issues: List[Issue]       # Validation issues found
    .passed: bool              # Whether validation passed

# Issue object
Issue:
    .severity: str             # "error" | "warning"
    .column: str               # Column name (or "timestamp", "schema")
    .message: str              # Human-readable description
    .count: int                # Number of affected rows
```

#### Data Validation → Data Processing

```python
# Input
validated_df: pd.DataFrame     # From validation (passed == True)

# Output
processed_df: pd.DataFrame     # Clean data

# ProcessingLog
ProcessingLog:
    .input_rows: int
    .output_rows: int
    .missing_handled: int
    .outliers_treated: int
    .strategy_used: str
```

#### Data Processing → Feature Engine

```python
# Input
clean_df: pd.DataFrame         # Clean data with OHLCV

# Output
feature_df: pd.DataFrame       # Features with DatetimeIndex

# FeatureMetadata
FeatureMetadata:
    .name: str                 # "returns_5d"
    .category: str             # "price_returns"
    .lookback: int             # 5
    .formula: str              # "returns(close, 5)"
    .nan_count: int            # NaN values in this feature
```

#### Feature Engine + Label Engine → Dataset Builder

```python
# Input
feature_df: pd.DataFrame       # From FeatureEngine
label_series: pd.Series        # From LabelEngine
config: DatasetConfig          # Split ratios, etc.

# Output
DatasetSplit:
    .train: Tuple[pd.DataFrame, pd.Series]
    .val: Tuple[pd.DataFrame, pd.Series]
    .test: Tuple[pd.DataFrame, pd.Series]
    .metadata: SplitMetadata
        .feature_names: List[str]
        .split_boundaries: Dict[str, Tuple[str, str]]
        .record_counts: Dict[str, int]
        .data_hash: str
```

#### Dataset Builder → Training Engine

```python
# Input
split: DatasetSplit            # Train/val/test splits
model_config: Dict             # Model type, hyperparameters

# Output
TrainedModel:
    .model: Any                # sklearn estimator
    .model_type: str           # "logistic_regression"
    .model_version: str        # "v1.0.0-20260904"
    .metrics: Dict[str, float] # {"accuracy": 0.54, "f1": 0.52, ...}
    .config: Dict              # Full config snapshot
    .data_hash: str            # SHA256 of training data
    .feature_names: List[str]
    .trained_at: datetime
    .artifact_path: Path
```

#### Training Engine → Model Registry

```python
# Input
model: TrainedModel

# Output
Path                            # Path to saved artifact

# Registry Query
ModelRegistry.list_models() -> List[Dict]  # [{version, type, metrics, date}]
ModelRegistry.load(version: str) -> TrainedModel
ModelRegistry.get_latest() -> TrainedModel
```

#### Model Registry → Prediction Service

```python
# Input
features: Dict[str, float]     # Feature values from request

# Output
PredictionResponse:
    .model_version: str
    .timestamp: str
    .ticker: str
    .predictions:
        .label: str            # "UP", "DOWN", "HOLD"
        .probabilities:
            .UP: float
            .DOWN: float
            .HOLD: float
        .confidence: float
    .features_used: List[str]
    .inference_time_ms: float
```

#### Backtesting Engine → Reports

```python
# Input
features: pd.DataFrame
labels: pd.Series
model_config: Dict
backtest_config: Dict

# Output
BacktestReport:
    .backtest_config: Dict
    .model: str
    .total_folds: int
    .metrics:
        .accuracy: float
        .precision: float
        .recall: float
        .f1: float
        .sharpe_ratio: float
        .max_drawdown: float
        .win_rate: float
    .per_fold: List[FoldResult]
        .fold: int
        .train_start: str
        .train_end: str
        .test_start: str
        .test_end: str
        .accuracy: float
        .sharpe_ratio: float
```

### 5.2 External API (REST)

#### POST /predict

```json
// Request
{
  "ticker": "AAPL",
  "features": {
    "returns_1d": 0.012,
    "returns_5d": 0.034,
    "volatility_20d": 0.021,
    "volume_ratio_5d": 1.23,
    "rsi_14d": 62.5
  }
}

// Response (200 OK)
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
  "features_used": ["returns_1d", "returns_5d", "volatility_20d", "volume_ratio_5d", "rsi_14d"],
  "inference_time_ms": 12.3
}

// Error Response (422 Unprocessable Entity)
{
  "error": "validation_error",
  "message": "Missing required feature: returns_1d",
  "missing_features": ["returns_1d"]
}
```

#### GET /health

```json
// Response (200 OK)
{
  "status": "healthy",
  "model_loaded": true,
  "model_version": "v1.0.0-20260904",
  "uptime_seconds": 3600
}
```

#### GET /model/info

```json
// Response (200 OK)
{
  "model_version": "v1.0.0-20260904",
  "model_type": "random_forest",
  "trained_at": "2026-09-04T10:30:00Z",
  "metrics": {
    "accuracy": 0.54,
    "precision": 0.56,
    "recall": 0.52,
    "f1": 0.54,
    "sharpe_ratio": 1.23,
    "max_drawdown": -0.08,
    "win_rate": 0.57
  },
  "feature_count": 32,
  "training_samples": 1750
}
```

---

## 6. Database Boundaries

### 6.1 MVP: File-Based Storage

The MVP uses **no database**. All data is stored as files.

| Storage Type | Location | Format | Purpose |
|-------------|----------|--------|---------|
| Raw data | `data/raw/` | CSV/Parquet | Immutable source data |
| Processed data | `data/processed/` | CSV/Parquet | Cleaned data |
| Model artifacts | `models/` | `.joblib` | Serialized sklearn models |
| Model metadata | `models/` | `.json` | Config, metrics, hash |
| Backtest reports | `reports/` | `.json` | Backtest results |
| Experiment logs | `experiments/` | `.json` | Config snapshots + results |

### 6.2 Module Read/Write Responsibilities

| Module | Reads From | Writes To |
|--------|-----------|-----------|
| DataIngestion | `data/raw/` | In-memory only |
| DataValidator | In-memory | In-memory only |
| DataProcessor | In-memory | In-memory only |
| FeatureEngine | In-memory | In-memory only |
| LabelEngine | In-memory | In-memory only |
| DatasetBuilder | In-memory | In-memory only |
| TrainingEngine | In-memory | `models/` (artifact + metadata) |
| ModelRegistry | `models/` | `models/` (new artifacts) |
| BacktestEngine | In-memory | `reports/` (JSON report) |
| PredictionService | `models/` (via registry) | In-memory (API response) |
| Dashboard | API (HTTP) | In-memory (rendered page) |

### 6.3 File Naming Conventions

```
models/
├── model_v1.0.0-20260904.joblib     ← Serialized model
├── model_v1.0.0-20260904.json       ← Model metadata
├── model_v1.0.0-20260905.joblib     ← Updated model
└── model_v1.0.0-20260905.json

reports/
├── backtest_20260904_123456.json     ← Backtest report
└── backtest_20260905_123456.json

experiments/
├── exp_20260904_001.json             ← Experiment log
└── exp_20260905_002.json
```

### 6.4 Future Database Boundaries (Phase 2+)

```
Phase 2: SQLite/PostgreSQL
├── models table     ← Model registry
├── experiments table ← Experiment tracking
├── predictions table ← Prediction history
└── data_quality table ← Data quality logs

Phase 3: Production
├── TimescaleDB      ← Time-series data
├── Redis            ← Prediction cache
└── S3               ← Model artifact storage
```

---

## 7. Configuration Architecture

### 7.1 Configuration Layers

```
┌─────────────────────────────────────────────┐
│           Environment Variables              │  ← Highest priority (secrets)
│           (.env file / OS env)               │
├─────────────────────────────────────────────┤
│        Environment-Specific Config           │  ← Medium priority
│        (config/development.yaml)             │
├─────────────────────────────────────────────┤
│           Default Config                     │  ← Lowest priority (base)
│           (config/default.yaml)              │
└─────────────────────────────────────────────┘
```

### 7.2 Config File Structure

```yaml
# config/default.yaml — Base configuration

project:
  name: finance-ai-mvp
  version: "0.1.0"

data:
  raw_dir: data/raw
  interim_dir: data/interim
  processed_dir: data/processed
  default_format: csv

processing:
  missing_strategy: fill_forward
  max_missing_pct: 0.3
  outlier_method: none

features:
  lookback_windows: [5, 10, 20, 50, 100, 200]
  categories: [price_returns, volatility, volume, momentum, mean_reversion]

dataset:
  label_type: classification
  label_window: 5
  split_ratios: { train: 0.7, val: 0.15, test: 0.15 }

model:
  random_seed: 42
  models:
    - name: logistic_regression
      type: linear
    - name: random_forest
      type: ensemble
      params: { n_estimators: 100, max_depth: 10 }

evaluation:
  walk_forward:
    train_window: 252
    test_window: 21
    step_size: 21
  transaction_cost_bps: 10
  metrics: [accuracy, precision, recall, f1, sharpe_ratio, max_drawdown, win_rate]

logging:
  level: INFO
  format: json

reproducibility:
  random_seed: 42
  log_config: true
  log_versions: true
```

### 7.3 Environment-Specific Overrides

```yaml
# config/development.yaml
logging:
  level: DEBUG

processing:
  outlier_method: zscore
```

```yaml
# config/testing.yaml
logging:
  level: WARNING

data:
  raw_dir: tests/fixtures/raw
```

### 7.4 Environment Variables

```bash
# .env (gitignored)
ENVIRONMENT=development
LOG_LEVEL=INFO
DATA_API_KEY=your_key_here  # Future use
```

### 7.5 Config Validation

At startup, the ConfigLoader validates:
- All required sections present
- Data types correct (int, float, list, dict)
- Numeric values within valid ranges
- Model types are supported
- File paths exist (or can be created)
- Split ratios sum to 1.0

Invalid configuration raises `ConfigValidationError` with specific field and reason.

---

## 8. Logging Architecture

### 8.1 Structured Log Format

```json
{
  "timestamp": "2026-09-04T12:00:00.000Z",
  "level": "info",
  "logger": "finance_ai.data.ingestion",
  "event": "data_loaded",
  "module": "DataIngestion",
  "stage": "ingestion",
  "source_path": "data/raw/AAPL.csv",
  "record_count": 2520,
  "date_range": ["2016-01-04", "2025-12-31"],
  "duration_ms": 125.3
}
```

### 8.2 Log Levels

| Level | When | Examples |
|-------|------|----------|
| **DEBUG** | Development troubleshooting | Feature values, intermediate shapes |
| **INFO** | Pipeline progress | Stage start/end, record counts, metrics |
| **WARNING** | Data quality issues | Missing values, outliers, format deviations |
| **ERROR** | Failures requiring attention | Validation failed, training error, API error |

### 8.3 Structured Log Events by Module

#### Data Ingestion
```json
{"event": "ingestion_started", "source_path": "...", "format": "csv"}
{"event": "data_loaded", "record_count": 2520, "columns": [...], "date_range": [...]}
{"event": "ingestion_failed", "error": "FileNotFoundError", "source_path": "..."}
```

#### Data Validation
```json
{"event": "validation_started", "record_count": 2520}
{"event": "validation_passed", "checks_run": 6, "issues_found": 0}
{"event": "validation_failed", "checks_run": 6, "issues_found": 3, "issues": [...]}
{"event": "data_quality_warning", "column": "volume", "issue": "missing_values", "count": 5}
```

#### Feature Engineering
```json
{"event": "features_computed", "feature_count": 32, "nan_count": 200, "duration_ms": 450}
{"event": "feature_category", "category": "returns", "features": ["returns_5d", "returns_10d"]}
{"event": "leakage_check_passed", "features_checked": 32}
```

#### Training
```json
{"event": "training_started", "model_type": "random_forest", "train_samples": 1750}
{"event": "training_completed", "model_type": "random_forest", "duration_ms": 2300, "metrics": {...}}
{"event": "model_saved", "model_version": "v1.0.0-20260904", "artifact_path": "..."}
```

#### Backtesting
```json
{"event": "backtest_started", "total_folds": 10, "config": {...}}
{"event": "fold_completed", "fold": 1, "train_range": [...], "test_range": [...], "accuracy": 0.53}
{"event": "backtest_completed", "total_folds": 10, "aggregate_metrics": {...}, "duration_ms": 45000}
```

#### API
```json
{"event": "prediction_requested", "ticker": "AAPL", "feature_count": 32}
{"event": "prediction_completed", "label": "UP", "confidence": 0.72, "latency_ms": 12}
{"event": "prediction_error", "error": "MissingFeatureError", "missing": ["returns_1d"]}
```

### 8.4 Log Categories

| Category | Module | Purpose |
|----------|--------|---------|
| `pipeline` | orchestrator.py | Pipeline stage transitions |
| `data` | ingestion.py, validation.py, processing.py | Data operations |
| `features` | engine.py, labels.py | Feature computation |
| `model` | training.py, registry.py | Model operations |
| `evaluation` | backtesting.py, metrics.py | Backtest operations |
| `api` | app.py, routes.py | API operations |
| `config` | loader.py | Configuration loading |

---

## 9. Testing Architecture

### 9.1 Test Pyramid

```
                    ┌───────┐
                    │  E2E  │  ← End-to-end pipeline test (1-2 tests)
                   ┌┴───────┴┐
                   │Integration│  ← Pipeline stage integration (5-10 tests)
                  ┌┴───────────┴┐
                  │    Unit      │  ← Per-module unit tests (50-100 tests)
                  └──────────────┘
```

### 9.2 Test Categories

#### Unit Tests (`tests/unit/`)

| Test File | Module Under Test | Key Tests |
|-----------|-------------------|-----------|
| `test_data_ingestion.py` | `src/data/ingestion.py` | Load CSV, load Parquet, reject missing columns, reject duplicates |
| `test_data_validation.py` | `src/data/validation.py` | Schema validation, type checking, ordering, range checks |
| `test_data_processing.py` | `src/data/processing.py` | Missing value handling, outlier detection |
| `test_feature_engine.py` | `src/features/engine.py` | Returns, volatility, volume, momentum, mean-reversion computation |
| `test_label_engine.py` | `src/features/labels.py` | UP/DOWN/HOLD classification, threshold application |
| `test_dataset_builder.py` | `src/dataset/builder.py` | Chronological splits, no overlap, boundary logging |
| `test_training_engine.py` | `src/model/training.py` | Model training, artifact saving, config snapshot |
| `test_backtesting.py` | `src/evaluation/backtesting.py` | Walk-forward folds, metric computation, Sharpe ratio |
| `test_config_loader.py` | `src/config/loader.py` | Config loading, validation, environment overrides |

#### Integration Tests (`tests/integration/`)

| Test File | What It Tests |
|-----------|---------------|
| `test_pipeline.py` | Full pipeline: raw data → features → model → predictions |
| `test_no_leakage.py` | Feature engineering does not use future information |
| `test_api_endpoints.py` | API contract validation, input/output schemas |

#### Foundation Tests (`tests/test_foundation.py`)

| Test | What It Verifies |
|------|------------------|
| Directory structure | All required directories exist |
| Documentation | All required docs exist |
| Configuration | .gitignore, .env.example, requirements.txt present |

### 9.3 Test Data Strategy

```
tests/fixtures/
├── sample_data.csv              ← 100 rows of valid OHLCV data
├── sample_data_missing.csv      ← Data with missing values
├── sample_data_duplicates.csv   ← Data with duplicate timestamps
├── sample_data_unordered.csv    ← Data with non-chronological timestamps
├── sample_data_short.csv        ← Data too short for features
└── expected_features.csv        ← Expected feature output for validation
```

**Rules:**
- Test fixtures are small (< 1000 rows) for fast tests
- Fixtures are committed to git (they are small)
- No tests depend on external services
- Test data is representative of real data patterns

### 9.4 Test Execution Commands

```bash
# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests only
pytest tests/integration/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Run specific test
pytest tests/unit/test_feature_engine.py::TestFeatureEngine::test_returns_computation -v

# Run tests matching pattern
pytest tests/ -k "validation" -v
```

### 9.5 Coverage Requirements

| Module | Minimum Coverage | Justification |
|--------|-----------------|---------------|
| `src/data/` | 90% | Data integrity is critical |
| `src/features/` | 85% | Feature correctness is critical |
| `src/dataset/` | 80% | Split logic must be correct |
| `src/model/` | 80% | Training must be reproducible |
| `src/evaluation/` | 80% | Metrics must be accurate |
| `src/api/` | 75% | API contracts must be valid |
| `src/config/` | 80% | Config validation is important |
| **Overall** | **≥ 80%** | Per NFR-TE-01 |

### 9.6 CI/CD Test Pipeline

```
On every PR / push to main:
  1. Run foundation tests (structure, docs, config)
  2. Run linting (ruff, black, isort)
  3. Run unit tests
  4. Run integration tests
  5. Check coverage ≥ 80%
  6. Type checking (mypy — future)
```

---

## 10. Future Extension Points

### 10.1 Extension Architecture

The MVP architecture is designed with **extension points** — places where future modules can plug in without rewriting existing code.

```
┌─────────────────────────────────────────────────────────────┐
│                     Future Extensions                        │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  News Engine │  │Options Engine│  │  Risk Engine │      │
│  │  (NLP/Sent.) │  │  (Pricing)   │  │ (Portfolio)  │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                  │               │
│         └─────────┬───────┴────────┬────────┘               │
│                   │                │                         │
│                   ▼                ▼                         │
│  ┌─────────────────────┐  ┌──────────────────────────┐     │
│  │  Extended Feature   │  │   Autonomous Retraining  │     │
│  │  Engine (v2)        │  │   Pipeline               │     │
│  └─────────────────────┘  └──────────────────────────┘     │
│                                                              │
│  ┌─────────────────────┐  ┌──────────────────────────┐     │
│  │   LLM Agent         │  │   Live Trading Engine    │     │
│  │   (Analysis)        │  │   (Broker Integration)   │     │
│  └─────────────────────┘  └──────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### 10.2 News Engine (Placeholder)

| Property | Value |
|----------|-------|
| **Module** | `src/features/news_engine.py` |
| **Responsibility** | Process news/sentiment data into features |
| **Inputs** | News headlines, social media, SEC filings |
| **Outputs** | Sentiment features (merged with price features) |
| **Extension Point** | `FeatureEngine._compute_news_features()` — plugin hook |
| **Dependencies** | NLP libraries, news API client |
| **Status** | ⏳ Placeholder — not in MVP |

**Integration Pattern:**
```python
class FeatureEngine:
    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        # Existing price features
        features = self._compute_price_features(df)

        # Extension point: news features (if enabled)
        if self.config.get("features.enable_news", False):
            news_features = self._compute_news_features(df)
            features = pd.concat([features, news_features], axis=1)

        return features
```

### 10.3 Options Engine (Placeholder)

| Property | Value |
|----------|-------|
| **Module** | `src/features/options_engine.py` |
| **Responsibility** | Process options chain data into features |
| **Inputs** | Options chain data (calls, puts, strikes, expirations) |
| **Outputs** | Options-derived features (IV, put/call ratio, gamma exposure) |
| **Extension Point** | `FeatureEngine._compute_options_features()` — plugin hook |
| **Dependencies** | Options data provider, pricing models |
| **Status** | ⏳ Placeholder — not in MVP |

### 10.4 Risk Engine (Placeholder)

| Property | Value |
|----------|-------|
| **Module** | `src/evaluation/risk_engine.py` |
| **Responsibility** | Portfolio risk analysis, position sizing, exposure management |
| **Inputs** | Predictions, market data, portfolio positions |
| **Outputs** | Risk metrics, position recommendations, exposure limits |
| **Extension Point** | BacktestingEngine post-processing hook |
| **Dependencies** | Portfolio optimization libraries |
| **Status** | ⏳ Placeholder — not in MVP |

### 10.5 Autonomous Retraining (Placeholder)

| Property | Value |
|----------|-------|
| **Module** | `src/pipeline/retraining.py` |
| **Responsibility** | Detect model drift, trigger retraining, validate new model |
| **Inputs** | Prediction history, new data, drift metrics |
| **Outputs** | Retrained model (if drift detected) |
| **Extension Point** | `PipelineOrchestrator._check_retrain_needed()` — scheduled hook |
| **Dependencies** | Drift detection libraries, model comparison logic |
| **Status** | ⏳ Placeholder — not in MVP |

**Retraining Logic (Future):**
```
1. Monitor prediction accuracy over time
2. Detect drift (accuracy drops below threshold)
3. Trigger retraining with latest data
4. Compare new model vs current model
5. Promote if new model is better (with human approval)
```

### 10.6 LLM Agent (Placeholder)

| Property | Value |
|----------|-------|
| **Module** | `src/agent/llm_agent.py` |
| **Responsibility** | Natural language analysis of predictions and market conditions |
| **Inputs** | Predictions, market data, user queries |
| **Outputs** | Natural language analysis, recommendations |
| **Extension Point** | Dashboard integration hook |
| **Dependencies** | LLM API (OpenAI, Anthropic, etc.) |
| **Status** | ⏳ Placeholder — not in MVP |

### 10.7 Live Trading Engine (Placeholder)

| Property | Value |
|----------|-------|
| **Module** | `src/trading/engine.py` |
| **Responsibility** | Execute trades based on predictions |
| **Inputs** | Predictions, risk parameters, broker credentials |
| **Outputs** | Order confirmations, position updates |
| **Extension Point** | Prediction Service webhook/callback |
| **Dependencies** | Broker API (Alpaca, Interactive Brokers, etc.) |
| **Status** | ⏳ Placeholder — not in MVP |

### 10.8 Extension Point Summary

| Extension | Extension Point | Module | Status |
|-----------|----------------|--------|--------|
| News Engine | FeatureEngine plugin | `src/features/news_engine.py` | ⏳ Placeholder |
| Options Engine | FeatureEngine plugin | `src/features/options_engine.py` | ⏳ Placeholder |
| Risk Engine | BacktestEngine hook | `src/evaluation/risk_engine.py` | ⏳ Placeholder |
| Autonomous Retraining | PipelineOrchestrator hook | `src/pipeline/retraining.py` | ⏳ Placeholder |
| LLM Agent | Dashboard hook | `src/agent/llm_agent.py` | ⏳ Placeholder |
| Live Trading | PredictionService hook | `src/trading/engine.py` | ⏳ Placeholder |
| Cloud Deployment | Docker/K8s manifests | `deploy/` | ⏳ Placeholder |
| Database Storage | ModelRegistry backend | `src/model/registry.py` | ⏳ Placeholder |
| Authentication | API middleware | `src/api/middleware.py` | ⏳ Placeholder |
| Monitoring | Logging hooks | `src/logging/metrics.py` | ⏳ Placeholder |

---

## Appendix A: Module Quick Reference

| Module | Class | File | Responsibility |
|--------|-------|------|----------------|
| Data Ingestion | `DataIngestion` | `src/data/ingestion.py` | Load raw data from files |
| Data Validation | `DataValidator` | `src/data/validation.py` | Validate schema, types, ordering |
| Data Processing | `DataProcessor` | `src/data/processing.py` | Clean, impute, handle outliers |
| Feature Engine | `FeatureEngine` | `src/features/engine.py` | Compute technical features |
| Label Engine | `LabelEngine` | `src/features/labels.py` | Generate UP/DOWN/HOLD labels |
| Dataset Builder | `DatasetBuilder` | `src/dataset/builder.py` | Assemble chronological splits |
| Training Engine | `TrainingEngine` | `src/model/training.py` | Train ML models |
| Model Registry | `ModelRegistry` | `src/model/registry.py` | Store/load model artifacts |
| Prediction Service | `PredictionService` | `src/model/prediction.py` | Serve predictions via API |
| Backtest Engine | `BacktestEngine` | `src/evaluation/backtesting.py` | Walk-forward backtesting |
| Dashboard | `DashboardApp` | `src/dashboard/app.py` | Visualize results |
| Config Loader | `ConfigLoader` | `src/config/loader.py` | Load/validate YAML config |
| Pipeline Logger | `PipelineLogger` | `src/logging/logger.py` | Structured logging |
| Pipeline Orchestrator | `PipelineOrchestrator` | `src/pipeline/orchestrator.py` | Orchestrate full pipeline |

---

## Appendix B: Cross-Reference to PRD

| PRD Section | Architecture Module |
|-------------|-------------------|
| FR-DI-* (Data Input) | Data Ingestion, Data Validation |
| FR-DS-* (Dataset) | Dataset Builder |
| FR-FE-* (Features) | Feature Engine |
| FR-LG-* (Labels) | Label Engine |
| FR-TM-* (Training) | Training Engine, Model Registry |
| FR-PM-* (Prediction) | Prediction Service |
| FR-BT-* (Backtesting) | Backtest Engine |
| FR-API-* (API) | API (FastAPI) |
| FR-DB-* (Dashboard) | Dashboard |
| NFR-LO-* (Logging) | Pipeline Logger |
| NFR-CF-* (Config) | Config Loader |
| NFR-TE-* (Testing) | Testing Architecture (Section 9) |
