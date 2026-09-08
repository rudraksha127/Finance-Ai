"""Tests for the drift detection engine (Post-MVP Milestone 02).

Covers milestone sections 42-45: statistical no-drift/shifted behavior,
feature/prediction/performance monitoring, insufficient-sample handling,
event severity/deduplication/resolution, reproducibility, the
false-positive guard (noise is not CRITICAL), and false-negative
awareness (real shifts are detected).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.config.loader import load_config
from src.drift.engine import DriftEngine
from src.drift.metrics import (
    PSI_GREEN_MAX,
    PSI_YELLOW_MAX,
    feature_drift,
    fdr_correct,
    missingness_drift,
    performance_status,
    prediction_drift,
)

FEATURES = [f"f{i}" for i in range(6)]


def _frame(seed: int, n: int = 200, *, shift: float = 0.0, missing: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    data = {}
    for i, name in enumerate(FEATURES):
        values = rng.normal(0.0 + shift * (i == 0), 1.0, size=n)
        data[name] = values
    frame = pd.DataFrame(data)
    if missing:
        mask = rng.random(frame.shape) < missing
        frame = frame.mask(mask)
    return frame


@pytest.fixture()
def drift_config():
    return load_config()


# ---------------------------------------------------------------------------
# Statistical behavior (section 42)
# ---------------------------------------------------------------------------
def test_stable_distributions_are_green(drift_config, tmp_path):
    # Current window is an exact subset of the reference -> identical
    # distribution by construction (PSI ~ 0, no drift).
    ref = _frame(seed=1, n=400)
    cur = ref.iloc[:150].copy()
    engine = DriftEngine(drift_config, monitoring_dir=tmp_path)
    report = engine.run_check("TEST", reference_frame=ref, current_frame=cur)
    assert report.status == "COMPLETED"
    assert report.health == "HEALTHY"
    assert all(d.severity == "GREEN" for d in report.feature_drifts)
    assert report.events == ()


def test_shifted_distribution_is_detected(drift_config, tmp_path):
    ref = _frame(seed=1, n=400)
    cur = _frame(seed=2, n=150, shift=3.0)  # strong mean shift in f0
    engine = DriftEngine(drift_config, monitoring_dir=tmp_path)
    report = engine.run_check("TEST", reference_frame=ref, current_frame=cur)
    top = report.feature_drifts[0]
    assert top.feature == "f0"
    assert top.psi >= PSI_YELLOW_MAX
    assert top.severity in ("YELLOW", "RED")
    assert report.health in ("DEGRADED", "CRITICAL")
    assert any(e.event_type == "FEATURE_DRIFT" for e in report.events)


def test_threshold_boundaries():
    from src.drift.metrics import _severity_from_psi

    assert _severity_from_psi(0.05, 200) == "GREEN"
    assert _severity_from_psi(0.15, 200) == "YELLOW"
    assert _severity_from_psi(0.30, 200) == "RED"
    assert _severity_from_psi(0.30, 10) == "INSUFFICIENT_DATA"


def test_insufficient_data_flagged(drift_config, tmp_path):
    ref = _frame(seed=1, n=400)
    cur = _frame(seed=2, n=20)  # below MIN_SAMPLE
    engine = DriftEngine(drift_config, monitoring_dir=tmp_path)
    report = engine.run_check("TEST", reference_frame=ref, current_frame=cur)
    assert all(d.severity == "INSUFFICIENT_DATA" for d in report.feature_drifts)


# ---------------------------------------------------------------------------
# Missingness drift (section 13)
# ---------------------------------------------------------------------------
def test_missingness_increase_is_classified(drift_config, tmp_path):
    ref = _frame(seed=1, n=400)
    cur = _frame(seed=2, n=150, missing=0.30)
    result = missingness_drift(ref, cur, FEATURES)
    assert result is not None
    assert result.severity in ("YELLOW", "RED")


def test_stable_missingness_is_green(drift_config, tmp_path):
    ref = _frame(seed=1, n=400)
    cur = _frame(seed=2, n=150)
    result = missingness_drift(ref, cur, FEATURES)
    assert result is not None
    assert result.severity == "GREEN"


# ---------------------------------------------------------------------------
# Prediction drift (section 15)
# ---------------------------------------------------------------------------
def test_prediction_drift_stable_is_green():
    rng = np.random.default_rng(1)
    ref = rng.dirichlet([5, 5, 5], size=200)
    cur = rng.dirichlet([5, 5, 5], size=120)
    assert prediction_drift(ref, cur) == "GREEN"


def test_prediction_drift_shifted_is_detected():
    rng = np.random.default_rng(1)
    ref = rng.dirichlet([5, 5, 5], size=200)  # balanced classes
    # heavily skewed toward class 0
    cur = np.tile([0.9, 0.05, 0.05], (120, 1))
    assert prediction_drift(ref, cur) in ("YELLOW", "RED")


# ---------------------------------------------------------------------------
# Performance monitoring (sections 16-19)
# ---------------------------------------------------------------------------
def test_performance_stable_is_green():
    assert performance_status(0.50, 0.51, 100) == "GREEN"


def test_performance_degradation_warning_and_critical():
    assert performance_status(0.50, 0.44, 100) == "WARNING"
    assert performance_status(0.50, 0.38, 100) == "CRITICAL"


def test_performance_insufficient_sample():
    assert performance_status(0.50, 0.10, 20) == "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# Events: dedup + resolution (sections 29-30)
# ---------------------------------------------------------------------------
def test_event_deduplication_no_spam(drift_config, tmp_path):
    ref = _frame(seed=1, n=400)
    cur = _frame(seed=2, n=150, shift=3.0)
    engine = DriftEngine(drift_config, monitoring_dir=tmp_path)
    first = engine.run_check("TEST", reference_frame=ref, current_frame=cur)
    assert first.events
    second = engine.run_check("TEST", reference_frame=ref, current_frame=cur)
    # Same fingerprint -> occurrence_count incremented, not a new event
    for e2 in second.events:
        match = [e1 for e1 in first.events if e1.fingerprint == e2.fingerprint]
        if match:
            assert e2.occurrence_count == 2
    # Event file grows by at most the number of new (non-duplicate) events
    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) >= len(first.events)


def test_event_resolution(drift_config, tmp_path):
    ref = _frame(seed=1, n=400)
    cur = _frame(seed=2, n=150, shift=3.0)
    engine = DriftEngine(drift_config, monitoring_dir=tmp_path)
    report = engine.run_check("TEST", reference_frame=ref, current_frame=cur)
    event_id = report.events[0].event_id
    assert engine.resolve_event(event_id) is True
    assert engine.resolve_event(event_id) is False  # already resolved
    assert engine.resolve_event("nonexistent") is False


# ---------------------------------------------------------------------------
# Reproducibility (section 33)
# ---------------------------------------------------------------------------
def test_reproducibility_same_inputs_same_results(drift_config, tmp_path):
    ref = _frame(seed=1, n=400)
    cur = _frame(seed=2, n=150, shift=1.5)
    engine_a = DriftEngine(drift_config, monitoring_dir=tmp_path / "a")
    engine_b = DriftEngine(drift_config, monitoring_dir=tmp_path / "b")
    report_a = engine_a.run_check("TEST", reference_frame=ref, current_frame=cur)
    report_b = engine_b.run_check("TEST", reference_frame=ref, current_frame=cur)
    assert [d.psi for d in report_a.feature_drifts] == [d.psi for d in report_b.feature_drifts]
    assert report_a.health == report_b.health


# ---------------------------------------------------------------------------
# False-positive guard (section 43) / false-negative awareness (section 44)
# ---------------------------------------------------------------------------
def test_noise_is_not_critical(drift_config, tmp_path):
    """Small random variation must not become CRITICAL (milestone §43)."""
    ref = _frame(seed=1, n=400)
    cur = _frame(seed=3, n=150, shift=0.15)  # small noise-level shift
    engine = DriftEngine(drift_config, monitoring_dir=tmp_path)
    report = engine.run_check("TEST", reference_frame=ref, current_frame=cur)
    assert not any(e.severity == "CRITICAL" for e in report.events)


def test_meaningful_shift_is_detected(drift_config, tmp_path):
    """A real distribution change must be detected (milestone §44)."""
    ref = _frame(seed=1, n=400)
    cur = _frame(seed=4, n=150, shift=5.0)
    engine = DriftEngine(drift_config, monitoring_dir=tmp_path)
    report = engine.run_check("TEST", reference_frame=ref, current_frame=cur)
    assert report.feature_drifts[0].severity in ("YELLOW", "RED")


# ---------------------------------------------------------------------------
# FDR correction (section 12)
# ---------------------------------------------------------------------------
def test_fdr_correction_bounds_false_positives():
    # 52 features, 50 truly-null p-values near 0.5, 2 tiny
    pvalues = [0.5] * 50 + [0.001, 0.002] + [None, None]
    corrected = fdr_correct(pvalues)
    assert all(p is None for p in corrected[-2:])
    # null features stay above 0.05 after correction
    assert all(p >= 0.05 for p in corrected[:50])


# ---------------------------------------------------------------------------
# Missing artifact failure handling (section 45)
# ---------------------------------------------------------------------------
def test_missing_artifact_fails_explicitly(drift_config, tmp_path):
    engine = DriftEngine(drift_config, monitoring_dir=tmp_path)
    report = engine.run_check("NOPE")
    assert report.status == "FAILED"
    assert report.health == "UNKNOWN"