# DATA INGESTION BLUEPRINT — Finance AI MVP

> Complete data ingestion system design for the Finance AI platform.
> Defines the historical data collection pipeline, validation rules, error handling, and metadata tracking.
> Every ingestion is traceable, idempotent, and produces immutable raw data.

---

## Table of Contents

1. [Supported Data Sources (MVP Only)](#1-supported-data-sources-mvp-only)
2. [Ingestion Pipeline](#2-ingestion-pipeline)
3. [Historical Backfill Strategy](#3-historical-backfill-strategy)
4. [Incremental Update Strategy](#4-incremental-update-strategy)
5. [Data Validation Rules](#5-data-validation-rules)
6. [Normalization Rules](#6-normalization-rules)
7. [Error Handling](#7-error-handling)
8. [Metadata Tracking](#8-metadata-tracking)
9. [Future Extension Points](#9-future-extension-points)

---

## 1. Supported Data Sources (MVP Only)

### 1.1 Source Overview

| Source | Data Type | Priority | Rate Limit | Fallback |
|--------|-----------|----------|------------|----------|
| **Yahoo Finance** | OHLCV, Corporate Actions | P0 | 2000 req/hr | Manual CSV |
| **NSE Historical** | OHLCV (Indian equities) | P1 | Varies | Yahoo Finance |
| **Trading Calendar** | Market open/close days | P0 | Unlimited | Hardcoded NYSE |
| **Corporate Actions** | Splits, Dividends | P1 | Varies | Yahoo Finance |

### 1.2 Yahoo Finance (Primary)

| Property | Value |
|----------|-------|
| **Library** | `yfinance` (Python) |
| **Data Types** | OHLCV candles, dividends, splits, ticker info |
| **Intervals** | 1d, 1wk, 1mo |
| **History** | Up to max period (10+ years for daily) |
| **Fields** | Open, High, Low, Close, Adj Close, Volume |
| **Tickers** | US equities (NYSE, NASDAQ, AMEX) |
| **Format** | DataFrame → CSV/Parquet |

**Capabilities:**
- Single ticker: `yf.download("AAPL", period="10y", interval="1d")`
- Multiple tickers: `yf.download(["AAPL", "MSFT"], period="10y")`
- Date range: `yf.download("AAPL", start="2016-01-01", end="2026-01-01")`
- Dividends: `ticker.dividends`
- Splits: `ticker.splits`
- Info: `ticker.info` (sector, industry, market cap)

**Limitations:**
- Rate limited (not officially documented)
- Occasional data gaps
- Adjusted close may lag
- No real-time data (15-min delay)

### 1.3 NSE Historical Data (Secondary)

| Property | Value |
|----------|-------|
| **Source** | NSE India website / API |
| **Data Types** | OHLCV (daily) |
| **Tickers** | NSE-listed Indian equities |
| **Format** | CSV download |
| **Priority** | P1 (not critical for MVP) |

**Note:** NSE data is region-specific. MVP focuses on US equities. NSE support is a future extension.

### 1.4 Trading Calendar

| Property | Value |
|----------|-------|
| **Source** | NYSE calendar (hardcoded + exchange_holidays library) |
| **Data Types** | Trading days, holidays, early closes |
| **Format** | CSV (generated) |
| **Priority** | P0 |

**Trading Calendar Data:**
```csv
date,is_trading_day,exchange,session_type
2024-01-01,true,NYSE,regular
2024-01-01,false,NASDAQ,holiday
2024-07-03,true,NYSE,early_close
2024-07-04,false,NYSE,holiday
```

**Sources:**
- `exchange_calendars` Python library
- NYSE official calendar
- NASDAQ official calendar
- Hardcoded federal holidays

### 1.5 Corporate Actions

| Property | Value |
|----------|-------|
| **Source** | Yahoo Finance (dividends, splits) |
| **Data Types** | Stock splits, dividends |
| **Format** | DataFrame → CSV |
| **Priority** | P1 |

**Corporate Actions Data:**
```csv
ticker,action_type,effective_date,ratio,amount,description
AAPL,split,2020-08-31,4.0,,4-for-1 stock split
AAPL,dividend,2024-08-09,,0.25,Quarterly dividend
MSFT,split,2021-03-29,2.0,,2-for-1 stock split
```

### 1.6 Source Priority & Fallback Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    Source Fallback Chain                      │
│                                                              │
│  Primary Source                                              │
│  ──────────────                                              │
│  Yahoo Finance (yfinance)                                    │
│       │                                                      │
│       ├── Success → Store raw data → Done                    │
│       │                                                      │
│       ▼ Failure                                              │
│  Retry (with backoff)                                        │
│       │                                                      │
│       ├── Success → Store raw data → Done                    │
│       │                                                      │
│       ▼ Failure after retries                                │
│  Manual CSV Import                                           │
│       │                                                      │
│       ├── Success → Store raw data → Done                    │
│       │                                                      │
│       ▼ Failure                                              │
│  Log error → Skip ticker → Continue with next ticker         │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│                                                              │
│  Trading Calendar Fallback Chain                             │
│  ────────────────────────────────                            │
│  1. exchange_calendars library                               │
│  2. Hardcoded NYSE holidays                                  │
│  3. Conservative default (assume trading day)                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Ingestion Pipeline

### 2.1 High-Level Pipeline Flow

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  Source  │──▶│  Fetch   │──▶│ Validate │──▶│ Normalize│──▶│ Store Raw│──▶│Log Meta  │
│  Select  │   │  Data    │   │  Data    │   │  Data    │   │  Data    │   │  data    │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
     │              │              │              │              │              │
     ▼              ▼              ▼              ▼              ▼              ▼
  Config       HTTP/API       Validation     Column/TZ     CSV/Parquet    Structured
  Loading      Request        Rules          Conversion    File Write     Log Entry
```

### 2.2 Detailed Pipeline Stages

#### Stage 1: Source Selection

```
Input:   Ticker list + config (source, interval, period)
Process: Load ticker list from config or CLI argument
Output:  List of (ticker, source, params) tuples
Logging: Ticker count, source selected, parameters
```

**Configuration:**
```yaml
ingestion:
  sources:
    yahoo_finance:
      enabled: true
      priority: 1
    nse:
      enabled: false
      priority: 2
  tickers:
    list: ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
    # or file: config/tickers.txt
  interval: "1d"
  period: "10y"
```

#### Stage 2: Fetch Data

```
Input:   (ticker, source, params) tuple
Process: Call source API/library to fetch historical data
Output:  Raw DataFrame (as-returned by source)
Logging: Source, ticker, request time, response size, duration
Error:   Retry with backoff, fallback to next source
```

**Fetch Logic:**
```python
# Pseudocode
for ticker in tickers:
    for source in sorted(sources, key=priority):
        try:
            raw_df = source.fetch(ticker, params)
            log_fetch_success(ticker, source, len(raw_df))
            break  # Success, move to validation
        except RateLimitError:
            wait_and_retry(source)
        except SourceError:
            log_fetch_failure(ticker, source, error)
            continue  # Try next source
    else:
        log_all_sources_failed(ticker)
        skip_ticker(ticker)
```

#### Stage 3: Validate Data

```
Input:   Raw DataFrame from fetch
Process: Run validation rules (Section 5)
Output:  ValidationResult { passed, issues, summary }
Logging: Rules checked, issues found, pass/fail
Error:   Reject file if critical errors, log warnings
```

**Validation Flow:**
```
Raw DataFrame
    │
    ├──▶ Check required columns (VAL-001)
    │        │
    │        ├── FAIL → Reject (return error)
    │        └── PASS → Continue
    │
    ├──▶ Check null values (VAL-002)
    │        │
    │        ├── FAIL → Reject (return error)
    │        └── PASS → Continue
    │
    ├──▶ Check timestamp ordering (VAL-003)
    │        │
    │        ├── FAIL → Reject (return error)
    │        └── PASS → Continue
    │
    ├──▶ Check duplicates (VAL-004)
    │        │
    │        ├── FAIL → Reject (return error)
    │        └── PASS → Continue
    │
    ├──▶ Check OHLCV ranges (VAL-005 to VAL-011)
    │        │
    │        ├── FAIL → Log bad rows, continue (warning)
    │        └── PASS → Continue
    │
    ├──▶ Check missing data % (VAL-012)
    │        │
    │        ├── HIGH → Log warning, continue
    │        └── OK → Continue
    │
    └──▶ Validation PASSED
             │
             ▼
         Return validated DataFrame
```

#### Stage 4: Normalize Data

```
Input:   Validated DataFrame
Process: Standardize columns, types, timezone (Section 6)
Output:  Normalized DataFrame
Logging: Transformations applied, column changes
```

**Normalization Steps:**
1. Rename columns to standard names
2. Convert timestamp to UTC datetime
3. Sort by timestamp (ascending)
4. Set datetime as index
5. Cast numeric columns to float64
6. Ensure volume is int64

#### Stage 5: Store Raw Data

```
Input:   Normalized DataFrame
Process: Write to data/raw/ directory
Output:  CSV/Parquet file
Logging: File path, row count, file size, checksum
Rules:   Raw data is IMMUTABLE after writing
```

**File Naming:**
```
data/raw/
├── {TICKER}_{interval}.csv          # e.g., AAPL_daily.csv
├── {TICKER}_{interval}.parquet      # Compressed alternative
├── calendar_{exchange}.csv          # e.g., calendar_NYSE.csv
└── actions_{TICKER}.csv             # e.g., actions_AAPL.csv
```

**Idempotency:**
- Before writing, check if file exists
- If exists: compare checksums
  - Same checksum → Skip (idempotent)
  - Different checksum → Overwrite (new data available)
  - Log the comparison result

#### Stage 6: Log Metadata

```
Input:   Ingestion result (success/failure, metadata)
Process: Write structured log entry
Output:  Log entry + metadata record
Logging: Full ingestion metadata (Section 8)
```

### 2.3 Pipeline State Machine

```
┌─────────────────────────────────────────────────────────────┐
│                    Ingestion State Machine                    │
│                                                              │
│  ┌──────────┐                                                │
│  │  IDLE    │                                                │
│  └────┬─────┘                                                │
│       │ start                                                │
│       ▼                                                      │
│  ┌──────────┐                                                │
│  │ FETCHING │◀──────────┐                                    │
│  └────┬─────┘           │                                    │
│       │                 │                                    │
│       ├── success       │ retry                              │
│       ▼                 │                                    │
│  ┌──────────┐           │                                    │
│  │VALIDATING│           │                                    │
│  └────┬─────┘           │                                    │
│       │                 │                                    │
│       ├── passed        │                                    │
│       ▼                 │                                    │
│  ┌──────────┐           │                                    │
│  │NORMALIZING│          │                                    │
│  └────┬─────┘           │                                    │
│       │                 │                                    │
│       ├── success       │                                    │
│       ▼                 │                                    │
│  ┌──────────┐           │                                    │
│  │ STORING  │           │                                    │
│  └────┬─────┘           │                                    │
│       │                 │                                    │
│       ├── success       │                                    │
│       ▼                 │                                    │
│  ┌──────────┐           │                                    │
│  │ LOGGING  │           │                                    │
│  └────┬─────┘           │                                    │
│       │                 │                                    │
│       ├── success       │                                    │
│       ▼                 │                                    │
│  ┌──────────┐           │                                    │
│  │ COMPLETED│           │                                    │
│  └──────────┘           │                                    │
│                         │                                    │
│  ┌──────────┐           │                                    │
│  │  FAILED  │───────────┘                                    │
│  └──────────┘                                                │
│       │                                                      │
│       ▼                                                      │
│  ┌──────────┐                                                │
│  │ SKIPPED  │  (ticker permanently failed)                   │
│  └──────────┘                                                │
└─────────────────────────────────────────────────────────────┘
```

### 2.4 Pipeline Orchestrator

```
┌─────────────────────────────────────────────────────────────┐
│                 Ingestion Orchestrator                        │
│                                                              │
│  Input:  Ticker list + config                                │
│                                                              │
│  FOR EACH ticker (parallel or sequential):                   │
│    1. Create IngestionJob                                    │
│    2. Run pipeline: fetch → validate → normalize → store     │
│    3. Record result (success/failure)                        │
│    4. Update metadata                                        │
│                                                              │
│  Output:  IngestionReport                                    │
│    - total_tickers: 100                                      │
│    - successful: 98                                          │
│    - failed: 2                                               │
│    - skipped: 0                                              │
│    - duration: 45.2s                                         │
│    - failed_tickers: ["BRK.A", "BF.B"]                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Historical Backfill Strategy

### 3.1 Backfill Modes

| Mode | Description | Use Case | Duration |
|------|-------------|----------|----------|
| **Quick** | 1 day of data | Testing, debugging | ~1 sec |
| **Recent** | 1 month of data | Recent trend analysis | ~2 sec |
| **Standard** | 1 year of data | Short-term modeling | ~5 sec |
| **Full** | Maximum history (10+ years) | Long-term modeling | ~30 sec |
| **Custom** | User-specified date range | Specific research | Varies |

### 3.2 Backfill Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Backfill Strategy                          │
│                                                              │
│  1. CHECK EXISTING DATA                                      │
│     │                                                        │
│     ├── No existing file → Fetch full range                  │
│     │                                                        │
│     └── Existing file found                                  │
│         │                                                    │
│         ├── Read last timestamp from existing file           │
│         │                                                    │
│         ├── Calculate gap: last_timestamp → today            │
│         │                                                    │
│         ├── Gap = 0 → Skip (already up to date)              │
│         │                                                    │
│         └── Gap > 0 → Fetch only the gap (incremental)       │
│                                                              │
│  2. FETCH DATA                                               │
│     │                                                        │
│     ├── Full backfill: yf.download(ticker, period="10y")     │
│     │                                                        │
│     └── Incremental: yf.download(ticker, start=last_date)    │
│                                                              │
│  3. MERGE                                                    │
│     │                                                        │
│     ├── Concatenate existing + new data                      │
│     │                                                        │
│     ├── Remove duplicates (by timestamp)                     │
│     │                                                        │
│     ├── Sort by timestamp ascending                          │
│     │                                                        │
│     └── Validate merged dataset                              │
│                                                              │
│  4. STORE                                                    │
│     │                                                        │
│     └── Write to data/raw/{TICKER}_daily.csv                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Backfill Configuration

```yaml
ingestion:
  backfill:
    # Default period
    default_period: "10y"
    
    # Period presets
    periods:
      quick: "1d"
      recent: "1mo"
      standard: "1y"
      full: "max"
    
    # Custom range
    custom:
      start_date: "2016-01-01"
      end_date: "2026-01-01"
    
    # Merge strategy
    merge_strategy: "concat_dedup"  # concat + deduplicate by timestamp
    
    # Skip if up to date
    skip_if_current: true
    current_threshold_days: 1  # Skip if data is within 1 day of today
```

### 3.4 Deduplication Logic

```
Existing Data (data/raw/AAPL_daily.csv):
┌────────────┬───────┬───────┬───────┬───────┬───────┬────────┐
│ timestamp  │ open  │ high  │ low   │ close │ adj   │ volume │
├────────────┼───────┼───────┼───────┼───────┼───────┼────────┤
│ 2024-01-02 │ 185.5 │ 186.3 │ 184.2 │ 185.6 │ 185.1 │ 450000 │
│ 2024-01-03 │ 184.8 │ 185.9 │ 183.7 │ 184.2 │ 183.7 │ 380000 │
│ ...        │ ...   │ ...   │ ...   │ ...   │ ...   │ ...    │
│ 2024-06-30 │ 192.3 │ 193.1 │ 191.5 │ 192.8 │ 192.3 │ 520000 │
└────────────┴───────┴───────┴───────┴───────┴───────┴────────┘

New Data (fetched from Yahoo Finance):
┌────────────┬───────┬───────┬───────┬───────┬───────┬────────┐
│ timestamp  │ open  │ high  │ low   │ close │ adj   │ volume │
├────────────┼───────┼───────┼───────┼───────┼───────┼────────┤
│ 2024-06-28 │ 191.5 │ 192.8 │ 190.9 │ 192.0 │ 191.5 │ 480000 │ ← Duplicate
│ 2024-06-30 │ 192.3 │ 193.1 │ 191.5 │ 192.8 │ 192.3 │ 520000 │ ← Duplicate
│ 2024-07-01 │ 193.0 │ 194.2 │ 192.1 │ 193.5 │ 193.0 │ 410000 │ ← New
│ 2024-07-02 │ 193.8 │ 195.0 │ 193.0 │ 194.2 │ 193.7 │ 390000 │ ← New
└────────────┴───────┴───────┴───────┴───────┴───────┴────────┘

Merged Data (after deduplication):
┌────────────┬───────┬───────┬───────┬───────┬───────┬────────┐
│ timestamp  │ open  │ high  │ low   │ close │ adj   │ volume │
├────────────┼───────┼───────┼───────┼───────┼───────┼────────┤
│ 2024-01-02 │ 185.5 │ 186.3 │ 184.2 │ 185.6 │ 185.1 │ 450000 │
│ ...        │ ...   │ ...   │ ...   │ ...   │ ...   │ ...    │
│ 2024-06-30 │ 192.3 │ 193.1 │ 191.5 │ 192.8 │ 192.3 │ 520000 │
│ 2024-07-01 │ 193.0 │ 194.2 │ 192.1 │ 193.5 │ 193.0 │ 410000 │ ← Added
│ 2024-07-02 │ 193.8 │ 195.0 │ 193.0 │ 194.2 │ 193.7 │ 390000 │ ← Added
└────────────┴───────┴───────┴───────┴───────┴───────┴────────┘
```

### 3.5 Backfill Rate Limiting

```
┌─────────────────────────────────────────────────────────────┐
│                    Rate Limit Strategy                        │
│                                                              │
│  Yahoo Finance:                                              │
│    - No official rate limit documented                       │
│    - Practical limit: ~2000 requests/hour                    │
│    - Strategy: 0.5s delay between requests                   │
│    - Batch multiple tickers in single request                │
│                                                              │
│  Batch Strategy:                                             │
│    - Download up to 10 tickers per request                   │
│    - Reduces total requests by 10x                           │
│    - Wait 2s between batches                                 │
│                                                              │
│  Rate Limiter:                                               │
│    - Token bucket algorithm                                  │
│    - Tokens: 2000 per hour                                   │
│    - Refill: ~0.56 tokens/second                             │
│    - Wait if bucket empty                                    │
│                                                              │
│  Example:                                                    │
│    100 tickers ÷ 10 per batch = 10 batches                   │
│    10 batches × 2s wait = 20s total                          │
│    Well within rate limits                                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Incremental Update Strategy

### 4.1 Daily Update Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Daily Update Flow                          │
│                                                              │
│  TRIGGER:                                                    │
│    - Cron job: daily at 6:00 PM EST (after market close)     │
│    - Manual: python scripts/update_data.py                   │
│                                                              │
│  FOR EACH ticker in watchlist:                               │
│                                                              │
│    1. CHECK LAST DATE                                        │
│       │                                                      │
│       ├── Read last timestamp from data/raw/{ticker}.csv     │
│       │                                                      │
│       ├── Calculate days since last update                   │
│       │                                                      │
│       └── Skip if 0 days (already current)                   │
│                                                              │
│    2. FETCH INCREMENTAL                                      │
│       │                                                      │
│       ├── start_date = last_timestamp + 1 day                │
│       ├── end_date = today                                   │
│       │                                                      │
│       └── yf.download(ticker, start=start_date, end=end_date)│
│                                                              │
│    3. VALIDATE NEW DATA                                      │
│       │                                                      │
│       ├── Run validation rules (Section 5)                   │
│       │                                                      │
│       └── Reject if critical errors                          │
│                                                              │
│    4. APPEND TO RAW FILE                                     │
│       │                                                      │
│       ├── Read existing CSV                                  │
│       ├── Concatenate new rows                               │
│       ├── Deduplicate by timestamp                           │
│       ├── Sort by timestamp                                  │
│       └── Write back to CSV                                  │
│                                                              │
│    5. LOG UPDATE                                             │
│       │                                                      │
│       ├── Records added: N                                   │
│       ├── Date range: YYYY-MM-DD to YYYY-MM-DD               │
│       └── File size: X KB                                    │
│                                                              │
│  OUTPUT: IngestionReport                                     │
│    - tickers_updated: 98                                     │
│    - tickers_skipped: 2                                      │
│    - records_added: 196                                      │
│    - duration: 45s                                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Update Configuration

```yaml
ingestion:
  incremental:
    enabled: true
    
    # Schedule
    schedule:
      cron: "0 18 * * 1-5"  # 6 PM EST, Mon-Fri
      timezone: "US/Eastern"
    
    # What to update
    watchlist:
      source: "config/tickers.txt"  # or inline list
      # tickers: ["AAPL", "MSFT", ...]
    
    # What to skip
    skip:
      if_current_days: 0  # Skip if data is from today
      if_no_trading_days: true  # Skip weekends/holidays
    
    # Append strategy
    append:
      dedup_strategy: "last_write_wins"  # or "first_write_wins"
      sort_after: true
      validate_before_append: true
```

### 4.3 Trading Calendar Integration

```
┌─────────────────────────────────────────────────────────────┐
│                 Trading Calendar Check                        │
│                                                              │
│  Before fetching data for a date range:                      │
│                                                              │
│  1. Load trading calendar for exchange                       │
│                                                              │
│  2. Filter requested dates                                   │
│     │                                                        │
│     ├── Remove weekends (Saturday, Sunday)                   │
│     │                                                        │
│     ├── Remove holidays (from calendar)                      │
│     │                                                        │
│     └── Keep only trading days                               │
│                                                              │
│  3. If no trading days in range → Skip fetch                 │
│                                                              │
│  4. If trading days exist → Fetch only those dates           │
│                                                              │
│  Example:                                                    │
│    Request: 2024-07-01 to 2024-07-07                        │
│    Calendar:                                                 │
│      2024-07-01 (Mon) → Trading day ✓                       │
│      2024-07-02 (Tue) → Trading day ✓                       │
│      2024-07-03 (Wed) → Early close ✓                       │
│      2024-07-04 (Thu) → Holiday ✗                           │
│      2024-07-05 (Fri) → Trading day ✓                       │
│      2024-07-06 (Sat) → Weekend ✗                           │
│      2024-07-07 (Sun) → Weekend ✗                           │
│    Fetch: 2024-07-01 to 2024-07-05 (4 days)                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4.4 Update Idempotency

| Scenario | Behavior |
|----------|----------|
| **First run (no existing data)** | Full backfill |
| **Second run (data exists, same date)** | Skip (no-op) |
| **Third run (data exists, new day)** | Append new day only |
| **Manual re-run (same data)** | Dedup → no change |
| **Corrupted file detected** | Re-fetch from scratch |
| **Partial update (interrupted)** | Resume from last good row |

---

## 5. Data Validation Rules

### 5.1 Validation Rule Reference

| Rule ID | Category | Rule | Severity | Action |
|---------|----------|------|----------|--------|
| VAL-001 | Schema | Required columns present | ERROR | Reject file |
| VAL-002 | Completeness | No nulls in required columns | ERROR | Reject row |
| VAL-003 | Ordering | Timestamps ascending | ERROR | Reject file |
| VAL-004 | Uniqueness | No duplicate timestamps per ticker | ERROR | Reject file |
| VAL-005 | Range | `open > 0` | ERROR | Reject row |
| VAL-006 | Range | `high > 0` | ERROR | Reject row |
| VAL-007 | Range | `low > 0` | ERROR | Reject row |
| VAL-008 | Range | `close > 0` | ERROR | Reject row |
| VAL-009 | Range | `volume >= 0` | ERROR | Reject row |
| VAL-010 | Consistency | `high >= max(open, close)` | ERROR | Reject row |
| VAL-011 | Consistency | `low <= min(open, close)` | ERROR | Reject row |
| VAL-012 | Completeness | Missing data % < 30% | WARNING | Log, proceed |
| VAL-013 | Anomaly | Price change > 50% in 1 day | WARNING | Log, flag |
| VAL-014 | Anomaly | Volume = 0 on non-holiday | WARNING | Log, flag |
| VAL-015 | Freshness | Data not older than 7 days | WARNING | Log, flag |

### 5.2 Validation Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Validation Flow                           │
│                                                              │
│  Raw DataFrame                                               │
│       │                                                      │
│       ▼                                                      │
│  ┌─────────────────┐                                         │
│  │ Schema Check    │  VAL-001                                │
│  │ (columns exist) │──── FAIL → Reject + Log                │
│  └────────┬────────┘                                         │
│           │ PASS                                             │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ Null Check      │  VAL-002                                │
│  │ (no nulls)      │──── FAIL → Reject + Log                │
│  └────────┬────────┘                                         │
│           │ PASS                                             │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ Order Check     │  VAL-003                                │
│  │ (ascending)     │──── FAIL → Reject + Log                │
│  └────────┬────────┘                                         │
│           │ PASS                                             │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ Duplicate Check │  VAL-004                                │
│  │ (no dupes)      │──── FAIL → Reject + Log                │
│  └────────┬────────┘                                         │
│           │ PASS                                             │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ OHLCV Range     │  VAL-005 to VAL-011                     │
│  │ (valid prices)  │──── FAIL → Log bad rows, continue      │
│  └────────┬────────┘                                         │
│           │ PASS (or warnings only)                          │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ Missing Data %  │  VAL-012                                │
│  │ (< 30%)         │──── HIGH → Log warning, continue       │
│  └────────┬────────┘                                         │
│           │ OK                                               │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ Anomaly Check   │  VAL-013, VAL-014                       │
│  │ (reasonable)    │──── ANOMALY → Log warning, flag        │
│  └────────┬────────┘                                         │
│           │ OK                                               │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ Freshness Check │  VAL-015                                │
│  │ (not stale)     │──── STALE → Log warning                │
│  └────────┬────────┘                                         │
│           │ OK                                               │
│           ▼                                                  │
│  Validation PASSED                                           │
│       │                                                      │
│       ▼                                                      │
│  Return ValidationResult                                     │
│    - passed: True                                            │
│    - issues: [list of warnings]                              │
│    - summary: {errors: 0, warnings: 2}                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 Validation Report Structure

```python
@dataclass
class ValidationResult:
    passed: bool                          # Overall pass/fail
    rules_checked: int                    # Number of rules evaluated
    errors: int                           # Critical errors found
    warnings: int                         # Non-critical issues found
    issues: List[ValidationIssue]         # Detailed issues list
    summary: Dict[str, int]               # Counts by category

@dataclass
class ValidationIssue:
    rule_id: str                          # "VAL-001"
    severity: str                         # "error" | "warning"
    category: str                         # "schema", "range", "anomaly"
    column: str                           # Column name (or "timestamp")
    message: str                          # Human-readable description
    affected_rows: int                    # Number of rows affected
    sample_values: List[Any]              # Example values for debugging
    recommendation: str                   # How to fix
```

### 5.4 Trading Holiday Validation

```
┌─────────────────────────────────────────────────────────────┐
│                 Trading Holiday Check                         │
│                                                              │
│  Purpose: Detect if data exists for non-trading days         │
│                                                              │
│  Logic:                                                      │
│    1. Load trading calendar                                  │
│    2. For each timestamp in data:                            │
│       │                                                      │
│       ├── Is it a trading day?                               │
│       │    ├── YES → Valid                                   │
│       │    └── NO → Flag as anomaly                          │
│       │                                                      │
│       └── Is volume > 0 on non-trading day?                  │
│            ├── YES → Major anomaly (reject)                  │
│            └── NO → Minor anomaly (warn)                     │
│                                                              │
│  Common Non-Trading Days:                                    │
│    - Weekends (Sat, Sun)                                     │
│    - New Year's Day (Jan 1)                                  │
│    - Martin Luther King Jr. Day (3rd Mon Jan)                │
│    - Presidents' Day (3rd Mon Feb)                           │
│    - Good Friday (varies)                                    │
│    - Memorial Day (last Mon May)                             │
│    - Juneteenth (Jun 19)                                     │
│    - Independence Day (Jul 4)                                │
│    - Labor Day (1st Mon Sep)                                 │
│    - Thanksgiving (4th Thu Nov)                              │
│    - Christmas (Dec 25)                                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Normalization Rules

### 6.1 Column Normalization

| Source Column | Normalized Column | Type | Notes |
|---------------|-------------------|------|-------|
| `Date` | `timestamp` | datetime64[ns] | UTC, ISO 8601 |
| `Open` | `open` | float64 | > 0 |
| `High` | `high` | float64 | > 0 |
| `Low` | `low` | float64 | > 0 |
| `Close` | `close` | float64 | > 0 |
| `Adj Close` | `adj_close` | float64 | Adjusted for splits/dividends |
| `Volume` | `volume` | int64 | >= 0 |
| `Ticker` | `ticker` | str | Uppercase, stripped |

### 6.2 Timestamp Normalization

```
┌─────────────────────────────────────────────────────────────┐
│                 Timestamp Normalization                       │
│                                                              │
│  Source Formats (examples):                                  │
│    "2024-01-02"                                              │
│    "2024-01-02 00:00:00"                                     │
│    "2024-01-02T00:00:00Z"                                    │
│    "01/02/2024"                                              │
│    "January 2, 2024"                                         │
│                                                              │
│  Normalized Format:                                          │
│    2024-01-02 00:00:00+00:00 (UTC)                          │
│                                                              │
│  Rules:                                                      │
│    1. Parse to datetime using pandas.to_datetime()           │
│    2. Convert to UTC (if timezone-naive, assume UTC)         │
│    3. Set time to 00:00:00 for daily data                   │
│    4. Set as DataFrame index                                 │
│    5. Ensure ascending order                                 │
│                                                              │
│  Timezone Handling:                                          │
│    - Source data is usually timezone-naive                   │
│    - Assume US market timezone (ET) if naive                 │
│    - Convert to UTC for storage                              │
│    - Store as TIMESTAMP (without timezone in DB)             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 Symbol Normalization

```
┌─────────────────────────────────────────────────────────────┐
│                 Symbol Normalization                          │
│                                                              │
│  Input (various formats):                                    │
│    "AAPL"                                                    │
│    "aapl"                                                    │
│    "aapl.us"                                                 │
│    "AAPL.US"                                                 │
│    "Apple Inc."                                               │
│                                                              │
│  Normalized Output:                                          │
│    "AAPL"                                                    │
│                                                              │
│  Rules:                                                      │
│    1. Strip whitespace                                       │
│    2. Convert to uppercase                                   │
│    3. Remove exchange suffix (.US, .L, etc.)                 │
│    4. Remove dots unless part of ticker (BRK.B)              │
│    5. Validate format: ^[A-Z]{1,5}(\.[A-Z])?$               │
│                                                              │
│  Special Cases:                                              │
│    "BRK.B" → "BRK.B" (valid, has dot)                       │
│    "BF.B"  → "BF.B" (valid, has dot)                        │
│    "TICKER.US" → "TICKER" (remove suffix)                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 6.4 Interval Normalization

| Source Format | Normalized | Description |
|---------------|------------|-------------|
| `1d`, `daily`, `D` | `"1d"` | Daily |
| `1wk`, `weekly`, `W` | `"1wk"` | Weekly |
| `1mo`, `monthly`, `M` | `"1mo"` | Monthly |
| `1h`, `hourly`, `60m` | `"1h"` | Hourly (future) |

### 6.5 Numeric Precision

```
┌─────────────────────────────────────────────────────────────┐
│                 Numeric Precision Rules                       │
│                                                              │
│  Prices (open, high, low, close, adj_close):                 │
│    - Source: float64 (variable precision)                    │
│    - Storage: float64 (pandas default)                       │
│    - Display: 2 decimal places (USD)                         │
│    - DB: NUMERIC(12,4) for PostgreSQL                        │
│                                                              │
│  Volume:                                                     │
│    - Source: int64 or float64                                │
│    - Storage: int64                                          │
│    - Display: integer with commas                            │
│    - DB: BIGINT                                              │
│                                                              │
│  Ratios (returns, volatility):                               │
│    - Source: float64                                         │
│    - Storage: float64                                        │
│    - Display: 4 decimal places                               │
│    - DB: DOUBLE PRECISION                                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 6.6 Normalization Flow

```
Raw DataFrame (from source)
    │
    ├──▶ Rename columns to standard names
    │    {"Date": "timestamp", "Open": "open", ...}
    │
    ├──▶ Parse timestamps to datetime
    │    pd.to_datetime(df["timestamp"])
    │
    ├──▶ Convert to UTC
    │    df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")
    │
    ├──▶ Set datetime as index
    │    df = df.set_index("timestamp")
    │
    ├──▶ Sort by timestamp ascending
    │    df = df.sort_index()
    │
    ├──▶ Cast numeric columns
    │    df["open"] = df["open"].astype("float64")
    │    df["volume"] = df["volume"].astype("int64")
    │
    ├──▶ Normalize ticker symbol
    │    df["ticker"] = ticker.upper().strip()
    │
    └──▶ Return normalized DataFrame
```

---

## 7. Error Handling

### 7.1 Error Categories

| Category | Examples | Severity | Handling |
|----------|----------|----------|----------|
| **Network** | Timeout, connection refused, DNS failure | HIGH | Retry with backoff |
| **Rate Limit** | HTTP 429, Too Many Requests | MEDIUM | Wait and retry |
| **Auth** | HTTP 401, 403 | HIGH | Log and skip |
| **Not Found** | HTTP 404, ticker delisted | LOW | Log and skip |
| **Data** | Invalid prices, missing fields | MEDIUM | Validate and log |
| **Storage** | Disk full, permission denied | HIGH | Log and abort |
| **Schema** | Unexpected columns, wrong types | MEDIUM | Log and skip |

### 7.2 Retry Policy

```
┌─────────────────────────────────────────────────────────────┐
│                    Retry Policy                               │
│                                                              │
│  Strategy: Exponential Backoff with Jitter                   │
│                                                              │
│  Parameters:                                                 │
│    max_retries: 3                                            │
│    base_delay: 1.0 seconds                                   │
│    max_delay: 60.0 seconds                                   │
│    exponential_base: 2                                       │
│    jitter: random(0, 0.5) * delay                            │
│                                                              │
│  Retry Schedule:                                             │
│    Attempt 1: Wait 1.0s + jitter                             │
│    Attempt 2: Wait 2.0s + jitter                             │
│    Attempt 3: Wait 4.0s + jitter                             │
│    After 3 failures: Give up, log error, skip ticker         │
│                                                              │
│  Retryable Errors:                                           │
│    - ConnectionError                                          │
│    - TimeoutError                                            │
│    - HTTP 429 (Too Many Requests)                             │
│    - HTTP 500-599 (Server Errors)                             │
│                                                              │
│  Non-Retryable Errors:                                       │
│    - HTTP 401 (Unauthorized)                                 │
│    - HTTP 403 (Forbidden)                                    │
│    - HTTP 404 (Not Found)                                    │
│    - ValueError (invalid data)                               │
│    - FileNotFoundError                                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 7.3 Rate Limit Handling

```
┌─────────────────────────────────────────────────────────────┐
│                 Rate Limit Handling                           │
│                                                              │
│  Detection:                                                  │
│    - HTTP 429 response                                       │
│    - "Rate limit exceeded" in response body                  │
│    - X-RateLimit-Remaining header = 0                        │
│                                                              │
│  Response:                                                   │
│    1. Extract Retry-After header (if present)                │
│    2. If no Retry-After: wait 60 seconds                     │
│    3. Log rate limit event                                    │
│    4. Reduce batch size for next request                     │
│    5. Retry request                                          │
│                                                              │
│  Prevention:                                                 │
│    - Maintain token bucket (2000 tokens/hour)                │
│    - Wait if bucket empty                                    │
│    - Batch requests (10 tickers per request)                 │
│    - 0.5s delay between requests                             │
│    - 2s delay between batches                                │
│                                                              │
│  Monitoring:                                                 │
│    - Log rate limit events                                   │
│    - Track tokens remaining                                  │
│    - Alert if rate limit hit frequently                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 7.4 Partial Failure Handling

```
┌─────────────────────────────────────────────────────────────┐
│                 Partial Failure Strategy                      │
│                                                              │
│  Scenario: Batch of 100 tickers, 5 fail                     │
│                                                              │
│  Strategy: Continue with successful tickers                  │
│                                                              │
│  1. Log each failure individually                            │
│  2. Track failed tickers in separate list                    │
│  3. Continue processing remaining tickers                    │
│  4. Generate partial success report                          │
│  5. Optionally retry failed tickers later                    │
│                                                              │
│  Report:                                                     │
│    total: 100                                                │
│    successful: 95                                            │
│    failed: 5                                                 │
│    failed_tickers: ["BRK.A", "BF.B", "SEEK", "XYZ", "ABC"]  │
│    failed_reasons: {                                         │
│      "BRK.A": "Rate limit exceeded after 3 retries",        │
│      "BF.B": "Data source returned empty response",          │
│      "SEEK": "Ticker not found (delisted?)",                 │
│      "XYZ": "Timeout after 30s",                             │
│      "ABC": "Invalid price data (all zeros)"                 │
│    }                                                         │
│                                                              │
│  Retry Strategy:                                             │
│    - Option A: Retry immediately (if transient)              │
│    - Option B: Queue for later retry                         │
│    - Option C: Skip and report (for permanent failures)      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 7.5 Error Logging

```python
@dataclass
class IngestionError:
    ticker: str
    error_type: str              # "network", "rate_limit", "data", "storage"
    error_message: str           # Human-readable description
    source: str                  # "yahoo_finance"
    attempt: int                 # 1, 2, 3
    timestamp: datetime          # When error occurred
    traceback: str               # Full traceback (for debugging)
    retryable: bool              # Whether to retry
    context: Dict                # Additional context (params, response, etc.)

# Example log entry
{
    "event": "ingestion_error",
    "ticker": "BRK.A",
    "error_type": "rate_limit",
    "error_message": "HTTP 429: Too Many Requests",
    "source": "yahoo_finance",
    "attempt": 3,
    "timestamp": "2024-07-04T18:30:00Z",
    "retryable": true,
    "context": {
        "retry_after": 60,
        "tokens_remaining": 0,
        "batch_size": 10
    }
}
```

---

## 8. Metadata Tracking

### 8.1 Ingestion Metadata Schema

```python
@dataclass
class IngestionMetadata:
    # Identity
    ingestion_id: str              # UUID for this ingestion run
    ticker: str                    # Ticker symbol
    
    # Source
    source: str                    # "yahoo_finance"
    source_url: str                # API endpoint or file path
    
    # Timing
    fetch_started_at: datetime     # When fetch started
    fetch_completed_at: datetime   # When fetch completed
    fetch_duration_ms: float       # Duration in milliseconds
    
    # Data
    record_count: int              # Number of records fetched
    date_range_start: str          # First date in data
    date_range_end: str            # Last date in data
    columns: List[str]             # Column names
    
    # Quality
    validation_passed: bool        # Whether validation passed
    validation_errors: int         # Number of validation errors
    validation_warnings: int       # Number of validation warnings
    
    # Storage
    file_path: str                 # Path to stored file
    file_size_bytes: int           # File size
    file_format: str               # "csv" or "parquet"
    checksum: str                  # SHA-256 of file content
    
    # Status
    status: str                    # "success", "failed", "skipped"
    error_message: str             # Error message (if failed)
    
    # Versioning
    data_version: str              # Version of data (date-based)
    pipeline_version: str          # Version of ingestion pipeline
    
    # Environment
    environment: str               # "development", "production"
    python_version: str            # Python version used
    library_versions: Dict         # yfinance, pandas versions
```

### 8.2 Metadata Storage

**MVP (File-based):**
```
data/raw/
├── metadata/
│   ├── AAPL_daily_metadata.json
│   ├── MSFT_daily_metadata.json
│   └── ingestion_log_2024-07-04.json
```

**Phase 2 (Database):**
```sql
CREATE TABLE ingestion_metadata (
    ingestion_id UUID PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    source VARCHAR(50) NOT NULL,
    fetch_started_at TIMESTAMP NOT NULL,
    fetch_completed_at TIMESTAMP,
    fetch_duration_ms FLOAT,
    record_count INTEGER,
    date_range_start DATE,
    date_range_end DATE,
    validation_passed BOOLEAN,
    validation_errors INTEGER,
    validation_warnings INTEGER,
    file_path TEXT,
    file_size_bytes BIGINT,
    file_format VARCHAR(10),
    checksum VARCHAR(64),
    status VARCHAR(20),
    error_message TEXT,
    data_version VARCHAR(20),
    pipeline_version VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 8.3 Checksum Calculation

```python
import hashlib

def compute_checksum(file_path: Path) -> str:
    """Compute SHA-256 checksum of file content."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

# Example: "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0..."
```

### 8.4 Metadata Log Entry

```json
{
    "event": "ingestion_completed",
    "ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
    "ticker": "AAPL",
    "source": "yahoo_finance",
    "fetch_started_at": "2024-07-04T18:00:00Z",
    "fetch_completed_at": "2024-07-04T18:00:02Z",
    "fetch_duration_ms": 2000,
    "record_count": 2520,
    "date_range_start": "2014-07-04",
    "date_range_end": "2024-07-04",
    "columns": ["open", "high", "low", "close", "adj_close", "volume"],
    "validation_passed": true,
    "validation_errors": 0,
    "validation_warnings": 1,
    "file_path": "data/raw/AAPL_daily.csv",
    "file_size_bytes": 256000,
    "file_format": "csv",
    "checksum": "a1b2c3d4e5f6...",
    "status": "success",
    "data_version": "2024-07-04",
    "pipeline_version": "0.1.0"
}
```

### 8.5 Ingestion Report

```
┌─────────────────────────────────────────────────────────────┐
│                 Ingestion Report                              │
│                                                              │
│  Run ID:     550e8400-e29b-41d4-a716-446655440000           │
│  Started:    2024-07-04 18:00:00 UTC                         │
│  Completed:  2024-07-04 18:00:45 UTC                         │
│  Duration:   45.2 seconds                                    │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│                                                              │
│  Total Tickers:     100                                      │
│  Successful:        98                                       │
│  Failed:            2                                        │
│  Skipped:           0                                        │
│                                                              │
│  Records Ingested:  252,000                                  │
│  Data Range:        2014-07-04 to 2024-07-04                 │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│                                                              │
│  Validation Summary:                                         │
│    Errors:          0                                        │
│    Warnings:        12                                       │
│    Anomalies:       3                                        │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│                                                              │
│  Failed Tickers:                                             │
│    1. BRK.A — Rate limit exceeded after 3 retries            │
│    2. BF.B  — Data source returned empty response            │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│                                                              │
│  Files Written:                                              │
│    data/raw/AAPL_daily.csv (256 KB)                          │
│    data/raw/MSFT_daily.csv (248 KB)                          │
│    ... (98 files)                                            │
│                                                              │
│  Total Size:      24.5 MB                                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. Future Extension Points

### 9.1 Placeholder: Live WebSocket Feed

| Property | Value |
|----------|-------|
| **Module** | `src/data/live_feed.py` |
| **Purpose** | Real-time price data via WebSocket |
| **Sources** | Polygon.io, Alpha Vantage WebSocket, IEX Cloud |
| **Data Types** | Real-time trades, quotes, OHLCV (1-min) |
| **Status** | ⏳ Placeholder — not in MVP |

**Integration Point:**
```python
class LiveFeed:
    def connect(self, tickers: List[str]) -> None:
        """Connect to WebSocket feed."""
        pass
    
    def on_tick(self, callback: Callable) -> None:
        """Register tick handler."""
        pass
    
    def disconnect(self) -> None:
        """Disconnect from feed."""
        pass
```

### 9.2 Placeholder: News Ingestion

| Property | Value |
|----------|-------|
| **Module** | `src/data/news_ingestion.py` |
| **Purpose** | Ingest news articles and press releases |
| **Sources** | NewsAPI, SEC EDGAR, RSS feeds |
| **Data Types** | Headlines, articles, filings |
| **Status** | ⏳ Placeholder — not in MVP |

**Integration Point:**
```python
class NewsIngestion:
    def fetch_news(self, ticker: str, date_range: Tuple) -> List[Article]:
        """Fetch news articles for a ticker."""
        pass
    
    def fetch_filings(self, ticker: str) -> List[Filing]:
        """Fetch SEC filings for a ticker."""
        pass
```

### 9.3 Placeholder: Options Chain Ingestion

| Property | Value |
|----------|-------|
| **Module** | `src/data/options_ingestion.py` |
| **Purpose** | Ingest options chain data |
| **Sources** | CBOE, Yahoo Finance Options, Polygon.io |
| **Data Types** | Calls, puts, strikes, expirations, IV |
| **Status** | ⏳ Placeholder — not in MVP |

**Integration Point:**
```python
class OptionsIngestion:
    def fetch_chain(self, ticker: str, expiration: date) -> OptionsChain:
        """Fetch options chain for a ticker and expiration."""
        pass
    
    def fetch_all_expirations(self, ticker: str) -> List[OptionsChain]:
        """Fetch all available expirations."""
        pass
```

### 9.4 Placeholder: Macro Data Ingestion

| Property | Value |
|----------|-------|
| **Module** | `src/data/macro_ingestion.py` |
| **Purpose** | Ingest macroeconomic indicators |
| **Sources** | FRED API, World Bank, IMF |
| **Data Types** | GDP, CPI, interest rates, unemployment |
| **Status** | ⏳ Placeholder — not in MVP |

**Integration Point:**
```python
class MacroIngestion:
    def fetch_indicator(self, indicator: str, date_range: Tuple) -> pd.Series:
        """Fetch macro indicator time series."""
        pass
    
    def fetch_all(self, indicators: List[str]) -> pd.DataFrame:
        """Fetch multiple indicators."""
        pass
```

### 9.5 Placeholder: Sentiment Feed

| Property | Value |
|----------|-------|
| **Module** | `src/data/sentiment_ingestion.py` |
| **Purpose** | Ingest social media sentiment data |
| **Sources** | Twitter API, StockTwits, Reddit |
| **Data Types** | Sentiment scores, social volume |
| **Status** | ⏳ Placeholder — not in MVP |

**Integration Point:**
```python
class SentimentIngestion:
    def fetch_sentiment(self, ticker: str, date_range: Tuple) -> pd.Series:
        """Fetch sentiment time series for a ticker."""
        pass
    
    def fetch_social_volume(self, ticker: str, date_range: Tuple) -> pd.Series:
        """Fetch social media mention volume."""
        pass
```

### 9.6 Extension Summary

| Extension | Module | Source | Data Type | Status |
|-----------|--------|--------|-----------|--------|
| Live WebSocket | `src/data/live_feed.py` | Polygon, IEX | Real-time prices | ⏳ Placeholder |
| News Ingestion | `src/data/news_ingestion.py` | NewsAPI, EDGAR | Articles, filings | ⏳ Placeholder |
| Options Chain | `src/data/options_ingestion.py` | CBOE, Yahoo | Options data | ⏳ Placeholder |
| Macro Data | `src/data/macro_ingestion.py` | FRED, World Bank | Economic indicators | ⏳ Placeholder |
| Sentiment Feed | `src/data/sentiment_ingestion.py` | Twitter, Reddit | Sentiment scores | ⏳ Placeholder |

---

## Appendix A: Configuration Reference

```yaml
# config/ingestion.yaml — Complete ingestion configuration

ingestion:
  # Source configuration
  sources:
    yahoo_finance:
      enabled: true
      priority: 1
      rate_limit:
        tokens_per_hour: 2000
        batch_size: 10
        delay_between_requests_ms: 500
        delay_between_batches_ms: 2000
      retry:
        max_retries: 3
        base_delay_s: 1.0
        max_delay_s: 60.0
    
    nse:
      enabled: false
      priority: 2
  
  # Ticker configuration
  tickers:
    source: "config/tickers.txt"  # or inline list
    # list: ["AAPL", "MSFT", ...]
    filter:
      exchanges: ["NYSE", "NASDAQ", "AMEX"]
      min_market_cap: 1000000000  # $1B
      exclude: ["BRK.A", "BF.B"]  # Problematic tickers
  
  # Data configuration
  data:
    interval: "1d"
    period: "10y"
    adjustments: true  # Include adjusted close
  
  # Backfill configuration
  backfill:
    default_period: "10y"
    merge_strategy: "concat_dedup"
    skip_if_current_days: 1
  
  # Incremental update
  incremental:
    enabled: true
    schedule: "0 18 * * 1-5"  # 6 PM EST, Mon-Fri
    timezone: "US/Eastern"
  
  # Validation
  validation:
    max_missing_pct: 0.3
    max_price_change_pct: 0.5
    reject_on_error: true
    log_warnings: true
  
  # Storage
  storage:
    raw_dir: "data/raw"
    format: "csv"  # or "parquet"
    compression: null  # for parquet: "gzip", "snappy"
    immutable: true  # Never overwrite raw data
  
  # Metadata
  metadata:
    enabled: true
    store_with_data: true  # Store metadata alongside data
    log_format: "json"
  
  # Error handling
  errors:
    continue_on_failure: true  # Don't abort entire run
    log_failed_tickers: true
    retry_failed: true  # Queue for retry
```

---

## Appendix B: Cross-Reference to Data Architecture

| Data Architecture Table | Ingestion Module | Data Flow |
|------------------------|-----------------|-----------|
| `instruments` | DataIngestion (ticker info) | Source → instruments |
| `market_candles` | DataIngestion (OHLCV) | Source → market_candles |
| `corporate_actions` | DataIngestion (splits/dividends) | Source → corporate_actions |
| `trading_calendar` | TradingCalendar (generated) | Calendar → trading_calendar |
| `features` | FeatureEngine (downstream) | market_candles → features |
| `labels` | LabelEngine (downstream) | market_candles → labels |
| `dataset_versions` | DatasetBuilder (downstream) | features + labels → dataset_versions |
| `model_predictions` | PredictionService (downstream) | model → model_predictions |
