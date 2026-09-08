"""Reproducible training of the approved logistic and random-forest baselines."""

from __future__ import annotations

import csv
import json
import platform
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from src.config.loader import AppConfig, ModelSpec
from src.logging.logger import get_logger
from src.model.errors import ArtifactError, ConfigurationError, InsufficientDataError, ModelError
from src.model.loader import CLASSES, load_training_dataset
from src.model.metrics import classification_metrics

logger = get_logger("model.trainer")


@dataclass(frozen=True)
class TrainingResult:
    """Machine-readable outcome of one baseline experiment."""

    experiment_id: str
    model_version: str
    config_version: str
    dataset_version: str
    feature_version: str
    label_version: str
    metrics: dict[str, Any]
    artifact_dir: Path
    experiment_dir: Path
    training_seconds: float


class BaselineTrainer:
    """Load, validate, train, evaluate, and persist one approved baseline."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def run(
        self,
        *,
        model_name: str = "logistic_regression",
        dataset_version: str | None = None,
        feature_version: str | None = None,
        label_version: str | None = None,
        model_version: str | None = None,
        experiment_id: str | None = None,
    ) -> TrainingResult:
        """Train one model using TRAIN and evaluate only on VALIDATION."""
        dataset_version = dataset_version or self.config.dataset_builder.dataset_version
        feature_version = feature_version or self.config.features.version
        label_version = label_version or self.config.dataset.label_version
        spec = self._model_spec(model_name)
        dataset = load_training_dataset(
            self.config.data.processed_dir,
            dataset_version=dataset_version,
            feature_version=feature_version,
            label_version=label_version,
        )
        if dataset.train.empty or dataset.val.empty:
            raise InsufficientDataError("TRAIN and VALIDATION splits must both contain rows")

        model_version = model_version or f"{model_name}_v0.1"
        experiment_id = (
            experiment_id
            or f"exp_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
        )
        started = time.perf_counter()
        X_train = dataset.train[list(dataset.feature_names)]
        y_train = dataset.train["label"]
        X_val = dataset.val[list(dataset.feature_names)]
        y_val = dataset.val["label"]
        scaler = StandardScaler() if model_name == "logistic_regression" else None
        train_values = scaler.fit_transform(X_train) if scaler else X_train.to_numpy()
        val_values = scaler.transform(X_val) if scaler else X_val.to_numpy()
        estimator = self._make_estimator(spec)
        try:
            estimator.fit(train_values, y_train)
            predictions = estimator.predict(val_values)
            probabilities = (
                estimator.predict_proba(val_values) if hasattr(estimator, "predict_proba") else None
            )
        except (ValueError, RuntimeError) as error:
            raise ModelError(f"baseline training failed: {error}") from error
        metrics = classification_metrics(
            y_val.to_numpy(),
            predictions,
            probabilities,
            getattr(estimator, "classes_", CLASSES),
        )
        importance = _feature_importance(estimator, dataset.feature_names)
        elapsed = time.perf_counter() - started
        result = TrainingResult(
            experiment_id=experiment_id,
            model_version=model_version,
            config_version=self.config.model.config_version,
            dataset_version=dataset_version,
            feature_version=feature_version,
            label_version=label_version,
            metrics=metrics,
            artifact_dir=self._artifact_root() / model_version,
            experiment_dir=self._artifact_root() / "experiments" / experiment_id,
            training_seconds=round(elapsed, 6),
        )
        self._persist(
            result=result,
            dataset=dataset,
            spec=spec,
            estimator=estimator,
            scaler=scaler,
            importance=importance,
            predictions=predictions,
            probabilities=probabilities,
        )
        logger.info(
            "baseline_training_completed",
            experiment_id=experiment_id,
            model_version=model_version,
            dataset_version=dataset_version,
            feature_version=feature_version,
            label_version=label_version,
            train_rows=len(dataset.train),
            val_rows=len(dataset.val),
            feature_count=len(dataset.feature_names),
            metrics=metrics,
            duration_seconds=round(elapsed, 4),
            status="COMPLETED",
        )
        return result

    def _model_spec(self, name: str) -> ModelSpec:
        for spec in self.config.model.models:
            if spec.name == name:
                return spec
        raise ConfigurationError(f"model {name!r} is not configured")

    def _make_estimator(self, spec: ModelSpec):
        params = dict(spec.params)
        params.setdefault("random_state", self.config.model.random_seed)
        if spec.name == "logistic_regression":
            return LogisticRegression(**params)
        if spec.name == "random_forest":
            params.setdefault("n_jobs", self.config.model.n_jobs)
            return RandomForestClassifier(**params)
        if spec.name == "lightgbm":
            from lightgbm import LGBMClassifier

            params.setdefault("n_jobs", self.config.model.n_jobs)
            params.setdefault("verbose", -1)
            return LGBMClassifier(**params)
        if spec.name == "xgboost":
            from src.model.wrappers import XGBoostClassifierWrapper

            params.setdefault("n_jobs", self.config.model.n_jobs)
            return XGBoostClassifierWrapper(**params)
        raise ConfigurationError(f"unsupported model {spec.name!r}")

    def _artifact_root(self) -> Path:
        path = self.config.model.artifact_dir
        return path if path.is_absolute() else Path.cwd() / path

    def _persist(
        self, *, result, dataset, spec, estimator, scaler, importance, predictions, probabilities
    ):
        """Write conflict-protected model and experiment artifacts."""
        model_dir = result.artifact_dir
        experiment_dir = result.experiment_dir
        try:
            if model_dir.exists():
                raise ArtifactError(f"model version already exists: {result.model_version}")
            model_dir.mkdir(parents=True, exist_ok=True)
            experiment_dir.mkdir(parents=True, exist_ok=False)
            metadata = {
                "experiment_id": result.experiment_id,
                "model_version": result.model_version,
                "config_version": result.config_version,
                "dataset_version": result.dataset_version,
                "feature_version": result.feature_version,
                "label_version": result.label_version,
                "git_commit": _git_commit(),
                "random_seed": self.config.model.random_seed,
                "model_name": spec.name,
                "model_type": spec.type,
                "feature_count": len(dataset.feature_names),
                "train_rows": len(dataset.train),
                "validation_rows": len(dataset.val),
                "test_rows": len(dataset.test),
                "train_period": _period(dataset.train),
                "validation_period": _period(dataset.val),
                "metrics": result.metrics,
                "training_seconds": result.training_seconds,
                "training_timestamp": datetime.now(timezone.utc).isoformat(),
                "environment": {
                    "python": platform.python_version(),
                    "sklearn": sklearn.__version__,
                },
            }
            _write_json(experiment_dir / "metadata.json", metadata)
            _write_json(
                experiment_dir / "config_snapshot.json", _config_snapshot(self.config, spec)
            )
            joblib.dump(estimator, experiment_dir / "model.joblib")
            if scaler is not None:
                joblib.dump(scaler, experiment_dir / "scaler.joblib")
            _write_predictions(
                experiment_dir / "val_predictions.csv",
                dataset.val,
                predictions,
                probabilities,
                getattr(estimator, "classes_", CLASSES),
            )
            _write_csv(experiment_dir / "confusion_matrix.csv", result.metrics["confusion_matrix"])
            _write_csv(experiment_dir / "feature_importance.csv", importance)
            (experiment_dir / "report.md").write_text(
                _report(metadata, importance), encoding="utf-8"
            )
            model_metadata = model_dir / "metadata.json"
            joblib.dump(estimator, model_dir / "model.joblib")
            if scaler is not None:
                joblib.dump(scaler, model_dir / "scaler.joblib")
            _write_json(model_metadata, metadata)
        except (OSError, ValueError, RuntimeError) as error:
            raise ArtifactError(f"cannot persist baseline artifacts: {error}") from error


def _feature_importance(estimator, feature_names: tuple[str, ...]) -> list[dict[str, Any]]:
    values = None
    if hasattr(estimator, "feature_importances_") and estimator.feature_importances_ is not None:
        values = estimator.feature_importances_
    elif hasattr(estimator, "coef_") and estimator.coef_ is not None:
        values = np.abs(estimator.coef_).mean(axis=0)
    if values is None:
        return []
    order = np.argsort(values)[::-1]
    return [
        {"feature": feature_names[index], "importance": float(values[index]), "rank": rank}
        for rank, index in enumerate(order, start=1)
    ]


def _git_commit() -> str:
    """Best-effort short HEAD commit for reproducibility metadata.

    Returns ``"unknown"`` when git is unavailable or the repository has
    no commits yet (fresh repositories have no HEAD) — never raises.
    """
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    commit = completed.stdout.strip()
    return commit if commit else "unknown"


def _period(frame: pd.DataFrame) -> dict[str, str | None]:
    if frame.empty:
        return {"start": None, "end": None}
    timestamps = pd.to_datetime(frame["timestamp"])
    return {"start": timestamps.min().isoformat(), "end": timestamps.max().isoformat()}


def _config_snapshot(config: AppConfig, spec: ModelSpec) -> dict[str, Any]:
    return {
        "config_version": config.model.config_version,
        "model": {"name": spec.name, "type": spec.type, "params": dict(spec.params)},
        "random_seed": config.model.random_seed,
        "n_jobs": config.model.n_jobs,
        "preprocessing": (
            "StandardScaler fit on TRAIN only" if spec.name == "logistic_regression" else "none"
        ),
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )


def _write_predictions(
    path: Path, frame: pd.DataFrame, predictions, probabilities, probability_classes
) -> None:
    output = frame[["ticker", "timestamp", "label"]].copy()
    output["prediction"] = predictions
    if probabilities is not None:
        for label in CLASSES:
            source_index = list(probability_classes).index(label)
            output[f"probability_{label}"] = probabilities[:, source_index]
    output.to_csv(path, index=False)


def _write_csv(path: Path, rows) -> None:
    if path.name == "confusion_matrix.csv":
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["true/predicted", *CLASSES])
            for label, row in zip(CLASSES, rows):
                writer.writerow([label, *row])
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["rank", "feature", "importance"])
        writer.writeheader()
        writer.writerows(rows)


def _report(metadata: dict, importance: list[dict[str, Any]]) -> str:
    return "\n".join(
        [
            f"# Baseline training experiment `{metadata['experiment_id']}`",
            "",
            f"- Model: `{metadata['model_version']}`",
            f"- Dataset: `{metadata['dataset_version']}`",
            f"- Features: `{metadata['feature_version']}` ({metadata['feature_count']})",
            f"- Labels: `{metadata['label_version']}`",
            f"- Training rows: {metadata['train_rows']}",
            f"- Validation rows: {metadata['validation_rows']}",
            "",
            "## Validation metrics",
            "",
            "```json",
            json.dumps(metadata["metrics"], indent=2, sort_keys=True),
            "```",
            "",
            "Feature importance is a model-specific association measure, not causality.",
            "Financial performance is intentionally not evaluated in this milestone.",
            "",
            (
                f"Top feature: `{importance[0]['feature']}`"
                if importance
                else "No feature importance available."
            ),
            "",
        ]
    )
