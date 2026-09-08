# OBSERVABILITY & OPERATIONS IMPLEMENTATION — Finance AI

> **Post-MVP Milestone 05 — Observability & Operations Center**
> **Date:** 2026-09-08 · **Status:** Implemented
> Companion to the P01–P04 implementation docs. This milestone is
> **observability, health, alerting, auditability, and operations only** —
> no new ML features, no retraining, no promotion logic.

---

## 1. Scope

Implemented: unified health model (HEALTHY/DEGRADED/CRITICAL/UNKNOWN/
NOT_CONFIGURED), component health for the components that actually exist
(data pipeline, drift monitor, retraining, model registry, inference API,
storage), data freshness with trading-calendar awareness, data-quality
aggregation (reusing existing quality scores), model health (active model,
age, drift status), inference health (audit-based), operational events with
alert deduplication + cooldown + OPEN/ACKNOWLEDGED/RESOLVED lifecycle,
system-level aggregation with explicit critical-override rules, a health
API surface (`/health/system` on the existing FastAPI app), a dashboard
data contract, and the operations CLI (`scripts/run_ops.py`).

NOT implemented: new prediction models, retraining/promotion logic,
trading, broker integration, new data sources, external monitoring
platforms (Kubernetes/Kafka/SIEM).

## 2. Health Model

| State | Meaning |
|-------|---------|
| HEALTHY | component operating; last run succeeded; freshness within thresholds |
| DEGRADED | operating but with warnings (stale-ish data, drift warnings, recent failures) |
| CRITICAL | unsafe: no active model, storage unavailable, repeated failures, critical drift |
| UNKNOWN | insufficient information (e.g. no runs recorded yet) |
| NOT_CONFIGURED | component intentionally absent/disabled |

Aggregation is explainable: the system status is derived from component
statuses with documented precedence (any CRITICAL → CRITICAL; else any
DEGRADED → DEGRADED; else all present → HEALTHY; else UNKNOWN) plus the
critical-override rules below. Never a mysterious single score.

**Critical overrides (force CRITICAL):** no ACTIVE model in the registry;
artifact/storage dirs unreadable; repeated pipeline failure (≥ 3
consecutive FAILED runs); critical drift event unresolved.

## 3. Freshness

Per instrument: latest source/processed/feature/label timestamps from the
pipeline run records; lag = now − latest, compared against configurable
NORMAL/WARNING/CRITICAL thresholds. Market-closed periods (weekends) are
never staleness failures (business-day calendar; holidays approximated as
in the pipeline layer).

## 4. Events & Alerts

Operational events reuse the drift-event shape (event_id, timestamp,
component, type, severity, message, correlation_id, entity ids, status).
Alert deduplication: fingerprint = (component, event_type, severity);
repeats increment occurrence_count and update last_seen — no alert spam.
Cooldown suppresses duplicate notifications while keeping the condition
OPEN. Lifecycle: OPEN → ACKNOWLEDGED → RESOLVED (explicit; never
auto-resolved by one good sample).

Storage: `data/operations/{events.jsonl, snapshots/latest.json}`.

## 5. Health API & Dashboard Contract

`GET /health/system` (existing FastAPI app) returns:
system status, per-component statuses, data freshness, model health,
drift status, open alerts, recent pipeline runs. The dashboard System
Health page can consume this contract without redesign. No secrets or
internal paths are exposed.

## 6. CLI

```bash
# One-shot operations snapshot (system status + components + alerts)
python -m scripts.run_ops --snapshot

# Acknowledge / resolve an operational event
python -m scripts.run_ops --acknowledge <event_id>
python -m scripts.run_ops --resolve <event_id>
```

## 7. Testing

- Health: healthy/degraded/critical/unknown/not-configured components.
- Freshness: current, stale, weekend (market closed ≠ stale).
- Events: creation, deduplication, acknowledgment, resolution.
- Alerts: warning/critical, cooldown suppression.
- Aggregation: correct system status from component states; overrides.
- Failure: monitoring storage unavailable → core behavior unaffected
  (observability must not become a single point of failure).

## 8. Limitations

- File-based, single-host; no metrics TSDB, no external alert transport.
- Inference latency percentiles come from audit records (p50/p95 computed
  on demand), not a streaming metrics pipeline.
- Monitoring storage failure degrades to log-only (documented, tested).
