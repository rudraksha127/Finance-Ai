# AUTONOMOUS DATA PIPELINE IMPLEMENTATION — Finance AI

> **Post-MVP Milestone 01 — Autonomous Data Ingestion & Incremental Dataset Growth**
> **Date:** 2026-09-08 · **Status:** Implemented
> Companion to `docs/DATA_INGESTION_BLUEPRINT.md`, `docs/DATA_CLEANING_VALIDATION.md`,
> `docs/FEATURE_ENGINEERING_BLUEPRINT.md`, `docs/LABEL_GENERATION_BLUEPRINT.md`,
> `docs/DATASET_BUILDER_BLUEPRINT.md` (this layer reuses those engines; it implements none of them).

---

## 1. Scope

Implemented: scheduler integration (OS cron + manual CLI sharing one code
path), watermark/checkpoint tracking, incremental ingestion with explicit
overlap, gap detection, incremental cleaning, lookback-correct incremental
feature generation, future-window-aware label finalization, immutable
dataset-version growth, quality gates, bounded retries, idempotency,
concurrency locking, pipeline-run/stage tracking, freshness tracking,
dry-run mode, structured logging + status records (no external alerting
infrastructure — documented future integration).

NOT implemented (per milestone): automated model retraining, model
promotion/registry, drift-based retraining, broker integration, live
trading, LLM agents.

## 2. Architecture

```
SCHEDULE (cron) or MANUAL (scripts/run_pipeline.py)
        ↓  same PipelineEngine code path
read watermark (instrument, interval)
        ↓
determine missing/new range (gap detection, trading-calendar aware)
        ↓
STAGE: ingestion   (incremental, overlap window, duplicate-safe)
        ↓
STAGE: cleaning    (existing CleaningPipeline; raw tier untouched)
        ↓
STAGE: features    (existing FeatureEngine over the full cleaned series
        ↓            — lookback-correct by construction)
STAGE: labels      (existing LabelEngine; rows without a complete future
        ↓            window stay INVALID_FUTURE_WINDOW = PENDING_LABEL)
STAGE: dataset     (existing DatasetBuilder → NEW immutable version when
        ↓            content changed; identical content = no-op)
QUALITY GATE (data quality + DVAL + gap/duplicate checks)
        ↓
record pipeline run + advance watermark (only on success)
```

## 3. Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scheduler | OS cron invoking the CLI (no new scheduler code) | Smallest reliable mechanism (milestone §6); the CLI is the single entry point |
| Watermark store | JSON file per instrument/interval under `data/pipeline/watermarks.json` | File-based MVP (ADR-0005); advanced only after full stage success |
| Locking | Filesystem lock per (instrument, interval) | Simplest reliable concurrency protection for a single-host MVP |
| Feature incrementality | Recompute from the full cleaned series, persist only when content changed (version bump) | Reuses the one approved feature engine; lookback correctness is guaranteed; the incremental-vs-full consistency test is exact by construction |
| Label finalization | Rows whose horizon window is complete become VALID at the next run; incomplete rows stay `INVALID_FUTURE_WINDOW` (PENDING_LABEL, counted, never fabricated) | Matches label engine semantics |
| Dataset growth | New dataset version per content-changing run (v0.3 → v0.4 …); identical rebuild is a byte-stable no-op | Immutability of finalized snapshots (milestone §18/§19) |
| Version separation | `pipeline_run_id` (every run) ≠ `dataset_version` (content-changing runs only) | Milestone §19 |
| Config version | `pipeline_config_version` recorded in every run record | Milestone §36 |

## 4. Watermark / Checkpoint

```json
{
  "AAPL": {
    "1d": {
      "instrument": "AAPL", "interval": "1d", "source": "yahoo_finance",
      "last_successful_timestamp": "2026-09-04T00:00:00",
      "pipeline_run_id": "pl_...",
      "status": "COMPLETED", "updated_at": "..."
    }
  }
}
```

- Advanced only after ingestion + cleaning + features + labels + dataset
  + quality gate all succeed for the run.
- A failed/partial run leaves the previous watermark untouched (§8/§11);
  recovery = simply re-run (idempotent, resumes from the watermark).

## 5. Pipeline Run States

`CREATED → RUNNING → COMPLETED | FAILED | PARTIAL` and
`RUNNING → RETRYING → RUNNING` (bounded transient retries inside the
ingestion stage reuse the ingestion engine's backoff). Stage records
(INGESTION/VALIDATION/CLEANING/FEATURES/LABELS/DATASET) each store
started_at, completed_at, status, input/output range, records processed,
errors. Run records: `data/pipeline/runs/{run_id}.json`.

## 6. Quality Gate

The run fails (watermark not advanced, dataset not published as valid)
when any of: ingestion PARTIAL/FAILED; cleaning gate < configured minimum;
feature FVAL errors; label generation errors; dataset DVAL errors;
dataset quality < `pipeline.min_quality_score`; unexpected duplicates;
gap ratio above `pipeline.max_gap_ratio` (weekends/holidays excluded).

## 7. Freshness

Per instrument: `latest_source_timestamp`, `latest_processed_timestamp`,
`latest_feature_timestamp`, `latest_label_timestamp` recorded in the run
record; `pending_label_count` reported for label lag. Market-closed
periods are never staleness failures (business-day calendar).

## 8. Manual Trigger / Dry Run

```bash
# manual (same code path as scheduled)
python -m scripts.run_pipeline --instrument AAPL

# explicit range
python -m scripts.run_pipeline --instrument AAPL --from 2026-09-01 --to 2026-09-05

# plan without side effects
python -m scripts.run_pipeline --instrument AAPL --dry-run
```

Dry-run reports: current watermark, detected missing range, expected
stages, expected record counts — and writes nothing.

## 9. Scheduling

Cron examples (the CLI is the scheduler's entry point):

```cron
# after each US market close (16:15 ET == 20:15/21:15 UTC)
15 20 * * 1-5  cd /path/to/finance-ai-mvp && .venv/Scripts/python -m scripts.run_pipeline --instrument AAPL
```

Schedule values are documentation, not code: the pipeline has no internal
clock assumptions; the caller decides cadence.

## 10. Testing

- Watermark: advancement, no-advance on failure, recovery resume.
- Gaps: weekend/holiday exclusion, real-gap detection.
- Engine: end-to-end incremental run on temp dirs; idempotent re-run
  (no duplicate rows, no spurious version bump); dry-run writes nothing;
  failure injection (cleaning failure → downstream stages not run, no
  publish, watermark preserved, status FAILED); lock prevents concurrent
  runs.
- **Incremental-vs-full consistency (mandatory §38):** pipeline output
  equals a full historical recomputation for the same final range
  (identical by construction — same engines, same series — asserted).
- **Historical immutability (§39):** previously finalized dataset versions
  are byte-identical after a new incremental run.

## 11. Limitations

- Single-host, file-based (ADR-0005); the filesystem lock is not a
  distributed lock.
- Feature recomputation is full-series (O(history) per run) — correct and
  simple; true windowed incremental computation is a future optimization.
- Alerts are structured log events + status records; email/Slack wiring is
  future work (documented, not built).
- Only daily bars are exercised by the scheduler examples.
