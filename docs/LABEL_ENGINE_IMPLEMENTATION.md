# LABEL ENGINE IMPLEMENTATION — Finance AI MVP (Milestone 05)

> Implementation record for the Label Generation Engine.
> Reference: `docs/LABEL_GENERATION_BLUEPRINT.md`, `docs/FEATURE_CATALOG.md`,
> `docs/DATA_ARCHITECTURE.md`, `docs/DATASET_BUILDER_BLUEPRINT.md`.

---

## 1. Target Implemented

**PRIMARY TARGET: Direction Classification (UP / DOWN / HOLD)** —
exactly per blueprint §3.3 / §20. No secondary target for MVP.

## 2. Horizon

**5 trading days** (`dataset.label_window: 5`, blueprint §5). The horizon
is expressed in *rows of the price series* (trading days), so it never
crosses a weekend/holiday by naive wall-clock shift — the future
observation is the 5th subsequent available candle (blueprint §9/§10).

## 3. Exact Label Rule (v0.1)

```python
future_return = (price_{t+5} - price_t) / price_t        # simple return
if future_return >  +0.01:  label = "UP"
elif future_return < -0.01: label = "DOWN"
else:                       label = "HOLD"
```

- **Price source:** `dataset.price_column` (default `adj_close`) — the
  Milestone-03 cleaned tier already carries adjusted prices, which the
  blueprint §12.2 requires at corporate-action boundaries.
- **Timing:** close-to-close (entry close_t, exit close_{t+H}, §6.3 MVP
  simplification).
- **Thresholds:** fixed +1% / −1% (§4.4) — never tuned on test data, never
  auto-adjusted from observed class balance (§14.3).
- **Strict comparisons** (`>`, `<`); the boundary itself is HOLD.

## 4. Label Version

- `label_set_version = v0.1` (config `dataset.label_version`).
- Version hash: SHA-256 over `{label_type, label_window, thresholds,
  cost_aware, price_column}` (blueprint §17.2). Any change to the target
  definition, horizon, threshold or timing produces a new hash and must
  ship as a new label version.
- Storage refuses to overwrite an existing label set with materially
  different content: identical re-generation is a byte-stable no-op,
  different content raises `LabelStorageConflictError`.

## 5. Edge-Case Behavior

| Case | Handling |
|------|----------|
| Missing future candle (end of series) | `INVALID_FUTURE_WINDOW`, label NaN — never fabricated |
| Invalid future price (NaN/0/negative) | `INVALID_FUTURE_WINDOW`, label NaN |
| Invalid current price (0/negative) | `INVALID_PRICE`, label NaN |
| NaN gap in the middle of the series | future landing on the gap → invalid |
| Horizon ≥ dataset length | all rows invalid; warning logged |
| Duplicate / unsorted timestamps | rejected with `ValueError` before generation |

Rows with NaN labels are counted in metadata (`invalid_count`) and are
the Dataset Builder's job to drop (next milestone) — never silently dropped
here.

## 6. Class Distribution

Computed over valid rows only (blueprint §14.1): UP/DOWN/HOLD counts +
percentages, invalid counts by reason. Acceptable ranges (blueprint §7.3):
UP 25-45 %, DOWN 25-45 %, HOLD 20-50 %. Outside → **WARNING only**; the
engine never rebalances or auto-adjusts thresholds.

## 7. Leakage Protections

- Labels use ONLY the price at T and T+H — future data never enters the
  feature inputs; the generator never mutates its input frame.
- Persisted label frame contains only `future_price`, `future_return`,
  `label`, `status`, `target_timestamp` — no OHLCV/feature columns
  (target and feature storage stay disjoint).

### Mandatory leakage tests (all pass)

| Test | What it proves |
|------|----------------|
| **A — Feature independence** | Label generation leaves the input OHLCV frame byte-identical and outputs no source columns. |
| **B — Historical invariance** | Labels on a dataset ending at T are identical to labels on the longer dataset for every row whose future window is within T. |
| **C — Horizon test** | The label at T uses exactly the price at timestamp T+H. |
| **D — Shift integrity** | `future_price == price.shift(-H)` and `future_return == future_price/price − 1` (aligned). |
| **E — No target contamination** | Label columns are disjoint from the 52 feature columns (verified against the M04 registry and persisted files). |

## 8. Persistence

Per-ticker files under `data/processed/labels/` (blueprint §18.2 layout):

- `labels_{version}_{TICKER}.parquet` — timestamp index + 5 columns
- `labels_{version}_{TICKER}.metadata.json` — blueprint §18.1 metadata:
  label_id (`direction_v0.1`), version + hash, name/type, horizon (+unit),
  thresholds, source column/file/checksum, generation rule, timestamp,
  distribution counts, status
- `labels_{version}_{TICKER}.hash.txt` — version hash

## 9. CLI

```bash
python -m scripts.run_labels --ticker AAPL
python -m scripts.run_labels --ticker MSFT --source data/interim/cleaned_20250315_MSFT_daily.csv
python -m scripts.run_labels --ticker AAPL --horizon 5 --label-version v0.1
```

Prerequisites: cleaned interim CSV (Milestone 03), `dataset.*` config.
Output: label Parquet + metadata + hash. Re-running the identical
generation is a byte-stable no-op (verified).

## 10. Test Strategy

- **Unit tests** — return math, threshold classification (incl. just-below
  threshold → HOLD), horizon mapping, alignment, all edge cases.
- **Fixed reference case** — hand-derivable 12-row fixture with expected
  returns/labels per row (regression anchor, milestone §27).
- **Leakage tests** — the five mandatory tests above.
- **Persistence tests** — valid generation, byte-stable idempotent re-run,
  conflict refusal on changed input, horizon/version overrides, version-hash
  sensitivity.
- **Distribution tests** — counts/percentages, imbalance warnings, zero-valid
  case.

## 11. Known Limitations

- Real-data validation used the small M02 sample ingestions (10 rows) —
  only 5 valid labels; class balance is sample-dominated (warnings fired,
  correctly, and were not auto-corrected). Larger ranges are needed for
  research.
- The horizon counts *available candles*; for suspended instruments the
  "trading day" mapping would need the trading-calendar domain (later
  milestone). NaN-gap behavior is tested and explicit.
- No purging/embargo (blueprint §13.3 MVP decision: not needed for daily
  data).
- Labels and features are persisted separately and are NOT yet joined —
  dataset building is the next milestone.

## 12. Exact Next Milestone

**Milestone 06 — Dataset Builder** (`docs/DATASET_BUILDER_BLUEPRINT.md`):
join features (T) with labels (T+H) into versioned training datasets —
chronological train/val/test splits, warm-up-row dropping (rows with any
feature NaN or label NaN), schema/metadata persistence.