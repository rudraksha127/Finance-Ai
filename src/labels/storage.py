"""Label persistence (LABEL_GENERATION_BLUEPRINT.md sections 18-19).

Storage layout (``data/processed/labels/``):

- ``labels_{version}_{TICKER}.parquet`` — label frame (timestamp index:
  observation_timestamp, target_timestamp, future_return, label, status)
- ``labels_{version}_{TICKER}.metadata.json`` — :class:`LabelSetMetadata`
- ``labels_{version}_{TICKER}.hash.txt`` — deterministic version hash

Identical re-generation is a byte-stable no-op; a materially different
label set for the same version raises :class:`LabelStorageConflictError`
— bump the label version instead of silently replacing (idempotency +
reproducibility contract).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.core.errors import StorageError
from src.labels.metadata import LabelSetMetadata, metadata_to_dict


class LabelStorageConflictError(StorageError):
    """A label set already exists with materially different content."""


def labels_dir(processed_dir: Path) -> Path:
    """The ``data/processed/labels`` directory."""
    return processed_dir / "labels"


def label_file_path(processed_dir: Path, version: str, ticker: str) -> Path:
    return labels_dir(processed_dir) / f"labels_{version}_{ticker}.parquet"


def metadata_file_path(processed_dir: Path, version: str, ticker: str) -> Path:
    return labels_dir(processed_dir) / f"labels_{version}_{ticker}.metadata.json"


def hash_file_path(processed_dir: Path, version: str, ticker: str) -> Path:
    return labels_dir(processed_dir) / f"labels_{version}_{ticker}.hash.txt"


def write_labels(
    processed_dir: Path,
    frame: pd.DataFrame,
    *,
    version: str,
    ticker: str,
    metadata: LabelSetMetadata,
    output_format: str = "parquet",
) -> Path:
    """Persist a label frame + metadata + hash, never silently replacing."""
    target = label_file_path(processed_dir, version, ticker)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise StorageError(f"cannot create label directory {target.parent}: {error}") from error

    if output_format == "parquet":
        buffer = frame.to_parquet(index=True, engine="pyarrow")
    else:
        buffer = frame.to_csv(index=True).encode("utf-8")

    existing = target.read_bytes() if target.exists() else None
    if existing is not None and existing != buffer:
        raise LabelStorageConflictError(
            f"label set {target} already exists with different content; "
            f"bump the label version instead of overwriting",
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


def read_labels(path: Path) -> pd.DataFrame:
    """Load a persisted label frame (timestamp index)."""
    try:
        if path.suffix == ".parquet":
            return pd.read_parquet(path, engine="pyarrow")
        return pd.read_csv(path, index_col=0, parse_dates=True)
    except (OSError, ValueError) as error:
        raise StorageError(f"cannot read label file {path}: {error}") from error


def read_metadata(path: Path) -> dict[str, Any]:
    """Load a persisted label metadata JSON."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise StorageError(f"cannot read label metadata {path}: {error}") from error


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
