"""Tests for controlled autonomous retraining (Post-MVP Milestone 03).

Covers milestone section 40: triggers, eligibility, candidate lifecycle,
gates (pass/fail/tradeoff), idempotency, failure recovery, and the
MANDATORY critical safety test (section 41): candidate training failure,
evaluation failure, or rejection can NEVER change the current model.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from src.config.loader import ModelConfig, RetrainingConfig
from src.retraining.engine import RetrainingEngine
from tests.api_helpers import make_api_config  # sandboxed config + trained model


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def retrain_config(tmp_path: Path):
    """Sandboxed config with a trained fixture model and retraining dirs."""
    config = make_api_config(tmp_path)
    return replace(
        config,
        retraining=RetrainingConfig(
            cooldown_days=0,  # tests run back-to-back
            min_train_rows=50,
            min_quality_score=50.0,
            model_name="logistic_regression",
        ),
        model=ModelConfig(artifact_dir=tmp_path / "models"),
    )


# ---------------------------------------------------------------------------
# Eligibility (section 8)
# ---------------------------------------------------------------------------
def test_missing_dataset_is_skipped(retrain_config, tmp_path):
    engine = RetrainingEngine(retrain_config, retraining_dir=tmp_path / "retraining")
    run = engine.evaluate_trigger(
        trigger_type="manual", trigger_reason="test", dataset_version="v9.9"
    )
    assert run.status == "SKIPPED"
    assert "not found" in (run.error or "")


def test_cooldown_blocks_retraining(retrain_config, tmp_path, monkeypatch):
    """Cooldown blocks retraining when the fingerprint DIFFERS (new inputs)
    but the cooldown window has not elapsed."""
    strict = replace(
        retrain_config, retraining=replace(retrain_config.retraining, cooldown_days=30)
    )
    engine = RetrainingEngine(strict, retraining_dir=tmp_path / "retraining")
    first = engine.evaluate_trigger(trigger_type="manual", trigger_reason="first")
    assert first.status in ("APPROVED", "REJECTED")

    # Simulate changed inputs: a different fingerprint on the next trigger.
    calls = {"n": 0}

    def _varying(*args, **kwargs):
        calls["n"] += 1
        return f"fp_{calls['n']}"

    monkeypatch.setattr(engine, "_fingerprint", _varying)
    second = engine.evaluate_trigger(trigger_type="manual", trigger_reason="second")
    assert second.status == "SKIPPED"
    assert "cooldown" in (second.error or "")


def test_identical_fingerprint_is_skipped(retrain_config, tmp_path):
    engine = RetrainingEngine(retrain_config, retraining_dir=tmp_path / "retraining")
    first = engine.evaluate_trigger(trigger_type="manual", trigger_reason="first")
    assert first.status in ("APPROVED", "REJECTED")
    second = engine.evaluate_trigger(trigger_type="manual", trigger_reason="second")
    assert second.status == "SKIPPED"
    assert "already evaluated" in (second.error or "")


# ---------------------------------------------------------------------------
# Dry run (section 39)
# ---------------------------------------------------------------------------
def test_dry_run_does_not_train(retrain_config, tmp_path):
    engine = RetrainingEngine(retrain_config, retraining_dir=tmp_path / "retraining")
    run = engine.evaluate_trigger(trigger_type="manual", trigger_reason="dry", dry_run=True)
    assert run.status == "TRIGGERED"
    assert run.candidate_model_version is None
    # No new model artifacts beyond the fixture model
    models = [p.name for p in retrain_config.model.artifact_dir.iterdir() if p.is_dir()]
    assert all("candidate" not in name for name in models)


# ---------------------------------------------------------------------------
# Candidate flow + gates (sections 15/18/19)
# ---------------------------------------------------------------------------
def test_candidate_trains_and_gates_evaluate(retrain_config, tmp_path):
    engine = RetrainingEngine(retrain_config, retraining_dir=tmp_path / "retraining")
    run = engine.evaluate_trigger(trigger_type="manual", trigger_reason="gate-test")
    assert run.status in ("APPROVED", "REJECTED")
    assert run.decision in ("CANDIDATE_APPROVED", "CANDIDATE_REJECTED")
    assert run.candidate_model_version is not None
    assert len(run.gate_results) == 7
    gate_names = [g["gate"] for g in run.gate_results]
    assert gate_names == [
        "G1_DATA_QUALITY",
        "G2_TRAINING_VALIDITY",
        "G3_PREDICTION_SANITY",
        "G4_PREDICTIVE_QUALITY",
        "G5_FINANCIAL_PERFORMANCE",
        "G6_ROBUSTNESS",
        "G7_OPERATIONAL_HEALTH",
    ]
    # Run record persisted with full audit trail
    record_path = tmp_path / "retraining" / f"{run.retraining_run_id}.json"
    assert record_path.exists()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["decision"] == run.decision
    assert record["fingerprint"] == run.fingerprint


def test_candidate_version_uses_new_artifact(retrain_config, tmp_path):
    engine = RetrainingEngine(retrain_config, retraining_dir=tmp_path / "retraining")
    run = engine.evaluate_trigger(trigger_type="manual", trigger_reason="artifact-test")
    assert run.status in ("APPROVED", "REJECTED")
    candidate_dir = retrain_config.model.artifact_dir / run.candidate_model_version
    assert (candidate_dir / "model.joblib").exists()
    assert (candidate_dir / "metadata.json").exists()


# ---------------------------------------------------------------------------
# CRITICAL SAFETY TEST (section 41 — mandatory)
# ---------------------------------------------------------------------------
def test_training_failure_cannot_change_current_model(retrain_config, tmp_path, monkeypatch):
    engine = RetrainingEngine(retrain_config, retraining_dir=tmp_path / "retraining")
    before = engine._latest_model_version()
    assert before is not None

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated training crash")

    monkeypatch.setattr("src.model.trainer.BaselineTrainer.run", _boom)
    run = engine.evaluate_trigger(trigger_type="manual", trigger_reason="failure-test")
    assert run.status == "FAILED"
    # Current model unchanged and still loadable
    after = engine._latest_model_version()
    assert after == before
    from src.api.resolver import load_model

    model = load_model(retrain_config, before)
    assert model.model_version == before


def test_rejection_cannot_change_current_model(retrain_config, tmp_path):
    """Even when a candidate is REJECTED, the current model is untouched."""
    engine = RetrainingEngine(retrain_config, retraining_dir=tmp_path / "retraining")
    before = engine._latest_model_version()
    run = engine.evaluate_trigger(
        trigger_type="manual",
        trigger_reason="rejection-test",
    )
    # Whether approved or rejected, the previous model artifact still exists
    # and loads; no artifact was deleted or overwritten.
    assert run.candidate_model_version != before
    from src.api.resolver import load_model

    model = load_model(retrain_config, before)
    assert model.model_version == before


# ---------------------------------------------------------------------------
# Run record / state machine (section 36)
# ---------------------------------------------------------------------------
def test_run_states_are_explicit(retrain_config, tmp_path):
    engine = RetrainingEngine(retrain_config, retraining_dir=tmp_path / "retraining")
    run = engine.evaluate_trigger(trigger_type="manual", trigger_reason="states")
    assert run.status in ("APPROVED", "REJECTED", "SKIPPED", "FAILED")
    if run.status == "SKIPPED":
        assert run.decision is None
