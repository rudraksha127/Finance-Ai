# FEATURE ENGINE IMPLEMENTATION — Finance AI MVP (Milestone 04)

> Implementation record for the Feature Engineering Engine.
> Reference: `docs/FEATURE_ENGINEERING_BLUEPRINT.md`, `docs/FEATURE_CATALOG.md`,
> `docs/DATA_ARCHITECTURE.md` (§7 tiers), `docs/DATA_CLEANING_VALIDATION.md`.

---

## 1. Implemented Feature Groups

All **52 approved MVP features** across the 8 approved categories
(FEATURE_CATALOG.md is the reference specification table):

| Category | Count | Feature IDs |
|----------|-------|-------------|
| Price / Return | 8 | RET-01 .. RET-08 |
| Trend | 8 | TRD-01 .. TRD-08 |
| Momentum | 6 | MOM-01 .. MOM-06 |
| Volatility | 8 | VOL-01 .. VOL-08 |
| Volume | 6 | VLM-01 .. VLM-06 |
| Volume-Price | 4 | VP-01 .. VP-04 |
| Bollinger / Range | 6 | BB-01 .. BB-06 |
| Candle Structure | 6 | CS-01 .. CS-06 |
| **Total** | **52** | |

No features were added to inflate the count; the catalog's 52 are the
approved MVP set. Future families (relative strength, market context,
regime) remain out of scope (blueprint §3.1).

## 2. Feature IDs / Names / Version

- **Feature-set version:** `v0.1` (`src/features/registry.py::FEATURE_SET_VERSION`).
- **Per-feature versions:** `v1` for every MVP feature (definition frozen at
  the catalog).
- **Version hash:** SHA-256 over `{feature_set_version, feature specs
  (id/name/formula/lookback/version), config}` (`metadata.compute_feature_version_hash`).
  Any definition change produces a different hash; existing datasets are
  never silently replaced (storage conflict protection).

## 3. Implementation Notes (per family)

| Family | Implementation |
|--------|----------------|
| **Returns** | `close.pct_change(k)` for k ∈ {1,3,5,10,20}; log return `ln(close_t/close_{t-1})`; intraday `(c-o)/o`; overnight `(o-c_{t-1})/c_{t-1}`. |
| **Trend** | SMA via `rolling(k).mean()`; EMA via `ewm(span=k, adjust=False, min_periods=k)`; price-to-SMA distance `close/sma - 1`. |
| **Momentum** | RSI via Wilder smoothing (`ewm(alpha=1/period, adjust=False)`); **zero-average-loss → RSI = 100** (Wilder convention), flat series → NaN. ROC = `pct_change(k)*100`; absolute momentum = `close - close.shift(10)`. |
| **Volatility** | Rolling std of daily returns (`ddof=1`, pandas default); ATR = Wilder EMA of True Range (`alpha=1/14`); realized vol = `std(returns,20)*sqrt(252)`; volatility ratio = `vol5/vol20`. |
| **Volume** | Ratios vs `sma(volume, k)`; z-score vs 20-day mean/std; OBV = cumulative `sign(diff(close))*volume`; **OBV slope = exact least-squares slope** over a trailing 10-day window (vectorized closed form). |
| **Volume-Price** | VWAP deviation vs `sum(tp*vol,k)/sum(vol,k)` with `tp=(h+l+c)/3`; **VP-03** implemented as `sign(returns_1d) * (volume_t / volume_{t-1})` (the catalog's "sign(returns) × volume_ratio" with lookback 1); A/D money flow with zero-range → 0. |
| **Bollinger** | Bands = `sma(close,20) ± 2*std(close,20)`; position/bandwidth ratios; **BB-05 squeeze** = `bandwidth < rolling 20th percentile over 100 days` (NaN preserved during warm-up); 20-day high-low range. |
| **Candle** | Body/wick/close-position ratios with `max(high-low, 1e-12)` guard (doji-safe); bullish flag; gap `(o-c_{t-1})/c_{t-1}`. |

## 4. Versioning / Metadata

Every persisted feature dataset writes three files under
`data/processed/features/` (blueprint §18.2):

- `features_{version}_{TICKER}.parquet` — 52 float64 columns + timestamp index
- `features_{version}_{TICKER}.metadata.json` — feature_set_version,
  version_hash, feature_count, ticker, source_file, source_checksum,
  row_count, feature_columns, generated_at, status
- `features_{version}_{TICKER}.hash.txt` — the version hash

Parquet engine: **pyarrow** (added to `requirements.txt` with documented
reason — see ADR-0026; the blueprint mandates Parquet storage and no
allowed dependency can write Parquet without an engine).

## 5. Leakage Protection

- Every feature uses only `rolling` / `ewm` / `shift` with backward-looking
  semantics; no centered windows, no future fills, no future normalization.
- Warm-up rows (insufficient lookback) are **NaN**, never fabricated.
- Maximum lookback = **100** (BB-05 squeeze); first fully-valid row is at
  index 118 (bandwidth needs 20 rows before its 100-row quantile window).

### Mandatory leakage tests (all pass)

| Test | What it proves |
|------|----------------|
| **A — Future mutation** | Mutating only rows after T changes no feature value at or before T. |
| **B — Truncation** | Features computed on a series ending at T are identical to features through T computed on the longer series. |
| **C — Timestamp** | Every feature column at T is unchanged when data after T is removed (verified per column at multiple cutoffs). |

Plus shift-consistency checks and rolling-window sensitivity tests
(removing a row *before* T changes the value; removing rows after T never does).

## 6. Feature Validation (FVAL-*)

| Check | Behavior |
|-------|----------|
| FVAL-01 NaN ratio > 30% | WARNING (logged, reported) |
| FVAL-02 infinite values > 0 | **ERROR — generation aborted** |
| FVAL-03 outside documented range (bounded features) | **ERROR — generation aborted** |
| FVAL-04 constant feature | WARNING |
| FVAL-05 |correlation| > 0.99 pair | WARNING (log, don't delete — blueprint §15) |
| FVAL-06 |z| > 5 outliers > 1% | WARNING |
| FVAL-08 index not ascending / duplicated | **ERROR — generation aborted** |

Errors fail the run **before any persistence** — a feature is never
silently replaced with zeros (milestone §33). Warnings are surfaced in the
summary and metadata for researcher review.

## 7. CLI

```bash
python -m scripts.run_features --ticker AAPL
python -m scripts.run_features --ticker MSFT --source data/interim/cleaned_20250315_MSFT_daily.csv
python -m scripts.run_features --ticker AAPL --feature-version v0.1
```

Prerequisites: cleaned interim CSV (Milestone 03), `features.*` config.
Output: `data/processed/features/features_{version}_{TICKER}.parquet` + metadata + hash.
Re-running the same source+version is a byte-stable no-op; a materially
different regeneration is refused (conflict error) — bump the version.

## 8. Test Strategy

- **Registry tests** — 52 features, unique IDs/names, complete metadata,
  category counts match the catalog.
- **Unit tests** — per-family mathematical verification (manual formulas),
  RSI Wilder reference value, warm-up NaN counts, doji guard.
- **Leakage tests** — the three mandatory tests + shift/rolling checks.
- **Validation tests** — every FVAL-* path (error + warning branches).
- **Integration tests** — cleaned CSV → engine → Parquet/metadata/hash,
  determinism (byte-stable re-run), conflict protection, error paths.

## 9. Known Limitations

- **Sample-size sensitivity:** the M02 sample ingestions are tiny (10 rows),
  so most lookback features are NaN and NaN-ratio WARNINGs dominate the
  report. Behavior is correct; larger ranges are needed for research use.
- **Correlation/outlier checks** compute on non-NaN values only; with heavy
  warm-up NaN the reported pairs/counts reflect available data.
- Parquet is written via pyarrow 18.x; engine format pinned to
  `parquet` (config allows `csv` fallback but it is not the MVP format).
- No scaling is applied (blueprint §11: tree models need none; scaling for
  linear models happens at training time on train splits only — M06+).

## 10. Exact Next Milestone

**Milestone 05 — Label Generation Engine** (`docs/LABEL_GENERATION_BLUEPRINT.md`):
future-return direction labels (UP/DOWN/HOLD, 5-day horizon, ±1% thresholds)
over the cleaned interim tier, with the five mandatory leakage tests and
versioned label persistence.