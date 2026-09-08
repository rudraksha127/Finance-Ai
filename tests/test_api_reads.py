"""Read-only dashboard endpoint tests (Milestone 10, UI_UX §29.3).

Exercises every read endpoint against the deterministic M08/M09 fixture
artifacts: datasets, models, experiments, backtests, candles, prediction
audit, and system status.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pandas as pd


def test_list_datasets(api_client, api_state):
    response = api_client.get("/datasets")
    assert response.status_code == 200
    datasets = response.json()
    assert len(datasets) >= 1
    top = datasets[0]
    for field in ("dataset_version", "row_count", "feature_count", "quality_score", "label_version"):
        assert field in top
    assert top["dataset_version"] == "v0.1"


def test_get_dataset_detail(api_client, api_state):
    response = api_client.get("/datasets/v0.1")
    assert response.status_code == 200
    body = response.json()
    assert body["dataset_version"] == "v0.1"
    assert body["split_row_counts"]["train"] == 80
    assert body["instruments"] == ["AAPL"]


def test_get_dataset_unknown_version(api_client):
    response = api_client.get("/datasets/v9.9")
    assert response.status_code == 400


def test_list_models(api_client, api_state):
    response = api_client.get("/models")
    assert response.status_code == 200
    models = response.json()
    assert any(m["model_version"] == "api_test_model_v1" for m in models)
    model = next(m for m in models if m["model_version"] == "api_test_model_v1")
    assert model["feature_count"] == 52
    assert "metrics" in model


def test_list_experiments(api_client, api_state):
    response = api_client.get("/experiments")
    assert response.status_code == 200
    experiments = response.json()
    assert any(e["experiment_id"] == "exp_api_test" for e in experiments)


def test_get_experiment_detail(api_client, api_state):
    response = api_client.get("/experiments/exp_api_test")
    assert response.status_code == 200
    body = response.json()
    assert body["experiment_id"] == "exp_api_test"
    assert body["random_seed"] == api_state.config.model.random_seed
    assert body["rows"]["train"] == 80
    assert "config_snapshot" in body


def test_get_experiment_unknown(api_client):
    response = api_client.get("/experiments/exp_ghost")
    assert response.status_code == 400


def test_backtest_end_to_end_roundtrip(api_client, api_state):
    """Run a real static backtest, then read it back through the API."""
    from src.backtest.engine import BacktestEngine
    from src.backtest.data import load_backtest_data
    from src.backtest.prediction import load_model_predictions
    from tests.backtest_helpers import TICKER

    engine = BacktestEngine(api_state.config)
    data = load_backtest_data(
        api_state.config.data.processed_dir,
        api_state.config.data.interim_dir,
        ticker=TICKER,
        dataset_version="v0.1",
        feature_version="v0.1",
        label_version="v0.1",
    )
    predictions = load_model_predictions(
        data, model_version="api_test_model_v1", model_dir=api_state.config.model.artifact_dir
    )
    result = engine.run_static(data, predictions.frame, model_version="api_test_model_v1", backtest_id="bt_readtest")

    listing = api_client.get("/backtests").json()
    assert any(b["backtest_id"] == "bt_readtest" for b in listing)

    detail_response = api_client.get("/backtests/bt_readtest")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["model_version"] == "api_test_model_v1"
    assert detail["strategy_version"] == "stg_v0.1"
    assert detail["backtest_version"] == "v0.1"
    assert "cumulative_return" in detail["financial_metrics"]
    assert len(detail["equity_curve"]) > 0
    assert len(detail["drawdown_curve"]) > 0


def test_get_backtest_unknown(api_client):
    response = api_client.get("/backtests/bt_ghost")
    assert response.status_code == 400


def test_candles_endpoint(api_client, api_state):
    response = api_client.get("/candles/AAPL")
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "AAPL"
    assert body["count"] > 0
    first = body["candles"][0]
    for field in ("timestamp", "open", "high", "low", "close", "volume"):
        assert field in first
    assert body["stale"] is True  # fixture data is historical


def test_candles_rejects_lowercase(api_client):
    response = api_client.get("/candles/aapl")
    assert response.status_code == 400


def test_predictions_endpoint_after_predict(api_client, api_state):
    from tests.api_helpers import valid_request_payload

    payload = valid_request_payload(api_state.config)
    assert api_client.post("/predict", json=payload).status_code == 200
    response = api_client.get("/predictions", params={"ticker": "AAPL"})
    assert response.status_code == 200
    records = response.json()
    assert len(records) >= 1
    assert records[0]["ticker"] == "AAPL"
    assert "prediction_id" in records[0]
    assert "probabilities" in records[0]


def test_system_status(api_client, api_state):
    response = api_client.get("/system/status")
    assert response.status_code == 200
    body = response.json()
    assert body["latest_dataset"]["dataset_version"] == "v0.1"
    assert body["latest_model"]["model_version"] == "api_test_model_v1"
    assert body["counts"]["models"] >= 1
