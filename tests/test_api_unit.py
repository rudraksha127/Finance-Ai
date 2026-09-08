"""Unit tests for the inference API internals (M09, milestone section 33).

Covers request/response validation, model resolution, version
compatibility, and decision-engine integration — all offline and
deterministic (milestone section 34).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.api import decision as decision_module
from src.api.errors import (
    FEATURE_VALIDATION_FAILED,
    FEATURE_VERSION_INCOMPATIBLE,
    MODEL_NOT_FOUND,
    ApiError,
)
from src.api.resolver import ModelCache, check_compatibility, resolve_model_version
from src.api.schemas import PredictionRequest
from tests.api_helpers import MODEL_VERSION, make_api_config, valid_request_payload

# ---------------------------------------------------------------------------
# Request schema (layer 1)
# ---------------------------------------------------------------------------


def test_valid_request_parses(tmp_path):
    config = make_api_config(tmp_path)
    request = PredictionRequest(**valid_request_payload(config))
    assert request.ticker == "AAPL"
    assert request.market_context.current_price > 0


def test_unknown_extra_field_rejected(tmp_path):
    config = make_api_config(tmp_path)
    payload = valid_request_payload(config, future_label="UP")
    with pytest.raises(ValidationError):
        PredictionRequest(**payload)


def test_bad_ticker_rejected(tmp_path):
    config = make_api_config(tmp_path)
    payload = valid_request_payload(config, ticker="AAPL$$")
    with pytest.raises(ValidationError):
        PredictionRequest(**payload)


def test_negative_price_rejected(tmp_path):
    config = make_api_config(tmp_path)
    payload = valid_request_payload(config)
    payload["market_context"]["current_price"] = -5.0
    with pytest.raises(ValidationError):
        PredictionRequest(**payload)


def test_nan_price_rejected(tmp_path):
    config = make_api_config(tmp_path)
    payload = valid_request_payload(config)
    payload["market_context"]["current_price"] = float("nan")
    with pytest.raises(ValidationError):
        PredictionRequest(**payload)


# ---------------------------------------------------------------------------
# Model resolution (section 9)
# ---------------------------------------------------------------------------


def test_explicit_version_wins(tmp_path):
    config = make_api_config(tmp_path)
    assert resolve_model_version(config, MODEL_VERSION) == MODEL_VERSION


def test_unknown_version_raises_model_not_found(tmp_path):
    config = make_api_config(tmp_path)
    with pytest.raises(ApiError) as excinfo:
        resolve_model_version(config, "missing_v9")
    assert excinfo.value.code == MODEL_NOT_FOUND


def test_default_model_from_config(tmp_path):
    from dataclasses import replace as _replace

    config = make_api_config(tmp_path)
    pinned = _replace(config, api=_replace(config.api, default_model=MODEL_VERSION))
    assert resolve_model_version(pinned, None) == MODEL_VERSION


def test_no_models_raises_model_not_found(tmp_path):
    from dataclasses import replace as _replace

    from src.config.loader import ModelConfig

    config = make_api_config(tmp_path)
    empty = _replace(config, model=ModelConfig(artifact_dir=tmp_path / "none"))
    with pytest.raises(ApiError) as excinfo:
        resolve_model_version(empty, None)
    assert excinfo.value.code == MODEL_NOT_FOUND


# ---------------------------------------------------------------------------
# Compatibility (section 10)
# ---------------------------------------------------------------------------


def test_feature_version_mismatch_raises(tmp_path):
    from src.api.resolver import load_model

    config = make_api_config(tmp_path)
    model = load_model(config, MODEL_VERSION)
    with pytest.raises(ApiError) as excinfo:
        check_compatibility(
            model,
            feature_set_version="v9.9",
            feature_names=model.feature_names,
            label_version=model.label_version,
        )
    assert excinfo.value.code == FEATURE_VERSION_INCOMPATIBLE


def test_wrong_feature_names_raise(tmp_path):
    from src.api.resolver import load_model

    config = make_api_config(tmp_path)
    model = load_model(config, MODEL_VERSION)
    with pytest.raises(ApiError) as excinfo:
        check_compatibility(
            model,
            feature_set_version=model.feature_version,
            feature_names=tuple(model.feature_names)[:-1] + ("made_up_feature",),
            label_version=model.label_version,
        )
    assert excinfo.value.code == FEATURE_VALIDATION_FAILED


def test_compatible_request_passes(tmp_path):
    from src.api.resolver import load_model

    config = make_api_config(tmp_path)
    model = load_model(config, MODEL_VERSION)
    check_compatibility(
        model,
        feature_set_version=model.feature_version,
        feature_names=model.feature_names,
        label_version=model.label_version,
    )


# ---------------------------------------------------------------------------
# Model cache (section 13)
# ---------------------------------------------------------------------------


def test_model_cache_evicts_least_recently_used(tmp_path):
    cache = ModelCache(2)
    cache.put(object.__new__(type("M", (), {"model_version": "a"})))
    first = type("M", (), {"model_version": "a"})
    second = type("M", (), {"model_version": "b"})
    third = type("M", (), {"model_version": "c"})
    cache.put(first)
    cache.put(second)
    assert cache.get("a") is first
    cache.put(third)  # evicts b (least recently used)
    assert cache.get("b") is None
    assert cache.get("a") is first
    assert cache.get("c") is third


# ---------------------------------------------------------------------------
# Decision integration (sections 15/23 — shared logic, risk, reason codes)
# ---------------------------------------------------------------------------


def test_buy_decision_uses_shared_thresholds():
    result = decision_module.decide(
        probabilities={"UP": 0.72, "DOWN": 0.15, "HOLD": 0.13},
        buy_threshold=0.55,
        sell_threshold=0.55,
        recent_volatility=0.2,
        volatility_20d=0.2,
    )
    assert result.signal == "BUY"
    assert "MODEL_SIGNAL_BUY" in result.reason_codes
    assert 0.0 <= result.risk_score <= 1.0


def test_no_trade_below_threshold():
    result = decision_module.decide(
        probabilities={"UP": 0.48, "DOWN": 0.31, "HOLD": 0.21},
        buy_threshold=0.55,
        sell_threshold=0.55,
        recent_volatility=0.2,
        volatility_20d=0.2,
    )
    assert result.signal == "NO_TRADE"
    assert "MODEL_CONFIDENCE_LOW" in result.reason_codes
    assert result.position_size is None


def test_high_volatility_blocks_signal():
    result = decision_module.decide(
        probabilities={"UP": 0.90, "DOWN": 0.05, "HOLD": 0.05},
        buy_threshold=0.55,
        sell_threshold=0.55,
        recent_volatility=1.5,
        volatility_20d=1.5,
    )
    assert result.signal == "NO_TRADE"
    assert "HIGH_VOLATILITY" in result.reason_codes


def test_decision_matches_backtest_signal_logic():
    """Backtest Logic = API Logic (blueprint section 23.2)."""
    import pandas as pd

    from src.backtest.signals import generate_signals

    probabilities = {"UP": 0.60, "DOWN": 0.25, "HOLD": 0.15}
    frame = pd.DataFrame(
        {
            "probability_UP": [probabilities["UP"]],
            "probability_DOWN": [probabilities["DOWN"]],
            "probability_HOLD": [probabilities["HOLD"]],
        }
    )
    backtest_signal = generate_signals(frame, buy_threshold=0.55, sell_threshold=0.55).iloc[0]
    api_decision = decision_module.decide(
        probabilities=probabilities,
        buy_threshold=0.55,
        sell_threshold=0.55,
        recent_volatility=0.2,
        volatility_20d=0.2,
    )
    assert api_decision.signal == backtest_signal


def test_risk_score_bounded_and_monotone_in_volatility():
    low = decision_module.risk_score(
        max_probability=0.9, recent_volatility=0.1, volatility_20d=None
    )
    high = decision_module.risk_score(
        max_probability=0.9, recent_volatility=0.9, volatility_20d=None
    )
    assert 0.0 <= low < high <= 1.0
