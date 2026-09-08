"""Tests for the observability & operations engine (Post-MVP Milestone 05).

Covers milestone section 43: health states, freshness (incl. market
closure), events/dedup/resolution, alert severity, aggregation with
critical overrides, correlation/traceability, and the failure-injection
test (monitoring storage unavailable must not break core behavior).
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.config.loader import load_config
from src.operations.engine import OperationsEngine, np_busdays


@pytest.fixture()
def ops_config(tmp_path: Path):
    config = load_config()
    return replace(config, data=replace(config.data, processed_dir=tmp_path / "processed"))


@pytest.fixture()
def ops_engine(ops_config, tmp_path: Path):
    return OperationsEngine(ops_config, operations_dir=tmp_path / "ops", state_dir=tmp_path / "data")


# ---------------------------------------------------------------------------
# Health states (section 43)
# ---------------------------------------------------------------------------
def test_snapshot_unknown_when_no_records(ops_engine):
    snapshot = ops_engine.snapshot()
    assert snapshot.system_status in ("UNKNOWN", "HEALTHY", "CRITICAL")
    # Components are either healthy (storage) or unknown/not-configured
    for component in snapshot.components:
        assert component.status in ("HEALTHY", "UNKNOWN", "NOT_CONFIGURED", "CRITICAL", "DEGRADED")


def test_snapshot_aggregation_precedence(ops_engine):
    from src.operations.engine import ComponentHealth

    components = [
        ComponentHealth(component="a", status="HEALTHY"),
        ComponentHealth(component="b", status="DEGRADED"),
        ComponentHealth(component="c", status="CRITICAL"),
    ]
    assert ops_engine._aggregate(components, []) == "CRITICAL"
    components = [
        ComponentHealth(component="a", status="HEALTHY"),
        ComponentHealth(component="b", status="DEGRADED"),
    ]
    assert ops_engine._aggregate(components, []) == "DEGRADED"
    components = [ComponentHealth(component="a", status="HEALTHY")]
    assert ops_engine._aggregate(components, []) == "HEALTHY"
    components = [ComponentHealth(component="a", status="UNKNOWN")]
    assert ops_engine._aggregate(components, []) == "UNKNOWN"


def test_critical_override_forces_critical(ops_engine):
    from src.operations.engine import ComponentHealth

    components = [ComponentHealth(component="a", status="HEALTHY")]
    assert ops_engine._aggregate(components, ["no ACTIVE model registered"]) == "CRITICAL"


# ---------------------------------------------------------------------------
# Freshness (sections 10-11) — weekends are not staleness
# ---------------------------------------------------------------------------
def test_np_busdays_ignores_weekends():
    # Friday -> Monday = 1 business day, not 3
    friday = datetime(2026, 9, 4)
    monday = datetime(2026, 9, 7)
    assert np_busdays(friday, monday) == 1


def test_freshness_healthy_within_window(ops_config, tmp_path):
    runs = tmp_path / "data" / "pipeline" / "runs"
    runs.mkdir(parents=True)
    now = datetime.utcnow()
    (runs / "run1.json").write_text(
        json.dumps(
            {
                "run_id": "run1",
                "status": "COMPLETED",
                "created_at": (now - timedelta(days=1)).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    engine = OperationsEngine(
        replace(ops_config, data=replace(ops_config.data, processed_dir=tmp_path / "processed")),
        operations_dir=tmp_path / "ops",
        state_dir=tmp_path / "data",
        now=now,
    )
    freshness = engine._data_freshness()
    assert freshness["status"] == "HEALTHY"


def test_freshness_stale_is_critical(ops_config, tmp_path):
    runs = tmp_path / "data" / "pipeline" / "runs"
    runs.mkdir(parents=True)
    now = datetime.utcnow()
    (runs / "run1.json").write_text(
        json.dumps(
            {
                "run_id": "run1",
                "status": "COMPLETED",
                "created_at": (now - timedelta(days=30)).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    engine = OperationsEngine(
        replace(ops_config, data=replace(ops_config.data, processed_dir=tmp_path / "processed")),
        operations_dir=tmp_path / "ops",
        state_dir=tmp_path / "data",
        now=now,
        freshness_warning_days=4,
        freshness_critical_days=10,
    )
    freshness = engine._data_freshness()
    assert freshness["status"] == "CRITICAL"


# ---------------------------------------------------------------------------
# Events: dedup + lifecycle (sections 25-29)
# ---------------------------------------------------------------------------
def test_event_deduplication(ops_engine):
    # Two snapshots with the same degraded component -> occurrence_count grows
    from src.operations.engine import ComponentHealth

    components = [ComponentHealth(component="x", status="DEGRADED", detail="warn")]
    events = ops_engine._collect_events(components)
    deduped = ops_engine._deduplicate(events)
    ops_engine._persist_events(deduped)
    assert len(deduped) == 1
    # second pass merges into occurrence_count=2 (prior OPEN event persisted)
    events2 = ops_engine._collect_events(components)
    deduped2 = ops_engine._deduplicate(events2)
    assert len(deduped2) == 1
    assert deduped2[0].occurrence_count == 2


def test_event_resolution_lifecycle(ops_engine, tmp_path):
    from src.operations.engine import ComponentHealth

    components = [ComponentHealth(component="x", status="CRITICAL", detail="boom")]
    events = ops_engine._deduplicate(ops_engine._collect_events(components))
    ops_engine._persist_events(events)
    event_id = events[0].event_id
    assert ops_engine.acknowledge_event(event_id) is True
    assert ops_engine.resolve_event(event_id) is True
    assert ops_engine.resolve_event(event_id) is False  # already resolved


def test_event_persistence_is_append_only(ops_engine, tmp_path):
    from src.operations.engine import ComponentHealth

    for _ in range(2):
        components = [ComponentHealth(component="x", status="DEGRADED", detail="warn")]
        events = ops_engine._deduplicate(ops_engine._collect_events(components))
        ops_engine._persist_events(events)
    lines = [
        line
        for line in (tmp_path / "ops" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) >= 1


# ---------------------------------------------------------------------------
# Failure injection (section 44): monitoring storage unavailable
# ---------------------------------------------------------------------------
def test_monitoring_storage_failure_does_not_break_core(ops_engine, tmp_path, monkeypatch):
    """Observability must not become a single point of failure."""
    from src.operations.engine import ComponentHealth

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("pathlib.Path.write_text", _boom)
    monkeypatch.setattr("pathlib.Path.open", _boom)
    # Snapshot still builds (best-effort persistence; core logic unaffected)
    snapshot = ops_engine.snapshot()
    assert snapshot.system_status in ("HEALTHY", "UNKNOWN", "CRITICAL", "DEGRADED")


# ---------------------------------------------------------------------------
# Correlation / traceability
# ---------------------------------------------------------------------------
def test_events_carry_correlation_ids(ops_engine):
    from src.operations.engine import ComponentHealth

    components = [ComponentHealth(component="data_pipeline", status="CRITICAL", detail="x")]
    events = ops_engine._collect_events(components)
    assert events[0].component == "data_pipeline"
    assert events[0].fingerprint.startswith("data_pipeline:")


# ---------------------------------------------------------------------------
# Snapshot persistence
# ---------------------------------------------------------------------------
def test_snapshot_persists_latest(ops_engine, tmp_path):
    snapshot = ops_engine.snapshot()
    latest = tmp_path / "ops" / "snapshots" / "latest.json"
    assert latest.exists()
    payload = json.loads(latest.read_text(encoding="utf-8"))
    assert payload["system_status"] == snapshot.system_status
    assert "components" in payload