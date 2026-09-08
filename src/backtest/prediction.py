"""Prediction adapter for the backtest engine (M08).

Loads a trained baseline model artifact (produced by Milestone 07) and
generates deterministic predictions/probabilities for the evaluation
rows. The model's recorded dataset/feature/label versions must match the
backtest dataset — the API never silently substitutes versions
(EVALUATION_BACKTESTING_BLUEPRINT sections 9.4, 29, 31).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.backtest.data import BacktestData
from src.backtest.errors import BacktestError, DataQualityError
from src.logging.logger import get_logger
from src.model.errors import VersionMismatchError
from src.model.loader import CLASSES

logger = get_logger("backtest.prediction")


@dataclass(frozen=True)
class ModelPredictions:
    """Evaluation rows augmented with model output columns."""

    frame: pd.DataFrame
    model_version: str
    model_metadata: dict

    @property
    def prediction_columns(self) -> tuple[str, ...]:
        return ("prediction", *[f"probability_{label}" for label in CLASSES])


def _load_model_artifact(model_dir: Path, model_version: str) -> tuple[object, object | None, dict]:
    """Load model.joblib + optional scaler.joblib + metadata.json."""
    directory = model_dir / model_version
    metadata_path = directory / "metadata.json"
    model_path = directory / "model.joblib"
    if not metadata_path.exists() or not model_path.exists():
        raise BacktestError(
            f"model artifact {model_version} not found at {directory}",
            context={"model_version": model_version, "path": str(directory)},
        )
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        estimator = joblib.load(model_path)
        scaler_path = directory / "scaler.joblib"
        scaler = joblib.load(scaler_path) if scaler_path.exists() else None
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise BacktestError(f"cannot load model artifact {model_version}: {error}") from error
    return estimator, scaler, metadata


def _verify_model_versions(metadata: dict, data: BacktestData, model_version: str) -> None:
    """Fail loudly when the model was trained on different versions."""
    checks = (
        ("dataset_version", data.dataset_version),
        ("feature_version", data.feature_version),
        ("label_version", data.label_version),
    )
    for key, expected in checks:
        actual = metadata.get(key)
        if actual is not None and str(actual) != str(expected):
            raise VersionMismatchError(
                f"model {model_version} was trained on {key}={actual}, "
                f"backtest dataset requires {expected}",
                context={"model_version": model_version, key: actual, "expected": expected},
            )


def load_model_predictions(
    data: BacktestData,
    *,
    model_version: str,
    model_dir: Path,
) -> ModelPredictions:
    """Generate predictions for every evaluation row from a versioned artifact.

    Raises:
        BacktestError: artifact missing/corrupt, model incompatible.
        DataQualityError: prediction output is invalid (NaN probabilities).
    """
    estimator, scaler, metadata = _load_model_artifact(model_dir, model_version)
    _verify_model_versions(metadata, data, model_version)

    frame = data.rows.copy()
    # The dataset loader already validated the schema equals FEATURE_COLUMNS,
    # so inference always uses the registered feature set in registry order.
    from src.features.registry import FEATURE_COLUMNS

    X = frame[list(FEATURE_COLUMNS)].to_numpy(dtype=float)
    if scaler is not None:
        X = scaler.transform(X)
    try:
        predictions = estimator.predict(X)
        probabilities = estimator.predict_proba(X)
    except (ValueError, RuntimeError) as error:
        raise BacktestError(f"model inference failed: {error}") from error

    model_classes = list(getattr(estimator, "classes_", CLASSES))
    if sorted(model_classes) != sorted(CLASSES):
        raise BacktestError(
            f"model {model_version} classes {model_classes} do not match {CLASSES}",
            context={"model_version": model_version, "classes": model_classes},
        )
    frame["prediction"] = predictions
    for label in CLASSES:
        source_index = model_classes.index(label)
        frame[f"probability_{label}"] = probabilities[:, source_index]
    proba_cols = [f"probability_{label}" for label in CLASSES]
    if not np.isfinite(frame[proba_cols].to_numpy()).all():
        raise DataQualityError("model produced non-finite probabilities")

    logger.info(
        "backtest_predictions_generated",
        model_version=model_version,
        rows=len(frame),
        status="READY",
    )
    return ModelPredictions(frame=frame, model_version=model_version, model_metadata=metadata)
