"""Integration tests for the backtest engine (M08)."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from src.backtest.engine import BacktestEngine
from src.backtest.errors import DataQualityError
from src.model.errors import VersionMismatchError
from src.model.trainer import BaselineTrainer
from tests.backtest_helpers import TICKER, build_backtest_fixture


def _train(config) -> str:
    """Train a small deterministic baseline; return its model version."""
    result = BaselineTrainer(config).run(
        model_name="random_forest",
        model_version="baseline_rf_backtest_test",
        experiment_id="exp_bt_test",
    )
    return result.model_version


def test_end_to_end_static_backtest(tmp_path):
    config = build_backtest_fixture(tmp_path, n_train=80, n_val=30, n_test=25)
    model_version = _train(config)
    engine = BacktestEngine(config)
    result = engine.run(ticker=TICKER, model_version=model_version)

    assert result.backtest_id.startswith("bt_")
    assert result.ticker == TICKER
    assert result.model_version == model_version
    assert result.strategy_version == "stg_v0.1"
    assert result.cost_model_version == "cost_v0.1"
    assert result.experiment_record["backtest_version"] == "v0.1"
    assert result.experiment_record["initial_capital"] == 1.0
    snapshot = json.loads(result.paths["config_snapshot"].read_text(encoding="utf-8"))
    assert snapshot["backtest_version"] == "v0.1"
    assert snapshot["initial_capital"] == 1.0
    assert result.financial_metrics["number_of_trades"] >= 0
    assert "sharpe_ratio" in result.financial_metrics
    assert "max_drawdown" in result.financial_metrics
    assert "buy_and_hold" in result.benchmarks and "zero_trade" in result.benchmarks
    assert result.cost_adjusted["per_side_bps"] == 10.0
    assert result.cost_adjusted["round_trip_bps"] == 20.0
    assert result.cost_adjusted["net_cumulative_return"] == pytest.approx(
        result.financial_metrics["cumulative_return"]
    )

    # All required blueprint section-27 outputs exist.
    assert result.paths["trade_ledger"].exists()
    assert result.paths["equity_curve"].exists()
    assert result.paths["drawdown_curve"].exists()
    assert result.paths["financial_metrics"].exists()
    assert result.paths["prediction_metrics"].exists()
    assert result.paths["cost_adjusted"].exists()
    assert result.paths["config_snapshot"].exists()
    assert result.paths["experiment_record"].exists()
    assert result.paths["report"].exists()

    predictions = pd.read_csv(result.paths["predictions"])
    assert set(predictions.columns) >= {
        "timestamp",
        "label",
        "prediction",
        "probability_UP",
        "signal",
    }
    record = json.loads(result.paths["experiment_record"].read_text(encoding="utf-8"))
    assert record["dataset_version"] == "v0.1"
    assert record["model_version"] == model_version
    assert record["walk_forward"]["enabled"] is False

    # Evaluation rows must be exactly the dataset TEST split (out-of-sample).
    test = pd.read_parquet(config.data.processed_dir / "datasets" / "dataset_v0.1" / "test.parquet")
    assert set(predictions["timestamp"]) == set(test["timestamp"].astype(str))


def test_version_mismatch_aborts(tmp_path):
    config = build_backtest_fixture(tmp_path, n_train=80, n_val=30, n_test=25)
    model_version = _train(config)
    with pytest.raises(VersionMismatchError):
        BacktestEngine(config).run(
            ticker=TICKER, model_version=model_version, feature_version="v9.9"
        )


def test_missing_model_artifact_aborts(tmp_path):
    config = build_backtest_fixture(tmp_path, n_train=80, n_val=30, n_test=25)
    with pytest.raises(Exception, match="not found"):
        BacktestEngine(config).run(ticker=TICKER, model_version="does_not_exist_v0.1")


def test_missing_price_source_aborts(tmp_path):
    config = build_backtest_fixture(tmp_path, n_train=40, n_val=20, n_test=20)
    # Point source_versions at a checksum no cleaned file can match.

    from src.backtest.data import load_backtest_data

    processed = config.data.processed_dir
    metadata_path = processed / "datasets" / "dataset_v0.1" / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["source_versions"] = {TICKER: "deadbeefcafe"}
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(DataQualityError, match="no cleaned price source"):
        load_backtest_data(
            processed,
            config.data.interim_dir,
            ticker=TICKER,
            dataset_version="v0.1",
            feature_version="v0.1",
            label_version="v0.1",
        )


def test_engine_reports_same_outputs_for_same_input(tmp_path):
    config = build_backtest_fixture(tmp_path, n_train=60, n_val=25, n_test=20)
    model_version = _train(config)
    first = BacktestEngine(config).run(
        ticker=TICKER, model_version=model_version, backtest_id="bt_repro_a"
    )
    second = BacktestEngine(config).run(
        ticker=TICKER, model_version=model_version, backtest_id="bt_repro_b"
    )
    assert first.financial_metrics == second.financial_metrics
    first_ledger = pd.read_csv(first.paths["trade_ledger"])
    second_ledger = pd.read_csv(second.paths["trade_ledger"])
    pd.testing.assert_frame_equal(first_ledger, second_ledger)
