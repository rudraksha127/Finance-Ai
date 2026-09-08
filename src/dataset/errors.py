"""Dataset-builder error taxonomy (milestone section 31).

Explicit categories, no silent fallback. Each class carries its machine-
readable ``category`` so callers/logs stay consistent.
"""

from __future__ import annotations

from typing import Any

from src.core.errors import FinanceAIError


class DatasetError(FinanceAIError):
    """Base class for dataset-builder errors (carries ``category``)."""

    category = "UNKNOWN_ERROR"

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message, context=context)
        self.context["category"] = self.category


class DatasetDataNotFoundError(DatasetError):
    """Required input artifact (features/labels/source) does not exist."""

    category = "DATA_NOT_FOUND"


class FeatureVersionMismatchError(DatasetError):
    """Persisted feature set does not match the requested feature version."""

    category = "FEATURE_VERSION_MISMATCH"


class LabelVersionMismatchError(DatasetError):
    """Persisted label set does not match the requested label version."""

    category = "LABEL_VERSION_MISMATCH"


class SchemaMismatchError(DatasetError):
    """Dataset/frame schema violates the approved contract."""

    category = "SCHEMA_MISMATCH"


class InvalidTimestampError(DatasetError):
    """Timestamp integrity violated (duplicate/unsorted/out-of-range)."""

    category = "INVALID_TIMESTAMP"


class SplitConfigurationError(DatasetError):
    """Split ratios/boundaries are invalid or unproducible."""

    category = "SPLIT_CONFIGURATION_ERROR"


class MissingFeatureError(DatasetError):
    """A mandatory feature column is absent or invalid."""

    category = "MISSING_FEATURE"


class MissingLabelError(DatasetError):
    """A mandatory label column is absent or invalid."""

    category = "MISSING_LABEL"


class DatasetAlreadyExistsError(DatasetError):
    """An immutable dataset version already exists with different content."""

    category = "DATASET_ALREADY_EXISTS"


class DatasetPersistenceError(DatasetError):
    """Writing the dataset artifact failed."""

    category = "PERSISTENCE_ERROR"
