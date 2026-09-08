# DATA CLEANING & VALIDATION — Finance AI MVP

> Production-grade data cleaning and validation engine design for the Finance AI platform.
> Converts raw market data into clean, trustworthy, ML-ready data through a deterministic pipeline.
> Every transformation is logged. Raw data is never modified.

---

## Table of Contents

1. [Cleaning Pipeline](#1-cleaning-pipeline)
2. [Validation Rules](#2-validation-rules)
3. [Corporate Actions](#3-corporate-actions)
4. [Missing Data Strategy](#4-missing-data-strategy)
5. [Outlier Detection](#5-outlier-detection)
6. [Data Quality Score](#6-data-quality-score)
7. [Audit Trail](#7-audit-trail)
8. [Error Categories](#8-error-categories)

---

## 1. Cleaning Pipeline

### 1.1 Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     DATA CLEANING PIPELINE                               │
│                                                                          │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐            │
│  │ Raw Data │──▶│ Validate │──▶│  Clean   │──▶│Normalize │            │
│  │ (CSV/    │   │  Rules   │   │  Data    │   │  Data    │            │
│  │  Parquet)│   └──────────┘   └──────────┘   └──────────┘            │
│  └──────────┘        │              │              │                    │
│                      ▼              ▼              ▼                    │
│               ValidationReport  CleaningLog   Normalized Data          │
│                                                                          │
│                      ┌──────────┐   ┌──────────┐                        │
│                      │ Quality  │──▶│ Processed│                        │
│                      │  Score   │   │   Data   │                        │
│                      └──────────┘   └──────────┘                        │
│                            │                                             │
│                            ▼                                             │
│                      QualityReport                                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Detailed Pipeline Stages

#### Stage 1: Raw Data Ingestion

```
Input:   CSV/Parquet files from data/raw/
Process: Load into pandas DataFrame
Output:  Raw DataFrame (unmodified)
Logging: File path, row count, column list, file hash
Rules:   Raw data is IMMUTABLE — never modified in this stage
```

**Invariants:**
- Raw files in `data/raw/` are never written to after initial ingestion
- Every read operation logs the source file path and checksum
- DataFrame is a copy — modifications do not affect the raw file

#### Stage 2: Schema Validation

```
Input:   Raw DataFrame
Process: Validate structure, types, required columns
Output:  SchemaValidationResult { passed, issues }
Logging: Checks run, issues found, pass/fail
```

**Schema Checks:**

| Check | Rule | Action |
|-------|------|--------|
| Column presence | All required columns exist | ERROR → Reject |
| Data types | Numeric columns are numeric | ERROR → Reject |
| Timestamp type | timestamp is parseable as datetime | ERROR → Reject |
| Minimum rows | At least 2 rows (need diff) | ERROR → Reject |
| Index uniqueness | No duplicate timestamps | ERROR → Reject |

#### Stage 3: Data Validation

```
Input:   Schema-validated DataFrame
Process: Validate data values (OHLCV rules)
Output:  DataValidationResult { passed, issues, affected_rows }
Logging: Issues by category, row counts
```

**Data Checks:**

| Check | Rule | Action |
|-------|------|--------|
| Price positivity | open, high, low, close > 0 | ERROR → Reject row |
| Volume non-negative | volume >= 0 | ERROR → Reject row |
| OHLC consistency | high >= max(open, close) | ERROR → Reject row |
| OHLC consistency | low <= min(open, close) | ERROR → Reject row |
| Timestamp ordering | Ascending chronological | ERROR → Reject file |
| Duplicate timestamps | No duplicates per ticker | ERROR → Reject file |
| Null values | No nulls in required columns | ERROR → Reject row |
| Missing data % | < 30% per column | WARNING → Log |

#### Stage 4: Cleaning

```
Input:   Validated DataFrame
Process: Apply cleaning rules
Output:  Cleaned DataFrame
Logging: Rows modified, strategies applied, counts
```

**Cleaning Operations:**

| Operation | Trigger | Strategy | Logging |
|-----------|---------|----------|---------|
| Remove duplicates | Duplicate timestamps | Keep last (most recent) | Count removed |
| Fix OHLC order | high < open or close | Swap high/max(open,close) | Count fixed |
| Fix OHLC order | low > open or close | Swap low/min(open,close) | Count fixed |
| Handle missing values | Null values present | Strategy-based (Section 4) | Strategy + count |
| Remove zero-volume rows | volume = 0 on non-holiday | Flag and keep | Count flagged |
| Apply corporate actions | Split/dividend events | Adjust historical prices (Section 3) | Actions applied |

#### Stage 5: Normalization

```
Input:   Cleaned DataFrame
Process: Standardize formats, types, timezone
Output:  Normalized DataFrame
Logging: Transformations applied
```

**Normalization Steps:**

| Step | Operation | Output |
|------|-----------|--------|
| 1 | Rename columns to standard names | `open`, `high`, `low`, `close`, `volume` |
| 2 | Parse timestamps to datetime | `datetime64[ns, UTC]` |
| 3 | Set datetime as index | DatetimeIndex |
| 4 | Sort by timestamp ascending | Chronological order |
| 5 | Cast numeric columns | `float64` for prices, `int64` for volume |
| 6 | Normalize ticker symbol | Uppercase, stripped, validated format |
| 7 | Set interval | Standardized interval string (`1d`, `1wk`, `1mo`) |

#### Stage 6: Quality Scoring

```
Input:   Normalized DataFrame + Validation Results
Process: Compute data quality score (0-100)
Output:  DataQualityReport { score, dimensions, issues }
Logging: Score breakdown, contributing factors
```

**Scoring Dimensions:**
- Completeness (missing data)
- Validity (rule violations)
- Consistency (OHLC relationships)
- Freshness (data recency)
- Uniqueness (duplicate-free)

#### Stage 7: Output

```
Input:   Normalized DataFrame + Quality Report
Process: Write to data/interim/ or data/processed/
Output:  Cleaned Parquet file + metadata
Logging: File path, row count, file size, quality score
Rules:   Output is versioned, never overwritten
```

### 1.3 Pipeline State Machine

```
┌─────────────────────────────────────────────────────────────┐
│                 Cleaning Pipeline States                      │
│                                                              │
│  ┌──────────┐                                                │
│  │   IDLE   │                                                │
│  └────┬─────┘                                                │
│       │ start                                                │
│       ▼                                                      │
│  ┌──────────┐                                                │
│  │ LOADING  │  Read raw data                                 │
│  └────┬─────┘                                                │
│       │ success                                              │
│       ▼                                                      │
│  ┌──────────┐                                                │
│  │SCHEMA_   │  Validate schema                               │
│  │VALIDATE  │──── FAIL → Log error, return                   │
│  └────┬─────┘                                                │
│       │ pass                                                 │
│       ▼                                                      │
│  ┌──────────┐                                                │
│  │DATA_     │  Validate values                               │
│  │VALIDATE  │──── FAIL → Log errors, continue with warnings  │
│  └────┬─────┘                                                │
│       │ pass (or warnings only)                              │
│       ▼                                                      │
│  ┌──────────┐                                                │
│  │ CLEANING │  Fix issues                                    │
│  └────┬─────┘                                                │
│       │ success                                              │
│       ▼                                                      │
│  ┌──────────┐                                                │
│  │NORMALIZE │  Standardize                                    │
│  └────┬─────┘                                                │
│       │ success                                              │
│       ▼                                                      │
│  ┌──────────┐                                                │
│  │ QUALITY  │  Score data                                    │
│  │  SCORE   │                                                │
│  └────┬─────┘                                                │
│       │ success                                              │
│       ▼                                                      │
│  ┌──────────┐                                                │
│  │ STORING  │  Write output                                  │
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

### 1.4 Pipeline Configuration

```yaml
cleaning:
  # Schema validation
  schema:
    required_columns: ["timestamp", "open", "high", "low", "close", "volume"]
    optional_columns: ["adj_close", "ticker"]
    min_rows: 2
  
  # Data validation
  validation:
    price_positive: true
    volume_non_negative: true
    ohlc_consistency: true
    timestamp_ascending: true
    no_duplicates: true
    max_missing_pct: 0.3
  
  # Cleaning strategies
  cleaning:
    duplicate_strategy: "keep_last"  # keep_last, keep_first, drop_all
    missing_strategy: "forward_fill"  # forward_fill, backward_fill, drop, interpolate, mark
    outlier_strategy: "flag"  # flag, clip, drop, none
    corporate_actions: true  # Apply split/dividend adjustments
  
  # Normalization
  normalization:
    timezone: "UTC"
    price_precision: 2
    volume_type: "int64"
    sort_ascending: true
  
  # Quality scoring
  quality:
    enabled: true
    min_score: 70  # Minimum acceptable quality score
    dimensions:
      completeness: 0.30  # Weight for completeness
      validity: 0.30      # Weight for validity
      consistency: 0.20   # Weight for consistency
      freshness: 0.10     # Weight for freshness
      uniqueness: 0.10    # Weight for uniqueness
```

---

## 2. Validation Rules

### 2.1 Complete Rule Reference

| Rule ID | Category | Check | Severity | Handling |
|---------|----------|-------|----------|----------|
| **Schema Rules** | | | | |
| VAL-S01 | Schema | Required columns present | ERROR | Reject file |
| VAL-S02 | Schema | Correct data types | ERROR | Reject file |
| VAL-S03 | Schema | Minimum row count (≥ 2) | ERROR | Reject file |
| VAL-S04 | Schema | Timestamp parseable | ERROR | Reject file |
| **Price Rules** | | | | |
| VAL-P01 | Price | open > 0 | ERROR | Reject row |
| VAL-P02 | Price | high > 0 | ERROR | Reject row |
| VAL-P03 | Price | low > 0 | ERROR | Reject row |
| VAL-P04 | Price | close > 0 | ERROR | Reject row |
| VAL-P05 | Price | high >= max(open, close) | ERROR | Fix row |
| VAL-P06 | Price | low <= min(open, close) | ERROR | Fix row |
| VAL-P07 | Price | adj_close > 0 | WARNING | Log row |
| VAL-P08 | Price | Price change < 50% per day | WARNING | Flag row |
| VAL-P09 | Price | Price change < 100% per week | WARNING | Flag row |
| **Volume Rules** | | | | |
| VAL-V01 | Volume | volume >= 0 | ERROR | Reject row |
| VAL-V02 | Volume | volume = 0 on trading day | WARNING | Flag row |
| VAL-V03 | Volume | volume < 1000 (unusual) | WARNING | Flag row |
| **Timestamp Rules** | | | | |
| VAL-T01 | Timestamp | No duplicate timestamps | ERROR | Remove duplicate |
| VAL-T02 | Timestamp | Ascending chronological order | ERROR | Sort ascending |
| VAL-T03 | Timestamp | No future timestamps | ERROR | Reject row |
| VAL-T04 | Timestamp | No weekend data (daily) | WARNING | Flag row |
| VAL-T05 | Timestamp | No holiday data (daily) | WARNING | Flag row |
| **Completeness Rules** | | | | |
| VAL-C01 | Completeness | Missing data < 30% per column | WARNING | Log |
| VAL-C02 | Completeness | No consecutive gaps > 5 days | WARNING | Log |
| VAL-C03 | Completeness | Data covers expected date range | WARNING | Log |

### 2.2 Validation Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       VALIDATION FLOW                                    │
│                                                                          │
│  Raw DataFrame                                                           │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    SCHEMA VALIDATION                             │    │
│  │                                                                  │    │
│  │  VAL-S01: Required columns present?                              │    │
│  │     ├── NO  → REJECT + LOG + RETURN                              │    │
│  │     └── YES → Continue                                            │    │
│  │                                                                  │    │
│  │  VAL-S02: Correct data types?                                    │    │
│  │     ├── NO  → ATTEMPT CAST → LOG WARNING                        │    │
│  │     └── YES → Continue                                            │    │
│  │                                                                  │    │
│  │  VAL-S03: Minimum rows (≥ 2)?                                    │    │
│  │     ├── NO  → REJECT + LOG + RETURN                              │    │
│  │     └── YES → Continue                                            │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│       │ pass                                                             │
│       ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    DATA VALIDATION                               │    │
│  │                                                                  │    │
│  │  VAL-P01 to VAL-P04: Prices positive?                           │    │
│  │     ├── NO  → MARK BAD ROWS → CONTINUE                           │    │
│  │     └── YES → Continue                                            │    │
│  │                                                                  │    │
│  │  VAL-P05, VAL-P06: OHLC consistency?                            │    │
│  │     ├── NO  → MARK FOR FIX → CONTINUE                            │    │
│  │     └── YES → Continue                                            │    │
│  │                                                                  │    │
│  │  VAL-V01: Volume non-negative?                                   │    │
│  │     ├── NO  → MARK BAD ROWS → CONTINUE                           │    │
│  │     └── YES → Continue                                            │    │
│  │                                                                  │    │
│  │  VAL-T01: No duplicate timestamps?                               │    │
│  │     ├── NO  → MARK FOR DEDUP → CONTINUE                          │    │
│  │     └── YES → Continue                                            │    │
│  │                                                                  │    │
│  │  VAL-T02: Timestamps ascending?                                  │    │
│  │     ├── NO  → MARK FOR SORT → CONTINUE                           │    │
│  │     └── YES → Continue                                            │    │
│  │                                                                  │    │
│  │  VAL-P08, VAL-P09: Price anomaly check?                         │    │
│  │     ├── ANOMALY → FLAG ROW → CONTINUE                            │    │
│  │     └── OK → Continue                                             │    │
│  │                                                                  │    │
│  │  VAL-C01: Missing data percentage?                               │    │
│  │     ├── HIGH → LOG WARNING → CONTINUE                            │    │
│  │     └── OK → Continue                                             │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│       │ pass (or warnings only)                                         │
│       ▼                                                                  │
│  Validation PASSED                                                       │
│    → Return DataFrame + ValidationReport                                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Validation Report Structure

```python
@dataclass
class ValidationReport:
    passed: bool                          # Overall pass/fail
    schema_valid: bool                    # Schema checks passed
    data_valid: bool                      # Data checks passed
    rules_checked: int                    # Total rules evaluated
    errors: int                           # Critical errors
    warnings: int                         # Non-critical issues
    issues: List[ValidationIssue]         # Detailed issues
    summary: Dict[str, int]               # Counts by category
    affected_rows: Set[int]              # Row indices with issues

@dataclass
class ValidationIssue:
    rule_id: str                          # "VAL-P01"
    severity: str                         # "error" | "warning" | "critical"
    category: str                         # "price", "volume", "timestamp", "schema"
    column: str                           # Column name
    row_indices: List[int]                # Affected row indices
    message: str                          # Human-readable description
    sample_values: List[Any]              # Example values
    count: int                            # Number of affected rows
    recommendation: str                   # How to fix
```

### 2.4 Trading Day Validation

```
┌─────────────────────────────────────────────────────────────┐
│                 Trading Day Validation                       │
│                                                              │
│  Purpose: Detect data on non-trading days                    │
│                                                              │
│  Input:                                                      │
│    - DataFrame with timestamps                               │
│    - Trading calendar (from trading_calendar table/file)     │
│                                                              │
│  Logic:                                                      │
│    1. Load trading calendar for the exchange                 │
│    2. For each timestamp in DataFrame:                       │
│       │                                                      │
│       ├── Is date a trading day?                             │
│       │    ├── YES → Valid                                   │
│       │    └── NO  → Check if weekend or holiday             │
│       │                                                      │
│       ├── If weekend (Sat/Sun):                              │
│       │    └── WARNING: Weekend data detected                │
│       │                                                      │
│       └── If holiday:                                        │
│            └── WARNING: Holiday data detected                │
│                                                              │
│  Output:                                                     │
│    - List of non-trading-day timestamps                      │
│    - Flag rows for potential removal or investigation        │
│                                                              │
│  Decision:                                                   │
│    - Keep rows by default (some sources include early close) │
│    - Log all non-trading-day observations                    │
│    - Let downstream pipeline decide to keep/drop             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Corporate Actions

### 3.1 Action Types

| Action Type | Effect on Historical Prices | Adjustment Direction |
|-------------|----------------------------|---------------------|
| **Stock Split** | Shares multiply, price divides | Backward adjust (before split date) |
| **Reverse Split** | Shares divide, price multiplies | Backward adjust (before split date) |
| **Dividend** | Cash payment per share | Backward adjust (before ex-date) |
| **Bonus Issue** | Free shares issued | Backward adjust (before issue date) |
| **Symbol Change** | Ticker symbol updated | Rename only, no price adjustment |
| **Merger/Acquisition** | Company acquired | Stop data at acquisition date |

### 3.2 Adjustment Strategy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                 Corporate Action Adjustment Strategy                     │
│                                                                          │
│  PRINCIPLE:                                                              │
│    Adjust historical prices so that the adjusted series is continuous    │
│    and comparable across corporate action events.                        │
│                                                                          │
│  DIRECTION: Backward adjustment                                          │
│    - Adjust all historical prices BEFORE the action date                 │
│    - Leave post-action prices as-is                                      │
│    - This ensures current prices are "real" and historical are adjusted  │
│                                                                          │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                          │
│  EXAMPLE: AAPL 4-for-1 Split (2020-08-31)                               │
│                                                                          │
│  Before Adjustment:                                                      │
│    2020-08-28: close = $499.23                                           │
│    2020-08-31: close = $129.04  (post-split)                             │
│                                                                          │
│  After Adjustment (backward):                                            │
│    2020-08-28: close = $124.81  ($499.23 / 4)                           │
│    2020-08-31: close = $129.04  (unchanged)                              │
│                                                                          │
│  Result: Smooth price series across split date                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Adjustment Formulas

#### Stock Split

```
For a split with ratio R (e.g., 4-for-1 → R = 4):

  adjusted_price = price / R     (for all dates BEFORE split)

Where:
  price = original OHLC price
  R = split ratio
  adjusted_price = backward-adjusted price
```

#### Dividend

```
For a dividend with amount D and closing price P on ex-date:

  adjustment_factor = 1 - (D / P_close_before_ex_date)
  adjusted_price = price × adjustment_factor     (for all dates BEFORE ex-date)

Where:
  D = dividend amount per share
  P_close_before_ex_date = closing price on day before ex-date
  adjustment_factor = ratio to apply to historical prices
```

#### Reverse Split

```
For a reverse split with ratio R (e.g., 1-for-5 → R = 0.2):

  adjusted_price = price / R     (for all dates BEFORE split)

Same formula as forward split — just R < 1.
```

### 3.4 Adjustment Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                 Corporate Action Adjustment Flow                         │
│                                                                          │
│  1. LOAD CORPORATE ACTIONS                                               │
│     │                                                                    │
│     ├── Load actions for ticker from corporate_actions table/file        │
│     ├── Sort by effective_date ascending                                 │
│     └── Filter to relevant types (split, dividend, bonus)               │
│                                                                          │
│  2. FOR EACH ACTION (chronological order):                               │
│     │                                                                    │
│     ├── Compute adjustment factor                                        │
│     │                                                                    │
│     ├── Apply to all rows WHERE timestamp < effective_date               │
│     │                                                                    │
│     ├── For splits: divide OHLC by ratio                                │
│     │                                                                    │
│     ├── For dividends: multiply by (1 - D/P)                            │
│     │                                                                    │
│     └── Log: action_type, effective_date, factor, rows_affected         │
│                                                                          │
│  3. VERIFY ADJUSTMENT                                                    │
│     │                                                                    │
│     ├── Check price continuity at action dates                           │
│     ├── Verify no negative prices after adjustment                       │
│     └── Log adjustment summary                                           │
│                                                                          │
│  OUTPUT: Adjusted DataFrame with smooth historical prices                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.5 Adjacent Close (Adjusted Close)

| Field | Description | When to Use |
|-------|-------------|-------------|
| `close` | Raw closing price | Intraday analysis, current prices |
| `adj_close` | Adjusted closing price | Historical analysis, returns computation |

**Decision Rule:**
- Use `adj_close` for feature engineering (returns, volatility)
- Use `close` for current price display
- Document which field is used in every analysis

### 3.6 Symbol Change Handling

```
┌─────────────────────────────────────────────────────────────┐
│                 Symbol Change Handling                        │
│                                                              │
│  Scenario: Ticker symbol changes (e.g., FB → META)          │
│                                                              │
│  Strategy:                                                   │
│    1. Track old and new symbols in corporate_actions table   │
│    2. Merge historical data under new symbol                 │
│    3. Keep old symbol as alias for lookup                    │
│    4. No price adjustment needed (same company)              │
│                                                              │
│  Metadata:                                                   │
│    - action_type: "ticker_change"                            │
│    - old_symbol: "FB"                                        │
│    - new_symbol: "META"                                      │
│    - effective_date: "2022-06-09"                             │
│                                                              │
│  Data Flow:                                                  │
│    Raw: FB_daily.csv (2012-2022)                             │
│    Raw: META_daily.csv (2022-present)                        │
│         │                                                    │
│         ▼                                                    │
│    Cleaned: META_daily.csv (2012-present) ← merged          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Missing Data Strategy

### 4.1 Strategy Overview

| Strategy | When to Use | Pros | Cons |
|----------|-------------|------|------|
| **Forward Fill** | Default for price data | Preserves trend, no artificial gaps | Carries stale values |
| **Backward Fill** | Small gaps at start | Fills from future data | Uses future info (caution) |
| **Interpolation** | Short gaps (1-3 days) | Smooth transition | May create unrealistic values |
| **Drop Rows** | > 30% missing | No artificial data | Reduces dataset size |
| **Mark Incomplete** | Audit trail | Full transparency | Requires downstream handling |
| **Zero Fill** | Volume only | Simple | Unrealistic for prices |

### 4.2 Strategy Selection Logic

```
┌─────────────────────────────────────────────────────────────────────────┐
│                 Missing Data Strategy Selection                          │
│                                                                          │
│  FOR EACH ROW with missing values:                                       │
│                                                                          │
│  1. COUNT consecutive missing values (gap length)                        │
│                                                                          │
│  2. SELECT strategy based on gap length:                                 │
│     │                                                                    │
│     ├── Gap = 1 day                                                      │
│     │    └── Strategy: FORWARD FILL                                      │
│     │        (Carry last known value forward)                            │
│     │                                                                    │
│     ├── Gap = 2-3 days                                                   │
│     │    └── Strategy: INTERPOLATE                                       │
│     │        (Linear interpolation between neighbors)                    │
│     │                                                                    │
│     ├── Gap = 4-5 days                                                   │
│     │    └── Strategy: FORWARD FILL                                      │
│     │        (Carry last known value, log warning)                       │
│     │                                                                    │
│     ├── Gap = 6-10 days                                                  │
│     │    └── Strategy: MARK INCOMPLETE                                   │
│     │        (Set flag, let downstream decide)                           │
│     │                                                                    │
│     └── Gap > 10 days                                                    │
│          └── Strategy: DROP ROW                                          │
│              (Remove row, log warning)                                   │
│                                                                          │
│  3. APPLY strategy to affected columns:                                  │
│     │                                                                    │
│     ├── Price columns (open, high, low, close):                          │
│     │    └── Forward fill or interpolate                                 │
│     │                                                                    │
│     ├── Volume column:                                                   │
│     │    └── Zero fill (volume = 0 for missing)                          │
│     │                                                                    │
│     └── Adj Close column:                                                │
│          └── Forward fill (same as close)                                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Forward Fill Rules

```
┌─────────────────────────────────────────────────────────────┐
│                 Forward Fill Rules                           │
│                                                              │
│  Input:                                                      │
│    timestamp: [2024-01-01, 2024-01-02, 2024-01-03, ...]     │
│    close:     [100.0, NaN, NaN, 105.0, ...]                 │
│                                                              │
│  Forward Fill (limit=3):                                     │
│    close:     [100.0, 100.0, 100.0, 105.0, ...]             │
│                                                              │
│  Rules:                                                      │
│    1. Only forward fill if gap <= limit (default: 3 days)    │
│    2. Never forward fill across weekends (skip Sat/Sun)      │
│    3. Never forward fill across holidays                     │
│    4. Log every forward fill operation                       │
│    5. Count forward fills per column                         │
│                                                              │
│  Edge Cases:                                                 │
│    - First row has NaN → Cannot forward fill → Use NaN       │
│    - Consecutive NaN > limit → Do not fill → Leave NaN       │
│    - All values NaN → Cannot fill → Drop row                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4.4 Interpolation Rules

```
┌─────────────────────────────────────────────────────────────┐
│                 Interpolation Rules                          │
│                                                              │
│  Method: Linear interpolation                                │
│                                                              │
│  Input:                                                      │
│    timestamp: [2024-01-01, 2024-01-02, 2024-01-03, ...]     │
│    close:     [100.0, NaN, 105.0, ...]                      │
│                                                              │
│  Interpolation:                                              │
│    close:     [100.0, 102.5, 105.0, ...]                    │
│    (100.0 + 105.0) / 2 = 102.5                              │
│                                                              │
│  Rules:                                                      │
│    1. Only interpolate gaps of 1-3 days                      │
│    2. Use linear method (not spline, not polynomial)         │
│    3. Do not extrapolate beyond known values                 │
│    4. Log every interpolation operation                      │
│    5. Verify interpolated values are within reasonable range │
│                                                              │
│  Reasonable Range Check:                                     │
│    - Interpolated price must be within ±20% of neighbors     │
│    - If outside range → Use forward fill instead             │
│    - Log warning for suspicious interpolations               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4.5 Missing Data Monitoring

```python
@dataclass
class MissingDataReport:
    ticker: str
    total_rows: int
    missing_before: Dict[str, int]      # Column → missing count before cleaning
    missing_after: Dict[str, int]       # Column → missing count after cleaning
    strategy_applied: Dict[str, str]    # Column → strategy used
    rows_dropped: int                   # Rows removed due to excessive missing
    rows_interpolated: int              # Rows with interpolated values
    rows_forward_filled: int            # Rows with forward-filled values
    gaps_detected: List[DataGap]        # List of gap periods found

@dataclass
class DataGap:
    start_date: str
    end_date: str
    days: int
    columns_affected: List[str]
    strategy_applied: str
```

---

## 5. Outlier Detection

### 5.1 Outlier Types

| Type | Description | Detection Method | Example |
|------|-------------|-----------------|---------|
| **Price Spike** | Abnormal price movement | Z-score or IQR | 50% jump in 1 day |
| **Volume Spike** | Abnormal volume | Z-score or IQR | 10x average volume |
| **Data Error** | Corrupted or wrong values | Range checks | Price = 0, Volume = -100 |
| **Corporate Action** | Split/dividend effect | Calendar check | Sudden 4x price change |
| **Flash Crash** | Extreme intraday move | Range + context | 30% drop then recovery |

### 5.2 Detection Methods

#### Method 1: Z-Score

```
┌─────────────────────────────────────────────────────────────┐
│                 Z-Score Detection                            │
│                                                              │
│  Formula:                                                    │
│    z = (value - mean) / std_dev                             │
│                                                              │
│  Thresholds:                                                 │
│    |z| > 3.0  → Outlier (99.7% confidence)                  │
│    |z| > 2.5  → Suspicious (99.4% confidence)               │
│    |z| > 2.0  → Unusual (95.4% confidence)                  │
│                                                              │
│  Parameters:                                                 │
│    - Window: 20-day rolling window                           │
│    - Min observations: 10                                    │
│    - Threshold: 3.0 (default)                                │
│                                                              │
│  Example:                                                    │
│    20-day mean return: 0.05%                                 │
│    20-day std return: 1.2%                                   │
│    Day return: 8.5%                                          │
│    z = (8.5 - 0.05) / 1.2 = 7.04 → OUTLIER                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Method 2: IQR (Interquartile Range)

```
┌─────────────────────────────────────────────────────────────┐
│                 IQR Detection                                │
│                                                              │
│  Formula:                                                    │
│    Q1 = 25th percentile                                     │
│    Q3 = 75th percentile                                     │
│    IQR = Q3 - Q1                                            │
│    lower_bound = Q1 - 1.5 * IQR                            │
│    upper_bound = Q3 + 1.5 * IQR                            │
│                                                              │
│  Parameters:                                                 │
│    - Window: 60-day rolling window                           │
│    - Multiplier: 1.5 (standard) or 3.0 (extreme)            │
│                                                              │
│  Example:                                                    │
│    Q1 (returns): -0.8%                                       │
│    Q3 (returns): 0.9%                                        │
│    IQR: 1.7%                                                 │
│    lower: -0.8 - 1.5*1.7 = -3.35%                           │
│    upper: 0.9 + 1.5*1.7 = 3.45%                             │
│    Day return: 5.2% → OUTLIER (above 3.45%)                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Method 3: Rolling Window

```
┌─────────────────────────────────────────────────────────────┐
│                 Rolling Window Detection                     │
│                                                              │
│  Logic:                                                      │
│    1. Compute rolling mean and rolling std over window       │
│    2. Flag points outside mean ± k * std                     │
│    3. Adjust k based on window size                          │
│                                                              │
│  Parameters:                                                 │
│    - Window sizes: [20, 50, 100]                             │
│    - k = 3.0 for 20-day window                              │
│    - k = 2.5 for 50-day window                              │
│    - k = 2.0 for 100-day window                             │
│                                                              │
│  Multi-Window Consensus:                                     │
│    - Flag as outlier only if detected by ≥ 2 windows         │
│    - Reduces false positives                                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 Outlier Handling Strategies

| Strategy | When to Use | Implementation |
|----------|-------------|----------------|
| **Flag Only** | Default — for investigation | Add `is_outlier` column |
| **Clip** | Known bounds | Clip to percentile range |
| **Interpolate** | Confirmed data error | Replace with interpolated value |
| **Drop** | Corrupted data | Remove row entirely |
| **Keep** | Valid extreme move (flash crash) | No action, just log |

### 5.4 Outlier Detection Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                 Outlier Detection Flow                                   │
│                                                                          │
│  Input: Cleaned DataFrame                                                │
│                                                                          │
│  1. COMPUTE RETURNS                                                      │
│     daily_return = close.pct_change()                                    │
│                                                                          │
│  2. COMPUTE ROLLING STATISTICS                                           │
│     rolling_mean = daily_return.rolling(20).mean()                       │
│     rolling_std = daily_return.rolling(20).std()                         │
│                                                                          │
│  3. DETECT PRICE OUTLIERS                                                │
│     z_score = (daily_return - rolling_mean) / rolling_std                │
│     price_outlier = |z_score| > 3.0                                      │
│                                                                          │
│  4. DETECT VOLUME OUTLIERS                                               │
│     volume_ratio = volume / volume.rolling(20).mean()                    │
│     volume_outlier = volume_ratio > 5.0                                  │
│                                                                          │
│  5. DETECT CORPORATE ACTION DATES                                        │
│     ca_dates = load_corporate_actions(ticker)                            │
│     ca_outlier = timestamp in ca_dates                                   │
│                                                                          │
│  6. CLASSIFY OUTLIERS                                                    │
│     │                                                                    │
│     ├── price_outlier AND NOT ca_outlier → Data error → Flag            │
│     ├── price_outlier AND ca_outlier → Corporate action → Log           │
│     ├── volume_outlier AND NOT ca_outlier → Volume anomaly → Flag       │
│     └── volume_outlier AND ca_outlier → Expected → Log                  │
│                                                                          │
│  7. OUTPUT                                                               │
│     DataFrame with outlier flags and metadata                            │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.5 Outlier Report

```python
@dataclass
class OutlierReport:
    ticker: str
    total_rows: int
    price_outliers: int
    volume_outliers: int
    corporate_action_events: int
    outliers: List[OutlierDetail]

@dataclass
class OutlierDetail:
    timestamp: str
    column: str            # "close", "volume", etc.
    value: float
    expected_range: Tuple[float, float]
    z_score: float
    classification: str    # "data_error", "corporate_action", "valid_extreme", "unknown"
    action_taken: str      # "flagged", "clipped", "interpolated", "kept"
```

---

## 6. Data Quality Score

### 6.1 Scoring Dimensions

| Dimension | Weight | Description | Computation |
|-----------|--------|-------------|-------------|
| **Completeness** | 30% | How much data is present | 1 - (missing_cells / total_cells) |
| **Validity** | 30% | How many values pass validation | valid_rows / total_rows |
| **Consistency** | 20% | OHLC relationships correct | consistent_rows / total_rows |
| **Freshness** | 10% | How recent the data is | Based on days since last data point |
| **Uniqueness** | 10% | No duplicate records | unique_timestamps / total_timestamps |

### 6.2 Score Computation

```
┌─────────────────────────────────────────────────────────────────────────┐
│                 Data Quality Score Computation                           │
│                                                                          │
│  FORMULA:                                                                │
│    score = (completeness × 0.30) +                                      │
│            (validity × 0.30) +                                          │
│            (consistency × 0.20) +                                       │
│            (freshness × 0.10) +                                         │
│            (uniqueness × 0.10)                                          │
│                                                                          │
│  SCALE: 0-100                                                            │
│    90-100: Excellent — Ready for ML                                       │
│    80-89:  Good — Minor issues, acceptable                                │
│    70-79:  Fair — Some issues, review recommended                         │
│    60-69:  Poor — Significant issues, caution                             │
│    < 60:   Failing — Do not use, fix issues first                         │
│                                                                          │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                          │
│  DIMENSION COMPUTATION:                                                  │
│                                                                          │
│  Completeness:                                                           │
│    missing_cells = sum of NaN values across all required columns         │
│    total_cells = rows × required_columns                                 │
│    completeness = (1 - missing_cells / total_cells) × 100               │
│                                                                          │
│  Validity:                                                               │
│    valid_rows = rows passing all ERROR-level validation rules            │
│    validity = (valid_rows / total_rows) × 100                           │
│                                                                          │
│  Consistency:                                                            │
│    consistent_rows = rows with correct OHLC relationships                │
│    consistency = (consistent_rows / total_rows) × 100                    │
│                                                                          │
│  Freshness:                                                              │
│    days_since_last = today - max(timestamp)                              │
│    freshness = max(0, 100 - days_since_last × 2)                        │
│    (Loses 2 points per day stale, minimum 0)                             │
│                                                                          │
│  Uniqueness:                                                             │
│    unique_timestamps = nunique(timestamp)                                │
│    uniqueness = (unique_timestamps / total_timestamps) × 100            │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Quality Score Example

```
┌─────────────────────────────────────────────────────────────┐
│                 Quality Score Example                        │
│                                                              │
│  Dataset: AAPL_daily (2520 rows, 6 columns)                 │
│                                                              │
│  Completeness:                                               │
│    Missing cells: 12 (out of 15,120)                         │
│    Score: (1 - 12/15120) × 100 = 99.92                      │
│    Weighted: 99.92 × 0.30 = 29.98                           │
│                                                              │
│  Validity:                                                   │
│    Valid rows: 2515 (out of 2520)                            │
│    Score: (2515/2520) × 100 = 99.80                         │
│    Weighted: 99.80 × 0.30 = 29.94                           │
│                                                              │
│  Consistency:                                                │
│    Consistent rows: 2510 (out of 2520)                       │
│    Score: (2510/2520) × 100 = 99.60                         │
│    Weighted: 99.60 × 0.20 = 19.92                           │
│                                                              │
│  Freshness:                                                  │
│    Days since last: 1                                        │
│    Score: 100 - (1 × 2) = 98.00                             │
│    Weighted: 98.00 × 0.10 = 9.80                            │
│                                                              │
│  Uniqueness:                                                 │
│    Unique timestamps: 2520 (out of 2520)                     │
│    Score: (2520/2520) × 100 = 100.00                        │
│    Weighted: 100.00 × 0.10 = 10.00                          │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│                                                              │
│  TOTAL QUALITY SCORE: 29.98 + 29.94 + 19.92 + 9.80 + 10.00 │
│                     = 99.64                                  │
│                                                              │
│  Rating: EXCELLENT                                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 6.4 Quality Score Report

```python
@dataclass
class DataQualityReport:
    ticker: str
    overall_score: float                 # 0-100
    rating: str                          # "excellent", "good", "fair", "poor", "failing"
    dimensions: Dict[str, float]         # Dimension → score (0-100)
    weights: Dict[str, float]            # Dimension → weight
    issues: List[QualityIssue]           # Contributing issues
    recommendation: str                  # What to do next
    computed_at: datetime                # When score was computed

@dataclass
class QualityIssue:
    dimension: str                       # "completeness", "validity", etc.
    severity: str                        # "warning", "error"
    description: str                     # What the issue is
    affected_rows: int                   # How many rows
    impact: float                        # Impact on score (negative)
```

### 6.5 Quality Gate

```
┌─────────────────────────────────────────────────────────────┐
│                 Quality Gate                                 │
│                                                              │
│  Before data proceeds to feature engineering:                │
│                                                              │
│  1. Compute quality score                                    │
│                                                              │
│  2. Check against threshold                                  │
│     │                                                        │
│     ├── Score >= 90 → PASS → Proceed to feature engineering  │
│     │                                                        │
│     ├── Score 70-89 → PASS WITH WARNINGS                     │
│     │    └── Log warnings, proceed with caution              │
│     │                                                        │
│     ├── Score 60-69 → REVIEW REQUIRED                        │
│     │    └── Log issues, require manual review               │
│     │                                                        │
│     └── Score < 60 → FAIL                                    │
│          └── Stop pipeline, fix issues first                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. Audit Trail

### 7.1 Audit Principles

| Principle | Description |
|-----------|-------------|
| **Traceability** | Every cleaned record can be traced back to its raw source |
| **Immutability** | Raw data is never modified; cleaning produces new output |
| **Transparency** | Every transformation is logged and documented |
| **Reproducibility** | Same input + same config → same output |
| **Accountability** | Every change has a reason and a log entry |

### 7.2 Audit Trail Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       AUDIT TRAIL STRUCTURE                              │
│                                                                          │
│  RAW DATA (immutable)                                                    │
│  ├── File: data/raw/AAPL_daily.csv                                       │
│  ├── SHA-256: a1b2c3d4e5f6...                                           │
│  ├── Rows: 2520                                                          │
│  ├── Columns: [timestamp, open, high, low, close, volume]               │
│  └── Ingested: 2024-07-04T18:00:00Z                                     │
│                                                                          │
│       │                                                                  │
│       ▼ (Transformation Log)                                             │
│                                                                          │
│  TRANSFORMATION #1: Schema Validation                                    │
│  ├── Input: data/raw/AAPL_daily.csv                                      │
│  ├── Rule: VAL-S01 (required columns)                                    │
│  ├── Result: PASSED                                                      │
│  ├── Rows affected: 0                                                    │
│  └── Duration: 12ms                                                      │
│                                                                          │
│  TRANSFORMATION #2: Data Validation                                      │
│  ├── Input: raw DataFrame                                                │
│  ├── Rules: VAL-P01 to VAL-P09                                           │
│  ├── Result: PASSED (2 warnings)                                         │
│  ├── Rows with warnings: 3                                               │
│  └── Duration: 45ms                                                      │
│                                                                          │
│  TRANSFORMATION #3: Duplicate Removal                                    │
│  ├── Input: 2520 rows                                                    │
│  ├── Strategy: keep_last                                                 │
│  ├── Duplicates found: 2                                                 │
│  ├── Rows removed: 2                                                     │
│  └── Duration: 8ms                                                       │
│                                                                          │
│  TRANSFORMATION #4: Forward Fill                                         │
│  ├── Input: 2518 rows                                                    │
│  ├── Strategy: forward_fill (limit=3)                                    │
│  ├── Values filled: 5                                                    │
│  ├── Columns affected: [close, volume]                                   │
│  └── Duration: 15ms                                                      │
│                                                                          │
│  TRANSFORMATION #5: Outlier Flagging                                     │
│  ├── Input: 2518 rows                                                    │
│  ├── Method: z-score (threshold=3.0)                                     │
│  ├── Outliers found: 1                                                   │
│  ├── Action: flagged (kept)                                              │
│  └── Duration: 22ms                                                      │
│                                                                          │
│  TRANSFORMATION #6: Normalization                                        │
│  ├── Input: 2518 rows                                                    │
│  ├── Columns renamed: {Date→timestamp, Open→open, ...}                   │
│  ├── Timezone: UTC                                                       │
│  ├── Sort: ascending                                                     │
│  └── Duration: 10ms                                                      │
│                                                                          │
│  OUTPUT                                                                  │
│  ├── File: data/interim/AAPL_daily_cleaned.parquet                       │
│  ├── SHA-256: f6e5d4c3b2a1...                                           │
│  ├── Rows: 2518                                                          │
│  ├── Quality Score: 98.5                                                 │
│  └── Audit ID: audit-2024-07-04-AAPL-001                                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.3 Audit Metadata Schema

```python
@dataclass
class AuditRecord:
    # Identity
    audit_id: str                    # Unique audit trail ID
    ticker: str                      # Ticker symbol
    
    # Source
    raw_file_path: str               # Path to raw data file
    raw_file_hash: str               # SHA-256 of raw file
    raw_row_count: int               # Rows in raw data
    
    # Transformations
    transformations: List[Transformation]  # Ordered list of transformations
    
    # Output
    output_file_path: str            # Path to cleaned data file
    output_file_hash: str            # SHA-256 of output file
    output_row_count: int            # Rows in cleaned data
    
    # Quality
    quality_score: float             # Data quality score (0-100)
    validation_report: ValidationReport
    quality_report: DataQualityReport
    
    # Timing
    started_at: datetime             # When cleaning started
    completed_at: datetime           # When cleaning completed
    duration_ms: float               # Total duration
    
    # Configuration
    config_snapshot: Dict            # Full config used for cleaning
    pipeline_version: str            # Version of cleaning pipeline

@dataclass
class Transformation:
    step: int                        # Step number (1, 2, 3, ...)
    name: str                        # "schema_validation", "forward_fill", etc.
    rule_id: str                     # "VAL-S01", "CLEAN-FF", etc.
    input_rows: int                  # Rows before transformation
    output_rows: int                 # Rows after transformation
    rows_affected: int               # Rows modified/removed
    strategy: str                    # Strategy applied (if applicable)
    details: Dict                    # Additional details
    duration_ms: float               # Transformation duration
```

### 7.4 Traceability Chain

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       TRACEABILITY CHAIN                                 │
│                                                                          │
│  Level 1: Raw Data                                                       │
│    File: data/raw/AAPL_daily.csv                                         │
│    Hash: a1b2c3d4...                                                     │
│    Ingested: 2024-07-04T18:00:00Z                                        │
│                                                                          │
│  Level 2: Cleaned Data                                                   │
│    File: data/interim/AAPL_daily_cleaned.parquet                         │
│    Hash: f6e5d4c3...                                                     │
│    Audit: audit-2024-07-04-AAPL-001                                      │
│    Raw reference: data/raw/AAPL_daily.csv (hash: a1b2c3d4...)           │
│                                                                          │
│  Level 3: Features                                                       │
│    File: data/processed/features_v1.0.0.parquet                          │
│    Hash: ...                                                             │
│    Clean reference: data/interim/AAPL_daily_cleaned.parquet              │
│    Config: config/default.yaml (hash: ...)                               │
│                                                                          │
│  Level 4: Dataset                                                        │
│    File: data/processed/dataset_v1.0.0/train.parquet                     │
│    Version: v1.0.0-2024-07-04                                            │
│    Feature reference: features_v1.0.0.parquet                            │
│    Split config: train=0.7, val=0.15, test=0.15                          │
│                                                                          │
│  Level 5: Model                                                          │
│    File: models/model_v1.0.0-2024-07-04.joblib                           │
│    Dataset reference: v1.0.0-2024-07-04                                  │
│    Training config: ...                                                   │
│                                                                          │
│  CHAIN: Raw → Cleaned → Features → Dataset → Model                       │
│  Each level references the previous level's hash                         │
│  Any level can be traced back to raw data                                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.5 Audit Log Storage

```
audit/
├── audit_2024-07-04_AAPL_001.json      ← Per-ticker audit record
├── audit_2024-07-04_AAPL_002.json      ← Updated audit record
├── audit_2024-07-04_MSFT_001.json
├── audit_2024-07-04_batch_001.json     ← Batch audit summary
└── audit_log.jsonl                     ← Append-only audit log
```

---

## 8. Error Categories

### 8.1 Error Severity Levels

| Level | Color | Description | Action | Example |
|-------|-------|-------------|--------|---------|
| **CRITICAL** | 🔴 | System cannot proceed | Halt pipeline, alert | Raw file missing, disk full |
| **ERROR** | 🟠 | Data is invalid, cannot use | Reject data, log error | Negative prices, duplicate timestamps |
| **WARNING** | 🟡 | Data has issues, may be usable | Log, flag, continue | High missing data %, zero volume |
| **INFO** | 🟢 | Notable observation, not an issue | Log only | Data freshness check, row count |

### 8.2 Error Categories

#### Category 1: Data Integrity Errors

| Error Code | Severity | Description | Handling |
|------------|----------|-------------|----------|
| ERR-DI-01 | CRITICAL | Raw file not found | Halt, alert |
| ERR-DI-02 | ERROR | Required columns missing | Reject file |
| ERR-DI-03 | ERROR | Negative price values | Reject row |
| ERR-DI-04 | ERROR | OHLC inconsistency | Fix or reject row |
| ERR-DI-05 | ERROR | Duplicate timestamps | Remove duplicate |
| ERR-DI-06 | WARNING | Zero volume on trading day | Flag row |
| ERR-DI-07 | WARNING | Price change > 50% | Flag row |
| ERR-DI-08 | INFO | Data freshness check | Log |

#### Category 2: Data Completeness Errors

| Error Code | Severity | Description | Handling |
|------------|----------|-------------|----------|
| ERR-DC-01 | ERROR | > 50% missing data | Reject column |
| ERR-DC-02 | WARNING | > 30% missing data | Log warning |
| ERR-DC-03 | WARNING | Gap > 5 trading days | Log warning |
| ERR-DC-04 | INFO | Missing data percentage | Log info |

#### Category 3: Data Consistency Errors

| Error Code | Severity | Description | Handling |
|------------|----------|-------------|----------|
| ERR-DC-05 | ERROR | Timezone mismatch | Convert or reject |
| ERR-DC-06 | WARNING | Weekend data in daily series | Flag |
| ERR-DC-07 | WARNING | Holiday data in daily series | Flag |
| ERR-DC-08 | WARNING | Out-of-sequence timestamps | Sort |

#### Category 4: System Errors

| Error Code | Severity | Description | Handling |
|------------|----------|-------------|----------|
| ERR-SY-01 | CRITICAL | Disk full | Halt pipeline |
| ERR-SY-02 | CRITICAL | Permission denied | Halt pipeline |
| ERR-SY-03 | ERROR | File write failed | Retry, then halt |
| ERR-SY-04 | ERROR | Config invalid | Halt, fix config |
| ERR-SY-05 | WARNING | Slow processing | Log performance |

#### Category 5: Corporate Action Errors

| Error Code | Severity | Description | Handling |
|------------|----------|-------------|----------|
| ERR-CA-01 | WARNING | Split detected without action | Log, flag |
| ERR-CA-02 | WARNING | Dividend adjustment failed | Log, skip adjustment |
| ERR-CA-03 | INFO | Corporate action applied | Log action |

### 8.3 Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       ERROR HANDLING FLOW                                │
│                                                                          │
│  Error Detected                                                          │
│       │                                                                  │
│       ├── CRITICAL                                                       │
│       │    │                                                             │
│       │    ├── Log CRITICAL error with full context                      │
│       │    ├── Write to error log (data/errors/CRITICAL.log)             │
│       │    ├── Send alert (if alerting configured)                       │
│       │    ├── Halt pipeline immediately                                 │
│       │    └── Exit with non-zero code                                   │
│       │                                                                  │
│       ├── ERROR                                                          │
│       │    │                                                             │
│       │    ├── Log ERROR with context                                    │
│       │    ├── Write to error log (data/errors/ERROR.log)                │
│       │    ├── Add to validation report                                  │
│       │    ├── Mark affected rows                                        │
│       │    ├── Continue to next row (if row-level)                       │
│       │    └── Or reject file (if file-level)                            │
│       │                                                                  │
│       ├── WARNING                                                        │
│       │    │                                                             │
│       │    ├── Log WARNING with context                                  │
│       │    ├── Write to warning log (data/warnings/WARN.log)             │
│       │    ├── Add to validation report                                  │
│       │    ├── Flag affected rows                                        │
│       │    └── Continue processing                                        │
│       │                                                                  │
│       └── INFO                                                           │
│            │                                                             │
│            ├── Log INFO with context                                     │
│            └── Continue processing                                        │
│                                                                          │
│  All errors are aggregated into the final report:                        │
│    - Total errors by category                                            │
│    - Total warnings by category                                          │
│    - Affected row counts                                                 │
│    - Processing summary                                                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.4 Error Report Structure

```python
@dataclass
class ErrorReport:
    ticker: str
    started_at: datetime
    completed_at: datetime
    
    # Counts
    critical_count: int
    error_count: int
    warning_count: int
    info_count: int
    
    # By category
    data_integrity_errors: List[ErrorEntry]
    completeness_errors: List[ErrorEntry]
    consistency_errors: List[ErrorEntry]
    system_errors: List[ErrorEntry]
    corporate_action_errors: List[ErrorEntry]
    
    # Summary
    total_rows_processed: int
    rows_rejected: int
    rows_flagged: int
    rows_cleaned: int
    
    # Outcome
    pipeline_outcome: str  # "success", "partial_success", "failed"
    quality_score: float

@dataclass
class ErrorEntry:
    error_code: str          # "ERR-DI-03"
    severity: str            # "critical", "error", "warning", "info"
    category: str            # "data_integrity", "completeness", etc.
    message: str             # Human-readable description
    row_indices: List[int]   # Affected rows
    context: Dict            # Additional context
    timestamp: datetime      # When error occurred
    recommendation: str      # How to fix
```

### 8.5 Error Log Files

```
data/logs/
├── errors/
│   ├── critical_2024-07-04.log      ← CRITICAL errors
│   ├── error_2024-07-04.log         ← ERROR-level issues
│   └── warning_2024-07-04.log       ← WARNING-level issues
├── audit/
│   ├── audit_2024-07-04_AAPL.json   ← Per-ticker audit
│   └── audit_2024-07-04_batch.json  ← Batch summary
└── quality/
    ├── quality_2024-07-04.json      ← Quality scores
    └── quality_trend.json           ← Historical scores
```

---

## Appendix A: Configuration Reference

```yaml
# config/cleaning.yaml — Complete cleaning configuration

cleaning:
  # Pipeline version (for audit trail)
  pipeline_version: "0.1.0"
  
  # Schema validation
  schema:
    required_columns: ["timestamp", "open", "high", "low", "close", "volume"]
    optional_columns: ["adj_close", "ticker"]
    min_rows: 2
    timestamp_column: "timestamp"
    price_columns: ["open", "high", "low", "close"]
    volume_column: "volume"
  
  # Data validation
  validation:
    price_positive: true
    volume_non_negative: true
    ohlc_consistency: true
    timestamp_ascending: true
    no_duplicates: true
    max_missing_pct: 0.3
    max_price_change_pct: 0.5
    max_price_change_weekly_pct: 1.0
  
  # Cleaning strategies
  cleaning:
    duplicate_strategy: "keep_last"
    missing_strategy: "forward_fill"
    missing_fill_limit: 3
    outlier_strategy: "flag"
    outlier_zscore_threshold: 3.0
    outlier_iqr_multiplier: 1.5
    apply_corporate_actions: true
  
  # Normalization
  normalization:
    timezone: "UTC"
    price_precision: 2
    volume_type: "int64"
    sort_ascending: true
    set_index: "timestamp"
  
  # Quality scoring
  quality:
    enabled: true
    min_score: 70
    weights:
      completeness: 0.30
      validity: 0.30
      consistency: 0.20
      freshness: 0.10
      uniqueness: 0.10
    freshness_max_days: 50
  
  # Audit trail
  audit:
    enabled: true
    store_transformations: true
    store_hashes: true
    store_config_snapshot: true
  
  # Error handling
  errors:
    halt_on_critical: true
    halt_on_error: false
    log_warnings: true
    log_level: "INFO"
```

---

## Appendix B: Cross-Reference to Pipeline

| Pipeline Stage | Cleaning Module | Input | Output |
|---------------|----------------|-------|--------|
| Ingestion | DataIngestion | Files | Raw DataFrame |
| **Cleaning** | **DataValidator** | Raw DataFrame | ValidationReport |
| **Cleaning** | **DataProcessor** | Validated DataFrame | Cleaned DataFrame |
| **Cleaning** | **DataNormalizer** | Cleaned DataFrame | Normalized DataFrame |
| **Cleaning** | **QualityScorer** | Normalized DataFrame | QualityReport |
| Feature Engineering | FeatureEngine | Normalized DataFrame | Feature DataFrame |
| Label Generation | LabelEngine | Normalized DataFrame | Label Series |
| Dataset Assembly | DatasetBuilder | Features + Labels | DatasetSplit |
