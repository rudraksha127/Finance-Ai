# AUTONOMOUS RETRAINING IMPLEMENTATION — Finance AI

> **Post-MVP Milestone 03 — Autonomous Retraining & Candidate Model Evaluation**
> **Date:** 2026-09-08 · **Status:** Implemented
> Companion to `docs/DRIFT_DETECTION_IMPLEMENTATION.md` and the training/
> backtesting blueprints. **Governance principle:** autonomous retraining,
> experimentation, and candidate evaluation are allowed; autonomous LIVE
> model replacement is NOT — the pipeline can produce `CANDIDATE_APPROVED`
> but never activates a model (no registry/promotion exists yet; that is
> Post-MVP Milestone 04).

---

## 1. Scope

Implemented: retraining triggers (scheduled, dataset-growth, drift,
performance-degradation, manual), eligibility checks with
`RETRAINING_SKIPPED` reasons, cooldown protection against retraining
loops, candidate identity/metadata, candidate training via the EXISTING
`BaselineTrainer`, candidate evaluation (ML metrics + financial backtest
on the same evaluation framework), current-vs-candidate comparison with
risk-aware tradeoff rules, explicit promotion gates (7 gates), candidate
lifecycle records, idempotency fingerprinting, concurrency locking,
failure recovery, dry-run, manual trigger CLI, and the critical safety
test (a failed/rejected candidate can never change the current model).

NOT implemented: automatic live deployment, broker integration, live
trading, strategy rewriting, autonomous feature/label redesign, LLM agents.

## 2. Trigger → Flow

```
Trigger (schedule | dataset-growth | drift | performance | manual)
    ↓
Eligibility check (new data, quality, labels finalized, no critical drift,
                   cooldown, not already running)
    ↓  (fails -> RETRAINING_SKIPPED with reason; nothing trained)
Retraining run record (CREATED -> RUNNING)
    ↓
Candidate training (existing BaselineTrainer, approved config only)
    ↓
Candidate validation (artifact integrity + prediction sanity)
    ↓
Evaluation: ML metrics (VAL) + financial backtest (TEST, shared engine)
    ↓
Current-vs-candidate comparison (same dataset/period/costs/strategy)
    ↓
Promotion gates G1..G7 (measurable criteria; no "looks better")
    ↓
CANDIDATE_APPROVED | CANDIDATE_REJECTED (audit record with reasons)
    ↓
Retraining run COMPLETED (current model UNCHANGED)
```

## 3. Triggers & Cooldown

| Trigger | Default rule |
|---------|--------------|
| `schedule` | enabled, evaluated per run; actual cadence is the caller's cron |
| `dataset_growth` | new dataset version hash differs from the last retraining's |
| `drift` | any CRITICAL drift event open for the active model |
| `performance` | PERFORMANCE_DRIFT event with severity CRITICAL |
| `manual` | CLI `--reason` (bypasses trigger evaluation, not eligibility) |

**Cooldown:** minimum interval between retraining runs (default 7 days);
a retraining fingerprint (dataset hash + feature/label versions + config
version + model family) makes identical triggers idempotent — a repeated
trigger with the same fingerprint is SKIPPED (`already_evaluated`).

## 4. Eligibility (all must pass)

1. Dataset artifact exists, quality score ≥ configured minimum.
2. Labels finalized for the training range (no INVALID rows in TRAIN).
3. Feature/label versions compatible with the training config.
4. No unresolved CRITICAL data-quality failure in the latest pipeline run.
5. Cooldown elapsed; no concurrent retraining (filesystem lock).
6. Sufficient rows (train ≥ 100) after the last run.

Failure → `RETRAINING_SKIPPED` record with the failing reason. Nothing is
trained, nothing changes.

## 5. Candidate Evaluation & Gates

The candidate and the current model are evaluated on the SAME dataset
version, split, cost model, and strategy (fair comparison, milestone §16).
Metrics: ML (accuracy, macro precision/recall/F1, ROC-AUC, PR-AUC) and
financial (cumulative return, Sharpe, Sortino, max drawdown, profit
factor, win rate, turnover) from the shared backtest engine.

**Gates (measurable):**

| Gate | Criterion (defaults; config-driven) |
|------|-------------------------------------|
| G1 Data Quality | dataset quality ≥ min; no critical pipeline failures |
| G2 Training Validity | artifact loads; metadata matches; versions consistent |
| G3 Prediction Sanity | probabilities valid (sum≈1, no NaN/Inf); classes valid |
| G4 Predictive Quality | candidate F1_macro ≥ current − 0.02 (no material regression) |
| G5 Financial Performance | candidate Sharpe ≥ current − 0.10 AND max drawdown ≤ current + 0.02 (risk-aware tradeoff) |
| G6 Robustness | evaluation on ≥ 2 windows (VAL + TEST); no split with catastrophic failure |
| G7 Operational Health | artifact integrity; runtime health checks pass |

All gates must PASS → `CANDIDATE_APPROVED`; any FAIL → `CANDIDATE_REJECTED`
with per-gate results recorded (milestone §19/§20). Minimum-improvement
thresholds are configurable; defaults documented as research baselines.

## 6. Model Lifecycle (registry boundary, pre-P04)

Statuses: `CANDIDATE → VALIDATING → APPROVED | REJECTED`; approved models
are marked `APPROVED` (activation is P04's job). Every retraining run
records: retraining_run_id, trigger_type/reason, current model version,
candidate model version, dataset/feature/label versions, config version,
fingerprint, started/completed, status, decision, gate results.

Storage: `data/retraining/{run_id}.json` + candidate evaluation reports
under `data/processed/models/experiments/` (existing experiment artifacts).

## 7. CLI

```bash
# Dry run: show trigger/eligibility/plan without training
python -m scripts.run_retraining --dry-run

# Manual trigger (same workflow as scheduled)
python -m scripts.run_retraining --reason "monthly schedule" --dataset v0.3

# Scheduled: cron invokes the same command
```

## 8. Critical Safety

The current model is never modified: retraining produces a NEW model
artifact under a new version; the inference API keeps resolving its
configured default until P04 introduces explicit promotion. The mandatory
test proves that candidate training failure, evaluation failure, and
candidate rejection all leave the current model untouched and serving.

## 9. Testing

- Triggers: schedule/dataset-growth/drift/performance/insufficient-data.
- Eligibility: valid/invalid dataset, insufficient labels, quality failure.
- Candidate: creation, metadata, artifact integrity, prediction sanity.
- Comparison: same evaluation period, same costs, metric comparison.
- Gates: pass, fail, tradeoff rejection.
- Idempotency: repeated identical trigger → SKIPPED.
- Failure: training/backtest/evaluation failure → run FAILED, model unchanged.
- **Critical safety test (§41, mandatory).**

## 10. Limitations

- Hyperparameters: approved baseline configuration only (no search) —
  per milestone §13.
- Single candidate per retraining run; no ensembles.
- Robustness = multi-window evaluation (VAL/TEST) + cost scenarios from
  the existing scenario runner; regime-stratified evaluation is future work.
- No automatic activation (by design; see P04).