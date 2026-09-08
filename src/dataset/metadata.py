"""Dataset metadata + versioning (DATASET_BUILDER_BLUEPRINT.md sections 6/8).

The dataset version hash is a deterministic SHA-256 over the full build
identity: feature/label versions, per-ticker source checksums, config
snapshot, feature names, split ratios/boundaries and record counts.
Any material change (source data, feature set, labels, split or filter
policy) changes the hash; a new dataset version must be created.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class DatasetMetadata:
    """Blueprint section 8.1 metadata for one dataset version."""

    # Identity
    version: str
    version_hash: str
    # Source versions
    feature_version: str
    label_version: str
    source_versions: dict[str, str]  # ticker -> source checksum (short)
    # Creation
    created_at: str
    created_by: str
    config_snapshot: dict[str, Any]
    # Features
    feature_names: tuple[str, ...]
    feature_count: int
    # Record counts (usable rows before split; splits after purge/embargo)
    total_rows: int
    train_rows: int
    val_rows: int
    test_rows: int
    # Split boundaries (inclusive ISO or None)
    train_start: str | None
    train_end: str | None
    val_start: str | None
    val_end: str | None
    test_start: str | None
    test_end: str | None
    # Quality
    nan_count_total: int
    label_distribution: dict[str, int]
    quality_score: float
    quality_rating: str
    # Build report (drops accounting)
    input_rows: int
    dropped_warmup: int
    dropped_invalid_label: int
    dropped_out_of_range: int
    dropped_unmatched: int = 0
    missing_feature_count: int = 0
    missing_label_count: int = 0
    # File references
    train_file: str = ""
    val_file: str = ""
    test_file: str = ""


@dataclass(frozen=True)
class DatasetManifest:
    """Machine-readable manifest (milestone section 18)."""

    dataset_version: str
    version_hash: str
    source_versions: dict[str, str]
    feature_version: str
    label_version: str
    generation_time: str
    generation_code_version: str
    row_counts: dict[str, int]
    instruments: list[str]
    intervals: list[str]
    date_range: dict[str, str | None]
    split_boundaries: dict[str, str | None]
    split_row_counts: dict[str, int]
    feature_count: int
    target_definition: dict[str, Any]
    quality_summary: dict[str, Any]
    build_report: dict[str, int]
    checksums: dict[str, str] = field(default_factory=dict)


def compute_dataset_version_hash(
    *,
    feature_version: str,
    label_version: str,
    source_versions: dict[str, str],
    config: dict[str, Any],
    feature_names: tuple[str, ...],
    split_boundaries: dict[str, str | None],
    record_counts: dict[str, int],
) -> str:
    """Deterministic SHA-256 of the dataset definition (blueprint 6.2)."""
    version_input = {
        "feature_version": feature_version,
        "label_version": label_version,
        "source_versions": source_versions,
        "config": config,
        "feature_names": sorted(feature_names),
        "split_boundaries": split_boundaries,
        "record_counts": record_counts,
    }
    encoded = json.dumps(version_input, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def metadata_to_dict(metadata: DatasetMetadata) -> dict[str, Any]:
    """Serialize metadata to a JSON-safe mapping."""
    data = asdict(metadata)
    data["feature_names"] = list(metadata.feature_names)
    return data


def manifest_to_dict(manifest: DatasetManifest) -> dict[str, Any]:
    """Serialize the manifest to a JSON-safe mapping."""
    return asdict(manifest)
