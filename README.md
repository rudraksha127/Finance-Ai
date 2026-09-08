# Finance AI — MVP

> A research-grade, reproducible ML system for financial prediction.
> Built with time-series correctness, no future leakage, and walk-forward validation.

---

## Current Status

✅ **MVP COMPLETE — Milestones 01–11 implemented and integration-verified (GO).**

The complete research workflow was verified end-to-end on 2026-09-08
(AAPL daily, versions v0.3): ingest → clean → features → labels → dataset →
train → backtest → inference API → dashboard. See
`docs/MVP_INTEGRATION_QA_REPORT.md` (authoritative QA report) and
`docs/MVP_RELEASE_NOTES.md`.

Implemented (see `docs/CURRENT_STATE.md`):

- Milestone 01: typed configuration, structlog logging, errors, enums,
  validation primitives, domain models (Instrument, Candle), and
  raw/interim/processed storage layout (`src/core/`, `src/config/`, `src/logging/`)
- Milestone 02: historical market-data ingestion (`src/data/`): source-adapter
  contract + **Yahoo Finance adapter**, normalization, validation, immutable
  raw-tier CSV store with duplicate/conflict protection, ingestion metadata
  journal, instrument registry, bounded retries + rate-limit handling, CLI
- Milestone 03: data cleaning & quality engine (`src/cleaning/`): validation
  (VAL-* rules with explicit reasons), cleaning (dedup, OHLC repair, missing
  strategies, outlier flag), corporate-action adjustment (split/bonus/dividend),
  0–100 quality score, audit trail, and interim-tier output (raw never modified)
- Milestone 04: feature engineering engine (`src/features/`): all **52 approved
  MVP features** (registry + vectorized, leak-free computation), FVAL-*
  validation, feature-set versioning, Parquet storage under
  `data/processed/features/` (pyarrow — ADR-0026), CLI
- Milestone 05: label generation engine (`src/labels/`): UP/DOWN/HOLD direction
  labels (5-trading-day horizon, fixed ±1% thresholds on the adjusted close),
  VALID/INVALID_* edge-case statuses, class-distribution checks, label
  versioning + Parquet storage under `data/processed/labels/`, CLI
- Milestone 06: dataset builder & versioning engine (`src/dataset/`): exact
  (ticker, timestamp) alignment of versioned features + labels, warm-up /
  invalid-label drops (counted), DVAL-01..10 validation, chronological
  per-instrument TRAIN/VAL/TEST splits (ADR-0027; purge/embargo implemented
  for walk-forward), 0–100 dataset quality score, immutable versioned
  snapshots under `data/processed/datasets/dataset_{v}/` (metadata +
  manifest + hash), CLI
- Milestone 07: reproducible baseline training (`src/model/`): validated
  dataset loading, logistic regression and random forest, train-only scaling,
  validation metrics (incl. ROC-AUC and PR-AUC), feature importance,
  conflict-protected model and experiment artifacts, CLI
- Milestone 08: evaluation & walk-forward backtesting (`src/backtest/`):
  version-verified predictions → signal generator → long-only close-to-close
  execution simulator with costs → financial metrics vs. benchmarks → report,
  plus an expanding-window walk-forward engine with per-fold retraining and
  label-overlap purge (`scripts/run_backtest.py`)
- Milestone 09: research-only inference API (`src/api/`): FastAPI service
  with `/predict`, `/health`, `/ready`, `/model/info`, `/version`,
  deterministic model resolution, shared decision logic with the backtest,
  append-only prediction audit trail, standardized error model
  (`scripts/run_api.py`; RESEARCH mode only — no live trading)
- Milestone 10: research dashboard (`dashboard/`): React 19 + TypeScript +
  Vite SPA with 8 blueprint pages, typed API client, read-only dashboard
  endpoints in `src/api/reads.py`
- Milestone 11: end-to-end integration, QA & research run — **MVP GO**
  (see `docs/MVP_INTEGRATION_QA_REPORT.md`)
- Test suite: **514 backend + 35 dashboard tests passing** (run the full
  suites with the commands below)

Not yet implemented: live/broker execution (out of scope by design).
PostgreSQL is **Phase 2** (ADR-0005 — the MVP is file-based).

## Historical Data Ingestion

The MVP fetches historical OHLCV candles from **Yahoo Finance** — the
first-priority source from `docs/DATA_INGESTION_BLUEPRINT.md` §1. The adapter
implements the Yahoo chart API directly over `requests` (the Engineering
Constitution's allowed HTTP stack; recorded in ADR-0024).

### Supported

- Intervals: `1d`, `1wk`, `1mo`
- Fields: open, high, low, close, adjusted close, volume + timestamp
- Re-runs are safe: identical rows are skipped (idempotent), materially
  different rows for an existing timestamp are kept (never overwritten)

### Configuration

The Yahoo adapter needs **no API key** — nothing to configure. Ingestion
settings live in `config/default.yaml` under `ingestion:` (source, interval,
timeout, retry backoff, pacing).

### Ingestion command

```bash
# Fetch, validate, persist AAPL daily candles for 2025-01-02..2025-01-10
python -m scripts.run_ingest --ticker AAPL --start 2025-01-02 --end 2025-01-10

# Weekly bars for a dotted ticker from a different quarter
python -m scripts.run_ingest --ticker BRK.B --start 2024-06-01 --end 2024-12-31 --interval 1wk
```

Output is a machine-readable metadata summary. Rows are stored at
`data/raw/{TICKER}_{interval}.csv`; every run is journaled to
`data/raw/metadata/ingestion_log.jsonl`. Exit codes: `0` success,
`1` FAILED/PARTIAL run, `2` usage/configuration error.

### Limitations (honest, not exhaustive)

- Yahoo Finance is an unofficial endpoint; response availability/format can
  change without notice. Only `1d`/`1wk`/`1mo` are supported (no intraday).
- Timestamps are UTC calendar dates for daily/weekly/monthly bars; a
  scheduled intraday source is out of MVP scope.
- The engine is a research/development pipeline: ingest → clean → features →
  labels. Features/labels computed from small sample ranges are warm-up
  dominated; use larger ranges for research.

## Feature Generation

Computes all 52 approved MVP features from a cleaned interim CSV
(Milestone-03 output), validates them, and persists a versioned Parquet
dataset (Milestone 04).

```bash
# Latest cleaned file for the ticker
python -m scripts.run_features --ticker AAPL

# Explicit source and version
python -m scripts.run_features --ticker MSFT --source data/interim/cleaned_20250315_MSFT_daily.csv --feature-version v0.1
```

Output: `data/processed/features/features_{version}_{TICKER}.parquet` +
`.metadata.json` + `.hash.txt`. Re-running the same source/version is a
byte-stable no-op; regenerating with different data for the same version is
refused (bump the feature version).

## Label Generation

Generates UP/DOWN/HOLD direction labels over a 5-trading-day horizon with
fixed ±1% thresholds (Milestone 05; target per
`docs/LABEL_GENERATION_BLUEPRINT.md` §20).

```bash
python -m scripts.run_labels --ticker AAPL
python -m scripts.run_labels --ticker MSFT --horizon 5 --label-version v0.1
```

Output: `data/processed/labels/labels_{version}_{TICKER}.parquet` +
`.metadata.json` + `.hash.txt`. Rows without a future observation are marked
`INVALID_FUTURE_WINDOW` (label NaN) — never fabricated.

## Dataset Generation

Builds a versioned training dataset by aligning persisted feature sets
(Milestone 04) with label sets (Milestone 05) on exact (ticker, timestamp),
dropping warm-up and invalid-label rows (recorded), validating (DVAL-01..10),
and splitting chronologically into TRAIN/VAL/TEST (Milestone 06; blueprint
`docs/DATASET_BUILDER_BLUEPRINT.md`).

```bash
# Every ticker that has both a feature set and a label set
python -m scripts.run_dataset

# Explicit instruments and versions
python -m scripts.run_dataset --ticker AAPL --ticker MSFT --feature-version v0.1 --label-version v0.1 --output-version v0.1

# Restrict the observation range
python -m scripts.run_dataset --start 2024-01-01 --end 2025-12-31
```

Output: `data/processed/datasets/dataset_{version}/` with `metadata.json`,
`manifest.json`, `feature_names.json`, `train.parquet`, `val.parquet`,
`test.parquet` and `hash.txt`. Datasets are immutable: an identical rebuild
is a byte-stable no-op, a different dataset under the same version is
refused (bump `dataset_builder.dataset_version` in `config/default.yaml`).

Prerequisites: persisted feature + label artifacts for the requested
versions (see above) with a data volume that clears the feature warm-up
(≈100+ sessions) — small sample ingestions fail loudly, they do not produce
empty datasets.

## Baseline Model Training

Train an approved baseline against an immutable dataset snapshot. Logistic
regression scales features using TRAIN only; random forest does not require
scaling. Validation metrics are generated from VALIDATION, while TEST is
validated but protected from fitting and model-selection feedback.

```bash
python -m scripts.run_model --model logistic_regression --dataset-version v0.1
python -m scripts.run_model --model random_forest --dataset-version v0.1
```

Artifacts are written to
`data/processed/models/{model_version}/` and
`data/processed/models/experiments/{experiment_id}/`. See
`docs/BASELINE_MODEL_IMPLEMENTATION.md` for the artifact contract,
configuration, metrics, and reproducibility details.

## Backtesting (Evaluation)

Evaluate a trained baseline over a frozen dataset split (static backtest) or
across expanding-window walk-forward folds (per-fold retraining with
label-overlap purge):

```bash
# Static backtest on the dataset's TEST split
python -m scripts.run_backtest --ticker AAPL --dataset-version v0.1 \
  --model logistic_regression --model-version <model-version> --split test

# Expanding-window walk-forward
python -m scripts.run_backtest --ticker AAPL --dataset-version v0.1 \
  --model logistic_regression --walk-forward

# Built-in cost/slippage scenario study (BASE/LOW_COST/HIGH_COST/STRESSED_SLIPPAGE)
python -m scripts.run_backtest --ticker AAPL --model-version <model-version> --scenarios
```

Outputs (trade ledger, financial metrics vs. buy-and-hold, report) are
written under `backtests/{run_id}/`; scenario comparisons land in
`backtests/{study_id}/scenario_summary.json`. See
`docs/EVALUATION_BACKTESTING_IMPLEMENTATION.md` for the output contract and
current limitations.

Finance AI is a pipeline that transforms historical financial data into validated predictions through a clean, auditable, leak-free process.

```
Raw Data → Clean → Features → Labels → Dataset → Model → Backtest → Predictions
```

## MVP Roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| 1. Foundation | Documentation, standards, structure | ✅ Complete |
| 2. Data Layer | Ingestion, validation, cleaning | ✅ Ingestion + cleaning implemented |
| 3. Feature Layer | Deterministic feature engineering | ✅ Implemented (52 features, `src/features/`) |
| 4. Dataset Layer | Label generation, dataset builder, chronological splits | ✅ Implemented (`src/labels/` + `src/dataset/`) |
| 5. Model Layer | Baseline training; walk-forward evaluation remains separate | ✅ Baseline implemented |
| 6. Evaluation | Static + walk-forward backtesting, metrics, reports | ✅ Implemented (M08, `src/backtest/`) |
| 7. API | Prediction serving endpoint | ✅ Implemented (M09, `src/api/`) |
| 8. Dashboard | Results visualization | ✅ Implemented (M10, `dashboard/`) |
| 9. Integration & QA | E2E research run, audits, GO/NO-GO | ✅ Complete (M11 — GO) |

## High-Level Architecture

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│   Data   │──▶│Processing│──▶│ Feature  │──▶│ Dataset  │
└──────────┘   └──────────┘   └──────────┘   └──────────┘
                                                      │
┌──────────┐   ┌──────────┐   ┌──────────┐          │
│    UI    │◀──│   API    │◀──│Evaluation│◀──┌──────┴─────┐
└──────────┘   └──────────┘   └──────────┘   │   Model    │
                                              └────────────┘
```

## Development Principles

1. **No future information leakage** — features never see future data
2. **Chronological splits always** — train < val < test in time
3. **Reproducible experiments** — seeds, versions, config snapshots
4. **Configuration over hardcoding** — YAML-driven everything
5. **Test before ship** — no untested code in `src/`

## Repository Structure

```
finance-ai-mvp/
├── docs/           ← All documentation
├── config/         ← YAML configuration files
├── src/            ← Source code
├── tests/          ← Test suite
├── scripts/        ← Utility scripts
├── data/           ← Data (raw, interim, processed)
├── notebooks/      ← Exploration notebooks
├── experiments/    ← Experiment logs
├── models/         ← Model artifacts (gitignored)
└── reports/        ← Generated reports
```

## Setup

```bash
git clone <repository-url>
cd finance-ai-mvp
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # optional; defaults are safe
```

## Configuration

Configuration is YAML under `config/` (see `src/config/loader.py`):

- `config/default.yaml` — base configuration (always loaded)
- `config/{environment}.yaml` — optional overlay, selected by `ENVIRONMENT`
  (`development` | `testing` | `production`; default `development`)
- Environment variables override specific keys: `ENVIRONMENT`, `LOG_LEVEL`,
  `LOG_FORMAT` (documented in `.env.example`)

No secrets belong in YAML or source code — secrets arrive via environment
variables. The MVP stores data as files (ADR-0005); no `DATABASE_URL` is
needed until the Phase-2 PostgreSQL milestone.

## Running the Foundation

```bash
# Verify configuration loads (optional smoke check)
python -c "from src.config.loader import load_config; print(load_config())"

# 1. Ingest historical data (Milestone 02)
python -m scripts.run_ingest --ticker AAPL --start 2025-01-02 --end 2025-01-10

# 2. Clean + quality score -> data/interim (Milestone 03; run programmatically
#    via src.cleaning.pipeline.CleaningPipeline — no standalone CLI)

# 3. Generate the 52-feature dataset (Milestone 04)
python -m scripts.run_features --ticker AAPL

# 4. Generate direction labels (Milestone 05)
python -m scripts.run_labels --ticker AAPL
```

## Verified MVP Workflow (Milestone 11)

The exact command chain verified end-to-end on 2026-09-08 (AAPL daily,
versions v0.3). Feature/label/dataset/model versions must be passed
explicitly once newer artifacts exist than the configured defaults:

```bash
# 1. Ingest historical data
python -m scripts.run_ingest --ticker AAPL --start 2026-08-24 --end 2026-09-04

# 2. Build cleaned data (quality score + audit; raw tier never modified)
python -c "from src.config.loader import load_config; from src.cleaning.pipeline import CleaningPipeline; from src.logging.logger import configure_from_config; c=load_config(); configure_from_config(c); print(CleaningPipeline(c).run('AAPL','1d').output_file)"

# 3. Generate features (52 approved features)
python -m scripts.run_features --ticker AAPL --feature-version v0.3

# 4. Generate labels (UP/DOWN/HOLD, 5-day horizon)
python -m scripts.run_labels --ticker AAPL --label-version v0.3

# 5. Build the versioned dataset (chronological TRAIN/VAL/TEST)
python -m scripts.run_dataset --ticker AAPL --feature-version v0.3 --label-version v0.3 --output-version v0.3

# 6. Train the baseline model
python -m scripts.run_model --model logistic_regression --dataset-version v0.3 --feature-version v0.3 --label-version v0.3 --model-version logistic_regression_v0.3

# 7. Run the backtest (static on TEST; add --walk-forward for folds)
python -m scripts.run_backtest --ticker AAPL --dataset-version v0.3 --feature-version v0.3 --label-version v0.3 --model-version logistic_regression_v0.3 --split test

# 8. Start the inference API (http://127.0.0.1:8000 — /predict, /health, /ready, /model/info, /version)
python -m scripts.run_api

# 9. Start the dashboard (separate terminal; http://localhost:5173, proxies /api/* to :8000)
cd dashboard && npm run dev
```

Every stage is idempotent and conflict-protected: re-running identical work
is a byte-stable no-op, and material changes require a new version.

## Autonomous Data Pipeline (Post-MVP 01)

Incremental, scheduler-driven data growth reusing the existing engines
(no second implementations). Watermark-based: each run ingests only the
missing/new range, cleans, regenerates features/labels, publishes a new
immutable dataset version when content changed, runs the quality gate,
records the run, and advances the watermark only on full success.

```bash
# Manual trigger (same code path as a scheduled cron run)
python -m scripts.run_pipeline --instrument AAPL

# Explicit range
python -m scripts.run_pipeline --instrument AAPL --from 2026-09-01 --to 2026-09-05

# Plan without side effects
python -m scripts.run_pipeline --instrument AAPL --dry-run

# Scheduled: add to crontab (the CLI is the scheduler's entry point)
# 15 20 * * 1-5  cd /path/to/finance-ai-mvp && .venv/Scripts/python -m scripts.run_pipeline --instrument AAPL
```

Configuration: `pipeline:` section in `config/default.yaml` (lookback,
overlap, retries, quality gate, gap tolerance, instruments). State:
`data/pipeline/watermarks.json` (checkpoints), `data/pipeline/runs/*.json`
(run records), `data/pipeline/locks/` (concurrency locks). See
`docs/AUTONOMOUS_DATA_PIPELINE_IMPLEMENTATION.md` for design, recovery,
and limitations.

## Temporal Model (Post-MVP 06)

One compact single-layer LSTM trained on causal sequences from the SAME
versioned datasets as the baseline models (same features, labels, target,
metrics, registry, backtest). Sequences contain only observations up to and
including their end row; sequences never cross split boundaries. Normalization
is fit on TRAIN only and persisted inside the artifact. Early stopping monitors
validation loss only. Inference uses a torch-free numpy forward pass so the
backtest/API processes never import torch (Windows DLL conflict mitigation).

```bash
# Train the temporal model on a versioned dataset
python -m scripts.run_temporal --dataset-version v0.3 --feature-version v0.3 --label-version v0.3

# Small sequence-length experiment (validation-only selection; final test untouched)
python -m scripts.run_temporal --sequence-length-experiment 5 10 20

# Backtest through the EXISTING backtest engine (no new backtester)
python -m scripts.run_backtest --ticker AAPL --model-version temporal_lstm_v0.1 \
  --dataset-version v0.3 --feature-version v0.3 --label-version v0.3
```

The temporal model is registered as CANDIDATE via the existing registry
(`python -m scripts.run_registry --list`); it is never activated automatically.
Interpretability is limited (documented honestly; no attention visualizations).
Research-only: weak validation metrics on the small MVP dataset are reported
as-is, never tuned against the test set. See
`docs/TEMPORAL_MODEL_IMPLEMENTATION.md`.

## Testing

```bash
pytest tests/ -v                      # full suite
pytest tests/ --cov=src --cov-report=term-missing   # coverage
```

## Code Quality

```bash
black --check src tests scripts
isort --check-only src tests scripts
ruff check src tests scripts
```

## Documentation

| Document | Purpose |
|----------|---------|
| `docs/PRD_MVP.md` | **MVP Product Requirements Document** — single source of truth |
| `docs/SYSTEM_ARCHITECTURE.md` | **System Architecture Blueprint** — technical design |
| `docs/DATA_ARCHITECTURE.md` | **Data Architecture & Database Blueprint** — schema and data lifecycle |
| `docs/DATA_INGESTION_BLUEPRINT.md` | **Data Ingestion Engine Blueprint** — ingestion pipeline design |
| `docs/DATA_CLEANING_VALIDATION.md` | **Data Cleaning & Validation Blueprint** — cleaning, validation, quality scoring |
| `docs/DATA_CLEANING_ENGINE_IMPLEMENTATION.md` | Milestone 03 implementation report |
| `docs/FEATURE_ENGINEERING_BLUEPRINT.md` | **Feature Engineering Blueprint** — feature design and leakage prevention |
| `docs/FEATURE_ENGINE_IMPLEMENTATION.md` | Milestone 04 implementation report |
| `docs/FEATURE_CATALOG.md` | **Feature Catalog** — 52 MVP feature specifications |
| `docs/LABEL_GENERATION_BLUEPRINT.md` | **Label Generation Blueprint** — target definition and leakage prevention |
| `docs/LABEL_ENGINE_IMPLEMENTATION.md` | Milestone 05 implementation report |
| `docs/DATASET_BUILDER_BLUEPRINT.md` | **Dataset Builder Blueprint** — versioned dataset creation and walk-forward splits |
| `docs/PROJECT_BIBLE.md` | Canonical project document |
| `docs/ENGINEERING_CONSTITUTION.md` | Engineering standards |
| `docs/ARCHITECTURE_PRINCIPLES.md` | Layer definitions |
| `docs/DATASET_BUILDER_IMPLEMENTATION.md` | Milestone 06 implementation report |
| `docs/BASELINE_MODEL_BLUEPRINT.md` | **Baseline Model Blueprint** — LR + RF baselines and input contract |
| `docs/BASELINE_MODEL_IMPLEMENTATION.md` | Milestone 07 implementation report |
| `docs/TRAINING_PIPELINE_BLUEPRINT.md` | **Training Pipeline Blueprint** — experiment management and reproducibility |
| `docs/EVALUATION_BACKTESTING_BLUEPRINT.md` | **Evaluation & Walk-Forward Backtesting Blueprint** |
| `docs/EVALUATION_BACKTESTING_IMPLEMENTATION.md` | Milestone 08 implementation report |
| `docs/RISK_DECISION_ENGINE_BLUEPRINT.md` | **Risk & Decision Engine Blueprint** |
| `docs/INFERENCE_API_BLUEPRINT.md` | **Prediction & Inference API Blueprint** (Milestone 09) |
| `docs/UI_UX_BLUEPRINT.md` | **Dashboard UI/UX Blueprint** (Milestone 10) |
| `docs/INFERENCE_API_IMPLEMENTATION.md` | Milestone 09 implementation report |
| `docs/DASHBOARD_IMPLEMENTATION.md` | Milestone 10 implementation report |
| `docs/MVP_INTEGRATION_QA_REPORT.md` | **Milestone 11 — authoritative integration & QA report (GO)** |
| `docs/MVP_RELEASE_NOTES.md` | MVP release notes (capabilities, versions, reproducibility) |
| `docs/AUTONOMOUS_DATA_PIPELINE_IMPLEMENTATION.md` | Post-MVP 01 — autonomous data pipeline |
| `docs/DRIFT_DETECTION_IMPLEMENTATION.md` | Post-MVP 02 — drift detection engine |
| `docs/AUTONOMOUS_RETRAINING_IMPLEMENTATION.md` | Post-MVP 03 — autonomous retraining |
| `docs/MODEL_REGISTRY_IMPLEMENTATION.md` | Post-MVP 04 — model registry & safe promotion |
| `docs/OBSERVABILITY_OPERATIONS_IMPLEMENTATION.md` | Post-MVP 05 — observability & operations |
| `docs/TEMPORAL_MODEL_IMPLEMENTATION.md` | Post-MVP 06 — temporal LSTM model |
| `docs/ENSEMBLE_CALIBRATION_IMPLEMENTATION.md` | Post-MVP 07 — ensemble & probability calibration |
| `docs/MULTIMODAL_FINANCE_DATA_IMPLEMENTATION.md` | Post-MVP 08 — multimodal finance data (point-in-time) |
| `docs/DECISIONS.md` | Architecture decision records |
| `docs/CURRENT_STATE.md` | Current repository status |
