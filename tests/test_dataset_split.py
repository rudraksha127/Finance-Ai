"""Dataset split-engine tests (DATASET_BUILDER_BLUEPRINT.md sections 3/5)."""

from __future__ import annotations

import pandas as pd
import pytest

from src.dataset.errors import SplitConfigurationError
from src.dataset.split import (
    SPLIT_NAMES,
    ChronologicalSplit,
    apply_embargo,
    compute_split_sizes,
    split_chronologically,
)

RATIOS = {"train": 0.7, "val": 0.15, "test": 0.15}


def _frame(rows: int, *, start: str = "2025-01-02", ticker: str = "AAPL") -> pd.DataFrame:
    """Deterministic sorted frame with business-day timestamps + labels."""
    timestamps = pd.date_range(start, periods=rows, freq="B")
    n = len(timestamps)
    # Mix classes deterministically so DVAL-08 never trips at the unit level.
    labels = ["HOLD", "UP", "DOWN"] * (n // 3 + 1)
    return pd.DataFrame(
        {
            "ticker": ticker,
            "timestamp": timestamps,
            "label": labels[:n],
            "future_return": 0.0,
            # target strictly after the observation
            "target_timestamp": timestamps.shift(-1, freq="B"),
        }
    )


# ---------------------------------------------------------------------------
# compute_split_sizes
# ---------------------------------------------------------------------------
def test_split_sizes_floor_and_remainder():
    sizes = compute_split_sizes(1000, RATIOS)
    assert sizes == (700, 150, 150)
    assert sum(sizes) == 1000
    sizes = compute_split_sizes(10, RATIOS)
    assert sizes == (7, 1, 2)  # train=floor(1.5)=1 -> test gets the remainder
    assert sum(sizes) == 10


def test_split_sizes_zero_rows():
    assert compute_split_sizes(0, RATIOS) == (0, 0, 0)


def test_split_sizes_reject_negative_rows():
    with pytest.raises(SplitConfigurationError):
        compute_split_sizes(-1, RATIOS)


def test_split_sizes_reject_impossible_ratios():
    with pytest.raises(SplitConfigurationError):
        compute_split_sizes(10, {"train": 5.0, "val": 0.15, "test": 0.15})


# ---------------------------------------------------------------------------
# chronological splitting
# ---------------------------------------------------------------------------
def test_split_contiguous_and_non_overlapping():
    frame = _frame(300)
    split: ChronologicalSplit = split_chronologically(frame, ratios=RATIOS)
    assert len(split.train) == 210
    assert len(split.val) == 45
    assert len(split.test) == 45

    # Contiguous: no rows lost, no rows duplicated across splits.
    all_rows = pd.concat([split.train, split.val, split.test])
    assert len(all_rows) == 300
    assert all_rows.duplicated(subset=["timestamp", "ticker"]).sum() == 0

    # Chronological ordering preserved per split and across splits.
    for part in (split.train, split.val, split.test):
        assert part["timestamp"].is_monotonic_increasing
    assert split.train["timestamp"].max() < split.val["timestamp"].min()
    assert split.val["timestamp"].max() < split.test["timestamp"].min()


def test_split_boundaries_recorded():
    frame = _frame(300, start="2025-01-02")
    split: ChronologicalSplit = split_chronologically(frame, ratios=RATIOS)
    expected = {
        "train_start": "2025-01-02T00:00:00",
        "train_end": split.train["timestamp"].max().isoformat(),
        "val_start": split.val["timestamp"].min().isoformat(),
        "val_end": split.val["timestamp"].max().isoformat(),
        "test_start": split.test["timestamp"].min().isoformat(),
        "test_end": split.test["timestamp"].max().isoformat(),
    }
    assert split.boundaries.to_dict() == expected


def test_multi_ticker_each_instrument_split_and_non_overlapping():
    # Two instruments spanning the SAME date range: splitting the concatenated
    # frame by row index would put identical timestamps in two splits. Each
    # instrument must receive its own chronological split instead.
    aapl = _frame(300, ticker="AAPL")
    msft = _frame(300, ticker="MSFT")
    frame = pd.concat([aapl, msft], ignore_index=True)
    split: ChronologicalSplit = split_chronologically(frame, ratios=RATIOS)

    # Per-instrument ratio boundaries hold exactly (70/15/15 of 300 each).
    assert len(split.train) == 420  # 210 + 210
    assert len(split.val) == 90
    assert len(split.test) == 90
    for name in SPLIT_NAMES:
        part = getattr(split, name)
        assert sorted(part["ticker"].unique()) == ["AAPL", "MSFT"]
        assert part["timestamp"].is_monotonic_increasing
        counts = part.groupby("ticker").size()
        assert set(counts.index) == {"AAPL", "MSFT"}  # every ticker contributes

    # Global chronological isolation: no timestamps shared between splits.
    train_ts = set(split.train["timestamp"])
    val_ts = set(split.val["timestamp"])
    test_ts = set(split.test["timestamp"])
    assert train_ts.isdisjoint(val_ts)
    assert val_ts.isdisjoint(test_ts)
    assert split.train["timestamp"].max() < split.val["timestamp"].min()
    assert split.val["timestamp"].max() < split.test["timestamp"].min()


def test_split_deterministic():
    frame = _frame(500)
    first = split_chronologically(frame, ratios=RATIOS)
    second = split_chronologically(frame, ratios=RATIOS)
    for name in SPLIT_NAMES:
        a = getattr(first, name)
        b = getattr(second, name)
        assert a.equals(b)


def test_split_empty_val_and_test_when_small():
    # 3 rows -> train=2, val=0, test=1 (floor math). Empty splits allowed
    # at the engine level; DVAL-07 warns downstream.
    frame = _frame(3)
    split = split_chronologically(frame, ratios=RATIOS)
    assert len(split.train) == 2
    assert len(split.val) == 0
    assert len(split.test) == 1
    assert split.boundaries.val_start is None
    assert split.boundaries.val_end is None


def test_split_never_random_input_unsorted():
    # Input order must not matter: split is computed on sorted order.
    frame = _frame(200).sample(frac=1.0, random_state=7)
    split = split_chronologically(frame, ratios=RATIOS)
    for part in (split.train, split.val, split.test):
        assert part["timestamp"].is_monotonic_increasing


def test_split_rejects_bad_ratios():
    with pytest.raises(SplitConfigurationError):
        split_chronologically(_frame(100), ratios={"train": 0.7, "val": 0.15})
    with pytest.raises(SplitConfigurationError):
        split_chronologically(_frame(100), ratios={"train": 0.8, "val": 0.15, "test": 0.15})
    with pytest.raises(SplitConfigurationError):
        split_chronologically(_frame(100), ratios={"train": 0.7, "val": 0.15, "test": 0.05})


def test_embargo_requires_non_negative_rows():
    with pytest.raises(SplitConfigurationError):
        apply_embargo(100, -1)


# ---------------------------------------------------------------------------
# purge (walk-forward knob; disabled for the static MVP split)
# ---------------------------------------------------------------------------
def test_static_split_without_purge_needs_none():
    """Contiguous per-instrument splits need no purge (blueprint 5.3).

    With row-based contiguous splits, no train row's label target reaches
    into the validation period, so purging changes nothing — this is why
    the MVP static split disables it (blueprint 5.3: daily static split).
    """
    frame = _frame(300)
    baseline = split_chronologically(frame, ratios=RATIOS)
    purged = split_chronologically(frame, ratios=RATIOS, purging_enabled=True)
    # No train target reaches the val start in a contiguous static split.
    val_start = baseline.val["timestamp"].min()
    targets = pd.to_datetime(baseline.train["target_timestamp"])
    assert (targets < val_start).all()
    assert len(purged.train) == len(baseline.train)
    assert len(purged.val) == len(baseline.val)
    assert len(purged.test) == len(baseline.test)


def test_purge_rule_drops_rows_whose_target_reaches_next_split():
    """The purge RULE (blueprint 5.1/5.4): a row whose label target reaches
    into the following split (target >= next split start) is dropped.

    This bites in time-based/walk-forward splits (a later milestone).
    Construct the boundary condition directly: an observation H sessions
    before a date-based val start has its target exactly at val_start.
    """
    from src.dataset.split import _purge

    # A Monday boundary: the purge rule must catch targets landing exactly
    # on the next split's start (target >= next start).
    train = _frame(60, start="2025-03-03")  # business days
    train["target_timestamp"] = pd.Timestamp("2025-06-02")
    baseline = len(train)
    val = _frame(10, start="2025-06-02")

    purged = _purge(train, val)
    assert len(purged) == 0  # every train label overlaps the next split

    # Non-overlapping targets survive.
    train["target_timestamp"] = pd.Timestamp("2025-05-30")
    kept = _purge(train, val)
    assert len(kept) == baseline


def test_purge_without_target_timestamp_rejected():
    frame = _frame(100).drop(columns=["target_timestamp"])
    with pytest.raises(SplitConfigurationError):
        split_chronologically(frame, ratios=RATIOS, purging_enabled=True)


def test_embargo_creates_gap_between_splits():
    frame = _frame(300)
    baseline = split_chronologically(frame, ratios=RATIOS)
    gapped = split_chronologically(frame, ratios=RATIOS, embargo_enabled=True, embargo_rows=5)

    # Gap rows are excluded from later splits.
    total_rows = len(gapped.train) + len(gapped.val) + len(gapped.test)
    assert total_rows == 300 - 10  # 5 rows skipped before val and before test

    # Boundary gap is real (not merely equal to the un-embargoed boundary).
    assert baseline.val["timestamp"].min() < gapped.val["timestamp"].min()


def test_purge_and_embargo_compose():
    frame = _frame(600)
    result = split_chronologically(
        frame,
        ratios=RATIOS,
        purging_enabled=True,
        embargo_enabled=True,
        embargo_rows=3,
    )
    # Ordering invariants hold under both policies.
    assert result.train["timestamp"].max() < result.val["timestamp"].min()
    assert result.val["timestamp"].max() < result.test["timestamp"].min()
    for part in (result.train, result.val, result.test):
        assert part["timestamp"].is_monotonic_increasing
