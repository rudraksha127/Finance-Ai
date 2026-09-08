"""Temporal LSTM model (Post-MVP Milestone 06).

One compact temporal architecture — a single-layer LSTM — trained on causal
sequences built by :mod:`src.temporal.sequence` from the SAME versioned
datasets the baseline models consume. It deliberately reuses the existing
training contracts (feature order, CLASSES, metrics, artifact layout) instead
of creating a second ML system.

Key components:

- :class:`TemporalLSTM` — the torch module. Input shape
  ``[batch, sequence_length, feature_count]``; output = class logits over
  ``("UP", "DOWN", "HOLD")`` (same target as the baseline; no new labels).
- :class:`TemporalLSTMClassifier` — a sklearn-compatible wrapper persisted in
  ``model.joblib`` (``predict`` / ``predict_proba`` / ``classes_``) so the
  EXISTING backtest engine, registry, and API code run the temporal model
  unchanged.
- :class:`TemporalTrainer` — reproducible training with train-only
  normalization, validation-loss early stopping, best-checkpoint
  restoration, and baseline-layout artifact persistence.
"""

from __future__ import annotations

import json

# NOTE: torch must be imported BEFORE anything that pulls in scikit-learn.
# On Windows, loading sklearn's OpenMP runtime before torch's c10.dll can
# fail DLL initialization (WinError 1114). The KMP_DUPLICATE_LIB_OK escape
# hatch (set BEFORE torch loads) is the standard workaround for the duplicate
# OpenMP runtime; it is scoped to processes that use the temporal module.
import os
import platform
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

try:  # torch is a hard dependency of this milestone; fail with a clear message.
    import torch
    from torch import nn
except ImportError as _error:  # pragma: no cover - environment guard
    raise ImportError(
        "Post-MVP Milestone 06 requires PyTorch. Install the CPU build with: "
        "pip install torch --index-url https://download.pytorch.org/whl/cpu"
    ) from _error

import joblib
import numpy as np
import pandas as pd

from src.config.loader import AppConfig
from src.logging.logger import get_logger
from src.model.errors import ArtifactError, InsufficientDataError
from src.model.loader import CLASSES, load_training_dataset
from src.model.metrics import classification_metrics
from src.temporal.sequence import InsufficientSequenceError, SequenceError, build_sequences

logger = get_logger("temporal.model")


CLASS_TO_INDEX = {label: index for index, label in enumerate(CLASSES)}


def _git_commit() -> str:
    """Best-effort short HEAD commit (matches the baseline trainer contract)."""
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
    return completed.stdout.strip() or "unknown"


class TemporalLSTM(nn.Module):
    """Compact LSTM classifier over causal feature sequences."""

    def __init__(self, *, input_size: int, hidden_size: int, num_layers: int, dropout: float):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Linear(hidden_size, len(CLASSES))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        outputs, _ = self.lstm(x)
        return self.head(outputs[:, -1, :])  # last timestep carries the decision


class TemporalLSTMClassifier:
    """Sklearn-compatible wrapper around :class:`TemporalLSTM`.

    The wrapper is what gets persisted in ``model.joblib``. Its ``predict`` /
    ``predict_proba`` consume the standard per-row feature matrix
    (``[rows, feature_count]``) and return one prediction per row, exactly like
    the baseline estimators — achieved by prepending the persisted warm-up
    context (the final ``L-1`` scaled rows of the preceding split, strictly
    earlier than every predicted row) so every row has a full causal window
    without ever using future observations.

    Attributes match what the backtest engine inspects: ``classes_`` is the
    canonical ``("UP", "DOWN", "HOLD")`` order; probabilities are returned in
    that order.
    """

    def __init__(
        self,
        *,
        state_dict: dict,
        config: dict[str, Any],
        feature_names: tuple[str, ...],
        scaler_mean: np.ndarray,
        scaler_scale: np.ndarray,
        warmup: np.ndarray,
    ):
        self.state_dict = state_dict
        self.config = dict(config)
        self.feature_names = tuple(feature_names)
        self.scaler_mean = np.asarray(scaler_mean, dtype=float)
        self.scaler_scale = np.asarray(scaler_scale, dtype=float)
        self.warmup = np.asarray(warmup, dtype=float)
        self.classes_ = np.asarray(CLASSES)
        self._model: TemporalLSTM | None = None

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _materialize(self) -> TemporalLSTM:
        if self._model is None:
            self._model = TemporalLSTM(
                input_size=len(self.feature_names),
                hidden_size=int(self.config["hidden_size"]),
                num_layers=int(self.config["num_layers"]),
                dropout=float(self.config.get("dropout", 0.0)),
            )
            self._model.load_state_dict(
                {key: torch.as_tensor(value) for key, value in self.state_dict.items()}
            )
            self._model.eval()
        return self._model

    def _context(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        expected = len(self.feature_names)
        if X.ndim != 2 or X.shape[1] != expected:
            raise ValueError(
                f"temporal model expects {expected} features in registry order, "
                f"received shape {X.shape}"
            )
        scaled = (X - self.scaler_mean) / self.scaler_scale
        if not np.isfinite(scaled).all():
            raise ValueError("temporal model input contains NaN/Inf after scaling")
        length = int(self.config["sequence_length"])
        if len(self.warmup) != length - 1:
            raise ArtifactError(
                "persisted warm-up context has the wrong length; artifact is corrupt"
            )
        return np.vstack([self.warmup, scaled])

    # ------------------------------------------------------------------
    # sklearn-compatible inference
    # ------------------------------------------------------------------
    def predict_proba(self, X) -> np.ndarray:
        context = self._context(X)
        length = int(self.config["sequence_length"])
        windows = np.stack([context[i : i + length] for i in range(context.shape[0] - length + 1)])
        if windows.shape[0] != len(X):  # every input row gets exactly one prediction
            raise ValueError(
                "internal error: sequence construction did not align 1:1 with input rows"
            )
        model = self._materialize()
        with torch.no_grad():
            logits = model(torch.tensor(windows, dtype=torch.float32))
            probabilities = torch.softmax(logits, dim=1).numpy()
        return probabilities

    def predict(self, X) -> np.ndarray:
        probabilities = self.predict_proba(X)
        return self.classes_[probabilities.argmax(axis=1)]


# The class persisted into ``model.joblib`` is the TORCH-FREE inference
# wrapper from :mod:`src.temporal.inference`. Backtest/API processes load
# that artifact without importing torch (Windows DLL conflict mitigation).
from src.temporal.inference import (
    TemporalLSTMClassifier as PersistedTemporalLSTMClassifier,
)

__all__ = [
    "PersistedTemporalLSTMClassifier",
    "TemporalLSTM",
    "TemporalLSTMClassifier",
    "TemporalTrainer",
]


class TemporalTrainer:
    """Train the temporal LSTM on a versioned dataset with the baseline contracts."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    def run(
        self,
        *,
        dataset_version: str | None = None,
        feature_version: str | None = None,
        label_version: str | None = None,
        model_version: str | None = None,
        sequence_length: int | None = None,
        baseline_metrics: dict[str, Any] | None = None,
        experiment_id: str | None = None,
    ) -> dict[str, Any]:
        """Train, early-stop on validation, restore the best checkpoint, persist."""
        cfg = self.config.temporal
        dataset_version = dataset_version or self.config.dataset_builder.dataset_version
        feature_version = feature_version or self.config.features.version
        label_version = label_version or self.config.dataset.label_version
        model_version = model_version or cfg.model_version
        sequence_length = sequence_length or cfg.sequence_length
        experiment_id = (
            experiment_id
            or f"temp_exp_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
        )

        seed = self.config.model.random_seed
        np.random.seed(seed)
        torch.manual_seed(seed)
        torch.set_num_threads(1)

        dataset = load_training_dataset(
            self.config.data.processed_dir,
            dataset_version=dataset_version,
            feature_version=feature_version,
            label_version=label_version,
        )
        if dataset.train.empty or dataset.val.empty:
            raise InsufficientDataError("TRAIN and VALIDATION splits must both contain rows")

        features = list(dataset.feature_names)
        started = time.perf_counter()

        # --- normalization: fit on TRAIN only (milestone section 10) ---
        train_values = dataset.train[features].to_numpy(dtype=float)
        val_values = dataset.val[features].to_numpy(dtype=float)
        scaler_mean = train_values.mean(axis=0)
        scaler_scale = train_values.std(axis=0)
        scaler_scale[scaler_scale == 0.0] = 1.0  # constant columns are information-free

        train_scaled = (train_values - scaler_mean) / scaler_scale
        val_scaled = (val_values - scaler_mean) / scaler_scale

        # --- causal sequences per split (split isolation, no future rows) ---
        try:
            train_seq = build_sequences(
                dataset.train.assign(
                    **{name: train_scaled[:, index] for index, name in enumerate(features)}
                ),
                feature_names=tuple(features),
                sequence_length=sequence_length,
            )
            # Validation sequences end within the val split; the warm-up context
            # (L-1 rows) comes from the END of the train split — strictly earlier.
            warmup_train = (
                train_scaled[-(sequence_length - 1) :] if sequence_length > 1 else train_scaled[:0]
            )
            val_context = np.vstack([warmup_train, val_scaled])
            val_seq = _sequences_from_matrix(
                context=val_context,
                labels=dataset.val["label"].to_numpy(),
                timestamps=pd.to_datetime(dataset.val["timestamp"]).to_numpy(),
                feature_count=len(features),
                sequence_length=sequence_length,
            )
        except (SequenceError, InsufficientSequenceError) as error:
            raise InsufficientDataError(f"cannot build temporal sequences: {error}") from error

        y_train = np.asarray([CLASS_TO_INDEX[label] for label in train_seq.y])
        y_val_index = np.asarray([CLASS_TO_INDEX[label] for label in val_seq.y])

        model = TemporalLSTM(
            input_size=len(features),
            hidden_size=cfg.hidden_size,
            num_layers=cfg.num_layers,
            dropout=cfg.dropout,
        )
        criterion = nn.CrossEntropyLoss()  # approved multi-class loss; no exotic objectives
        optimizer = torch.optim.Adam(
            model.parameters(), lr=cfg.learning_rate, weight_decay=cfg.weight_decay
        )
        generator = torch.Generator().manual_seed(seed)

        x_train_t = torch.tensor(train_seq.X, dtype=torch.float32)
        y_train_t = torch.tensor(y_train, dtype=torch.long)
        x_val_t = torch.tensor(val_seq.X, dtype=torch.float32)

        # --- training loop with validation-loss early stopping ---
        best_val_loss = float("inf")
        best_epoch = 0
        best_state: dict | None = None
        patience_left = cfg.patience
        history: list[dict[str, float]] = []
        for epoch in range(1, cfg.max_epochs + 1):
            model.train()
            permutation = torch.randperm(x_train_t.shape[0], generator=generator)
            epoch_loss = 0.0
            for start in range(0, len(permutation), cfg.batch_size):
                batch = permutation[start : start + cfg.batch_size]
                optimizer.zero_grad()
                loss = criterion(model(x_train_t[batch]), y_train_t[batch])
                loss.backward()
                optimizer.step()
                epoch_loss += float(loss.detach()) * len(batch)
            model.eval()
            with torch.no_grad():
                val_logits = model(x_val_t)
                val_loss = float(criterion(val_logits, torch.tensor(y_val_index, dtype=torch.long)))
            history.append(
                {"epoch": epoch, "train_loss": epoch_loss / len(permutation), "val_loss": val_loss}
            )
            if val_loss < best_val_loss - 1e-6:
                best_val_loss = val_loss
                best_epoch = epoch
                best_state = {
                    key: value.detach().clone() for key, value in model.state_dict().items()
                }
                patience_left = cfg.patience
            else:
                patience_left -= 1
                if patience_left <= 0:
                    break

        if best_state is None:  # pragma: no cover - first epoch always improves on +inf
            raise ArtifactError("training never produced a validation improvement")
        model.load_state_dict(best_state)  # best checkpoint, never the final epoch
        training_seconds = time.perf_counter() - started

        # --- validation metrics via the SHARED evaluation framework ---
        with torch.no_grad():
            val_probabilities = torch.softmax(model(x_val_t), dim=1).numpy()
        val_predictions = np.asarray(CLASSES)[val_probabilities.argmax(axis=1)]
        metrics = classification_metrics(
            np.asarray(val_seq.y), val_predictions, val_probabilities, CLASSES
        )

        # --- persist artifacts in the baseline layout ---
        result = self._persist(
            model_version=model_version,
            experiment_id=experiment_id,
            dataset=dataset,
            sequence_length=sequence_length,
            scaler_mean=scaler_mean,
            scaler_scale=scaler_scale,
            best_state=best_state,
            best_epoch=best_epoch,
            history=history,
            metrics=metrics,
            val_frame=dataset.val,
            val_predictions=val_predictions,
            val_probabilities=val_probabilities,
            training_seconds=training_seconds,
            baseline_metrics=baseline_metrics,
            train_sequences=len(train_seq),
            val_sequences=len(val_seq),
        )
        artifact_root = self._artifact_root()
        result["model_dir"] = str(artifact_root / model_version)
        result["experiment_dir"] = str(artifact_root / "experiments" / experiment_id)
        logger.info(
            "temporal_training_completed",
            experiment_id=experiment_id,
            model_version=model_version,
            dataset_version=dataset_version,
            sequence_length=sequence_length,
            best_epoch=best_epoch,
            best_val_loss=round(best_val_loss, 6),
            train_sequences=len(train_seq),
            val_sequences=len(val_seq),
            duration_seconds=round(training_seconds, 4),
            status="COMPLETED",
        )
        return result

    # ------------------------------------------------------------------
    def _artifact_root(self) -> Path:
        path = self.config.model.artifact_dir
        return path if path.is_absolute() else Path.cwd() / path

    def _persist(
        self,
        *,
        model_version: str,
        experiment_id: str,
        dataset,
        sequence_length: int,
        scaler_mean: np.ndarray,
        scaler_scale: np.ndarray,
        best_state: dict,
        best_epoch: int,
        history: list[dict[str, float]],
        metrics: dict[str, Any],
        val_frame: pd.DataFrame,
        val_predictions: np.ndarray,
        val_probabilities: np.ndarray,
        training_seconds: float,
        baseline_metrics: dict[str, Any] | None,
        train_sequences: int,
        val_sequences: int,
    ) -> dict[str, Any]:
        cfg = self.config.temporal
        model_dir = self._artifact_root() / model_version
        experiment_dir = self._artifact_root() / "experiments" / experiment_id
        try:
            if model_dir.exists():
                raise ArtifactError(f"model version already exists: {model_version}")
            model_dir.mkdir(parents=True, exist_ok=True)
            experiment_dir.mkdir(parents=True, exist_ok=False)

            # Warm-up for FUTURE inference (e.g. the test split): the final L-1
            # scaled VALIDATION rows — strictly earlier than any later period.
            val_values = val_frame[list(dataset.feature_names)].to_numpy(dtype=float)
            val_scaled = (val_values - scaler_mean) / scaler_scale
            warmup = val_scaled[-(sequence_length - 1) :] if sequence_length > 1 else val_scaled[:0]

            wrapper = PersistedTemporalLSTMClassifier(
                state_dict={key: value.cpu().numpy() for key, value in best_state.items()},
                config={
                    "sequence_length": sequence_length,
                    "hidden_size": cfg.hidden_size,
                    "num_layers": cfg.num_layers,
                    "dropout": cfg.dropout,
                },
                feature_names=tuple(dataset.feature_names),
                scaler_mean=scaler_mean,
                scaler_scale=scaler_scale,
                warmup=warmup,
            )
            metadata = {
                "experiment_id": experiment_id,
                "model_version": model_version,
                "model_name": "temporal_lstm",
                "model_type": "temporal",
                "config_version": self.config.model.config_version,
                "dataset_version": dataset.dataset_version,
                "feature_version": dataset.feature_version,
                "label_version": dataset.label_version,
                "git_commit": _git_commit(),
                "random_seed": self.config.model.random_seed,
                "sequence_length": sequence_length,
                "input_dimension": [sequence_length, len(dataset.feature_names)],
                "feature_count": len(dataset.feature_names),
                "feature_names": list(dataset.feature_names),
                "train_sequences": train_sequences,
                "val_sequences": val_sequences,
                "best_epoch": best_epoch,
                "metrics": metrics,
                "ablation": {
                    "description": "single-row baseline vs sequence input (validation only)",
                    "baseline_metrics": baseline_metrics,
                    "temporal_metrics": metrics,
                },
                "training_seconds": round(training_seconds, 6),
                "training_timestamp": datetime.now(timezone.utc).isoformat(),
                "environment": {
                    "python": platform.python_version(),
                    "torch": torch.__version__,
                },
            }
            _write_json(experiment_dir / "metadata.json", metadata)
            _write_json(
                experiment_dir / "config_snapshot.json",
                {
                    "temporal": {
                        "sequence_length": sequence_length,
                        "hidden_size": cfg.hidden_size,
                        "num_layers": cfg.num_layers,
                        "dropout": cfg.dropout,
                        "batch_size": cfg.batch_size,
                        "max_epochs": cfg.max_epochs,
                        "patience": cfg.patience,
                        "learning_rate": cfg.learning_rate,
                        "weight_decay": cfg.weight_decay,
                    },
                    "random_seed": self.config.model.random_seed,
                    "normalization": "StandardScaler fit on TRAIN rows only",
                    "early_stopping": "validation loss (final test never monitored)",
                },
            )
            _write_json(
                experiment_dir / "training_history.json",
                {"history": history, "selected_epoch": best_epoch},
            )
            torch.save(
                {
                    "epoch": best_epoch,
                    "val_loss": history[best_epoch - 1]["val_loss"],
                    "state_dict": best_state,
                    "dataset_version": dataset.dataset_version,
                    "feature_version": dataset.feature_version,
                    "label_version": dataset.label_version,
                },
                experiment_dir / "checkpoint.pt",
            )
            _write_predictions(
                experiment_dir / "val_predictions.csv",
                val_frame,
                val_predictions,
                val_probabilities,
            )
            (experiment_dir / "report.md").write_text(_report(metadata), encoding="utf-8")

            # Model artifact (baseline layout: model.joblib + metadata.json)
            joblib.dump(wrapper, model_dir / "model.joblib")
            _write_json(model_dir / "metadata.json", metadata)
        except (OSError, ValueError, RuntimeError) as error:
            raise ArtifactError(f"cannot persist temporal artifacts: {error}") from error
        return metadata


def _sequences_from_matrix(
    *,
    context: np.ndarray,
    labels: np.ndarray,
    timestamps: np.ndarray,
    feature_count: int,
    sequence_length: int,
):
    """Build sequences from a pre-scaled context matrix (train warm-up + split)."""
    from src.temporal.sequence import Sequences

    if context.shape[1] != feature_count:
        raise SequenceError("context matrix width does not match the feature contract")
    if not np.isfinite(context).all():
        raise SequenceError("scaled context contains NaN/Inf")
    n = len(labels)
    if len(context) != n + sequence_length - 1:
        raise SequenceError(
            "context matrix must be exactly (split rows + sequence_length - 1) rows"
        )
    windows = np.stack([context[i : i + sequence_length] for i in range(n)])
    return Sequences(
        X=windows,
        y=labels,
        timestamps=timestamps,
        sequence_length=sequence_length,
        feature_names=(),
    )


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )


def _write_predictions(
    path: Path,
    frame: pd.DataFrame,
    predictions: np.ndarray,
    probabilities: np.ndarray,
) -> None:
    output = frame[["ticker", "timestamp", "label"]].copy()
    output["prediction"] = predictions
    for index, label in enumerate(CLASSES):
        output[f"probability_{label}"] = probabilities[:, index]
    output.to_csv(path, index=False)


def _report(metadata: dict) -> str:
    return "\n".join(
        [
            f"# Temporal training experiment `{metadata['experiment_id']}`",
            "",
            f"- Model: `{metadata['model_version']}` (LSTM, sequence_length={metadata['sequence_length']})",
            f"- Dataset: `{metadata['dataset_version']}`",
            f"- Features: `{metadata['feature_version']}` ({metadata['feature_count']})",
            f"- Labels: `{metadata['label_version']}`",
            f"- Best epoch: {metadata['best_epoch']} (validation loss)",
            "",
            "## Validation metrics",
            "",
            "```json",
            json.dumps(metadata["metrics"], indent=2, sort_keys=True),
            "```",
            "",
            "Interpretability is limited for temporal models; no attention",
            "visualisations are produced. Research-only artifact.",
            "",
        ]
    )
