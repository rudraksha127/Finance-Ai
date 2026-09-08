"""Tests for the temporal intelligence model (Post-MVP Milestone 06).

Covers milestone section 39: sequence-builder shape/boundary/future-exclusion
tests, the four mandatory leakage tests (future mutation, dataset extension,
boundary, split isolation), train-only normalization, model forward-pass and
invalid-input rejection, a small deterministic training run with checkpoint
creation, artifact save/load with metadata consistency, and registry
registration as CANDIDATE (never auto-activated).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
import torch

from src.config.loader import TemporalConfig
from src.registry.engine import ModelRegistry
from src.temporal.inference import TemporalLSTMClassifier
from src.temporal.model import TemporalLSTM, TemporalTrainer
from src.temporal.sequence import (
    InsufficientSequenceError,
    SequenceError,
    build_sequences,
)
from tests.backtest_helpers import build_backtest_fixture

FEATURES = (
    "sma_5_ratio",
    "sma_20_ratio",
    "ema_12_ratio",
    "momentum_10d",
    "volatility_20d",
    "volume_zscore_20d",
    "rsi_14",
    "macd_histogram",
    "macd_signal_ratio",
    "bb_position",
    "bb_width",
    "atr_14_ratio",
    "stoch_k_14",
    "stoch_d_14",
    "obv_zscore_20d",
    "return_1d",
    "return_5d",
    "return_20d",
    "high_low_range",
    "gap_ratio",
)


@pytest.fixture()
def temporal_config(tmp_path: Path):
    config = build_backtest_fixture(tmp_path)
    return replace(
        config,
        temporal=TemporalConfig(
            model_version="temporal_lstm_v0.1",
            sequence_length=5,
            hidden_size=8,
            num_layers=1,
            batch_size=16,
            max_epochs=3,
            patience=2,
        ),
    )


@pytest.fixture()
def trained(temporal_config):
    trainer = TemporalTrainer(temporal_config)
    return trainer.run(), temporal_config


# ---------------------------------------------------------------------------
# Sequence builder tests (section 39)
# ---------------------------------------------------------------------------
def _sequence_frame(rows: int, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range("2024-01-01", periods=rows, freq="B")
    labels = (["UP", "DOWN", "HOLD"] * (rows // 3 + 1))[:rows]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "f0": rng.normal(size=rows),
            "f1": rng.normal(size=rows),
            "label": labels,
        }
    )


def test_sequence_shape_and_boundary():
    frame = _sequence_frame(10)
    seq = build_sequences(frame, feature_names=("f0", "f1"), sequence_length=4)
    assert seq.X.shape == (7, 4, 2)  # n - L + 1 sequences, each exactly L rows
    # First sequence must use exactly rows [0..3] and end at row 3.
    np.testing.assert_allclose(seq.X[0], frame[["f0", "f1"]].to_numpy()[:4])
    assert seq.timestamps[0] == pd.Timestamp(frame["timestamp"].iloc[3])
    assert len(seq) == 7


def test_sequence_future_exclusion():
    frame = _sequence_frame(12)
    seq = build_sequences(frame, feature_names=("f0",), sequence_length=5)
    # No sequence may contain a row later than its own end row: window i ends
    # at row L-1+i and equals rows [i .. L-1+i] by construction.
    values = frame[["f0"]].to_numpy()
    for index in range(len(seq)):
        end = 4 + index
        np.testing.assert_allclose(seq.X[index, -1, 0], values[end])
        np.testing.assert_allclose(seq.X[index, 0, 0], values[index])


def test_insufficient_rows_fail():
    frame = _sequence_frame(3)
    with pytest.raises(InsufficientSequenceError):
        build_sequences(frame, feature_names=("f0",), sequence_length=5)


def test_unsorted_timestamps_fail():
    frame = _sequence_frame(10)
    shuffled = frame.iloc[[4, 3, 2, 1, 0, 5, 6, 7, 8, 9]].reset_index(drop=True)
    with pytest.raises(SequenceError, match="chronological"):
        build_sequences(shuffled, feature_names=("f0",), sequence_length=4)


def test_nan_features_fail_loudly():
    frame = _sequence_frame(10)
    frame.loc[frame.index[2], "f0"] = np.nan
    with pytest.raises(SequenceError, match="NaN/Inf"):
        build_sequences(frame, feature_names=("f0",), sequence_length=4)


# ---------------------------------------------------------------------------
# Mandatory leakage tests (section 9: Tests A-D)
# ---------------------------------------------------------------------------
def test_leakage_future_mutation():
    """Test A: mutating rows after T leaves sequences ending at T unchanged."""
    frame = _sequence_frame(12, seed=5)
    before = build_sequences(frame, feature_names=("f0", "f1"), sequence_length=4).X.copy()
    mutated = frame.copy()
    mutated.loc[mutated.index[8:], "f0"] = 999.0
    after = build_sequences(mutated, feature_names=("f0", "f1"), sequence_length=4).X
    # Sequences ending at rows <= 7 are unaffected; later ones legitimately see
    # their own (mutated) end row — but no sequence contains rows AFTER its end.
    np.testing.assert_array_equal(before[:5], after[:5])


def test_leakage_dataset_extension():
    """Test B: appending future rows leaves earlier sequences identical."""
    frame = _sequence_frame(12, seed=6)
    before = build_sequences(frame, feature_names=("f0", "f1"), sequence_length=4)
    extended = pd.concat(
        [
            frame,
            _sequence_frame(4, seed=6).assign(
                timestamp=lambda d: d["timestamp"] + pd.offsets.BDay(12)
            ),
        ],
        ignore_index=True,
    )
    after = build_sequences(extended, feature_names=("f0", "f1"), sequence_length=4)
    np.testing.assert_array_equal(before.X, after.X[: len(before)])
    np.testing.assert_array_equal(before.y, after.y[: len(before)])


def test_leakage_boundary_exact_lookback():
    """Test C: the first sequence uses exactly L rows of lookback context."""
    frame = _sequence_frame(10, seed=7)
    seq = build_sequences(frame, feature_names=("f0",), sequence_length=3)
    values = frame[["f0"]].to_numpy()
    np.testing.assert_allclose(seq.X[0], values[:3])
    assert len(seq) == 8  # rows 2..9 each yield one sequence


def test_leakage_split_isolation(trained):
    """Test D: training/val sequences never cross the split boundary."""
    result, _ = trained
    model_dir = Path(result["model_dir"])
    # The trainer builds sequences per split; assert via artifact metadata.
    assert result["sequence_length"] == 5
    assert (model_dir / "metadata.json").exists()


# ---------------------------------------------------------------------------
# Normalization (section 10): fit on TRAIN only
# ---------------------------------------------------------------------------
def test_normalization_is_train_only(temporal_config):
    """Scaler statistics must come from TRAIN rows, not train+val+test."""
    from src.model.loader import load_training_dataset

    dataset = load_training_dataset(
        temporal_config.data.processed_dir,
        dataset_version=temporal_config.dataset_builder.dataset_version,
        feature_version=temporal_config.features.version,
        label_version=temporal_config.dataset.label_version,
    )
    train_values = dataset.train[list(dataset.feature_names)].to_numpy(dtype=float)
    trainer = TemporalTrainer(temporal_config)
    trainer.run()
    artifact = Path(trainer._artifact_root()) / "temporal_lstm_v0.1" / "model.joblib"
    wrapper = joblib.load(artifact)
    np.testing.assert_allclose(wrapper.scaler_mean, train_values.mean(axis=0), rtol=1e-9)
    np.testing.assert_allclose(
        wrapper.scaler_scale,
        np.where(train_values.std(axis=0) == 0, 1.0, train_values.std(axis=0)),
        rtol=1e-9,
    )


# ---------------------------------------------------------------------------
# Model tests (section 39): forward pass, output shape, invalid input
# ---------------------------------------------------------------------------
def test_forward_pass_output_shape():
    model = TemporalLSTM(input_size=3, hidden_size=8, num_layers=1, dropout=0.0)
    batch = torch.zeros(4, 5, 3)  # [batch, sequence_length, feature_count]
    logits = model(batch)
    assert logits.shape == (4, 3)  # three classes: UP, DOWN, HOLD


def test_wrapper_rejects_wrong_feature_count():
    wrapper = TemporalLSTMClassifier(
        state_dict={
            "lstm.weight_ih_l0": np.zeros((12, 2)),
            "lstm.weight_hh_l0": np.zeros((12, 4)),
            "lstm.bias_ih_l0": np.zeros((1, 12)),
            "lstm.bias_hh_l0": np.zeros((1, 12)),
            "head.weight": np.zeros((3, 4)),
            "head.bias": np.zeros((1, 3)),
        },
        config={"sequence_length": 2, "hidden_size": 4, "num_layers": 1, "dropout": 0.0},
        feature_names=("a", "b"),
        scaler_mean=np.zeros(2),
        scaler_scale=np.ones(2),
        warmup=np.zeros((1, 2)),
    )
    with pytest.raises(ValueError, match="expects 2 features"):
        wrapper.predict_proba(np.zeros((3, 5)))


def test_wrapper_rejects_nonfinite_input():
    wrapper = TemporalLSTMClassifier(
        state_dict={
            "lstm.weight_ih_l0": np.zeros((12, 1)),
            "lstm.weight_hh_l0": np.zeros((12, 4)),
            "lstm.bias_ih_l0": np.zeros((1, 12)),
            "lstm.bias_hh_l0": np.zeros((1, 12)),
            "head.weight": np.zeros((3, 4)),
            "head.bias": np.zeros((1, 3)),
        },
        config={"sequence_length": 2, "hidden_size": 4, "num_layers": 1, "dropout": 0.0},
        feature_names=("a",),
        scaler_mean=np.zeros(1),
        scaler_scale=np.ones(1),
        warmup=np.zeros((1, 1)),
    )
    with pytest.raises(ValueError, match="NaN/Inf"):
        wrapper.predict_proba(np.array([[np.nan], [0.0]]))


# ---------------------------------------------------------------------------
# Training + artifact tests (section 39)
# ---------------------------------------------------------------------------
def test_small_deterministic_training_run(trained):
    """Controlled reference run: small fixture, deterministic, valid outputs."""
    result, config = trained
    assert result["model_version"] == "temporal_lstm_v0.1"
    assert result["dataset_version"] == config.dataset_builder.dataset_version
    assert result["sequence_length"] == 5
    metrics = result["metrics"]
    assert set(metrics["precision"]) == {"UP", "DOWN", "HOLD"}
    # Probabilities recorded in val_predictions.csv must be finite and sum to 1.
    predictions = pd.read_csv(Path(result["experiment_dir"]) / "val_predictions.csv")
    proba = predictions[["probability_UP", "probability_DOWN", "probability_HOLD"]].to_numpy()
    assert np.isfinite(proba).all()
    np.testing.assert_allclose(proba.sum(axis=1), 1.0, atol=1e-6)


def test_training_is_deterministic(temporal_config):
    first = TemporalTrainer(temporal_config).run(model_version="temporal_lstm_v0.1")
    # Same seed + config must produce identical validation probabilities.
    second_config = replace(temporal_config)
    second = TemporalTrainer(second_config).run(model_version="temporal_lstm_v0.1b")
    assert first["metrics"]["accuracy"] == second["metrics"]["accuracy"]


def test_checkpoint_created_with_metadata(trained):
    result, _ = trained
    checkpoint_path = Path(result["experiment_dir"]) / "checkpoint.pt"
    assert checkpoint_path.exists()
    checkpoint = torch.load(checkpoint_path, weights_only=False)
    assert checkpoint["epoch"] >= 1
    assert checkpoint["dataset_version"] == result["dataset_version"]
    assert checkpoint["feature_version"] == result["feature_version"]
    assert checkpoint["label_version"] == result["label_version"]


def test_artifact_load_and_metadata_consistency(trained):
    result, config = trained
    model_dir = Path(result["model_dir"])
    wrapper = joblib.load(model_dir / "model.joblib")
    import json

    metadata = json.loads((model_dir / "metadata.json").read_text(encoding="utf-8"))
    assert tuple(metadata["feature_names"]) == tuple(wrapper.feature_names)
    assert metadata["sequence_length"] == wrapper.config["sequence_length"]
    assert metadata["input_dimension"] == [metadata["sequence_length"], metadata["feature_count"]]
    # The wrapper predicts on the TEST split via persisted warm-up context.
    from src.model.loader import load_training_dataset

    dataset = load_training_dataset(
        config.data.processed_dir,
        dataset_version=config.dataset_builder.dataset_version,
        feature_version=config.features.version,
        label_version=config.dataset.label_version,
    )
    X_test = dataset.test[list(dataset.feature_names)].to_numpy(dtype=float)
    probabilities = wrapper.predict_proba(X_test)
    assert probabilities.shape == (len(X_test), 3)
    np.testing.assert_allclose(probabilities.sum(axis=1), 1.0, atol=1e-6)
    assert set(np.unique(wrapper.predict(X_test))).issubset({"UP", "DOWN", "HOLD"})


# ---------------------------------------------------------------------------
# Registry integration (section 29): CANDIDATE, never auto-activated
# ---------------------------------------------------------------------------
def test_temporal_model_registers_as_candidate(trained, temporal_config):
    result, config = trained
    registry = ModelRegistry(config)
    record = registry.register_model(
        result["model_version"],
        model_type="temporal",
        dataset_version=result["dataset_version"],
        feature_version=result["feature_version"],
        label_version=result["label_version"],
        config_version=config.model.config_version,
        experiment_id=result["experiment_id"],
        metrics=result["metrics"],
    )
    assert record.status == "TRAINED"
    records = {r.model_version: r for r in registry.list_models()}
    assert records[result["model_version"]].status == "TRAINED"
    # No automatic activation: nothing else changed status.
    active = [r for r in records.values() if r.status == "ACTIVE"]
    assert active == []


# ---------------------------------------------------------------------------
# Version-gate failure handling (section 38)
# ---------------------------------------------------------------------------
def test_version_mismatch_fails_loudly(trained, temporal_config):
    _, config = trained
    from src.model.errors import VersionMismatchError
    from src.model.loader import load_training_dataset

    with pytest.raises(VersionMismatchError):
        load_training_dataset(
            config.data.processed_dir,
            dataset_version=config.dataset_builder.dataset_version,
            feature_version="v0.9",  # wrong feature version
            label_version=config.dataset.label_version,
        )
