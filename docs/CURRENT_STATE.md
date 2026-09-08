# CURRENT_STATE.md — Repository Status

> Updated after every significant change. Read this before starting any work.

---

## Last Updated

**2026-09-08 (Post-MVP Milestone 05 — Observability & Operations Center) — COMPLETE** — Implemented `src/operations/engine.py` + `scripts/run_ops.py`: unified health model (HEALTHY/DEGRADED/CRITICAL/UNKNOWN/NOT_CONFIGURED), component healths (data pipeline, drift monitor, retraining, model registry, storage, data freshness), business-day freshness (weekends are not staleness), operational events with fingerprint dedup + occurrence counting, OPEN→ACKNOWLEDGED→RESOLVED lifecycle, critical overrides (no ACTIVE model, storage failure, ≥3 repeated pipeline failures, critical drift), system aggregation, best-effort persistence (observability can never become a single point of failure — OSError is logged, never propagated), and CLI (--snapshot/--acknowledge/--resolve). Reuses existing records only (pipeline runs, drift summaries, retraining runs, registry) — no second monitoring system. 12 new tests incl. the failure-injection test (§44). See `docs/OBSERVABILITY_OPERATIONS_IMPLEMENTATION.md`. Next: Post-MVP Milestone 06 (Temporal Intelligence Model).

**2026-09-08 (Post-MVP Milestone 08 — Multimodal Finance Intelligence) — COMPLETE** — Implemented `src/multimodal/` (contracts.py + asoof.py + sources.py + features.py): strict point-in-time external data layer with four timestamps per record (event/publication/ingestion/AVAILABILITY — availability is the join key), temporal-reliability classes (RELIABLE / DAY_ONLY→next-day eligibility / INSUFFICIENT→never eligible, no silent timezone interpretation), deterministic as-of joins (latest availability, explicit tie-break), fundamental carry-forward only after publication, controlled event windows {1,3,7d}, `feature_set_v0.2` (10 fundamentals + debt_ratio/margin/has_fundamentals + 4 event features; v0.1 untouched; missing modality = NaN, never fabricated). No licensed fundamentals/news source is approved → full abstraction + deterministic fixtures per the source policy; experiments A–D deliberately NOT run on fixtures (would fabricate results) — the integration chain is test-verified for when real history arrives. Dedup = identifier + content fingerprint; restatement policy = first publication is truth (as-of makes later restatements invisible before their publication). All six mandatory leakage tests + the controlled 12:00/15:00/17:00/next-day-filing fixture PASS. Sentiment and embeddings deferred by design. 20 new tests (643 total passing). See `docs/MULTIMODAL_FINANCE_DATA_IMPLEMENTATION.md`.

**2026-09-08 (Post-MVP Milestone 07 — Model Ensemble & Probability Calibration) — COMPLETE** — Implemented `src/ensemble/engine.py` + `scripts/run_ensemble.py`: measured diversity analysis first (v0.3 models ARE complementary: agreement 0.412, P(UP) correlation −0.175), leakage-safe out-of-sample validation predictions of both constituents (chronological VAL split — no random K-fold), explicit class-order alignment (never inferred from column position), simple-average + validation-log-loss-grid weighted ensemble (w=0.2 selected on validation only), Platt-style multinomial calibration fitted on validation and frozen before any test evaluation (calibration_v0.1 with Brier/ECE diagnostics), torch-free `EnsemblePredictor` artifact in the standard model layout. Honest result: ensemble f1_macro 0.186 regresses vs constituents (0.240/0.295) despite marginal accuracy gain → registered `ensemble_v0.1` as CANDIDATE, NOT promoted (existing backtests: 0 trades for all three at the 0.55 threshold — no financial improvement either). Final-test protection verified (validation rows disjoint from test rows). 18 new tests (623 total passing). See `docs/ENSEMBLE_CALIBRATION_IMPLEMENTATION.md`. Next: Post-MVP Milestone 08 (Multimodal Finance Intelligence).

**2026-09-08 (Post-MVP Milestone 06 — Temporal Intelligence Model) — COMPLETE** — Implemented `src/temporal/` (sequence.py + model.py + inference.py) + `scripts/run_temporal.py`: one compact single-layer LSTM over causal sequences built from the SAME versioned datasets/features/labels as the baseline (sequence ends at T, contains only rows ≤ T; per-split construction = split isolation). Train-only StandardScaler persisted in the artifact; validation-loss early stopping with best-epoch checkpointing (final test never monitored); torch-free numpy inference wrapper persisted in `model.joblib` (Windows DLL conflict mitigation — backtest/API processes never import torch; numpy↔torch equivalence verified to 3.4e-08). Mandatory leakage tests A–D pass (future mutation, dataset extension, boundary, split isolation). Sequence-length experiment L∈{5,10,20} on dataset v0.3 (validation-only selection → L=10, f1_macro 0.2953 vs 0.2716/0.2649). Registered `temporal_lstm_v0.1` as CANDIDATE via the existing registry (never auto-activated); run through the EXISTING backtest engine on the v0.3 test split (0 trades at 0.55 threshold — honest result). New `temporal:` config section; torch added as documented CPU dependency. 19 new tests (605 total passing). See `docs/TEMPORAL_MODEL_IMPLEMENTATION.md`. Next: Post-MVP Milestone 07 (Model Ensemble & Probability Calibration).

**2026-09-08 (Post-MVP Milestone 04 — Model Registry & Safe Promotion) — COMPLETE** — Implemented `src/registry/engine.py` + `scripts/run_registry.py`: model registry records with full version identity (artifact checksum, dataset/feature/label/config versions, experiment id, metrics snapshot), explicit lifecycle state machine (TRAINED→CANDIDATE→VALIDATING→APPROVED→ACTIVE→ARCHIVED + REJECTED; invalid transitions rejected), single-ACTIVE invariant (DB-style uniqueness check), atomic promotion with integrity + compatibility checks (failure preserves the previous ACTIVE model), integrity-verified rollback, append-only audit trail (`registry/audit.jsonl`), filesystem-lock concurrency protection, `get_active_model()`/`get_model(version)` resolvers, and CLI (--list/--show/--promote/--rollback with --dry-run). 17 new tests incl. critical safety + promote/rollback regression. See `docs/MODEL_REGISTRY_IMPLEMENTATION.md`. Next: Post-MVP Milestone 05 (Observability & Operations Center).

**2026-09-08 (Post-MVP Milestone 03 — Autonomous Retraining & Candidate Evaluation) — COMPLETE** — Implemented `src/retraining/engine.py` + `scripts/run_retraining.py`: trigger evaluation (manual/schedule/dataset-growth/drift/performance), eligibility checks with `RETRAINING_SKIPPED` reasons (dataset exists, version match, quality gate, train rows, cooldown, fingerprint idempotency), candidate training via the existing `BaselineTrainer` (approved config only, new artifact version), candidate validation, fair current-vs-candidate comparison (same dataset/split/costs via the shared backtest engine), 7 measurable promotion gates (G1 data quality → G7 operational health), CANDIDATE_APPROVED/REJECTED decisions with full audit records under `data/retraining/`, dry-run mode. **Critical safety test (§41) passes**: training failure, evaluation failure, or rejection can never change the current model. New `retraining:` config section. 9 new tests. See `docs/AUTONOMOUS_RETRAINING_IMPLEMENTATION.md`. Next: Post-MVP Milestone 04 (Model Registry & Safe Promotion).

**2026-09-08 (Post-MVP Milestone 02 — Data & Model Drift Detection Engine) — COMPLETE** — Implemented `src/drift/` (metrics + engine): PSI-based feature/data drift with KS + Benjamini-Hochberg FDR correction, missingness drift, prediction-distribution drift, performance degradation (WARNING/CRITICAL with minimum-sample gates), reference/current windows, severity classification GREEN/YELLOW/RED, drift-event records with alert deduplication (fingerprint + occurrence_count) and manual resolution lifecycle, monitoring-run records + aggregated health summaries under `data/monitoring/`, and `scripts/run_drift.py` (manual + scheduled, `--resolve`). Monitoring only — no automatic retraining. 18 new tests. See `docs/DRIFT_DETECTION_IMPLEMENTATION.md`. Next: Post-MVP Milestone 03 (Autonomous Retraining & Candidate Model Evaluation).

**2026-09-08 (Post-MVP Milestone 01 — Autonomous Data Ingestion & Incremental Dataset Growth) — COMPLETE** — Implemented the controlled autonomous data pipeline (`src/pipeline/`): `PipelineEngine` orchestrates the existing ingestion/cleaning/features/labels/dataset engines into one incremental flow (watermark → missing-range/Gap detection → ingest → clean → features → labels → dataset → quality gate → record run → advance watermark), filesystem locking prevents concurrent runs, watermark/run/stage tracking with audit records, bounded retries, dry-run mode, and the CLI `scripts/run_pipeline.py` (same code path as scheduled cron). Watermark advances only after full success; failures preserve the watermark and record the run. New `pipeline:` config section (config_version, lookback_days, overlap_days, retry_count, min_quality_score, max_gap_ratio). Mandatory incremental-vs-full consistency + historical immutability tests. 11 new tests. See `docs/AUTONOMOUS_DATA_PIPELINE_IMPLEMENTATION.md`. Next: Post-MVP Milestone 02 (Data & Model Drift Detection Engine).

**2026-09-08 (Milestone 11 — End-to-End Integration, QA & Research Run) — MVP: GO** — Full E2E research run executed on AAPL daily (ingest → clean → features v0.3 → labels v0.3 → dataset v0.3 → LR/RF v0.3 → static + walk-forward backtests → inference API → dashboard). 514 backend + 35 dashboard tests passing; dashboard production build verified. Audits: integration contracts (9 boundaries), version consistency, timezone, data integrity (0 dupes / 0 OHLC violations / 0 orphans), leakage (NO), security (no secrets). Failure injection + acceptance tests AT-01..AT-12 all pass. Two P1 defects found and fixed: (1) `/version` reported stale configured versions instead of the resolved model's versions (now fixed + regression test); (2) `config/development.yaml` pinned v0.2 after the v0.3 run, causing 409s on v0.3 models (overlay bumped to v0.3). Performance smoke: inference median 2.4 ms / p95 3.3 ms (n=50). Full report: `docs/MVP_INTEGRATION_QA_REPORT.md`; release notes: `docs/MVP_RELEASE_NOTES.md`. Next: Post-MVP Milestone 01 (Autonomous Data Pipeline).

**2026-09-05** — Architecture phase complete (19 docs, 28 ADRs). **Milestones 01–08 implemented** (Data Foundation, Historical Ingestion, Cleaning & Quality, Feature Engineering, Label Generation, Dataset Builder, Baseline Model Training, Evaluation & Walk-Forward Backtesting) — 439 tests passing; M08 adds the backtest engine per EVALUATION_BACKTESTING_BLUEPRINT.md + RISK_DECISION_ENGINE_BLUEPRINT.md (ADR-0028).

**2026-09-05 (verification pass)** — Audited the M01/M02/M04/M05/M06 implementation against the milestone specifications; all code requirements verified present and green (439/439, counts re-measured per milestone: 122/69/65/57/26/66/3/31). Fixed stale documentation only: README status now reflects Milestone 08 + backtesting, and CURRENT_STATE's not-implemented list, ADR table (added ADR-0028), and repository-state summary were corrected.

**2026-09-05 (M07 audit)** — Audited Milestone 07 (Baseline ML Model) against its specification. Verified complete: dataset loader + version/schema/checksum validation, TRAIN-only preprocessing (StandardScaler), LR + RF baselines, VALIDATION-only feedback, ML metrics (macro + per-class), feature importance, conflict-protected model/experiment artifacts, leakage audit, reproducibility. Closed one spec gap: experiment metadata now records `git_commit` (best-effort; `unknown` while the repo has no commits) per spec section 22. M07 tests (3/3) and full suite re-run green.

**2026-09-07 (Milestone 10 — Research Dashboard UI)** — Implemented the React 19 + TypeScript + Vite 7 SPA per UI_UX_BLUEPRINT.md (ADR-0030): `dashboard/` with all 8 blueprint pages (Overview, Market Explorer, Predictions, Backtests, Experiments, Models, Datasets, System Health), design-token CSS Modules, tree-shaken ECharts wrappers with accessible summaries, persistent RESEARCH MODE badge, and a single typed API client with request-id propagation and `ApiError` conversion. Added the blueprint §29.3 read-only dashboard endpoints in `src/api/reads.py` (datasets, models, experiments, backtests, candles, predictions, system/status — file-backed, no computation, same error envelope; 13 tests). Frontend: 35 tests (client mock tests, component tests incl. non-color status, page tests incl. §9.3 model/decision separation and §14 risk-as-text), strict `tsc --noEmit` clean, production build verified against the live API through the Vite proxy. Live verification: backend + dev server + production preview all served API-backed data (health, datasets v0.2, models, experiments, backtests, audit trail, candles with stale flag). Known limitation: agent-browser CDP startup hung on this machine, so interactive browser walkthrough was replaced by dev-server module checks + production preview + component/page tests; no visual-regression system per blueprint §40. Full backend suite **513 passing** (two real-config tests now pin ENVIRONMENT=testing so the development overlay cannot shift asserted defaults).

**2026-09-05 (M08 audit)** — Audited Milestone 08 (Financial Backtest Engine) against its specification. Verified complete: data adapter (version + checksum-matched prices), frozen-model prediction adapter, deterministic signals (config thresholds, no test tuning), close-to-close long-only execution simulator (fixed quantity, max holding, force-close), gross/net P&L with per-side costs + slippage bps, full financial metric set, buy-and-hold + zero-trade benchmarks, ML metrics kept separate, trade ledger, equity/drawdown curves, experiment record + config snapshot, expanding-window walk-forward with per-fold retraining + purge. No code changes required. Re-verified by execution: full suite 439/439; fresh static backtest (5 trades) and walk-forward run (9 folds, 18 trades) on the v0.1 fixture dataset produced complete artifact sets under `backtests/`.

**2026-09-05 (real-data E2E + scenario runner)** — Ran the full pipeline on **real Yahoo data** (AAPL daily, 2023-01-02 → 2026-08-31): 892 rows ingested (COMPLETED), cleaned (918 sessions, quality 99, gate PASS), features + labels at version **v0.2** (52 features; 913 valid labels: UP 47.5% / DOWN 31.3% / HOLD 21.1%), dataset **v0.2** (795 rows; train 556 / val 119 / test 120; quality 95.98), trained logistic regression + random forest at **v0.2** (honest weak validation metrics, accuracy ≈ 0.32–0.36). Static backtests on the real TEST split produced zero trades for both models at the 0.55 threshold (buy-and-hold +18.2%); walk-forward (LR) ran 25 folds / 17 trades (−7.5% net). Version gating verified live (mismatched feature version aborts). Also added a built-in **cost/slippage scenario runner** (`src/backtest/scenarios.py`, `--scenarios`): BASE / LOW_COST / HIGH_COST / STRESSED_SLIPPAGE re-run the exact static pipeline with identical trade sets and ordered cost results; 6 new tests. Full suite now **445 passing**.

**2026-09-07 (Milestone 09 — Prediction & Inference API)** — Implemented the research-only inference service per INFERENCE_API_BLUEPRINT.md (ADR-0029): `src/api/` (errors, schemas, resolver, decision, audit, orchestrator, app) + `scripts/run_api.py`. FastAPI at root paths (blueprint §26.2 defers `/api/v1`); deterministic model resolution (explicit > `api.default_model` > newest artifact); pre-inference compatibility checks (status/feature/label versions, schema) with blueprint §16 error codes; shared decision logic via `src/backtest/signals.py` + RISK §20/§21 risk score and reason codes; append-only JSONL audit trail with explicit `audit_written: false` on persistence failure; `/health` 200/503, `/ready` structured checks; `mode: live` refuses to boot; no order/execution code exists (structural test). New deps: fastapi, uvicorn, httpx (ADR-0029). Config `api:` section added; development overlay pins v0.2 versions to match live artifacts. 43 new tests; full suite **500 passing**. Live verification: real `random_forest_v0.2` served a controlled /predict (DOWN 0.628, signal SELL, risk 0.292, audited); 400/404/409/422 paths verified live; latency median 7.4 ms / p95 8.7 ms (50 requests).

**2026-09-07 (M07+M08 deep re-verification audit)** — Independently re-audited Milestones 07 and 08 against their milestone specifications. Code was blueprint-complete except for three gaps, all fixed: (1) **PR-AUC added** to `src/model/metrics.py` (macro one-vs-rest average precision, same applicability rule as ROC-AUC) per milestone §17; (2) **ROC-AUC silently degraded to `null`** on every real run because sklearn requires an *ordered* `labels` argument and `CLASSES = (UP, DOWN, HOLD)` is not lexicographic — the sort order is now applied before metric calls and a regression test pins both ranking metrics to numeric values when all classes are present (real v0.2 run now reports ROC-AUC 0.531, PR-AUC 0.371); (3) **`backtest_version` + `initial_capital`** added to the `backtest:` config (validated), every static and walk-forward experiment record, and configuration snapshot, per milestone M08 §26/§30/§31. M07 test coverage expanded from 3 to 14 tests per spec §28/§29: missing/unexpected feature columns, invalid target, non-finite features, row-level version mismatch, tampered-split checksum, TRAIN-only scaler statistics, VAL/TEST mutation cannot influence fitted artifacts (mandatory leakage audit), probability shape/normalization, full version-identity artifacts, and feature-matrix exclusion of target/metadata columns. Verified by execution: full suite **457 passing**, black/ruff/isort clean, controlled training run on real dataset v0.2 (556/119/120 rows, all 8 experiment artifacts), fresh static backtest on real data (zero trades, honest None/0.0 metrics), version gating verified live.

## What Currently Exists

### Repository
- Fresh git repository initialized on `main` branch
- No prior commits (initial commit pending)
- **Architecture documentation: COMPLETE** (19 docs, 28 ADRs) + **implementation reports**: `docs/DATA_CLEANING_ENGINE_IMPLEMENTATION.md`, `docs/FEATURE_ENGINE_IMPLEMENTATION.md`, `docs/LABEL_ENGINE_IMPLEMENTATION.md`, `docs/DATASET_BUILDER_IMPLEMENTATION.md`, `docs/BASELINE_MODEL_IMPLEMENTATION.md`, `docs/EVALUATION_BACKTESTING_IMPLEMENTATION.md`
- **Implementation: Milestones 01–08 COMPLETE** — foundation (`src/core/`,`src/config/`,`src/logging/`), ingestion (`src/data/` + `scripts/` CLI), cleaning & quality (`src/cleaning/`), feature engine (`src/features/`), label engine (`src/labels/`), dataset builder (`src/dataset/`), baseline model (`src/model/`), backtest engine (`src/backtest/` + `scripts/run_backtest.py`)

## What Was Created

### Architecture Documentation (19 files)

| File | Purpose | Status |
|------|---------|--------|
| `docs/PRD_MVP.md` | MVP Product Requirements Document | ✅ Complete |
| `docs/PROJECT_BIBLE.md` | Canonical project document | ✅ Complete |
| `docs/ENGINEERING_CONSTITUTION.md` | Engineering standards | ✅ Complete |
| `docs/ARCHITECTURE_PRINCIPLES.md` | Layer definitions | ✅ Complete |
| `docs/SYSTEM_ARCHITECTURE.md` | System Architecture Blueprint | ✅ Complete |
| `docs/DATA_ARCHITECTURE.md` | Data Architecture & Database Blueprint | ✅ Complete |
| `docs/DATA_INGESTION_BLUEPRINT.md` | Data Ingestion Engine Blueprint | ✅ Complete |
| `docs/DATA_CLEANING_VALIDATION.md` | Data Cleaning & Validation Blueprint | ✅ Complete |
| `docs/FEATURE_ENGINEERING_BLUEPRINT.md` | Feature Engineering Engine Blueprint | ✅ Complete |
| `docs/FEATURE_CATALOG.md` | Feature Catalog (52 MVP features) | ✅ Complete |
| `docs/LABEL_GENERATION_BLUEPRINT.md` | Label Generation & Target Definition Blueprint | ✅ Complete |
| `docs/DATASET_BUILDER_BLUEPRINT.md` | Dataset Builder & Versioning Blueprint | ✅ Complete |
| `docs/BASELINE_MODEL_BLUEPRINT.md` | Baseline ML Model Blueprint | ✅ Complete |
| `docs/TRAINING_PIPELINE_BLUEPRINT.md` | Training Pipeline & Experiment Management Blueprint | ✅ Complete |
| `docs/EVALUATION_BACKTESTING_BLUEPRINT.md` | Evaluation & Walk-Forward Backtesting Blueprint | ✅ Complete |
| `docs/RISK_DECISION_ENGINE_BLUEPRINT.md` | Risk Management & Decision Engine Blueprint | ✅ Complete |
| `docs/INFERENCE_API_BLUEPRINT.md` | Prediction & Inference API Blueprint | ✅ Complete |
| `docs/UI_UX_BLUEPRINT.md` | Dashboard UI/UX Blueprint | ✅ Complete |
| `docs/DECISIONS.md` | Architecture decision records (27 ADRs) | ✅ Complete |

| `docs/CURRENT_STATE.md` | This file | ✅ Complete |

### Known Issues

| Issue | File | Description |
|-------|------|-------------|
| ~~YAML config inconsistency~~ | `config/default.yaml` | **RESOLVED** — `dataset.label_type` is now `classification`, matching all blueprints. |

### Project Files

| File | Purpose | Status |
|------|---------|--------|
| `README.md` | Project overview + local setup | ✅ Complete |
| `requirements.txt` | Python dependencies | ✅ Complete |
| `.gitignore` | Git exclusions | ✅ Complete |
| `.env.example` | Environment variable template (`ENVIRONMENT`, `LOG_LEVEL`, `LOG_FORMAT`) | ✅ Complete |
| `pyproject.toml` | Tooling config: pytest, coverage, black, isort, ruff | ✅ Complete |
| `config/default.yaml` | Default configuration | ✅ Complete |
| `config/development.yaml` | Development overlay (empty by default) | ✅ Complete |
| `config/testing.yaml` | Testing overlay (empty by default) | ✅ Complete |
| `config/production.yaml` | Production overlay placeholder (future) | ✅ Complete |
| `src/__init__.py` | Source package marker | ✅ Complete |
| `src/core/` | Foundation: errors, enums, validation, models, storage | ✅ Complete |
| `src/config/` | Typed, environment-aware config loader | ✅ Complete |
| `src/logging/` | structlog logging foundation | ✅ Complete |
| `src/data/` | **Milestone 02**: sources, normalize, store, metadata, instruments, engine | ✅ Complete |
| `src/cleaning/` | **Milestone 03**: validation, cleaning, actions, quality, audit, io, pipeline | ✅ Complete |
| `src/features/` | **Milestone 04**: registry (52 features), compute, validation, metadata, storage, engine | ✅ Complete |
| `src/labels/` | **Milestone 05**: generator, metadata, storage, engine | ✅ Complete |
| `src/dataset/` | **Milestone 06**: errors, split, validation, quality, metadata, storage, builder | ✅ Complete |
| `src/data/sources/` | Source-adapter contract + Yahoo Finance adapter (requests-based) | ✅ Complete |
| `scripts/` | Developer CLIs (`run_ingest`, `run_features`, `run_labels`, `run_dataset`) | ✅ Complete |
| `tests/__init__.py` | Test package marker | ✅ Complete |
| `tests/test_foundation.py` | Foundation structure tests (17 tests) | ✅ Complete |
| `tests/test_config.py` | Config loader tests | ✅ Complete |
| `tests/test_logging.py` | Logging foundation tests | ✅ Complete |
| `tests/test_errors.py` | Error hierarchy tests | ✅ Complete |
| `tests/test_validation.py` | Validation primitive tests | ✅ Complete |
| `tests/test_models.py` | Domain model tests | ✅ Complete |
| `tests/test_storage.py` | Storage layout tests | ✅ Complete |
| `tests/data_helpers.py` | Shared deterministic ingestion test helpers | ✅ Complete |
| `tests/test_yahoo_adapter.py` | Yahoo response parsing + HTTP error mapping | ✅ Complete |
| `tests/test_ingest_normalize.py` | Normalization + row-level rejection | ✅ Complete |
| `tests/test_ingest_store.py` | Raw-tier store + metadata journal | ✅ Complete |
| `tests/test_ingest_engine.py` | Engine: workflows, retries, idempotency, conflicts | ✅ Complete |
| `tests/test_cleaning_validation.py` | Cleaning validation engine (explicit reasons) | ✅ Complete |
| `tests/test_cleaning_engine.py` | Cleaning + corporate-action adjustment | ✅ Complete |
| `tests/test_cleaning_quality_audit.py` | Quality score + audit trail | ✅ Complete |
| `tests/test_cleaning_pipeline.py` | End-to-end pipeline (raw→interim) | ✅ Complete |
| `tests/test_cleaning_io.py` | I/O: raw reader, hashing, interim writer, holidays | ✅ Complete |
| `tests/test_features_registry.py` | M04: registry metadata completeness | ✅ Complete |
| `tests/test_features_compute.py` | M04: per-family feature math | ✅ Complete |
| `tests/test_features_leakage.py` | M04: mandatory leakage tests (mutation/truncation/timestamp) | ✅ Complete |
| `tests/test_features_validation.py` | M04: FVAL-* checks | ✅ Complete |
| `tests/test_features_pipeline.py` | M04: end-to-end Parquet generation + conflict protection | ✅ Complete |
| `tests/test_labels_generator.py` | M05: label math, thresholds, horizon, edge cases | ✅ Complete |
| `tests/test_labels_leakage.py` | M05: five mandatory leakage tests (A-E) | ✅ Complete |
| `tests/test_labels_pipeline.py` | M05: fixed reference fixture, persistence, idempotency | ✅ Complete |
| `tests/test_dataset_split.py` | M06: chronological split engine, purge/embargo, multi-ticker | ✅ Complete |
| `tests/test_dataset_validation.py` | M06: DVAL-01..10 checks + quality-score math | ✅ Complete |
| `tests/test_dataset_pipeline.py` | M06: real-engine integration, 5 leakage tests, immutability, failures | ✅ Complete |
| `tests/fixtures/config/` | Config test fixtures | ✅ Complete |
| `src/model/` | **Milestone 07**: errors, loader, metrics, trainer + `scripts/run_model.py` | ✅ Complete |
| `tests/test_model_pipeline.py` | M07: dataset contract, artifacts, reproducibility, leakage isolation | ✅ Complete |
| `src/backtest/` | **Milestone 08**: data/prediction adapters, signals, execution, metrics, benchmarks, report, engine, walk-forward + `scripts/run_backtest.py` | ✅ Complete |
| `tests/backtest_helpers.py` | Shared M08 fixture: versioned dataset + matching price source | ✅ Complete |
| `tests/test_backtest_signals.py` | M08: signal rules + threshold sensitivity | ✅ Complete |
| `tests/test_backtest_execution.py` | M08: trades, costs, max holding, equity, fail-loud conditions | ✅ Complete |
| `tests/test_backtest_metrics.py` | M08: financial-metric math | ✅ Complete |
| `tests/test_backtest_engine.py` | M08: end-to-end static backtest, outputs, version mismatches | ✅ Complete |
| `tests/test_backtest_walkforward.py` | M08: fold generation, purge, end-to-end walk-forward | ✅ Complete |
| `src/backtest/scenarios.py` + `tests/test_backtest_scenarios.py` | Built-in cost/slippage scenario study (BASE/LOW_COST/HIGH_COST/STRESSED_SLIPPAGE, `--scenarios`) | ✅ Complete |

## What Was Implemented (Milestone 01 — Data Foundation)

Implemented per the approved architecture (no new architecture was designed):

| Area | Implementation | Architecture source |
|------|----------------|---------------------|
| **Configuration foundation** | Typed `AppConfig` dataclasses; `config/default.yaml` + optional `config/{environment}.yaml` overlay; env-var overrides (`ENVIRONMENT`, `LOG_LEVEL`, `LOG_FORMAT`); strict validation raising `ConfigError` | ENGINEERING_CONSTITUTION §5, PRD NFR-CF-01..05, SYSTEM_ARCHITECTURE §7 |
| **Environment configuration** | `.env.example` documents env vars; `.env` gitignored; production-ready overlay files without deployment | PRD NFR-CF, Security Baseline |
| **Database foundation** | **Not implemented by design** — MVP is file-based (ADR-0005, PRD §10). PostgreSQL schema in DATA_ARCHITECTURE.md remains Phase-2 reference. No SQLAlchemy/Alembic/psycopg dependencies added | ADR-0005, ADR-0010 |
| **Logging foundation** | `src/logging/logger.py`: structlog, JSON (default) or console renderer, ISO-8601 UTC timestamps, levels DEBUG..CRITICAL, module context; nothing sensitive logged | ADR-0006, ENGINEERING_CONSTITUTION §4, NFR-LO |
| **Error handling foundation** | `src/core/errors.py`: `FinanceAIError` base + `ConfigError`/`ValidationError`/`StorageError`; no silent swallowing; `DatabaseError` reserved for Phase 2 | ENGINEERING_CONSTITUTION §3 |
| **Validation primitives** | `src/core/validation.py`: ticker format (DATA_ARCHITECTURE instruments CHECK), naive-UTC timestamp policy, positive prices, volume >= 0, approved intervals, chronological + uniqueness sequence checks | DATA_ARCHITECTURE §3/§4/§6 |
| **Domain enums/constants** | `src/core/enums.py`: MarketInterval, LabelValue, CorporateActionType, TradingSessionType, AppEnvironment, StorageTier (all fixed by architecture) | DATA_ARCHITECTURE, LABEL blueprint |
| **Domain models** | `src/core/models.py`: frozen validated `Instrument` and `Candle` (ticker-keyed for the file-based MVP); `candle_observation_key` mirrors the market_candles UNIQUE constraint | DATA_ARCHITECTURE §3.1/§3.2 |
| **Storage separation** | `src/core/storage.py`: raw/interim/processed tier mapping + idempotent directory creation; no data files created | DATA_ARCHITECTURE §7 |
| **Time-series integrity** | Constraint-level primitives: duplicate observation rejection, chronological order, UTC consistency — enforceable before storage | DATA_ARCHITECTURE §4/§6 (VAL-003/004) |
| **Testing foundation** | 105 new tests + 17 foundation tests = **122 passing, 97% line coverage**; `pyproject.toml` pytest/coverage/black/isort/ruff config | ENGINEERING_CONSTITUTION §6 |

**Definition-of-done checklist:** configuration foundation ✅ · database foundation (file-based, per architecture) ✅ · migrations ✅ N/A (no DB in MVP — documented) · schema constraints ✅ enforced at domain/validation layer · domain models ✅ · logging ✅ · validation primitives ✅ · tests ✅ · tests pass ✅ (122/122) · README accurate ✅ · no secrets ✅ · CURRENT_STATE updated ✅

## What Was Implemented (Milestone 02 — Historical Data Ingestion)

Implemented per the approved architecture (no new architecture was designed):

| Area | Implementation | Architecture source |
|------|----------------|---------------------|
| **Source adapter contract** | `src/data/sources/base.py`: `FetchParams` / `FetchedData` / `HistoricalDataSource` protocol — provider isolation | DATA_INGESTION_BLUEPRINT §1/§5 |
| **Yahoo Finance adapter** | `src/data/sources/yahoo.py`: chart-API fetch over approved `requests` (ADR-0024 for the ADR-0011 `yfinance` deviation); epoch→UTC-date conversion; typed error taxonomy; HTTP 429 Retry-After + 5xx/4xx mapping | DATA_INGESTION_BLUEPRINT §1.2/§4, ADR-0011, ENGINEERING_CONSTITUTION deps |
| **Normalization** | `src/data/normalize.py`: provider-neutral records → validated domain `Candle`s; deterministic ascending sort; row-level rejection never aborts the fetch | DATA_INGESTION_BLUEPRINT §6 |
| **Raw-tier store** | `src/data/store.py`: `{TICKER}_{interval}.csv` per `(ticker, interval)`; UNIQUE key `(ticker, timestamp, interval)`; concat-dedup merge with relative-tolerance (1e-6) row equality — provider adj_close float noise (≈1e-7) is a safe duplicate, real corrections (≫1e-6) are conflicts and never overwritten; SHA-256 checksum; atomic rewrite | DATA_ARCHITECTURE §3.2/§7.3, DATA_INGESTION_BLUEPRINT §3.4/§5 |
| **Ingestion metadata** | `src/data/metadata.py`: append-only JSONL journal (`metadata/ingestion_log.jsonl`) with ingestion id, source, requested/actual range, counts, status, checksum — full traceability | DATA_INGESTION_BLUEPRINT §8 |
| **Instrument registry** | `src/data/instruments.py`: file-backed ticker registry (identity guarantee, duplicate registration impossible) | DATA_ARCHITECTURE §3.1 |
| **Ingestion engine** | `src/data/engine.py`: register→fetch→normalize→validate→persist→journal; bounded exponential-backoff retries (transient only); rate-limit pacing; per-ticker sequential; statuses CREATED/RUNNING/COMPLETED/PARTIAL/FAILED | DATA_INGESTION_BLUEPRINT §2/§7 |
| **CLI** | `scripts/run_ingest.py` (`python -m scripts.run_ingest --ticker AAPL --start ... --end ...`); machine-readable summary; exit codes 0/1/2 | DATA_INGESTION_BLUEPRINT §9.3 |
| **Configuration** | `ingestion:` section in `config/default.yaml` (source, interval, timeout, retry backoff, pacing); typed `IngestionConfig` in loader | ENGINEERING_CONSTITUTION §5 |
| **Testing** | 69 new tests (adapter parsing/HTTP, normalization, store/journal incl. float-noise tolerance, engine workflows/retries/idempotency/conflicts) — all offline, deterministic fixtures; **191 passing total, 94% coverage** | ENGINEERING_CONSTITUTION §6 |

**Definition-of-done checklist:** one approved historical source works ✅ (Yahoo Finance, live-verified) · source adapter exists ✅ · historical fetch works ✅ · normalization works ✅ · validation works ✅ (domain layer) · persistence works ✅ · duplicate protection works ✅ · ingestion metadata recorded ✅ · retry behavior works ✅ · failures explicit ✅ (typed error taxonomy) · CLI triggers ingestion ✅ · tests exist ✅ · tests pass ✅ (191/191) · README accurate ✅ · CURRENT_STATE updated ✅ · no secrets committed ✅

## What Was Implemented (Milestone 03 — Data Cleaning & Quality Engine)

Implemented per the approved architecture (no new architecture was designed; companion doc `docs/DATA_CLEANING_ENGINE_IMPLEMENTATION.md`):

| Area | Implementation | Architecture source |
|------|----------------|---------------------|
| **Validation engine** | `src/cleaning/validation.py`: VAL-S01..VAL-C03 rule engine (schema, price, volume, timestamp, completeness) with explicit per-record reasons (rule_id/severity/category/message/raw_line); rejects unfixable rows, flags/fixes the rest | DATA_CLEANING_VALIDATION §2 |
| **Cleaning engine** | `src/cleaning/cleaning.py`: deterministic dedup (keep_last/keep_first), OHLC repair, missing strategies (ffill/interpolate with ±20% both-neighbor guard/zero-fill/mark/drop), outlier flag (keep) | DATA_CLEANING_VALIDATION §4/§5 |
| **Corporate actions** | `src/cleaning/actions.py`: backward adjustment — split/bonus (`×1/ratio`), dividend (`×1−D/close_pre_ex`), ticker change (rename); defensive validation; optional `data/external/corporate_actions/{TICKER}.json` | DATA_CLEANING_VALIDATION §3, DATA_ARCHITECTURE §3.3 |
| **Quality score** | `src/cleaning/quality.py`: 0–100 weighted (30/30/20/10/10); completeness, validity, consistency, freshness, uniqueness; ratings + gate stored in audit | DATA_CLEANING_VALIDATION §6 |
| **Audit trail** | `src/cleaning/audit.py`: transformation log, per-run JSON + append-only JSONL under `data/interim/audit/`; every record links raw_line, raw hash, pipeline version, validation status, transforms | DATA_CLEANING_VALIDATION §7 |
| **Pipeline + I/O** | `src/cleaning/{pipeline,io}.py`: 8-stage state machine, tolerant raw reader, SHA-256, interim writer `cleaned_{date}_{TICKER}_{interval}.csv`; **raw tier never modified** | DATA_CLEANING_VALIDATION §1.3, DATA_ARCHITECTURE §7 |
| **Configuration** | `cleaning:` section in `config/default.yaml` + typed `CleaningConfig` (pipeline_version, min_rows, validation/cleaning/quality/audit knobs) | DATA_CLEANING_VALIDATION Appendix A |
| **Testing** | 65 new offline tests (validation, cleaning, actions, quality, audit, pipeline, I/O); **256 passing total, 92% coverage**; black + ruff clean | ENGINEERING_CONSTITUTION §6 |

**Definition-of-done:** validation engine ✅ · cleaning engine ✅ · raw immutable ✅ · corporate-action adjustment ✅ · quality score stored with metadata ✅ · audit trail ✅ · processed output to interim tier ✅ · tests ✅ (256/256) · doc + CURRENT_STATE updated ✅

## What Was Implemented (Milestone 04 — Feature Engineering Engine)

Implemented per the approved architecture (no new architecture was designed; companion doc `docs/FEATURE_ENGINE_IMPLEMENTATION.md`):

| Area | Implementation | Architecture source |
|------|----------------|---------------------|
| **Feature registry** | `src/features/registry.py`: all **52 approved MVP features** (RET-01..CS-06) with feature_id, name, category, formula, inputs, lookback, output type, normalization, leakage, expected range — single source of truth | FEATURE_CATALOG.md, FEATURE_ENGINEERING_BLUEPRINT §6/§17 |
| **Feature computation** | `src/features/compute.py`: pandas-vectorized family functions (price/return, trend, momentum incl. Wilder RSI, volatility incl. ATR/true range, volume incl. OBV slope, volume-price incl. VWAP, Bollinger, candle structure); strictly backward-looking (rolling/ewm/shift), zero-range guards, warm-up NaN | FEATURE_ENGINEERING_BLUEPRINT §5-§7, FEATURE_CATALOG formulas |
| **Feature validation** | `src/features/validation.py`: FVAL-01..08 (NaN ratio, inf, bounded ranges, constants, duplicate pairs, outliers, timestamp alignment) — errors abort generation, warnings logged | FEATURE_ENGINEERING_BLUEPRINT §14 |
| **Metadata + versioning** | `src/features/metadata.py`: `v0.1` feature-set version, SHA-256 definition hash, per-run metadata | FEATURE_ENGINEERING_BLUEPRINT §16/§17 |
| **Storage** | `src/features/storage.py`: Parquet via **pyarrow** (ADR-0026) at `data/processed/features/features_{v}_{TICKER}.parquet` + metadata.json + hash.txt; atomic write; conflict-protected (identical re-run byte-stable, different content refused) | FEATURE_ENGINEERING_BLUEPRINT §18 |
| **Engine + CLI** | `src/features/engine.py` (cleaned CSV → compute → validate → persist; shares `load_cleaned_csv`/`find_latest_cleaned` with the label engine) + `scripts/run_features.py` | FEATURE_ENGINEERING_BLUEPRINT §19/§30 |
| **Leakage prevention** | Mandatory tests: future-mutation, truncation, per-column timestamp checks, shift consistency — all green | FEATURE_ENGINEERING_BLUEPRINT §13, milestone §21 |
| **Testing** | 57 new offline tests; **339 passing total (M04+M05), 92% coverage**; black + ruff clean | ENGINEERING_CONSTITUTION §6 |

**Definition-of-done:** approved 52 MVP features implemented ✅ · registry ✅ · metadata ✅ · versioning ✅ · leakage tests ✅ (mutation/truncation/timestamp) · feature validation ✅ (FVAL-*) · persistence ✅ (Parquet) · CLI works ✅ · unit + integration tests ✅ (339/339 total) · docs + CURRENT_STATE updated ✅

## What Was Implemented (Milestone 05 — Label Generation Engine)

Implemented per the approved architecture (no new architecture was designed; companion doc `docs/LABEL_ENGINE_IMPLEMENTATION.md`):

| Area | Implementation | Architecture source |
|------|----------------|---------------------|
| **Target** | Direction classification **UP/DOWN/HOLD** — simple future return `(close_{t+5} - close_t) / close_t` on the adjusted close; fixed ±1% thresholds; close-to-close timing | LABEL_GENERATION_BLUEPRINT §3/§6/§20 |
| **Horizon** | **5 trading days** (config `dataset.label_window`); expressed in rows of the price series so weekends/holidays are never crossed by wall-clock shift | LABEL_GENERATION_BLUEPRINT §5/§9 |
| **Generator** | `src/labels/generator.py`: `generate_labels()` — future price/return, strict-threshold classification, VALID / INVALID_FUTURE_WINDOW / INVALID_PRICE statuses; never fabricates missing futures; never mutates inputs | LABEL_GENERATION_BLUEPRINT §11/§12 |
| **Distribution** | UP/DOWN/HOLD counts + percentages over valid rows; acceptable-range warnings (never auto-tuned/rebalanced) | LABEL_GENERATION_BLUEPRINT §7.3/§14 |
| **Metadata + versioning** | `src/labels/metadata.py`: `label_set_version v0.1`; SHA-256 over {type, window, thresholds, cost_aware, price_column} — any target change forces a new version | LABEL_GENERATION_BLUEPRINT §17/§18 |
| **Storage** | `src/labels/storage.py`: Parquet at `data/processed/labels/labels_{v}_{TICKER}.parquet` + metadata.json + hash.txt; columns limited to target data (`future_price/future_return/label/status/target_timestamp`) — never features | LABEL_GENERATION_BLUEPRINT §18-§19 |
| **Engine + CLI** | `src/labels/engine.py` (load → generate → validate balance → persist; conflict-protected idempotency) + `scripts/run_labels.py` | LABEL_GENERATION_BLUEPRINT §11/§21 |
| **Leakage prevention** | All five mandatory tests green: A feature-independence, B historical-invariance, C horizon, D shift-integrity, E no-target-contamination | LABEL_GENERATION_BLUEPRINT §10/§13 |
| **Testing** | 26 new offline tests incl. hand-derivable fixed-reference fixture + byte-stable idempotency re-run; **339 passing total, 92% coverage**; black + ruff clean | ENGINEERING_CONSTITUTION §6 |

**Definition-of-done:** approved target implemented ✅ · 5-day horizon ✅ · classification logic verified ✅ (strict thresholds) · label_set_version v0.1 ✅ · metadata ✅ · persistence ✅ · idempotency ✅ (byte-stable) · edge cases ✅ · 5 leakage tests ✅ · integration + fixed-reference ✅ · tests pass ✅ (339/339) · CLI works ✅ · docs + CURRENT_STATE updated ✅

## What Was Implemented (Milestone 06 — Dataset Builder & Versioning Engine)

Implemented per the approved architecture (companion doc `docs/DATASET_BUILDER_IMPLEMENTATION.md`):

| Area | Implementation | Architecture source |
|------|----------------|---------------------|
| **Assembly** | `src/dataset/builder.py`: per-ticker load of persisted M04 features + M05 labels with version/checksum/type/horizon checks, exact (ticker, timestamp) alignment, warm-up + invalid-label + range drops (each counted), version columns on every row, run identifiers, and class percentages | DATASET_BUILDER_BLUEPRINT §1.2/§5/§6 |
| **Schema** | Rows carry identity (`ticker`, `timestamp`), all 52 features, `label`/`future_return`/`target_timestamp`, and version columns — no OHLCV, no target leakage into features | DATASET_BUILDER_BLUEPRINT §2 |
| **Split engine** | `src/dataset/split.py`: chronological TRAIN/VAL/TEST (ratios 70/15/15), applied **per instrument** then concatenated (ADR-0027) — chronological isolation across multi-ticker datasets; purge + embargo implemented and config-gated (off for the static MVP split, blueprint §5.3) | DATASET_BUILDER_BLUEPRINT §3/§5, ADR-0004 |
| **Validation** | DVAL-01..10 in `src/dataset/validation.py`: NaN/duplicates/ordering/label alignment/leakage/split overlap/feature schema — ERRORs abort the build, WARNINGs log (DVAL-07/08/10) | DATASET_BUILDER_BLUEPRINT §9 |
| **Quality** | 0–100 score (retention 30 / feature-gap 20 / label-gap 20 / ordering 15 / schema 15) with rating + gate (default 70, DVAL-10 warning) | DATASET_BUILDER_BLUEPRINT §8/§9 |
| **Versioning** | `dataset_version` (default v0.1); deterministic SHA-256 over feature/label versions, source checksums, config, feature names, split boundaries, record counts — any material change forces a new version | DATASET_BUILDER_BLUEPRINT §6 |
| **Storage** | `src/dataset/storage.py`: `data/processed/datasets/dataset_{v}/` with metadata.json + manifest.json + feature_names.json + train/val/test.parquet + hash.txt; atomic writes, split SHA-256 checksums; immutable (identical rebuild = byte-stable no-op, different content under same version refused) | DATASET_BUILDER_BLUEPRINT §6.4/§7 |
| **CLI** | `scripts/run_dataset.py`: `--ticker --feature-version --label-version --output-version --start --end`; auto-discovers tickers with both artifacts; JSON summary; exit 0/1/2 | DATASET_BUILDER_BLUEPRINT §1 |
| **Leakage prevention** | All five mandatory tests green: A temporal ordering, B split isolation, C label horizon (target = 5th subsequent session), D future-extension invariance, E version integrity | DATASET_BUILDER_BLUEPRINT §16 |
| **Testing** | 66 new offline tests; **405 passing total, 93% coverage** (every `src/dataset/` module ≥ 86%, builder 96%); black + ruff clean | ENGINEERING_CONSTITUTION §6 |

**Definition-of-done:** feature/label alignment works ✅ · dataset schema validated ✅ · chronological splitting works ✅ · purge/embargo rules implemented (config-gated for walk-forward) ✅ · dataset versioning ✅ · manifest ✅ · dataset quality validation ✅ · leakage tests ✅ (A–E) · deterministic build ✅ (byte-stable) · immutable snapshots ✅ · CLI works ✅ · tests pass ✅ (405/405) · docs + CURRENT_STATE updated ✅

## What Is Intentionally NOT Implemented

- ✅ Milestones 01–10 implemented: foundation, historical ingestion, cleaning
  & quality, feature engineering (52 features), label generation, dataset
  builder, baseline model training, evaluation & walk-forward backtesting,
  prediction & inference API, research dashboard UI
- ❌ Live/broker execution, news/sentiment/options/order-book engines,
  autonomous retraining, and the Phase-2 PostgreSQL database (ADR-0005 —
  the MVP is file-based)

## Architecture Documentation Summary

### Completed Blueprints

| Blueprint | Sections | Features/Items |
|-----------|----------|----------------|
| PRD_MVP.md | 12 | Product requirements, user stories, acceptance criteria |
| SYSTEM_ARCHITECTURE.md | 10 | 12 modules, API boundaries, data flow |
| DATA_ARCHITECTURE.md | 10 | 8 tables, 15 validation rules, storage strategy |
| DATA_INGESTION_BLUEPRINT.md | 9 | 4 data sources, 6-stage pipeline, error handling |
| DATA_CLEANING_VALIDATION.md | 8 | 7-stage pipeline, 23 validation rules, quality scoring |
| FEATURE_ENGINEERING_BLUEPRINT.md | 28 | 52 features, 8 categories, leakage prevention |
| FEATURE_CATALOG.md | 1 | 52 feature specifications with formulas |
| LABEL_GENERATION_BLUEPRINT.md | 25 | Direction classification, 5-day horizon, edge cases, config inconsistency flagged |
| DATASET_BUILDER_BLUEPRINT.md | 10 + 2 appendices | Pipeline, schema, splits, walk-forward, purging, versioning, storage, metadata, validation, incremental updates |
| BASELINE_MODEL_BLUEPRINT.md | 11 + 2 appendices | LR + RF baselines, input contract, training pipeline, hyperparameters, imbalance, tracking, versioning, checkpoints, reproducibility, failure handling, future models |
| TRAINING_PIPELINE_BLUEPRINT.md | 29 sections | 15-stage pipeline, experiment identity, YAML config, reproducibility, preprocessing, hyperparameter mgmt, 6 experiment types, tracking, artifact structure, model mgmt, status lifecycle, failure handling, compatibility checks, seed policy, compute profile, metric policy, evaluation separation, experiment comparability, model selection gate, research report, future MLOps, security, testing strategy, research questions, consistency check |
| EVALUATION_BACKTESTING_BLUEPRINT.md | 37 sections | 5 evaluation layers, data quality gate, prediction/probability/regression metrics, signal evaluation, walk-forward validation, temporal leakage controls, execution timing, transaction cost model, slippage model, position model, trading rules, 15+ financial metrics, equity curve, benchmarks, ablation testing, robustness testing, cost/slippage/threshold sensitivity, model comparison, statistical significance, overfitting safeguards, final test protocol, 9 backtest outputs, trade ledger, reproducibility, backtest engine architecture, failure conditions, 14-section report structure, future extensions, consistency check |
| RISK_DECISION_ENGINE_BLUEPRINT.md | 32 sections + Final Report (A-J) | Prediction/decision/execution separation, input/output contracts, signal generation, cost-aware decision, 8 risk filters, regime filter, confidence handling, position sizing, risk budget, stop-loss/take-profit eval, holding period, signal expiry, position states, conflicting signals, model quality gate, data quality gate, risk score, decision explanation (22 reason codes), decision log, backtest integration, research safety, threshold research, sensitivity analysis, no-trade policy, future extensions, consistency check |
| INFERENCE_API_BLUEPRINT.md | 34 sections + Final Report (A-K) | Service responsibilities, API architecture (FastAPI), 4 endpoints (/predict, /health, /model/info, /version), request contract (client-supplied features + market context), response contract (model_output vs decision_output), version resolution (explicit > default), model compatibility, input validation (12 checks), feature sourcing (Approach A), model loading, performance targets (<100 ms), batch deferred, error model (10 codes), health checks (liveness/readiness), observability, audit trail (JSONL), idempotency, security baseline, configuration, backtest compatibility (shared decision logic), research/live mode separation, structured reason codes, contract versioning (5 identifiers), testing strategy, fail-closed degradation, OpenAPI docs, future extensions, consistency check |
| UI_UX_BLUEPRINT.md | 41 sections + Final Report (A-J) | Product UX principles, 8-item navigation, app shell (research-mode indicator), 8 pages (Overview, Market Explorer, Prediction, Backtest, Experiments, Models, Datasets, System Health), probability/risk/signal visualization, experiment comparison with compatibility gate, model status facets (pipeline/registry/gate), design system + semantic color tokens, accessibility, responsive, loading/empty/error/stale states, API→UI + Backtest→UI contracts, dashboard read-API gaps (7 required endpoints), frontend stack (Vite/React/TS + ECharts), research-mode safety, page inventory, 5 user flows, design handoff, consistency check |

### Architecture Decision Records (28 ADRs)

| ADR | Title |
|-----|-------|
| ADR-0001 | Project Initialization — Foundation Only |
| ADR-0002 | Python as Primary Language |
| ADR-0003 | YAML-Based Configuration |
| ADR-0004 | Chronological Data Splits Only |
| ADR-0005 | File-Based Data Storage (MVP) |
| ADR-0006 | structlog for Logging |
| ADR-0007 | No Cloud/External Dependencies (MVP) |
| ADR-0008 | MVP Product Requirements Document |
| ADR-0009 | System Architecture Blueprint |
| ADR-0010 | Data Architecture & Database Blueprint |
| ADR-0011 | Data Ingestion Engine Blueprint |
| ADR-0012 | Data Cleaning & Validation Engine Blueprint |
| ADR-0013 | Feature Engineering Engine Blueprint |
| ADR-0014 | Label Generation & Target Definition Blueprint |
| ADR-0015 | Dataset Builder & Versioning Blueprint |
| ADR-0016 | Baseline ML Model Selection |
| ADR-0017 | Training Pipeline & Experiment Management |
| ADR-0018 | Evaluation & Walk-Forward Backtesting Framework |
| ADR-0019 | Risk Management & Decision Engine |
| ADR-0020 | Prediction / Decision / Execution Separation |
| ADR-0021 | Prediction & Inference API Blueprint |
| ADR-0022 | Dashboard UI/UX & Frontend Stack |
| ADR-0023 | Milestone 01 — Data Foundation (File-Based, ADR-0005 Confirmed) |
| ADR-0024 | Milestone 02 — Yahoo Finance Adapter over Requests (ADR-0011 Deviation) |
| ADR-0025 | Milestone 03 — Cleaned Data Goes to the Interim Tier (DATA_ARCHITECTURE Clarification) |
| ADR-0026 | Milestone 04 — pyarrow Added for Parquet Feature/Label Storage (Dependency Addition) |
| ADR-0027 | Milestone 06 — Chronological Splits Computed Per Instrument (Multi-Ticker Clarification) |
| ADR-0028 | Milestone 08 — Evaluation & Walk-Forward Backtesting Engine |

## Current Repository State

```
Branch:     main
Commits:    0 (initial commit pending)
Status:     MVP GO (Milestones 01-11 complete; full E2E research run verified 2026-09-08 on AAPL daily v0.3 chain; 2 P1 fixes landed; all audits + AT-01..AT-12 pass)
Docs:       19 architecture docs + 8 implementation reports + MVP_INTEGRATION_QA_REPORT.md + MVP_RELEASE_NOTES.md + 5 post-MVP implementation docs
ADRs:       30 architecture decisions
Tests:      586 backend passing (557 + 17 P04 registry + 12 P05 operations) + 35 dashboard tests (Vitest)
Coverage:   93% line coverage on src/ (re-verified 2026-09-05: 93.4% line, 91% branch-combined)
Phase:      MVP GO + Post-MVP Milestones 01-05 (Data Pipeline, Drift Detection, Retraining, Model Registry, Observability) COMPLETE. Next: Post-MVP Milestone 06 (Temporal Intelligence Model)
```

## Architecture Phase: COMPLETE

All required architecture documentation is complete:
- ✅ Product Requirements (PRD_MVP.md)
- ✅ System Architecture (SYSTEM_ARCHITECTURE.md)
- ✅ Data Architecture (DATA_ARCHITECTURE.md)
- ✅ Data Ingestion Blueprint (DATA_INGESTION_BLUEPRINT.md)
- ✅ Data Cleaning & Validation Blueprint (DATA_CLEANING_VALIDATION.md)
- ✅ Feature Engineering Blueprint (FEATURE_ENGINEERING_BLUEPRINT.md + FEATURE_CATALOG.md)
- ✅ Label Generation Blueprint (LABEL_GENERATION_BLUEPRINT.md)
- ✅ Dataset Builder Blueprint (DATASET_BUILDER_BLUEPRINT.md)
- ✅ Baseline Model Blueprint (BASELINE_MODEL_BLUEPRINT.md)
- ✅ Training Pipeline & Experiment Management Blueprint (TRAINING_PIPELINE_BLUEPRINT.md)
- ✅ Evaluation & Walk-Forward Backtesting Blueprint (EVALUATION_BACKTESTING_BLUEPRINT.md)
- ✅ Risk Management & Decision Engine Blueprint (RISK_DECISION_ENGINE_BLUEPRINT.md)
- ✅ Prediction & Inference API Blueprint (INFERENCE_API_BLUEPRINT.md)
- ✅ Dashboard UI/UX Blueprint (UI_UX_BLUEPRINT.md)
- ✅ All ADRs documented (DECISIONS.md)

## Milestone 07 — Baseline Model Training (Complete)

Implemented per `docs/BASELINE_MODEL_BLUEPRINT.md` +
`docs/TRAINING_PIPELINE_BLUEPRINT.md`:

1. `src/model/` consumes the Milestone-06 dataset (features at T, labels at T+H).
2. Logistic regression and random forest are configured in YAML.
3. Preprocessing is fit on TRAIN only; TEST is not used for fitting or model selection.
4. Training records experiment identity, versions, fixed seed, and `n_jobs=1`.
5. Model and experiment artifacts are versioned and conflict-protected under
   `data/processed/models/`.
6. Dataset, artifact, reproducibility, and leakage-isolation tests cover the
   training contract.

See `docs/BASELINE_MODEL_IMPLEMENTATION.md` for commands and artifact details.

## Milestone 08 — Evaluation & Walk-Forward Backtesting (Complete)

Implemented per `docs/EVALUATION_BACKTESTING_BLUEPRINT.md` +
`docs/RISK_DECISION_ENGINE_BLUEPRINT.md` (ADR-0028; companion doc
`docs/EVALUATION_BACKTESTING_IMPLEMENTATION.md`):

1. `src/backtest/` chains the eight blueprint modules: data adapter (dataset
   split + checksum-matched cleaned prices) -> prediction adapter (M07 model
   artifact, version-verified) -> signal generator (0.55 thresholds) ->
   execution simulator (long-only, close-to-close, max holding 5 rows, 10
   bps/side costs) -> metrics engine -> benchmarks (buy-and-hold,
   zero-trade) -> report generator (blueprint §27 output set).
2. `src/backtest/walkforward.py` implements expanding-window folds (252/21/21
   defaults) with per-fold retraining and label-overlap purge.
3. `scripts/run_backtest.py` drives both static (`--model-version`) and
   walk-forward (`--walk-forward`) modes.
4. Backtests fail loudly (no silent corrections) and every run is
   reproducible via the experiment record (all versions, strategy/cost
   model, execution convention, price source checksum).
5. Verified live: static run (5 trades, full ledger, honest net-of-cost
   result) and walk-forward run (6 folds, 16 trades) on a deterministic
   synthetic fixture; 439 tests pass; black + ruff clean.

Deferred until the API milestone: `api` config section (INFERENCE_API_BLUEPRINT §22).
PostgreSQL remains Phase 2 (ADR-0005).

## Milestone 09 — Prediction & Inference API (Complete)

Implemented per `docs/INFERENCE_API_BLUEPRINT.md` (ADR-0029; companion doc
`docs/INFERENCE_API_IMPLEMENTATION.md`):

1. `src/api/` serves the four blueprint endpoints at root paths plus the
   milestone-required `/ready`, with the standardized §16 error envelope.
2. Model resolution is explicit > configured default > newest artifact;
   compatibility (status, feature schema, feature/label versions) is
   verified before inference; models are immutable and LRU-cached.
3. Decision logic is the shared M08 signal module; the API adds only the
   RISK §20 risk score and §21 reason codes (regression-tested equality
   with the backtest path).
4. Every prediction is audited to append-only JSONL; audit failure sets
   `audit_written: false` (milestone §27) instead of mutating output.
5. Research/paper modes only — `mode: live` refuses to boot and no
   order/execution code exists (structural test enforces this).
6. Verified live on real artifacts: controlled prediction, all error
   paths, audit record, median latency 7.4 ms (50 requests).

## Milestone 11 — End-to-End Integration, QA & Research Run (COMPLETE — GO)

The complete MVP was validated end-to-end on 2026-09-08. See
`docs/MVP_INTEGRATION_QA_REPORT.md` (authoritative) and
`docs/MVP_RELEASE_NOTES.md`.

- Full E2E research run: AAPL daily, ingest → clean (quality 99.2) →
  features v0.3 (52/52) → labels v0.3 (917 valid) → dataset v0.3 (799 rows,
  559/119/121, quality 96.0) → LR + RF v0.3 → static + walk-forward
  backtests → inference API (200, audited) → dashboard (all read endpoints
  served through the Vite proxy).
- 514 backend + 35 dashboard tests passing; dashboard production build OK.
- Audits: 9 integration boundaries, version consistency, timezone, data
  integrity (0 dupes / 0 OHLC violations / 0 orphans), leakage (NO),
  security (no secrets). Failure injection + AT-01..AT-12 all pass.
- P1 fixes: `/version` now reports the resolved model's versions (regression
  test added); `config/development.yaml` bumped to v0.3.

## Next Milestone: Post-MVP 01 — Autonomous Data Ingestion & Incremental Dataset Growth

The next milestone converts the manual historical workflow into a
controlled incremental data pipeline: scheduler, watermark/checkpoint
tracking, incremental ingestion/cleaning/features, future-window-aware
label finalization, immutable dataset version growth, quality gates,
retry/recovery, idempotency, concurrency protection, pipeline run
observability, and the mandatory incremental-vs-full consistency test.

Precondition: Milestone 11 (MVP GO) approved.
