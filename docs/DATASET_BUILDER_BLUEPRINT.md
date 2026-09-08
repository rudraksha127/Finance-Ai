# DATASET BUILDER BLUEPRINT — Finance AI MVP

> Production-grade dataset pipeline design for the Finance AI platform.
> Converts clean data + features + labels into versioned training datasets.
> Every dataset is reproducible, immutable, and traceable.

---

## Table of Contents

1. [Dataset Pipeline](#1-dataset-pipeline)
2. [Dataset Schema](#2-dataset-schema)
3. [Train / Validation / Test Split](#3-train--validation--test-split)
4. [Walk-Forward Dataset Strategy](#4-walk-forward-dataset-strategy)
5. [Purging & Embargo](#5-purging--embargo)
6. [Dataset Versioning](#6-dataset-versioning)
7. [Storage Format](#7-storage-format)
8. [Dataset Metadata](#8-dataset-metadata)
9. [Dataset Validation](#9-dataset-validation)
10. [Future Incremental Updates](#10-future-incremental-updates)

---

## 1. Dataset Pipeline

### 1.1 Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       DATASET PIPELINE                                   │
│                                                                          │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐            │
│  │ Raw Data │──▶│ Features │──▶│  Labels  │──▶│ Dataset  │            │
│  │ (Clean)  │   │ (52 ft)  │   │ (UP/DN/  │   │ Builder  │            │
│  │          │   │          │   │  HOLD)   │   │          │            │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘            │
│       │              │              │              │                     │
│       ▼              ▼              ▼              ▼                     │
│  DataFrame     DataFrame      Series         DatasetSplit               │
│                                                                          │
│                                    │                                     │
│                                    ▼                                     │
│                           ┌────────────────┐                             │
│                           │  Version       │                             │
│                           │  Snapshot      │                             │
│                           └────────────────┘                             │
│                                    │                                     │
│                                    ▼                                     │
│                           ┌────────────────┐                             │
│                           │  Validated     │                             │
│                           │  Dataset       │                             │
│                           └────────────────┘                             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Detailed Pipeline Stages

#### Stage 1: Load Clean Data

```
Input:   Clean DataFrame from DataProcessor
Process: Verify data is clean and ready for feature computation
Output:  Validated clean DataFrame
Logging: Row count, column list, date range
```

#### Stage 2: Compute Features

```
Input:   Clean DataFrame
Process: FeatureEngine computes all 52 MVP features
Output:  Feature DataFrame with DatetimeIndex
Logging: Feature count, NaN count per feature, computation time
Rules:   Features use only past information
```

#### Stage 3: Generate Labels

```
Input:   Clean DataFrame (for close prices)
Process: LabelEngine generates UP/DOWN/HOLD labels
Output:  Label Series with DatetimeIndex
Logging: Label distribution, forward window, thresholds
Rules:   Labels use future information, features do not
```

#### Stage 4: Align Features and Labels

```
Input:   Feature DataFrame + Label Series
Process: Align on DatetimeIndex, drop rows with NaN labels
Output:  Aligned features and labels
Logging: Rows before/after alignment, NaN label count
Rules:   Features and labels must share same timestamp index
```

#### Stage 5: Drop Warm-Up Rows

```
Input:   Aligned features + labels
Process: Drop rows where ANY feature is NaN (insufficient lookback)
Output:  Clean dataset with no NaN values
Logging: Rows before/after drop, warm-up period used
Rules:   Maximum warm-up: 50 rows (SMA_50 lookback)
```

#### Stage 6: Compute Chronological Splits

```
Input:   Clean features + labels
Process: Split into train/val/test by timestamp
Output:  DatasetSplit object with three (X, y) tuples
Logging: Split boundaries, record counts per split
Rules:   Train end < val start, val end < test start
```

#### Stage 7: Validate Dataset

```
Input:   DatasetSplit
Process: Run dataset validation checks (Section 9)
Output:  ValidationResult
Logging: Checks run, issues found, pass/fail
Rules:   No leakage, no overlap, label distribution acceptable
```

#### Stage 8: Version and Store

```
Input:   Validated DatasetSplit + metadata
Process: Compute version hash, save to Parquet
Output:  Versioned dataset files
Logging: Version hash, file paths, record counts
Rules:   Immutable snapshots, never overwrite
```

### 1.3 Pipeline State Machine

```
┌─────────────────────────────────────────────────────────────┐
│                 Dataset Pipeline States                       │
│                                                              │
│  ┌──────────┐                                                │
│  │   IDLE   │                                                │
│  └────┬─────┘                                                │
│       │ start                                                │
│       ▼                                                      │
│  ┌──────────┐                                                │
│  │ LOADING  │  Load clean data                               │
│  └────┬─────┘                                                │
│       │ success                                              │
│       ▼                                                      │
│  ┌──────────┐                                                │
│  │FEATURES  │  Compute features                              │
│  └────┬─────┘                                                │
│       │ success                                              │
│       ▼                                                      │
│  ┌──────────┐                                                │
│  │ LABELS   │  Generate labels                               │
│  └────┬─────┘                                                │
│       │ success                                              │
│       ▼                                                      │
│  ┌──────────┐                                                │
│  │ ALIGNING │  Align features + labels                       │
│  └────┬─────┘                                                │
│       │ success                                              │
│       ▼                                                      │
│  ┌──────────┐                                                │
│  │ SPLITTING│  Compute chronological splits                  │
│  └────┬─────┘                                                │
│       │ success                                              │
│       ▼                                                      │
│  ┌──────────┐                                                │
│  │VALIDATING│  Validate dataset                              │
│  └────┬─────┘                                                │
│       │ pass                                                 │
│       ▼                                                      │
│  ┌──────────┐                                                │
│  │ VERSIONING│ Version and store                             │
│  └────┬─────┘                                                │
│       │ success                                              │
│       ▼                                                      │
│  ┌──────────┐                                                │
│  │COMPLETED │                                                │
│  └──────────┘                                                │
│                                                              │
│  Any stage can transition to FAILED                          │
│  FAILED → Log full context, raise exception                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Dataset Schema

### 2.1 Column Groups

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       DATASET SCHEMA                                     │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    METADATA GROUP                                │    │
│  │  timestamp        datetime64[ns]   Observation timestamp         │    │
│  │  ticker           string           Ticker symbol (optional)      │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    RAW VALUES GROUP                              │    │
│  │  open             float64          Opening price                 │    │
│  │  high             float64          Highest price                 │    │
│  │  low              float64          Lowest price                  │    │
│  │  close            float64          Closing price                 │    │
│  │  adj_close        float64          Adjusted close                │    │
│  │  volume           int64            Trading volume                │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    FEATURES GROUP (52 columns)                   │    │
│  │  returns_1d       float64          1-day return                  │    │
│  │  returns_5d       float64          5-day return                  │    │
│  │  ... (52 total features)                                         │    │
│  │  gap_pct          float64          Gap from previous close       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    LABELS GROUP                                  │    │
│  │  label            string           "UP", "DOWN", or "HOLD"       │    │
│  │  future_return    float64          Raw future return (audit)     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Column Specification

| Group | Column | Type | Nullable | Description |
|-------|--------|------|----------|-------------|
| **Metadata** | timestamp | datetime64[ns] | No | Observation timestamp (UTC) |
| **Metadata** | ticker | string | Yes | Ticker symbol (multi-ticker only) |
| **Raw** | open | float64 | No | Opening price |
| **Raw** | high | float64 | No | Highest price |
| **Raw** | low | float64 | No | Lowest price |
| **Raw** | close | float64 | No | Closing price |
| **Raw** | adj_close | float64 | Yes | Adjusted closing price |
| **Raw** | volume | int64 | No | Trading volume |
| **Features** | returns_1d | float64 | No | 1-day return |
| **Features** | returns_3d | float64 | No | 3-day return |
| **Features** | ... | float64 | No | ... (52 total) |
| **Features** | gap_pct | float64 | No | Gap percentage |
| **Labels** | label | string | No | "UP", "DOWN", or "HOLD" |
| **Labels** | future_return | float64 | Yes | Raw future return |

### 2.3 Output Objects

```python
@dataclass
class DatasetSplit:
    """Container for chronologically-split datasets."""
    train: Tuple[pd.DataFrame, pd.Series]  # (X_train, y_train)
    val: Tuple[pd.DataFrame, pd.Series]    # (X_val, y_val)
    test: Tuple[pd.DataFrame, pd.Series]   # (X_test, y_test)
    metadata: DatasetMetadata               # Split info and stats

@dataclass
class DatasetMetadata:
    """Metadata for a dataset version."""
    version: str                    # "v0.1"
    version_hash: str               # SHA-256 hash
    feature_version: str            # Feature set version
    label_version: str              # Label set version
    source_version: str             # Raw data version
    created_at: str                 # ISO timestamp
    config_snapshot: Dict           # Full config used
    feature_names: List[str]        # Ordered feature names
    feature_count: int              # Number of features
    total_rows: int                 # Total rows (before split)
    train_rows: int                 # Training set size
    val_rows: int                   # Validation set size
    test_rows: int                  # Test set size
    train_start: str                # Training period start
    train_end: str                  # Training period end
    val_start: str                  # Validation period start
    val_end: str                    # Validation period end
    test_start: str                 # Test period start
    test_end: str                   # Test period end
    nan_count_total: int            # NaN values in features
    label_distribution: Dict        # Class counts
    quality_score: float            # Data quality score (0-100)
```

---

## 3. Train / Validation / Test Split

### 3.1 Chronological Split Design

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       CHRONOLOGICAL SPLIT                                 │
│                                                                          │
│  Timeline:                                                               │
│    ├───────────────────┼──────────┼──────────┤                           │
│    2016-01-01          2023-01-01 2024-01-01 2025-01-01                  │
│                                                                          │
│    ├───────────────────┤          │          │                            │
│    │     TRAIN         │          │          │                            │
│    │     (70%)         │          │          │                            │
│    │                   │          │          │                            │
│    │  2016-01-01 to    │          │          │                            │
│    │  2022-12-31       │          │          │                            │
│    ├───────────────────┤──────────┤          │                            │
│                        │  VAL     │          │                            │
│                        │  (15%)   │          │                            │
│                        │          │          │                            │
│                        │2023-01-01│          │                            │
│                        │to        │          │                            │
│                        │2023-12-31│          │                            │
│                        ├──────────┼──────────┤                            │
│                                   │  TEST    │                            │
│                                   │  (15%)   │                            │
│                                   │          │                            │
│                                   │2024-01-01│                            │
│                                   │to        │                            │
│                                   │2025-12-31│                            │
│                                   ├──────────┤                            │
│                                                                          │
│  Rules:                                                                  │
│    - Train end < Validation start (no overlap)                           │
│    - Validation end < Test start (no overlap)                            │
│    - All splits are contiguous in time                                   │
│    - No random splitting (violates temporal ordering)                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Split Configuration

```yaml
dataset:
  split_ratios:
    train: 0.70    # 70% of data for training
    val: 0.15      # 15% for validation
    test: 0.15     # 15% for testing (held out until final evaluation)
  
  # Alternatively, specify exact dates:
  # split_dates:
  #   train_end: "2022-12-31"
  #   val_end: "2023-12-31"
  #   test_end: "2025-12-31"
```

### 3.3 Split Computation

```
Algorithm:
  1. Sort data by timestamp ascending
  2. Compute total rows: N
  3. Train rows: floor(N × 0.70)
  4. Val rows: floor(N × 0.15)
  5. Test rows: N - train_rows - val_rows
  6. Train: rows[0 : train_rows]
  7. Val: rows[train_rows : train_rows + val_rows]
  8. Test: rows[train_rows + val_rows : N]

Verification:
  assert train_end < val_start
  assert val_end < test_start
  assert train_rows + val_rows + test_rows == N
```

### 3.4 Split Validation

| Check | Rule | Action |
|-------|------|--------|
| **Chronological order** | train_end < val_start | ERROR → Reject |
| **No overlap** | val_end < test_start | ERROR → Reject |
| **Minimum sizes** | train >= 100, val >= 20, test >= 20 | WARNING → Log |
| **Label distribution** | Each class >= 10% in each split | WARNING → Log |

---

## 4. Walk-Forward Dataset Strategy

### 4.1 Walk-Forward Design

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       WALK-FORWARD DATASET STRATEGY                      │
│                                                                          │
│  Purpose:                                                                │
│    Create multiple train/test folds that simulate realistic              │
│    out-of-sample evaluation over time.                                   │
│                                                                          │
│  Configuration:                                                          │
│    train_window: 252 days (~1 year)                                      │
│    test_window: 21 days (~1 month)                                       │
│    step_size: 21 days (~1 month)                                         │
│                                                                          │
│  Fold Generation:                                                        │
│                                                                          │
│  Fold 1:                                                                 │
│    Train: 2020-01-01 to 2020-12-31  (252 days)                          │
│    Test:  2021-01-01 to 2021-01-31  (21 days)                           │
│                                                                          │
│  Fold 2:                                                                 │
│    Train: 2020-01-21 to 2021-01-20  (252 days)                          │
│    Test:  2021-01-21 to 2021-02-19  (21 days)                           │
│                                                                          │
│  Fold 3:                                                                 │
│    Train: 2020-02-11 to 2021-02-10  (252 days)                          │
│    Test:  2021-02-11 to 2021-03-12  (21 days)                           │
│                                                                          │
│  ... (slide forward by step_size)                                        │
│                                                                          │
│  Fold N:                                                                 │
│    Train: (N-1)×step to (N-1)×step + train_window                        │
│    Test:  (N-1)×step + train_window to + test_window                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Walk-Forward Configuration

```yaml
evaluation:
  walk_forward:
    train_window: 252    # ~1 year of trading days
    test_window: 21      # ~1 month
    step_size: 21        # ~1 month
    min_train_size: 252  # Minimum training window
    min_test_size: 21    # Minimum test window
```

### 4.3 Fold Generation Algorithm

```
Algorithm:
  1. Get all timestamps sorted ascending
  2. total_rows = len(timestamps)
  3. folds = []
  4. start = 0
  
  while start + train_window + test_window <= total_rows:
      train_start = start
      train_end = start + train_window
      test_start = train_end
      test_end = test_start + test_window
      
      folds.append({
          train_range: [timestamps[train_start], timestamps[train_end-1]],
          test_range: [timestamps[test_start], timestamps[test_end-1]],
          train_size: train_window,
          test_size: test_window
      })
      
      start += step_size
  
  return folds
```

### 4.4 Walk-Forward vs Static Split

| Aspect | Static Split | Walk-Forward |
|--------|-------------|-------------|
| **Purpose** | Single train/val/test | Multiple rolling evaluations |
| **Evaluation** | One point estimate | Distribution of performance |
| **Realism** | Less realistic | More realistic |
| **Complexity** | Simple | Moderate |
| **MVP Use** | Initial training | Backtesting |

**MVP Recommendation:** Use static split for initial model training, walk-forward for backtesting.

---

## 5. Purging & Embargo

### 5.1 Purging

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       PURGING                                             │
│                                                                          │
│  Problem:                                                                │
│    When using walk-forward with overlapping label windows,               │
│    training and test sets may share information.                         │
│                                                                          │
│  Example:                                                                │
│    Label window = 5 days                                                 │
│    Train ends: 2021-01-15                                                │
│    Test starts: 2021-01-18                                               │
│                                                                          │
│    Training row at 2021-01-13 has label using close at 2021-01-18       │
│    This overlaps with test period!                                       │
│                                                                          │
│  Solution: Purge training rows whose labels overlap with test period     │
│                                                                          │
│  Purging Rule:                                                           │
│    Remove training rows where:                                           │
│      label_timestamp + label_window > test_start                         │
│                                                                          │
│  Example:                                                                │
│    Label window = 5                                                      │
│    Test starts: 2021-01-18                                               │
│    Purge training rows after: 2021-01-18 - 5 = 2021-01-13               │
│    Keep training rows up to: 2021-01-12                                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Embargo

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       EMBARGO                                              │
│                                                                          │
│  Purpose:                                                                │
│    Add a gap between training and test sets to prevent                   │
│    any information leakage through feature overlap.                      │
│                                                                          │
│  Embargo Period:                                                         │
│    - Default: 0 (no embargo for daily data)                              │
│    - For intraday data: embargo = label_window                           │
│                                                                          │
│  Timeline with Embargo:                                                  │
│                                                                          │
│    ├───────────────┤    gap    ├──────────┤                              │
│    │     TRAIN     │ ◄─embargo─▶│   TEST   │                              │
│    ├───────────────┤            ├──────────┤                              │
│                                                                          │
│  MVP Recommendation:                                                     │
│    - No embargo for daily data (walk-forward handles dependencies)       │
│    - Embargo = 0                                                         │
│    - Document as future enhancement for intraday data                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.3 MVP Purging Strategy

| Scenario | Embargo | Purge | Justification |
|----------|---------|-------|---------------|
| **Daily data, static split** | 0 | No | No overlap in static split |
| **Daily data, walk-forward** | 0 | Yes | Purge overlapping label rows |
| **Intraday data (future)** | label_window | Yes | Prevent information leakage |

### 5.4 Purging Implementation Notes

```
When generating walk-forward folds:
  1. For each fold, identify train and test date ranges
  2. Remove training rows where:
     train_timestamp + label_window >= test_start
  3. Log purged row count
  4. Verify no temporal overlap remains
```

---

## 6. Dataset Versioning

### 6.1 Version Scheme

```
Dataset Version: v{major}.{minor}

Examples:
  v0.1  → Initial dataset (52 features, UP/DOWN/HOLD, 5-day horizon)
  v0.2  → Adjusted split ratios (70/15/15 → 75/12.5/12.5)
  v0.3  → Added new features (58 total)
  v1.0  → Production-ready dataset
  v1.1  → Cost-aware labels
```

### 6.2 Version Hash Calculation

```python
def compute_dataset_version_hash(
    feature_version: str,
    label_version: str,
    source_version: str,
    config: dict,
    feature_names: list,
    split_boundaries: dict,
    record_counts: dict
) -> str:
    """Compute deterministic hash for dataset version."""
    version_input = {
        "feature_version": feature_version,
        "label_version": label_version,
        "source_version": source_version,
        "config": config,
        "feature_names": sorted(feature_names),
        "split_boundaries": split_boundaries,
        "record_counts": record_counts
    }
    version_string = json.dumps(version_input, sort_keys=True, default=str)
    return hashlib.sha256(version_string.encode()).hexdigest()
```

### 6.3 Version Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       VERSION LIFECYCLE                                   │
│                                                                          │
│  1. CREATE                                                               │
│     │  DatasetBuilder assembles features + labels                        │
│     │  Computes chronological splits                                    │
│     │                                                                    │
│     ▼                                                                    │
│  2. HASH                                                                 │
│     │  Compute SHA-256 of:                                               │
│     │  - feature_version + label_version + source_version                │
│     │  - config snapshot                                                 │
│     │  - feature names (sorted)                                          │
│     │  - split boundaries                                                │
│     │  - record counts                                                   │
│     │                                                                    │
│     ▼                                                                    │
│  3. REGISTER                                                             │
│     │  Insert into dataset_versions (if DB) or save metadata JSON        │
│     │  Link to source versions                                           │
│     │                                                                    │
│     ▼                                                                    │
│  4. VALIDATE                                                             │
│     │  - No future leakage                                               │
│     │  - Chronological splits verified                                   │
│     │  - Label distribution acceptable                                   │
│     │  - Feature completeness acceptable                                 │
│     │                                                                    │
│     ▼                                                                    │
│  5. STORE                                                                │
│     │  Save to data/processed/datasets/                                  │
│     │  Parquet files per split                                           │
│     │  Metadata JSON                                                     │
│     │                                                                    │
│     ▼                                                                    │
│  6. USE                                                                  │
│     │  Training Engine reads dataset                                     │
│     │  Backtesting Engine reads dataset                                  │
│     │                                                                    │
│     ▼                                                                    │
│  7. RETAIN                                                               │
│        Old versions retained for reproducibility                         │
│        New versions supersede old (no deletion)                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.4 Version Immutability Rules

| Rule | Description |
|------|-------------|
| **No mutation** | Once created, a dataset version is never modified |
| **No deletion** | Old versions are retained for reproducibility |
| **Superseded, not deleted** | New versions mark old ones as superseded |
| **Hash-based identity** | Same config + data = same hash = same version |
| **Audit trail** | Every model training references a specific dataset_version |

---

## 7. Storage Format

### 7.1 Format Comparison

| Format | Speed | Compression | Inspection | Versioning | MVP? |
|--------|-------|-------------|------------|------------|------|
| **CSV** | Slow | None | Easy (text) | Manual | ❌ |
| **Parquet** | Fast | Excellent | Moderate | File-based | ✅ |
| **PostgreSQL** | Fast | Built-in | SQL queries | Table-based | ❌ (Phase 2) |

### 7.2 MVP Recommendation

**Use Parquet files for dataset storage.**

**Justification:**
- Columnar format is efficient for ML workloads
- Built-in compression reduces storage
- Pandas native support (read_parquet, to_parquet)
- Versioned via file naming (no overwrites)
- Easy to inspect with standard tools

### 7.3 Storage Layout

```
data/processed/
├── datasets/
│   ├── dataset_v0.1/
│   │   ├── metadata.json              ← Dataset metadata
│   │   ├── train.parquet              ← Training split
│   │   ├── val.parquet                ← Validation split
│   │   ├── test.parquet               ← Test split
│   │   └── feature_names.json         ← Ordered feature names
│   ├── dataset_v0.2/
│   │   └── ...
│   └── dataset_v1.0/
│       └── ...
├── features/
│   ├── features_v0.1.parquet          ← Full feature matrix
│   └── feature_metadata.json
└── labels/
    ├── labels_v0.1.parquet            ← Full label series
    └── label_metadata.json
```

### 7.4 Parquet Schema

```python
# Schema for train.parquet / val.parquet / test.parquet

dataset_schema = {
    # Metadata
    "timestamp": "datetime64[ns]",
    "ticker": "string",  # optional
    
    # Raw values
    "open": "float64",
    "high": "float64",
    "low": "float64",
    "close": "float64",
    "adj_close": "float64",
    "volume": "int64",
    
    # Features (52 columns)
    "returns_1d": "float64",
    "returns_3d": "float64",
    # ... (52 total)
    "gap_pct": "float64",
    
    # Labels
    "label": "string",
    "future_return": "float64"
}
```

---

## 8. Dataset Metadata

### 8.1 Metadata Schema

```python
@dataclass
class DatasetMetadata:
    # Identity
    version: str                    # "v0.1"
    version_hash: str               # SHA-256 hash
    
    # Source versions
    feature_version: str            # "v0.1"
    label_version: str              # "v0.1"
    source_version: str             # "v0.1"
    
    # Creation
    created_at: str                 # ISO timestamp
    created_by: str                 # "pipeline" or "researcher"
    config_snapshot: Dict           # Full config used
    
    # Features
    feature_names: List[str]        # Ordered feature names
    feature_count: int              # Number of features
    
    # Record counts
    total_rows: int                 # Total rows (before split)
    train_rows: int                 # Training set size
    val_rows: int                   # Validation set size
    test_rows: int                  # Test set size
    
    # Split boundaries
    train_start: str                # Training period start
    train_end: str                  # Training period end
    val_start: str                  # Validation period start
    val_end: str                    # Validation period end
    test_start: str                 # Test period start
    test_end: str                   # Test period end
    
    # Quality
    nan_count_total: int            # NaN values in features
    nan_count_per_feature: Dict     # Feature → NaN count
    label_distribution: Dict        # Class → count
    quality_score: float            # Data quality score (0-100)
    
    # File references
    train_file: str                 # Path to train.parquet
    val_file: str                   # Path to val.parquet
    test_file: str                  # Path to test.parquet
```

### 8.2 Metadata Storage

```json
{
  "version": "v0.1",
  "version_hash": "a1b2c3d4e5f6...",
  "feature_version": "v0.1",
  "label_version": "v0.1",
  "source_version": "v0.1",
  "created_at": "2026-09-04T12:00:00Z",
  "feature_count": 52,
  "total_rows": 2465,
  "train_rows": 1725,
  "val_rows": 370,
  "test_rows": 370,
  "train_start": "2016-03-15",
  "train_end": "2023-06-30",
  "val_start": "2023-07-01",
  "val_end": "2024-06-30",
  "test_start": "2024-07-01",
  "test_end": "2025-12-31",
  "label_distribution": {
    "UP": 820,
    "DOWN": 785,
    "HOLD": 860
  },
  "quality_score": 98.5
}
```

---

## 9. Dataset Validation

### 9.1 Validation Checks

| Check ID | Check | Severity | Action |
|----------|-------|----------|--------|
| DVAL-01 | No NaN values in features | ERROR | Reject dataset |
| DVAL-02 | No duplicate rows | ERROR | Reject dataset |
| DVAL-03 | Timestamps in ascending order | ERROR | Reject dataset |
| DVAL-04 | Labels aligned with features | ERROR | Reject dataset |
| DVAL-05 | No future leakage | ERROR | Reject dataset |
| DVAL-06 | Chronological splits (no overlap) | ERROR | Reject dataset |
| DVAL-07 | Minimum split sizes | WARNING | Log warning |
| DVAL-08 | Label distribution acceptable | WARNING | Log warning |
| DVAL-09 | Feature count matches expected | ERROR | Reject dataset |
| DVAL-10 | Data quality score >= 70 | WARNING | Log warning |

### 9.2 Leakage Verification

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       LEAKAGE VERIFICATION                               │
│                                                                          │
│  Test 1: Temporal Separation                                             │
│    - Verify train end < val start                                        │
│    - Verify val end < test start                                         │
│    - Verify no shared timestamps between splits                          │
│                                                                          │
│  Test 2: Feature-Label Separation                                        │
│    - Features use data ≤ T                                               │
│    - Labels use data > T                                                 │
│    - No shared columns between feature and label DataFrames              │
│                                                                          │
│  Test 3: No Future in Features                                           │
│    - Compute F(T) and F(T+1)                                             │
│    - Verify F(T) does not use close_{T+1} or later                      │
│    - Shift test: F(T) == F(T+1) shifted by 1                            │
│                                                                          │
│  Test 4: Label Uses Only Future Data                                     │
│    - Label at T uses close_{T+5}                                         │
│    - Never uses close_T or earlier                                        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Validation Report

```python
@dataclass
class DatasetValidationReport:
    passed: bool                          # Overall pass/fail
    checks_run: int                       # Total checks executed
    checks_passed: int                    # Checks that passed
    errors: int                           # Critical errors
    warnings: int                         # Non-critical issues
    issues: List[DatasetIssue]            # Detailed issues
    leakage_detected: bool                # Whether leakage was found
    quality_score: float                  # Dataset quality score

@dataclass
class DatasetIssue:
    check_id: str                         # "DVAL-01"
    severity: str                         # "error" | "warning"
    description: str                      # Human-readable description
    affected_rows: int                    # Number of rows affected
    recommendation: str                   # How to fix
```

---

## 10. Future Incremental Updates

### 10.1 Incremental Update Strategy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       INCREMENTAL UPDATE STRATEGY                        │
│                                                                          │
│  Problem:                                                                │
│    New data arrives daily. Rebuilding the entire dataset is wasteful.    │
│                                                                          │
│  Solution:                                                               │
│    Append new data to existing dataset without rebuilding.               │
│                                                                          │
│  Strategy:                                                               │
│                                                                          │
│  1. CHECK IF UPDATE NEEDED                                               │
│     │  Compare last timestamp in dataset with today's date               │
│     │  If same → Skip (no new data)                                      │
│     │  If different → Proceed                                            │
│     │                                                                    │
│     ▼                                                                    │
│  2. FETCH NEW DATA                                                       │
│     │  Load new OHLCV data (since last timestamp)                        │
│     │  Validate new data                                                 │
│     │                                                                    │
│     ▼                                                                    │
│  3. COMPUTE NEW FEATURES                                                 │
│     │  Run FeatureEngine on new data only                                │
│     │  Append to existing feature matrix                                 │
│     │                                                                    │
│     ▼                                                                    │
│  4. COMPUTE NEW LABELS                                                   │
│     │  Run LabelEngine on new data only                                  │
│     │  Append to existing label series                                   │
│     │                                                                    │
│     ▼                                                                    │
│  5. UPDATE SPLITS                                                        │
│     │  - Train: unchanged (historical)                                   │
│     │  - Val: unchanged (historical)                                     │
│     │  - Test: append new data to test set                               │
│     │  - OR: recompute splits if ratios change                           │
│     │                                                                    │
│     ▼                                                                    │
│  6. VALIDATE UPDATED DATASET                                             │
│     │  Run all validation checks                                         │
│     │  Verify no new leakage introduced                                  │
│     │                                                                    │
│     ▼                                                                    │
│  7. VERSION AND STORE                                                    │
│     │  Create new version (v0.1 → v0.2)                                  │
│     │  Save updated dataset                                              │
│     │  Retain old version                                                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 10.2 Incremental Update Rules

| Rule | Description |
|------|-------------|
| **Append, don't rebuild** | Add new rows to existing splits |
| **Version increment** | New data → new version |
| **Retain old versions** | Never delete previous versions |
| **Validate before store** | Run all checks on updated dataset |
| **Log everything** | Record what changed and why |

### 10.3 Update Configuration

```yaml
dataset:
  incremental:
    enabled: true
    
    # What to update
    update_scope: "test_only"  # or "all_splits"
    
    # Validation
    validate_before_store: true
    require_no_new_leakage: true
    
    # Versioning
    auto_version_increment: true
    retain_old_versions: true
```

### 10.4 Limitations (MVP)

- **No real-time updates** — batch updates only
- **No automatic retraining** — manual trigger required
- **No drift detection** — future enhancement
- **Simple append logic** — no complex merge strategies

---

## Appendix A: Configuration Reference

```yaml
# config/dataset.yaml — Complete dataset configuration

dataset:
  # Split configuration
  split_ratios:
    train: 0.70
    val: 0.15
    test: 0.15
  
  # Label configuration
  label_type: classification
  label_window: 5
  thresholds:
    up: 0.01
    down: 0.01
  
  # Feature configuration
  feature_version: "v0.1"
  feature_count: 52
  
  # Storage
  storage_format: parquet
  output_dir: "data/processed/datasets"
  
  # Validation
  validation:
    min_quality_score: 70
    require_no_nan: true
    require_chronological: true
  
  # Walk-forward (for backtesting)
  walk_forward:
    train_window: 252
    test_window: 21
    step_size: 21
  
  # Purging/Embargo
  purging:
    enabled: true
    label_window: 5
  embargo:
    enabled: false
    period: 0
```

---

## Appendix B: Cross-Reference to Pipeline

| Pipeline Stage | Dataset Builder Input | Dataset Builder Output |
|---------------|----------------------|----------------------|
| Feature Engine | Feature DataFrame | Features in dataset |
| Label Engine | Label Series | Labels in dataset |
| Dataset Builder | Features + Labels | DatasetSplit object |
| Training Engine | DatasetSplit | TrainedModel |
| Backtesting Engine | DatasetSplit + config | BacktestReport |
| Prediction Service | Features only | Predictions |
