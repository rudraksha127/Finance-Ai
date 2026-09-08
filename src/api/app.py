"""FastAPI application for the inference service (M09).

Implements the four blueprint endpoints (INFERENCE_API_BLUEPRINT
section 6.1) at root paths (section 26.2 — the ``/api/v1`` prefix is
explicitly deferred by the blueprint), the standardized error envelope
(section 16), startup readiness (sections 13/17), and research/paper
mode safety (section 24 — live mode refuses to boot; no execution code
exists in this service).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.api import orchestrator
from src.api.errors import (
    FEATURE_VALIDATION_FAILED,
    INTERNAL_ERROR,
    PREDICTION_FAILED,
    SERVICE_NOT_READY,
    ApiError,
    error_response,
)
from src.api.orchestrator import ServiceState, build_service_state
from src.api.reads import configure_reads
from src.api.reads import router as reads_router
from src.api.resolver import (
    API_VERSION,
    available_model_versions,
    load_model,
    resolve_model_version,
)
from src.api.schemas import (
    HealthResponse,
    ModelInfoResponse,
    PredictionRequest,
    PredictionResponse,
    ReadyResponse,
    VersionResponse,
)
from src.config.loader import AppConfig, load_config
from src.logging.logger import get_logger

logger = get_logger("api.app")

CONFIG: AppConfig | None = None
STATE: ServiceState | None = None


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Application factory; used by both the CLI entry point and tests."""
    global CONFIG, STATE
    CONFIG = config or load_config()
    if CONFIG.api.mode not in ("research", "paper"):
        # Blueprint section 24.2: the service refuses to boot in live mode.
        raise SystemExit("api.mode 'live' is not implemented; refusing to start")
    app = FastAPI(
        title="Finance AI Inference API",
        description=(
            "Research-only prediction service for the Finance AI MVP. "
            "Not financial advice; not a live trading system."
        ),
        version=API_VERSION,
    )
    STATE = build_service_state(CONFIG)
    # Dashboard read endpoints (UI_UX_BLUEPRINT §29.3): read-only,
    # file-backed views over the existing artifact stores.
    configure_reads(CONFIG)
    app.include_router(reads_router)

    @app.exception_handler(ApiError)
    async def _handle_api_error(_: Request, error: ApiError) -> JSONResponse:
        return error_response(error)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        # Layer 1 (pydantic) failures map to the standard envelope; the raw
        # pydantic detail is not leaked (section 16.3).
        request_id = _request_id_from(request)
        return error_response(
            ApiError(
                FEATURE_VALIDATION_FAILED,
                "request payload violates the API contract",
                request_id=request_id,
            )
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, error: Exception) -> JSONResponse:
        logger.error(
            "api_unexpected_error",
            error_type=type(error).__name__,
            status="ERROR",
        )
        return error_response(ApiError(INTERNAL_ERROR, "unexpected server error"))

    @app.post(
        "/predict",
        response_model=PredictionResponse,
        responses={
            400: {"description": "Invalid request"},
            404: {"description": "Model not found"},
            409: {"description": "Version incompatibility"},
            422: {"description": "Validation failure"},
            500: {"description": "Prediction/decision failure"},
            503: {"description": "Service not ready"},
        },
    )
    def predict(payload: PredictionRequest) -> PredictionResponse:
        if STATE is None or STATE.default_model_version is None:
            raise ApiError(SERVICE_NOT_READY, "service is not ready; no model is loaded")
        try:
            return orchestrator.run_prediction(STATE, payload)
        except ApiError:
            raise
        except Exception as error:  # fail closed; never fabricate (section 28.2)
            logger.error(
                "prediction_pipeline_failed",
                ticker=payload.ticker,
                error_type=type(error).__name__,
                status="ERROR",
            )
            raise ApiError(PREDICTION_FAILED, "prediction pipeline failed") from error

    @app.get(
        "/health",
        response_model=HealthResponse,
        responses={503: {"description": "Degraded — model not loaded"}},
    )
    def health() -> JSONResponse:
        assert STATE is not None and CONFIG is not None
        model_loaded = STATE.default_model_version is not None
        body = HealthResponse(
            status="ok" if model_loaded else "degraded",
            model_loaded=model_loaded,
            model_version=STATE.default_model_version,
            uptime_seconds=round(
                (datetime.now(timezone.utc) - STATE.started_at).total_seconds(), 3
            ),
            mode=STATE.mode,
        )
        # Blueprint section 17.2: HTTP 200 only when ready; 503 when degraded.
        return JSONResponse(
            status_code=200 if model_loaded else 503,
            content=body.model_dump(),
        )

    @app.get(
        "/ready",
        response_model=ReadyResponse,
        responses={503: {"description": "Service not ready"}},
    )
    def ready() -> JSONResponse:
        assert STATE is not None and CONFIG is not None
        checks = {
            "config_loaded": CONFIG is not None,
            "model_available": bool(available_model_versions(CONFIG)),
            "default_model_loaded": STATE.default_model_version is not None,
            "audit_dir_writable": _audit_dir_writable(CONFIG),
        }
        all_ready = all(checks.values())
        body = ReadyResponse(status="ready" if all_ready else "not_ready", checks=checks)
        return JSONResponse(status_code=200 if all_ready else 503, content=body.model_dump())

    @app.get(
        "/model/info",
        response_model=ModelInfoResponse,
        responses={
            404: {"description": "Model not found"},
            503: {"description": "Service not ready"},
        },
    )
    def model_info(model_version: str | None = Query(default=None)) -> ModelInfoResponse:
        assert CONFIG is not None and STATE is not None
        if STATE.default_model_version is None:
            raise ApiError(SERVICE_NOT_READY, "service is not ready; no model is loaded")
        resolved = resolve_model_version(CONFIG, model_version)
        model = STATE.cache.get(resolved) or load_model(CONFIG, resolved)
        STATE.cache.put(model)
        metadata = model.metadata
        return ModelInfoResponse(
            model_version=model.model_version,
            model_type=model.model_type,
            status="active" if resolved == STATE.default_model_version else "available",
            trained_at=metadata.get("training_timestamp"),
            feature_version=model.feature_version,
            label_version=model.label_version,
            dataset_version=model.dataset_version,
            feature_count=model.feature_count,
            metrics=metadata.get("metrics") or {},
        )

    @app.get("/version", response_model=VersionResponse)
    def version() -> VersionResponse:
        assert CONFIG is not None and STATE is not None
        return VersionResponse(
            api_version=API_VERSION,
            model_version=STATE.default_model_version,
            # Report the versions of the resolved default model when available;
            # fall back to configured values when no model is loaded.
            feature_version=(STATE.default_feature_version or CONFIG.features.version),
            label_version=(STATE.default_label_version or CONFIG.dataset.label_version),
            strategy_version=CONFIG.backtest.strategy_version,
            mode=STATE.mode,
        )

    return app


def _request_id_from(request: Request) -> str | None:
    try:
        body = getattr(request.state, "json_body", None)
    except AttributeError:
        body = None
    return body if isinstance(body, str) and body else None


def _audit_dir_writable(config: AppConfig) -> bool:
    try:
        directory = config.api.audit_dir
        directory = directory if directory.is_absolute() else Path.cwd() / directory
        probe = directory / ".ready_probe"
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text("ready", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def get_app() -> FastAPI:
    """ASGI entry point for ``uvicorn src.api.app:get_app``."""
    return create_app()
