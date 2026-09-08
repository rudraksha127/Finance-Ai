"""Observability & operations engine (Post-MVP Milestone 05).

Answers: Is the system running? Is data fresh? Is the model healthy?
Are there unresolved critical failures? — with an explainable health model,
event/alert lifecycle (dedup + cooldown), and system aggregation.

Monitoring only: never retrains, promotes, or trades. Reuses existing
records (pipeline runs, drift events, retraining runs, registry, audit).
Storage: data/operations/{events.jsonl, snapshots/latest.json}.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.config.loader import AppConfig
from src.logging.logger import get_logger

logger = get_logger("operations.engine")

HEALTH_STATES = ("HEALTHY", "DEGRADED", "CRITICAL", "UNKNOWN", "NOT_CONFIGURED")
SEVERITIES = ("INFO", "WARNING", "CRITICAL")
EVENT_STATUSES = ("OPEN", "ACKNOWLEDGED", "RESOLVED")

# Critical overrides (milestone §24): any of these forces CRITICAL.
REPEATED_PIPELINE_FAILURES = 3


@dataclass(frozen=True)
class ComponentHealth:
    """Health record for one system component (milestone §8)."""

    component: str
    status: str
    last_success: str | None = None
    last_failure: str | None = None
    last_run: str | None = None
    error_count: int = 0
    warning_count: int = 0
    detail: str = ""


@dataclass(frozen=True)
class OpsEvent:
    """Operational event (milestone §25)."""

    event_id: str
    timestamp: str
    component: str
    event_type: str
    severity: str
    status: str = "OPEN"
    message: str = ""
    correlation_id: str | None = None
    entity_id: str | None = None
    model_version: str | None = None
    dataset_version: str | None = None
    fingerprint: str = ""
    first_seen: str = ""
    last_seen: str = ""
    occurrence_count: int = 1


@dataclass(frozen=True)
class SystemSnapshot:
    """Aggregated system health (milestone §23)."""

    generated_at: str
    system_status: str
    components: tuple[ComponentHealth, ...]
    data_freshness: dict
    model_health: dict
    drift_status: dict
    open_alerts: tuple[OpsEvent, ...]
    overrides: list[str] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class OperationsEngine:
    """Builds the unified operational health snapshot."""

    def __init__(
        self,
        config: AppConfig,
        *,
        operations_dir: Path | None = None,
        state_dir: Path | None = None,
        now: datetime | None = None,
        freshness_warning_days: int = 4,
        freshness_critical_days: int = 10,
    ) -> None:
        self.config = config
        self.operations_dir = operations_dir or Path("data/operations")
        self.state_dir = state_dir or Path("data")
        self.now = now or _now()
        self.freshness_warning_days = freshness_warning_days
        self.freshness_critical_days = freshness_critical_days

    # ------------------------------------------------------------------
    def snapshot(self) -> SystemSnapshot:
        """Build the full system snapshot (explainable aggregation)."""
        components: list[ComponentHealth] = []
        overrides: list[str] = []

        pipeline = self._pipeline_health()
        components.append(pipeline)
        drift = self._drift_health()
        components.append(drift)
        retraining = self._retraining_health()
        components.append(retraining)
        registry_health, model_health = self._model_health()
        components.append(registry_health)
        storage = self._storage_health()
        components.append(storage)

        freshness = self._data_freshness()
        components.append(freshness["component"])

        # --- Critical overrides ----------------------------------------
        if registry_health.status == "CRITICAL":
            overrides.append("no ACTIVE model registered")
        if storage.status == "CRITICAL":
            overrides.append("storage unavailable")
        if pipeline.error_count >= REPEATED_PIPELINE_FAILURES:
            overrides.append(f"repeated pipeline failures ({pipeline.error_count})")
        if drift.status == "CRITICAL":
            overrides.append("critical drift unresolved")

        system_status = self._aggregate(components, overrides)
        events = self._collect_events(components)
        deduped = self._deduplicate(events)
        self._persist_events(deduped)

        snapshot = SystemSnapshot(
            generated_at=self.now.isoformat(),
            system_status=system_status,
            components=tuple(components),
            data_freshness={k: v for k, v in freshness.items() if k != "component"},
            model_health=model_health,
            drift_status={
                "status": drift.status,
                "detail": drift.detail,
            },
            open_alerts=tuple(e for e in deduped if e.status == "OPEN"),
            overrides=overrides,
        )
        self._persist_snapshot(snapshot)
        return snapshot

    # ------------------------------------------------------------------
    # Component healths (only components that exist are monitored)
    # ------------------------------------------------------------------
    def _pipeline_health(self) -> ComponentHealth:
        runs_dir = self.state_dir / "pipeline" / "runs"
        if not runs_dir.exists():
            return ComponentHealth(
                component="data_pipeline",
                status="UNKNOWN",
                detail="no pipeline runs recorded yet",
            )
        runs = []
        for path in sorted(runs_dir.glob("*.json"))[-10:]:
            try:
                runs.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        if not runs:
            return ComponentHealth(
                component="data_pipeline", status="UNKNOWN", detail="runs unreadable"
            )
        failures = sum(1 for r in runs if r.get("status") == "FAILED")
        successes = [r for r in runs if r.get("status") == "COMPLETED"]
        last_run = runs[-1]
        last_success = successes[-1]["created_at"] if successes else None
        last_failure = next(
            (r["created_at"] for r in reversed(runs) if r.get("status") == "FAILED"), None
        )
        if failures >= REPEATED_PIPELINE_FAILURES:
            status = "CRITICAL"
        elif failures and not successes or last_run.get("status") == "FAILED":
            status = "DEGRADED"
        else:
            status = "HEALTHY"
        return ComponentHealth(
            component="data_pipeline",
            status=status,
            last_success=last_success,
            last_failure=last_failure,
            last_run=last_run.get("created_at"),
            error_count=failures,
            warning_count=sum(len(r.get("warnings") or []) for r in runs),
            detail=f"{len(runs)} recent runs, {failures} failed",
        )

    def _drift_health(self) -> ComponentHealth:
        summary_path = self.state_dir / "monitoring" / "summaries" / "latest.json"
        if not summary_path.exists():
            return ComponentHealth(
                component="drift_monitor",
                status="NOT_CONFIGURED",
                detail="no drift checks recorded",
            )
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ComponentHealth(
                component="drift_monitor", status="UNKNOWN", detail="summary unreadable"
            )
        health = summary.get("health", "UNKNOWN")
        status = {"HEALTHY": "HEALTHY", "DEGRADED": "DEGRADED", "CRITICAL": "CRITICAL"}.get(
            health, "UNKNOWN"
        )
        return ComponentHealth(
            component="drift_monitor",
            status=status,
            detail=f"open critical={summary.get('open_critical', 0)}, open warning={summary.get('open_warning', 0)}",
        )

    def _retraining_health(self) -> ComponentHealth:
        runs_dir = self.state_dir / "retraining"
        if not runs_dir.exists():
            return ComponentHealth(
                component="retraining",
                status="NOT_CONFIGURED",
                detail="no retraining runs recorded",
            )
        runs = []
        for path in sorted(runs_dir.glob("*.json"))[-10:]:
            try:
                runs.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        if not runs:
            return ComponentHealth(
                component="retraining", status="UNKNOWN", detail="runs unreadable"
            )
        failed = sum(1 for r in runs if r.get("status") == "FAILED")
        approved = sum(1 for r in runs if r.get("decision") == "CANDIDATE_APPROVED")
        last = runs[-1]
        status = "CRITICAL" if failed >= 3 else ("DEGRADED" if failed else "HEALTHY")
        return ComponentHealth(
            component="retraining",
            status=status,
            last_run=last.get("completed_at") or last.get("started_at"),
            error_count=failed,
            detail=f"last={last.get('status')}, approved={approved}, failed={failed}",
        )

    def _model_health(self) -> tuple[ComponentHealth, dict]:
        from src.registry.engine import ModelRegistry, RegistryError

        registry = ModelRegistry(self.config)
        try:
            active = registry.get_active_model()
        except (RegistryError, OSError, ValueError) as error:
            # Monitoring must not become a single point of failure: an
            # unreadable registry (e.g. storage failure) degrades the
            # component instead of crashing the snapshot.
            return (
                ComponentHealth(
                    component="model_registry",
                    status="UNKNOWN",
                    detail=f"registry probe failed: {error}",
                ),
                {"status": "UNKNOWN", "active_model": None, "detail": str(error)},
            )
            return (
                ComponentHealth(component="model_registry", status="CRITICAL", detail=str(error)),
                {"status": "CRITICAL", "active_model": None, "detail": str(error)},
            )
        age_days = None
        if active.activated_at:
            try:
                activated = datetime.fromisoformat(active.activated_at)
                age_days = round((self.now - activated).total_seconds() / 86400, 2)
            except ValueError:
                pass
        health = {
            "status": "HEALTHY",
            "active_model": active.model_version,
            "model_age_days": age_days,
            "dataset_version": active.dataset_version,
            "feature_version": active.feature_version,
            "label_version": active.label_version,
        }
        return (
            ComponentHealth(
                component="model_registry",
                status="HEALTHY",
                last_success=active.activated_at,
                detail=f"active={active.model_version}",
            ),
            health,
        )

    def _storage_health(self) -> ComponentHealth:
        processed = self.config.data.processed_dir
        processed = processed if processed.is_absolute() else Path.cwd() / processed
        try:
            processed.mkdir(parents=True, exist_ok=True)
            probe = processed / ".ops_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return ComponentHealth(
                component="storage", status="HEALTHY", detail="processed tier writable"
            )
        except OSError as error:
            return ComponentHealth(
                component="storage", status="CRITICAL", detail=f"storage failure: {error}"
            )

    def _data_freshness(self) -> dict:
        """Freshness from pipeline run records (weekends are not staleness)."""
        runs_dir = self.state_dir / "pipeline" / "runs"
        latest: dict | None = None
        if runs_dir.exists():
            for path in sorted(runs_dir.glob("*.json"), reverse=True):
                try:
                    record = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if record.get("status") == "COMPLETED":
                    latest = record
                    break
        component_status = "UNKNOWN"
        detail = "no completed pipeline runs"
        freshness: dict = {
            "component": None,
            "latest_run": None,
            "lag_days": None,
            "status": component_status,
            "detail": detail,
        }
        if latest is not None:
            try:
                last_ts = datetime.fromisoformat(latest["created_at"])
                lag_days = (self.now - last_ts).total_seconds() / 86400
                # Weekend adjustment: a weekend gap is expected, not staleness.
                business_lag = float(np_busdays(last_ts, self.now))
                freshness["latest_run"] = latest["created_at"]
                freshness["lag_days"] = round(lag_days, 2)
                freshness["business_lag_days"] = round(business_lag, 2)
                if business_lag >= self.freshness_critical_days:
                    component_status = "CRITICAL"
                elif business_lag >= self.freshness_warning_days:
                    component_status = "DEGRADED"
                else:
                    component_status = "HEALTHY"
                detail = f"last successful run {latest['created_at']} ({business_lag:.1f} business days ago)"
            except (KeyError, ValueError) as error:
                detail = f"freshness unreadable: {error}"
        freshness["status"] = component_status
        freshness["detail"] = detail
        freshness["component"] = ComponentHealth(
            component="data_freshness", status=component_status, detail=detail
        )
        return freshness

    # ------------------------------------------------------------------
    # Events & alerts
    # ------------------------------------------------------------------
    def _collect_events(self, components: list[ComponentHealth]) -> list[OpsEvent]:
        events: list[OpsEvent] = []
        for component in components:
            if component.status == "CRITICAL":
                events.append(
                    self._event(
                        component.component, "COMPONENT_CRITICAL", "CRITICAL", component.detail
                    )
                )
            elif component.status == "DEGRADED":
                events.append(
                    self._event(
                        component.component, "COMPONENT_DEGRADED", "WARNING", component.detail
                    )
                )
        return events

    def _event(self, component: str, event_type: str, severity: str, message: str) -> OpsEvent:
        ts = self.now.isoformat()
        return OpsEvent(
            event_id=uuid.uuid4().hex,
            timestamp=ts,
            component=component,
            event_type=event_type,
            severity=severity,
            message=message,
            fingerprint=f"{component}:{event_type}:{severity}",
            first_seen=ts,
            last_seen=ts,
        )

    def _deduplicate(self, events: list[OpsEvent]) -> list[OpsEvent]:
        """Merge repeats into occurrence counts; keep prior OPEN events."""
        existing: dict[str, OpsEvent] = {}
        path = self.operations_dir / "events.jsonl"
        if path.exists():
            try:
                raw_lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                raw_lines = []
            for line in raw_lines:
                if not line.strip():
                    continue
                raw = json.loads(line)
                if raw.get("status") == "OPEN":
                    existing[raw["fingerprint"]] = OpsEvent(**raw)
        merged: list[OpsEvent] = []
        for event in events:
            prior = existing.pop(event.fingerprint, None)
            if prior is not None:
                merged.append(
                    OpsEvent(
                        **{
                            **asdict(prior),
                            "last_seen": event.timestamp,
                            "occurrence_count": prior.occurrence_count + 1,
                        }
                    )
                )
            else:
                merged.append(event)
        return merged

    def _persist_events(self, events: list[OpsEvent]) -> None:
        if not events:
            return
        try:
            self.operations_dir.mkdir(parents=True, exist_ok=True)
            with (self.operations_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
                for event in events:
                    handle.write(json.dumps(asdict(event), sort_keys=True) + "\n")
        except OSError as error:
            # Observability must never become a single point of failure (§40).
            logger.warning("ops_event_persist_failed", error=str(error))

    def _persist_snapshot(self, snapshot: SystemSnapshot) -> None:
        try:
            snapshots = self.operations_dir / "snapshots"
            snapshots.mkdir(parents=True, exist_ok=True)
            payload = asdict(snapshot)
            payload["open_alerts"] = [asdict(e) for e in snapshot.open_alerts]
            payload["components"] = [asdict(c) for c in snapshot.components]
            (snapshots / "latest.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
            )
        except OSError as error:
            # Observability must never become a single point of failure (§40).
            logger.warning("ops_snapshot_persist_failed", error=str(error))

    # ------------------------------------------------------------------
    def acknowledge_event(self, event_id: str) -> bool:
        return self._transition_event(event_id, "ACKNOWLEDGED")

    def resolve_event(self, event_id: str) -> bool:
        return self._transition_event(event_id, "RESOLVED")

    def _transition_event(self, event_id: str, to_status: str) -> bool:
        path = self.operations_dir / "events.jsonl"
        if not path.exists():
            return False
        lines = path.read_text(encoding="utf-8").splitlines()
        # ACKNOWLEDGED only from OPEN; RESOLVED from OPEN or ACKNOWLEDGED.
        allowed_source = ("OPEN",) if to_status == "ACKNOWLEDGED" else ("OPEN", "ACKNOWLEDGED")
        updated, found = [], False
        for line in lines:
            if not line.strip():
                continue
            raw = json.loads(line)
            if raw.get("event_id") == event_id and raw.get("status") in allowed_source:
                raw["status"] = to_status
                found = True
            updated.append(json.dumps(raw, sort_keys=True))
        if found:
            path.write_text("\n".join(updated) + "\n", encoding="utf-8")
        return found

    # ------------------------------------------------------------------
    @staticmethod
    def _aggregate(components: list[ComponentHealth], overrides: list[str]) -> str:
        if overrides:
            return "CRITICAL"
        statuses = [c.status for c in components]
        if "CRITICAL" in statuses:
            return "CRITICAL"
        if "DEGRADED" in statuses:
            return "DEGRADED"
        if all(s in ("HEALTHY", "NOT_CONFIGURED") for s in statuses):
            return "HEALTHY"
        return "UNKNOWN"


def np_busdays(start: datetime, end: datetime) -> int:
    """Business days between two naive-UTC datetimes (weekends excluded)."""
    import numpy as np

    return int(np.busday_count(start.date(), end.date()))
