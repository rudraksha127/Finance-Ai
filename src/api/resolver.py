"""Deterministic model resolution and loading for the inference API (M09).

Implements INFERENCE_API_BLUEPRINT sections 9 (resolution), 10
(compatibility), and 13 (loading):

- Explicit ``model_version`` wins; otherwise the configured default
  (``api.default_model``); otherwise the newest trained artifact.
  No silent switching, no round-robin, no metrics-based selection.
- Compatibility checks happen BEFORE inference and fail with the exact
  blueprint error codes; there is never a hidden conversion.
- Loading reuses the Milestone-07 artifact layout (``model.joblib``,
  optional ``scaler.joblib``, ``metadata.json``) — the API layer adds no
  second serialization format. Models are immutable at inference time.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import joblib

from src.api.errors import (
    FEATURE_VALIDATION_FAILED,
    FEATURE_VERSION_INCOMPATIBLE,
    MODEL_NOT_FOUND,
    MODEL_VERSION_INCOMPATIBLE,
    ApiError,
)
from src.config.loader import AppConfig
from src.logging.logger import get_logger
from src.model.loader import CLASSES

logger = get_logger("api.resolver")

API_VERSION = "v1"


@dataclass(frozen=True)
class LoadedModel:
    """One immutable model artifact plus its verified metadata."""

    model_version: str
    estimator: object
    scaler: object | None
    metadata: dict

    @property
    def feature_version(self) -> str:
        return str(self.metadata["feature_version"])

    @property
    def label_version(self) -> str:
        return str(self.metadata["label_version"])

    @property
    def feature_names(self) -> tuple[str, ...]:
        """The model's input schema.

        M07 metadata records ``feature_count``; the feature *names* come
        from the versioned feature registry, which the M07 dataset loader
        guarantees matches the training schema (same convention as
        ``src/backtest/prediction.py``).
        """
        recorded = self.metadata.get("feature_names")
        if recorded:
            return tuple(recorded)
        from src.features.registry import FEATURE_COLUMNS

        return tuple(FEATURE_COLUMNS)

    @property
    def feature_count(self) -> int:
        return int(self.metadata["feature_count"])

    @property
    def model_type(self) -> str:
        return str(self.metadata.get("model_type", "unknown"))

    @property
    def training_status(self) -> str:
        return str(self.metadata.get("training_status", "COMPLETED"))

    @property
    def dataset_version(self) -> str:
        return str(self.metadata.get("dataset_version", "unknown"))

    @property
    def trained_at(self) -> str | None:
        return self.metadata.get("training_timestamp")


def _artifact_root(config: AppConfig) -> Path:
    path = config.model.artifact_dir
    return path if path.is_absolute() else Path.cwd() / path


def available_model_versions(config: AppConfig) -> list[str]:
    """List model versions that have a loadable artifact on disk."""
    root = _artifact_root(config)
    if not root.exists():
        return []
    versions = [
        entry.name
        for entry in sorted(root.iterdir())
        if entry.is_dir() and (entry / "model.joblib").exists() and entry.name != "experiments"
    ]
    return sorted(versions)


def resolve_model_version(config: AppConfig, requested: str | None) -> str:
    """Resolve the model version deterministically (blueprint section 9)."""
    if requested:
        if requested not in available_model_versions(config):
            raise ApiError(
                MODEL_NOT_FOUND,
                f"model version {requested!r} is not available on this service",
            )
        return requested
    if config.api.default_model:
        if config.api.default_model not in available_model_versions(config):
            raise ApiError(
                MODEL_NOT_FOUND,
                "configured default model is not available on this service",
            )
        return config.api.default_model
    versions = available_model_versions(config)
    if not versions:
        raise ApiError(MODEL_NOT_FOUND, "no trained model artifacts are available")
    return versions[-1]  # newest artifact; deterministic, never random


def load_model(config: AppConfig, model_version: str) -> LoadedModel:
    """Load and structurally validate one model artifact."""
    directory = _artifact_root(config) / model_version
    metadata_path = directory / "metadata.json"
    model_path = directory / "model.joblib"
    if not metadata_path.exists() or not model_path.exists():
        raise ApiError(
            MODEL_NOT_FOUND,
            f"model version {model_version!r} is not available on this service",
        )
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        estimator = joblib.load(model_path)
        scaler_path = directory / "scaler.joblib"
        scaler = joblib.load(scaler_path) if scaler_path.exists() else None
    except (OSError, ValueError) as error:
        raise ApiError(
            MODEL_NOT_FOUND,
            f"model artifact {model_version!r} cannot be loaded",
        ) from error
    if "feature_version" not in metadata or "label_version" not in metadata:
        raise ApiError(
            MODEL_VERSION_INCOMPATIBLE,
            f"model artifact {model_version!r} is missing version metadata",
        )
    return LoadedModel(
        model_version=model_version, estimator=estimator, scaler=scaler, metadata=metadata
    )


def check_compatibility(
    model: LoadedModel,
    *,
    feature_set_version: str,
    feature_names: tuple[str, ...],
    label_version: str | None,
) -> None:
    """Verify model/request compatibility before inference (section 10.1).

    Raises the exact blueprint codes; never attempts conversion.
    """
    if model.training_status != "COMPLETED":
        raise ApiError(
            MODEL_VERSION_INCOMPATIBLE,
            f"model {model.model_version!r} is not in a usable training state",
        )
    if feature_set_version != model.feature_version:
        raise ApiError(
            FEATURE_VERSION_INCOMPATIBLE,
            f"requested feature_set_version {feature_set_version!r} does not match "
            f"model feature_version {model.feature_version!r}",
        )
    if model.feature_names:
        if tuple(feature_names) != model.feature_names:
            raise ApiError(
                FEATURE_VALIDATION_FAILED,
                "request features do not match the model's expected input schema",
            )
    elif model.feature_count and len(feature_names) != model.feature_count:
        raise ApiError(
            FEATURE_VALIDATION_FAILED,
            "request feature count does not match the model's expected feature count",
        )
    if label_version and label_version != model.label_version:
        raise ApiError(
            MODEL_VERSION_INCOMPATIBLE,
            f"model label_version {model.label_version!r} does not match configured "
            f"label version {label_version!r}",
        )


class ModelCache:
    """Small bounded LRU cache of loaded models (blueprint section 13.1)."""

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("model cache capacity must be >= 1")
        self.capacity = capacity
        self._entries: OrderedDict[str, LoadedModel] = OrderedDict()

    def get(self, model_version: str) -> LoadedModel | None:
        if model_version not in self._entries:
            return None
        self._entries.move_to_end(model_version)
        return self._entries[model_version]

    def put(self, model: LoadedModel) -> None:
        self._entries[model.model_version] = model
        self._entries.move_to_end(model.model_version)
        while len(self._entries) > self.capacity:
            self._entries.popitem(last=False)

    def __len__(self) -> int:
        return len(self._entries)


def model_classes(model: LoadedModel) -> tuple[str, ...]:
    """Class order reported by the estimator, falling back to MVP classes."""
    return tuple(getattr(model.estimator, "classes_", CLASSES))
