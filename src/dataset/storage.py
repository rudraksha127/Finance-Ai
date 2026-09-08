"""Dataset persistence (DATASET_BUILDER_BLUEPRINT.md section 7.3).

Layout under ``data/processed/datasets/``:

    dataset_{version}/
        metadata.json       # blueprint 8.1 metadata
        manifest.json       # machine-readable manifest (milestone 18)
        feature_names.json  # ordered feature columns
        train.parquet       # TRAIN split
        val.parquet         # VAL split
        test.parquet        # TEST split
        hash.txt            # deterministic version hash

Immutability: a dataset version is written once. Rebuilding the identical
version is a safe no-op (byte-stable, hash match); building a *different*
dataset under an existing version raises :class:`DatasetAlreadyExistsError`
(never overwrite — bump the dataset version).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd

from src.dataset.errors import (
    DatasetAlreadyExistsError,
    DatasetDataNotFoundError,
    DatasetPersistenceError,
)
from src.dataset.metadata import (
    DatasetManifest,
    DatasetMetadata,
    manifest_to_dict,
    metadata_to_dict,
)


def datasets_dir(processed_dir: Path) -> Path:
    """``data/processed/datasets`` root."""
    return processed_dir / "datasets"


def dataset_dir(processed_dir: Path, version: str) -> Path:
    """``data/processed/datasets/dataset_{version}``."""
    return datasets_dir(processed_dir) / f"dataset_{version}"


def write_dataset(
    processed_dir: Path,
    *,
    version: str,
    metadata: DatasetMetadata,
    manifest: DatasetManifest,
    feature_names: tuple[str, ...],
    train: pd.DataFrame,
    val: pd.DataFrame,
    test: pd.DataFrame,
) -> Path:
    """Persist a dataset version immutably; identical rebuild = no-op.

    Returns the dataset directory.

    Raises:
        DatasetAlreadyExistsError: if the version exists with different
            content (same version must imply same data).
        DatasetPersistenceError: on I/O failure.
    """
    target = dataset_dir(processed_dir, version)
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise DatasetPersistenceError(f"cannot create {target}: {error}") from error

    existing_hash = _read_existing_hash(target)
    if existing_hash is not None:
        if existing_hash == metadata.version_hash:
            return target  # identical deterministic rebuild -> safe no-op
        raise DatasetAlreadyExistsError(
            f"dataset version {version} already exists with a different hash "
            f"({existing_hash[:12]} != {metadata.version_hash[:12]}); "
            f"bump the dataset version instead of overwriting",
            context={"version": version, "path": str(target)},
        )

    try:
        _atomic_write_json(target / "metadata.json", metadata_to_dict(metadata))
        _atomic_write_json(target / "feature_names.json", list(feature_names))
        for name, frame in (("train", train), ("val", val), ("test", test)):
            path = target / f"{name}.parquet"
            tmp = path.with_suffix(".parquet.tmp")
            frame.to_parquet(tmp, index=False, engine="pyarrow")
            tmp.replace(path)
        _atomic_write_text(target / "hash.txt", metadata.version_hash + "\n")
        artifact_checksums = {
            f"{name}.parquet": sha256_of(target / f"{name}.parquet")
            for name in ("train", "val", "test")
        }
        _atomic_write_json(
            target / "manifest.json",
            manifest_to_dict(replace(manifest, checksums=artifact_checksums)),
        )
    except OSError as error:
        raise DatasetPersistenceError(f"cannot write dataset {target}: {error}") from error
    return target


def load_dataset(processed_dir: Path, version: str) -> dict[str, Any]:
    """Load a persisted dataset version (metadata + split frames)."""
    directory = dataset_dir(processed_dir, version)
    if not directory.exists():
        raise DatasetDataNotFoundError(
            f"dataset version {version} not found under {directory}",
            context={"version": version, "path": str(directory)},
        )
    metadata_path = directory / "metadata.json"
    if not metadata_path.exists():
        raise DatasetDataNotFoundError(
            f"dataset {version} missing metadata.json", context={"version": version}
        )
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        frames = {
            name: pd.read_parquet(directory / f"{name}.parquet", engine="pyarrow")
            for name in ("train", "val", "test")
        }
    except (OSError, ValueError) as error:
        raise DatasetDataNotFoundError(f"cannot load dataset {version}: {error}") from error
    return {"metadata": metadata, "directory": directory, **frames}


def sha256_of(path: Path) -> str:
    """SHA-256 of a file's bytes (artifact integrity)."""
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as error:
        raise DatasetPersistenceError(f"cannot hash {path}: {error}") from error


def _read_existing_hash(directory: Path) -> str | None:
    hash_path = directory / "hash.txt"
    if not hash_path.exists():
        return None
    return hash_path.read_text(encoding="utf-8").strip() or None


def _atomic_write_json(path: Path, payload: Any) -> None:
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _atomic_write_text(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)
