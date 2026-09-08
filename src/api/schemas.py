"""Request/response contracts for the inference API (M09).

Implements INFERENCE_API_BLUEPRINT sections 7 (request), 8 (response),
and 16 (error envelope) with pydantic strictness: no silent repair of
malformed input (section 11.2). Semantic validation (staleness, ranges,
feature-set completeness) happens in the orchestrator — pydantic covers
layer 1 only.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Format-only guard at layer 1; unknown/invalid instruments are rejected
# semantically in the orchestrator (blueprint section 11.1 maps unknown
# instruments to INVALID_REQUEST, not FEATURE_VALIDATION_FAILED).
TICKER_PATTERN = r"^[A-Za-z0-9.\-]{1,12}$"
INTERVALS = ("1d",)  # MVP supports daily only (blueprint section 7.3)


class MarketContext(BaseModel):
    """Minimal decision-engine inputs (blueprint section 7.2/12.3)."""

    model_config = ConfigDict(extra="forbid")

    current_price: float = Field(gt=0, allow_inf_nan=False)
    recent_volatility: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    data_timestamp: str


class PredictionRequest(BaseModel):
    """POST /predict request (blueprint section 7)."""

    model_config = ConfigDict(extra="forbid")

    request_id: str | None = Field(default=None, max_length=128)
    ticker: str = Field(pattern=TICKER_PATTERN)
    timestamp: str
    interval: str
    feature_set_version: str = Field(min_length=1, max_length=64)
    model_version: str | None = Field(default=None, min_length=1, max_length=128)
    features: dict[str, Any]
    market_context: MarketContext


class ModelInfoBlock(BaseModel):
    """Resolved model identity echoed in every response (section 8.3)."""

    model_version: str
    model_type: str
    feature_version: str
    label_version: str


class ModelOutput(BaseModel):
    """Raw model result — never merged with the decision (section 8.1)."""

    prediction: str
    probabilities: dict[str, float]
    confidence: float
    expected_return: float | None = None


class DecisionOutput(BaseModel):
    """Shared decision-engine result (section 8.2)."""

    signal: str
    confidence: float
    expected_return: float | None = None
    risk_score: float
    position_size: float | None = None
    reason_codes: list[str]
    strategy_version: str


class PredictionResponse(BaseModel):
    """POST /predict success response (blueprint section 8.2)."""

    prediction_id: str
    request_id: str
    status: str
    ticker: str
    inference_timestamp: str
    inference_time_ms: float
    model: ModelInfoBlock
    model_output: ModelOutput
    decision_output: DecisionOutput
    features_used: list[str]
    audit_written: bool = True  # false => prediction served but NOT persisted to the audit trail


class HealthResponse(BaseModel):
    """GET /health (blueprint section 17.2)."""

    status: str
    model_loaded: bool
    model_version: str | None
    uptime_seconds: float
    mode: str


class ReadyResponse(BaseModel):
    """GET /ready — structured readiness detail (milestone section 23)."""

    status: str
    checks: dict[str, bool]


class ModelInfoResponse(BaseModel):
    """GET /model/info (blueprint section 6.4)."""

    model_version: str
    model_type: str
    status: str
    trained_at: str | None
    feature_version: str
    label_version: str
    dataset_version: str
    feature_count: int
    metrics: dict[str, Any]


class VersionResponse(BaseModel):
    """GET /version (blueprint section 6.5)."""

    api_version: str
    model_version: str | None
    feature_version: str
    label_version: str
    strategy_version: str
    mode: str
