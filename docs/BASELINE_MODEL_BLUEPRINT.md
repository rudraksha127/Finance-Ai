# BASELINE MODEL BLUEPRINT — Finance AI MVP

> Reproducible ML pipeline design for training the first benchmark model.
> Defines model selection, training contract, versioning, and reproducibility guarantees.

---

## Table of Contents

1. [Model Selection](#1-model-selection)
2. [Input Contract](#2-input-contract)
3. [Training Pipeline](#3-training-pipeline)
4. [Hyperparameter Strategy](#4-hyperparameter-strategy)
5. [Class Imbalance Strategy](#5-class-imbalance-strategy)
6. [Experiment Tracking](#6-experiment-tracking)
7. [Model Versioning](#7-model-versioning)
8. [Checkpoint Strategy](#8-checkpoint-strategy)
9. [Reproducibility Rules](#9-reproducibility-rules)
10. [Failure Handling](#10-failure-handling)
11. [Future Compatibility](#11-future-compatibility)

---

## 1. Model Selection

### 1.1 Candidate Comparison

| Model | Type | Pros | Cons | MVP Priority |
|-------|------|------|------|--------------|
| **Logistic Regression** | Linear classifier | Interpretable coefficients, fast training, probabilistic outputs, baseline for comparison | Assumes linear decision boundary, limited feature interaction capture | **P0 — MVP Baseline** |
| **Random Forest** | Ensemble trees | Captures non-linear patterns, robust to noise, no scaling required, feature importance | Slower than LR, less interpretable, can overfit with deep trees | **P0 — MVP Baseline** |
| **Gradient Boosting** | Ensemble trees | Higher accuracy potential, sequential error correction | More hyperparameter tuning, slower training, overfitting risk | P1 — If time permits |
| **XGBoost** | Optimized GBM | Industry standard, regularization built-in, fast | Extra dependency, more tuning required | Future extension |
| **LightGBM** | Optimized GBM | Fast training, low memory, handles large data | Extra dependency, less mature ecosystem | Future extension |

### 1.2 Selection Decision

**MVP BASELINES (per PRD_MVP.md FR-TM-01, FR-TM-02):**

| Priority | Model | Role |
|----------|-------|------|
| P0 | Logistic Regression | Simple, interpretable baseline — establishes whether signal exists |
| P0 | Random Forest | Non-linear baseline — captures patterns LR misses |

**NOT in MVP scope (per PRD_MVP.md Section 10 — Out of Scope):**
- XGBoost, LightGBM — deferred to future phases (extra dependencies, tuning complexity)
- Deep learning (LSTM, Transformer) — explicitly out of scope for MVP

### 1.3 Justification

| Factor | Logistic Regression | Random Forest |
|--------|--------------------|---------------|
| **Simplicity** | Minimal config, few hyperparameters | Moderate config |
| **Training speed** | Fast (seconds) | Moderate (minutes) |
| **Interpretability** | Coefficients directly interpretable | Feature importance available |
| **Signal detection** | Tests if linear signal exists | Tests if non-linear signal exists |
| **Dependency** | sklearn (already required) | sklearn (already required) |
| **Overfitting risk** | Low (linear, regularized) | Moderate (tune max_depth, n_estimators) |

**Rationale:** The MVP goal is to establish whether *any* predictive signal exists in the features. Starting with two simple, well-understood models (one linear, one tree-based) provides:
- A floor for comparison (LR)
- A step up in complexity (RF)
- Both use existing sklearn dependency (no new packages)
- Both produce probabilistic outputs compatible with the prediction API

---

## 2. Input Contract

### 2.1 Required Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| **Dataset** | `DatasetSplit` object | `DatasetBuilder` output | Yes |
| **Model config** | YAML configuration dict | `config/default.yaml` → `model` section | Yes |
| **Feature version** | String (e.g., "v0.1") | Dataset metadata | Yes |
| **Label version** | String (e.g., "v0.1") | Dataset metadata | Yes |
| **Dataset version** | String (e.g., "v0.1") | Dataset metadata | Yes |
| **Config snapshot** | Dict | Full config at training time | Yes |

### 2.2 Dataset Contract

```python
@dataclass
class TrainingInput:
    # Data
    X_train: pd.DataFrame       # Features (rows × 52 features)
    y_train: pd.Series          # Labels ("UP", "DOWN", "HOLD")
    X_val: pd.DataFrame         # Validation features
    y_val: pd.Series            # Validation labels

    # Metadata
    feature_names: List[str]    # Ordered feature names
    feature_version: str        # "v0.1"
    label_version: str          # "v0.1"
    dataset_version: str        # "v0.1"
    train_start: str            # ISO timestamp
    train_end: str              # ISO timestamp
    val_start: str              # ISO timestamp
    val_end: str                # ISO timestamp
```

### 2.3 Preprocessing Requirements

| Model | Scaling Required | Method | Fit On |
|-------|-----------------|--------|--------|
| **Logistic Regression** | Yes | StandardScaler | Training data only |
| **Random Forest** | No | None | N/A |

**Rules:**
- Scaler fitted on training data only
- Same scaler applied to validation/test (never refit)
- Scaler saved with model artifact
- No global scaling across all data (prevents leakage)

### 2.4 Validation Before Training

Training must NOT start until:
- Dataset passes all validation checks (DVAL-01 through DVAL-10)
- Feature count matches expected (52 for MVP)
- Label distribution is acceptable (no class < 10%)
- Chronological splits verified (train_end < val_start)
- No NaN values in features
- Feature and label versions recorded

---

## 3. Training Pipeline

### 3.1 Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       TRAINING PIPELINE                                   │
│                                                                          │
│  DatasetSplit                                                             │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────────────┐                                                    │
│  │ VALIDATE INPUT  │  Check dataset validity, versions, distribution     │
│  └────────┬────────┘                                                    │
│           │ PASS                                                          │
│           ▼                                                              │
│  ┌─────────────────┐                                                    │
│  │ PREPROCESS      │  Scale features (LR only), encode labels           │
│  └────────┬────────┘                                                    │
│           │                                                              │
│           ▼                                                              │
│  ┌─────────────────┐     ┌─────────────────┐                            │
│  │ TRAIN MODEL     │     │ TRAIN MODEL     │                            │
│  │ Logistic Reg.   │     │ Random Forest   │                            │
│  │ (parallel)      │     │ (parallel)      │                            │
│  └────────┬────────┘     └────────┬────────┘                            │
│           │                      │                                      │
│           ▼                      ▼                                      │
│  ┌─────────────────┐     ┌─────────────────┐                            │
│  │ EVALUATE        │     │ EVALUATE        │                            │
│  │ Train metrics   │     │ Train metrics   │                            │
│  │ Val metrics     │     │ Val metrics     │                            │
│  └────────┬────────┘     └────────┬────────┘                            │
│           │                      │                                      │
│           ▼                      ▼                                      │
│  ┌─────────────────────────────────────────┐                           │
│  │ SAVE ARTIFACTS                           │                           │
│  │ - Model (.joblib)                        │                           │
│  │ - Scaler (LR only, .joblib)              │                           │
│  │ - Metadata (.json)                       │                           │
│  │ - Config snapshot                        │                           │
│  └──────────────────┬──────────────────────┘                           │
│                     ▼                                                  │
│  ┌─────────────────────────────────────────┐                           │
│  │ LOG & REGISTER                          │                           │
│  │ - Training duration                     │                           │
│  │ - Final metrics                         │                           │
│  │ - Model version                         │                           │
│  └─────────────────────────────────────────┘                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Stage Details

#### Stage 1: Validate Input
- Verify `DatasetSplit` structure
- Check feature count == expected
- Verify label distribution
- Confirm versions match config

#### Stage 2: Preprocess
- Encode labels: UP=0, DOWN=1, HOLD=2 (or one-hot for certain models)
- Fit StandardScaler on X_train (LR only)
- Transform X_train, X_val with scaler (LR only)
- No preprocessing for Random Forest

#### Stage 3: Train Model
- Instantiate model from config parameters
- Set random_seed explicitly
- Fit on (X_train, y_train)
- Log training duration

#### Stage 4: Evaluate
- Predict on X_train → compute train metrics
- Predict on X_val → compute validation metrics
- Metrics: accuracy, precision (per class), recall (per class), F1 (per class), macro F1
- Store raw predictions for audit

#### Stage 5: Save Artifacts
- Serialize model to `.joblib`
- Serialize scaler to `.joblib` (LR only)
- Write metadata JSON
- Store config snapshot

#### Stage 6: Log & Register
- Log: model type, version, duration, metrics
- Register model in ModelRegistry
- Return `TrainedModel` object

### 3.3 Training Configuration (YAML)

```yaml
# config/default.yaml — model section

model:
  random_seed: 42

  models:
    - name: logistic_regression
      type: linear
      params:
        C: 1.0
        penalty: l2
        solver: lbfgs
        max_iter: 1000
        class_weight: balanced

    - name: random_forest
      type: ensemble
      params:
        n_estimators: 100
        max_depth: 10
        min_samples_split: 5
        min_samples_leaf: 2
        class_weight: balanced
        random_state: 42
```

---

## 4. Hyperparameter Strategy

### 4.1 Configurable Parameters

All hyperparameters MUST be configurable via YAML. No hardcoded values in training code.

| Model | Parameter | Default | Description | Tunable |
|-------|-----------|---------|-------------|---------|
| **Logistic Regression** | C | 1.0 | Inverse regularization strength | Yes |
| | penalty | l2 | Regularization type | Yes |
| | solver | lbfgs | Optimization solver | Yes |
| | max_iter | 1000 | Max iterations | Yes |
| | class_weight | balanced | Handle class imbalance | Yes |
| **Random Forest** | n_estimators | 100 | Number of trees | Yes |
| | max_depth | 10 | Max tree depth | Yes |
| | min_samples_split | 5 | Min samples to split | Yes |
| | min_samples_leaf | 2 | Min samples in leaf | Yes |
| | class_weight | balanced | Handle class imbalance | Yes |

### 4.2 Parameter Validation

```yaml
# Config validation rules

model:
  models:
    - name: logistic_regression
      params:
        C:                          # Must be float > 0
        max_iter:                   # Must be int > 0
        solver:                     # Must be valid sklearn solver

    - name: random_forest
      params:
        n_estimators:               # Must be int > 0
        max_depth:                  # Must be int > 0 or null
        min_samples_split:          # Must be int > 0
        min_samples_leaf:           # Must be int > 0
```

### 4.3 Hyperparameter Tuning (Future)

**MVP: Use defaults from config. No automatic tuning.**

**Future enhancement:**
- Grid search over validation set
- Random search for expensive models
- Bayesian optimization for production

**Rule:** Never tune hyperparameters on test set. Validation set only.

---

## 5. Class Imbalance Strategy

### 5.1 Problem

With 5-day horizon and 1% thresholds, expected class distribution:

| Class | Expected % | Risk |
|-------|-----------|------|
| UP | ~33% | Balanced |
| DOWN | ~33% | Balanced |
| HOLD | ~34% | Balanced |

However, actual distribution may vary by:
- Market regime (bull → more UP, bear → more DOWN)
- Ticker selection
- Threshold settings

### 5.2 MVP Strategy

**Use `class_weight: balanced` in model training.**

This automatically adjusts sample weights inversely proportional to class frequencies:

```python
# sklearn behavior with class_weight='balanced'
n_samples / (n_classes * np.bincount(y))
```

**Why this approach:**

| Approach | MVP? | Justification |
|----------|------|---------------|
| `class_weight: balanced` | ✅ Yes | Built into sklearn, no extra code, supported by both LR and RF |
| Manual sample weights | ⚠️ Optional | More control but requires computing weights |
| Stratified sampling | ❌ No | Changes data distribution, not needed for MVP |
| SMOTE / oversampling | ❌ No | Synthetic samples risky for financial data |
| Undersampling majority | ❌ No | Discards data, not informative |

### 5.3 Monitoring

After training, log:
- Class distribution in training set
- Class distribution in validation set
- Per-class metrics (precision, recall, F1)
- Whether class_weight was applied

If one class drops below 10%:
- Log WARNING
- Flag in metadata
- Do NOT auto-adjust — researcher decides

---

## 6. Experiment Tracking

### 6.1 Required Metadata Per Run

Every training run stores:

```python
@dataclass
class ExperimentRecord:
    # Identity
    experiment_id: str              # "exp_20260904_120000"
    run_timestamp: str              # ISO timestamp

    # Versions
    model_version: str              # "v1.0.0-20260904"
    dataset_version: str            # "v0.1"
    feature_version: str            # "v0.1"
    label_version: str              # "v0.1"
    config_version: str             # Config hash

    # Inputs
    model_type: str                 # "logistic_regression" or "random_forest"
    model_params: Dict              # Full parameter snapshot
    feature_names: List[str]        # Ordered feature list
    dataset_split: Dict             # train/val/test boundaries and counts

    # Metrics
    train_metrics: Dict             # accuracy, precision, recall, f1 per class
    val_metrics: Dict               # Same structure
    train_duration_seconds: float   # Wall clock time

    # Artifacts
    model_path: str                 # Path to .joblib
    scaler_path: str                # Path to scaler .joblib (LR only)
    metadata_path: str              # Path to .json

    # Status
    status: str                     # "success", "failed", "skipped"
    error_message: str              # If failed
```

### 6.2 Storage Location

```
models/
├── experiments/
│   ├── exp_20260904_120000/
│   │   ├── model.joblib
│   │   ├── scaler.joblib          # (LR only)
│   │   ├── metadata.json
│   │   └── config_snapshot.json
│   ├── exp_20260904_140000/
│   │   └── ...
├── registry/
│   └── registry.json              # Latest model pointers
```

### 6.3 Logging Requirements

Every training run logs:
- Start: model type, dataset version, feature count, timestamp
- During: training progress (if applicable), duration
- End: metrics (train + val), model version, artifact paths, status
- Errors: full exception context if failed

---

## 7. Model Versioning

### 7.1 Version Scheme

```
Model Version: v{major}.{minor}.{patch}-{date}

Examples:
  v1.0.0-20260904        → Initial production model
  v1.1.0-20260904        → Updated hyperparameters
  v1.1.1-20260904        → Bug fix in training
  v2.0.0-20260904        → New feature set
```

### 7.2 Version Components

| Component | Source | Description |
|-----------|--------|-------------|
| **major** | Incremented for feature set changes, target changes | Breaking change |
| **minor** | Incremented for hyperparameter changes, model type changes | Backward compatible |
| **patch** | Incremented for bug fixes, data fixes | No functional change |
| **date** | Training date (YYYYMMDD) | Reproducibility anchor |

### 7.3 Version Lifecycle

```python
@dataclass
class ModelVersion:
    version: str                   # "v1.0.0-20260904"
    model_type: str                # "logistic_regression"
    status: str                    # "active", "deprecated", "archived"
    created_at: str                # ISO timestamp
    created_by: str                # "pipeline" or "researcher"
    dataset_version: str           # Source dataset
    feature_version: str           # Source features
    label_version: str             # Source labels
    config_snapshot: Dict          # Full config used
    metrics: Dict                  # Final validation metrics
    artifact_path: str             # Path to model file
    superseded_by: str             # If deprecated
```

### 7.4 Version Rules

| Rule | Description |
|------|-------------|
| **No overwrite** | Never overwrite an existing model version |
| **Version increment** | Each training run produces a new version |
| **Retain old versions** | Old versions kept for reproducibility (file-based, can be pruned) |
| **Active pointer** | Registry tracks which version is "active" |
| **Reproducibility** | Same config + same data + same seed = same version |

---

## 8. Checkpoint Strategy

### 8.1 Storage Location

```yaml
# config/default.yaml

model:
  artifact_dir: models          # Base directory for model artifacts
  registry_path: models/registry/registry.json  # Model registry
  max_versions_to_retain: 10    # Keep last N versions (future)
```

### 8.2 Artifact Structure

Each model version produces:

```
models/experiments/{experiment_id}/
├── model.joblib              # Serialized sklearn estimator
├── scaler.joblib             # StandardScaler (LR only, omitted for RF)
├── metadata.json             # Full ExperimentRecord as JSON
└── config_snapshot.json      # Exact config used for this run
```

### 8.3 Model Registry

Simple JSON-based registry for MVP:

```json
{
  "active_model": {
    "version": "v1.0.0-20260904",
    "model_type": "random_forest",
    "experiment_id": "exp_20260904_140000",
    "artifact_path": "models/experiments/exp_20260904_140000/model.joblib",
    "created_at": "2026-09-04T14:00:00Z",
    "metrics": {
      "accuracy": 0.54,
      "macro_f1": 0.53
    }
  },
  "version_history": [
    {
      "version": "v0.9.0-20260904",
      "model_type": "logistic_regression",
      "status": "archived",
      "created_at": "2026-09-04T12:00:00Z"
    }
  ]
}
```

### 8.4 Model Loading

At prediction time:
1. Read registry to find active model
2. Load model from artifact path
3. Load scaler if model type requires it (LR)
4. Validate model version matches expected

---

## 9. Reproducibility Rules

### 9.1 Random Seed

```yaml
# config/default.yaml

model:
  random_seed: 42
```

**Rules:**
- Random seed set explicitly at training start
- Seed passed to all stochastic operations (model init, shuffling if any)
- Seed logged with experiment record
- Same seed + same data + same config → same result

### 9.2 Configuration Snapshot

Every training run saves the **exact configuration** used:

```json
{
  "config_snapshot": {
    "model": {
      "random_seed": 42,
      "models": [...]
    },
    "dataset": {
      "label_type": "classification",
      "label_window": 5,
      "split_ratios": {...}
    },
    "features": {
      "lookback_windows": [...]
    }
  },
  "config_hash": "sha256:a1b2c3d4..."
}
```

### 9.3 Environment Metadata

```python
@dataclass
class EnvironmentMetadata:
    python_version: str            # "3.10.12"
    platform: str                  # "Linux-5.15.0..."
    packages: Dict[str, str]       # {"scikit-learn": "1.3.2", "pandas": "2.0.3", ...}
    numpy_version: str
    sklearn_version: str
    timestamp: str
```

### 9.4 Reproducibility Checklist

| Check | Verified By |
|-------|-------------|
| Random seed set | Logged in experiment record |
| Config snapshot saved | File on disk |
| Feature version recorded | Dataset metadata |
| Label version recorded | Dataset metadata |
| Dataset version recorded | Dataset metadata |
| Package versions recorded | Environment metadata |
| Same input → same output | Verified by re-running (future) |

### 9.5 Determinism Guarantees

| Component | Deterministic? | Condition |
|-----------|---------------|-----------|
| **Logistic Regression** | Yes | Fixed seed, fixed data, fixed config |
| **Random Forest** | Yes (with seed) | `random_state` set, `n_jobs=1` |
| **Feature computation** | Yes | Deterministic transforms (per FE blueprint) |
| **Label generation** | Yes | Deterministic thresholds (per LG blueprint) |

**Note:** Random Forest with `n_jobs > 1` may not be fully deterministic across runs due to thread scheduling. MVP uses `n_jobs=1` for reproducibility.

---

## 10. Failure Handling

### 10.1 Failure Categories

| Category | Trigger | Handling |
|----------|---------|----------|
| **Invalid dataset** | Dataset fails validation (DVAL-01 through DVAL-10) | Abort training, log error, do not save artifacts |
| **Missing features** | Feature count mismatch, missing columns | Abort, log which features missing |
| **Wrong versions** | Feature/label version mismatch with config | Abort, log expected vs actual versions |
| **Training interruption** | Keyboard interrupt, OOM, timeout | Log partial state, do not register incomplete model |
| **Invalid config** | Missing params, invalid values | Abort before training, log validation error |
| **Model convergence failure** | LR fails to converge (max_iter reached) | Log warning, still save model with flag |
| **Empty dataset** | After warm-up, no rows remain | Abort, log reason |

### 10.2 Error Flow

```
Training Start
    │
    ├──▶ Validate Input
    │     │
    │     ├──▶ PASS → Continue
    │     │
    │     └──▶ FAIL → Log error + context
    │                Raise TrainingInputError
    │                Do NOT save artifacts
    │
    ├──▶ Preprocess
    │     │
    │     ├──▶ PASS → Continue
    │     │
    │     └──▶ FAIL → Log error
    │                Raise PreprocessingError
    │
    ├──▶ Train Model
    │     │
    │     ├──▶ SUCCESS → Continue
    │     │
    │     ├──▶ WARNING (non-convergence) → Log, continue with flag
    │     │
    │     └──▶ FAIL (exception) → Log full context
    │                              Raise TrainingError
    │                              Do NOT register model
    │
    ├──▶ Evaluate
    │     │
    │     └──▶ FAIL → Log error
    │                Raise EvaluationError
    │
    └──▶ Save Artifacts
          │
          ├──▶ SUCCESS → Log success, register model
          │
          └──▶ FAIL → Log error, raise ArtifactError
```

### 10.3 Error Classes

```python
# Explicit error types for clear failure handling

class TrainingError(Exception):
    """Base class for training failures."""
    stage: str
    message: str
    context: Dict

class TrainingInputError(TrainingError):
    """Input dataset is invalid."""
    stage = "input_validation"

class PreprocessingError(TrainingError):
    """Preprocessing failed."""
    stage = "preprocessing"

class ModelTrainingError(TrainingError):
    """Model training failed."""
    stage = "training"

class EvaluationError(TrainingError):
    """Evaluation failed."""
    stage = "evaluation"

class ArtifactError(TrainingError):
    """Saving artifacts failed."""
    stage = "artifact_save"
```

### 10.4 Partial State Handling

| Scenario | Action |
|----------|--------|
| Training fails before model saved | No artifacts saved, no registry update |
| Training fails after model saved but before registry update | Model file exists but not registered (orphaned) |
| Training interrupted (OOM) | Log memory usage, partial metrics if available |
| Validation fails | Abort, full error logged, exit non-zero |

**Rule:** Never register a model that didn't complete training successfully.

---

## 11. Future Compatibility

### 11.1 Reserved Architecture

The training pipeline architecture supports future model types without rewriting core infrastructure:

```
                    ┌─────────────────────────────┐
                    │     TrainingEngine           │
                    │  (orchestrates training)    │
                    └────────────┬────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
    ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
    │   LR Trainer  │  │   RF Trainer  │  │ XGBoost      │
    │   (MVP)       │  │   (MVP)       │  │ (Future)     │
    └───────────────┘  └───────────────┘  └───────────────┘
```

### 11.2 Supported Future Models

| Model | Status | Architecture Support |
|-------|--------|---------------------|
| **XGBoost** | Future | Same interface (fit/predict), different params |
| **LightGBM** | Future | Same interface, categorical feature support |
| **LSTM** | Future | Different preprocessing (sequences), different input format |
| **Transformer** | Future | Different preprocessing, attention-based |
| **Ensemble (stacking)** | Future | Multiple base models → meta-learner |
| **Reinforcement Learning** | Future | Different training loop entirely, out of scope for near future |

### 11.3 Extension Points

| Extension | What Changes | What Stays |
|-----------|-------------|------------|
| **New model type** | New trainer class, new config section | TrainingPipeline, ExperimentRecord, versioning |
| **Different scaling** | New scaler in preprocessing | Fit-on-train-only rule, save-with-artifact rule |
| **Sequence models (LSTM)** | Different input format (sequences vs rows) | Versioning, experiment tracking, reproducibility |
| **Multi-target** | Different y format | Same training pipeline structure |
| **Custom loss functions** | Model-specific implementation | No change to pipeline |

### 11.4 Architecture Rules for Extensions

| Rule | Description |
|------|-------------|
| **No pipeline rewrite** | New models plug into existing TrainingEngine interface |
| **Config-driven** | Every new model has YAML config section |
| **Versioned** | New model types get their own version namespace |
| **Logged** | All models use same experiment tracking |
| **Validated** | New models pass same input validation |

### 11.5 Placeholder Configurations

```yaml
# Future: XGBoost (not in MVP)

model:
  models:
    - name: xgboost
      type: boosting
      params:
        n_estimators: 100
        max_depth: 6
        learning_rate: 0.1
        subsample: 0.8
        colsample_bytree: 0.8
        objective: multi:softprob
        num_class: 3
        random_state: 42

# Future: LSTM (not in MVP)

model:
  models:
    - name: lstm
      type: sequential_nn
      params:
        sequence_length: 10
        hidden_units: [64, 32]
        dropout: 0.2
        epochs: 50
        batch_size: 32
        learning_rate: 0.001
```

---

## Appendix A: Configuration Reference

```yaml
# config/default.yaml — Complete model section

model:
  # Reproducibility
  random_seed: 42

  # Artifact storage
  artifact_dir: models
  registry_path: models/registry/registry.json

  # Models to train (MVP: logistic_regression + random_forest)
  models:
    - name: logistic_regression
      type: linear
      params:
        C: 1.0
        penalty: l2
        solver: lbfgs
        max_iter: 1000
        class_weight: balanced

    - name: random_forest
      type: ensemble
      params:
        n_estimators: 100
        max_depth: 10
        min_samples_split: 5
        min_samples_leaf: 2
        class_weight: balanced
        random_state: 42

  # Reproducibility
  n_jobs: 1  # Set to 1 for deterministic RF

# Future: additional models would be added here
```

---

## Appendix B: Cross-Reference to Pipeline

| Pipeline Stage | Baseline Model Input | Baseline Model Output |
|---------------|---------------------|----------------------|
| Data Ingestion | Raw OHLCV CSV | Clean DataFrame |
| Data Validation | Raw DataFrame | Validated DataFrame |
| Data Processing | Validated DataFrame | Clean DataFrame |
| Feature Engineering | Clean DataFrame | Feature DataFrame (52 cols) |
| Label Generation | Clean DataFrame | Label Series (UP/DOWN/HOLD) |
| Dataset Builder | Features + Labels | DatasetSplit (train/val/test) |
| **Baseline Model** | **DatasetSplit** | **TrainedModel (LR + RF)** |
| Model Registry | TrainedModel | Model artifact + metadata |
| Backtesting | DatasetSplit + TrainedModel | BacktestReport |
| Prediction API | Feature dict + TrainedModel | Prediction JSON |

---

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| Model selection justified (LR + RF per PRD) | ✅ |
| Input contract defined (DatasetSplit + metadata) | ✅ |
| Training pipeline stages defined | ✅ |
| Hyperparameter strategy configurable (no hardcoded values) | ✅ |
| Class imbalance strategy defined (class_weight: balanced) | ✅ |
| Experiment tracking metadata defined | ✅ |
| Model versioning scheme defined | ✅ |
| Checkpoint strategy defined (joblib + JSON) | ✅ |
| Reproducibility rules explicit (seed, config snapshot, env metadata) | ✅ |
| Failure handling categories defined | ✅ |
| Future compatibility placeholders defined (XGBoost, LSTM, etc.) | ✅ |
| Consistent with PRD (FR-TM-01, FR-TM-02) | ✅ |
| Consistent with SYSTEM_ARCHITECTURE.md (TrainingEngine module) | ✅ |
| Consistent with FEATURE_ENGINEERING_BLUEPRINT.md (scaling rules) | ✅ |
| Consistent with LABEL_GENERATION_BLUEPRINT.md (classification target) | ✅ |
| NO implementation code written | ✅ |
