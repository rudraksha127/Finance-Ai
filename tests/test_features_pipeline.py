"""Feature engine integration tests — cleaned CSV -> Parquet dataset."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.config.loader import load_config
from src.core.errors import ValidationError
from src.features.engine import FeatureEngine, find_latest_cleaned
from src.features.registry import FEATURE_COLUMNS
from src.features.storage import (
    FeatureStorageConflictError,
    feature_file_path,
    hash_file_path,
    metadata_file_path,
    read_features,
    read_metadata,
)
from tests.data_helpers import make_app_config

CLEANED_COLUMNS = (
    "ticker",
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "raw_line",
)


def write_cleaned_csv(tmp_path: Path, *, ticker: str = "AAPL", n: int = 130) -> Path:
    """Write a Milestone-03 style cleaned interim CSV."""
    interim = tmp_path / "interim"
    interim.mkdir(parents=True, exist_ok=True)
    start = date(2025, 1, 2)
    rows = []
    close = 100.0
    for i in range(n):
        day = start + timedelta(days=i + (i // 5) * 2)  # skip weekends-ish
        close = close * 1.002 + np.sin(i) * 0.1
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


def test_find_latest_cleaned(tmp_path: Path):
    write_cleaned_csv(tmp_path, n=10)
    found = find_latest_cleaned(tmp_path / "interim", "AAPL", "1d")
    assert found.name == "cleaned_20250315_AAPL_daily.csv"


def test_find_latest_cleaned_missing(tmp_path: Path):
    from src.core.errors import StorageError

    with pytest.raises(StorageError):
        find_latest_cleaned(tmp_path / "interim", "MSFT", "1d")


def test_end_to_end_generation(config, tmp_path: Path):
    source = write_cleaned_csv(tmp_path, n=130)
    result = FeatureEngine(config).run("AAPL", "1d", source=source)

    assert result.ticker == "AAPL"
    assert result.feature_set_version == "v0.1"
    assert result.row_count == 130
    assert result.feature_count == 52
    assert result.max_lookback == 100
    assert result.validation.errors == ()
    assert result.validation.total_features == 52

    parquet = feature_file_path(config.data.processed_dir, "v0.1", "AAPL")
    assert parquet.exists()
    assert result.output_file == parquet

    back = read_features(parquet)
    assert back.shape == (130, 52)
    assert list(back.columns) == list(FEATURE_COLUMNS)
    assert back.index.name == "timestamp"

    metadata = read_metadata(metadata_file_path(config.data.processed_dir, "v0.1", "AAPL"))
    assert metadata["feature_set_version"] == "v0.1"
    assert metadata["feature_count"] == 52
    assert metadata["ticker"] == "AAPL"
    assert metadata["version_hash"] == result.version_hash
    assert metadata["source_file"] == str(source)
    assert metadata["row_count"] == 130
    assert metadata["status"] == "active"

    saved_hash = (hash_file_path(config.data.processed_dir, "v0.1", "AAPL")).read_text().strip()
    assert saved_hash == result.version_hash


def test_warmup_rows_reported(config, tmp_path: Path):
    source = write_cleaned_csv(tmp_path, n=130)
    result = FeatureEngine(config).run("AAPL", "1d", source=source)
    # bb_squeeze (100-day lookback) drives the warm-up: rows 0..98 have NaN
    # (first valid row at index 99), plus shorter lookbacks for other features.
    assert result.warmup_rows >= 99
    assert result.warmup_rows < 130


def test_deterministic_rerun_is_safe_noop(config, tmp_path: Path):
    source = write_cleaned_csv(tmp_path, n=130)
    first = FeatureEngine(config).run("AAPL", "1d", source=source)
    parquet = feature_file_path(config.data.processed_dir, "v0.1", "AAPL")
    first_bytes = parquet.read_bytes()

    second = FeatureEngine(config).run("AAPL", "1d", source=source)
    assert second.version_hash == first.version_hash
    assert parquet.read_bytes() == first_bytes  # byte-stable


def test_conflicting_regeneration_refused(config, tmp_path: Path):
    source = write_cleaned_csv(tmp_path, n=130)
    FeatureEngine(config).run("AAPL", "1d", source=source)

    # Change the source data (materially different input) and regenerate.
    # All price columns scale together so OHLC invariants stay valid and the
    # failure is the storage conflict, not a feature-validation error.
    frame = pd.read_csv(source)
    for column in ("open", "high", "low", "close", "adj_close"):
        frame[column] = frame[column] * 10.0
    frame.to_csv(source, index=False)

    with pytest.raises(FeatureStorageConflictError):
        FeatureEngine(config).run("AAPL", "1d", source=source)


def test_feature_version_from_config_and_cli_flag(config, tmp_path: Path):
    source = write_cleaned_csv(tmp_path, n=130)
    result = FeatureEngine(config).run("AAPL", "1d", source=source, feature_version="v0.2")
    assert result.feature_set_version == "v0.2"
    assert feature_file_path(config.data.processed_dir, "v0.2", "AAPL").exists()


def test_invalid_inputs_rejected(config):
    from src.core.errors import ValidationError

    with pytest.raises(ValidationError):
        FeatureEngine(config).run("bad ticker!", "1d")
    with pytest.raises(ValidationError):
        FeatureEngine(config).run("AAPL", "5m")


def test_missing_cleaned_columns_fail_loudly(config, tmp_path: Path):
    source = write_cleaned_csv(tmp_path, n=30)
    frame = pd.read_csv(source).drop(columns=["volume"])
    frame.to_csv(source, index=False)
    with pytest.raises(ValidationError):
        FeatureEngine(config).run("AAPL", "1d", source=source)


def test_duplicate_timestamps_fail_loudly(config, tmp_path: Path):
    source = write_cleaned_csv(tmp_path, n=30)
    frame = pd.read_csv(source)
    frame = pd.concat([frame, frame.iloc[[0]]])
    frame.to_csv(source, index=False)
    with pytest.raises(ValidationError):
        FeatureEngine(config).run("AAPL", "1d", source=source)


def test_real_config_loads(monkeypatch: pytest.MonkeyPatch):
    # The shipped default.yaml features section must load and validate.
    # Pin the testing environment so environment overlays (development.yaml
    # aligns versions with live artifacts) cannot change the asserted values.
    monkeypatch.setenv("ENVIRONMENT", "testing")
    config = load_config()
    assert config.features.version == "v0.1"
    assert config.features.output_format == "parquet"
    assert config.features.validation.max_nan_ratio == 0.30
    assert config.dataset.label_window == 5
    assert config.dataset.threshold_up == 0.01
    assert config.dataset.price_column == "adj_close"
