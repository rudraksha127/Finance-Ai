"""Standardized error model for the inference API (M09).

Every failure maps to the blueprint section 16.1 envelope::

    {"error": {"code": ..., "message": ..., "request_id": ..., "timestamp": ...}}

Rules (section 16.3): no stack traces, no artifact paths, no secrets;
every failure is deterministic for a given input; a prediction is never
fabricated to avoid an error (fail closed, section 28.2).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse

INVALID_REQUEST = "INVALID_REQUEST"
FEATURE_VALIDATION_FAILED = "FEATURE_VALIDATION_FAILED"
MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
MODEL_VERSION_INCOMPATIBLE = "MODEL_VERSION_INCOMPATIBLE"
FEATURE_VERSION_INCOMPATIBLE = "FEATURE_VERSION_INCOMPATIBLE"
STALE_DATA = "STALE_DATA"
PREDICTION_FAILED = "PREDICTION_FAILED"
DECISION_ENGINE_FAILED = "DECISION_ENGINE_FAILED"
SERVICE_NOT_READY = "SERVICE_NOT_READY"
INTERNAL_ERROR = "INTERNAL_ERROR"

HTTP_STATUS: dict[str, int] = {
    INVALID_REQUEST: 400,
    FEATURE_VALIDATION_FAILED: 422,
    MODEL_NOT_FOUND: 404,
    MODEL_VERSION_INCOMPATIBLE: 409,
    FEATURE_VERSION_INCOMPATIBLE: 409,
    STALE_DATA: 422,
    PREDICTION_FAILED: 500,
    DECISION_ENGINE_FAILED: 500,
    SERVICE_NOT_READY: 503,
    INTERNAL_ERROR: 500,
}


class ApiError(Exception):
    """A deterministic, client-safe API failure with a blueprint error code."""

    def __init__(self, code: str, message: str, *, request_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.request_id = request_id

    def to_payload(self) -> dict[str, Any]:
        """Serialize to the blueprint error envelope."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "request_id": self.request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        }


def error_response(error: ApiError) -> JSONResponse:
    """Render an :class:`ApiError` as its blueprint status code + envelope."""
    return JSONResponse(
        status_code=HTTP_STATUS.get(error.code, 500),
        content=error.to_payload(),
    )


async def api_error_handler(_: Request, error: ApiError) -> Response:
    """FastAPI handler so raised ApiErrors always use the standard envelope."""
    return error_response(error)
