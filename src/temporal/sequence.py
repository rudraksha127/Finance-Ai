"""Sequence builder for the temporal model (Post-MVP Milestone 06).

Builds causal input sequences for the temporal LSTM from a chronologically
ordered dataset split. For a sequence ending at row T:

    sequence = feature rows [T-L+1 ... T]   (features only)
    target   = label at row T               (encodes Y(T+H) from the label engine)

Leakage invariants (docs/TEMPORAL_MODEL_IMPLEMENTATION.md section 4):

- a sequence may only contain observations <= T (no centered windows);
- no future-fill: missing feature values fail loudly instead of being filled;
- sequences are built strictly within ONE frame (one split), so no sequence
  crosses a train/validation/test boundary (split isolation);
- the first ``L-1`` rows of a frame are context-only and yield no sequence.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.model.loader import CLASSES


class SequenceError(ValueError):
    """Raised when a frame cannot be converted into valid sequences."""


class InsufficientSequenceError(SequenceError):
    """Raised when a frame has fewer rows than the configured sequence length."""


@dataclass(frozen=True)
class Sequences:
    """Causal sequences plus their targets and sequence-end timestamps."""

    X: np.ndarray  # (n, L, F) float64
    y: np.ndarray  # (n,) object labels from CLASSES
    timestamps: np.ndarray  # (n,) sequence-end timestamps (datetime64)
    sequence_length: int
    feature_names: tuple[str, ...]

    def __len__(self) -> int:
        return int(self.X.shape[0])


def build_sequences(
    frame: pd.DataFrame,
    *,
    feature_names: tuple[str, ...],
    sequence_length: int,
) -> Sequences:
    """Build causal sequences ending at each eligible row of ``frame``.

    The frame must be one chronological split. Rows ``[L-1 ... n-1]`` each yield
    one sequence of exactly ``sequence_length`` rows ending at that row; the
    target is the label of the sequence-end row (the same target the baseline
    model uses).

    Raises:
        SequenceError: unsorted timestamps, missing columns, non-finite or
            missing feature values, invalid labels.
        InsufficientSequenceError: fewer rows than ``sequence_length``.
    """
    if sequence_length < 1:
        raise SequenceError(f"sequence_length must be >= 1, got {sequence_length}")
    if frame.empty:
        raise SequenceError("cannot build sequences from an empty frame")
    if len(frame) < sequence_length:
        raise InsufficientSequenceError(
            f"frame has {len(frame)} rows; sequence_length {sequence_length} "
            "requires at least that many rows in one split"
        )

    missing = [column for column in feature_names if column not in frame.columns]
    if missing:
        raise SequenceError(f"frame is missing feature columns: {missing}")
    if "timestamp" not in frame.columns or "label" not in frame.columns:
        raise SequenceError("frame must contain 'timestamp' and 'label' columns")

    timestamps = pd.to_datetime(frame["timestamp"]).to_numpy()
    if np.any(timestamps[1:] < timestamps[:-1]):
        raise SequenceError("frame timestamps must be sorted chronologically (no future rows)")

    values = frame[list(feature_names)].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise SequenceError(
            "feature matrix contains NaN/Inf; the temporal builder never "
            "future-fills missing values"
        )

    labels = frame["label"].to_numpy()
    invalid = ~np.isin(labels, list(CLASSES))
    if invalid.any():
        raise SequenceError(f"labels outside {CLASSES} at {int(invalid.sum())} row(s)")

    # Causal windows: sequence i ends at row (L-1+i) and contains rows
    # [i ... i+L-1] — strictly observations <= the sequence-end timestamp.
    n = len(frame)
    windows = np.stack([values[i : i + sequence_length] for i in range(n - sequence_length + 1)])
    return Sequences(
        X=windows,
        y=labels[sequence_length - 1 :],
        timestamps=timestamps[sequence_length - 1 :],
        sequence_length=sequence_length,
        feature_names=tuple(feature_names),
    )
