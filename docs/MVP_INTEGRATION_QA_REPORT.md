# MVP INTEGRATION & QA REPORT — Finance AI

> **Milestone 11 — End-to-End Integration, QA & Research Run**
> **Date:** 2026-09-08 · **Status: GO** (research-only MVP; no production claim)
> This is the authoritative integration and QA report for the Finance AI MVP.

---

## 1. MVP Status

**GO** — with two integration defects found and fixed (P1), all acceptance
tests AT-01..AT-12 pass, the complete research workflow executes end-to-end
with traceable versions, and no critical leakage exists.

**Research-only warning:** the MVP is a research system. It produces signals,
never orders. No live/broker/execution capability exists (structural test
enforced in the API suite).

---

## 2. Repository Assessment

| Item | State |
|------|-------|
| Git | `main`, 0 commits (initial commit pending), working tree untracked by design |
| Python | 3.11.15 (`.venv`) — meets ADR-0002 (3.10+) |
| Node | v24.18.0 / npm 11.16.0 (dashboard) |
| Dependencies | `requirements.txt` pinned; `dashboard/package.json` locked; no new deps added in M11 |
| Configuration | `config/{default,development,testing,production}.yaml`; env overlays |
| Database | None — file-based by design (ADR-0005); migrations N/A (documented) |
| Artifacts | raw CSV (AAPL, MSFT) · interim cleaned · features/labels v0.1–v0.3 · datasets v0.1–v0.3 · models v0.1–v0.3 · backtests · predictions audit |
| Tests | **514 backend + 35 dashboard = 549 passing** |

### Test Suites Executed

| Suite | Result |
|-------|--------|
| Backend unit + integration (pytest) | **514 passed** (22 s) |
| Dashboard (Vitest) | **35 passed** (2.7 s) |
| Dashboard production build (`npm run build`) | **PASS** (2.5 s; chunk-size warning only) |

---

## 3. Integration Boundaries Verified

| # | Boundary | Contract verified | Result |
|---|----------|-------------------|--------|
| 1 | Ingestion → Cleaning | raw CSV immutable; cleaning reads raw + journals audit; raw hash recorded | ✅ |
| 2 | Cleaning → Features | feature engine consumes cleaned CSV; source checksum recorded | ✅ |
| 3 | Features → Labels | both reference the **same source checksum**; exact (ticker, timestamp) index | ✅ |
| 4 | Features + Labels → Dataset | version/checksum/horizon/target-type checks; exact alignment; **0 orphan rows** | ✅ |
| 5 | Dataset → Model | dataset version + feature/label version gating; split checksums | ✅ |
| 6 | Model → Decision Engine | shared `src/backtest/signals.py` used by both backtest and API (regression-tested equality) | ✅ |
| 7 | Model + Dataset → Backtest | frozen model + checksum-matched prices + version-verified predictions | ✅ |
| 8 | Model + Features → Inference API | pre-inference compatibility (status/feature/label/schema) | ✅ |
| 9 | Inference API → Dashboard | Vite proxy serves all read endpoints; typed client matches backend contracts | ✅ |

**Version consistency:** every boundary validates versions explicitly; the
one incoherence found (`/version` reporting stale config versions) was fixed
(see Defects).

---

## 4. E2E Research Run (controlled, AAPL daily)

| Stage | Command | Result |
|-------|---------|--------|
| Ingest | `run_ingest --ticker AAPL --start 2026-08-24 --end 2026-09-04` | COMPLETED: 10 fetched, 4 new, 6 dupes skipped, 0 conflicts |
| Clean | `CleaningPipeline(config).run('AAPL','1d')` | 922 rows, quality **99.2** (gate PASS), audit written |
| Features | `run_features --feature-version v0.3` | **52/52 valid**, 922 rows, 118 warm-up, 0 errors |
| Labels | `run_labels --label-version v0.3` | 917 valid (UP 47.7 / DOWN 31.2 / HOLD 21.2), 5 invalid-future-window, 0 fabricated |
| Dataset | `run_dataset --feature-version v0.3 --label-version v0.3 --output-version v0.3` | 799 rows (559/119/121), 20/20 checks, quality **96.0** |
| Train | `run_model --model logistic_regression --dataset-version v0.3 --feature-version v0.3 --label-version v0.3 --model-version logistic_regression_v0.3` | ROC-AUC 0.538, PR-AUC 0.380, F1 0.240 (honest weak baseline; **no tuning** per M11 §15) |
| Train | `run_model --model random_forest ... --model-version random_forest_v0.3` | ROC-AUC 0.476, PR-AUC 0.370, F1 0.232 |
| Backtest | `run_backtest ... --model-version logistic_regression_v0.3 --split test` | 0 trades at 0.55 threshold; B&H +23.0% (honest abstention) |
| Backtest | `run_backtest ... --walk-forward` | 26 folds, 17 trades, −7.5% net, Sharpe −0.214 |
| Inference | `POST /predict` | 200 · DOWN 0.6155 → SELL · risk 0.232 · reason codes · audited |
| Dashboard | Vite dev proxy | all read endpoints 200 (datasets/models/experiments/backtests/system/status) |

### Run Manifest (research run 2026-09-08)

| Identifier | Value |
|------------|-------|
| run_id | `m11_20260908_aaple2e` |
| source_version | Yahoo Finance chart API (raw CSV, SHA `40c739ea…` full-file after merge; features/labels reference cleaned `4fdb5374…`) |
| feature_set_version | `v0.3` (definition hash `c44261d3…`) |
| label_set_version | `v0.3` (definition hash `eeaba92a…`) |
| dataset_version | `v0.3` (hash `5e07c142…`) |
| model_version | `logistic_regression_v0.3` / `random_forest_v0.3` |
| strategy_version | `stg_v0.1` (backtest config) |
| backtest_version | `v0.1` (config) |
| date range | 2023-01-03 → 2026-09-04 (raw); dataset 2023-06-23 → 2026-08-28 |
| instruments / interval | AAPL / 1d |
| environment | development; Python 3.11.15; git commit: none (repo uncommitted) |
| execution timestamps | 2026-09-08 06:08–07:25 UTC |

---

## 5. Reproducibility

| Check | Result |
|-------|--------|
| Dataset rebuild (same inputs) | **Byte-stable** — identical `version_hash 5e07c142…` |
| Model re-train under same version | **Refused** (conflict protection) — correct |
| Deterministic predictions | Same input → identical probabilities/signal/risk (API regression test) |
| Backtest rerun | Deterministic (fixed seed, frozen artifacts) |

Documented nondeterminism: none observed in the executed paths (all engines
are seed-fixed and conflict-protected).

---

## 6. Leakage Audit

**Question: Can future information influence a historical prediction? → NO.**

| Layer | Check | Result |
|-------|-------|--------|
| Ingestion | timestamps are observation times; no future rows at fetch | ✅ |
| Features | strictly backward-looking (rolling/ewm/shift); mandatory mutation/truncation/timestamp tests | ✅ |
| Labels | label at T uses close at T+5 (horizon); future-extension invariance test | ✅ |
| Dataset split | chronological per instrument; TRAIN < VAL < TEST; purge/embargo config-gated | ✅ |
| Preprocessing | scaler fit on TRAIN only (test asserts VAL/TEST cannot influence fitted artifacts) | ✅ |
| Model training | validation-only feedback; TEST protected | ✅ |
| Thresholds | fixed ±1% / 0.55; never tuned on test data | ✅ |
| Backtest | close-to-close execution; no future execution; label-overlap purge in walk-forward | ✅ |
| Inference | request features are past-only; staleness + future-timestamp rejection | ✅ |

---

## 7. Timezone Audit

| Layer | Policy | Verified |
|-------|--------|----------|
| Source | UTC calendar dates (naive) | ✅ |
| Raw CSV | naive UTC `YYYY-MM-DD` | ✅ |
| Features/Labels/Dataset | naive UTC `datetime64` | ✅ |
| API serialization | ISO-8601 with `+00:00` offset | ✅ |
| Audit trail | ISO-8601 UTC with offset | ✅ |
| Display | dashboard renders UTC timestamps | ✅ |

No ambiguous local timestamps; no DST assumptions (daily bars, UTC).

---

## 8. Data Integrity Audit

| Check | Result |
|-------|--------|
| Duplicates (raw AAPL, 922 rows) | **0** |
| Impossible OHLC | **0** |
| Chronological order | **monotonic** |
| Missing business days | 37/959 (3.9%) — market holidays (no silent gaps) |
| Orphaned features / labels | **0 / 0** (922/922 aligned) |
| Version mismatch at boundaries | 0 (all gates enforced; 1 API display bug fixed) |
| Corrupted artifacts | 0 (checksums verified at every load) |

---

## 9. API Contract Audit

| Check | Result |
|-------|--------|
| Endpoints | `/predict`, `/health`, `/ready`, `/model/info`, `/version` + 10 read endpoints |
| Request schema | pydantic-validated; features + market_context only |
| Response schema | model_output vs decision_output separated (ADR-0020) |
| Error schema | uniform `{error:{code,message,request_id,timestamp}}`; no stack traces |
| Versioning | api v1 · model/feature/label/strategy in `/version` (now coherent) |
| Field names | dashboard typed client matches backend exactly |

**Backtest/Decision consistency:** API and backtest call the same
`src/backtest/signals.py` with the same config; regression test asserts
identical decisions through both paths.

---

## 10. Failure-Injection Results

| Scenario | Behavior | Result |
|----------|----------|--------|
| Future timestamp | 400 INVALID_REQUEST (fail closed) | ✅ |
| Stale data | 422 STALE_DATA | ✅ |
| Feature/label version mismatch | 409 (reachable now that staleness passes first) | ✅ |
| Unknown model | 404 MODEL_NOT_FOUND | ✅ |
| Missing/NaN/Inf features | 422 FEATURE_VALIDATION_FAILED | ✅ |
| Model artifact conflict | Refused (never overwritten) | ✅ |
| Dataset version mismatch | Aborts with VERSION_MISMATCH | ✅ |
| Model unavailable | `/health` degraded 503; `/version` + `/model/info` stay up (28.3) | ✅ |

No fabricated outputs observed anywhere.

---

## 11. Security Audit

| Check | Result |
|-------|--------|
| API keys / DB passwords in repo | **None** |
| `.env` ignored | ✅ |
| Credentials in logs | **None** |
| Secrets in frontend bundle/config | **None** (scanned; only a node_modules doc example) |
| Stack traces in API errors | **None** (uniform error envelope) |
| Yahoo adapter | No credentials required (ADR-0024) |

---

## 12. Performance Smoke Test (local, single process)

| Metric | Value |
|--------|-------|
| Ingestion (10 rows) | 0.8 s |
| Cleaning (922 rows) | <1 s |
| Feature generation | 146 ms |
| Label generation | 28 ms |
| Dataset build | 153 ms |
| Training (LR / RF) | 0.05 / 0.21 s |
| Backtest static / walk-forward | 0.1 / ~40 s (26 folds) |
| Inference latency (n=50) | **median 2.4 ms / p95 3.3 ms** (target <100 ms) |
| Dashboard | dev proxy 200s; production build 2.5 s |

No production-scale claims — these are local smoke numbers only.

---

## 13. UI/UX QA (M10 dashboard)

- All 8 blueprint pages render; typed API client; RESEARCH MODE badge.
- Loading/error/empty/stale states implemented and unit-tested.
- Non-color status communication (icons + text) tested.
- Charts readable (tree-shaken ECharts with accessible summaries).
- Keyboard navigation + responsive layout per UI_UX_BLUEPRINT.
- Known limitation: no interactive browser walkthrough on this machine
  (CDP hang) — replaced by dev-server module checks + production preview +
  component/page tests (documented in CURRENT_STATE).

---

## 14. Acceptance Tests

| ID | Scenario | Result |
|----|----------|--------|
| AT-01 | Historical ingestion succeeds | ✅ COMPLETED, 4 persisted |
| AT-02 | Duplicate ingestion idempotent | ✅ 6 skipped, 0 conflicts |
| AT-03 | Cleaning produces valid processed data | ✅ quality 99.2, gate PASS |
| AT-04 | Feature generation produces expected features | ✅ 52/52 valid |
| AT-05 | Label generation uses correct horizon | ✅ horizon 5, target_timestamp = T+5 |
| AT-06 | Dataset builder creates valid TRAIN/VAL/TEST | ✅ 559/119/121, 20/20 checks |
| AT-07 | Baseline model trains successfully | ✅ LR + RF v0.3 |
| AT-08 | Backtest produces deterministic output | ✅ reproducible artifacts |
| AT-09 | Inference API returns valid prediction | ✅ 200, DOWN 0.6155, SELL, audited |
| AT-10 | Dashboard displays API-backed results | ✅ all read endpoints via proxy |
| AT-11 | Invalid model/version rejected | ✅ 404 / 409 |
| AT-12 | Future leakage checks pass | ✅ (Section 6) |

---

## 15. Bugs Discovered & Fixed

| # | Severity | Description | Fix |
|---|----------|-------------|-----|
| B1 | **P1** | `/version` reported configured feature/label versions (v0.2) while the resolved default model was v0.3 — incoherent version set at the API boundary (M11 §6) | `/version` now reports the resolved default model's versions (`src/api/orchestrator.py` + `src/api/app.py`); regression test added |
| B2 | **P1** | `config/development.yaml` pinned v0.2 after the v0.3 research run, so `/predict` on v0.3 models returned 409 MODEL_VERSION_INCOMPATIBLE (label-version check) | Overlay bumped to v0.3 (same practice as M10) |

No P0 bugs. No remaining P1/P2 known defects.

---

## 16. Remaining Blockers

**None** for the MVP research scope.

Known limitations (not blockers):
- Yahoo Finance is an unofficial endpoint; availability/format can change.
- Daily bars only (no intraday).
- File-based storage (ADR-0005) — no concurrent access.
- Models show honest weak predictive performance (ROC-AUC ≈ 0.48–0.54);
  this is the approved baseline, not a production signal.
- Repo has no commits yet — reproducibility currently rests on artifact
  checksums + config snapshots; an initial commit is recommended.

---

## 17. MVP Release Checklist

**DATA** — [x] ingestion [x] validation [x] cleaning [x] features [x] labels [x] dataset
**ML** — [x] baseline model [x] training [x] validation [x] artifact
**RESEARCH** — [x] backtest [x] metrics [x] benchmarks [x] leakage audit
**API** — [x] prediction [x] errors [x] health [x] readiness
**UI** — [x] dashboard [x] prediction page [x] backtest [x] model/dataset [x] health
**ENGINEERING** — [x] tests [x] documentation [x] security [x] reproducibility

---

## 18. Final Verified Commands (research workflow)

```bash
# 1. Ingest
python -m scripts.run_ingest --ticker AAPL --start 2026-08-24 --end 2026-09-04

# 2. Clean (programmatic; no standalone CLI)
python -c "from src.config.loader import load_config; from src.cleaning.pipeline import CleaningPipeline; from src.logging.logger import configure_from_config; c=load_config(); configure_from_config(c); print(CleaningPipeline(c).run('AAPL','1d').output_file)"

# 3/4. Features + labels
python -m scripts.run_features --ticker AAPL --feature-version v0.3
python -m scripts.run_labels --ticker AAPL --label-version v0.3

# 5. Dataset
python -m scripts.run_dataset --ticker AAPL --feature-version v0.3 --label-version v0.3 --output-version v0.3

# 6. Train
python -m scripts.run_model --model logistic_regression --dataset-version v0.3 --feature-version v0.3 --label-version v0.3 --model-version logistic_regression_v0.3

# 7. Backtest
python -m scripts.run_backtest --ticker AAPL --dataset-version v0.3 --feature-version v0.3 --label-version v0.3 --model-version logistic_regression_v0.3 --split test
python -m scripts.run_backtest --ticker AAPL --dataset-version v0.3 --feature-version v0.3 --label-version v0.3 --walk-forward

# 8. API
python -m scripts.run_api

# 9. Dashboard (separate terminal)
cd dashboard && npm run dev
```

---

## 19. Next Milestone

**Post-MVP Milestone 01 — Autonomous Data Ingestion & Incremental Dataset
Growth** (scheduler, watermarks, incremental processing, label finalization,
dataset versioning, quality gates, recovery, observability). Precondition:
this report (GO).