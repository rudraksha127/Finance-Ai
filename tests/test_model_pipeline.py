"""Controlled tests for baseline training, artifacts, and leakage boundaries."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from src.dataset.metadata import DatasetManifest, DatasetMetadata, compute_dataset_version_hash
from src.dataset.storage import sha256_of, write_dataset
from src.features.registry import FEATURE_COLUMNS
from src.model.errors import (
    InvalidFeaturesError,
    InvalidTargetError,
    SchemaMismatchError,
    VersionMismatchError,
)
from src.model.loader import CLASSES as CLASSES_ORDER
from src.model.loader import NON_FEATURE_COLUMNS, _validate_frame, load_training_dataset
from src.model.trainer import BaselineTrainer
from tests.data_helpers import make_app_config


def _frame(start: str, rows: int) -> pd.DataFrame:
    timestamps = pd.date_range(start, periods=rows, freq="B")
    frame = pd.DataFrame(
        {
            "ticker": ["AAPL"] * rows,
            "timestamp": timestamps,
            **{name: [float(index + 1) for index in range(rows)] for name in FEATURE_COLUMNS},
            "label": (["UP", "DOWN", "HOLD"] * rows)[:rows],
            "future_return": ([0.01, -0.01, 0.0] * rows)[:rows],
            "target_timestamp": timestamps + pd.Timedelta(days=5),
            "dataset_version": ["v0.1"] * rows,
            "feature_set_version": ["v0.1"] * rows,
            "label_set_version": ["v0.1"] * rows,
            "source_data_version": ["source123456"] * rows,
        }
    )
    return frame


def _write_dataset(tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    train = _frame("2025-01-02", 30)
    val = _frame("2025-03-01", 15)
    test = _frame("2025-04-01", 15)
    config_snapshot = {
        "dataset_version": "v0.1",
        "feature_version": "v0.1",
        "label_version": "v0.1",
    }
    boundaries = {
        "train_start": train["timestamp"].min().isoformat(),
        "train_end": train["timestamp"].max().isoformat(),
        "val_start": val["timestamp"].min().isoformat(),
        "val_end": val["timestamp"].max().isoformat(),
        "test_start": test["timestamp"].min().isoformat(),
        "test_end": test["timestamp"].max().isoformat(),
    }
    version_hash = compute_dataset_version_hash(
        feature_version="v0.1",
        label_version="v0.1",
        source_versions={"AAPL": "source123456"},
        config=config_snapshot,
        feature_names=FEATURE_COLUMNS,
        split_boundaries=boundaries,
        record_counts={"input_rows": 60, "total_rows": 60, "train": 30, "val": 15, "test": 15},
    )
    metadata = DatasetMetadata(
        version="v0.1",
        version_hash=version_hash,
        feature_version="v0.1",
        label_version="v0.1",
        source_versions={"AAPL": "source123456"},
        created_at="2026-01-01T00:00:00",
        created_by="test",
        config_snapshot=config_snapshot,
        feature_names=FEATURE_COLUMNS,
        feature_count=len(FEATURE_COLUMNS),
        total_rows=60,
        train_rows=30,
        val_rows=15,
        test_rows=15,
        **boundaries,
        nan_count_total=0,
        label_distribution={"UP": 20, "DOWN": 20, "HOLD": 20},
        quality_score=100.0,
        quality_rating="excellent",
        input_rows=60,
        dropped_warmup=0,
        dropped_invalid_label=0,
        dropped_out_of_range=0,
    )
    manifest = DatasetManifest(
        dataset_version="v0.1",
        version_hash=version_hash,
        source_versions={"AAPL": "source123456"},
        feature_version="v0.1",
        label_version="v0.1",
        generation_time="2026-01-01T00:00:00",
        generation_code_version="test",
        row_counts={"input": 60, "final": 60},
        instruments=["AAPL"],
        intervals=["1d"],
        date_range={
            "actual_start": boundaries["train_start"],
            "actual_end": boundaries["test_end"],
        },
        split_boundaries=boundaries,
        split_row_counts={"train": 30, "val": 15, "test": 15},
        feature_count=len(FEATURE_COLUMNS),
        target_definition={"target_type": "classification"},
        quality_summary={"score": 100.0},
        build_report={"input_rows": 60, "invalid_rows": 0},
    )
    write_dataset(
        processed,
        version="v0.1",
        metadata=metadata,
        manifest=manifest,
        feature_names=FEATURE_COLUMNS,
        train=train,
        val=val,
        test=test,
    )


@pytest.fixture()
def training_config(tmp_path: Path):
    config = make_app_config(tmp_path / "raw")
    _write_dataset(tmp_path)
    return replace(
        config,
        model=replace(config.model, artifact_dir=tmp_path / "models"),
    )


def test_loader_validates_versions_and_feature_contract(training_config):
    loaded = load_training_dataset(
        training_config.data.processed_dir,
        dataset_version="v0.1",
        feature_version="v0.1",
        label_version="v0.1",
    )
    assert loaded.feature_names == FEATURE_COLUMNS
    assert list(loaded.train[list(FEATURE_COLUMNS)].columns) == list(FEATURE_COLUMNS)
    with pytest.raises(VersionMismatchError):
        load_training_dataset(
            training_config.data.processed_dir,
            dataset_version="v0.1",
            feature_version="v9.9",
            label_version="v0.1",
        )


def test_logistic_training_persists_artifacts_and_validation_predictions(training_config):
    result = BaselineTrainer(training_config).run(
        model_name="logistic_regression",
        model_version="baseline_logistic_regression_test",
        experiment_id="exp_test_logistic",
    )
    assert result.metrics["accuracy"] >= 0.0
    assert (result.experiment_dir / "model.joblib").exists()
    assert (result.experiment_dir / "scaler.joblib").exists()
    assert (result.experiment_dir / "val_predictions.csv").exists()
    assert (result.experiment_dir / "feature_importance.csv").exists()
    metadata = json.loads((result.experiment_dir / "metadata.json").read_text())
    assert metadata["test_rows"] == 15
    assert metadata["dataset_version"] == "v0.1"


def test_random_forest_training_is_reproducible_and_does_not_use_test_rows(training_config):
    first = BaselineTrainer(training_config).run(
        model_name="random_forest",
        model_version="baseline_random_forest_test_a",
        experiment_id="exp_test_rf_a",
    )
    second = BaselineTrainer(training_config).run(
        model_name="random_forest",
        model_version="baseline_random_forest_test_b",
        experiment_id="exp_test_rf_b",
    )
    assert first.metrics == second.metrics
    predictions = pd.read_csv(first.experiment_dir / "val_predictions.csv")
    test = pd.read_parquet(
        training_config.data.processed_dir / "datasets" / "dataset_v0.1" / "test.parquet"
    )
    assert set(predictions["timestamp"]).isdisjoint(set(test["timestamp"].astype(str)))
    assert not (first.experiment_dir / "scaler.joblib").exists()


def test_lightgbm_training_persists_artifacts_and_validation_predictions(training_config):
    result = BaselineTrainer(training_config).run(
        model_name="lightgbm",
        model_version="baseline_lightgbm_test",
        experiment_id="exp_test_lgb",
    )
    assert result.metrics["accuracy"] >= 0.0
    assert (result.experiment_dir / "model.joblib").exists()
    assert not (result.experiment_dir / "scaler.joblib").exists()
    assert (result.experiment_dir / "val_predictions.csv").exists()
    assert (result.experiment_dir / "feature_importance.csv").exists()
    predictions = pd.read_csv(result.experiment_dir / "val_predictions.csv")
    assert set(predictions["prediction"]).issubset({"UP", "DOWN", "HOLD"})
    prob_cols = [f"probability_{label}" for label in ("UP", "DOWN", "HOLD")]
    assert np.allclose(predictions[prob_cols].sum(axis=1), 1.0)
    metadata = json.loads((result.experiment_dir / "metadata.json").read_text())
    assert metadata["test_rows"] == 15
    assert metadata["dataset_version"] == "v0.1"


def test_lightgbm_training_is_reproducible_and_does_not_use_test_rows(training_config):
    first = BaselineTrainer(training_config).run(
        model_name="lightgbm",
        model_version="baseline_lightgbm_test_a",
        experiment_id="exp_test_lgb_a",
    )
    second = BaselineTrainer(training_config).run(
        model_name="lightgbm",
        model_version="baseline_lightgbm_test_b",
        experiment_id="exp_test_lgb_b",
    )
    assert first.metrics == second.metrics
    predictions = pd.read_csv(first.experiment_dir / "val_predictions.csv")
    test = pd.read_parquet(
        training_config.data.processed_dir / "datasets" / "dataset_v0.1" / "test.parquet"
    )
    assert set(predictions["timestamp"]).isdisjoint(set(test["timestamp"].astype(str)))


def test_xgboost_training_persists_artifacts_and_validation_predictions(training_config):
    result = BaselineTrainer(training_config).run(
        model_name="xgboost",
        model_version="baseline_xgboost_test",
        experiment_id="exp_test_xgb",
    )
    assert result.metrics["accuracy"] >= 0.0
    assert (result.experiment_dir / "model.joblib").exists()
    assert not (result.experiment_dir / "scaler.joblib").exists()
    assert (result.experiment_dir / "val_predictions.csv").exists()
    assert (result.experiment_dir / "feature_importance.csv").exists()
    predictions = pd.read_csv(result.experiment_dir / "val_predictions.csv")
    assert set(predictions["prediction"]).issubset({"UP", "DOWN", "HOLD"})
    prob_cols = [f"probability_{label}" for label in ("UP", "DOWN", "HOLD")]
    assert np.allclose(predictions[prob_cols].sum(axis=1), 1.0)
    metadata = json.loads((result.experiment_dir / "metadata.json").read_text())
    assert metadata["test_rows"] == 15
    assert metadata["dataset_version"] == "v0.1"


def test_xgboost_training_is_reproducible_and_does_not_use_test_rows(training_config):
    first = BaselineTrainer(training_config).run(
        model_name="xgboost",
        model_version="baseline_xgboost_test_a",
        experiment_id="exp_test_xgb_a",
    )
    second = BaselineTrainer(training_config).run(
        model_name="xgboost",
        model_version="baseline_xgboost_test_b",
        experiment_id="exp_test_xgb_b",
    )
    assert first.metrics == second.metrics
    predictions = pd.read_csv(first.experiment_dir / "val_predictions.csv")
    test = pd.read_parquet(
        training_config.data.processed_dir / "datasets" / "dataset_v0.1" / "test.parquet"
    )
    assert set(predictions["timestamp"]).isdisjoint(set(test["timestamp"].astype(str)))


def test_feature_importance_csv_structure_for_gradient_boosters(training_config):
    for model_name in ("lightgbm", "xgboost"):
        result = BaselineTrainer(training_config).run(
            model_name=model_name,
            model_version=f"fi_{model_name}_test",
            experiment_id=f"exp_fi_{model_name}",
        )
        fi = pd.read_csv(result.experiment_dir / "feature_importance.csv")
        assert list(fi.columns) == ["rank", "feature", "importance"]
        assert len(fi) == len(FEATURE_COLUMNS)
        assert (fi["rank"] == list(range(1, len(FEATURE_COLUMNS) + 1))).all()


# ---------------------------------------------------------------------------
# Spec section 28 — dataset loader tests (missing/unexpected feature, target)
# ---------------------------------------------------------------------------


def _valid_frame() -> pd.DataFrame:
    return _frame("2025-01-02", 10)


def _validate(frame: pd.DataFrame) -> None:
    expected_columns = (
        "ticker",
        "timestamp",
        *FEATURE_COLUMNS,
        "label",
        "future_return",
        "target_timestamp",
        "dataset_version",
        "feature_set_version",
        "label_set_version",
        "source_data_version",
    )
    _validate_frame(
        frame,
        split="train",
        expected_columns=expected_columns,
        dataset_version="v0.1",
        feature_version="v0.1",
        label_version="v0.1",
    )


def test_loader_rejects_missing_feature_column():
    frame = _valid_frame().drop(columns=[FEATURE_COLUMNS[0]])
    with pytest.raises(SchemaMismatchError, match="schema mismatch"):
        _validate(frame)


def test_loader_rejects_unexpected_feature_column():
    frame = _valid_frame()
    frame["sneaky_extra_feature"] = 1.0
    with pytest.raises(SchemaMismatchError, match="schema mismatch"):
        _validate(frame)


def test_loader_rejects_invalid_target():
    frame = _valid_frame()
    frame["label"] = frame["label"].replace({"UP": "SIDEWAYS"})
    with pytest.raises(InvalidTargetError):
        _validate(frame)


def test_loader_rejects_non_finite_features():
    frame = _valid_frame()
    frame.loc[frame.index[0], FEATURE_COLUMNS[0]] = np.nan
    with pytest.raises(InvalidFeaturesError):
        _validate(frame)


def test_loader_rejects_row_level_version_mismatch():
    frame = _valid_frame()
    frame["feature_set_version"] = "v9.9"
    with pytest.raises(VersionMismatchError):
        _validate(frame)


def test_loader_detects_tampered_split_checksum(training_config):
    """A modified split file must abort loading (checksum integrity)."""
    directory = training_config.data.processed_dir / "datasets" / "dataset_v0.1"
    train = pd.read_parquet(directory / "train.parquet")
    train.loc[train.index[0], FEATURE_COLUMNS[0]] = -999.0
    train.to_parquet(directory / "train.parquet", engine="pyarrow")
    with pytest.raises(SchemaMismatchError, match="checksum mismatch"):
        load_training_dataset(
            training_config.data.processed_dir,
            dataset_version="v0.1",
            feature_version="v0.1",
            label_version="v0.1",
        )


# ---------------------------------------------------------------------------
# Spec sections 10/28 — preprocessing fitted on TRAIN only
# ---------------------------------------------------------------------------


def test_scaler_statistics_come_from_train_split_only(training_config):
    result = BaselineTrainer(training_config).run(
        model_name="logistic_regression",
        model_version="prep_scaler_stats",
        experiment_id="exp_prep_scaler_stats",
    )
    scaler = joblib.load(result.experiment_dir / "scaler.joblib")
    train = pd.read_parquet(
        training_config.data.processed_dir / "datasets" / "dataset_v0.1" / "train.parquet"
    )
    expected_mean = train[list(FEATURE_COLUMNS)].to_numpy(dtype=float).mean(axis=0)
    expected_scale = train[list(FEATURE_COLUMNS)].to_numpy(dtype=float).std(axis=0, ddof=0)
    assert np.allclose(scaler.mean_, expected_mean)
    assert np.allclose(scaler.scale_, expected_scale)


def _overwrite_split(processed_dir: Path, split: str, frame: pd.DataFrame) -> None:
    """Replace a split file and refresh its manifest checksum so loading succeeds."""
    import json as _json

    directory = processed_dir / "datasets" / "dataset_v0.1"
    path = directory / f"{split}.parquet"
    frame.to_parquet(path, engine="pyarrow")
    manifest_path = directory / "manifest.json"
    manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checksums"][f"{split}.parquet"] = sha256_of(path)
    manifest_path.write_text(_json.dumps(manifest, indent=2), encoding="utf-8")


def test_validation_and_test_data_cannot_influence_fitted_artifacts(training_config):
    """Mandatory leakage audit: mutating VAL/TEST leaves the fit unchanged."""
    first = BaselineTrainer(training_config).run(
        model_name="logistic_regression",
        model_version="leak_probe_a",
        experiment_id="exp_leak_probe_a",
    )
    first_scaler = joblib.load(first.experiment_dir / "scaler.joblib")
    first_model = joblib.load(first.experiment_dir / "model.joblib")

    directory = training_config.data.processed_dir / "datasets" / "dataset_v0.1"
    for split in ("val", "test"):
        frame = pd.read_parquet(directory / f"{split}.parquet")
        for name in FEATURE_COLUMNS:
            frame[name] = frame[name] * 1000.0 + 5.0
        _overwrite_split(training_config.data.processed_dir, split, frame)

    second = BaselineTrainer(training_config).run(
        model_name="logistic_regression",
        model_version="leak_probe_b",
        experiment_id="exp_leak_probe_b",
    )
    second_scaler = joblib.load(second.experiment_dir / "scaler.joblib")
    second_model = joblib.load(second.experiment_dir / "model.joblib")
    assert np.allclose(first_scaler.mean_, second_scaler.mean_)
    assert np.allclose(first_scaler.scale_, second_scaler.scale_)
    assert np.allclose(first_model.coef_, second_model.coef_)
    assert np.allclose(first_model.intercept_, second_model.intercept_)


# ---------------------------------------------------------------------------
# Spec section 16/28 — model output probabilities + artifact identity
# ---------------------------------------------------------------------------


def test_validation_probabilities_have_correct_shape_and_normalization(training_config):
    result = BaselineTrainer(training_config).run(
        model_name="logistic_regression",
        model_version="proba_shape",
        experiment_id="exp_proba_shape",
    )
    predictions = pd.read_csv(result.experiment_dir / "val_predictions.csv")
    probability_columns = [f"probability_{label}" for label in ("UP", "DOWN", "HOLD")]
    assert set(probability_columns).issubset(predictions.columns)
    assert len(predictions) == 15  # validation split row count
    assert np.allclose(predictions[probability_columns].sum(axis=1), 1.0)
    assert set(predictions["prediction"]).issubset({"UP", "DOWN", "HOLD"})


def test_ranking_metrics_computed_when_all_classes_present(training_config):
    """ROC-AUC/PR-AUC must be numeric, never silently None, when applicable."""
    from src.model.metrics import classification_metrics

    y_true = np.array(["UP", "DOWN", "HOLD", "UP", "DOWN", "HOLD"])
    probabilities = np.array(
        [
            [0.7, 0.2, 0.1],
            [0.1, 0.8, 0.1],
            [0.2, 0.2, 0.6],
            [0.6, 0.3, 0.1],
            [0.2, 0.6, 0.2],
            [0.3, 0.3, 0.4],
        ]
    )
    predictions = np.array(["UP", "DOWN", "HOLD", "UP", "DOWN", "HOLD"])
    metrics = classification_metrics(y_true, predictions, probabilities, CLASSES_ORDER)
    assert metrics["roc_auc_ovr_macro"] is not None
    assert metrics["pr_auc_ovr_macro"] is not None
    assert 0.0 <= metrics["roc_auc_ovr_macro"] <= 1.0
    assert 0.0 <= metrics["pr_auc_ovr_macro"] <= 1.0


def test_experiment_and_model_artifacts_record_full_version_identity(training_config):
    result = BaselineTrainer(training_config).run(
        model_name="logistic_regression",
        model_version="identity_check",
        experiment_id="exp_identity_check",
    )
    metadata = json.loads((result.experiment_dir / "metadata.json").read_text(encoding="utf-8"))
    for key in (
        "experiment_id",
        "model_version",
        "config_version",
        "dataset_version",
        "feature_version",
        "label_version",
        "git_commit",
        "random_seed",
        "training_timestamp",
    ):
        assert key in metadata
    snapshot = json.loads(
        (result.experiment_dir / "config_snapshot.json").read_text(encoding="utf-8")
    )
    assert snapshot["random_seed"] == training_config.model.random_seed
    assert snapshot["model"]["name"] == "logistic_regression"
    model_metadata = json.loads((result.artifact_dir / "metadata.json").read_text())
    assert model_metadata["dataset_version"] == "v0.1"
    assert model_metadata["feature_version"] == "v0.1"
    assert model_metadata["label_version"] == "v0.1"


def test_feature_matrix_excludes_target_and_metadata_columns(training_config):
    """Mandatory leakage audit: metadata/target columns can never enter X."""
    loaded = load_training_dataset(
        training_config.data.processed_dir,
        dataset_version="v0.1",
        feature_version="v0.1",
        label_version="v0.1",
    )
    assert not (set(NON_FEATURE_COLUMNS) & set(loaded.feature_names))
    assert not ({"label", "future_return", "target_timestamp"} & set(loaded.feature_names))
    X_train = loaded.train[list(loaded.feature_names)]
    assert list(X_train.columns) == list(FEATURE_COLUMNS)
    train_timestamps = pd.to_datetime(loaded.train["timestamp"])
    val_timestamps = pd.to_datetime(loaded.val["timestamp"])
    test_timestamps = pd.to_datetime(loaded.test["timestamp"])
    assert train_timestamps.max() < val_timestamps.min() < test_timestamps.min()
