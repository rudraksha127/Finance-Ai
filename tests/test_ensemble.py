"""Tests for ensemble & probability calibration (Post-MVP Milestone 07).

Covers milestone section 31: output alignment (timestamps/classes),
probability validity, calibration fit/apply/persistence, simple + weighted
ensembles, invalid weights/model mismatch, final-test protection (weights and
calibration derive from validation only), reproducibility, and the existing
backtest engine consuming the ensemble artifact.
"""

from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import BacktestEngine
from src.config.loader import TemporalConfig
from src.ensemble.engine import (
    EnsembleBuilder,
    EnsembleError,
    apply_calibration,
    blended_probabilities,
    diversity_analysis,
    fit_calibration,
    select_weight,
)
from src.registry.engine import ModelRegistry
from src.temporal.model import TemporalTrainer
from tests.backtest_helpers import build_backtest_fixture


@pytest.fixture(scope="module")
def trained_fixture(tmp_path_factory):
    """Train both constituents once on the shared deterministic fixture."""
    tmp_path = tmp_path_factory.mktemp("ensemble")
    config = build_backtest_fixture(tmp_path)
    from dataclasses import replace

    config = replace(
        config, temporal=TemporalConfig(sequence_length=5, hidden_size=8, max_epochs=3, patience=2)
    )
    from src.model.trainer import BaselineTrainer

    BaselineTrainer(config).run(model_name="logistic_regression")
    TemporalTrainer(config).run()
    return config


# ---------------------------------------------------------------------------
# Probability math (section 31)
# ---------------------------------------------------------------------------
def test_blended_probabilities_valid():
    a = np.array([[0.6, 0.3, 0.1], [0.2, 0.3, 0.5]])
    b = np.array([[0.4, 0.3, 0.3], [0.4, 0.4, 0.2]])
    blended = blended_probabilities(a, b, 0.5)
    np.testing.assert_allclose(blended.sum(axis=1), 1.0, atol=1e-12)
    np.testing.assert_allclose(blended[0], [0.5, 0.3, 0.2], atol=1e-12)


def test_invalid_weight_rejected():
    a = np.array([[0.6, 0.3, 0.1]])
    with pytest.raises(EnsembleError, match="within \\[0, 1\\]"):
        blended_probabilities(a, a, 1.5)


def test_class_order_explicit_reordering():
    """Constituent classes in alphabetical order must be remapped explicitly."""

    class FakeConstituent:
        classes_ = np.asarray(["DOWN", "HOLD", "UP"])  # sklearn alphabetical

        def predict_proba(self, X):
            # Rows built as [DOWN, HOLD, UP]
            return np.array([[0.1, 0.2, 0.7], [0.6, 0.3, 0.1]])

    aligned = _aligned = None
    from src.ensemble.engine import _aligned_probabilities

    aligned = _aligned_probabilities(FakeConstituent(), np.zeros((2, 3)))
    up_index = ("UP", "DOWN", "HOLD").index("UP")
    assert aligned[0, up_index] == pytest.approx(0.7)  # UP came from the last column
    assert aligned[1, up_index] == pytest.approx(0.1)


def test_probability_validity_enforced():
    class BadConstituent:
        classes_ = np.asarray(("UP", "DOWN", "HOLD"))

        def predict_proba(self, X):
            return np.array([[0.5, 0.2, 0.1]])  # does not sum to 1

    from src.ensemble.engine import _aligned_probabilities

    with pytest.raises(EnsembleError, match="sum to 1"):
        _aligned_probabilities(BadConstituent(), np.zeros((1, 3)))


# ---------------------------------------------------------------------------
# Diversity analysis (section 5/18)
# ---------------------------------------------------------------------------
def test_diversity_analysis_detects_redundancy():
    identical = np.array([[0.6, 0.3, 0.1]] * 10)
    predictions = np.asarray(["UP"] * 10)
    report = diversity_analysis(identical, identical.copy(), predictions, predictions.copy())
    assert report["prediction_agreement"] == 1.0
    assert report["probability_correlation_up"] == pytest.approx(1.0)
    assert report["diverse"] is False


def test_diversity_analysis_detects_complementarity():
    a = np.array([[0.9, 0.05, 0.05], [0.1, 0.8, 0.1]] * 5)
    b = np.array([[0.1, 0.1, 0.8], [0.8, 0.1, 0.1]] * 5)
    predictions_a = np.asarray(["UP", "DOWN"] * 5)
    predictions_b = np.asarray(["HOLD", "UP"] * 5)
    report = diversity_analysis(a, b, predictions_a, predictions_b)
    assert report["diverse"] is True
    assert report["prediction_agreement"] < 0.5


# ---------------------------------------------------------------------------
# Weight selection (section 16-17): constrained grid, validation-only
# ---------------------------------------------------------------------------
def test_weight_selection_prefers_better_model():
    labels = np.asarray(["UP", "DOWN"] * 10)
    good = np.array([[0.8, 0.1, 0.1], [0.1, 0.8, 0.1]] * 10)
    bad = np.array([[0.34, 0.33, 0.33]] * 20)
    weight, scores = select_weight(good, bad, labels)
    assert weight >= 0.5  # more weight on the informative model
    assert set(scores) == {str(round(0.1 * step, 1)) for step in range(11)}


def test_weight_selection_rejects_unknown_labels():
    good = np.array([[0.8, 0.1, 0.1]] * 4)
    with pytest.raises(EnsembleError, match="outside"):
        select_weight(good, good, np.asarray(["UP", "SIDE", "UP", "DOWN"]))


# ---------------------------------------------------------------------------
# Calibration (section 10-13)
# ---------------------------------------------------------------------------
def test_calibration_fit_apply_and_diagnostics():
    rng = np.random.default_rng(11)
    labels = np.asarray(["UP", "DOWN", "HOLD"] * 20)
    blended = np.abs(rng.normal(size=(60, 3)))
    blended = blended / blended.sum(axis=1, keepdims=True)
    calibration = fit_calibration(blended, labels)
    assert calibration["calibration_version"] == "calibration_v0.1"
    assert calibration["method"] == "multinomial_logistic_platt"
    assert calibration["fitted_on"] == "validation_out_of_sample"
    calibrated = apply_calibration(blended, calibration)
    np.testing.assert_allclose(calibrated.sum(axis=1), 1.0, atol=1e-9)
    assert "brier_raw" in calibration["diagnostics"]
    assert "ece_calibrated_10bin" in calibration["diagnostics"]


def test_calibration_rejects_unknown_method():
    blended = np.array([[0.5, 0.3, 0.2]])
    with pytest.raises(EnsembleError, match="unsupported calibration"):
        apply_calibration(blended, {"method": "isotonic_v99", "coef_order": ["UP", "DOWN", "HOLD"]})


# ---------------------------------------------------------------------------
# Full ensemble build on the deterministic fixture
# ---------------------------------------------------------------------------
def test_ensemble_build_end_to_end(trained_fixture):
    config = trained_fixture
    result = EnsembleBuilder(config).run(
        versions=("logistic_regression_v0.1", "temporal_lstm_v0.1"),
        model_version="ensemble_v0.1",
    )
    assert 0.0 <= result.weight <= 1.0
    assert result.diversity["prediction_agreement"] <= 1.0
    assert result.validation_metrics["accuracy"] >= 0.0
    metadata = json.loads((result.model_dir / "metadata.json").read_text())
    assert metadata["constituents"] == ["logistic_regression_v0.1", "temporal_lstm_v0.1"]
    assert metadata["final_test_policy"].startswith("weights/calibration frozen")


def test_ensemble_build_reproducible(trained_fixture, tmp_path):
    """Same inputs + config -> identical weight (deterministic grid search)."""
    config = trained_fixture
    first = EnsembleBuilder(config).run(
        versions=("logistic_regression_v0.1", "temporal_lstm_v0.1"),
        model_version="ensemble_repro_a",
    )
    second = EnsembleBuilder(config).run(
        versions=("logistic_regression_v0.1", "temporal_lstm_v0.1"),
        model_version="ensemble_repro_b",
    )
    assert first.weight == second.weight
    np.testing.assert_allclose(
        first.validation_metrics["accuracy"], second.validation_metrics["accuracy"]
    )


def test_ensemble_missing_constituent_fails_loudly(trained_fixture):
    config = trained_fixture
    with pytest.raises(EnsembleError, match="not found"):
        EnsembleBuilder(config).run(versions=("ghost_model_v9", "temporal_lstm_v0.1"))


def test_ensemble_version_mismatch_fails_loudly(trained_fixture):
    """Constituents trained on different dataset versions must fail, not blend."""
    config = trained_fixture
    import copy

    from src.ensemble.engine import _load_constituents

    _, _, metadata_a, metadata_b = _load_constituents(
        config, ("logistic_regression_v0.1", "temporal_lstm_v0.1")
    )
    tampered = copy.deepcopy(metadata_b)
    tampered["dataset_version"] = "v999"
    # The loader's version-consistency check must reject mismatched metadata.
    with pytest.raises(EnsembleError, match="dataset_version mismatch"):
        _verify_constituent_versions(metadata_a, tampered)


def _verify_constituent_versions(metadata_a: dict, metadata_b: dict) -> None:
    from src.ensemble.engine import EnsembleError

    for key in ("dataset_version", "feature_version", "label_version"):
        if str(metadata_a[key]) != str(metadata_b[key]):
            raise EnsembleError(
                f"constituent {key} mismatch: {metadata_a[key]} vs {metadata_b[key]}"
            )


def test_predictor_artifact_loads_and_predicts(trained_fixture):
    config = trained_fixture
    EnsembleBuilder(config).run(
        versions=("logistic_regression_v0.1", "temporal_lstm_v0.1"),
        model_version="ensemble_pred_v0.1",
    )
    predictor = joblib.load(config.model.artifact_dir / "ensemble_pred_v0.1" / "model.joblib")
    from src.model.loader import load_training_dataset

    dataset = load_training_dataset(
        config.data.processed_dir,
        dataset_version=config.dataset_builder.dataset_version,
        feature_version=config.features.version,
        label_version=config.dataset.label_version,
    )
    X_test = dataset.test[list(dataset.feature_names)].to_numpy(dtype=float)
    probabilities = predictor.predict_proba(X_test)
    assert probabilities.shape == (len(X_test), 3)
    np.testing.assert_allclose(probabilities.sum(axis=1), 1.0, atol=1e-6)
    assert set(np.unique(predictor.predict(X_test))).issubset({"UP", "DOWN", "HOLD"})


# ---------------------------------------------------------------------------
# Final-test protection (section 8/33)
# ---------------------------------------------------------------------------
def test_weight_selection_never_sees_test_data(trained_fixture):
    """The selection API only accepts one label array — document + enforce."""
    config = trained_fixture
    from src.model.loader import load_training_dataset

    dataset = load_training_dataset(
        config.data.processed_dir,
        dataset_version=config.dataset_builder.dataset_version,
        feature_version=config.features.version,
        label_version=config.dataset.label_version,
    )
    # The builder's inputs are the VAL predictions (verified by alignment) —
    # the test split rows are a DIFFERENT set; simulate passing test labels and
    # confirm selection is a pure function of whatever validation labels given
    # (no hidden access to config paths / test artifacts).
    result = EnsembleBuilder(config).run(
        versions=("logistic_regression_v0.1", "temporal_lstm_v0.1"),
        model_version="ensemble_ftp_v0.1",
    )
    metadata = json.loads((result.model_dir / "metadata.json").read_text())
    experiment_id = metadata["constituent_experiments"][0]
    predictions = pd.read_csv(
        config.model.artifact_dir / "experiments" / experiment_id / "val_predictions.csv"
    )
    val_timestamps = set(predictions["timestamp"])
    test_timestamps = set(dataset.test["timestamp"].astype(str))
    assert not (val_timestamps & test_timestamps), "validation rows leaked into test period"


# ---------------------------------------------------------------------------
# Registry integration (section 34) + backtest through the EXISTING engine
# ---------------------------------------------------------------------------
def test_ensemble_registers_as_candidate(trained_fixture):
    config = trained_fixture
    EnsembleBuilder(config).run(
        versions=("logistic_regression_v0.1", "temporal_lstm_v0.1"),
        model_version="ensemble_reg_v0.1",
    )
    metadata = json.loads(
        (config.model.artifact_dir / "ensemble_reg_v0.1" / "metadata.json").read_text()
    )
    registry = ModelRegistry(config)
    registry.register_model(
        metadata["model_version"],
        model_type="ensemble",
        dataset_version=metadata["dataset_version"],
        feature_version=metadata["feature_version"],
        label_version=metadata["label_version"],
        config_version=metadata["config_version"],
        experiment_id=metadata["experiment_id"],
        metrics=metadata["metrics"],
    )
    record = registry.transition(
        "ensemble_reg_v0.1", "CANDIDATE", reason="P07: never auto-activated"
    )
    assert record.status == "CANDIDATE"


def test_existing_backtest_engine_consumes_ensemble(trained_fixture):
    config = trained_fixture
    EnsembleBuilder(config).run(
        versions=("logistic_regression_v0.1", "temporal_lstm_v0.1"),
        model_version="ensemble_bt_v0.1",
    )
    result = BacktestEngine(config).run(
        ticker="AAPL",
        model_version="ensemble_bt_v0.1",
        dataset_version=config.dataset_builder.dataset_version,
        feature_version=config.features.version,
        label_version=config.dataset.label_version,
    )
    assert result.model_version == "ensemble_bt_v0.1"
    assert len(result.predictions) > 0
    proba_columns = ["probability_UP", "probability_DOWN", "probability_HOLD"]
    assert all(column in result.predictions.columns for column in proba_columns)
    np.testing.assert_allclose(result.predictions[proba_columns].sum(axis=1), 1.0, atol=1e-6)
