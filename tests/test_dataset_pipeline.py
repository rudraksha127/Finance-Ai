"""Dataset Builder integration + mandatory leakage tests (blueprint section 4/16).

Runs the real Milestone-04 feature engine and Milestone-05 label engine on
deterministic cleaned fixtures, then builds a versioned dataset with the
Milestone-06 builder — including the mandatory dataset leakage tests:
Test A (temporal ordering), B (split isolation), C (label horizon),
D (future extension invariance), E (version integrity).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.config.loader import load_config
from src.dataset.builder import DatasetBuilder
from src.dataset.errors import (
    DatasetAlreadyExistsError,
    DatasetDataNotFoundError,
    FeatureVersionMismatchError,
    InvalidTimestampError,
    LabelVersionMismatchError,
    MissingFeatureError,
    MissingLabelError,
    SchemaMismatchError,
)
from src.dataset.storage import dataset_dir, load_dataset, sha256_of
from src.features.engine import FeatureEngine
from src.features.registry import FEATURE_COLUMNS
from src.labels.engine import LabelEngine
from tests.data_helpers import make_app_config

TICKERS = ("AAPL", "MSFT")


def write_cleaned_csv(tmp_path: Path, *, ticker: str, n: int = 150) -> Path:
    """Deterministic Milestone-03 cleaned interim CSV (weekday timestamps)."""
    interim = tmp_path / "interim"
    interim.mkdir(parents=True, exist_ok=True)
    start = date(2025, 1, 2)
    rows = []
    close = 100.0 + (0.0 if ticker == "AAPL" else 37.0)
    for i in range(n):
        day = start + timedelta(days=i + (i // 5) * 2)
        close = close * (1.0 + 0.004 * np.sin(i / 4.0)) + 0.05
        rows.append(
            {
                "ticker": ticker,
                "timestamp": f"{day}T00:00:00",
                "open": round(close - 0.2, 4),
                "high": round(close + 0.8, 4),
                "low": round(close - 0.8, 4),
                "close": round(close, 4),
                "adj_close": round(close, 4),
                "volume": int(1_000_000 + i * 1000),
                "raw_line": i + 2,
            }
        )
    path = interim / f"cleaned_20250315_{ticker}_daily.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


@pytest.fixture()
def config(tmp_path: Path):
    return make_app_config(tmp_path / "raw")


def build_feature_and_label_sets(config, tmp_path: Path, *, n: int = 150) -> dict[str, Path]:
    """Run the real M04/M05 engines per ticker; return {ticker: cleaned_path}."""
    cleaned: dict[str, Path] = {}
    for ticker in TICKERS:
        source = write_cleaned_csv(tmp_path, ticker=ticker, n=n)
        FeatureEngine(config).run(ticker, "1d", source=source)
        LabelEngine(config).run(ticker, "1d", source=source)
        cleaned[ticker] = source
    return cleaned


def _warmup_and_usable(config, tmp_path: Path, n: int) -> tuple[int, int]:
    """Warm-up + usable rows per ticker for THIS fixture series.

    Warm-up is not just the max lookback: any feature that is still NaN at
    row R (e.g. bb_squeeze needs 100 fully-filled bandwidth rows) extends
    it. Measured with an isolated probe config so no artifacts leak into
    the shared tmp processed directory.
    """
    probe_raw = tmp_path / "probe" / "raw"
    probe_config = make_app_config(probe_raw)
    source = write_cleaned_csv(probe_raw.parent, ticker="ZZZZ", n=n)
    result = FeatureEngine(probe_config).run("ZZZZ", "1d", source=source)
    warmup = result.warmup_rows
    return warmup, n - warmup - 5  # label horizon consumes the last 5 rows


# ---------------------------------------------------------------------------
# Controlled deterministic dataset build (integration)
# ---------------------------------------------------------------------------
def test_controlled_dataset_build(config, tmp_path: Path):
    n = 150
    build_feature_and_label_sets(config, tmp_path, n=n)
    warmup, usable_per_ticker = _warmup_and_usable(config, tmp_path, n)
    result = DatasetBuilder(config).run(tickers=list(TICKERS))

    assert result.total_rows == usable_per_ticker * len(TICKERS)
    assert result.dropped_warmup == warmup * len(TICKERS)
    # Labels: rows whose 5-day future window is missing (last 5 of 150).
    assert result.dropped_invalid_label == 5 * len(TICKERS)
    assert result.dropped_out_of_range == 0
    assert result.tickers == TICKERS
    assert result.feature_version == "v0.1"
    assert result.label_version == "v0.1"
    assert result.dataset_version == "v0.1"
    assert result.validation.passed  # no DVAL errors
    assert sum(result.split_rows.values()) == result.total_rows

    directory = dataset_dir(config.data.processed_dir, "v0.1")
    assert directory.exists()
    for name in (
        "metadata.json",
        "manifest.json",
        "feature_names.json",
        "train.parquet",
        "val.parquet",
        "test.parquet",
        "hash.txt",
    ):
        assert (directory / name).exists()

    stored = load_dataset(config.data.processed_dir, "v0.1")
    metadata = stored["metadata"]
    assert metadata["version"] == "v0.1"
    assert metadata["version_hash"] == result.version_hash
    assert metadata["feature_count"] == 52
    assert metadata["total_rows"] == result.total_rows
    assert metadata["train_rows"] == result.split_rows["train"]
    assert (directory / "hash.txt").read_text().strip() == result.version_hash
    manifest = json.loads((directory / "manifest.json").read_text())
    assert set(manifest["checksums"]) == {"train.parquet", "val.parquet", "test.parquet"}
    assert set(manifest["target_definition"]["class_distribution"]["counts"]) == {
        "UP",
        "DOWN",
        "HOLD",
    }


def test_dataset_rows_are_complete_and_chronological(config, tmp_path: Path):
    build_feature_and_label_sets(config, tmp_path)
    DatasetBuilder(config).run(tickers=list(TICKERS))
    stored = load_dataset(config.data.processed_dir, "v0.1")

    for name in ("train", "val", "test"):
        frame = stored[name]
        assert len(frame) == 0 or set(FEATURE_COLUMNS).issubset(frame.columns)
        assert frame["timestamp"].is_monotonic_increasing
        assert frame[list(FEATURE_COLUMNS)].isna().sum().sum() == 0  # DVAL-01
        assert frame["label"].notna().all()
        assert frame["target_timestamp"].notna().all()
        assert frame["feature_set_version"].eq("v0.1").all()
        assert frame["label_set_version"].eq("v0.1").all()
        assert frame["dataset_version"].eq("v0.1").all()


def test_deterministic_rebuild_identical_and_safe(config, tmp_path: Path):
    build_feature_and_label_sets(config, tmp_path)
    first = DatasetBuilder(config).run(tickers=list(TICKERS))
    directory = dataset_dir(config.data.processed_dir, "v0.1")
    hashes = {path.name: sha256_of(path) for path in directory.iterdir() if path.is_file()}

    second = DatasetBuilder(config).run(tickers=list(TICKERS))  # identical rebuild -> no-op
    assert second.version_hash == first.version_hash
    assert second.total_rows == first.total_rows
    # Byte-stable artifacts (only generation timestamp in metadata differs).
    for name, digest in hashes.items():
        if name != "metadata.json" and name != "manifest.json":
            assert sha256_of(directory / name) == digest


def test_different_content_same_version_refused(config, tmp_path: Path):
    build_feature_and_label_sets(config, tmp_path, n=150)
    DatasetBuilder(config).run(tickers=list(TICKERS))
    directory = dataset_dir(config.data.processed_dir, "v0.1")
    existing_hash = (directory / "hash.txt").read_text().strip()

    # A materially different build (extra ticker -> different rows/content)
    # under the same version must be refused, never silently overwritten.
    third = write_cleaned_csv(tmp_path, ticker="GOOG", n=150)
    FeatureEngine(config).run("GOOG", "1d", source=third)
    LabelEngine(config).run("GOOG", "1d", source=third)

    with pytest.raises(DatasetAlreadyExistsError):
        DatasetBuilder(config).run(tickers=["GOOG"])
    assert (directory / "hash.txt").read_text().strip() == existing_hash  # untouched


# ---------------------------------------------------------------------------
# Mandatory leakage tests (blueprint section 16)
# ---------------------------------------------------------------------------
def _built_dataset(config, tmp_path: Path):
    """Build feature/label sets and the dataset; return the stored splits."""
    build_feature_and_label_sets(config, tmp_path)
    DatasetBuilder(config).run(tickers=list(TICKERS))
    return load_dataset(config.data.processed_dir, "v0.1")


def test_a_temporal_ordering(config, tmp_path: Path):
    """Test A — no row may violate chronological ordering."""
    stored = _built_dataset(config, tmp_path)
    full = pd.concat([stored["train"], stored["val"], stored["test"]])
    timestamps = pd.to_datetime(full["timestamp"])
    assert timestamps.is_monotonic_increasing
    assert full.duplicated(subset=["ticker", "timestamp"]).sum() == 0


def test_b_split_isolation(config, tmp_path: Path):
    """Test B — train timestamps must not overlap val/test timestamps."""
    stored = _built_dataset(config, tmp_path)
    train_max = pd.to_datetime(stored["train"]["timestamp"]).max()
    val_min = pd.to_datetime(stored["val"]["timestamp"]).min()
    val_max = pd.to_datetime(stored["val"]["timestamp"]).max()
    test_min = pd.to_datetime(stored["test"]["timestamp"]).min()
    assert train_max < val_min
    assert val_max < test_min


def test_c_label_horizon_strictly_forward(config, tmp_path: Path):
    """Test C — target timestamps must remain strictly after observations,
    exactly H=5 sessions ahead in the source series (never less)."""
    cleaned_paths = build_feature_and_label_sets(config, tmp_path)
    DatasetBuilder(config).run(tickers=list(TICKERS))
    stored = load_dataset(config.data.processed_dir, "v0.1")
    source_ts = {
        ticker: pd.to_datetime(pd.read_csv(cleaned_paths[ticker])["timestamp"]).tolist()
        for ticker in TICKERS
    }
    timestamps_by_ticker: dict[str, dict] = {ticker: {} for ticker in TICKERS}
    for ticker in TICKERS:
        for i, ts in enumerate(source_ts[ticker]):
            timestamps_by_ticker[ticker][ts] = (
                source_ts[ticker][i + 5] if i + 5 < len(source_ts[ticker]) else None
            )

    for name in ("train", "val", "test"):
        frame = stored[name]
        obs = pd.to_datetime(frame["timestamp"])
        targets = pd.to_datetime(frame["target_timestamp"])
        assert (targets > obs).all()  # strictly after feature time T
        for ticker in TICKERS:
            rows = frame[frame["ticker"] == ticker]
            if rows.empty:
                continue
            # Every row's target = the 5th subsequent source observation.
            # Row positions are identical across tickers (same day series).
            expected = rows["timestamp"].map(
                lambda ts, _ticker=ticker: timestamps_by_ticker[_ticker].get(pd.Timestamp(ts))
            )
            assert (pd.to_datetime(expected) == pd.to_datetime(rows["target_timestamp"])).all()


def test_d_future_extension_invariance(config, tmp_path: Path):
    """Test D — appending future source data must not alter historical rows."""
    build_feature_and_label_sets(config, tmp_path, n=150)
    first = DatasetBuilder(config).run(tickers=list(TICKERS))
    base_dir = dataset_dir(config.data.processed_dir, "v0.1")
    # Snapshot historical rows from the initial build, keyed per ticker so
    # the invariance is compared on comparable per-instrument series.
    stored = load_dataset(config.data.processed_dir, "v0.1")
    historical = pd.concat([stored["train"], stored["val"], stored["test"]])
    cut = sorted(historical["timestamp"].unique())[len(historical["timestamp"].unique()) // 2]
    before = historical[historical["timestamp"] <= cut].set_index(["ticker", "timestamp"])[
        list(FEATURE_COLUMNS)
    ]

    # Extend both tickers with 30 more days of data and rebuild fresh
    # artifacts (new versions so the old dataset version is untouched).
    cleaned = {}
    for ticker in TICKERS:
        source = write_cleaned_csv(tmp_path, ticker=ticker, n=180)
        FeatureEngine(config).run(ticker, "1d", source=source, feature_version="v0.2")
        LabelEngine(config).run(ticker, "1d", source=source, label_version="v0.2")
        cleaned[ticker] = source
    DatasetBuilder(config).run(
        tickers=list(TICKERS),
        feature_version="v0.2",
        label_version="v0.2",
        dataset_version="v0.2",
    )
    extended_stored = load_dataset(config.data.processed_dir, "v0.2")
    extended_frame = pd.concat(
        [extended_stored["train"], extended_stored["val"], extended_stored["test"]]
    )
    after = extended_frame[extended_frame["timestamp"] <= cut].set_index(["ticker", "timestamp"])[
        list(FEATURE_COLUMNS)
    ]

    common = before.index.intersection(after.index)
    assert len(common) > 0
    pd.testing.assert_frame_equal(before.loc[common].sort_index(), after.loc[common].sort_index())
    # The original immutable dataset version was not modified by the extension.
    assert (base_dir / "hash.txt").read_text().strip() == first.version_hash


def test_e_version_integrity(config, tmp_path: Path):
    """Test E — every row carries the configured feature/label versions."""
    stored = _built_dataset(config, tmp_path)
    for name in ("train", "val", "test"):
        frame = stored[name]
        assert frame["feature_set_version"].eq("v0.1").all()
        assert frame["label_set_version"].eq("v0.1").all()
        assert frame["dataset_version"].eq("v0.1").all()
        assert frame["source_data_version"].str.len().eq(12).all()  # short source checksum
        # Target columns never leak into the feature columns (TEST E).
        assert not {"future_return", "target_timestamp"} & set(FEATURE_COLUMNS)


def test_a_b_c_splits_reload_consistently(config, tmp_path: Path):
    """Split files reload to the exact same rows (integrity of persistence)."""
    build_feature_and_label_sets(config, tmp_path)
    result = DatasetBuilder(config).run(tickers=list(TICKERS))
    stored = load_dataset(config.data.processed_dir, "v0.1")
    for name in ("train", "val", "test"):
        assert len(stored[name]) == result.split_rows[name]
        assert stored[name]["timestamp"].is_monotonic_increasing


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------
def test_build_without_artifacts_fails(config):
    with pytest.raises(DatasetDataNotFoundError):
        DatasetBuilder(config).run(tickers=["NOPE"])


def test_build_requires_matching_source_checksums(config, tmp_path: Path):
    # Features from one cleaned file, labels from a different one -> checksums
    # differ -> schema mismatch, never a silent misaligned join.
    source_a = write_cleaned_csv(tmp_path, ticker="AAPL", n=150)
    FeatureEngine(config).run("AAPL", "1d", source=source_a)
    source_b = write_cleaned_csv(tmp_path, ticker="AAPL", n=160)  # different bytes
    LabelEngine(config).run("AAPL", "1d", source=source_b)

    with pytest.raises(SchemaMismatchError):
        DatasetBuilder(config).run(tickers=["AAPL"])


def test_range_filtering_counts_dropped_rows(config, tmp_path: Path):
    # Usable rows start after warm-up (~row 118 of 150) + label horizon, so a
    # start cut inside the usable window drops some rows and keeps others.
    build_feature_and_label_sets(config, tmp_path, n=150)
    result = DatasetBuilder(config).run(tickers=list(TICKERS), start="2025-07-01")
    assert result.dropped_out_of_range > 0
    assert result.total_rows > 0
    # Every persisted observation is inside the requested range.
    stored = load_dataset(config.data.processed_dir, "v0.1")
    for name in ("train", "val", "test"):
        frame = stored[name]
        assert (pd.to_datetime(frame["timestamp"]) >= pd.Timestamp("2025-07-01")).all()


def test_start_after_end_rejected(config, tmp_path: Path):
    build_feature_and_label_sets(config, tmp_path)
    with pytest.raises(InvalidTimestampError):
        DatasetBuilder(config).run(tickers=list(TICKERS), start="2025-12-31", end="2025-01-01")


def test_invalid_date_rejected(config, tmp_path: Path):
    build_feature_and_label_sets(config, tmp_path)
    with pytest.raises(InvalidTimestampError):
        DatasetBuilder(config).run(tickers=list(TICKERS), start="not-a-date")


def test_no_rows_after_filter_fails_loudly(config, tmp_path: Path):
    # A requested range with no overlap leaves zero rows -> explicit error,
    # never an empty dataset artifact.
    build_feature_and_label_sets(config, tmp_path)
    with pytest.raises(DatasetDataNotFoundError):
        DatasetBuilder(config).run(tickers=list(TICKERS), start="2030-01-01")


def test_ticker_auto_discovery(config, tmp_path: Path):
    # Without an explicit ticker list the builder discovers instruments that
    # have BOTH a feature set and a label set (resolved tickers, sorted).
    build_feature_and_label_sets(config, tmp_path)
    result = DatasetBuilder(config).run()
    assert result.tickers == TICKERS


def test_auto_discovery_without_pair_fails(config, tmp_path: Path):
    # Only a feature artifact (no matching label set) -> nothing discoverable.
    source = write_cleaned_csv(tmp_path, ticker="NFLX", n=150)
    FeatureEngine(config).run("NFLX", "1d", source=source)
    with pytest.raises(DatasetDataNotFoundError):
        DatasetBuilder(config).run()


def _rewrite_label_metadata(config, tmp_path: Path, ticker: str, **changes) -> None:
    """Patch a persisted label metadata file for mismatch tests."""
    import json

    from src.labels.storage import metadata_file_path

    path = metadata_file_path(config.data.processed_dir, "v0.1", ticker)
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata.update(changes)
    path.write_text(json.dumps(metadata), encoding="utf-8")


def _rewrite_feature_metadata(config, tmp_path: Path, ticker: str, **changes) -> None:
    """Patch a persisted feature metadata file for mismatch tests."""
    import json

    from src.features.storage import metadata_file_path as feature_metadata_path

    path = feature_metadata_path(config.data.processed_dir, "v0.1", ticker)
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata.update(changes)
    path.write_text(json.dumps(metadata), encoding="utf-8")


def test_feature_version_mismatch_fails(config, tmp_path: Path):
    # Metadata claims a different feature-set version than the artifact path
    # -> mismatch error, never a silent cross-version join.
    build_feature_and_label_sets(config, tmp_path)
    _rewrite_feature_metadata(config, tmp_path, "AAPL", feature_set_version="v9.9")
    with pytest.raises(FeatureVersionMismatchError):
        DatasetBuilder(config).run(tickers=["AAPL"])


def test_label_version_mismatch_fails(config, tmp_path: Path):
    build_feature_and_label_sets(config, tmp_path)
    _rewrite_label_metadata(config, tmp_path, "AAPL", label_version="v9.9")
    with pytest.raises(LabelVersionMismatchError):
        DatasetBuilder(config).run(tickers=["AAPL"])


def test_wrong_target_type_fails(config, tmp_path: Path):
    build_feature_and_label_sets(config, tmp_path)
    _rewrite_label_metadata(config, tmp_path, "AAPL", target_type="regression")
    with pytest.raises(LabelVersionMismatchError):
        DatasetBuilder(config).run(tickers=["AAPL"])


def test_wrong_horizon_fails(config, tmp_path: Path):
    build_feature_and_label_sets(config, tmp_path)
    _rewrite_label_metadata(config, tmp_path, "AAPL", horizon=99)
    with pytest.raises(LabelVersionMismatchError):
        DatasetBuilder(config).run(tickers=["AAPL"])


def test_missing_label_column_fails(config, tmp_path: Path):
    import pandas as pd

    from src.labels.storage import label_file_path

    build_feature_and_label_sets(config, tmp_path)
    labels = pd.read_parquet(label_file_path(config.data.processed_dir, "v0.1", "AAPL"))
    labels.drop(columns=["target_timestamp"]).to_parquet(
        label_file_path(config.data.processed_dir, "v0.1", "AAPL"), index=True
    )
    with pytest.raises(MissingLabelError):
        DatasetBuilder(config).run(tickers=["AAPL"])


def test_missing_feature_columns_fails(config, tmp_path: Path):
    # Metadata advertises a feature list that does not match the registered
    # 52-column schema -> MissingFeatureError, never a reindexed fill.
    build_feature_and_label_sets(config, tmp_path)
    _rewrite_feature_metadata(
        config, tmp_path, "AAPL", feature_columns=list(FEATURE_COLUMNS) + ["extra_52"]
    )
    with pytest.raises(MissingFeatureError):
        DatasetBuilder(config).run(tickers=["AAPL"])


def test_quality_below_gate_logs_warning_not_fail(config, tmp_path: Path):
    # A dataset that clears DVAL but scores below the quality gate still
    # persists (DVAL-10 is a warning per the blueprint). Raise the gate on a
    # copy of the config so the branch is exercised without tuning the
    # shipped defaults.
    from dataclasses import replace

    build_feature_and_label_sets(config, tmp_path, n=150)
    strict = replace(
        config, dataset_builder=replace(config.dataset_builder, min_quality_score=99.0)
    )
    result = DatasetBuilder(strict).run(tickers=["AAPL"], dataset_version="v0.2")
    assert result.quality.score < strict.dataset_builder.min_quality_score
    assert result.total_rows > 0
    assert (dataset_dir(config.data.processed_dir, "v0.2") / "hash.txt").exists()


def test_real_config_loads_dataset_builder_section(monkeypatch: pytest.MonkeyPatch):
    # Pin the testing environment so environment overlays (development.yaml
    # aligns versions with live artifacts) cannot change the asserted values.
    monkeypatch.setenv("ENVIRONMENT", "testing")
    config = load_config()
    assert config.dataset_builder.dataset_version == "v0.1"
    assert config.dataset_builder.min_quality_score == 70
    assert config.dataset_builder.purging.enabled is False
    assert config.dataset_builder.embargo.enabled is False
    assert dict(config.dataset.split_ratios) == {"train": 0.7, "val": 0.15, "test": 0.15}
