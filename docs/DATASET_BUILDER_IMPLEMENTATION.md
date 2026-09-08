# DATASET BUILDER IMPLEMENTATION — Milestone 06

> Finance AI MVP — Dataset Builder & Versioning Engine.
> Reference: `docs/DATASET_BUILDER_BLUEPRINT.md`, `LABEL_GENERATION_BLUEPRINT.md`,
> `FEATURE_ENGINEERING_BLUEPRINT.md`, `DATA_ARCHITECTURE.md`.
> Date: 2026-09-04 · Implementation version: `dataset-builder-0.1.0`

---

## 1. What Was Built

The Dataset Builder assembles versioned feature sets (Milestone 04) and
versioned label sets (Milestone 05) into a training dataset:

```
Processed Market Data (M03 interim tier)
        +  Versioned Features (M04, data/processed/features/)
        +  Versioned Labels  (M05, data/processed/labels/)
        ↓
Dataset Builder (src/dataset/)
        ↓  exact (ticker, timestamp) alignment · drop warm-up rows
        ↓  drop invalid-label rows · optional time-range filter
        ↓  DVAL frame validation → chronological TRAIN/VAL/TEST
        ↓  metadata + manifest + version hash
        ↓  immutable persistence (data/processed/datasets/dataset_{v}/)
```

Every row is `X(T) → Y(T+H)`: features computed from data ≤ T, label
describing the outcome at T+H. The builder never shifts features, never
joins on anything but exact (instrument, timestamp), and never writes
partially — a failed validation aborts before persistence.

## 2. Dataset Schema (persisted rows)

| Group        | Columns                                                            |
|--------------|--------------------------------------------------------------------|
| Identity     | `ticker`, `timestamp` (datetime64, naive-UTC per DATA_ARCHITECTURE) |
| Features     | the 52 registered MVP features (registry order, all float64)        |
| Label        | `label` ∈ {UP, DOWN, HOLD}, `future_return` (audit)                |
| Horizon      | `target_timestamp` (the observation at T+H — leakage check DVAL-05) |
| Versioning   | `dataset_version`, `feature_set_version`, `label_set_version`, `source_data_version` (12-char source checksum) |

No OHLCV raw values are persisted in the dataset rows (they are not
training inputs); raw series remain traceable through
`source_data_version`.

## 3. Alignment and Row Accounting

- Features and labels are joined on **exact timestamp** per ticker
  (index intersection — never nearest-neighbour).
- Feature/label source checksums must match per ticker (same cleaned
  source), else `SCHEMA_MISMATCH` — a silent misaligned join is impossible.
- Persisted versions are checked against the requested versions and
  against the configured label `target_type`/`horizon` — mismatch fails
  the build loudly.
- Rows are never silently dropped. Every exclusion is counted in the
  build report and manifest:
  - `dropped_warmup` — rows where ANY feature is NaN (insufficient lookback).
  - `dropped_invalid_label` — rows whose label status is not VALID.
  - `missing_feature_count` — rows excluded because a mandatory feature is
    unavailable (warm-up rows).
  - `missing_label_count` — rows excluded because the label/status, target
    timestamp, or future return is invalid.
  - `dropped_unmatched` — rows present in only one of features/labels.
  - `dropped_out_of_range` — rows outside the requested time range.
  - `invalid_rows` — rows rejected by label status, target, or target-window
    validation.
- The manifest records UP/DOWN/HOLD counts and percentages, plus SHA-256
  checksums for each persisted split artifact.

## 4. Chronological Splitting

- Ratios from `dataset.split_ratios` (train 0.70 / val 0.15 / test 0.15),
  applied to **each instrument independently** (blueprint §3.3): every
  ticker contributes its own contiguous chronological split, which keeps
  temporal isolation between splits for multi-ticker datasets whose
  instruments span the same date range. **Never random** (ADR-0004).
- Split boundaries (inclusive start/end per split) are recorded in
  metadata, the manifest, and the deterministic version hash.
- `DVAL-06` verifies `train_end < val_start < test_start`; `DVAL-07`
  warns on small splits (`train < 100 / val < 20 / test < 20` per
  blueprint §3.4 — warnings, not errors).

## 5. Purge and Embargo

- **MVP static split: purge OFF and embargo OFF** (blueprint §5.3 —
  daily-data static splits are contiguous, so no label window from one
  split reaches into the next; this was verified by test).
- The purge rule (blueprint §5.1/§5.4 — drop rows whose
  `target_timestamp >= next-split start`) and embargo gap both exist in
  `src/dataset/split.py`, config-gated (`dataset_builder.purging`,
  `dataset_builder.embargo`), for the walk-forward/backtest engine
  (Milestone 09), where overlapping label windows require them.

## 6. Versioning and Immutability

- `dataset_version` defaults to `v0.1`; bump on any material change to
  source data, feature set, labels, split policy, or filtering policy.
- The version hash is a deterministic SHA-256 over feature version,
  label version, per-ticker source checksums, the config snapshot,
  sorted feature names, split boundaries, and record counts. Any
  material change produces a different hash.
- Persistence is **immutable**: an identical rebuild under the same
  version is a byte-stable safe no-op; a *different* dataset under an
  existing version raises `DATASET_ALREADY_EXISTS` (never overwrite).

## 7. Storage Layout

```
data/processed/datasets/
└── dataset_v0.1/
    ├── metadata.json       # blueprint §8.1 metadata (all row counts,
    │                       #   boundaries, quality, drops)
    ├── manifest.json       # machine-readable manifest (§18 of the brief)
    ├── feature_names.json  # ordered 52 feature columns
    ├── train.parquet       # TRAIN split
    ├── val.parquet         # VAL split
    ├── test.parquet        # TEST split
    └── hash.txt            # deterministic version hash
```

Parquet per the blueprint §7 (ADR-0026 added the pyarrow dependency in
Milestone 04; storage is written atomically via temp-file rename).

## 8. Dataset Validation (DVAL-01..10)

| Check | Rule | Action |
|-------|------|--------|
| DVAL-01 | No NaN or Infinity in features/target or mandatory columns | ERROR → reject |
| DVAL-02 | No duplicate (ticker, timestamp) rows | ERROR → reject |
| DVAL-03 | Timestamps ascending | ERROR → reject |
| DVAL-04 | Labels aligned with features / valid classes | ERROR → reject |
| DVAL-05 | Target timestamps strictly after observations | ERROR → reject |
| DVAL-06 | Chronological splits, no overlap | ERROR → reject |
| DVAL-07 | Minimum split sizes | WARNING → log |
| DVAL-08 | Per-split class balance (each class ≤ 50%, all classes valid) | WARNING → log |
| DVAL-09 | Feature schema matches the registered 52 exactly | ERROR → reject |
| DVAL-10 | Quality score ≥ gate (default 70) | WARNING → log |

The quality score (0–100, weights 30/20/20/15/15) covers retention,
feature-gap, label-gap, ordering, and schema exactness — computed on the
final aligned frame.

## 9. Leakage Protection (mandatory tests, all green)

- **Test A — Temporal ordering**: no row violates chronological order;
  no duplicate (ticker, timestamp) in the persisted dataset.
- **Test B — Split isolation**: train max < val min < test max — no
  overlap between splits.
- **Test C — Label horizon**: every `target_timestamp` is strictly after
  its observation and equals the 5th subsequent session of the source
  series (exact H=5 check against the cleaned CSV).
- **Test D — Future extension invariance**: appending 30 more days of
  source data and rebuilding (v0.2) leaves every historical feature row
  identical; the original v0.1 artifact is byte-unchanged.
- **Test E — Version integrity**: every row carries the configured
  dataset/feature/label versions and the source checksum; target columns
  are disjoint from the feature schema.

## 10. CLI

```
python -m scripts.run_dataset [--ticker AAPL] [--ticker MSFT]
    [--feature-version v0.1] [--label-version v0.1]
    [--output-version v0.1] [--interval 1d]
    [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

Default behaviour discovers every ticker that has BOTH a persisted
feature set and label set for the configured versions. Prints a JSON
summary (rows/drops/splits/quality/validation) and exits 0 on success
(including an identical immutable no-op rebuild), 1 on a build failure,
2 on a usage error.

## 11. Tests

- `tests/test_dataset_split.py` — chronological split engine: sizes,
  contiguity, determinism, boundaries, multi-ticker isolation, purge
  rule (incl. the boundary `target == next-start` case), embargo gaps.
- `tests/test_dataset_validation.py` — DVAL-01..09 frame checks,
  DVAL-06..08 split checks, non-finite/timestamp rejection, and the
  dataset quality-score math.
- `tests/test_dataset_pipeline.py` — real-engine integration (cleaned
  CSV → M04 features → M05 labels → M06 dataset), all five mandatory
  leakage tests, deterministic rebuild, immutability/conflict refusal,
  range filtering, ticker auto-discovery, version/horizon/target/column
  mismatch failures, and the below-gate warning path.

**Result: 405 tests pass (66 new dataset tests), 93% line coverage**
(every `src/dataset/` module ≥ 86%; `builder.py` 96%), black + ruff
clean.

## 12. Controlled Verification Runs

1. **Real-data guard**: the 6-row real AAPL cleaned sample cannot clear
   the 100+ row feature warm-up → the builder fails loudly with
   `DATA_NOT_FOUND` ("no usable dataset rows…"), never emitting an empty
   artifact. This is correct behaviour, not a defect.
2. **Controlled real-engine run** (400 sessions × AAPL+MSFT, scratch
   dir): 800 input rows → 554 usable (236 warm-up + 10 invalid-label +
   0 unmatched dropped) → splits 386/82/86 → quality **90.78 excellent**,
   0 DVAL errors. Rebuilding identically was a byte-stable no-op with an
   identical hash; persisted rows had zero duplicates, zero feature NaN,
   monotonic timestamps, and every target exactly 5 sessions ahead.

## 13. Known Limitations

- The static split is row-ratio based per instrument; walk-forward
  splits (with purge/embargo) are implemented in `split.py` but only
  wired into the backtest milestone.
- The label class distribution of real short samples is heavily
  imbalanced (DVAL-08 warns; nothing is rebalanced — that belongs to
  training research).
- Datasets are file-based Parquet (no DB) per ADR-0005/ADR-0026; no
  incremental append scheduling (manual deterministic rebuilds only).
- Manifest artifact checksums cover each persisted train/val/test Parquet
  file; `hash.txt` remains the deterministic dataset-definition hash.

## 14. Files

- Created: `src/dataset/` (`__init__`, `errors.py`, `split.py`,
  `validation.py`, `quality.py`, `metadata.py`, `storage.py`,
  `builder.py`), `scripts/run_dataset.py`,
  `tests/test_dataset_{split,validation,pipeline}.py`,
  `docs/DATASET_BUILDER_IMPLEMENTATION.md`.
- Modified: `config/default.yaml` + `src/config/loader.py`
  (`dataset_builder:` section, typed `DatasetBuilderConfig`),
  `src/cleaning/io.py` (shared cleaned-tier reader used by M04–M06).
- No dependencies added (pyarrow already present from M04, ADR-0026).
