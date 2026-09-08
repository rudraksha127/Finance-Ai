"""Label engine integration tests — fixed reference case, persistence, idempotency."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from src.core.errors import ValidationError
from src.features.registry import FEATURE_COLUMNS
from src.labels.engine import LabelEngine
from src.labels.generator import generate_labels
from src.labels.metadata import compute_label_version_hash
from src.labels.storage import (
    LabelStorageConflictError,
    hash_file_path,
    label_file_path,
    metadata_file_path,
    read_labels,
    read_metadata,
)
from tests.data_helpers import make_app_config


def write_cleaned_csv(tmp_path: Path, prices: list[float], *, ticker: str = "AAPL") -> Path:
    """Write a cleaned interim CSV whose adj_close equals the given prices."""
    interim = tmp_path / "interim"
    interim.mkdir(parents=True, exist_ok=True)
    start = date(2025, 1, 2)
    rows = []
    for i, price in enumerate(prices):
        day = start + timedelta(days=i + (i // 5) * 2)
        rows.append(
            {
                "ticker": ticker,
                "timestamp": f"{day}T00:00:00",
                "open": round(price - 0.2, 4),
                "high": round(price + 0.8, 4),
                "low": round(price - 0.8, 4),
                "close": round(price, 4),
                "adj_close": round(price, 4),
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


# ---------------------------------------------------------------------------
# Fixed reference case (hand-derivable; milestone section 27)
# ---------------------------------------------------------------------------
REFERENCE_PRICES = [100, 100, 100, 100, 100, 105, 95, 100, 100, 100, 100, 100]


def test_fixed_reference_case_labels():
    """Expected future returns and labels are manually derivable."""
    prices = [float(p) for p in REFERENCE_PRICES]
    result = generate_labels(
        pd.DataFrame(
            {"close": prices, "adj_close": prices},
            index=pd.date_range("2025-01-02", periods=len(prices), freq="B"),
        ),
        horizon=5,
        threshold_up=0.01,
        threshold_down=0.01,
        price_column="adj_close",
    )
    out = result.frame
    assert out["future_return"].iloc[0] == pytest.approx(0.05)  # 105/100 - 1
    assert out["label"].iloc[0] == "UP"
    assert out["future_return"].iloc[1] == pytest.approx(-0.05)  # 95/100 - 1
    assert out["label"].iloc[1] == "DOWN"
    assert out["label"].iloc[2] == "HOLD"
    assert out["label"].iloc[3] == "HOLD"
    assert out["label"].iloc[4] == "HOLD"
    assert out["future_return"].iloc[5] == pytest.approx(-5.0 / 105.0)  # 100/105 - 1
    assert out["label"].iloc[5] == "DOWN"
    assert out["future_return"].iloc[6] == pytest.approx(5.0 / 95.0)  # 100/95 - 1
    assert out["label"].iloc[6] == "UP"
    assert out["label"].iloc[7:].isna().all()  # no future window

    dist = result.distribution
    assert dist.valid_rows == 7
    assert dist.up_count == 2
    assert dist.down_count == 2
    assert dist.hold_count == 3
    assert dist.invalid_count == 5


def test_end_to_end_label_generation(config, tmp_path: Path):
    source = write_cleaned_csv(tmp_path, [float(p) for p in REFERENCE_PRICES])
    result = LabelEngine(config).run("AAPL", "1d", source=source)

    assert result.label_version == "v0.1"
    assert result.horizon == 5
    assert result.row_count == 12
    assert result.distribution.valid_rows == 7
    assert result.distribution.up_count == 2
    assert result.distribution.down_count == 2
    assert result.distribution.hold_count == 3
    assert result.distribution.invalid_count == 5

    parquet = label_file_path(config.data.processed_dir, "v0.1", "AAPL")
    assert parquet.exists()
    assert result.output_file == parquet

    back = read_labels(parquet)
    assert back.shape == (12, 5)
    assert "target_timestamp" in back.columns
    assert back["label"].iloc[0] == "UP"
    assert back["label"].iloc[6] == "UP"
    assert back["label"].iloc[7:].isna().all()
    # No feature/source columns leak into label storage (TEST E, integration).
    assert set(back.columns).isdisjoint(set(FEATURE_COLUMNS))
    assert not {"open", "high", "low", "close", "volume"} & set(back.columns)

    metadata = read_metadata(metadata_file_path(config.data.processed_dir, "v0.1", "AAPL"))
    assert metadata["label_version"] == "v0.1"
    assert metadata["horizon"] == 5
    assert metadata["threshold_up"] == 0.01
    assert metadata["threshold_down"] == 0.01
    assert metadata["label_name"] == "direction"
    assert metadata["target_type"] == "classification"
    assert metadata["up_count"] == 2
    assert metadata["down_count"] == 2
    assert metadata["hold_count"] == 3
    assert metadata["invalid_count"] == 5
    assert metadata["source_file"] == str(source)
    assert metadata["version_hash"] == result.version_hash
    assert metadata["status"] == "active"

    saved_hash = hash_file_path(config.data.processed_dir, "v0.1", "AAPL").read_text().strip()
    assert saved_hash == result.version_hash


def test_idempotent_rerun_byte_stable(config, tmp_path: Path):
    source = write_cleaned_csv(tmp_path, [float(p) for p in REFERENCE_PRICES])
    first = LabelEngine(config).run("AAPL", "1d", source=source)
    parquet = label_file_path(config.data.processed_dir, "v0.1", "AAPL")
    first_bytes = parquet.read_bytes()

    second = LabelEngine(config).run("AAPL", "1d", source=source)
    assert second.version_hash == first.version_hash
    assert parquet.read_bytes() == first_bytes
    assert second.distribution == first.distribution


def test_conflicting_regeneration_refused(config, tmp_path: Path):
    source = write_cleaned_csv(tmp_path, [float(p) for p in REFERENCE_PRICES])
    LabelEngine(config).run("AAPL", "1d", source=source)

    # Materially different prices -> different labels -> conflict, not overwrite.
    changed = [float(p) * 2 for p in REFERENCE_PRICES]
    write_cleaned_csv(tmp_path, changed)
    with pytest.raises(LabelStorageConflictError):
        LabelEngine(config).run("AAPL", "1d", source=source)


def test_horizon_override(config, tmp_path: Path):
    source = write_cleaned_csv(tmp_path, [float(p) for p in REFERENCE_PRICES])
    result = LabelEngine(config).run("AAPL", "1d", source=source, horizon=1)
    assert result.horizon == 1
    assert result.distribution.valid_rows == 11
    assert label_file_path(config.data.processed_dir, "v0.1", "AAPL").exists()
    metadata = read_metadata(metadata_file_path(config.data.processed_dir, "v0.1", "AAPL"))
    assert metadata["horizon"] == 1


def test_version_hash_changes_with_definition():
    base = compute_label_version_hash(
        horizon=5, threshold_up=0.01, threshold_down=0.01, price_column="adj_close"
    )
    assert base == compute_label_version_hash(
        horizon=5, threshold_up=0.01, threshold_down=0.01, price_column="adj_close"
    )
    assert base != compute_label_version_hash(
        horizon=10, threshold_up=0.01, threshold_down=0.01, price_column="adj_close"
    )
    assert base != compute_label_version_hash(
        horizon=5, threshold_up=0.02, threshold_down=0.01, price_column="adj_close"
    )
    assert base != compute_label_version_hash(
        horizon=5, threshold_up=0.01, threshold_down=0.01, price_column="close"
    )


def test_balance_warning_on_imbalanced_classes(config, tmp_path: Path):
    # Monotonic rising prices -> all UP -> balance warning, never auto-tune.
    prices = [float(100 + i) for i in range(20)]
    source = write_cleaned_csv(tmp_path, prices)
    result = LabelEngine(config).run("AAPL", "1d", source=source)
    assert result.distribution.up_pct == 100.0
    assert any("UP" in warning for warning in result.balance_warnings)
    assert any("never auto-tuned" in warning for warning in result.balance_warnings)


def test_no_valid_labels_when_horizon_exceeds_data(config, tmp_path: Path):
    source = write_cleaned_csv(tmp_path, [100.0, 101.0, 102.0])
    result = LabelEngine(config).run("AAPL", "1d", source=source, horizon=5)
    assert result.distribution.valid_rows == 0
    assert result.distribution.invalid_count == 3
    assert any("no valid labels" in warning for warning in result.balance_warnings)


def test_missing_price_column_rejected(config, tmp_path: Path):
    source = write_cleaned_csv(tmp_path, [100.0] * 10)
    frame = pd.read_csv(source).drop(columns=["adj_close"])
    frame.to_csv(source, index=False)
    with pytest.raises(ValidationError):
        LabelEngine(config).run("AAPL", "1d", source=source)


def test_invalid_inputs_rejected(config):
    with pytest.raises(ValidationError):
        LabelEngine(config).run("bad ticker!", "1d")
    with pytest.raises(ValidationError):
        LabelEngine(config).run("AAPL", "5m")
    with pytest.raises(ValidationError):
        LabelEngine(config).run("AAPL", "1d", horizon=0)
