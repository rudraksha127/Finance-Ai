# DATA CLEANING ENGINE — IMPLEMENTATION (Milestone 03)

> **Status:** Implemented
> **Date:** 2026-09-04
> **Architecture source:** `docs/DATA_CLEANING_VALIDATION.md` (all sections),
> `docs/DATA_ARCHITECTURE.md` §7 (storage tiers), §3.3 (corporate actions)
> **Parent milestone:** 03 — Data Cleaning & Quality Engine

This document records the implemented cleaning + quality pipeline for the
file-based MVP (ADR-0005). It is the implementation companion to
`DATA_CLEANING_VALIDATION.md`; the architecture was **not** redesigned.

---

## 1. Objective

Implement a deterministic pipeline over the Milestone-02 raw tier:

```
Raw Market Data (data/raw/{TICKER}_{interval}.csv)
      ↓
Validation (VAL-* rules, explicit per-record reasons)
      ↓
Cleaning (dedup, OHLC fix, missing-data strategies)
      ↓
Corporate-Action Adjustment (split / bonus / dividend / ticker change)
      ↓
Normalization (sort, casts, identity, traceability)
      ↓
Quality Scoring (0–100, five dimensions)
      ↓
Interim Tier (data/interim/cleaned_…_csv) + Audit Trail
```

The **raw tier is never modified** (DATA_ARCHITECTURE §7.1 immutability).
Corporate actions adjust **copies**; cleaned output is written separately.

## 2. Implementation Location

| Module | Responsibility |
|--------|----------------|
| `src/cleaning/io.py` | Tolerant raw-CSV reader (traceability `raw_line`), SHA-256 hashing, interim writer, holiday loader |
| `src/cleaning/validation.py` | `validate_batch` — VAL-S01..VAL-C03 rule engine, explicit reasons per record |
| `src/cleaning/cleaning.py` | `clean_batch` — dedup, OHLC repair, missing-value strategies, outlier flag |
| `src/cleaning/actions.py` | Corporate-action backward adjustment (split/bonus/dividend/ticker change) |
| `src/cleaning/quality.py` | `compute_quality` — 0–100 score, ratings, quality gate |
| `src/cleaning/audit.py` | Transformation log, `AuditRecord`, per-run JSON + append-only JSONL |
| `src/cleaning/pipeline.py` | `CleaningPipeline` — stage state machine (8 stages), normalization, orchestration |

Configuration added under `config/default.yaml` `cleaning:` and typed in
`src/config/loader.py` (`CleaningConfig` + sub-configs), mirroring
DATA_CLEANING_VALIDATION.md Appendix A.

## 3. Validation Engine (implemented rules)

Every failed record receives an explicit reason (rule_id + severity +
category + message + raw_line). Implemented checks:

| Rule | Check | Severity | Action |
|------|-------|----------|--------|
| VAL-S01 | Required columns present | error | schema fail |
| VAL-S03 | Minimum rows ≥ 2 | error | schema fail |
| VAL-S04 | Timestamp/row parseable | error | row rejected |
| VAL-P01..P04 | open/high/low/close > 0 | error | row rejected |
| VAL-P05 | high ≥ max(open, close) | error | fixed |
| VAL-P06 | low ≤ min(open, close) | error | fixed |
| VAL-P07 | adj_close > 0 | warning | flagged |
| VAL-P08 | daily price change < 50% | warning | flagged |
| VAL-V01 | volume ≥ 0 | error | row rejected |
| VAL-V02 | zero volume on trading day | warning | flagged |
| VAL-V03 | volume < 1000 | warning | flagged |
| VAL-T01 | no duplicate timestamps | error | dedup |
| VAL-T02 | ascending order | warning | sorted |
| VAL-T03 | no future timestamps | error | row rejected |
| VAL-T04 | no weekend data | warning | flagged |
| VAL-T05 | no holiday data | warning | flagged (optional holiday calendar) |
| VAL-C01 | missing < 30% per column | warning | logged |
| VAL-C02 | no gaps > 5 days | warning | logged (missing candles detected, not fabricated) |

## 4. Cleaning Engine (deterministic policies)

- **Duplicate removal** — `duplicate_strategy: keep_last` (default) or
  `keep_first`, keyed by timestamp.
- **OHLC repair** — high = max(high, open, close); low = min(low, open, close).
- **Missing values** — gap of 1 → forward fill; 2..N (≤ `missing_fill_limit`)
  → linear interpolation with a ±20% **both-neighbor** sanity guard (fallback:
  forward fill); 6–10 → marked incomplete (kept with `incomplete` flag);
  > 10 → row dropped. Leading/trailing gaps are never extrapolated.
- **Volume** — missing → zero fill (per blueprint, never fabricated prices).
- **Adj close** — forward fill like close; never interpolated.
- **Outliers** — z-score on daily close returns (threshold 3.0 default);
  flagged and **kept** (blueprint §5.3 `flag` strategy).

Cleaned records keep their `raw_line` for full traceability.

## 5. Corporate Actions

Implemented per DATA_CLEANING_VALIDATION.md §3 (backward adjustment):

- **Split / bonus / reverse split** — historical OHLC × `1/ratio`
  (ratio < 1 for reverse); bonus modeled as split-like (1:1 → ratio 2).
- **Dividend** — historical OHLC × `1 − D / close_before_ex_date`
  (ex-date itself is _not_ adjusted; the pre-ex close is the last close
  strictly before the ex-date).
- **Ticker change** — rename only, no price adjustment (§3.6).
- Defensive checks: ratio > 0, dividend factor must stay positive,
  effective_date parseability, unsupported types rejected.
- Action source: optional `data/external/corporate_actions/{TICKER}.json`
  (JSON list; fields per DATA_ARCHITECTURE §3.3).
- Raw records are **never** rewritten — adjustment operates on copies.

## 6. Quality Score

Formula (DATA_CLEANING_VALIDATION.md §6.2), weights 30/30/20/10/10:

```
score = completeness×0.30 + validity×0.30 + consistency×0.20
      + freshness×0.10 + uniqueness×0.10   (0–100)
```

- Completeness: 1 − missing_cells/total_cells (required columns)
- Validity: rows passing all ERROR-level rules / total (rejected-exclusive)
- Consistency: rows with correct OHLC relationships / total
- Freshness: max(0, 100 − 2·days_since_last), capped at `freshness_max_days`
- Uniqueness: unique timestamps / total

Ratings: ≥90 excellent, ≥80 good, ≥70 fair, ≥60 poor, <60 failing.
Gate: ≥90 PASS, 70–89 PASS_WITH_WARNINGS, 60–69 REVIEW_REQUIRED, <60 FAIL.
Score is stored in the audit record (metadata), not just logged.

## 7. Audit Trail

Per DATA_CLEANING_VALIDATION.md §7:

- **Every cleaned record** references `raw_line` (raw record ID), and the
  audit record stores the raw file SHA-256, cleaning timestamp, cleaning
  `pipeline_version`, validation status (errors/warnings counts), and the
  full ordered transformation history.
- `data/interim/audit/audit_{date}_{TICKER}_{interval}_{id}.json` (per run)
- `data/interim/audit/audit_log.jsonl` (append-only)

## 8. Output (storage separation)

Per DATA_ARCHITECTURE §7.1 the interim tier holds "validated data, cleaned
data"; the processed tier holds versioned features/labels/datasets (later
milestones). Cleaned output therefore goes to:

```
data/interim/cleaned_{YYYYMMDD}_{TICKER}_{interval}.csv
```

with columns `ticker,timestamp,open,high,low,close,adj_close,volume,raw_line`
(+ `incomplete`/`outlier_flagged`/`adjustments` carried as flags where set).
Raw and cleaned data remain completely separate; raw is byte-immutable.

> **Format note:** interim output is CSV this milestone because the MVP has
> no `parquet`/`pyarrow` dependency (Engineering Constitution allowed-deps).
> The naming and versioning convention matches §7.3; adding Parquet in a
> later milestone is a storage-detail change, not an architecture change.

## 9. Tests

65 new tests in `tests/test_cleaning_*.py`:
validation (explicit reasons, schema/price/volume/timestamp/completeness),
cleaning (dedup, OHLC fix, missing strategies, interpolation guard, outlier),
corporate actions (split/dividend/ticker-change, raw immutability),
quality (score, dimensions, ratings, gate), audit (JSON + JSONL),
end-to-end pipeline (raw→interim, raw untouched, audit written, corporate
actions in the real pipeline), and I/O edge cases (unparseable rows, hashing,
holidays).

**Result: 256 tests passing / 92% line coverage** across `src/`, all
cleaning modules ≥ 88%.

## 10. Live Data Verification

Ran the pipeline on the live-ingested Yahoo series from Milestone 02:

| Ticker | Raw rows | Cleaned | Quality | Rating | Gate |
|--------|----------|---------|---------|--------|------|
| MSFT (1d, 2025-02-03..14, 10 rows) | 10 | 10 | 94.2 | excellent | PASS |
| AAPL (1d, 2025-01-02..10, 6 rows) | 6 | 6 | 90.0 | excellent | PASS |

Both audit files + interim CSVs written; raw files byte-unchanged.

## 11. Known Limitations

- No real trading-calendar file by default (weekend detection only);
  an optional `data/external/holidays.json` enables VAL-T05.
- Z-score outlier detection can mask clustered anomalies (documented
  blueprint §5.2 limitation); outliers are flagged, never dropped.
- Missing *candles* between dates are detected (VAL-C02) but never
  fabricated — the cleaning engine only fills nulls inside existing rows.
- Interim output is CSV (no Parquet dependency yet — see §8).
- Corporate-action input is a manual JSON file; fetching actions from a
  provider is out of scope (future).
- Cleaning version `0.1.0`; weights/min-score are configurable.

## 12. Definition-of-Done Trace

- [x] Validation engine (explicit reasons per record)
- [x] Cleaning engine (dedup, OHLC fix, missing strategies, numeric
      normalization, timestamp normalization, symbol normalization)
- [x] Raw tier never modified (byte-verified in tests)
- [x] Corporate-action adjustment (split / bonus / dividend / rename)
- [x] Quality score (0–100) stored with metadata (audit)
- [x] Audit trail (raw ID, cleaning timestamp, version, validation status,
      transformation history)
- [x] Processed output written to the interim tier, raw/processed separated
- [x] Tests (invalid OHLC, missing timestamps, duplicates, corporate action,
      quality score, audit trail) — 256 passing
- [x] Logging (structured logs emitted by the pipeline stages)
- [x] `docs/DATA_CLEANING_ENGINE_IMPLEMENTATION.md` (this file)
- [x] `CURRENT_STATE.md` updated