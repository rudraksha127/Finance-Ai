# DATA ARCHITECTURE — Finance AI MVP

> Complete data architecture blueprint for the Finance AI platform.
> Defines the PostgreSQL schema, time-series rules, validation rules, and storage lifecycle.
> The MVP uses file-based storage; this document defines the target database architecture for Phase 2+.

---

## Table of Contents

1. [Data Sources](#1-data-sources)
2. [Database Design](#2-database-design)
3. [Column Definitions](#3-column-definitions)
4. [Time-Series Rules](#4-time-series-rules)
5. [Dataset Versioning](#5-dataset-versioning)
6. [Data Validation Rules](#6-data-validation-rules)
7. [Storage Strategy](#7-storage-strategy)
8. [Feature Storage Strategy](#8-feature-storage-strategy)
9. [Label Storage Strategy](#9-label-storage-strategy)
10. [Future Expansion](#10-future-expansion)

---

## 1. Data Sources

### 1.1 MVP Data Sources

| Source | Description | Frequency | Format | Priority |
|--------|-------------|-----------|--------|----------|
| **OHLCV Candles** | Open, High, Low, Close, Volume per ticker per interval | Daily | CSV/Parquet | P0 |
| **Index Data** | Market index values (S&P 500, NASDAQ, etc.) | Daily | CSV/Parquet | P1 |
| **Corporate Actions** | Splits, dividends, ticker changes | Event-based | CSV | P1 |
| **Trading Calendar** | Market open/close days, holidays | Daily | CSV | P0 |

### 1.2 Data Source Specifications

#### OHLCV Candles (Primary)

| Property | Value |
|----------|-------|
| **Source** | Yahoo Finance, Alpha Vantage, or CSV export |
| **Tickers** | US equities (NYSE, NASDAQ) |
| **Intervals** | Daily (primary), Weekly, Monthly |
| **History** | Up to 10 years (configurable) |
| **Fields** | timestamp, open, high, low, close, adj_close, volume |
| **Granularity** | One row per ticker per trading day |

#### Index Data

| Property | Value |
|----------|-------|
| **Source** | Same as OHLCV |
| **Indices** | ^GSPC (S&P 500), ^IXIC (NASDAQ), ^DJI (Dow Jones) |
| **Purpose** | Benchmark comparison, market regime detection |
| **Fields** | timestamp, open, high, low, close, volume |

#### Corporate Actions

| Property | Value |
|----------|-------|
| **Source** | SEC filings, exchange data |
| **Types** | Stock splits, dividends, ticker symbol changes |
| **Purpose** | Adjust historical prices, avoid survivorship bias |
| **Fields** | ticker, action_type, effective_date, ratio, amount |

#### Trading Calendar

| Property | Value |
|----------|-------|
| **Source** | Exchange calendars (NYSE, NASDAQ) |
| **Purpose** | Identify trading days, handle holidays |
| **Fields** | date, is_trading_day, exchange, session_type |

---

## 2. Database Design

### 2.1 Entity-Relationship Diagram

```
┌─────────────────┐         ┌─────────────────────────┐
│   instruments   │         │     market_candles       │
│─────────────────│         │─────────────────────────│
│ PK instrument_id│◄────────│ FK instrument_id        │
│    ticker       │         │ PK candle_id            │
│    name         │         │    timestamp            │
│    exchange     │         │    open                 │
│    sector       │         │    high                 │
│    industry     │         │    low                  │
│    market_cap   │         │    close                │
│    is_active    │         │    adj_close            │
│    first_seen   │         │    volume               │
│    last_updated │         │    interval             │
└─────────────────┘         │    source               │
                            │    ingested_at          │
                            └─────────────────────────┘
                                      │
                                      │ FK instrument_id
                                      ▼
┌──────────────────────┐    ┌─────────────────────────┐
│  corporate_actions   │    │   trading_calendar      │
│──────────────────────│    │─────────────────────────│
│ PK action_id         │    │ PK calendar_date        │
│ FK instrument_id     │    │    date                 │
│    action_type       │    │    is_trading_day       │
│    effective_date    │    │    exchange             │
│    ratio             │    │    session_type         │
│    amount            │    └─────────────────────────┘
│    description       │
│    source            │
│    ingested_at       │
└──────────────────────┘

                            ┌─────────────────────────┐
                            │      features           │
                            │─────────────────────────│
                            │ PK feature_id           │
                            │ FK instrument_id        │
                            │ FK dataset_version_id   │
                            │    timestamp            │
                            │    feature_name         │
                            │    feature_category     │
                            │    feature_value        │
                            │    lookback_window      │
                            │    is_nan               │
                            │    computed_at          │
                            └─────────────────────────┘
                                      │
                                      │ FK dataset_version_id
                                      ▼
┌─────────────────────────┐    ┌─────────────────────────┐
│   dataset_versions      │    │       labels            │
│─────────────────────────│    │─────────────────────────│
│ PK dataset_version_id   │◄───│ PK label_id             │
│    version_hash         │    │ FK instrument_id        │
│    created_at           │    │ FK dataset_version_id   │
│    config_snapshot      │    │    timestamp            │
│    feature_count        │    │    label_value          │
│    record_count         │    │    forward_return       │
│    split_train_count    │    │    forward_window       │
│    split_val_count      │    │    threshold_up         │
│    split_test_count     │    │    threshold_down       │
│    train_start          │    │    computed_at          │
│    train_end            │    └─────────────────────────┘
│    val_start            │
│    val_end              │
│    test_start           │
│    test_end             │
│    description          │
└─────────────────────────┘
              │
              │ FK dataset_version_id
              ▼
┌─────────────────────────┐
│    model_predictions    │
│─────────────────────────│
│ PK prediction_id        │
│ FK model_version_id     │
│ FK instrument_id        │
│    timestamp            │
│    predicted_label      │
│    probability_up       │
│    probability_down     │
│    probability_hold     │
│    confidence           │
│    actual_label         │
│    is_correct           │
│    predicted_at         │
└─────────────────────────┘
```

### 2.2 Table Summary

| Table | Purpose | Row Estimate (10yr, 100 tickers) |
|-------|---------|--------------------------------|
| `instruments` | Ticker metadata | ~500 |
| `market_candles` | OHLCV price data | ~250,000 |
| `corporate_actions` | Splits, dividends | ~5,000 |
| `trading_calendar` | Trading days | ~2,500 |
| `features` | Computed indicators | ~8,000,000 (250K × 32 features) |
| `labels` | Classification labels | ~250,000 |
| `dataset_versions` | Dataset snapshots | ~100 |
| `model_predictions` | Prediction history | ~250,000 |

---

## 3. Column Definitions

### 3.1 instruments

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `instrument_id` | SERIAL | No | auto | Primary key |
| `ticker` | VARCHAR(10) | No | — | Unique ticker symbol (e.g., "AAPL") |
| `name` | VARCHAR(255) | Yes | NULL | Company name |
| `exchange` | VARCHAR(20) | Yes | NULL | Exchange (NYSE, NASDAQ) |
| `sector` | VARCHAR(50) | Yes | NULL | GICS sector |
| `industry` | VARCHAR(100) | Yes | NULL | GICS industry |
| `market_cap` | BIGINT | Yes | NULL | Market capitalization (USD) |
| `is_active` | BOOLEAN | No | TRUE | Whether ticker is actively traded |
| `first_seen` | TIMESTAMP | No | NOW() | When ticker was first ingested |
| `last_updated` | TIMESTAMP | No | NOW() | Last modification timestamp |

**Constraints:**
- `UNIQUE (ticker)`
- `CHECK (ticker ~ '^[A-Z]{1,5}(\.[A-Z])?$')` — ticker format validation

**Indexes:**
- `CREATE UNIQUE INDEX idx_instruments_ticker ON instruments(ticker);`
- `CREATE INDEX idx_instruments_exchange ON instruments(exchange);`

---

### 3.2 market_candles

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `candle_id` | BIGSERIAL | No | auto | Primary key |
| `instrument_id` | INTEGER | No | — | FK → instruments.instrument_id |
| `timestamp` | TIMESTAMP | No | — | Candle open timestamp (UTC) |
| `open` | NUMERIC(12,4) | No | — | Opening price |
| `high` | NUMERIC(12,4) | No | — | Highest price during interval |
| `low` | NUMERIC(12,4) | No | — | Lowest price during interval |
| `close` | NUMERIC(12,4) | No | — | Closing price |
| `adj_close` | NUMERIC(12,4) | Yes | NULL | Adjusted close (splits/dividends) |
| `volume` | BIGINT | No | 0 | Trading volume (shares) |
| `interval` | VARCHAR(10) | No | '1d' | Candle interval (1d, 1wk, 1mo) |
| `source` | VARCHAR(50) | No | — | Data source identifier |
| `ingested_at` | TIMESTAMP | No | NOW() | When row was ingested |

**Constraints:**
- `FK (instrument_id) → instruments(instrument_id)`
- `CHECK (open > 0)`
- `CHECK (high > 0)`
- `CHECK (low > 0)`
- `CHECK (close > 0)`
- `CHECK (high >= GREATEST(open, close))`
- `CHECK (low <= LEAST(open, close))`
- `CHECK (volume >= 0)`
- `CHECK (interval IN ('1d', '1wk', '1mo'))`
- `UNIQUE (instrument_id, timestamp, interval)`

**Indexes:**
```sql
CREATE INDEX idx_candles_instrument_ts ON market_candles(instrument_id, timestamp);
CREATE INDEX idx_candles_timestamp ON market_candles(timestamp);
CREATE INDEX idx_candles_interval ON market_candles(interval);
```

**Partition Strategy (Future):**
```sql
-- Partition by timestamp for large datasets
CREATE TABLE market_candles (
    ...
) PARTITION BY RANGE (timestamp);

CREATE TABLE market_candles_2020 PARTITION OF market_candles
    FOR VALUES FROM ('2020-01-01') TO ('2021-01-01');
-- ... one partition per year
```

---

### 3.3 corporate_actions

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `action_id` | SERIAL | No | auto | Primary key |
| `instrument_id` | INTEGER | No | — | FK → instruments.instrument_id |
| `action_type` | VARCHAR(20) | No | — | Type of action |
| `effective_date` | DATE | No | — | When action takes effect |
| `ratio` | NUMERIC(10,6) | Yes | NULL | Split ratio (2.0 = 2-for-1 split) |
| `amount` | NUMERIC(10,4) | Yes | NULL | Dividend amount (USD) |
| `description` | TEXT | Yes | NULL | Human-readable description |
| `source` | VARCHAR(50) | No | — | Data source identifier |
| `ingested_at` | TIMESTAMP | No | NOW() | When row was ingested |

**Constraints:**
- `FK (instrument_id) → instruments(instrument_id)`
- `CHECK (action_type IN ('split', 'dividend', 'ticker_change', 'merger', 'delisting'))`
- `CHECK (ratio > 0)` — when applicable
- `CHECK (amount >= 0)` — when applicable

**Indexes:**
```sql
CREATE INDEX idx_actions_instrument ON corporate_actions(instrument_id);
CREATE INDEX idx_actions_date ON corporate_actions(effective_date);
CREATE INDEX idx_actions_type ON corporate_actions(action_type);
```

---

### 3.4 trading_calendar

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `calendar_date` | DATE | No | — | Primary key (date) |
| `is_trading_day` | BOOLEAN | No | TRUE | Whether market is open |
| `exchange` | VARCHAR(20) | No | 'NYSE' | Exchange identifier |
| `session_type` | VARCHAR(20) | No | 'regular' | regular, early_close, holiday |

**Constraints:**
- `PK (calendar_date, exchange)`
- `CHECK (session_type IN ('regular', 'early_close', 'holiday'))`

**Indexes:**
```sql
CREATE INDEX idx_calendar_trading ON trading_calendar(is_trading_day);
CREATE INDEX idx_calendar_exchange ON trading_calendar(exchange);
```

---

### 3.5 features

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `feature_id` | BIGSERIAL | No | auto | Primary key |
| `instrument_id` | INTEGER | No | — | FK → instruments.instrument_id |
| `dataset_version_id` | INTEGER | No | — | FK → dataset_versions.dataset_version_id |
| `timestamp` | TIMESTAMP | No | — | Observation timestamp |
| `feature_name` | VARCHAR(100) | No | — | Feature identifier (e.g., "returns_5d") |
| `feature_category` | VARCHAR(50) | No | — | Category (returns, volatility, etc.) |
| `feature_value` | DOUBLE PRECISION | Yes | NULL | Computed feature value |
| `lookback_window` | INTEGER | Yes | NULL | Lookback period used |
| `is_nan` | BOOLEAN | No | FALSE | Whether value is NaN |
| `computed_at` | TIMESTAMP | No | NOW() | When feature was computed |

**Constraints:**
- `FK (instrument_id) → instruments(instrument_id)`
- `FK (dataset_version_id) → dataset_versions(dataset_version_id)`
- `CHECK (feature_category IN ('returns', 'volatility', 'volume', 'momentum', 'mean_reversion'))`

**Indexes:**
```sql
CREATE INDEX idx_features_instrument ON features(instrument_id);
CREATE INDEX idx_features_dataset ON features(dataset_version_id);
CREATE INDEX idx_features_timestamp ON features(timestamp);
CREATE INDEX idx_features_name ON features(feature_name);
CREATE INDEX idx_features_instrument_ts ON features(instrument_id, timestamp);
CREATE INDEX idx_features_dataset_ts ON features(dataset_version_id, instrument_id, timestamp);
```

**Storage Note:**
Features are stored in EAV (Entity-Attribute-Value) format for flexibility. For performance-critical queries, a pivoted/materialized view can be created:

```sql
CREATE MATERIALIZED VIEW features_pivoted AS
SELECT
    instrument_id,
    timestamp,
    MAX(CASE WHEN feature_name = 'returns_5d' THEN feature_value END) AS returns_5d,
    MAX(CASE WHEN feature_name = 'returns_10d' THEN feature_value END) AS returns_10d,
    -- ... one column per feature
FROM features
WHERE is_nan = FALSE
GROUP BY instrument_id, timestamp;
```

---

### 3.6 labels

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `label_id` | BIGSERIAL | No | auto | Primary key |
| `instrument_id` | INTEGER | No | — | FK → instruments.instrument_id |
| `dataset_version_id` | INTEGER | No | — | FK → dataset_versions.dataset_version_id |
| `timestamp` | TIMESTAMP | No | — | Observation timestamp |
| `label_value` | VARCHAR(4) | No | — | Classification label (UP, DOWN, HOLD) |
| `forward_return` | DOUBLE PRECISION | Yes | NULL | Actual forward return (for auditing) |
| `forward_window` | INTEGER | No | — | Forward window used |
| `threshold_up` | DOUBLE PRECISION | No | — | Threshold for UP classification |
| `threshold_down` | DOUBLE PRECISION | No | — | Threshold for DOWN classification |
| `computed_at` | TIMESTAMP | No | NOW() | When label was computed |

**Constraints:**
- `FK (instrument_id) → instruments(instrument_id)`
- `FK (dataset_version_id) → dataset_versions(dataset_version_id)`
- `CHECK (label_value IN ('UP', 'DOWN', 'HOLD'))`
- `CHECK (forward_window > 0)`
- `CHECK (threshold_up > 0)`
- `CHECK (threshold_down > 0)`

**Indexes:**
```sql
CREATE INDEX idx_labels_instrument ON labels(instrument_id);
CREATE INDEX idx_labels_dataset ON labels(dataset_version_id);
CREATE INDEX idx_labels_timestamp ON labels(timestamp);
CREATE INDEX idx_labels_value ON labels(label_value);
CREATE INDEX idx_labels_instrument_ts ON labels(instrument_id, timestamp);
```

---

### 3.7 dataset_versions

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `dataset_version_id` | SERIAL | No | auto | Primary key |
| `version_hash` | VARCHAR(64) | No | — | SHA-256 hash of dataset config + data |
| `created_at` | TIMESTAMP | No | NOW() | When version was created |
| `config_snapshot` | JSONB | No | — | Full config used to create dataset |
| `feature_count` | INTEGER | No | — | Number of features |
| `record_count` | INTEGER | No | — | Total number of records |
| `split_train_count` | INTEGER | No | — | Training set size |
| `split_val_count` | INTEGER | No | — | Validation set size |
| `split_test_count` | INTEGER | No | — | Test set size |
| `train_start` | TIMESTAMP | No | — | Training period start |
| `train_end` | TIMESTAMP | No | — | Training period end |
| `val_start` | TIMESTAMP | No | — | Validation period start |
| `val_end` | TIMESTAMP | No | — | Validation period end |
| `test_start` | TIMESTAMP | No | — | Test period start |
| `test_end` | TIMESTAMP | No | — | Test period end |
| `description` | TEXT | Yes | NULL | Human-readable description |

**Constraints:**
- `UNIQUE (version_hash)`
- `CHECK (split_train_count + split_val_count + split_test_count = record_count)`
- `CHECK (train_end < val_start)`
- `CHECK (val_end < test_start)`

**Indexes:**
```sql
CREATE UNIQUE INDEX idx_dataset_hash ON dataset_versions(version_hash);
CREATE INDEX idx_dataset_created ON dataset_versions(created_at);
```

---

### 3.8 model_predictions

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `prediction_id` | BIGSERIAL | No | auto | Primary key |
| `model_version_id` | INTEGER | Yes | NULL | FK → model_versions.model_version_id (future) |
| `instrument_id` | INTEGER | No | — | FK → instruments.instrument_id |
| `timestamp` | TIMESTAMP | No | — | Prediction timestamp (when made) |
| `target_timestamp` | TIMESTAMP | No | — | Timestamp being predicted |
| `predicted_label` | VARCHAR(4) | No | — | Predicted class (UP, DOWN, HOLD) |
| `probability_up` | DOUBLE PRECISION | No | — | P(UP) |
| `probability_down` | DOUBLE PRECISION | No | — | P(DOWN) |
| `probability_hold` | DOUBLE PRECISION | No | — | P(HOLD) |
| `confidence` | DOUBLE PRECISION | No | — | max(probabilities) |
| `actual_label` | VARCHAR(4) | Yes | NULL | True label (filled after market close) |
| `is_correct` | BOOLEAN | Yes | NULL | Whether prediction was correct |
| `predicted_at` | TIMESTAMP | No | NOW() | When prediction was made |

**Constraints:**
- `FK (instrument_id) → instruments(instrument_id)`
- `CHECK (predicted_label IN ('UP', 'DOWN', 'HOLD'))`
- `CHECK (actual_label IS NULL OR actual_label IN ('UP', 'DOWN', 'HOLD'))`
- `CHECK (probability_up + probability_down + probability_hold BETWEEN 0.99 AND 1.01)` — allow floating point tolerance
- `CHECK (confidence = GREATEST(probability_up, probability_down, probability_hold))`

**Indexes:**
```sql
CREATE INDEX idx_predictions_instrument ON model_predictions(instrument_id);
CREATE INDEX idx_predictions_timestamp ON model_predictions(timestamp);
CREATE INDEX idx_predictions_target ON model_predictions(target_timestamp);
CREATE INDEX idx_predictions_label ON model_predictions(predicted_label);
CREATE INDEX idx_predictions_instrument_ts ON model_predictions(instrument_id, timestamp);
```

---

## 4. Time-Series Rules

### 4.1 Timestamp Format

| Rule | Value |
|------|-------|
| **Format** | ISO 8601: `YYYY-MM-DDTHH:MM:SSZ` |
| **Timezone** | UTC (all timestamps stored in UTC) |
| **Resolution** | Day-level for daily data (time set to `00:00:00Z`) |
| **Storage** | `TIMESTAMP` (without timezone — stores UTC) |

### 4.2 Timezone Handling

```
Source Data (any timezone)
    │
    ▼
Convert to UTC at ingestion
    │
    ▼
Store as TIMESTAMP (UTC)
    │
    ▼
Display in user-local timezone (dashboard only)
```

**Rules:**
- All timestamps stored in UTC
- Conversion to local time happens only at display layer
- No timezone-aware timestamps in database (simplifies queries)
- Ingestion logs original timezone for audit trail

### 4.3 Candle Interval Support

| Interval | PostgreSQL Value | Description | Use Case |
|----------|-----------------|-------------|----------|
| Daily | `'1d'` | One candle per trading day | Primary MVP interval |
| Weekly | `'1wk'` | One candle per week | Longer-term analysis |
| Monthly | `'1mo'` | One candle per month | Trend analysis |

**Rules:**
- Interval stored as string column (not embedded in timestamp)
- Same table supports multiple intervals via `interval` column
- Queries filter by interval: `WHERE interval = '1d'`
- Unique constraint includes interval: `UNIQUE (instrument_id, timestamp, interval)`

### 4.4 Partition Strategy

**MVP:** No partitioning (file-based storage).

**Phase 2 (PostgreSQL):**

```
Partitioning Strategy:
├── Primary: RANGE partitioning on timestamp (yearly)
├── Secondary: Hash partitioning on instrument_id (optional)
└── Retention: Auto-drop old partitions (configurable)

Benefits:
├── Faster queries on recent data
├── Easier data lifecycle management
├── Parallel query execution
└── Smaller index sizes per partition
```

**Partition Template:**
```sql
-- Yearly partitions for market_candles
CREATE TABLE market_candles_y2020 PARTITION OF market_candles
    FOR VALUES FROM ('2020-01-01') TO ('2021-01-01');
CREATE TABLE market_candles_y2021 PARTITION OF market_candles
    FOR VALUES FROM ('2021-01-01') TO ('2022-01-01');
-- ... auto-generate with pg_partman
```

### 4.5 Index Strategy

| Table | Primary Index | Secondary Indexes | Purpose |
|-------|--------------|-------------------|---------|
| `instruments` | `instrument_id` | `ticker` (unique), `exchange` | Fast ticker lookup |
| `market_candles` | `candle_id` | `(instrument_id, timestamp)`, `timestamp` | Time-range queries |
| `corporate_actions` | `action_id` | `(instrument_id)`, `effective_date` | Action lookup |
| `trading_calendar` | `(calendar_date, exchange)` | `is_trading_day` | Trading day check |
| `features` | `feature_id` | `(instrument_id, timestamp)`, `(dataset_version_id, instrument_id, timestamp)` | Feature retrieval |
| `labels` | `label_id` | `(instrument_id, timestamp)`, `(dataset_version_id, instrument_id, timestamp)` | Label retrieval |
| `dataset_versions` | `dataset_version_id` | `version_hash` (unique) | Version lookup |
| `model_predictions` | `prediction_id` | `(instrument_id, timestamp)`, `target_timestamp` | Prediction retrieval |

---

## 5. Dataset Versioning

### 5.1 Version Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                    Dataset Version Lifecycle                 │
│                                                              │
│  1. CREATE                                                   │
│     │  Feature Engine computes features                      │
│     │  Label Engine generates labels                         │
│     │  Dataset Builder assembles splits                      │
│     │                                                        │
│     ▼                                                        │
│  2. HASH                                                     │
│     │  Compute SHA-256 of:                                   │
│     │  - Config snapshot (all parameters)                    │
│     │  - Feature names + count                               │
│     │  - Split boundaries                                    │
│     │  - Record counts                                       │
│     │                                                        │
│     ▼                                                        │
│  3. REGISTER                                                 │
│     │  Insert into dataset_versions table                    │
│     │  Link features and labels via dataset_version_id       │
│     │                                                        │
│     ▼                                                        │
│  4. VALIDATE                                                 │
│     │  - No future leakage in features                       │
│     │  - Chronological splits verified                       │
│     │  - Label distribution acceptable                       │
│     │  - Feature completeness acceptable                     │
│     │                                                        │
│     ▼                                                        │
│  5. USE                                                      │
│     │  Training Engine reads features + labels               │
│     │  Backtesting Engine reads features + labels            │
│     │                                                        │
│     ▼                                                        │
│  6. RETAIN                                                   │
│        Old versions retained for audit                       │
│        New versions supersede old (no deletion)              │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Version Hash Calculation

```python
import hashlib
import json

def compute_version_hash(config: dict, feature_names: list, 
                         split_boundaries: dict, record_counts: dict) -> str:
    """Compute deterministic hash for dataset version."""
    version_input = {
        "config": config,
        "feature_names": sorted(feature_names),
        "split_boundaries": split_boundaries,
        "record_counts": record_counts
    }
    version_string = json.dumps(version_input, sort_keys=True, default=str)
    return hashlib.sha256(version_string.encode()).hexdigest()
```

### 5.3 Version Immutability Rules

| Rule | Description |
|------|-------------|
| **No mutation** | Once created, a dataset version is never modified |
| **No deletion** | Old versions are retained for audit |
| **Superseded, not deleted** | New versions mark old ones as superseded |
| **Hash-based identity** | Same config + data = same hash = same version |
| **Audit trail** | Every model training references a specific dataset_version_id |

### 5.4 Version Metadata

Each dataset version stores:
- Full config snapshot (JSONB) — every parameter used
- Split boundaries (timestamps) — exact date ranges
- Record counts — total, train, val, test
- Feature list — names, categories, count
- Creation timestamp — when version was generated
- SHA-256 hash — unique identifier

---

## 6. Data Validation Rules

### 6.1 OHLCV Validation Rules

| Rule ID | Rule | Severity | Action |
|---------|------|----------|--------|
| VAL-001 | Required columns present | ERROR | Reject file |
| VAL-002 | No null values in required columns | ERROR | Reject row/file |
| VAL-003 | Timestamps in ascending order | ERROR | Reject file |
| VAL-004 | No duplicate timestamps per ticker | ERROR | Reject file |
| VAL-005 | `open > 0` | ERROR | Reject row |
| VAL-006 | `high > 0` | ERROR | Reject row |
| VAL-007 | `low > 0` | ERROR | Reject row |
| VAL-008 | `close > 0` | ERROR | Reject row |
| VAL-009 | `volume >= 0` | ERROR | Reject row |
| VAL-010 | `high >= max(open, close)` | ERROR | Reject row |
| VAL-011 | `low <= min(open, close)` | ERROR | Reject row |
| VAL-012 | Missing data percentage < threshold | WARNING | Log, proceed |
| VAL-013 | Price change > 50% in single period | WARNING | Log, flag |
| VAL-014 | Volume = 0 on non-holiday | WARNING | Log, flag |
| VAL-015 | Data freshness (not stale) | WARNING | Log, flag |

### 6.2 Feature Validation Rules

| Rule ID | Rule | Severity | Action |
|---------|------|----------|--------|
| VAL-F01 | No future information in features | ERROR | Reject dataset |
| VAL-F02 | Feature computation is deterministic | ERROR | Reject dataset |
| VAL-F03 | NaN count per feature < threshold | WARNING | Log, flag |
| VAL-F04 | Feature values within reasonable range | WARNING | Log, flag |
| VAL-F05 | All required features computed | ERROR | Reject dataset |

### 6.3 Label Validation Rules

| Rule ID | Rule | Severity | Action |
|---------|------|----------|--------|
| VAL-L01 | Label distribution not degenerate (< 10% in any class) | WARNING | Log, flag |
| VAL-L02 | Labels aligned with feature timestamps | ERROR | Reject dataset |
| VAL-L03 | No label information in features | ERROR | Reject dataset |
| VAL-L04 | Forward window > 0 | ERROR | Reject config |

### 6.4 Dataset Validation Rules

| Rule ID | Rule | Severity | Action |
|---------|------|----------|--------|
| VAL-D01 | Splits are chronological (no overlap) | ERROR | Reject dataset |
| VAL-D02 | Train end < Validation start | ERROR | Reject dataset |
| VAL-D03 | Validation end < Test start | ERROR | Reject dataset |
| VAL-D04 | No data leakage between splits | ERROR | Reject dataset |
| VAL-D05 | Minimum split sizes met | WARNING | Log, flag |

### 6.5 Validation Report Structure

```python
@dataclass
class ValidationReport:
    passed: bool                          # Overall pass/fail
    rules_checked: int                    # Number of rules evaluated
    rules_passed: int                     # Number of rules passed
    issues: List[ValidationIssue]         # List of issues found
    summary: Dict[str, int]               # Counts by severity

@dataclass
class ValidationIssue:
    rule_id: str                          # "VAL-001"
    severity: str                         # "error" | "warning"
    column: str                           # Column name (or "schema", "timestamp")
    message: str                          # Human-readable description
    affected_rows: int                    # Number of rows affected
    sample_values: List[Any]              # Example values (for debugging)
```

---

## 7. Storage Strategy

### 7.1 Three-Tier Storage

```
┌─────────────────────────────────────────────────────────────┐
│                    Storage Lifecycle                          │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    RAW TIER                          │    │
│  │  Location:  data/raw/                                │    │
│  │  Format:    CSV/Parquet (as-ingested)                │    │
│  │  Immutability: NEVER modified after ingestion        │    │
│  │  Retention:  Permanent                                │    │
│  │  Purpose:    Source of truth, audit trail             │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                   INTERIM TIER                       │    │
│  │  Location:  data/interim/                            │    │
│  │  Format:    Parquet (compressed)                     │    │
│  │  Immutability: Regenerated on each pipeline run      │    │
│  │  Retention:  Overwritten on regeneration             │    │
│  │  Purpose:    Intermediate processing results         │    │
│  │  Contents:   Validated data, cleaned data            │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                  PROCESSED TIER                      │    │
│  │  Location:  data/processed/                          │    │
│  │  Format:    Parquet (compressed)                     │    │
│  │  Immutability: Versioned (never overwrite)           │    │
│  │  Retention:  Permanent (versioned)                   │    │
│  │  Purpose:    Feature matrices, labels, datasets      │    │
│  │  Contents:   Features, labels, train/val/test splits │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Storage Rules

| Rule | Description |
|------|-------------|
| **Raw is immutable** | Never modify files in `data/raw/` after ingestion |
| **Interim is ephemeral** | Files in `data/interim/` can be regenerated |
| **Processed is versioned** | Files in `data/processed/` are versioned, never overwritten |
| **No secrets in data** | Data files contain no API keys or credentials |
| **Git-ignores data** | Large data files excluded from version control |
| **Compression** | Parquet format for interim and processed (gzip/snappy) |

### 7.3 File Naming Conventions

```
data/raw/
├── AAPL_daily.csv                    ← Single ticker
├── MSFT_daily.csv
├── all_tickers_daily.csv             ← Multi-ticker
└── index_SP500_daily.csv             ← Index data

data/interim/
├── validated_20260904_123456.parquet ← Timestamped
├── cleaned_20260904_123456.parquet
└── features_temp_20260904_123456.parquet

data/processed/
├── features_v1.0.0-20260904.parquet  ← Versioned
├── labels_v1.0.0-20260904.parquet
├── dataset_v1.0.0-20260904/
│   ├── train.parquet
│   ├── val.parquet
│   └── test.parquet
└── dataset_v1.0.0-20260905/
    └── ...
```

### 7.4 File Size Estimation

| Dataset | Rows | Columns | Format | Estimated Size |
|---------|------|---------|--------|---------------|
| Raw OHLCV (100 tickers, 10yr) | 250,000 | 7 | CSV | ~25 MB |
| Raw OHLCV (100 tickers, 10yr) | 250,000 | 7 | Parquet | ~5 MB |
| Features (100 tickers, 10yr) | 250,000 | 32 | Parquet | ~15 MB |
| Labels (100 tickers, 10yr) | 250,000 | 1 | Parquet | ~1 MB |
| Train split (70%) | 175,000 | 33 | Parquet | ~12 MB |
| Model artifact | — | — | joblib | ~10 MB |

---

## 8. Feature Storage Strategy

### 8.1 Feature Storage Options

| Option | Format | Use Case | Performance |
|--------|--------|----------|-------------|
| **EAV Table** | PostgreSQL `features` | Flexible, queryable | Moderate (pivot needed) |
| **Wide Table** | PostgreSQL `features_wide` | Fast reads, fixed schema | Fast (direct read) |
| **Parquet Files** | `data/processed/features_*.parquet` | File-based MVP | Fast (columnar) |
| **Materialized View** | PostgreSQL `features_pivoted` | Cached pivot | Fast (pre-computed) |

### 8.2 EAV vs Wide Table Trade-offs

```
EAV (Entity-Attribute-Value)          Wide Table (One Column per Feature)
────────────────────────────          ──────────────────────────────────
+ Flexible: add features without      + Fast reads: single row = all features
  schema changes                      + Simple queries: no pivot needed
+ Sparse data efficient               + Pandas-native format
+ Easy to audit individual features   - Schema changes when features added
- Requires pivot for ML               - Sparse data wastes storage
- Slower for bulk reads               - Harder to audit individual features
```

**MVP Decision:** Use Parquet files in `data/processed/` for feature storage. EAV table in PostgreSQL for Phase 2.

### 8.3 Feature Metadata

Every feature is stored with metadata:

```python
@dataclass
class FeatureMetadata:
    name: str               # "returns_5d"
    category: str           # "returns"
    lookback_window: int    # 5
    formula: str            # "returns(close, 5)"
    data_type: str          # "float64"
    nan_count: int          # 200
    computed_at: datetime   # When computed
    config_hash: str        # Hash of config used
```

### 8.4 Feature Versioning

| Rule | Description |
|------|-------------|
| **Config-driven** | Features are versioned by the config that produced them |
| **Hash-based** | Same config + data = same feature set = same version |
| **Immutable** | Once computed, feature sets are never modified |
| **Traceable** | Every feature links to its computation config and source data |

---

## 9. Label Storage Strategy

### 9.1 Label Schema

Labels are stored in the `labels` table with explicit separation from features:

```
┌─────────────────────────────────────────────────────────────┐
│                 Label-Feature Separation                     │
│                                                              │
│  Features Table                  Labels Table                │
│  ──────────────                  ────────────                │
│  instrument_id                   instrument_id                │
│  timestamp                       timestamp                    │
│  feature_name                    label_value                  │
│  feature_value                   forward_return               │
│  ...                             forward_window               │
│                                                              │
│  ⚠️  CRITICAL: Features use PAST data                       │
│     Labels use FUTURE data                                  │
│     They are stored in SEPARATE tables                      │
│     Joined ONLY at dataset assembly time                    │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 Label Lifecycle

```
1. RAW PRICES (market_candles)
   │
   ▼
2. COMPUTE FORWARD RETURN (Label Engine)
   │  forward_return = (close_{t+n} - close_t) / close_t
   │  Uses FUTURE close prices
   │
   ▼
3. CLASSIFY (Label Engine)
   │  if forward_return > threshold_up → "UP"
   │  if forward_return < -threshold_down → "DOWN"
   │  else → "HOLD"
   │
   ▼
4. STORE (labels table)
   │  instrument_id, timestamp, label_value
   │  forward_return (for auditing)
   │  forward_window, thresholds (for reproducibility)
   │
   ▼
5. JOIN WITH FEATURES (Dataset Builder)
   │  Only at dataset assembly time
   │  Joined on (instrument_id, timestamp)
   │  ⚠️  Features must NOT contain label information
   │
   ▼
6. CHRONOLOGICAL SPLIT
   train: timestamps < split_1
   val:   split_1 <= timestamps < split_2
   test:  timestamps >= split_2
```

### 9.3 Leakage Prevention

| Protection | Description |
|------------|-------------|
| **Separate tables** | Features and labels in different tables |
| **No shared computation** | Feature engine never reads label data |
| **Temporal isolation** | Features use past, labels use future |
| **Integration tests** | Automated tests verify no leakage |
| **Audit trail** | `forward_return` stored for verification |

### 9.4 Label Distribution Monitoring

```sql
-- Check label distribution for a dataset version
SELECT 
    label_value,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as pct
FROM labels
WHERE dataset_version_id = 1
GROUP BY label_value
ORDER BY label_value;
```

**Expected Distribution (for 1% threshold):**
| Label | Expected % | Acceptable Range |
|-------|-----------|-----------------|
| UP | ~33% | 25-45% |
| DOWN | ~33% | 25-45% |
| HOLD | ~34% | 20-50% |

---

## 10. Future Expansion

### 10.1 Reserved Tables (Placeholders)

#### News Data

```sql
-- Placeholder: Future news/sentiment data
CREATE TABLE news_articles (
    article_id SERIAL PRIMARY KEY,
    instrument_id INTEGER REFERENCES instruments(instrument_id),
    published_at TIMESTAMP NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    source VARCHAR(50) NOT NULL,
    sentiment_score DOUBLE PRECISION,
    sentiment_label VARCHAR(10),  -- positive, negative, neutral
    relevance_score DOUBLE PRECISION,
    ingested_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE news_sentiment_daily (
    instrument_id INTEGER REFERENCES instruments(instrument_id),
    date DATE NOT NULL,
    avg_sentiment DOUBLE PRECISION,
    article_count INTEGER,
    positive_count INTEGER,
    negative_count INTEGER,
    PRIMARY KEY (instrument_id, date)
);
```

#### Options Data

```sql
-- Placeholder: Future options chain data
CREATE TABLE options_chain (
    option_id SERIAL PRIMARY KEY,
    instrument_id INTEGER REFERENCES instruments(instrument_id),
    expiry_date DATE NOT NULL,
    strike_price NUMERIC(12,4) NOT NULL,
    option_type VARCHAR(4) NOT NULL,  -- CALL, PUT
    bid NUMERIC(12,4),
    ask NUMERIC(12,4),
    last_price NUMERIC(12,4),
    volume INTEGER,
    open_interest INTEGER,
    implied_volatility DOUBLE PRECISION,
    snapshot_date TIMESTAMP NOT NULL,
    ingested_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE options_daily_metrics (
    instrument_id INTEGER REFERENCES instruments(instrument_id),
    date DATE NOT NULL,
    avg_implied_volatility DOUBLE PRECISION,
    put_call_ratio DOUBLE PRECISION,
    max_pain_price NUMERIC(12,4),
    PRIMARY KEY (instrument_id, date)
);
```

#### Order Book Data

```sql
-- Placeholder: Future order book snapshots
CREATE TABLE order_book_snapshots (
    snapshot_id BIGSERIAL PRIMARY KEY,
    instrument_id INTEGER REFERENCES instruments(instrument_id),
    timestamp TIMESTAMP NOT NULL,
    bid_price_1 NUMERIC(12,4),
    bid_volume_1 INTEGER,
    ask_price_1 NUMERIC(12,4),
    ask_volume_1 INTEGER,
    bid_price_2 NUMERIC(12,4),
    bid_volume_2 INTEGER,
    ask_price_2 NUMERIC(12,4),
    ask_volume_2 INTEGER,
    spread_bps DOUBLE PRECISION,
    ingested_at TIMESTAMP DEFAULT NOW()
);
```

#### Macro Data

```sql
-- Placeholder: Future macroeconomic indicators
CREATE TABLE macro_indicators (
    indicator_id SERIAL PRIMARY KEY,
    indicator_name VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    source VARCHAR(50) NOT NULL,
    unit VARCHAR(20),
    frequency VARCHAR(10),  -- daily, monthly, quarterly
    ingested_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (indicator_name, date)
);

-- Example indicators: GDP, CPI, Fed Funds Rate, VIX, Treasury Yields
```

#### Risk Metrics

```sql
-- Placeholder: Future risk engine outputs
CREATE TABLE risk_metrics (
    risk_id SERIAL PRIMARY KEY,
    instrument_id INTEGER REFERENCES instruments(instrument_id),
    date DATE NOT NULL,
    var_95 DOUBLE PRECISION,      -- Value at Risk (95%)
    var_99 DOUBLE PRECISION,      -- Value at Risk (99%)
    cvar_95 DOUBLE PRECISION,     -- Conditional VaR
    beta DOUBLE PRECISION,
    sharpe_rolling DOUBLE PRECISION,
    max_drawdown_rolling DOUBLE PRECISION,
    volatility_30d DOUBLE PRECISION,
    computed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (instrument_id, date)
);
```

### 10.2 Future Table Relationships

```
                    ┌─────────────────┐
                    │   instruments   │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ market_candles│    │ news_articles│    │options_chain │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       │                   ▼                   ▼
       │          ┌─────────────────┐  ┌─────────────────┐
       │          │news_sentiment_  │  │options_daily_   │
       │          │    daily        │  │   metrics       │
       │          └─────────────────┘  └─────────────────┘
       │
       ├──▶ features
       ├──▶ labels
       ├──▶ model_predictions
       └──▶ risk_metrics
```

### 10.3 Expansion Readiness

| Feature | Table | Status | Integration Point |
|---------|-------|--------|-------------------|
| News Engine | `news_articles`, `news_sentiment_daily` | ⏳ Placeholder | FeatureEngine plugin |
| Options Engine | `options_chain`, `options_daily_metrics` | ⏳ Placeholder | FeatureEngine plugin |
| Order Book | `order_book_snapshots` | ⏳ Placeholder | FeatureEngine plugin |
| Macro Data | `macro_indicators` | ⏳ Placeholder | FeatureEngine plugin |
| Risk Engine | `risk_metrics` | ⏳ Placeholder | BacktestEngine hook |
| Autonomous Retraining | — | ⏳ Placeholder | PipelineOrchestrator hook |
| LLM Agent | — | ⏳ Placeholder | Dashboard hook |
| Model Versions | `model_versions` | ⏳ Placeholder | ModelRegistry table |
| Live Trading | `trades`, `positions` | ⏳ Placeholder | PredictionService hook |

---

## Appendix A: SQL Migration Template

```sql
-- Migration: 001_create_initial_schema.sql
-- Finance AI MVP — Initial database schema

BEGIN;

-- 1. Create instruments table
CREATE TABLE instruments (...);

-- 2. Create market_candles table
CREATE TABLE market_candles (...);

-- 3. Create corporate_actions table
CREATE TABLE corporate_actions (...);

-- 4. Create trading_calendar table
CREATE TABLE trading_calendar (...);

-- 5. Create dataset_versions table
CREATE TABLE dataset_versions (...);

-- 6. Create features table
CREATE TABLE features (...);

-- 7. Create labels table
CREATE TABLE labels (...);

-- 8. Create model_predictions table
CREATE TABLE model_predictions (...);

-- 9. Create indexes
CREATE INDEX ...;

-- 10. Insert default trading calendar
INSERT INTO trading_calendar ...;

COMMIT;
```

---

## Appendix B: Cross-Reference to System Architecture

| System Architecture Module | Data Tables Used |
|---------------------------|-----------------|
| Data Ingestion | `instruments`, `market_candles`, `corporate_actions`, `trading_calendar` |
| Data Validation | `market_candles` (validation rules) |
| Data Processing | `market_candles` (cleaned copy) |
| Feature Engine | `features`, `market_candles` (input) |
| Label Engine | `labels`, `market_candles` (input) |
| Dataset Builder | `dataset_versions`, `features`, `labels` |
| Training Engine | `dataset_versions` (reference) |
| Model Registry | `model_predictions` (future: `model_versions`) |
| Prediction Service | `model_predictions` (write) |
| Backtest Engine | `features`, `labels` (read) |
| Dashboard | `model_predictions`, `dataset_versions` (read) |
