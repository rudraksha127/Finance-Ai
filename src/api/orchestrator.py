"""Inference orchestration for the prediction API (M09).

Implements the milestone section 2 core flow::

    HTTP Request -> Request Validation -> Input/Data Validation
      -> Feature Validation -> Model Resolution -> Model Inference
      -> Prediction Validation -> Decision Engine -> Audit Record
      -> HTTP Response

Fail-closed (blueprint section 28.2): a prediction is only served when
every stage completes; failures become deterministic ApiErrors, never
fabricated predictions. Inference is read-only — the only writes are
append-only audit records (section 13/19).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from src.api import decision as decision_module
from src.api.audit import AuditError, parse_utc, write_prediction_record
from src.api.errors import (
    FEATURE_VALIDATION_FAILED,
    INVALID_REQUEST,
    PREDICTION_FAILED,
    STALE_DATA,
    ApiError,
)
from src.api.resolver import (
    API_VERSION,
    LoadedModel,
    ModelCache,
    check_compatibility,
    load_model,
    model_classes,
    resolve_model_version,
)
from src.api.schemas import (
    DecisionOutput,
    ModelInfoBlock,
    ModelOutput,
    PredictionRequest,
    PredictionResponse,
)
from src.backtest.signals import BUY, SELL
from src.config.loader import AppConfig
from src.logging.logger import get_logger

logger = get_logger("api.orchestrator")

STATUS_SUCCESS = "success"
STATUS_NO_TRADE = "no_trade"

FUTURE_TOLERANCE_SECONDS = (
    300  # blueprint section 11.1: future timestamps beyond tolerance are invalid
)


@dataclass(frozen=True)
class ServiceState:
    """Startup-loaded service state (blueprint section 13.1)."""

    config: AppConfig
    cache: ModelCache
    default_model_version: str | None
    started_at: datetime
    known_instruments: frozenset[str] = frozenset()
    # Versions of the resolved default model artifact (blueprint section 26:
    # /version must report the versions actually in effect, not config
    # values that may lag the newest artifact).
    default_feature_version: str | None = None
    default_label_version: str | None = None

    @property
    def mode(self) -> str:
        return self.config.api.mode

    @property
    def strategy_version(self) -> str:
        return self.config.backtest.strategy_version


def build_service_state(config: AppConfig) -> ServiceState:
    """Eagerly load the default model; fail startup loudly if it cannot."""
    cache = ModelCache(config.api.model_cache_size)
    default_version: str | None = None
    known_instruments: frozenset[str] = frozenset()
    model = None
    try:
        default_version = resolve_model_version(config, None)
        model = load_model(config, default_version)
        cache.put(model)
        known_instruments = _load_instruments(config, model.dataset_version)
    except ApiError as error:
        logger.error(
            "api_startup_model_load_failed",
            error_code=error.code,
            message=error.message,
            status="DEGRADED",
        )
    return ServiceState(
        config=config,
        cache=cache,
        default_model_version=default_version,
        started_at=datetime.now(timezone.utc),
        known_instruments=known_instruments,
        default_feature_version=getattr(model, "feature_version", None),
        default_label_version=getattr(model, "label_version", None),
    )


def _load_instruments(config: AppConfig, dataset_version: str) -> frozenset[str]:
    """Instruments recorded in the training dataset manifest (best effort)."""
    import json

    processed = config.data.processed_dir
    processed = processed if processed.is_absolute() else Path.cwd() / processed
    manifest_path = processed / "datasets" / f"dataset_{dataset_version}" / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return frozenset(str(name).upper() for name in manifest.get("instruments", []))
    except (OSError, ValueError):
        return frozenset()


def _generate_request_id() -> str:
    return f"req_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"


def _generate_prediction_id() -> str:
    return f"pred_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"


def _validate_semantics(
    request: PredictionRequest, state: ServiceState
) -> tuple[datetime, datetime]:
    """Layer 2 semantic validation: timestamps, interval, staleness (section 11)."""
    try:
        as_of = parse_utc(request.timestamp)
        data_ts = parse_utc(request.market_context.data_timestamp)
    except ValueError as error:
        raise ApiError(INVALID_REQUEST, "timestamp fields must be ISO-8601 datetimes") from error
    now = datetime.now(timezone.utc)
    if as_of > now + _timedelta_seconds(FUTURE_TOLERANCE_SECONDS):
        raise ApiError(INVALID_REQUEST, "prediction timestamp must not be in the future")
    if request.interval not in ("1d",):
        raise ApiError(INVALID_REQUEST, "interval must be '1d' in the MVP")
    _validate_instrument(request.ticker, state)
    max_age = state.config.api.stale_data_max_age_seconds
    if (now - data_ts).total_seconds() > max_age:
        raise ApiError(
            STALE_DATA,
            "market data timestamp is older than the configured freshness window",
        )
    if data_ts > as_of + _timedelta_seconds(FUTURE_TOLERANCE_SECONDS):
        raise ApiError(INVALID_REQUEST, "market data timestamp cannot postdate the prediction time")
    return as_of, data_ts


def _timedelta_seconds(seconds: int):
    from datetime import timedelta

    return timedelta(seconds=seconds)


def _validate_instrument(ticker: str, state: ServiceState) -> None:
    """Unknown instruments are INVALID_REQUEST (blueprint section 11.1).

    The instrument universe comes from the training dataset manifest; an
    empty universe (metadata unavailable) is permissive and logged once —
    never a silent behavior change mid-request.
    """
    if not ticker or ticker != ticker.strip().upper():
        raise ApiError(INVALID_REQUEST, "ticker must be an uppercase instrument symbol")
    if state.known_instruments and ticker not in state.known_instruments:
        raise ApiError(
            INVALID_REQUEST,
            f"instrument {ticker!r} is not a registered research instrument",
        )


def _validate_features(
    request: PredictionRequest, model: LoadedModel
) -> tuple[list[float], list[str]]:
    """Layer 3 feature-set validation: names, count, finiteness (section 11.1)."""
    expected = model.feature_names or tuple(request.features.keys())
    if not expected:
        raise ApiError(FEATURE_VALIDATION_FAILED, "request contains no features")
    missing = [name for name in expected if name not in request.features]
    if missing:
        raise ApiError(
            FEATURE_VALIDATION_FAILED,
            f"missing required features: {missing[:5]}",
        )
    unexpected = [name for name in request.features if name not in expected]
    if unexpected:
        raise ApiError(
            FEATURE_VALIDATION_FAILED,
            f"unexpected features: {unexpected[:5]}",
        )
    values: list[float] = []
    for name in expected:
        value = request.features[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ApiError(
                FEATURE_VALIDATION_FAILED,
                f"feature {name!r} must be a finite number",
            )
        numeric = float(value)
        if not np.isfinite(numeric):
            raise ApiError(
                FEATURE_VALIDATION_FAILED,
                f"feature {name!r} must be a finite number",
            )
        values.append(numeric)
    return values, list(expected)


def _predict(model: LoadedModel, values: list[float]) -> tuple[str, dict[str, float]]:
    """Run model inference and validate the output (sections 14/16)."""
    try:
        matrix = np.asarray([values], dtype=float)
        if model.scaler is not None:
            matrix = model.scaler.transform(matrix)
        estimator = model.estimator
        prediction = estimator.predict(matrix)
        probabilities = estimator.predict_proba(matrix)
    except (ValueError, RuntimeError, AttributeError) as error:
        raise ApiError(
            PREDICTION_FAILED,
            "model inference failed for the supplied feature vector",
        ) from error
    classes = [str(label) for label in model_classes(model)]
    if len(probabilities[0]) != len(classes) or not np.isfinite(probabilities[0]).all():
        raise ApiError(PREDICTION_FAILED, "model produced an invalid probability distribution")
    distribution = {
        label: round(float(probabilities[0][index]), 6) for index, label in enumerate(classes)
    }
    predicted = str(prediction[0])
    if predicted not in distribution:
        raise ApiError(PREDICTION_FAILED, "model predicted an unknown class")
    return predicted, distribution


def run_prediction(state: ServiceState, request: PredictionRequest) -> PredictionResponse:
    """Execute the full deterministic prediction pipeline for one request."""
    started = time.perf_counter()
    request_id = request.request_id or _generate_request_id()
    prediction_id = _generate_prediction_id()
    inference_timestamp = datetime.now(timezone.utc)

    # Layers 2-4: semantics, features, compatibility.
    as_of, data_ts = _validate_semantics(request, state)
    model_version = resolve_model_version(state.config, request.model_version)
    model = state.cache.get(model_version) or load_model(state.config, model_version)
    state.cache.put(model)
    # Layer 3 first: the complete feature vector (names + values) must be
    # valid before it can be compared against the model schema (layer 4).
    values, feature_names = _validate_features(request, model)
    check_compatibility(
        model,
        feature_set_version=request.feature_set_version,
        feature_names=tuple(feature_names),
        label_version=state.config.dataset.label_version,
    )

    predicted, distribution = _predict(model, values)
    confidence = distribution[predicted]

    decision = decision_module.decide(
        probabilities=distribution,
        buy_threshold=state.config.backtest.signal.buy_threshold,
        sell_threshold=state.config.backtest.signal.sell_threshold,
        recent_volatility=request.market_context.recent_volatility,
        volatility_20d=request.features.get("volatility_20d"),
    )

    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
    response = PredictionResponse(
        prediction_id=prediction_id,
        request_id=request_id,
        status=STATUS_SUCCESS if decision.signal in (BUY, SELL) else STATUS_NO_TRADE,
        ticker=request.ticker,
        inference_timestamp=inference_timestamp.isoformat(),
        inference_time_ms=elapsed_ms,
        model=ModelInfoBlock(
            model_version=model.model_version,
            model_type=model.model_type,
            feature_version=model.feature_version,
            label_version=model.label_version,
        ),
        model_output=ModelOutput(
            prediction=predicted,
            probabilities=distribution,
            confidence=confidence,
            expected_return=None,
        ),
        decision_output=DecisionOutput(
            signal=decision.signal,
            confidence=decision.confidence,
            expected_return=decision.expected_return,
            risk_score=decision.risk_score,
            position_size=decision.position_size,
            reason_codes=list(decision.reason_codes),
            strategy_version=state.strategy_version,
        ),
        features_used=feature_names,
    )

    audit_record = {
        "prediction_id": prediction_id,
        "request_id": request_id,
        "ticker": request.ticker,
        "input_timestamp": as_of.isoformat(),
        "data_timestamp": data_ts.isoformat(),
        "model_version": model.model_version,
        "feature_version": model.feature_version,
        "label_version": model.label_version,
        "strategy_version": state.strategy_version,
        "prediction": predicted,
        "probabilities": distribution,
        "confidence": confidence,
        "signal": decision.signal,
        "risk_score": decision.risk_score,
        "reason_codes": list(decision.reason_codes),
        "inference_timestamp": inference_timestamp.isoformat(),
        "latency_ms": elapsed_ms,
        "api_version": API_VERSION,
        "mode": state.mode,
    }
    try:
        write_prediction_record(state.config.api.audit_dir, audit_record)
        audit_written = True
    except AuditError as error:
        # Milestone section 27: never silently report an audited prediction
        # when persistence failed. The prediction itself succeeded and is
        # returned, but the response carries an explicit unaudited marker.
        audit_written = False
        logger.error(
            "prediction_audit_failed",
            prediction_id=prediction_id,
            request_id=request_id,
            error=str(error),
            status="UNAUDITED",
        )
    response.audit_written = audit_written

    logger.info(
        "prediction_served",
        request_id=request_id,
        prediction_id=prediction_id,
        ticker=request.ticker,
        model_version=model.model_version,
        feature_version=model.feature_version,
        strategy_version=state.strategy_version,
        latency_ms=elapsed_ms,
        status=response.status,
        signal=decision.signal,
        mode=state.mode,
    )
    return response
