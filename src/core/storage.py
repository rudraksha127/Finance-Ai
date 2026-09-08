"""Raw / interim / processed storage layout.

Implements the directory part of the three-tier storage lifecycle
(DATA_ARCHITECTURE.md section 7.1):

- ``raw`` — immutable source data
- ``interim`` — regenerable intermediate results
- ``processed`` — versioned final artifacts

Only the *layout* is established here (directories + mapping). This
module deliberately creates no data files — fake or otherwise — and
performs no I/O beyond idempotent directory creation. The ``external``
directory is configured separately (it holds third-party reference
data, not a processing tier).

To keep the ``core`` package dependency-free, the storage tier
configuration is accepted structurally (any object exposing
``raw_dir``/``interim_dir``/``processed_dir`` — e.g. the config
package's ``DataConfig`` satisfies this protocol).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from src.core.enums import StorageTier
from src.core.errors import StorageError


class StoragePaths(Protocol):
    """Structural contract: the three storage-tier directories."""

    raw_dir: Path
    interim_dir: Path
    processed_dir: Path


_TIER_ATTRIBUTE: dict[StorageTier, str] = {
    StorageTier.RAW: "raw_dir",
    StorageTier.INTERIM: "interim_dir",
    StorageTier.PROCESSED: "processed_dir",
}


def tier_directory(paths: StoragePaths, tier: StorageTier) -> Path:
    """Return the configured directory for a storage tier.

    Raises:
        StorageError: for an unknown tier (defensive; the tier enum is
            closed by the architecture).
    """
    try:
        attribute = _TIER_ATTRIBUTE[tier]
    except KeyError:
        raise StorageError(f"unknown storage tier {tier!r}") from None
    return getattr(paths, attribute)


def ensure_data_directories(paths: StoragePaths) -> dict[StorageTier, Path]:
    """Create the three storage-tier directories (idempotent).

    Safe to call on every startup: existing directories are left
    untouched and no files are written inside them.

    Returns:
        Mapping of each storage tier to its (existing) directory.
    """
    result: dict[StorageTier, Path] = {}
    for tier in StorageTier:
        path = tier_directory(paths, tier)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise StorageError(
                f"could not create {tier.value} directory {path}",
                context={"path": str(path)},
            ) from error
        result[tier] = path
    return result
