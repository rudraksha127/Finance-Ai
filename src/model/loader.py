"""Validated loading of immutable Dataset Builder artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.dataset.storage import sha256_of
from src.features.registry import FEATURE_COLUMNS
from src.model.errors import (
    DatasetNotFoundError,
    InvalidFeaturesError,
    InvalidTargetError,
    SchemaMismatchError,
    VersionMismatchError,
)

TARGET = "label"
CLASSES = ("UP", "DOWN", "HOLD")
NON_FEATURE_COLUMNS = {
    "ticker",
    "timestamp",
    "label",
    "future_return",
    "target_timestamp",
    "dataset_version",
    "feature_set_version",
    "label_set_version",
    "source_data_version",
}


@dataclass(frozen=True)
class TrainingDataset:
    """Training-ready splits with metadata and an explicit feature contract."""

    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame
    metadata: dict
    feature_names: tuple[str, ...]
    directory: Path

    @property
    def dataset_version(self) -> str:
        """Return the immutable dataset version."""
        return str(self.metadata["version"])

    @property
    def feature_version(self) -> str:
        """Return the feature-set version."""
        return str(self.metadata["feature_version"])

    @property
    def label_version(self) -> str:
        """Return the label-set version."""
        return str(self.metadata["label_version"])


def load_training_dataset(
    processed_dir: Path,
    *,
    dataset_version: str,
    feature_version: str,
    label_version: str,
) -> TrainingDataset:
    """Load and validate a versioned dataset for model training.

    Args:
        processed_dir: Root of the processed data tier.
        dataset_version: Dataset snapshot to load.
        feature_version: Required feature-set version.
        label_version: Required label-set version.

    Raises:
        DatasetNotFoundError: if the snapshot or required files are absent.
        VersionMismatchError: if metadata versions differ from the request.
        SchemaMismatchError: if the persisted schema is not the MVP schema.
        InvalidFeaturesError: if feature values are non-finite.
        InvalidTargetError: if labels are not UP/DOWN/HOLD.
    """
    directory = processed_dir / "datasets" / f"dataset_{dataset_version}"
    metadata_path = directory / "metadata.json"
    manifest_path = directory / "manifest.json"
    names_path = directory / "feature_names.json"
    if not directory.exists() or not metadata_path.exists():
        raise DatasetNotFoundError(
            f"dataset {dataset_version} not found at {directory}",
            context={"dataset_version": dataset_version, "path": str(directory)},
        )
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        feature_names = tuple(json.loads(names_path.read_text(encoding="utf-8")))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise DatasetNotFoundError(f"cannot read dataset metadata: {error}") from error

    if metadata.get("version") != dataset_version:
        raise VersionMismatchError("metadata dataset version does not match requested version")
    if metadata.get("feature_version") != feature_version:
        raise VersionMismatchError(
            "dataset feature version does not match requested version",
            context={"expected": feature_version, "actual": metadata.get("feature_version")},
        )
    if metadata.get("label_version") != label_version:
        raise VersionMismatchError(
            "dataset label version does not match requested version",
            context={"expected": label_version, "actual": metadata.get("label_version")},
        )
    if tuple(feature_names) != tuple(FEATURE_COLUMNS):
        raise SchemaMismatchError(
            "dataset feature_names.json does not match the registered MVP feature order"
        )
    if manifest.get("version_hash") != metadata.get("version_hash"):
        raise SchemaMismatchError("dataset manifest hash does not match metadata")
    hash_path = directory / "hash.txt"
    if not hash_path.exists() or hash_path.read_text(encoding="utf-8").strip() != metadata.get(
        "version_hash"
    ):
        raise SchemaMismatchError("dataset definition hash is missing or inconsistent")

    checksums = manifest.get("checksums", {})
    frames: dict[str, pd.DataFrame] = {}
    for split in ("train", "val", "test"):
        path = directory / f"{split}.parquet"
        if not path.exists():
            raise DatasetNotFoundError(f"dataset split is missing: {path}")
        expected_checksum = checksums.get(f"{split}.parquet")
        if expected_checksum and sha256_of(path) != expected_checksum:
            raise SchemaMismatchError(f"dataset split checksum mismatch: {split}")
        try:
            frames[split] = pd.read_parquet(path, engine="pyarrow")
        except (OSError, ValueError) as error:
            raise DatasetNotFoundError(f"cannot read dataset split {split}: {error}") from error

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
    for split, frame in frames.items():
        _validate_frame(
            frame,
            split=split,
            expected_columns=expected_columns,
            dataset_version=dataset_version,
            feature_version=feature_version,
            label_version=label_version,
        )
    return TrainingDataset(
        train=frames["train"],
        val=frames["val"],
        test=frames["test"],
        metadata=metadata,
        feature_names=tuple(feature_names),
        directory=directory,
    )


def _validate_frame(
    frame: pd.DataFrame,
    *,
    split: str,
    expected_columns: tuple[str, ...],
    dataset_version: str,
    feature_version: str,
    label_version: str,
) -> None:
    """Validate one persisted split and keep metadata out of X."""
    if tuple(frame.columns) != expected_columns:
        raise SchemaMismatchError(
            f"{split} schema mismatch",
            context={"expected": list(expected_columns), "actual": list(frame.columns)},
        )
    numeric = frame[list(FEATURE_COLUMNS)].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(numeric.to_numpy()).all():
        raise InvalidFeaturesError(f"{split} contains NaN, Infinity, or non-numeric features")
    labels = set(frame[TARGET].dropna().unique())
    if not labels.issubset(set(CLASSES)) or frame[TARGET].isna().any():
        raise InvalidTargetError(f"{split} contains labels outside {CLASSES}")
    for column, expected in (
        ("dataset_version", dataset_version),
        ("feature_set_version", feature_version),
        ("label_set_version", label_version),
    ):
        if not frame[column].eq(expected).all():
            raise VersionMismatchError(f"{split} contains inconsistent {column}")
    if not pd.to_datetime(frame["timestamp"], errors="coerce").notna().all():
        raise SchemaMismatchError(f"{split} contains invalid timestamps")
