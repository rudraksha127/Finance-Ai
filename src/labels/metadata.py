"""Label metadata + versioning (LABEL_GENERATION_BLUEPRINT.md sections 17-18).

``label_set_version = v{major}.{minor}`` (blueprint 17.1). The version
hash (17.2) is a deterministic SHA-256 over the target definition:
label type, horizon, thresholds and cost-awareness. Changing any of
those produces a new hash and must produce a new label version.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

LABEL_SET_VERSION = "v0.1"
LABEL_TYPE = "classification"
DEFAULT_HORIZON = 5
DEFAULT_THRESHOLD_UP = 0.01
DEFAULT_THRESHOLD_DOWN = 0.01


@dataclass(frozen=True)
class LabelSetMetadata:
    """Metadata for one generated label set (blueprint section 18.1)."""

    # Identity
    label_id: str  # e.g. "direction_v0.1"
    label_version: str
    version_hash: str
    # Definition
    label_name: str  # "direction"
    target_type: str  # "classification"
    horizon: int  # trading days
    horizon_unit: str  # "trading_days"
    # Thresholds
    threshold_up: float
    threshold_down: float
    # Source
    source_column: str
    source_file: str
    source_checksum: str
    # Generation
    generation_rule: str
    generated_at: str
    # Distribution
    total_rows: int
    valid_rows: int
    up_count: int
    down_count: int
    hold_count: int
    invalid_count: int
    # Status
    status: str  # "active"


def compute_label_version_hash(
    *,
    horizon: int,
    threshold_up: float,
    threshold_down: float,
    price_column: str,
    label_type: str = LABEL_TYPE,
    cost_aware: bool = False,
) -> str:
    """Deterministic SHA-256 of the target definition (blueprint 17.2)."""
    version_input = {
        "label_type": label_type,
        "label_window": horizon,
        "thresholds": {"up": threshold_up, "down": threshold_down},
        "cost_aware": cost_aware,
        "price_column": price_column,
    }
    encoded = json.dumps(version_input, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def label_metadata(
    *,
    version: str,
    version_hash: str,
    ticker: str,
    horizon: int,
    threshold_up: float,
    threshold_down: float,
    source_column: str,
    source_file: str,
    source_checksum: str,
    distribution,
    now: datetime,
) -> LabelSetMetadata:
    """Build metadata for a generated label set."""
    return LabelSetMetadata(
        label_id=f"direction_{version}",
        label_version=version,
        version_hash=version_hash,
        label_name="direction",
        target_type=LABEL_TYPE,
        horizon=horizon,
        horizon_unit="trading_days",
        threshold_up=threshold_up,
        threshold_down=threshold_down,
        source_column=source_column,
        source_file=source_file,
        source_checksum=source_checksum,
        generation_rule=(
            f"future_return=(price_{{t+{horizon}}}-price_t)/price_t; "
            f"UP if > {threshold_up}, DOWN if < -{threshold_down}, else HOLD"
        ),
        generated_at=now.isoformat(),
        total_rows=distribution.total_rows,
        valid_rows=distribution.valid_rows,
        up_count=distribution.up_count,
        down_count=distribution.down_count,
        hold_count=distribution.hold_count,
        invalid_count=distribution.invalid_count,
        status="active",
    )


def metadata_to_dict(metadata: LabelSetMetadata) -> dict[str, Any]:
    """Serialize to JSON-safe mapping."""
    return asdict(metadata)
