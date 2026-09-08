"""Chronological split engine (DATASET_BUILDER_BLUEPRINT.md sections 3/5).

- Splits are computed on rows sorted by (timestamp, ticker) — **never
  random** (ADR-0004). Ratios come from ``dataset.split_ratios``.
- With multiple instruments, the split is applied **per ticker**: each
  instrument's own ascending series is split at the same ratio row
  boundaries (blueprint 3.3) and the results are concatenated. This keeps
  chronological isolation between splits for multi-ticker datasets where
  every instrument spans the same date range (a row-based cut across the
  concatenated frame would place identical timestamps in two splits).
- Split boundaries are recorded (start/end per split) and the splits are
  contiguous unless purge/embargo is enabled.
- MVP static split: **no purge, no embargo** (blueprint 5.3 — static split
  observations do not overlap). Purge/embargo are implemented and
  config-gated for the walk-forward/backtest engine (later milestone),
  where overlapping label windows require them.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.dataset.errors import SplitConfigurationError

SPLIT_NAMES = ("train", "val", "test")


@dataclass(frozen=True)
class SplitBoundaries:
    """Inclusive (start, end) observation timestamps per split (None if empty)."""

    train_start: object
    train_end: object
    val_start: object
    val_end: object
    test_start: object
    test_end: object

    def to_dict(self) -> dict[str, str | None]:
        return {
            "train_start": _iso(self.train_start),
            "train_end": _iso(self.train_end),
            "val_start": _iso(self.val_start),
            "val_end": _iso(self.val_end),
            "test_start": _iso(self.test_start),
            "test_end": _iso(self.test_end),
        }


@dataclass(frozen=True)
class ChronologicalSplit:
    """The dataset split into (feature/label) frames + recorded boundaries."""

    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame
    boundaries: SplitBoundaries


def compute_split_sizes(n_rows: int, ratios: dict[str, float]) -> tuple[int, int, int]:
    """Row counts from ratios: train=floor(N*t), val=floor(N*v), test=rest."""
    if n_rows < 0:
        raise SplitConfigurationError(
            f"cannot split negative row count {n_rows}", context={"rows": n_rows}
        )
    train = int(n_rows * ratios["train"])
    val = int(n_rows * ratios["val"])
    test = n_rows - train - val
    if train < 0 or val < 0 or test < 0:
        raise SplitConfigurationError(
            "split ratios produced negative counts; ratios must be within [0, 1] " "and sum to 1",
            context={"ratios": ratios, "rows": n_rows},
        )
    return train, val, test


def split_chronologically(
    frame: pd.DataFrame,
    *,
    ratios: dict[str, float],
    purging_enabled: bool = False,
    embargo_enabled: bool = False,
    embargo_rows: int = 0,
) -> ChronologicalSplit:
    """Split a sorted dataset frame into TRAIN / VAL / TEST.

    Args:
        frame: rows sorted by (timestamp, ticker); must contain ``timestamp``.
        ratios: train/val/test summing to 1.
        purging_enabled: drop earlier-split rows whose ``target_timestamp``
            reaches into the following split (blueprint 5.1). Requires a
            ``target_timestamp`` column.
        embargo_enabled / embargo_rows: exclude the first ``embargo_rows``
            rows of each later split (gap between splits).

    Returns:
        :class:`ChronologicalSplit` (frames reset to a RangeIndex).
    """
    expected = {"train", "val", "test"}
    if set(ratios) != expected:
        raise SplitConfigurationError(
            f"split ratios must define exactly {sorted(expected)}",
            context={"ratios": ratios},
        )
    total = sum(ratios.values())
    if abs(total - 1.0) > 1e-6:
        raise SplitConfigurationError(
            f"split ratios must sum to 1.0 (got {total})", context={"ratios": ratios}
        )
    if embargo_rows < 0:
        raise SplitConfigurationError("embargo rows must be >= 0", context={"rows": embargo_rows})
    if purging_enabled and "target_timestamp" not in frame.columns:
        raise SplitConfigurationError(
            "purging requires a target_timestamp column (generated labels)",
            context={},
        )

    ordered = frame.sort_values(by=["timestamp", "ticker"]).reset_index(drop=True)
    # Multi-ticker: split each instrument at the same row boundaries, then
    # concatenate. Single-ticker frames behave exactly like blueprint 3.3.
    if "ticker" in ordered.columns:
        instrument_names = ordered["ticker"].unique()
        parts: dict[str, list[pd.DataFrame]] = {"train": [], "val": [], "test": []}
        for instrument in instrument_names:
            one = ordered[ordered["ticker"] == instrument].reset_index(drop=True)
            train, val, test = _split_one(one, ratios, embargo_enabled, embargo_rows)
            parts["train"].append(train)
            parts["val"].append(val)
            parts["test"].append(test)
        train = _concat(parts["train"])
        val = _concat(parts["val"])
        test = _concat(parts["test"])
    else:
        train, val, test = _split_one(ordered, ratios, embargo_enabled, embargo_rows)

    if purging_enabled:
        train = _purge(train, val)
        val = _purge(val, test)

    return ChronologicalSplit(
        train=train.reset_index(drop=True),
        val=val.reset_index(drop=True),
        test=test.reset_index(drop=True),
        boundaries=SplitBoundaries(
            train_start=_first(train),
            train_end=_last(train),
            val_start=_first(val),
            val_end=_last(val),
            test_start=_first(test),
            test_end=_last(test),
        ),
    )


def _split_one(
    ordered: pd.DataFrame,
    ratios: dict[str, float],
    embargo_enabled: bool,
    embargo_rows: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split one sorted (per-instrument) frame at ratio row boundaries."""
    n = len(ordered)
    train_size, val_size, _test_size = compute_split_sizes(n, ratios)

    train_end = train_size
    val_end = train_end + val_size
    val_start = apply_embargo(train_end, embargo_rows) if embargo_enabled else train_end
    test_start = apply_embargo(val_end, embargo_rows) if embargo_enabled else val_end

    return (
        ordered.iloc[:train_end].copy(),
        ordered.iloc[val_start:val_end].copy(),
        ordered.iloc[test_start:n].copy(),
    )


def _concat(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame()
    result = pd.concat(frames, ignore_index=True)
    # The concatenated per-ticker split is already chronologically ordered:
    # re-sort for a deterministic global (timestamp, ticker) order.
    return result.sort_values(by=["timestamp", "ticker"]).reset_index(drop=True)


def apply_embargo(start_index: int, embargo_rows: int) -> int:
    """Advance a split start by ``embargo_rows`` (creates the inter-split gap)."""
    if embargo_rows < 0:
        raise SplitConfigurationError("embargo rows must be >= 0", context={"rows": embargo_rows})
    return start_index + embargo_rows


def _purge(split: pd.DataFrame, next_split: pd.DataFrame) -> pd.DataFrame:
    """Drop rows whose label target reaches into the following split.

    Purge rule (blueprint 5.1/5.4): drop rows where
    ``target_timestamp >= next split start``. Rows without a target
    timestamp are kept (no purge signal).
    """
    if split.empty or next_split.empty:
        return split
    if "target_timestamp" not in split.columns:
        return split
    next_start = next_split["timestamp"].iloc[0]
    targets = pd.to_datetime(split["target_timestamp"], errors="coerce")
    return split[targets < next_start].copy()


def _first(frame: pd.DataFrame):
    return frame["timestamp"].iloc[0] if not frame.empty else None


def _last(frame: pd.DataFrame):
    return frame["timestamp"].iloc[-1] if not frame.empty else None


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None
