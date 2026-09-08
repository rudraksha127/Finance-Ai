"""Feature persistence (FEATURE_ENGINEERING_BLUEPRINT.md section 18).

Storage layout (``data/processed/features/``):

- ``features_{version}_{TICKER}.parquet`` — per-ticker feature frame
- ``features_{version}_{TICKER}.metadata.json`` — feature-set metadata
- ``features_{version}_{TICKER}.hash.txt`` — deterministic version hash

Parquet is written atomically (tmp + rename). Existing outputs are
never silently replaced: an identical re-generation is a safe no-op,
a *different* output for the same version/ticker raises
:class:`FeatureStorageConflictError` (reproducibility contract).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.core.errors import StorageError
from src.features.metadata import FeatureSetMetadata, metadata_to_dict


class FeatureStorageConflictError(StorageError):
    """A feature dataset already exists with materially different content."""


def features_dir(processed_dir: Path) -> Path:
    """The ``data/processed/features`` directory."""
    return processed_dir / "features"


def feature_file_path(processed_dir: Path, version: str, ticker: str) -> Path:
    """Canonical Parquet path for a feature dataset."""
    return features_dir(processed_dir) / f"features_{version}_{ticker}.parquet"


def metadata_file_path(processed_dir: Path, version: str, ticker: str) -> Path:
    """Canonical JSON metadata path for a feature dataset."""
    return features_dir(processed_dir) / f"features_{version}_{ticker}.metadata.json"


def hash_file_path(processed_dir: Path, version: str, ticker: str) -> Path:
    """Canonical version-hash path for a feature dataset."""
    return features_dir(processed_dir) / f"features_{version}_{ticker}.hash.txt"


def write_features(
    processed_dir: Path,
    frame: pd.DataFrame,
    *,
    version: str,
    ticker: str,
    metadata: FeatureSetMetadata,
    output_format: str = "parquet",
) -> Path:
    """Persist a feature frame + metadata + hash, never silently replacing.

    Returns the written Parquet path.

    Raises:
        FeatureStorageConflictError: if the target already exists with
            different content (same version must imply same data).
    """
    target = feature_file_path(processed_dir, version, ticker)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise StorageError(f"cannot create feature directory {target.parent}: {error}") from error

    if output_format == "parquet":
        buffer = frame.to_parquet(index=True, engine="pyarrow")
    else:  # csv (fallback for constrained environments)
        buffer = frame.to_csv(index=True).encode("utf-8")

    existing = target.read_bytes() if target.exists() else None
    if existing is not None and existing != buffer:
        raise FeatureStorageConflictError(
            f"feature dataset {target} already exists with different content; "
            f"bump the feature-set version instead of overwriting",
            context={"path": str(target), "version": version, "ticker": ticker},
        )
    if existing is None:
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(buffer)
        tmp.replace(target)

    metadata_path = metadata_file_path(processed_dir, version, ticker)
    metadata_path.write_text(
        json.dumps(metadata_to_dict(metadata), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    hash_path = hash_file_path(processed_dir, version, ticker)
    hash_path.write_text(metadata.version_hash + "\n", encoding="utf-8")

    return target


def read_features(path: Path) -> pd.DataFrame:
    """Load a persisted feature frame (timestamp index)."""
    try:
        if path.suffix == ".parquet":
            return pd.read_parquet(path, engine="pyarrow")
        return pd.read_csv(path, index_col=0, parse_dates=True)
    except (OSError, ValueError) as error:
        raise StorageError(f"cannot read feature file {path}: {error}") from error


def read_metadata(path: Path) -> dict[str, Any]:
    """Load a persisted feature metadata JSON."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise StorageError(f"cannot read feature metadata {path}: {error}") from error


def sha256_of(path: Path) -> str:
    """SHA-256 of a file's bytes (source traceability)."""
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as error:
        raise StorageError(f"cannot hash {path}: {error}") from error
