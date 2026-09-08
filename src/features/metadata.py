"""Feature metadata + versioning (FEATURE_ENGINEERING_BLUEPRINT.md sections 16-17).

Every generated feature dataset identifies its feature-set version and a
deterministic SHA-256 of the feature configuration. Changing any feature
definition, the feature list, or the version bumps the hash; an existing
feature-set is never silently replaced (storage layer enforces this).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from src.features.registry import FEATURE_SET_VERSION, FEATURES

VERSION_PATTERN = r"^v\d+\.\d+$"


@dataclass(frozen=True)
class FeatureSetMetadata:
    """Metadata for one persisted feature dataset (blueprint section 17.1)."""

    feature_set_version: str
    version_hash: str
    feature_count: int
    ticker: str
    source_file: str
    source_checksum: str
    row_count: int
    feature_columns: tuple[str, ...]
    generated_at: str
    status: str = "active"


def compute_feature_version_hash(
    feature_names: tuple[str, ...],
    config: dict[str, Any] | None = None,
) -> str:
    """Deterministic SHA-256 of the feature-set definition (blueprint 16.3).

    Any change to the feature list, per-feature definition, or config
    produces a different hash.
    """
    version_input = {
        "feature_set_version": FEATURE_SET_VERSION,
        "feature_specs": [
            {
                "id": spec.feature_id,
                "name": spec.name,
                "formula": spec.formula,
                "lookback": spec.lookback,
                "version": spec.version,
            }
            for spec in FEATURES
        ],
        "config": config or {},
    }
    encoded = json.dumps(version_input, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def feature_set_metadata(
    *,
    version: str,
    version_hash: str,
    ticker: str,
    source_file: str,
    source_checksum: str,
    row_count: int,
    now: datetime,
) -> FeatureSetMetadata:
    """Build metadata for a generated feature dataset."""
    return FeatureSetMetadata(
        feature_set_version=version,
        version_hash=version_hash,
        feature_count=len(FEATURES),
        ticker=ticker,
        source_file=source_file,
        source_checksum=source_checksum,
        row_count=row_count,
        feature_columns=tuple(spec.name for spec in FEATURES),
        generated_at=now.isoformat(),
    )


def metadata_to_dict(metadata: FeatureSetMetadata) -> dict[str, Any]:
    """Serialize metadata to a JSON-safe mapping (tuples become lists)."""
    data = asdict(metadata)
    data["feature_columns"] = list(metadata.feature_columns)
    return data
