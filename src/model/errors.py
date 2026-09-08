"""Explicit failures raised by the baseline training pipeline."""

from __future__ import annotations

from typing import Any

from src.core.errors import FinanceAIError


class ModelError(FinanceAIError):
    """Base class for training failures."""

    category = "TRAINING_ERROR"

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message, context=context)
        self.context["category"] = self.category


class DatasetNotFoundError(ModelError):
    """The requested immutable dataset does not exist."""

    category = "DATASET_NOT_FOUND"


class SchemaMismatchError(ModelError):
    """A dataset does not match the training schema."""

    category = "SCHEMA_MISMATCH"


class VersionMismatchError(ModelError):
    """Dataset versions do not match the requested training versions."""

    category = "VERSION_MISMATCH"


class InvalidFeaturesError(ModelError):
    """Training features contain invalid values or columns."""

    category = "INVALID_FEATURES"


class InvalidTargetError(ModelError):
    """Training targets contain invalid classes or values."""

    category = "INVALID_TARGET"


class InsufficientDataError(ModelError):
    """A split does not contain enough rows to train or evaluate."""

    category = "INSUFFICIENT_DATA"


class ArtifactError(ModelError):
    """An immutable model or experiment artifact cannot be written."""

    category = "ARTIFACT_ERROR"


class ConfigurationError(ModelError):
    """The requested model configuration is invalid."""

    category = "CONFIGURATION_ERROR"
