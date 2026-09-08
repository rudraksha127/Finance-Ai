# DRIFT DETECTION IMPLEMENTATION — Finance AI

> **Post-MVP Milestone 02 — Data & Model Drift Detection Engine**
> **Date:** 2026-09-08 · **Status:** Implemented
> Companion to `docs/AUTONOMOUS_DATA_PIPELINE_IMPLEMENTATION.md` and the
> existing blueprints. This milestone is **monitoring only** — no automatic
> retraining, no model changes, no trading.

---

## 1. Scope

Implemented: reference/current window creation, data/feature/label/
prediction/performance/missingness drift statistics, severity
classification (GREEN/YELLOW/RED → INFO/WARNING/CRITICAL), drift-event
records with alert deduplication + resolution lifecycle, monitoring-run
records, scheduled + manual drift checks, reproducibility metadata,
structured storage under `data/monitoring/` (file-based per ADR-0005),
and a CLI (`scripts/run_drift.py`).

NOT implemented (per milestone): automatic retraining, model replacement,
model promotion, strategy changes, live trading, LLM agents.

## 2. Statistical Methods (chosen, with rationale)

| Method | Used for | Why / limitations |
|--------|----------|-------------------|
| **Population Stability Index (PSI)** | Primary feature/data drift score | Standard, bounded, interpretable (0 = identical); threshold-based; sensitive to binning |
| **Kolmogorov–Smirnov (KS)** | Secondary per-feature significance | Distribution-free; detects location/shape shifts; conservative with ties |
| **Mean / std / quantile deltas** | Contextual summary | Cheap, explainable; not a test |
| **Missingness rate delta** | Separate MISSINGNESS_DRIFT signal | Catches provider/pipeline issues (milestone §13) |

**Threshold strategy (research-backed, configurable):** PSI < 0.10 GREEN,
0.10–0.25 YELLOW, > 0.25 RED (industry-standard bands, documented in the
implementation; thresholds are config, not hard-coded). KS p-value < 0.01
flags YELLOW only when the sample is large enough (minimum current window
size, default 100; below → `INSUFFICIENT_DATA`).

**Multiple testing:** per-feature KS p-values are corrected with
Benjamini–Hochberg FDR (q < 0.05) to bound false positives across the 52
features (milestone §12) — a practical MVP choice, not over-engineering.

**Performance monitoring:** rolling window (default 30 predictions) of
directional accuracy vs the historical baseline; degradation rules:
WARNING when accuracy drops ≥ 5pp below baseline with ≥ 30 samples,
CRITICAL when ≥ 10pp below with ≥ 60 samples and persistence (2
consecutive checks) — no single-sample alerts (milestone §18/§19).

## 3. Windows

- **Reference window:** configurable; default = the training period of the
  active dataset version (or the latest N observations, default 500).
- **Current window:** the most recent N observations (default 120).
- Every analysis records `reference_dataset_version`,
  `reference_feature_version`, `reference_model_version`,
  `reference_period`, `current_period`, `comparison_configuration_version`.

## 4. Drift Event & Alert Lifecycle

Event record: event_id, timestamp, type (DATA_DRIFT / FEATURE_DRIFT /
LABEL_DRIFT / PREDICTION_DRIFT / PERFORMANCE_DRIFT / MISSINGNESS_DRIFT),
severity (INFO/WARNING/CRITICAL), metric, observed/baseline value,
threshold, reference/current window, affected features, model/dataset
versions, status (OPEN/ACKNOWLEDGED/RESOLVED).

**Deduplication:** identical (type, metric, severity, fingerprint) alerts
within a cooldown window (default 12 checks) increment
`occurrence_count`/`last_seen` instead of creating a new event (milestone
§29). **Resolution:** manual (CLI `--resolve`) or explicit safe condition;
never auto-resolved by one normal sample.

## 5. Storage

`data/monitoring/` (file-based, ADR-0005):

```
data/monitoring/
├── events.jsonl          # append-only drift events
├── runs/{run_id}.json    # per-check monitoring-run records
└── summaries/latest.json # aggregated health (HEALTHY/DEGRADED/CRITICAL/UNKNOWN)
```

## 6. CLI

```bash
# Manual drift check (default reference = training period of active dataset)
python -m scripts.run_drift --instrument AAPL

# Explicit reference/current windows + model
python -m scripts.run_drift --instrument AAPL --model random_forest_v0.3 \
    --reference dataset_v0.2 --current 120

# Resolve an open event (manual resolution, milestone §30)
python -m scripts.run_drift --resolve <event_id>
```

Scheduled checks run the same CLI via cron; the drift monitor never runs
more frequently than configured (default cadence documented, not enforced
in code — the caller decides).

## 7. Reproducibility

A drift report is reproducible from: reference version + current
dataset/window + monitoring configuration + code version. Every
monitoring run records all of these, plus the exact feature set used.

## 8. Testing

- Statistical: known no-drift distributions → GREEN; known shifted
  distributions → YELLOW/RED; threshold boundaries.
- Feature: stable feature → GREEN; shifted feature → detected; missingness
  increase → MISSINGNESS_DRIFT.
- Prediction: stable vs shifted prediction distributions.
- Performance: stable, sustained degradation (WARNING→CRITICAL),
  insufficient sample → INSUFFICIENT_DATA.
- Events: severity classification, deduplication (no spam), resolution.
- Reproducibility: same input/config → identical drift results.
- False-positive guard: small random noise → not CRITICAL (milestone §43).
- False-negative awareness: meaningful shifts → detected (milestone §44).

## 9. Limitations

- File-based, single-host; no external alert transport (structured log +
  status records; email/Slack wiring is future work).
- PSI/KS assume numeric distributions; categorical/binary features use
  proportion drift instead.
- Reference window is a fixed snapshot — updating it is an explicit
  versioned action, never silent.
- Drift detection is monitoring only: it never retrains or replaces models.