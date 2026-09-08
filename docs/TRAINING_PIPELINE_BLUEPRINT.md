# TRAINING PIPELINE BLUEPRINT — Finance AI MVP

> Reproducible, configuration-driven training and experiment-management system.
> Every training run is traceable, auditable, and designed for fair comparison.

---

## Table of Contents

1. [Primary Objective](#1-primary-objective)
2. [Training Pipeline](#2-training-pipeline)
3. [Experiment Identity](#3-experiment-identity)
4. [Configuration System](#4-configuration-system)
5. [Reproducibility](#5-reproducibility)
6. [Preprocessing](#6-preprocessing)
7. [Hyperparameter Management](#7-hyperparameter-management)
8. [Experiment Types](#8-experiment-types)
9. [Experiment Tracking](#9-experiment-tracking)
10. [Experiment Directory / Artifact Structure](#10-experiment-directory--artifact-structure)
11. [Model Artifact Management](#11-model-artifact-management)
12. [Training Status Lifecycle](#12-training-status-lifecycle)
13. [Failure Handling](#13-failure-handling)
14. [Dataset / Code / Config Compatibility](#14-dataset--code--config-compatibility)
15. [Seed & Randomness](#15-seed--randomness)
16. [Compute Profile](#16-compute-profile)
17. [Metric Policy](#17-metric-policy)
18. [Evaluation Data Separation](#18-evaluation-data-separation)
19. [Experiment Comparability](#19-experiment-comparability)
20. [Model Selection Gate](#20-model-selection-gate)
21. [Research Report](#21-research-report)
22. [Future MLOps Extensions](#22-future-mlops-extensions)
23. [Security & Data Integrity](#23-security--data-integrity)
24. [Testing Strategy](#24-testing-strategy)
25. [Research Questions](#25-research-questions)
26. [Consistency Check](#26-consistency-check)
27. [Deliverables](#27-deliverables)
28. [Acceptance Criteria](#28-acceptance-criteria)
29. [Stop Condition](#29-stop-condition)

---

## 1. Primary Objective

Design a training pipeline that takes a specific dataset version and produces a fully reproducible model-training experiment.

**Core flow:**

```
Dataset Version
      ↓
Training Configuration
      ↓
Preprocessing
      ↓
Model Training
      ↓
Validation
      ↓
Evaluation
      ↓
Artifacts
      ↓
Experiment Record
      ↓
Model Candidate
```

**Every training run must be traceable and reproducible.** A researcher must be able to answer: *"What exact data, code, features, labels, configuration, and dependencies produced this model?"*

---

## 2. Training Pipeline

### 2.1 Complete Lifecycle

The training pipeline executes 15 stages in strict order:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TRAINING PIPELINE — 15 STAGES                        │
│                                                                          │
│  Stage 1: Load dataset metadata                                          │
│    → Read dataset_version, feature_version, label_version               │
│    → Read split boundaries, record counts                                │
│    → Load config_snapshot from dataset metadata                          │
│                                                                          │
│  Stage 2: Verify dataset integrity                                       │
│    → Verify dataset file exists and is readable                         │
│    → Verify SHA-256 hash matches recorded hash                          │
│    → Verify row count matches recorded count                            │
│    → Verify no corruption                                               │
│                                                                          │
│  Stage 3: Verify feature version                                         │
│    → Confirm feature_version matches config expectation                 │
│    → Confirm feature count matches (52 for MVP)                        │
│    → Load feature_names list                                            │
│                                                                          │
│  Stage 4: Verify label version                                           │
│    → Confirm label_version matches config expectation                   │
│    → Confirm label type matches (classification)                        │
│    → Confirm label_window matches (5 for MVP)                          │
│                                                                          │
│  Stage 5: Load training configuration                                    │
│    → Load experiment config (model, hyperparameters, seed)              │
│    → Validate config schema                                             │
│    → Compute config hash                                                │
│                                                                          │
│  Stage 6: Create time-aware train/validation split                       │
│    → Use pre-computed splits from DatasetBuilder                        │
│    → NEVER re-split data — use immutable dataset splits                │
│    → Verify train_end < val_start (no temporal overlap)                 │
│                                                                          │
│  Stage 7: Fit preprocessing only on training data                       │
│    → StandardScaler: fit on X_train only                               │
│    → Encode labels: map UP/DOWN/HOLD → integers                       │
│    → NEVER fit any transformer on validation or test data              │
│    → Persist scaler parameters with experiment                          │
│                                                                          │
│  Stage 8: Train baseline model                                           │
│    → Instantiate model from config                                      │
│    → Set random_seed explicitly                                        │
│    → Fit on (X_train_scaled, y_train_encoded)                          │
│    → Log training duration                                              │
│                                                                          │
│  Stage 9: Generate validation predictions                                │
│    → Apply fitted scaler to X_val (if applicable)                      │
│    → Generate predictions on validation set                            │
│    → Store raw predictions for audit                                    │
│                                                                          │
│  Stage 10: Calculate ML metrics                                          │
│    → Accuracy, precision (per class), recall (per class)               │
│    → F1 score (per class), macro F1                                   │
│    → Confusion matrix                                                  │
│    → ROC-AUC (one-vs-rest for 3-class)                                 │
│                                                                          │
│  Stage 11: Calculate financial evaluation metrics (where applicable)   │
│    → NOT for individual model training                                 │
│    → Computed during backtesting (separate pipeline)                   │
│    → See Section 17: Metric Policy                                     │
│                                                                          │
│  Stage 12: Store artifacts                                               │
│    → Model artifact (.joblib)                                          │
│    → Scaler artifact (.joblib, if applicable)                          │
│    → Metadata JSON                                                     │
│    → Config snapshot JSON                                              │
│    → Predictions file (CSV/Parquet)                                   │
│                                                                          │
│  Stage 13: Store experiment metadata                                     │
│    → Complete ExperimentRecord                                         │
│    → Write to experiment directory                                      │
│    → Update registry index                                              │
│                                                                          │
│  Stage 14: Mark experiment status                                       │
│    → Set status to COMPLETED (or FAILED)                               │
│    → Record completion timestamp                                       │
│                                                                          │
│  Stage 15: Produce reproducible experiment summary                      │
│    → Generate human-readable report                                    │
│    → Include all versions, metrics, configuration                      │
│    → Save alongside artifacts                                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Key Principles

| Principle | Enforcement |
|-----------|-------------|
| **No hidden preprocessing** | Every transformation documented, fitted on train only, persisted |
| **Immutable splits** | Use DatasetBuilder splits; never re-split in training |
| **Fit on train, apply to test** | All preprocessors follow this rule |
| **Deterministic ordering** | Same input → same output given same seed |
| **Failure is loud** | Any stage failure stops pipeline, logs full context |

### 2.3 Pipeline Orchestration

```python
# Conceptual — NOT implementation code

class TrainingPipeline:
    def run(self, dataset_path: str, experiment_config: dict) -> ExperimentRecord:
        metadata = self._load_metadata(dataset_path)         # Stage 1
        self._verify_integrity(metadata)                     # Stage 2
        self._verify_feature_version(metadata)               # Stage 3
        self._verify_label_version(metadata)                 # Stage 4
        config = self._load_config(experiment_config)        # Stage 5
        split = self._load_splits(metadata)                  # Stage 6
        preprocessors = self._fit_preprocessing(split)       # Stage 7
        model = self._train_model(split, config)             # Stage 8
        predictions = self._predict(model, split)            # Stage 9
        ml_metrics = self._compute_ml_metrics(predictions)   # Stage 10
        artifacts = self._save_artifacts(...)                # Stage 12
        record = self._create_experiment_record(...)         # Stage 13
        self._mark_status(record, "COMPLETED")               # Stage 14
        self._generate_report(record)                        # Stage 15
        return record
```

---

## 3. Experiment Identity

### 3.1 Unique Experiment Identifier

Every experiment receives a unique, deterministic identifier:

```
Format: exp_{timestamp}_{model_type_short}_{config_hash_short}

Example: exp_20260904_120000_lr_a1b2c3d
```

**Alternative simpler format for MVP:**

```
Format: exp_{timestamp}

Example: exp_20260904_120000
```

**MVP Decision**: Use timestamp-based ID. Simplicity over cryptographic uniqueness for MVP. Timestamps are sufficient when combined with version metadata.

### 3.2 Required Experiment Metadata

Every experiment record stores:

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `experiment_id` | string | Unique identifier (e.g., "exp_20260904_120000") | Yes |
| `model_type` | string | "logistic_regression" or "random_forest" | Yes |
| `model_version` | string | Model version (e.g., "v1.0.0-20260904") | Yes |
| `dataset_version` | string | Dataset version (e.g., "v0.1") | Yes |
| `feature_version` | string | Feature set version (e.g., "v0.1") | Yes |
| `label_version` | string | Label definition version (e.g., "v0.1") | Yes |
| `config_version` | string | Config hash (SHA-256) | Yes |
| `code_version` | string | Git commit hash (or "unversioned" for MVP) | Yes |
| `random_seed` | integer | Seed used for training | Yes |
| `created_at` | string | ISO timestamp of experiment start | Yes |
| `training_period` | object | {start, end} timestamps | Yes |
| `validation_period` | object | {start, end} timestamps | Yes |
| `environment` | object | Python version, package versions, platform | Yes |

### 3.3 ExperimentRecord Schema

```python
@dataclass
class ExperimentRecord:
    # Identity
    experiment_id: str
    model_type: str                           # "logistic_regression"
    model_version: str                        # "v1.0.0-20260904"
    dataset_version: str                      # "v0.1"
    feature_version: str                      # "v0.1"
    label_version: str                        # "v0.1"
    config_version: str                       # SHA-256 hash
    code_version: str                         # Git commit or "unversioned"
    random_seed: int
    created_at: str                           # ISO timestamp

    # Time periods
    training_period: Dict                     # {"start": "...", "end": "..."}
    validation_period: Dict                   # {"start": "...", "end": "..."}

    # Environment
    environment: Dict                         # Python, packages, platform

    # Configuration
    config_snapshot: Dict                     # Full config used
    hyperparameters: Dict                     # Model-specific params

    # Data
    feature_names: List[str]
    train_rows: int
    val_rows: int

    # Metrics
    train_metrics: Dict[str, float]
    val_metrics: Dict[str, float]
    confusion_matrix: List[List[int]]

    # Artifacts
    artifact_dir: str                         # Path to experiment directory
    model_path: str
    scaler_path: Optional[str]               # None for tree models
    predictions_path: str
    report_path: str

    # Status
    status: str                               # CREATED, RUNNING, COMPLETED, FAILED, INVALIDATED
    completed_at: Optional[str]
    error_message: Optional[str]

    # Notes
    researcher_notes: Optional[str]
```

---

## 4. Configuration System

### 4.1 Configuration Format: YAML

**Decision: YAML for experiment configuration.**

**Rationale:**

| Criterion | YAML | TOML | JSON |
|-----------|------|------|------|
| Human-readable | ✅ Yes | ✅ Yes | ❌ No |
| Supports comments | ✅ Yes | ✅ Yes | ❌ No |
| Git-friendly | ✅ Yes | ✅ Yes | ⚠️ Okay |
| Industry standard for ML configs | ✅ Yes | ⚠️ Growing | ❌ No |
| Ecosystem support | ✅ Excellent | ⚠️ Moderate | ✅ Excellent |

YAML is chosen because:
- Comments enable documentation inline with configuration
- Ubiquitous support in ML ecosystem (Hydra, MLflow, wandb, etc.)
- Easy to diff in Git
- Already used for `config/default.yaml` in this project

### 4.2 Configuration Hierarchy

```
config/
├── default.yaml              ← Base configuration (all settings)
├── experiments/
│   ├── baseline_lr.yaml      ← Experiment-specific override (LR baseline)
│   ├── baseline_rf.yaml      ← Experiment-specific override (RF baseline)
│   ├── feature_ablation.yaml ← Feature comparison experiment
│   └── ...                   ← Additional experiment configs
└── environments/
    ├── local.yaml            ← Local dev overrides (optional)
    └── ...
```

**Rules:**
- `default.yaml` contains all settings with defaults
- Experiment configs override only what they need to change
- Environment configs override for deployment context
- No hardcoded experiment values in source code

### 4.3 Configuration Controls

The configuration system must control:

| Category | Configurable Items |
|----------|-------------------|
| **Dataset** | dataset_version, dataset_path, feature_version, label_version, split_name (train/val/test) |
| **Features** | feature_set, feature_version, feature_filter (optional column subset) |
| **Labels** | label_type, label_window, thresholds, label_version |
| **Horizon** | prediction_horizon (linked to label_window) |
| **Model** | model_type, model_name, hyperparameters |
| **Training** | random_seed, n_jobs, batch_size (for future NN), epochs (for future NN) |
| **Evaluation** | metrics_to_compute, evaluation_period |
| **Output** | artifact_dir, experiment_name, log_level |

### 4.4 Example Experiment Configuration

```yaml
# config/experiments/baseline_lr.yaml

experiment:
  name: "baseline_logistic_regression"
  description: "LR baseline on v0.1 dataset with default features"

dataset:
  version: "v0.1"
  path: "data/processed/datasets/dataset_v0.1"

features:
  version: "v0.1"
  count: 52

labels:
  version: "v0.1"
  type: classification
  window: 5
  thresholds:
    up: 0.01
    down: 0.01

model:
  type: logistic_regression
  params:
    C: 1.0
    penalty: l2
    solver: lbfgs
    max_iter: 1000
    class_weight: balanced

training:
  random_seed: 42
  n_jobs: 1

evaluation:
  metrics:
    - accuracy
    - precision
    - recall
    - f1
    - roc_auc
    - confusion_matrix

output:
  artifact_dir: "models/experiments"
  experiment_id: "exp_20260904_120000"  # Auto-generated if omitted
```

### 4.5 Configuration Validation

At pipeline startup, validate:
- All required fields present
- Dataset version exists and is accessible
- Feature version matches dataset
- Label version matches dataset
- Model type is supported
- Hyperparameters are valid for model type
- Random seed is integer
- Paths are valid

---

## 5. Reproducibility

### 5.1 The Reproducibility Question

A researcher must be able to answer:

> *"What exact data, code, features, labels, configuration, and dependencies produced this model?"*

### 5.2 What Is Recorded

| Layer | Recorded | Storage Location |
|-------|----------|-----------------|
| **Data** | dataset_version (v0.1), source_version, record count, hash | Dataset metadata + experiment record |
| **Features** | feature_version (v0.1), feature names (52), feature hash | Feature metadata + experiment record |
| **Labels** | label_version (v0.1), label type, window, thresholds | Label metadata + experiment record |
| **Code** | Git commit hash (or "unversioned" for MVP) | Experiment record |
| **Config** | Full config snapshot + config hash (SHA-256) | Config snapshot JSON in experiment directory |
| **Dependencies** | Python version, package versions (sklearn, pandas, numpy), platform | Environment metadata in experiment record |
| **Seed** | random_seed value | Experiment record + config snapshot |
| **Parameters** | All hyperparameters, preprocessing params | Config snapshot + hyperparameters field |

### 5.3 Reproducibility Strategy

**Strongest practical reproducibility for MVP:**

1. **Pin dataset version** — always train from a specific dataset_version, never from raw data directly
2. **Pin feature version** — always use a specific feature_version
3. **Pin label version** — always use a specific label_version
4. **Pin config** — save exact config snapshot with every experiment
5. **Pin seed** — always set random_seed explicitly
6. **Record environment** — record Python version, package versions, platform
7. **Record git commit** — record code version (or mark as "unversioned" for MVP without Git)

**Limitation acknowledged:**

Bitwise reproducibility cannot be guaranteed in all cases:
- Random Forest with OpenMP may vary across runs on some platforms
- Some sklearn operations may depend on BLAS/LAPACK implementations
- Floating point non-associativity across different hardware/architectures

**MVP mitigation:**
- Use `n_jobs=1` for Random Forest to maximize determinism
- Record platform information so differences can be investigated
- Accept that "functionally equivalent" (same metrics to 4+ decimal places) is sufficient for MVP

### 5.4 Reproducing an Experiment

To reproduce experiment `exp_20260904_120000`:

```
1. Locate experiment directory: models/experiments/exp_20260904_120000/
2. Read metadata.json → get all versions, config, environment
3. Locate dataset: data/processed/datasets/dataset_v0.1/ (from metadata)
4. Locate features: data/processed/features/features_v0.1.parquet
5. Locate labels: data/processed/labels/labels_v0.1.parquet
6. Read config_snapshot.json → exact config used
7. Check environment requirements → Python version, package versions
8. Run training pipeline with that exact config
9. Compare new metrics to recorded metrics
```

---

## 6. Preprocessing

### 6.1 Golden Rule

> **Fit transformations ONLY on training data. Apply fitted transformations to validation/test data. Never use validation/test distributions to fit preprocessing.**

### 6.2 Preprocessing Rules by Model Type

| Model Type | Scaling Required? | Method | Fit On | Persist |
|------------|------------------|--------|--------|---------|
| **Logistic Regression** | Yes | StandardScaler (mean=0, std=1) | Training data only | Yes — save with model |
| **Random Forest** | No | None | N/A | N/A |
| **Gradient Boosting** | No | None | N/A | N/A |
| **XGBoost / LightGBM** | No | None | N/A | N/A |
| **Neural Networks (future)** | Yes | StandardScaler or MinMaxScaler | Training data only | Yes — save with model |
| **LSTM (future)** | Yes | Per-feature scaling or standardization | Training data only | Yes — save with model |

### 6.3 Label Encoding

| Label | Integer Encoding | One-Hot Encoding |
|-------|-----------------|-----------------|
| UP | 0 | [1, 0, 0] |
| DOWN | 1 | [0, 1, 0] |
| HOLD | 2 | [0, 0, 1] |

**Decision: Use integer encoding for MVP.** Both LR and RF in sklearn handle integer-encoded multi-class targets natively. One-hot encoding would be needed for certain neural network architectures (future).

**Encode on training data only** — fit the label → integer mapping on training labels, apply identically to validation/test.

### 6.4 Preprocessing Metadata

Every experiment stores preprocessing metadata:

```python
@dataclass
class PreprocessingMetadata:
    scaler_type: Optional[str]              # "StandardScaler" or None
    scaler_mean: Optional[np.ndarray]       # Feature means (for LR)
    scaler_std: Optional[np.ndarray]        # Feature stds (for LR)
    label_encoding: Dict[str, int]          # {"UP": 0, "DOWN": 1, "HOLD": 2}
    features_scaled: bool                   # True for LR, False for RF
    features_scaled_list: List[str]         # Which features were scaled
```

---

## 7. Hyperparameter Management

### 7.1 Three-Level Configuration

```
Level 1: Default configuration (config/default.yaml)
  → Provides sensible defaults for every model type
  → Used when no experiment config overrides

Level 2: Experiment-specific override (config/experiments/*.yaml)
  → Overrides only what needs changing
  → Inherits all other values from default

Level 3: Hyperparameter search configuration (future)
  → Defines search space for automated tuning
  → NOT used in MVP
```

### 7.2 Default Configuration (MVP)

```yaml
# config/default.yaml — model defaults

model:
  random_seed: 42
  n_jobs: 1  # Deterministic RF

  defaults:
    logistic_regression:
      C: 1.0
      penalty: l2
      solver: lbfgs
      max_iter: 1000
      class_weight: balanced

    random_forest:
      n_estimators: 100
      max_depth: 10
      min_samples_split: 5
      min_samples_leaf: 2
      class_weight: balanced
      random_state: 42
```

### 7.3 Experiment Override Example

```yaml
# config/experiments/baseline_lr.yaml

model:
  type: logistic_regression
  params:
    C: 0.5          # Override default: stronger regularization
    max_iter: 2000  # Override default: more iterations
    # penalty, solver, class_weight inherited from defaults
```

### 7.4 Hyperparameter Search (Future Only)

**MVP: No automatic hyperparameter optimization.**

**Rationale for restrained MVP strategy:**

| Reason | Explanation |
|--------|-------------|
| **Limited data** | MVP has limited historical data — aggressive tuning risks overfitting to validation set |
| **Simplicity** | Manual configuration is easier to audit and reproduce |
| **Research task** | Hyperparameter tuning strategy is itself a research question |
| **Future** | Can add grid search, random search, or Bayesian optimization in Phase 2+ |

**Future hyperparameter search configuration placeholder:**

```yaml
# Future: hyperparameter search (NOT for MVP)

hyperparameter_search:
  strategy: grid_search  # or random_search, bayesian
  model: random_forest
  param_grid:
    n_estimators: [50, 100, 200]
    max_depth: [5, 10, 15, null]
    min_samples_split: [2, 5, 10]
  cv_folds: 5
  scoring: macro_f1
  n_jobs: 1
  max_combinations: 50  # Limit search budget
```

### 7.5 Hyperparameter Documentation

Every experiment that changes hyperparameters from defaults must document:
- Which parameters were changed
- Why they were changed (research hypothesis)
- What the default was
- What the new value is

---

## 8. Experiment Types

### 8.1 Standard Experiment Categories

| Type | Purpose | What Changes | What Stays Constant | Example |
|------|---------|-------------|---------------------|---------|
| **BASELINE** | Establish first benchmark | Nothing (uses defaults) | Everything | Train LR on v0.1 dataset with default config |
| **FEATURE_COMPARISON** | Test feature set impact | Feature set (subset, addition, removal) | Model, labels, dataset version | Train LR with 26 features vs 52 features |
| **LABEL_COMPARISON** | Test label definition impact | Label window, thresholds, label type | Model, features, dataset version | Compare 5-day vs 10-day horizon |
| **HYPERPARAMETER** | Test hyperparameter impact | Model hyperparameters | Model type, features, labels, dataset | Test C=0.1 vs C=1.0 vs C=10.0 |
| **TIME_WINDOW** | Test temporal robustness | Training/validation time period | Model, features, labels, dataset | Train on 2016-2020, validate on 2021 |
| **MODEL_COMPARISON** | Compare model types | Model type (LR vs RF) | Features, labels, dataset, config | LR vs RF on same dataset |

### 8.2 Experiment Type Metadata

Every experiment records its type:

```python
@dataclass
class ExperimentType:
    category: str                           # BASELINE | FEATURE_COMPARISON | etc.
    hypothesis: str                          # "Smaller feature set will perform similarly"
    changes_from_baseline: List[str]        # What was changed
    changes_description: str                # Human-readable explanation
```

### 8.3 When Comparison Is Valid

| Scenario | Valid Comparison? |
|----------|-------------------|
| Same dataset version, same features, same labels, same evaluation period | ✅ Yes |
| Same dataset version, different feature subsets, same labels, same period | ✅ Yes (feature comparison) |
| Different dataset versions | ❌ No (unless explicitly studying version impact) |
| Different label definitions | ❌ No (unless explicitly studying label impact) |
| Different evaluation periods | ❌ No (unless explicitly studying temporal robustness) |
| Different random seeds | ⚠️ Marginal (seed sensitivity study) |

---

## 9. Experiment Tracking

### 9.1 Tracked Parameters

| Category | Tracked Items |
|----------|---------------|
| **Model parameters** | model_type, model_name, all hyperparameters (C, max_depth, etc.) |
| **Preprocessing parameters** | scaler_type, scaler_params, label_encoding, features_scaled |
| **Dataset settings** | dataset_version, feature_version, label_version, split_name, train_rows, val_rows |
| **Training settings** | random_seed, n_jobs, training_duration_seconds |

### 9.2 Tracked Metrics

#### ML Metrics (per experiment)

| Metric | Type | Description |
|--------|------|-------------|
| `accuracy` | float | Correct predictions / total |
| `precision_UP` | float | TP_UP / (TP_UP + FP_UP) |
| `precision_DOWN` | float | TP_DOWN / (TP_DOWN + FP_DOWN) |
| `precision_HOLD` | float | TP_HOLD / (TP_HOLD + FP_HOLD) |
| `recall_UP` | float | TP_UP / (TP_UP + FN_UP) |
| `recall_DOWN` | float | TP_DOWN / (TP_DOWN + FN_DOWN) |
| `recall_HOLD` | float | TP_HOLD / (TP_HOLD + FN_HOLD) |
| `f1_UP` | float | 2 × P × R / (P + R) for UP |
| `f1_DOWN` | float | 2 × P × R / (P + R) for DOWN |
| `f1_HOLD` | float | 2 × P × R / (P + R) for HOLD |
| `macro_f1` | float | Mean of per-class F1 scores |
| `roc_auc_UP` | float | One-vs-rest ROC AUC for UP |
| `roc_auc_DOWN` | float | One-vs-rest ROC AUC for DOWN |
| `roc_auc_HOLD` | float | One-vs-rest ROC AUC for HOLD |
| `macro_roc_auc` | float | Mean of per-class ROC AUC |
| `confusion_matrix` | 3×3 matrix | [[TP_UP, FP_UP_to_DOWN, FP_UP_to_HOLD], ...] |

#### Financial Metrics (NOT during model training — during backtesting)

See Section 17: Metric Policy.

### 9.3 Tracked Artifacts

| Artifact | Format | Description |
|----------|--------|-------------|
| `model.joblib` | binary | Serialized sklearn estimator |
| `scaler.joblib` | binary | Fitted StandardScaler (LR only) |
| `metadata.json` | JSON | ExperimentRecord as JSON |
| `config_snapshot.json` | JSON | Exact config used |
| `predictions.csv` | CSV | Validation predictions with timestamps |
| `confusion_matrix.csv` | CSV | Confusion matrix as table |
| `report.md` | Markdown | Human-readable experiment report |
| `feature_importance.csv` | CSV | Feature importance (RF only, if available) |

### 9.4 Tracking Storage

```
models/
├── experiments/
│   ├── exp_20260904_120000/
│   │   ├── config/
│   │   │   └── config_snapshot.json
│   │   ├── metrics/
│   │   │   ├── ml_metrics.json
│   │   │   └── confusion_matrix.csv
│   │   ├── model/
│   │   │   ├── model.joblib
│   │   │   └── scaler.joblib          # (LR only)
│   │   ├── predictions/
│   │   │   └── val_predictions.csv
│   │   ├── reports/
│   │   │   └── report.md
│   │   └── metadata/
│   │       └── metadata.json
│   ├── exp_20260904_140000/
│   │   └── ...
│   └── index.json                      # Experiment index (list of all experiments)
├── registry/
│   └── registry.json                   # Active model pointer (simple MVP)
```

---

## 10. Experiment Directory / Artifact Structure

### 10.1 Chosen Structure

```
experiments/
  {experiment_id}/
    config/
      config_snapshot.json        ← Exact configuration used
    metrics/
      ml_metrics.json             ← All ML metrics (JSON)
      confusion_matrix.csv        ← Confusion matrix (CSV)
      feature_importance.csv      ← Feature importance (RF only)
    model/
      model.joblib                ← Serialized model
      scaler.joblib               ← Fitted scaler (LR only, omitted for RF)
    predictions/
      val_predictions.csv         ← Validation set predictions
    reports/
      report.md                   ← Human-readable experiment report
    metadata/
      metadata.json               ← Full ExperimentRecord
    README.md                     ← Quick reference (auto-generated)
```

### 10.2 Justification

| Design Choice | Rationale |
|---------------|-----------|
| **Separate subdirectories by artifact type** | Clear organization, easier to find specific artifacts, scales well as experiments accumulate |
| **config_snapshot.json in config/** | Configuration is the root of reproducibility — easy to locate |
| **ml_metrics.json in metrics/** | Machine-readable metrics separate from human-readable report |
| **model.joblib in model/** | Model artifact is the primary deliverable — prominent location |
| **scaler.joblib alongside model/** | Preprocessing is part of the model artifact — keep together |
| **val_predictions.csv in predictions/** | Raw predictions enable re-evaluation and audit |
| **report.md in reports/** | Human-readable summary separate from machine-readable metadata |
| **metadata.json in metadata/** | Complete machine-readable record of everything |
| **README.md at root of experiment** | Quick reference when browsing directory |

### 10.3 What Is NOT Stored

| Item | Reason |
|------|--------|
| Raw training data | Too large, dataset is immutable and versioned separately |
| Feature matrix (X_train, X_val) | Too large, reproducible from dataset + features |
| Intermediate computation results | Not needed for reproducibility or audit |
| Log files | Handled by structlog system, not in experiment directory |
| Temporary files | Cleaned up after experiment completes |

---

## 11. Model Artifact Management

### 11.1 Minimum Artifacts Per Experiment

When training finishes successfully, these MUST be saved:

| Artifact | Format | Required |
|----------|--------|----------|
| Model artifact | `.joblib` | Yes |
| Model metadata | `.json` (part of metadata.json) | Yes |
| Feature version | string in metadata | Yes |
| Label version | string in metadata | Yes |
| Dataset version | string in metadata | Yes |
| Configuration snapshot | `.json` | Yes |
| Training timestamp | ISO string in metadata | Yes |
| Metrics | `.json` in metrics/ | Yes |
| Git commit | string in metadata | Yes (or "unversioned") |
| Random seed | integer in metadata | Yes |

### 11.2 Model Metadata Schema

```python
@dataclass
class ModelArtifactMetadata:
    # Identity
    experiment_id: str
    model_version: str
    model_type: str

    # Source versions
    dataset_version: str
    feature_version: str
    label_version: str
    config_version: str
    code_version: str

    # Training context
    random_seed: int
    training_start: str
    training_end: str
    training_duration_seconds: float

    # Data
    train_rows: int
    val_rows: int
    feature_names: List[str]

    # Performance
    val_metrics: Dict[str, float]
    train_metrics: Dict[str, float]

    # Artifacts
    model_filename: str
    scaler_filename: Optional[str]

    # Status
    status: str
    created_at: str
```

### 11.3 Model Registry Boundary (MVP)

**MVP: Simple JSON-based registry. No full model registry implementation.**

The architectural boundary is defined:

```python
# Abstract interface — defines the contract for a future model registry

class ModelRegistry(Protocol):
    def register(self, model_metadata: ModelArtifactMetadata, artifact_path: str) -> str:
        """Register a new model artifact. Returns registry ID."""
        ...

    def get(self, model_version: str) -> Optional[ModelArtifactMetadata]:
        """Get metadata for a specific model version."""
        ...

    def list(self, limit: int = 10, offset: int = 0) -> List[ModelArtifactMetadata]:
        """List registered models."""
        ...

    def get_active(self) -> Optional[ModelArtifactMetadata]:
        """Get the currently active model."""
        ...

    def set_active(self, model_version: str) -> None:
        """Set a model as the active model."""
        ...

    def archive(self, model_version: str) -> None:
        """Archive a model (soft delete, keep artifacts)."""
        ...
```

**MVP Implementation:** File-based JSON registry in `models/registry/registry.json`. Future phases can implement database-backed registry without changing the interface.

---

## 12. Training Status Lifecycle

### 12.1 Status Values

| Status | Meaning | Can Transition To |
|--------|---------|-------------------|
| `CREATED` | Experiment record created, pipeline not started | RUNNING |
| `RUNNING` | Pipeline executing | COMPLETED, FAILED |
| `COMPLETED` | Pipeline finished successfully, all artifacts saved | INVALIDATED |
| `FAILED` | Pipeline failed at some stage, no valid model produced | None (terminal) |
| `INVALIDATED` | Previously COMPLETED, later found to be invalid (bad data, wrong config, etc.) | None (terminal) |

### 12.2 Transition Rules

```
CREATED ──▶ RUNNING ──▶ COMPLETED
                        │
                        ▼
                      FAILED

COMPLETED ──▶ INVALIDATED  (manual or automated invalidation)
```

**Rules:**
- `CREATED` → `RUNNING`: Pipeline starts execution
- `RUNNING` → `COMPLETED`: All stages complete, all artifacts saved, validation passes
- `RUNNING` → `FAILED`: Any stage fails, error logged, no valid model produced
- `COMPLETED` → `INVALIDATED`: Post-hoc discovery of invalid data, configuration error, version mismatch, or reproducibility failure

### 12.3 Terminal States

- **FAILED**: Cannot become anything else. A new experiment must be created.
- **INVALIDATED**: Cannot become anything else. The artifacts may be retained for audit but must not be treated as valid model candidates.

### 12.4 Status Enforcement

| Status | Can Be Used for Prediction? | Can Be Used for Backtesting? | Can Be Compared to Other Experiments? |
|--------|----------------------------|------------------------------|---------------------------------------|
| CREATED | No | No | No |
| RUNNING | No | No | No |
| COMPLETED | Yes (if passed gate) | Yes (if passed gate) | Yes |
| FAILED | No | No | No |
| INVALIDATED | No | No | No (unless studying failure) |

---

## 13. Failure Handling

### 13.1 Failure Categories

| Failure | Detection | Handling | Logged? |
|---------|-----------|----------|---------|
| **Dataset missing** | File not found at dataset_path | Abort immediately, log error | Yes — ERROR |
| **Dataset corrupted** | SHA-256 hash mismatch, unreadable file | Abort, log which hash mismatched | Yes — ERROR |
| **Schema mismatch** | Expected columns missing, wrong types | Abort, log expected vs actual schema | Yes — ERROR |
| **Feature version mismatch** | dataset.feature_version != config.feature_version | Abort, log expected vs actual | Yes — ERROR |
| **Label version mismatch** | dataset.label_version != config.label_version | Abort, log expected vs actual | Yes — ERROR |
| **Insufficient rows** | train_rows < minimum (100), val_rows < minimum (20) | Abort, log row counts | Yes — ERROR |
| **NaN/Inf values** | NaN or Inf found in features after loading | Abort, log which features affected | Yes — ERROR |
| **Training failure** | Model.fit() raises exception | Abort, log exception traceback | Yes — ERROR |
| **Non-convergence** | LR warning: max_iter reached without convergence | Log warning, continue with flag in metadata | Yes — WARNING |
| **Interrupted process** | KeyboardInterrupt, SIGTERM, OOM kill | Log partial state, mark FAILED, clean up partial artifacts | Yes — ERROR |
| **Artifact write failure** | Cannot write model.joblib, disk full, permission denied | Abort, log which artifact failed | Yes — ERROR |
| **Invalid configuration** | Missing required fields, invalid values | Abort before pipeline starts, log validation errors | Yes — ERROR |

### 13.2 Failure Response

```
For every failure:
1. Log full error context (stage, config, versions, error message, traceback)
2. Set experiment status to FAILED
3. Do NOT save any artifacts (model, scaler, etc.)
4. Do NOT update registry
5. Write failure metadata (error type, stage, message)
6. Exit with non-zero code (for CLI pipeline)
```

### 13.3 Partial State Cleanup

| Scenario | Cleanup Action |
|----------|---------------|
| Failed during training (model not saved) | No cleanup needed — no artifacts created |
| Failed during artifact save (model saved, scaler not saved) | Keep model artifact but mark experiment FAILED — do NOT register |
| Interrupted during training | Delete any partial model files if possible; if not, leave and mark FAILED |
| Failed before any artifacts | No cleanup needed |

**Rule:** A partial artifact set never represents a valid model. The experiment status reflects this.

---

## 14. Dataset / Code / Config Compatibility

### 14.1 Version Compatibility Matrix

Before training, the pipeline verifies:

```
dataset_version: v0.3
feature_version: v0.2
label_version: v0.1
config_version: v0.4
code_version:   git:a1b2c3d
```

**Compatibility checks:**

| Check | Rule | Fail Action |
|-------|------|-------------|
| **Dataset ↔ Features** | dataset.feature_version must match config.feature_version | Abort — version mismatch error |
| **Dataset ↔ Labels** | dataset.label_version must match config.label_version | Abort — version mismatch error |
| **Dataset ↔ Config** | dataset version must be accessible at dataset_path | Abort — dataset not found error |
| **Code ↔ Config** | config must be valid for the current code version | Warn if code_version is "unversioned" |
| **Features ↔ Labels** | feature_version and label_version must have been generated from the same dataset_version | Warn if dataset versions differ |
| **Self-consistency** | config must reference valid versions that exist in the system | Abort — version not found error |

### 14.2 Compatibility Verification Algorithm

```python
def verify_compatibility(dataset_metadata: dict, config: dict, code_version: str) -> CompatibilityResult:
    issues = []

    # Check 1: Feature version matches
    if dataset_metadata["feature_version"] != config["features"]["version"]:
        issues.append(f"Feature version mismatch: dataset={dataset_metadata['feature_version']}, config={config['features']['version']}")

    # Check 2: Label version matches
    if dataset_metadata["label_version"] != config["labels"]["version"]:
        issues.append(f"Label version mismatch: dataset={dataset_metadata['label_version']}, config={config['labels']['version']}")

    # Check 3: Dataset accessible
    dataset_path = config["dataset"]["path"]
    if not os.path.exists(dataset_path):
        issues.append(f"Dataset not found: {dataset_path}")

    # Check 4: Config references valid versions
    for version_ref in [config["dataset"]["version"], config["features"]["version"], config["labels"]["version"]]:
        if not version_exists(version_ref):
            issues.append(f"Version not found: {version_ref}")

    # Check 5: Code version
    if code_version == "unversioned":
        issues.append("Warning: code is unversioned — reproducibility not guaranteed")

    return CompatibilityResult(passed=len(issues) == 0, issues=issues)
```

### 14.3 Version Compatibility Policy

| Scenario | Policy |
|----------|--------|
| All versions match | ✅ Proceed with training |
| Feature version mismatch | ❌ Abort — features may not align with dataset |
| Label version mismatch | ❌ Abort — labels may not align with dataset |
| Dataset version not found | ❌ Abort — cannot train without dataset |
| Code unversioned | ⚠️ Warn — reproducibility limited, proceed with caution |
| Feature and label from different datasets | ⚠️ Warn — investigate before proceeding |

---

## 15. Seed & Randomness

### 15.1 Randomness Policy

Every experiment specifies:

| Item | Value | Source |
|------|-------|--------|
| **Random seed** | 42 (default) | config.default.yaml → model.random_seed |
| **Model random_state** | Same as random_seed | Passed to model constructor |
| **Train/test split** | Pre-computed by DatasetBuilder (deterministic) | No randomness in training |
| **Label shuffling** | None | Labels are time-ordered, never shuffled |
| **Feature computation** | Deterministic (per FE blueprint) | No randomness |

### 15.2 Deterministic Settings

| Component | Setting for Determinism |
|-----------|------------------------|
| **Logistic Regression** | `random_state` not needed (LR is deterministic with fixed solver) |
| **Random Forest** | `random_state=42`, `n_jobs=1` |
| **Train/validation split** | Pre-computed, immutable dataset splits |
| **Preprocessing** | Deterministic transformations |
| **Label encoding** | Deterministic mapping |

### 15.3 Sources of Non-Determinism

| Source | Impact | Mitigation |
|--------|--------|------------|
| **Random Forest multi-threading** | Non-deterministic with `n_jobs > 1` | Use `n_jobs=1` for MVP |
| **Floating point order** | Tiny differences across hardware/BLAS | Accept "functionally equivalent" results |
| **Python hash randomization** | dict ordering may vary | Not impactful for sklearn training |
| **GPU operations (future)** | Non-deterministic by nature | Document as limitation for future NN models |
| **Unversioned code** | Code changes not tracked | Mark as "unversioned" in experiment record |

### 15.4 Seed Documentation

Every experiment record includes:
- `random_seed`: The seed value used
- `n_jobs`: Parallelism setting (affects RF determinism)
- `code_version`: Git commit or "unversioned"

**Reproducibility expectation for MVP:**
With the same dataset version, feature version, label version, config, seed, and code version, the experiment should produce **functionally equivalent** results (metrics matching to at least 4 decimal places).

---

## 16. Compute Profile

### 16.1 MVP Compute Strategy

**Goal:** Run baseline experiments on a developer machine without requiring distributed infrastructure.

| Resource | MVP Requirement |
|----------|----------------|
| **CPU** | Single machine, 4+ cores sufficient |
| **RAM** | 8GB minimum, 16GB comfortable |
| **Disk** | Feature matrix ~50MB, model artifacts ~1MB each |
| **GPU** | Not required for MVP (LR + RF are CPU-only) |
| **Network** | Not required (all data local) |
| **Distributed** | Not required |

### 16.2 Expected Training Times (MVP)

| Model | Dataset Size | Expected Time |
|-------|-------------|---------------|
| Logistic Regression | 2,500 rows × 52 features | < 1 second |
| Random Forest | 2,500 rows × 52 features | < 10 seconds |

### 16.3 Future Extension Points

| Capability | Future Consideration | MVP Status |
|------------|---------------------|------------|
| **GPU training** | For neural networks (LSTM, Transformer) | Not applicable to MVP |
| **Distributed training** | For large datasets (100K+ rows, 100+ tickers) | Not needed for MVP |
| **Remote workers** | For running experiments on cloud/cluster | Not needed for MVP |
| **Hyperparameter search** | Grid/random search may benefit from parallelism | Future research task |

### 16.4 Compute Profile Recording

Every experiment records compute context:

```python
@dataclass
class ComputeProfile:
    platform: str                    # "Linux-5.15.0-x86_64"
    cpu_count: int                   # Logical CPU count
    ram_gb: float                    # Approximate available RAM
    python_version: str              # "3.10.12"
    sklearn_version: str             # "1.3.2"
    numpy_version: str               # "1.24.3"
    pandas_version: str              # "2.0.3"
    training_duration_seconds: float
    n_jobs: int                      # Parallelism used
```

---

## 17. Metric Policy

### 17.1 Critical Distinction

> **A high classification score does NOT automatically imply a profitable trading strategy.**

ML metrics measure prediction quality. Financial metrics measure economic outcomes. They are related but not equivalent. A model with 60% accuracy may still lose money after transaction costs. A model with 52% accuracy may be profitable with low turnover and favorable risk-reward.

### 17.2 ML Metrics (Model Training Evaluation)

Computed during model training, on validation set:

| Metric | Category | When to Use |
|--------|---------|-------------|
| **Accuracy** | Classification | Overall correctness |
| **Precision (per class)** | Classification | When false positives are costly |
| **Recall (per class)** | Classification | When false negatives are costly |
| **F1 (per class)** | Classification | Balance of precision and recall |
| **Macro F1** | Classification | Overall performance across imbalanced classes |
| **ROC-AUC (per class, one-vs-rest)** | Classification | Ranking quality, threshold-independent |
| **Macro ROC-AUC** | Classification | Overall ranking quality |
| **Confusion Matrix** | Classification | Detailed error analysis |

### 17.3 Financial Metrics (Backtesting Evaluation)

Computed during backtesting (separate pipeline), NOT during model training:

| Metric | Description | When to Use |
|--------|-------------|-------------|
| **Cumulative Return** | Total return over backtest period | Overall profitability |
| **Annualized Return** | Geometric mean return annualized | Comparison across periods |
| **Sharpe Ratio** | (Return - Risk Free) / Std(Return) | Risk-adjusted return |
| **Sortino Ratio** | (Return - Risk Free) / Downside Deviation | Risk-adjusted (only downside volatility) |
| **Maximum Drawdown** | Largest peak-to-trough decline | Worst-case risk |
| **Win Rate** | Winning trades / total trades | Trade-level success rate |
| **Profit Factor** | Gross profit / gross loss | Profitability per unit of loss |
| **Turnover** | Average position changes per period | Trading frequency |
| **Transaction-Cost-Adjusted Return** | Return minus estimated costs | Realistic profitability |
| **Trade Count** | Total number of trades executed | Activity level |

### 17.4 Metric Separation Enforcement

| Stage | Metrics Computed | Metrics NOT Computed |
|-------|-----------------|---------------------|
| **Model Training** | ML metrics (accuracy, precision, recall, F1, ROC-AUC) | Financial metrics |
| **Backtesting** | Financial metrics (Sharpe, drawdown, win rate) + ML metrics (for reference) | None — full evaluation |
| **Prediction Serving** | Confidence scores | Neither ML nor financial metrics |

**Rule:** Model training pipeline produces ML metrics only. Backtesting pipeline produces financial metrics. They are separate pipelines with separate responsibilities.

---

## 18. Evaluation Data Separation

### 18.1 Three-Way Split Policy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    EVALUATION DATA SEPARATION                            │
│                                                                          │
│  Training Data (70%)                                                     │
│    ├── Used for: Fitting model parameters                               │
│    ├── Used for: Fitting preprocessing (scaler, encoders)              │
│    └── NEVER used for: Model selection, threshold tuning               │
│                                                                          │
│  Validation Data (15%)                                                   │
│    ├── Used for: Model/configuration selection                         │
│    ├── Used for: Hyperparameter comparison                             │
│    ├── Used for: Feature comparison                                    │
│    └── NEVER used for: Final evaluation, reporting as "test results"   │
│                                                                          │
│  Test Data (15%)                                                         │
│    ├── Used for: Final out-of-sample evaluation                        │
│    ├── Used for: Final reporting                                      │
│    ├── Used for: Backtesting                                          │
│    └── NEVER used for: Feature selection, threshold tuning,            │
│                         hyperparameter optimization, model selection    │
│                                                                          │
│  ────────────────────────────────────────────────────────────────────  │
│                                                                          │
│  CRITICAL: Once the test set is touched for evaluation, it becomes      │
│  "used" and cannot be used as a fresh test set for that experiment.     │
│  Create new dataset versions to get fresh test sets.                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 18.2 What Each Set Is Used For

| Activity | Training | Validation | Test |
|----------|----------|------------|------|
| Fit model parameters | ✅ | ❌ | ❌ |
| Fit preprocessing | ✅ | ❌ | ❌ |
| Compute training metrics | ✅ | ❌ | ❌ |
| Model selection | ❌ | ✅ | ❌ |
| Hyperparameter tuning | ❌ | ✅ | ❌ |
| Feature selection | ❌ | ✅ | ❌ |
| Threshold tuning | ❌ | ✅ | ❌ |
| Compare experiments | ❌ | ✅ | ❌ |
| Final model evaluation | ❌ | ❌ | ✅ |
| Backtesting | ❌ | ❌ | ✅ |
| Report "test results" | ❌ | ❌ | ✅ |
| Publication / presentation | ❌ | ❌ | ✅ |

### 18.3 Test Set Protection

**Rules:**
1. Test set is created once by DatasetBuilder and never modified
2. Test set is NOT used during any model development activity
3. Test set metrics are computed only once (at final evaluation)
4. If test set metrics are examined and the model is changed, a new test set is needed
5. Test set use is recorded in experiment metadata (timestamp of first evaluation)

**Enforcement:** The training pipeline receives pre-computed splits from DatasetBuilder. It does NOT re-split data. This architectural constraint enforces the separation.

---

## 19. Experiment Comparability

### 19.1 Fair Comparison Rules

Two experiments can be fairly compared only when:

| Condition | Required For Fair Comparison |
|-----------|------------------------------|
| **Same evaluation period** | Validation (or test) timestamps must match exactly |
| **Same label definition** | label_version, label_window, thresholds must match |
| **Same cost assumptions** | When comparing financial metrics, cost model must match |
| **Same dataset version** | Unless the experiment's purpose is to compare dataset versions |
| **Same feature set** | Unless the experiment's purpose is to compare feature sets |
| **Same metric definitions** | All metrics computed identically (same sklearn functions, same parameters) |
| **Same preprocessing** | Same scaler, same label encoding, same feature filtering |
| **Same random seed** | For comparing non-deterministic models (RF), same seed ensures comparability |

### 19.2 When Comparison Is Invalid

| Scenario | Why Invalid | What to Do |
|----------|-------------|-----------|
| Different validation periods | Temporal regimes may differ | Align periods or acknowledge regime difference |
| Different label windows (5-day vs 10-day) | Different prediction problems | Compare only within same label definition |
| Different dataset versions | Different data, features, labels | Compare only within same dataset version |
| Different metric computation | Numbers are not comparable | Standardize metric computation code |
| Different random seeds for RF | Results may differ due to randomness | Use same seed or average multiple seeds |
| One experiment tuned on validation, other didn't | Information leakage advantage | Acknowledge or use fresh validation |
| Test set used for model selection in one experiment | Test set contamination | Reject comparison — test set is compromised |

### 19.3 Comparability Metadata

Every experiment records what it can be fairly compared to:

```python
@dataclass
class Comparability:
    can_compare_to: List[str]             # Experiment IDs that are fair comparisons
    comparison_constraints: List[str]     # Conditions that must hold for comparison
    cannot_compare_to: List[str]          # Experiment IDs that are NOT fair comparisons
    reason: str                            # Why constraints exist
```

**Example:**
```json
{
  "can_compare_to": ["exp_20260904_140000"],
  "comparison_constraints": [
    "Same validation period: 2023-01-01 to 2023-12-31",
    "Same label_version: v0.1",
    "Same random_seed: 42"
  ],
  "cannot_compare_to": ["exp_20260904_160000"],
  "reason": "exp_20260904_160000 uses different label window (10 days vs 5 days)"
}
```

---

## 20. Model Selection Gate

### 20.1 Model Selection Process (Future-Compatible)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       MODEL SELECTION GATE                               │
│                                                                          │
│  Candidate Model                                                         │
│    │                                                                     │
│    ▼                                                                     │
│  ┌─────────────────────────┐                                            │
│  │ 1. VALIDATION CHECK     │                                            │
│  │    - Model trained?     │                                            │
│  │    - Status = COMPLETED?│                                            │
│  │    - All artifacts present?                                │         │
│  └────────────┬────────────┘                                            │
│               │ PASS                                                      │
│               ▼                                                          │
│  ┌─────────────────────────┐                                            │
│  │ 2. QUALITY CHECKS       │                                            │
│  │    - Validation accuracy > random baseline?                        │
│  │    - Per-class metrics acceptable?                                │
│  │    - No signs of severe overfitting?                             │
│  │    - Label distribution not degenerate?                           │
│  └────────────┬────────────┘                                            │
│               │ PASS                                                      │
│               ▼                                                          │
│  ┌─────────────────────────┐                                            │
│  │ 3. BASELINE COMPARISON  │                                            │
│  │    - Better than LR baseline?                                    │
│  │    - Better than random (33% per class)?                         │
│  │    - Statistical significance considered?                        │
│  └────────────┬────────────┘                                            │
│               │ PASS                                                      │
│               ▼                                                          │
│  ┌─────────────────────────┐                                            │
│  │ 4. FINANCIAL EVALUATION │                                            │
│  │    - Backtest on test set                                      │
│  │    - Sharpe > 0?                                               │
│  │    - Drawdown acceptable?                                      │
│  │    - Transaction costs applied?                                │
│  └────────────┬────────────┘                                            │
│               │ PASS                                                      │
│               ▼                                                          │
│  ┌─────────────────────────┐                                            │
│  │ 5. DECISION             │                                            │
│  │    - PASS: Candidate becomes model candidate                     │
│  │    - REJECT: Document reasons, keep for research                │
│  │    - Needs more data: Queue for retest                          │
│  └─────────────────────────┘                                            │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 20.2 Gate Criteria (MVP — Guidelines Only)

| Gate | Criterion | MVP Threshold |
|------|-----------|---------------|
| **Validation Check** | Status == COMPLETED, artifacts present | Must pass |
| **Quality Check** | Validation accuracy > 33% (random baseline for 3-class) | Soft guideline |
| **Baseline Comparison** | Better than LR baseline on same data | Soft guideline |
| **Financial Evaluation** | Not performed during training — done in backtesting | Separate pipeline |

**Important:** These are guidelines for MVP, not hard gates. The MVP goal is to establish the pipeline and produce initial baselines. Formal model selection with statistical testing comes in Phase 2+.

### 20.3 Gate Outcomes

| Outcome | Meaning | Action |
|--------|---------|--------|
| **PASS** | Model passes all gates | Mark as model candidate, make available for backtesting |
| **REJECT** | Model fails one or more gates | Document reasons, retain artifacts for research, do NOT use for predictions |
| **INCONCLUSIVE** | Not enough evidence to decide | Retain for further study, may retest with more data |
| **NEEDS_MORE_DATA** | Insufficient data to evaluate | Queue for retest when more data available |

### 20.4 No Automatic Deployment

> **No model becomes "production" merely because it has the highest single metric.**

Model selection requires:
- Multiple metrics considered together
- Financial evaluation (backtesting)
- Human review and approval
- Documentation of trade-offs

The gate produces a *candidate*, not a *deployment*. Deployment is a separate decision.

---

## 21. Research Report

### 21.1 Required Report Contents

Every completed experiment produces a research report containing:

| Section | Content |
|---------|---------|
| **Objective** | What this experiment aims to learn |
| **Hypothesis** | Expected outcome and reasoning |
| **Dataset** | Dataset version, date range, record counts, source |
| **Features** | Feature version, feature count, feature list (or subset) |
| **Labels** | Label version, label type, window, thresholds, class distribution |
| **Model** | Model type, model version, hyperparameters (full list) |
| **Configuration** | Full config snapshot reference, random seed, training settings |
| **Results** | All ML metrics (train + val), confusion matrix, per-class breakdown |
| **Comparison** | Comparison to baseline (if applicable), comparison to related experiments |
| **Limitations** | Data limitations, regime limitations, generalization concerns |
| **Conclusion** | What was learned, whether hypothesis was supported, next steps |

### 21.2 Report Format

Two formats produced:

1. **Machine-readable**: `metrics/ml_metrics.json` — all numbers in structured JSON
2. **Human-readable**: `reports/report.md` — Markdown report with narrative

### 21.3 Example Report Structure

```markdown
# Experiment Report: exp_20260904_120000

**Status:** COMPLETED
**Model:** Logistic Regression v1.0.0-20260904
**Dataset:** v0.1 (2016-01-01 to 2025-12-31)
**Features:** v0.1 (52 features)
**Labels:** v0.1 (classification, 5-day horizon, ±1% thresholds)

## Objective

Establish first ML baseline for direction classification.

## Hypothesis

A simple logistic regression model will achieve accuracy above random baseline (33% for 3-class) on validation data.

## Results

### Training Set (2016-01-01 to 2022-12-31, 1,725 rows)
- Accuracy: 0.54
- Macro F1: 0.53

### Validation Set (2023-01-01 to 2023-12-31, 370 rows)
- Accuracy: 0.52
- Macro F1: 0.51
- Precision (UP): 0.55, Recall (UP): 0.50
- Precision (DOWN): 0.50, Recall (DOWN): 0.48
- Precision (HOLD): 0.52, Recall (HOLD): 0.55

### Confusion Matrix (Validation)
              Pred_UP  Pred_DOWN  Pred_HOLD
Actual_UP      62        28         35
Actual_DOWN    31        55         39
Actual_HOLD    29        33         90

## Comparison

- vs Random baseline (33% per class): ✅ Better
- vs LR baseline (this experiment IS the baseline): N/A

## Limitations

- Single dataset version, single time period
- No financial evaluation (backtesting required)
- Classification metrics do not imply profitability

## Conclusion

Hypothesis supported: LR achieves 52% validation accuracy, above random baseline. This establishes a floor for future model comparisons. Financial evaluation required before any claims about trading utility.
```

### 21.4 Unsupported Claims prohibition

Reports MUST NOT contain claims such as:

| Prohibited Claim | Why Prohibited |
|-----------------|----------------|
| "AI is profitable" | Financial metrics not computed at training stage |
| "Model predicts market direction" | Classification accuracy ≠ trading profitability |
| "Strategy returns X%" | No backtesting performed |
| "Beat the market" | No benchmark comparison performed |
| "Ready for live trading" | No production validation performed |

**Acceptable claims (if supported by evidence):**
- "Model achieves X% validation accuracy"
- "Model outperforms random baseline by Y percentage points"
- "Model shows signal above random chance on this dataset"

---

## 22. Future MLOps Extensions

### 22.1 Reserved Architecture

The following capabilities are reserved for future phases. The current architecture provides extension points but does NOT implement them.

| Capability | Future Tool/Approach | Current State |
|------------|---------------------|---------------|
| **Experiment tracking** | MLflow, Weights & Biases, Neptune | JSON files + directory structure (MVP) |
| **Model registry** | MLflow Model Registry, database-backed registry | JSON-based registry (MVP) |
| **Automated retraining** | Airflow, Prefect, cron + pipeline triggers | Manual trigger only (MVP) |
| **Model promotion** | Approval workflow, staged deployment | Manual decision (MVP) |
| **Drift detection** | Feature drift, label drift, performance drift monitoring | Not implemented (future) |
| **Feature store** | Feast, custom feature store | File-based features (MVP) |
| **Distributed training** | Spark, Ray, Dask, cloud ML platforms | Single-machine only (MVP) |
| **A/B testing** | Shadow deployment, traffic splitting | Not applicable (MVP is prediction-only) |
| **Model monitoring** | Performance dashboards, alerting | Not implemented (future) |
| **Pipeline orchestration** | Airflow, Prefect, Dagster | Sequential script execution (MVP) |

### 22.2 Extension Point Design

| Extension | What Changes | What Stays |
|-----------|-------------|------------|
| **MLflow tracking** | Replace JSON logging with MLflow API calls | ExperimentRecord schema, artifact structure |
| **Database registry** | Replace JSON registry with database queries | ModelRegistry Protocol interface |
| **Automated retraining** | Add scheduler/trigger to pipeline | TrainingPipeline, experiment structure |
| **Feature store** | Replace file-based features with store queries | Feature versioning, feature contract |
| **Distributed training** | Add distributed execution layer | Reproducibility, experiment tracking |

**Rule:** Extension points are designed so that future implementations can replace MVP components without rewriting the core training logic.

---

## 23. Security & Data Integrity

### 23.1 Security Requirements

| Requirement | Enforcement |
|-------------|-------------|
| **No secrets in experiment artifacts** | Experiment directories contain only model artifacts, metrics, config, metadata — no API keys, passwords, tokens |
| **No credentials in configs** | config/*.yaml files must not contain credentials; use environment variables for any secrets |
| **No accidental raw sensitive files** | Experiment directory creation validated to prevent copying sensitive files |
| **Immutable dataset references** | Dataset version pinned in experiment config; dataset files are read-only after creation |
| **Model artifacts traceable to source** | Every model artifact's metadata.json references dataset_version, feature_version, label_version, config_version, code_version |

### 23.2 Data Integrity Checks

| Check | When | Action if Failed |
|-------|------|-----------------|
| **Dataset hash verification** | Before training starts | Abort — dataset may be corrupted |
| **Artifact write verification** | After saving each artifact | Retry or abort — log failure |
| **Metadata completeness check** | After experiment completes | Mark as INCOMPLETE — do not register |
| **Version consistency check** | Before training starts | Abort — version mismatch |

### 23.3 Artifact Integrity

```
For every artifact saved:
1. Write to temporary file first
2. Verify file written correctly (size > 0, readable)
3. Atomically rename to final path
4. Record artifact hash in metadata
5. Verify hash matches on load (future)
```

---

## 24. Testing Strategy

### 24.1 Required Test Categories

| Test Category | What It Tests | Example |
|---------------|--------------|---------|
| **Configuration validation** | Config schema, required fields, value ranges | Invalid config → clear error before training starts |
| **Dataset compatibility** | Version matching, file existence, hash verification | Version mismatch → abort with clear error |
| **Preprocessing leakage** | Scaler fitted on train only, applied to test | Verify scaler parameters from train only, test transformation uses same params |
| **Reproducibility** | Same config + same data + same seed → same result | Run experiment twice, compare metrics |
| **Metric calculation** | Metrics computed correctly (accuracy, precision, recall, F1, ROC-AUC, confusion matrix) | Known input → expected metric values |
| **Artifact generation** | All required artifacts created, valid format, loadable | Experiment completes → all files exist, model loads, metrics load |
| **Experiment status transitions** | Status changes correctly through lifecycle | CREATED → RUNNING → COMPLETED (success path), CREATED → RUNNING → FAILED (failure path) |

### 24.2 Test Data

Use small, synthetic datasets for testing:
- Known labels (deterministic)
- Known feature values
- Small enough to run quickly (< 100 rows)
- Edge cases: all same class, balanced classes, missing values (for error handling tests)

### 24.3 Test Fixtures Location

```
tests/
├── fixtures/
│   ├── synthetic_dataset_v0.1.parquet    ← Small dataset for pipeline tests
│   ├── config_baseline_lr.yaml           ← Test config for LR baseline
│   └── config_baseline_rf.yaml           ← Test config for RF baseline
├── test_configuration.py                 ← Config validation tests
├── test_dataset_compatibility.py         ← Version/compatibility tests
├── test_preprocessing.py                 ← Preprocessing leakage tests
├── test_reproducibility.py               ← Reproducibility tests
├── test_metrics.py                       ← Metric calculation tests
├── test_artifacts.py                     ← Artifact generation tests
└── test_status_lifecycle.py              ← Status transition tests
```

---

## 25. Research Questions

### 25.1 Unresolved Questions

These are open research questions for the project. They are NOT resolved in this blueprint. They should be addressed through experimentation and documented in experiment reports.

| Question | Context | MVP Approach |
|----------|---------|--------------|
| **Hyperparameter search budget** | How many combinations to test? What search strategy? | Not addressed in MVP — manual configuration only |
| **Model calibration** | Do predicted probabilities reflect true likelihoods? | Not addressed in MVP — calibration curves are future work |
| **Threshold selection** | Are ±1% thresholds optimal? How to tune without test set leakage? | Fixed thresholds in MVP — tuning is research task |
| **Probability calibration** | Should we calibrate LR probabilities? Platt scaling? Isotonic? | Not addressed in MVP |
| **Class imbalance** | Is `class_weight: balanced` optimal? Other weighting schemes? | Balanced weights in MVP — alternative schemes are research task |
| **Temporal dependence** | How much do adjacent samples overlap? Does this affect validation? | Acknowledged in design — walk-forward backtesting handles this |
| **Feature selection** | Which features matter? How many features are optimal? | All 52 features used in MVP — feature selection is research task |
| **Regime sensitivity** | Does model performance vary by market regime? | Not addressed in MVP — regime analysis is future work |
| **Lookback window sensitivity** | Do different feature lookback windows affect results? | Fixed lookback windows in MVP — sensitivity analysis is future work |
| **Ensemble methods** | Would bagging/stacking improve over single models? | Not addressed in MVP |

### 25.2 Decisions vs Open Questions

**Decided in this blueprint:**
- YAML configuration format
- Timestamp-based experiment IDs
- 15-stage training pipeline
- StandardScaler fit on train only (LR), no scaling (RF)
- Integer label encoding
- `class_weight: balanced` for class imbalance
- 6 experiment types defined
- JSON-based experiment tracking (MVP)
- Specific artifact directory structure
- 5-status lifecycle (CREATED, RUNNING, COMPLETED, FAILED, INVALIDATED)
- ML metrics separated from financial metrics
- Three-way evaluation data separation
- Model selection gate with 5 stages

**Open questions (not decided):**
- Hyperparameter search strategy and budget
- Probability calibration approach
- Optimal threshold values
- Optimal class weighting scheme
- Feature selection methodology
- Regime-aware modeling
- Ensemble approaches

---

## 26. Consistency Check

### 26.1 Cross-Reference with Previous Documents

| Document | Check | Status | Notes |
|----------|-------|--------|--------|
| **PRD_MVP.md** | FR-TM-01: Train logistic regression baseline | ✅ Consistent | Baseline model type matches |
| **PRD_MVP.md** | FR-TM-02: Train random forest classifier | ✅ Consistent | Second baseline matches |
| **PRD_MVP.md** | FR-TM-04: Training config in YAML | ✅ Consistent | Configuration system matches |
| **PRD_MVP.md** | FR-TM-05: Random seeds set explicitly | ✅ Consistent | Reproducibility matches |
| **PRD_MVP.md** | FR-TM-06: Model artifacts with config, metrics, data hash | ✅ Consistent | Artifact strategy matches |
| **PRD_MVP.md** | FR-TM-08: No model promoted without walk-forward validation | ✅ Consistent | Model selection gate acknowledges this |
| **SYSTEM_ARCHITECTURE.md** | TrainingEngine module | ✅ Consistent | Pipeline stages align with module design |
| **SYSTEM_ARCHITECTURE.md** | TrainedModel object | ✅ Consistent | Artifact metadata aligns |
| **SYSTEM_ARCHITECTURE.md** | ModelRegistry placeholder | ✅ Consistent | Simple JSON registry matches MVP scope |
| **BASELINE_MODEL_BLUEPRINT.md** | Model selection (LR + RF) | ✅ Consistent | Same models, same priority |
| **BASELINE_MODEL_BLUEPRINT.md** | Input contract (DatasetSplit) | ✅ Consistent | Same input format |
| **BASELINE_MODEL_BLUEPRINT.md** | Preprocessing (StandardScaler for LR, none for RF) | ✅ Consistent | Same preprocessing rules |
| **BASELINE_MODEL_BLUEPRINT.md** | Experiment tracking metadata | ✅ Consistent | Extended with more fields in this document |
| **BASELINE_MODEL_BLUEPRINT.md** | Model versioning (v{major}.{minor}.{patch}-{date}) | ✅ Consistent | Same version scheme |
| **BASELINE_MODEL_BLUEPRINT.md** | Checkpoint strategy (joblib + JSON) | ✅ Consistent | Same artifact format |
| **BASELINE_MODEL_BLUEPRINT.md** | Reproducibility (seed, config snapshot, env metadata) | ✅ Consistent | Extended with more detail in this document |
| **BASELINE_MODEL_BLUEPRINT.md** | Failure handling categories | ✅ Consistent | Extended with more detail in this document |
| **BASELINE_MODEL_BLUEPRINT.md** | Future compatibility (XGBoost, LSTM) | ✅ Consistent | Same future model placeholders |
| **DATASET_BUILDER_BLUEPRINT.md** | Dataset versioning | ✅ Consistent | Dataset version referenced by training pipeline |
| **DATASET_BUILDER_BLUEPRINT.md** | Chronological splits (train/val/test) | ✅ Consistent | Training pipeline uses pre-computed splits |
| **LABEL_GENERATION_BLUEPRINT.md** | Classification target (UP/DOWN/HOLD) | ✅ Consistent | Label type matches |
| **LABEL_GENERATION_BLUEPRINT.md** | Label versioning | ✅ Consistent | Label version referenced by training pipeline |
| **FEATURE_ENGINEERING_BLUEPRINT.md** | Feature versioning | ✅ Consistent | Feature version referenced by training pipeline |
| **FEATURE_ENGINEERING_BLUEPRINT.md** | Scaling rules | ✅ Consistent | Matches preprocessing rules |

### 26.2 Conflicts Found

**None.** All documents are consistent. This blueprint extends and complements the existing architecture without contradicting it.

### 26.3 Required Changes

**None.** No changes to previous architecture required. This blueprint adds the training pipeline and experiment management layer that was implicitly required but not yet documented.

---

## 27. Deliverables

| Deliverable | Status | Description |
|-------------|--------|-------------|
| `docs/TRAINING_PIPELINE_BLUEPRINT.md` | ✅ This document | Complete training pipeline and experiment management design |
| `docs/CURRENT_STATE.md` | ⏳ To update | Add new blueprint to architecture documentation list |
| `docs/DECISIONS.md` | ⏳ To update | Add ADR if new architectural decision made |

---

## 28. Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| Training lifecycle defined (15 stages) | ✅ |
| Experiment identity defined (ID format + metadata) | ✅ |
| Configuration strategy defined (YAML, hierarchy, controls) | ✅ |
| Reproducibility strategy defined (versions, config, seed, environment) | ✅ |
| Preprocessing rules defined (fit on train, apply to test, by model type) | ✅ |
| Artifact strategy defined (directory structure, required artifacts) | ✅ |
| Metric policy defined (ML vs financial, separation) | ✅ |
| Validation/test separation defined (three-way split, usage rules) | ✅ |
| Failure handling defined (categories, responses, status) | ✅ |
| Compatibility checks defined (version matching, verification) | ✅ |
| Model selection gate defined (5 stages, criteria, outcomes) | ✅ |
| Future MLOps boundaries defined (reserved capabilities, extension points) | ✅ |
| Research report format defined (machine-readable + human-readable) | ✅ |
| Experiment types defined (6 categories) | ✅ |
| Security & data integrity requirements defined | ✅ |
| Testing strategy defined (7 test categories) | ✅ |
| Research questions identified (open vs decided) | ✅ |
| Consistency check completed (all documents cross-referenced) | ✅ |
| NO implementation code written | ✅ |

---

## 29. Stop Condition

**This document is architecture and research specification only.**

**DO NOT:**
- Write Python training code
- Train models
- Install ML libraries beyond what is already specified
- Run experiments
- Download data
- Create dashboards
- Implement MLflow
- Implement model registry
- Implement automated retraining
- Create experiment directories
- Generate any artifacts

**STOP after documentation is complete.**

---

## Final Report

### A. Training Lifecycle

15-stage pipeline: Load metadata → Verify integrity → Verify feature version → Verify label version → Load config → Load splits → Fit preprocessing → Train model → Predict → Compute ML metrics → (Financial metrics in backtesting) → Save artifacts → Save experiment record → Mark status → Generate report.

### B. Experiment Identity Strategy

Timestamp-based IDs (`exp_{timestamp}`). Full metadata recorded: model_type, model_version, dataset_version, feature_version, label_version, config_version, code_version, random_seed, created_at, training_period, validation_period, environment.

### C. Reproducibility Strategy

Pin dataset_version, feature_version, label_version, config (with hash), seed, code_version, environment. Acknowledge that bitwise reproducibility has limitations (OpenMP RF, floating point, hardware). MVP uses `n_jobs=1` for RF determinism. "Functionally equivalent" (4+ decimal places) is the practical standard.

### D. Configuration Strategy

YAML format (human-readable, comments, Git-friendly). Three-level hierarchy: default.yaml → experiment override → environment override. Configuration controls: dataset, features, labels, horizon, model, training, evaluation, output. No hardcoded experiment values in source code.

### E. Artifact Strategy

Directory structure: `experiments/{id}/config/`, `metrics/`, `model/`, `predictions/`, `reports/`, `metadata/`. Required artifacts: model.joblib, scaler.joblib (LR only), metadata.json, config_snapshot.json, val_predictions.csv, report.md. JSON-based registry for MVP (ModelRegistry Protocol interface for future).

### F. Metric Strategy

Strict separation: ML metrics (accuracy, precision, recall, F1, ROC-AUC, confusion matrix) computed during training. Financial metrics (Sharpe, drawdown, win rate, profit factor) computed during backtesting. High classification score ≠ profitable strategy.

### G. Model Selection Gate

5-stage gate: Validation Check → Quality Checks → Baseline Comparison → Financial Evaluation → Decision. Outcomes: PASS (model candidate), REJECT (document and retain), INCONCLUSIVE, NEEDS_MORE_DATA. No automatic deployment — gate produces candidate, not deployment.

### H. Risks Identified

| Risk | Mitigation |
|------|------------|
| Bitwise non-reproducibility (OpenMP RF, floating point) | `n_jobs=1`, acknowledge limitation, "functionally equivalent" standard |
| Test set contamination | Architectural constraint: pipeline uses pre-computed splits, never re-splits |
| Overfitting to validation set | No hyperparameter tuning in MVP; validation set only for model comparison |
| Unsupported claims | Report template prohibits claims like "AI is profitable" |
| Version incompatibility | Compatibility checks before training; abort on mismatch |
| Unversioned code | Mark as "unversioned" in experiment record; warn about reproducibility |

### I. Contradictions with Previous Documents

**None found.** This blueprint is fully consistent with:
- PRD_MVP.md (FR-TM-01 through FR-TM-08)
- SYSTEM_ARCHITECTURE.md (TrainingEngine, ModelRegistry, TrainedModel)
- BASELINE_MODEL_BLUEPRINT.md (model selection, preprocessing, versioning, reproducibility)
- DATASET_BUILDER_BLUEPRINT.md (dataset versioning, chronological splits)
- LABEL_GENERATION_BLUEPRINT.md (classification target, label versioning)
- FEATURE_ENGINEERING_BLUEPRINT.md (feature versioning, scaling rules)

### J. Exact Next Recommended Task

**Update CURRENT_STATE.md and DECISIONS.md** to reflect the new training pipeline blueprint, then proceed with pre-implementation configuration fixes (label_type: classification in config/default.yaml, add full model configuration section).