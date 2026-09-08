"""Endpoint/integration tests for the inference API (M09).

Covers the milestone sections 33 (API + health + audit tests), 35
(integration path), and 36 (failure integration / fail-closed) using the
real trained fixture model — no live services, no network (section 34).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from src.api.audit import audit_path
from tests.api_helpers import FEATURE_VERSION, LABEL_VERSION, MODEL_VERSION, valid_request_payload


def _stale_payload(config, **overrides):
    stale = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    payload = valid_request_payload(config)
    payload["market_context"]["data_timestamp"] = stale
    payload.update(overrides)
    return payload


def test_predict_success_contract(api_client, api_state):
    payload = valid_request_payload(api_state.config)
    response = api_client.post("/predict", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("success", "no_trade")
    assert body["ticker"] == "AAPL"
    assert body["request_id"]
    assert body["prediction_id"].startswith("pred_")
    assert body["model"]["model_version"] == MODEL_VERSION
    assert body["model"]["feature_version"] == FEATURE_VERSION
    assert body["model"]["label_version"] == LABEL_VERSION
    assert set(body["model_output"]["probabilities"]) == {"UP", "DOWN", "HOLD"}
    assert abs(sum(body["model_output"]["probabilities"].values()) - 1.0) < 1e-6
    assert body["decision_output"]["signal"] in ("BUY", "SELL", "NO_TRADE")
    assert body["decision_output"]["strategy_version"] == "stg_v0.1"
    assert body["decision_output"]["risk_score"] >= 0.0
    assert len(body["features_used"]) == 52
    assert body["inference_time_ms"] >= 0.0


def test_predict_generates_request_id_when_absent(api_client, api_state):
    payload = valid_request_payload(api_state.config)
    payload.pop("request_id", None)
    response = api_client.post("/predict", json=payload)
    assert response.status_code == 200
    assert response.json()["request_id"].startswith("req_")


def test_predict_is_deterministic_for_fixed_input(api_client, api_state):
    """Regression test (milestone section 33): same input -> same output."""
    payload = valid_request_payload(api_state.config)
    first = api_client.post("/predict", json=payload).json()
    second = api_client.post("/predict", json=payload).json()
    assert first["model_output"] == second["model_output"]
    assert first["decision_output"]["signal"] == second["decision_output"]["signal"]
    assert first["decision_output"]["risk_score"] == second["decision_output"]["risk_score"]


def test_predict_invalid_contract_returns_envelope(api_client, api_state):
    payload = valid_request_payload(api_state.config)
    payload["ticker"] = "AAPL$$"
    response = api_client.post("/predict", json=payload)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "FEATURE_VALIDATION_FAILED"
    assert "request_id" in error and "timestamp" in error


def test_predict_missing_feature_fails(api_client, api_state):
    payload = valid_request_payload(api_state.config)
    payload["features"].pop("returns_1d")
    response = api_client.post("/predict", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "FEATURE_VALIDATION_FAILED"


def test_predict_unexpected_feature_fails(api_client, api_state):
    payload = valid_request_payload(api_state.config)
    payload["features"]["made_up_feature"] = 1.0
    response = api_client.post("/predict", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "FEATURE_VALIDATION_FAILED"


def test_predict_nan_feature_fails(api_client, api_state):
    import json as _json

    payload = valid_request_payload(api_state.config)
    payload["features"]["returns_1d"] = float("nan")
    # NaN is not valid strict JSON; send raw content the way a broken/hostsile client would.
    response = api_client.post(
        "/predict",
        content=_json.dumps(payload).replace("NaN", "NaN"),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "FEATURE_VALIDATION_FAILED"


def test_predict_infinity_feature_fails(api_client, api_state):
    import json as _json

    payload = valid_request_payload(api_state.config)
    payload["features"]["returns_1d"] = float("inf")
    response = api_client.post(
        "/predict",
        content=_json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "FEATURE_VALIDATION_FAILED"


def test_predict_future_timestamp_fails(api_client, api_state):
    payload = valid_request_payload(api_state.config)
    payload["timestamp"] = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    response = api_client.post("/predict", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_predict_stale_data_fails(api_client, api_state):
    response = api_client.post("/predict", json=_stale_payload(api_state.config))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "STALE_DATA"


def test_predict_unknown_model_version_fails(api_client, api_state):
    payload = valid_request_payload(api_state.config, model_version="ghost_v9")
    response = api_client.post("/predict", json=payload)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MODEL_NOT_FOUND"


def test_predict_feature_version_mismatch_fails(api_client, api_state):
    payload = valid_request_payload(api_state.config, feature_set_version="v9.9")
    response = api_client.post("/predict", json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FEATURE_VERSION_INCOMPATIBLE"


def test_predict_unknown_ticker_fails(api_client, api_state):
    payload = valid_request_payload(api_state.config, ticker="MSFT")
    response = api_client.post("/predict", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_predict_wrong_interval_fails(api_client, api_state):
    payload = valid_request_payload(api_state.config, interval="1h")
    response = api_client.post("/predict", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_predict_audit_record_written(api_client, api_state):
    payload = valid_request_payload(api_state.config)
    response = api_client.post("/predict", json=payload)
    assert response.status_code == 200
    body = response.json()
    path = audit_path(
        api_state.config.api.audit_dir,
        inference_timestamp=datetime.fromisoformat(body["inference_timestamp"]),
    )
    assert path.exists()
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    match = [r for r in records if r["prediction_id"] == body["prediction_id"]]
    assert len(match) == 1
    record = match[0]
    for field in (
        "prediction_id",
        "request_id",
        "ticker",
        "input_timestamp",
        "data_timestamp",
        "model_version",
        "feature_version",
        "strategy_version",
        "prediction",
        "probabilities",
        "confidence",
        "signal",
        "risk_score",
        "reason_codes",
        "inference_timestamp",
    ):
        assert field in record
    assert record["model_version"] == MODEL_VERSION


def test_predict_audit_failure_marks_unaudited(api_client, api_state, monkeypatch):
    """Milestone section 27: audit failure is explicit, never silent."""
    from src.api import audit as audit_module

    def explode(*args, **kwargs):
        raise audit_module.AuditError("disk unavailable")

    # The orchestrator imported the symbol directly; patch where it is used.
    import src.api.orchestrator as orchestrator_module

    monkeypatch.setattr(orchestrator_module, "write_prediction_record", explode)
    payload = valid_request_payload(api_state.config)
    response = api_client.post("/predict", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["audit_written"] is False
    # Decision output itself is untouched (it is engine-authoritative).
    assert "AUDIT_WRITE_FAILED" not in body["decision_output"]["reason_codes"]


def test_health_ok(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["model_version"] == MODEL_VERSION
    assert body["mode"] == "research"
    assert body["uptime_seconds"] >= 0.0


def test_ready_ok(api_client):
    response = api_client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert all(body["checks"].values())


def test_ready_and_health_degraded_without_models(tmp_path):
    """Blueprint sections 17.2/28.3: observability stays up, /ready fails 503."""
    from dataclasses import replace as _replace

    from fastapi.testclient import TestClient

    from src.api.app import create_app
    from src.config.loader import ModelConfig
    from tests.api_helpers import make_api_config

    config = make_api_config(tmp_path)
    broken = _replace(
        config,
        model=ModelConfig(artifact_dir=tmp_path / "empty_models"),
        api=_replace(config.api, audit_dir=tmp_path / "audit"),
    )
    app = create_app(broken)
    client = TestClient(app, raise_server_exceptions=False)
    ready = client.get("/ready")
    assert ready.status_code == 503
    ready_body = ready.json()
    assert ready_body["status"] == "not_ready"
    assert ready_body["checks"]["model_available"] is False
    assert ready_body["checks"]["default_model_loaded"] is False
    health = client.get("/health")
    assert health.status_code == 503
    assert health.json()["status"] == "degraded"
    # Observability endpoints stay available during model failure (28.3).
    assert client.get("/version").status_code == 200
    assert client.get("/model/info").status_code == 503


def test_model_info_endpoint(api_client, api_state):
    response = api_client.get("/model/info")
    assert response.status_code == 200
    body = response.json()
    assert body["model_version"] == MODEL_VERSION
    assert body["feature_version"] == FEATURE_VERSION
    assert body["label_version"] == LABEL_VERSION
    assert body["feature_count"] == 52
    assert "metrics" in body


def test_model_info_unknown_version_404(api_client):
    response = api_client.get("/model/info", params={"model_version": "ghost_v9"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MODEL_NOT_FOUND"


def test_version_endpoint(api_client):
    response = api_client.get("/version")
    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "v1"
    assert body["model_version"] == MODEL_VERSION
    assert body["feature_version"] == FEATURE_VERSION
    assert body["strategy_version"] == "stg_v0.1"
    assert body["mode"] == "research"


def test_version_endpoint_reports_resolved_model_versions(api_client, api_state):
    """Regression (M11 §6): /version must report the resolved default model's
    feature/label versions, not configured values that lag the newest artifact."""
    from dataclasses import replace

    import src.api.app as app_module

    drifted = replace(
        api_state,
        default_feature_version="v9.9",
        default_label_version="v9.9",
    )
    original_state = app_module.STATE
    app_module.STATE = drifted
    try:
        response = api_client.get("/version")
    finally:
        app_module.STATE = original_state
    assert response.status_code == 200
    body = response.json()
    assert body["feature_version"] == "v9.9"
    assert body["label_version"] == "v9.9"
    assert body["model_version"] == MODEL_VERSION


def test_openapi_documents_contract(api_client):
    schema = api_client.get("/openapi.json").json()
    assert "/predict" in schema["paths"]
    assert "/health" in schema["paths"]
    assert "/model/info" in schema["paths"]
    assert "/version" in schema["paths"]
    assert "PredictionRequest" in schema["components"]["schemas"]


def test_golden_regression_vector(api_client, api_state):
    """Fixed model + fixed feature vector -> stable prediction structure."""
    from src.features.registry import FEATURE_COLUMNS

    golden = {name: 0.1 for name in FEATURE_COLUMNS}
    payload = valid_request_payload(api_state.config, features=golden)
    response = api_client.post("/predict", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert set(body["model_output"]["probabilities"]) == {"UP", "DOWN", "HOLD"}
    assert 0.0 <= body["model_output"]["confidence"] <= 1.0
    assert body["decision_output"]["signal"] in ("BUY", "SELL", "NO_TRADE")


def test_no_broker_or_execution_endpoints(api_client):
    """Research/live safety (milestone section 37): no order/execution routes."""
    schema = api_client.get("/openapi.json").json()
    forbidden = ("order", "execute", "trade", "broker", "position")
    for path in schema["paths"]:
        assert not any(word in path.lower() for word in forbidden), path
