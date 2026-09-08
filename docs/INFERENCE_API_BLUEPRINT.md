# PREDICTION & INFERENCE API BLUEPRINT — Finance AI MVP

> Clean inference service that exposes trained Finance AI models to downstream consumers.
> Reproducible, versioned predictions. Prediction → Decision → Response.
> Execution is OUT OF SCOPE for MVP. This document is architecture + API contract design only.

---

## Table of Contents

1. [Primary Objective](#1-primary-objective)
2. [Create Document](#2-create-document)
3. [Service Responsibilities](#3-service-responsibilities)
4. [API Architecture](#4-api-architecture)
5. [API Technology](#5-api-technology)
6. [Endpoint Design](#6-endpoint-design)
7. [Prediction Request Contract](#7-prediction-request-contract)
8. [Prediction Response Contract](#8-prediction-response-contract)
9. [Version Resolution](#9-version-resolution)
10. [Model Compatibility](#10-model-compatibility)
11. [Input Validation](#11-input-validation)
12. [Feature Sourcing](#12-feature-sourcing)
13. [Model Loading](#13-model-loading)
14. [Inference Performance](#14-inference-performance)
15. [Batch Prediction](#15-batch-prediction)
16. [Error Model](#16-error-model)
17. [Health Checks](#17-health-checks)
18. [Observability](#18-observability)
19. [Inference Audit Trail](#19-inference-audit-trail)
20. [Idempotency](#20-idempotency)
21. [Security](#21-security)
22. [Configuration](#22-configuration)
23. [Backtest Compatibility](#23-backtest-compatibility)
24. [Research / Live Mode Separation](#24-research--live-mode-separation)
25. [Response Explanation](#25-response-explanation)
26. [Contract Versioning](#26-contract-versioning)
27. [Testing Strategy](#27-testing-strategy)
28. [Failure & Degradation](#28-failure--degradation)
29. [API Documentation](#29-api-documentation)
30. [Future Extensions](#30-future-extensions)
31. [Acceptance Criteria](#31-acceptance-criteria)
32. [Consistency Check](#32-consistency-check)
33. [Deliverables](#33-deliverables)
34. [Stop Condition](#34-stop-condition)

---

## 1. Primary Objective

Design a clean inference service that exposes trained Finance AI models to downstream consumers (researchers, paper-simulation tooling, and eventually the dashboard).

**Core flow:**

```
Client
  ↓
Inference API
  ↓
Input Validation
  ↓
Data / Feature Validation
  ↓
Model Resolution
  ↓
Model Inference
  ↓
Prediction Validation
  ↓
Decision Engine
  ↓
Response
```

**The service must return reproducible, versioned predictions.** Every response is traceable to an exact model version, feature version, and input snapshot.

**The service never executes anything.** It produces research signals through the shared Decision Engine (RISK_DECISION_ENGINE_BLUEPRINT.md) — never orders.

---

## 2. Create Document

**Create:** `docs/INFERENCE_API_BLUEPRINT.md`

---

## 3. Service Responsibilities

### 3.1 What the Inference Service DOES

| # | Responsibility | Description |
|---|----------------|-------------|
| 1 | **Accept prediction requests** | Receive validated feature payloads for a ticker + timestamp |
| 2 | **Validate request data** | Schema, types, ranges, NaN/Inf checks — deterministic failures |
| 3 | **Resolve compatible model version** | Explicit version or configured default (Section 9) |
| 4 | **Load/use model artifact** | From the file-based registry (models/) — never retrain |
| 5 | **Generate prediction** | Class probabilities + point prediction via the model runtime |
| 6 | **Validate prediction** | Probability sums, ranges, alignment with data timestamp |
| 7 | **Call Decision Engine where appropriate** | Convert prediction → research signal via the SHARED decision logic |
| 8 | **Return structured result** | Machine-readable model output + decision output |
| 9 | **Log inference metadata** | Structured audit trail (Section 19) |

### 3.2 What the Inference Service MUST NOT do

| Prohibited Action | Why |
|-------------------|-----|
| Train models | Training is the TrainingEngine's job (TRAINING_PIPELINE_BLUEPRINT.md) |
| Modify datasets | Data layer is read-only from the API's perspective |
| Perform research optimization | No threshold tuning, no grid search at request time |
| Place live orders | Execution is OUT OF SCOPE for MVP (ADR-0020) |
| Modify model artifacts | Registry is append-only; versions are immutable |
| Silently change model versions | Resolution is deterministic and locked per request (Section 9) |
| Fabricate predictions on failure | Fail closed — errors are returned, never fake outputs |

---

## 4. API Architecture

### 4.1 Service Boundary

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT                                       │
│  (researcher tooling / paper simulation / dashboard)                │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP (JSON)
┌──────────────────────────────▼──────────────────────────────────────┐
│                     API Gateway / HTTP Layer                        │
│  (FastAPI app — routing, middleware, rate limiting, size limits)    │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Request Validator                            │
│  (schema, types, ranges, feature-set version)                       │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Inference Orchestrator                        │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────┐  │
│  │ Feature/Data     │  │ Model Resolver   │  │ Model Runtime     │  │
│  │ Validator        │  │ (version lock)   │  │ (loaded artifact) │  │
│  └──────────────────┘  └──────────────────┘  └───────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                   Decision Engine (SHARED)                    │  │
│  │  Same module used by backtesting — never a second copy        │  │
│  └───────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Response Serializer                          │
│  (model output + decision output, version identifiers)              │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Observability                               │
│  (structlog JSON logs, audit trail, latency)                        │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Module Boundaries

| Boundary | Component | Responsibility | Must NOT |
|----------|-----------|----------------|----------|
| HTTP layer | `src/api/app.py` (FastAPI) | Routing, middleware, lifecycle | Contain business logic |
| Routes | `src/api/routes.py` | Endpoint definitions | Compute features or decide |
| Schemas | `src/api/schemas.py` (pydantic) | Request/response contracts | Execute logic |
| Orchestrator | `src/api/prediction.py` (PredictionService) | Coordinate validation → resolve → infer → decide | Touch storage/registry internals directly |
| Model runtime | `src/model/registry.py` + loaded artifact | Load + run model | Decide anything |
| Decision Engine | shared module (RISK_DECISION_ENGINE_BLUEPRINT.md §23) | Signal + risk logic | Call brokers, retrain, invent data |

The API layer is thin. It orchestrates; it does not duplicate logic that exists in the model layer or decision layer.

---

## 5. API Technology

### 5.1 Candidate Evaluation

| Option | Strengths | Weaknesses | MVP Fit |
|--------|-----------|------------|---------|
| **FastAPI** | Async, pydantic validation built-in, auto OpenAPI docs, modern, active ecosystem | Slightly more concepts than Flask | ✅ **RECOMMENDED** |
| **Flask** | Minimal, familiar | Manual validation, manual OpenAPI, sync-only | ⚠️ Workable |
| **gRPC** | Fast, typed, streaming | Infra overhead, tooling complexity, poor browser fit | ❌ Overkill for MVP |

### 5.2 Recommendation: FastAPI

**FastAPI is already the committed choice in SYSTEM_ARCHITECTURE.md §2.9** (Prediction Service dependencies: `FastAPI`, `pydantic`, `structlog`). PRD FR-API-08 permits "FastAPI or Flask"; this blueprint locks the choice.

**Why FastAPI:**
- **Declarative validation** — pydantic models define the request/response contract directly; validation failures are deterministic and structured
- **Automatic OpenAPI documentation** — satisfies Section 29 without maintaining a duplicate API definition
- **Async by default** — clean fit for concurrent research/paper requests at MVP scale
- **Testable** — FastAPI's test client supports contract and integration tests without a live server

**Do not add unnecessary infrastructure.** No Kubernetes, no microservices, no API gateway product, no database. A single FastAPI process on localhost is the MVP (NFR-SE-04: local only).

---

## 6. Endpoint Design

### 6.1 MVP Endpoint Set

| Method | Path | Purpose | Priority | Source |
|--------|------|---------|----------|--------|
| POST | `/predict` | Single prediction + decision for one ticker/timestamp | P0 | PRD FR-API-02 |
| GET | `/health` | Liveness + readiness | P0 | PRD FR-API-03 |
| GET | `/model/info` | Metadata of the resolved/active model | P1 | PRD FR-API-04 |
| GET | `/version` | API + strategy contract introspection | P1 | New (this blueprint) |

Only these four endpoints are justified. Batch prediction is explicitly deferred (Section 15). Dashboard data reads come from the same API per PRD FR-DB-05.

**Path note:** MVP keeps the root paths exactly as defined in SYSTEM_ARCHITECTURE.md §5.2 (`/predict`, `/health`, `/model/info`). No `/api/v1/` prefix in MVP — see Section 26 for contract versioning policy.

### 6.2 POST /predict

| Attribute | Value |
|-----------|-------|
| **Purpose** | Produce a model prediction and a research decision for one instrument at one timestamp |
| **Method** | POST |
| **Path** | `/predict` |
| **Request schema** | Section 7 |
| **Response schema** | Section 8 (200 OK) |
| **Status codes** | 200 (success, incl. NO_TRADE decision), 400 (INVALID_REQUEST), 404 (MODEL_NOT_FOUND), 409 (version incompatibility), 422 (feature/validation failure, STALE_DATA), 429 (rate limited), 500 (PREDICTION_FAILED / DECISION_ENGINE_FAILED / INTERNAL_ERROR), 503 (model unavailable), 504 (timeout) |
| **Validation rules** | Full contract validation (Section 11); feature set version check; model compatibility check (Section 10) |
| **Failure modes** | Any validation/compatibility failure → structured error, never a fabricated prediction |

### 6.3 GET /health

| Attribute | Value |
|-----------|-------|
| **Purpose** | Report liveness and readiness (Section 17) |
| **Method** | GET |
| **Path** | `/health` |
| **Request schema** | None |
| **Response schema** | `{ "status": "ok" \| "degraded", "model_loaded": bool, "model_version": str \| null, "uptime_seconds": float, "mode": "research" \| "paper" }` |
| **Status codes** | 200 (ready), 503 (not ready — model not loaded / registry unreadable) |
| **Validation rules** | None |
| **Failure modes** | Never performs inference; must not fail because a model is stale (that is /predict's concern) |

### 6.4 GET /model/info

| Attribute | Value |
|-----------|-------|
| **Purpose** | Return metadata of the resolved default model (or requested version via query param `?model_version=`) |
| **Method** | GET |
| **Path** | `/model/info` |
| **Request schema** | Optional query param `model_version` |
| **Response schema** | `{ "model_version", "model_type", "status", "trained_at", "feature_version", "label_version", "dataset_version", "metrics": {...}, "feature_count" }` |
| **Status codes** | 200, 404 (requested version unknown) |
| **Validation rules** | If `model_version` given, it must exist in the registry |
| **Failure modes** | Registry unreadable → 503; unknown version → 404 |

### 6.5 GET /version

| Attribute | Value |
|-----------|-------|
| **Purpose** | Return all contract version identifiers for audit/negotiation (Section 26) |
| **Method** | GET |
| **Path** | `/version` |
| **Request schema** | None |
| **Response schema** | `{ "api_version": "v1", "model_version": "...", "feature_version": "...", "label_version": "...", "strategy_version": "stg_v0.1", "mode": "research" \| "paper" }` |
| **Status codes** | 200 |
| **Validation rules** | None |
| **Failure modes** | Config unreadable → 500 |

---

## 7. Prediction Request Contract

### 7.1 Design Principle

**Clients send features, not raw history.** The MVP avoids transmitting large historical datasets per request. The client sends the pre-computed feature vector (52 MVP features) plus a minimal market context required by the Decision Engine.

### 7.2 Request Schema

```json
{
  "request_id": "req_20260904_100000_001",
  "ticker": "AAPL",
  "timestamp": "2026-09-04T10:00:00Z",
  "interval": "1d",
  "feature_set_version": "feat_3f9a...",
  "model_version": "v1.0.0-20260904",
  "features": {
    "returns_1d": 0.012,
    "returns_5d": 0.034,
    "volatility_20d": 0.021,
    "volume_ratio_5d": 1.23,
    "rsi_14d": 62.5
  },
  "market_context": {
    "current_price": 185.60,
    "recent_volatility": 0.25,
    "data_timestamp": "2026-09-04T09:30:00Z"
  }
}
```

### 7.3 Field Specification

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `request_id` | string | No | Client-generated idempotency/correlation key; generated server-side if absent |
| `ticker` | string | **Yes** | Uppercase symbol; must be a known/registered research instrument |
| `timestamp` | datetime | **Yes** | ISO 8601 UTC; the prediction-as-of time; must be ≤ now (with tolerance) |
| `interval` | string | **Yes** | MVP supports `"1d"` only (daily frequency per PRD) |
| `feature_set_version` | string | **Yes** | Must match the model's feature version (Section 10) |
| `model_version` | string | No | Explicit version; if omitted → configured default (Section 9) |
| `features` | object | **Yes** | Exactly the feature names/types expected by the model's input schema |
| `market_context.current_price` | float | **Yes** | > 0, not NaN/Inf; decision-engine input |
| `market_context.recent_volatility` | float | No | If absent: derived deterministically from `features.volatility_20d` when present, else configured default, else NO_TRADE per RISK blueprint §4.3 |
| `market_context.data_timestamp` | datetime | **Yes** | Timestamp of the data used to compute the features; staleness check target (Section 11) |

### 7.4 What the Client Must NOT Send

- Full OHLCV history (only derived features + minimal market context)
- Labels or future data of any kind
- Secrets, credentials, or free-form payloads

---

## 8. Prediction Response Contract

### 8.1 Core Distinction

> **MODEL OUTPUT** = what the model says. **DECISION OUTPUT** = what the system should do with it.

These are distinct objects in every response (ADR-0020: Prediction / Decision / Execution separation).

### 8.2 Response Schema

```json
{
  "prediction_id": "pred_20260904_100000_001",
  "request_id": "req_20260904_100000_001",
  "status": "success",
  "ticker": "AAPL",
  "inference_timestamp": "2026-09-04T10:00:00.123Z",
  "inference_time_ms": 12.3,

  "model": {
    "model_version": "v1.0.0-20260904",
    "model_type": "random_forest",
    "feature_version": "feat_3f9a...",
    "label_version": "label_v0.1"
  },

  "model_output": {
    "prediction": "UP",
    "probabilities": { "UP": 0.72, "DOWN": 0.15, "HOLD": 0.13 },
    "confidence": 0.72,
    "expected_return": null
  },

  "decision_output": {
    "signal": "BUY",
    "confidence": 0.72,
    "expected_return": 0.012,
    "risk_score": 0.35,
    "position_size": 1.0,
    "reason_codes": ["MODEL_SIGNAL_BUY", "EDGE_ABOVE_COST"],
    "strategy_version": "stg_v0.1"
  },

  "features_used": ["returns_1d", "returns_5d", "volatility_20d", "volume_ratio_5d", "rsi_14d"]
}
```

### 8.3 Field Specification

| Field | Source | Description |
|-------|--------|-------------|
| `prediction_id` | API | Unique immutable identifier for audit trail (Section 19) |
| `request_id` | API/echo | Correlation with the request |
| `status` | API | `success` \| `no_trade` \| `error` |
| `ticker` | echo | Request ticker |
| `inference_timestamp` | API | When inference completed |
| `inference_time_ms` | API | End-to-end latency for this request |
| `model.*` | resolver | Resolved version identifiers (PRD FR-API-06: version in every response) |
| `model_output.*` | model runtime | Raw model result — prediction, probabilities, confidence, optional expected_return |
| `decision_output.*` | Decision Engine | Signal, risk score, position size, reason codes, strategy version |
| `features_used` | API | Feature names consumed by the model (audit convenience) |

### 8.4 NO_TRADE Responses

A NO_TRADE decision is a **successful** response (status 200). Example:

```json
{
  "prediction_id": "pred_20260904_100000_002",
  "request_id": "req_20260904_100000_002",
  "status": "no_trade",
  "ticker": "AAPL",
  "model_output": {
    "prediction": "UP",
    "probabilities": { "UP": 0.48, "DOWN": 0.31, "HOLD": 0.21 },
    "confidence": 0.48
  },
  "decision_output": {
    "signal": "NO_TRADE",
    "confidence": 0.48,
    "expected_return": null,
    "risk_score": 0.61,
    "position_size": null,
    "reason_codes": ["CONFIDENCE_BELOW_THRESHOLD", "EDGE_BELOW_COST"],
    "strategy_version": "stg_v0.1"
  }
}
```

Abstention is a feature (RISK blueprint §27) — NO_TRADE is not an error.

---

## 9. Version Resolution

### 9.1 Resolution Strategy (Deterministic)

```
1. If request.model_version is present and valid:
     → use it (explicit wins)

2. Else:
     → use the configured default model
       (config: api.default_model; if empty → registry active_model)

3. Lock the resolved version for the duration of the request.
   Echo it in the response. Never re-resolve mid-request.
```

### 9.2 Rules

| Rule | Description |
|------|-------------|
| **Explicit wins** | A requested version is always honored if it exists and is compatible |
| **Default is configurable** | `api.default_model` in YAML; empty means "registry active" |
| **No silent switching** | The default may only change via explicit config change + restart. Never automatically at request time |
| **No runtime mutation** | The API never writes to the registry or changes model status |
| **Evaluation pinning** | Ongoing evaluations (repeated predictions over time) MUST pass an explicit `model_version` — the API rejects version-omitting requests in evaluation mode, or the client pins the version itself |

### 9.3 Rejected Strategies

| Strategy | Rejected? | Why |
|----------|-----------|-----|
| Round-robin / random model selection | ❌ | Non-deterministic, unresearchable |
| Automatic best-metrics model at request time | ❌ | Violates version locking and reproducibility |
| Hot-swapping defaults without restart | ❌ | Silent behavior change mid-evaluation |

---

## 10. Model Compatibility

### 10.1 Pre-Inference Verification

Before running inference the API verifies:

| Check | Source | Failure Action |
|-------|--------|----------------|
| Model version exists | registry | `MODEL_NOT_FOUND` (404) |
| Model status usable | metadata (`active`; `COMPLETED` training status) | `MODEL_VERSION_INCOMPATIBLE` (409) |
| Feature version matches request | `model.feature_version` vs `request.feature_set_version` | `FEATURE_VERSION_INCOMPATIBLE` (409) |
| Label version compatible | model metadata vs configured label version | `MODEL_VERSION_INCOMPATIBLE` (409) |
| Expected input schema matches | artifact metadata (`feature_count`, feature names) | `FEATURE_VALIDATION_FAILED` (422) |
| Model not too old | `model_max_age_days` (RISK blueprint §15.3: 30 days) | Flag + `MODEL_VERSION_OLD` warning; still serves (research mode) |

### 10.2 Never Attempt Hidden Conversion

If the request features do not match the model's expected schema, the API **rejects** the request. It never:
- Reorders, renames, or infers missing features silently
- Substitutes a different model "that kind of works"
- Imputes values to force a fit

Compatibility failures are explicit errors, deterministically.

---

## 11. Input Validation

### 11.1 Validation Catalog

| Validation | Failure → Error Code |
|------------|----------------------|
| Missing `ticker` | `INVALID_REQUEST` |
| Invalid/malformed `timestamp` (not ISO UTC) | `INVALID_REQUEST` |
| `timestamp` in the future (beyond tolerance) | `INVALID_REQUEST` |
| Unsupported `interval` (only `1d`) | `INVALID_REQUEST` |
| Missing required features | `FEATURE_VALIDATION_FAILED` |
| Wrong feature types (non-numeric) | `FEATURE_VALIDATION_FAILED` |
| NaN / Inf in any feature value | `FEATURE_VALIDATION_FAILED` |
| Feature count ≠ expected schema | `FEATURE_VALIDATION_FAILED` |
| `feature_set_version` mismatch with model | `FEATURE_VERSION_INCOMPATIBLE` |
| Stale market data (`data_timestamp` older than `stale_data_max_age_seconds`, default 300 s) | `STALE_DATA` |
| Stale prediction-as-of time (`timestamp` older than prediction validity window) | `STALE_DATA` |
| `market_context.current_price` ≤ 0 or NaN/Inf | `FEATURE_VALIDATION_FAILED` |
| Unknown instrument | `INVALID_REQUEST` |

### 11.2 Determinism Requirement

**Every validation failure is deterministic** — same malformed input always produces the same error code and message. No random sampling, no heuristic guessing, no partial acceptance.

### 11.3 Validation Layers

```
Layer 1 — HTTP/schema (pydantic):    shape, types, required fields
Layer 2 — semantic (orchestrator):   ranges, timestamps, staleness
Layer 3 — feature-set (validator):   feature names, count, NaN/Inf
Layer 4 — compatibility (resolver):  feature/model/label version alignment
```

Failures at any layer short-circuit to the error model (Section 16).

---

## 12. Feature Sourcing

### 12.1 Two Candidate Approaches

| Criterion | A. Client supplies features | B. API computes features from market data |
|-----------|------------------------------|-------------------------------------------|
| **Consistency** | Features must come from the same versioned feature engine; the API enforces `feature_set_version` | Risk of divergence unless the API embeds the exact same engine + version |
| **Latency** | Fast — validation + inference only | Slower — market data fetch + 52-feature computation per request |
| **Reproducibility** | High — input is an explicit versioned vector | Medium — depends on data freshness and engine state at request time |
| **Security** | No arbitrary computation server-side | API must run the feature engine on request payloads |
| **Complexity** | Thin API, clear contract | API depends on data layer + feature engine; heavier |

### 12.2 Recommendation: Approach A — Client Supplies Features

**This matches SYSTEM_ARCHITECTURE.md §2.9**, where Prediction Service inputs are "Feature data (from request) + trained model (from registry)." It also matches FEATURE_ENGINEERING_BLUEPRINT.md's precompute-and-persist model: features are computed by the versioned FeatureEngine offline and stored/transmitted as vectors.

**Requirements to keep consistency:**
1. Features must be produced by the same feature engine version used in training (SHA-256 feature-version hash ties them together).
2. The API strictly validates `feature_set_version` against the model's `feature_version` — mismatch → 409.
3. Paper-simulation and research clients use the versioned feature pipeline (FEATURE_ENGINEERING_BLUEPRINT.md) to build request payloads — never ad-hoc formulas.

### 12.3 Market Context

The Decision Engine additionally needs `current_price` and `recent_volatility` (RISK blueprint §4.1). These are supplied in `market_context` (Section 7) — a small, explicit, validated block. The API does NOT reconstruct them from raw OHLCV.

---

## 13. Model Loading

### 13.1 MVP Loading Strategy

| Aspect | MVP Strategy |
|--------|--------------|
| **Initialization** | Load the default model at startup (eager). Fail startup loudly if it cannot load — the service is not ready |
| **Explicit versions** | Lazy load on first request for that version; cache in an in-memory dict (small, bounded — see below) |
| **Memory management** | Cache holds a configurable small number of models (default: 2 — default + one requested). LRU eviction beyond that |
| **Version-specific artifacts** | Load `model.joblib` + `scaler.joblib` (LR only) + metadata, exactly per BASELINE_MODEL_BLUEPRINT.md §8.2/§8.4 |
| **Hot-swapping** | NOT in MVP. Default model changes require restart |

### 13.2 Loading Sequence (per BASELINE_MODEL_BLUEPRINT.md §8.4)

```
1. Read registry (models/registry/registry.json) → resolve version
2. Load model.joblib from artifact_path
3. Load scaler.joblib if model_type requires it (logistic_regression)
4. Validate metadata: feature_version, label_version, feature_count, status
5. Serve
```

### 13.3 Failure Handling

| Failure | Behavior |
|---------|----------|
| Registry missing/corrupt at startup | Startup fails; `/health` reports not ready |
| Artifact file missing at load time | `MODEL_NOT_FOUND` (404) for that version; service stays up |
| Cache full | Evict LRU entry; load requested version |

---

## 14. Inference Performance

### 14.1 MVP Performance Goals

**PRD NFR-PF-01: single prediction request < 100 ms.** Targets below are configurable research/ops parameters — not marketing numbers.

### 14.2 Latency Budget (target: ≤ 60 ms typical)

| Stage | Budget |
|-------|--------|
| HTTP/schema validation | ≤ 5 ms |
| Feature-set validation | ≤ 5 ms |
| Model resolution | ≤ 2 ms |
| Inference (52 features, LR/RF) | ≤ 20 ms |
| Decision Engine (shared logic) | ≤ 10 ms |
| Serialization | ≤ 5 ms |
| Framework/overhead | ≤ 10 ms |
| **Total (target)** | **≤ 60 ms** (headroom under 100 ms) |

### 14.3 Other Goals

| Metric | MVP Target | Notes |
|--------|-----------|-------|
| Throughput | ≥ 10 req/s sustained | Local single-process; far beyond research needs |
| Model loading (startup) | ≤ 5 s for default model | joblib load of LR/RF at 52 features is well under this |
| Model loading (cold, explicit version) | ≤ 2 s | One-time cost; cached thereafter |
| Inference (hot) | ≤ 20 ms | No HFT requirements; daily frequency |

All targets are configurable in the `api` config section. Do NOT optimize further in MVP.

---

## 15. Batch Prediction

### 15.1 Decision: Deferred (not in MVP)

| Consideration | Assessment |
|---------------|------------|
| Use case | Backtesting already runs offline batch paths through the shared decision engine — not the HTTP API |
| Scale | Daily frequency, single-instrument requests — no throughput pressure (NFR-SC-01..03) |
| PRD | No batch endpoint requirement in PRD_MVP.md |
| Complexity | Partial-failure semantics, ordering guarantees, and response mapping add real complexity |

### 15.2 Deferral Conditions

`POST /predict/batch` is explicitly reserved for the future (Section 30). When added, it must specify: maximum batch size, ordering guarantee, per-item error handling, partial-failure semantics, and 1:1 response mapping with `request_id`s.

---

## 16. Error Model

### 16.1 Error Response Shape

Every error response has the same machine-readable shape:

```json
{
  "error": {
    "code": "FEATURE_VERSION_INCOMPATIBLE",
    "message": "Requested feature_set_version does not match model v1.0.0-20260904",
    "request_id": "req_20260904_100000_001",
    "timestamp": "2026-09-04T10:00:00.123Z"
  }
}
```

| Field | Description |
|-------|-------------|
| `code` | Machine-readable error code (below) |
| `message` | Human-readable, no internal stack traces or secrets |
| `request_id` | Correlation ID (client or server generated) |
| `timestamp` | Error timestamp (UTC) |

### 16.2 Error Codes

| Code | HTTP | Meaning |
|------|------|---------|
| `INVALID_REQUEST` | 400/422 | Malformed request, missing ticker, bad timestamp/interval, unknown instrument |
| `FEATURE_VALIDATION_FAILED` | 422 | Missing/wrong-typed/NaN/Inf features, count mismatch, bad market_context |
| `MODEL_NOT_FOUND` | 404 | Requested model version not in registry |
| `MODEL_VERSION_INCOMPATIBLE` | 409 | Model status not usable / label version mismatch |
| `FEATURE_VERSION_INCOMPATIBLE` | 409 | feature_set_version ≠ model.feature_version |
| `STALE_DATA` | 422 | Market data or prediction-as-of timestamp too old |
| `PREDICTION_FAILED` | 500 | Model runtime error during inference |
| `DECISION_ENGINE_FAILED` | 500 | Shared decision logic raised (should not happen; fail closed) |
| `RATE_LIMITED` | 429 | Rate limit exceeded (optional middleware) |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

### 16.3 Rules

- Do not expose sensitive internal details (artifact paths, registry contents, tracebacks).
- Every failure is deterministic for a given input.
- A prediction is never fabricated to avoid an error (Section 28).

---

## 17. Health Checks

### 17.1 Liveness vs Readiness

| Check | Question | Method |
|-------|----------|--------|
| **Liveness** | Is the service process running? | Process responds to `/health`; framework alive |
| **Readiness** | Is the required model available and usable? | Default model loaded in memory, registry readable, config valid |

**Health checks never perform expensive inference** (no model calls, no feature computation).

### 17.2 `/health` Semantics

```json
{
  "status": "ok",
  "model_loaded": true,
  "model_version": "v1.0.0-20260904",
  "uptime_seconds": 3600.0,
  "mode": "research"
}
```

| Field | Value |
|-------|-------|
| `status` | `ok` when ready; `degraded` when the process is up but readiness fails |
| `model_loaded` | Whether the default model is loaded |
| `model_version` | Loaded default model version (null if none) |
| `mode` | Active research mode (Section 24) |

HTTP 200 only when ready; 503 when degraded. Liveness is implied by the endpoint responding at all.

---

## 18. Observability

### 18.1 Structured Logging (structlog, JSON)

Per PRD NFR-LO-01..05 and SYSTEM_ARCHITECTURE logging architecture. Every request produces structured logs; no `print()`.

### 18.2 Required Log Fields

| Field | Description |
|-------|-------------|
| `request_id` | Correlation ID for the whole request |
| `prediction_id` | Audit identifier (Section 19) |
| `timestamp` | Log time (UTC) |
| `ticker` | Instrument |
| `model_version` | Resolved model |
| `feature_version` | Feature set version |
| `strategy_version` | Decision strategy version |
| `latency_ms` | Request latency |
| `status` | success / no_trade / error |
| `error_code` | Error code when applicable |
| `signal` | Decision signal (BUY/SELL/HOLD/NO_TRADE) |
| `mode` | research / paper |

### 18.3 Rules

| Rule | Description |
|------|-------------|
| **Never log secrets** | No credentials, tokens, or keys — ever |
| **No raw feature dumps** | Log feature names/counts, not values (privacy + noise) |
| **Correlation** | `request_id` propagated through every log line |
| **Levels** | DEBUG (dev), INFO (requests), WARNING (data issues), ERROR (failures) — per NFR-LO-03 |

---

## 19. Inference Audit Trail

### 19.1 Immutable Prediction Record

Every prediction is traceable. The audit record is written once, append-only, and never mutated:

```
prediction_id        # unique, immutable
request_id           # correlation
ticker               # instrument
input_timestamp      # prediction-as-of time
data_timestamp       # market data time
model_version        # resolved model
feature_version      # feature set
label_version        # label target version
strategy_version     # decision strategy
prediction           # predicted class
probabilities        # full distribution
confidence           # max probability
signal               # decision signal
risk_score           # normalized risk
reason_codes         # decision explanation
inference_timestamp  # when served
```

### 19.2 Storage (MVP, file-based per ADR-0005)

```
predictions/audit/
├── 2026/
│   └── 09/
│       └── 04/
│           └── predictions_2026-09-04.jsonl   # append-only, one JSON line per prediction
├── schema/
│   └── prediction_schema.json                 # schema definition
```

### 19.3 Prediction vs Actual Comparison (no online learning)

The audit trail supports later comparison of:

```
Prediction (stored probabilities/signal)
   vs
Actual Outcome (label engine over forward window — LABEL_GENERATION_BLUEPRINT.md)
```

This is a **reporting/offline analysis** capability only. The MVP does NOT implement online learning, feedback loops, or automatic retraining from API traffic.

---

## 20. Idempotency

### 20.1 Determinism First

Identical requests (same `model_version`, `features`, `market_context`, `timestamp`) **must produce the same prediction and decision**. This is guaranteed by:

| Requirement | Mechanism |
|-------------|-----------|
| Deterministic model inference | No RNG at inference time; fixed seeds at training time (BASELINE_MODEL_BLUEPRINT §9) |
| Model version locking | Resolution never changes mid-request or across replays (Section 9) |
| Deterministic decision logic | Shared Decision Engine is a pure function of its inputs (RISK blueprint §22.3) |
| Deterministic validation | Same input → same validation result (Section 11.2) |

### 20.2 Request Replay

| Aspect | MVP Policy |
|--------|-----------|
| Replay behavior | Replaying the same logical request returns the same result |
| `request_id` reuse | If a client resends the same `request_id`, the API may return the cached prior response (simple in-memory TTL cache keyed by `request_id`) |
| Audit writes | Replayed responses do not append duplicate audit records |
| Idempotency key | `request_id` serves this role in MVP — no separate header required |

Replay caching is a convenience, not a correctness requirement: the system is deterministic even without it.

---

## 21. Security

### 21.1 MVP Security Baseline (proportionate)

| Control | MVP Policy | Source |
|---------|-----------|--------|
| **Authentication** | None — localhost only (FR-API-07, NFR-SE-04) | PRD |
| **Authorization** | Not applicable (single-user local research) | PRD |
| **Rate limiting** | Optional simple in-process limiter (config: `rate_limit_per_minute`); default off or generous | New |
| **Request-size limits** | Max payload size enforced (config: `max_request_size_kb`, default 256 KB) | New |
| **Input validation** | Full contract validation on every endpoint (Section 11) | PRD FR-API-05 |
| **Secret management** | Secrets only via environment variables (NFR-CF-03); `.env` gitignored; nothing in source or YAML | PRD |
| **CORS** | Disabled by default; if needed, localhost origins only | New |
| **Payload safety** | No `eval()`/`exec()` on any input (NFR-SE-05) | PRD |

### 21.2 Explicit Non-Goals

- No enterprise IAM, no OAuth, no TLS termination (local only), no API keys in MVP.
- If the API is ever exposed beyond localhost, authentication and TLS become mandatory preconditions — that is a future task, not an MVP extension.

---

## 22. Configuration

### 22.1 API Configuration Section

All configuration lives in YAML (NFR-CF-01). The MVP `api` section:

```yaml
# config/default.yaml — api section (to be added during implementation)

api:
  host: 127.0.0.1          # local only (NFR-SE-04)
  port: 8000
  mode: research           # research | paper  (live is REJECTED at startup)
  default_model: ""        # empty → registry active_model (Section 9)
  inference_timeout_ms: 1000
  max_request_size_kb: 256
  rate_limit_per_minute: 0   # 0 = disabled
  log_level: INFO
  audit_dir: predictions/audit
  model_cache_size: 2        # in-memory model cache (Section 13)
  stale_data_max_age_seconds: 300
```

### 22.2 Configuration Rules

| Rule | Description |
|------|-------------|
| No secrets in source code | Environment variables only (NFR-CF-03) |
| Schema validation at startup | Config validated before serving; invalid config → startup failure (NFR-CF-04) |
| Defaults documented | Every value commented in the YAML |
| Environment overrides | `config/{env}.yaml` (NFR-CF-02) |

> **Note:** `config/default.yaml` currently has no `api:` section. Adding it (per the block above) is a pre-implementation task, mirroring how the `model:` section was added per BASELINE_MODEL_BLUEPRINT.md.

---

## 23. Backtest Compatibility

### 23.1 Mandatory: One Decision Code Path

> **The Decision Engine used by inference MUST be the same logical decision system specified for backtesting.**
> Backtest Logic ≠ API Logic is forbidden.

From RISK_DECISION_ENGINE_BLUEPRINT.md §23: the Decision Engine is a shared module used by both the research/API flow and the Backtest Engine. This blueprint inherits that requirement:

```
Research/API flow:    request features → model inference → DecisionEngine → response
Backtest flow:        historical features → model inference (offline) → DecisionEngine → trade ledger

Both call the SAME DecisionEngine module with the SAME configuration.
```

### 23.2 Enforcement Mechanisms

| Mechanism | Description |
|-----------|-------------|
| Single module | Decision logic exists in one place (`src/decision/` or equivalent), imported by both API and backtester |
| Config-driven | Both flows read thresholds/filters from the same YAML (`decision` config section per RISK blueprint §4.2) |
| Versioned | A `strategy_version` change is required to alter any decision parameter (RISK blueprint §25) |
| Regression tests | Same inputs → identical decision outputs in API path and backtest path (Section 27) |

### 23.3 What Differs (allowed)

Only the *surroundings* differ — execution simulation (backtester) vs. response serialization (API). The decision itself is identical.

---

## 24. Research / Live Mode Separation

### 24.1 Modes

| Mode | Meaning | MVP Support |
|------|---------|-------------|
| **RESEARCH** | Signals for research; default mode | ✅ Default |
| **PAPER / SIMULATION** | Signals + paper-simulation ledger | ✅ Optional (config) |
| **LIVE** | Real execution | ❌ **Disabled — not implemented** |

### 24.2 Preventing Accidental Live Operation

| Guard | Description |
|-------|-------------|
| No live code paths | No broker SDK, no order endpoint, no execution module exists in MVP (PRD §10) |
| Mode validation at startup | `mode: live` in config → **startup failure** with explicit error; the API refuses to boot in live mode |
| Mode in responses | `/version` and `/health` report the active mode so consumers can verify |
| Research labeling | Decision outputs labeled research-only (RISK blueprint §24.3) |

The inference service can only ever produce research signals in MVP. This is enforced structurally (no execution code), not just by convention.

---

## 25. Response Explanation

### 25.1 Structured Reason Codes

For MVP, responses return machine-readable reason codes from the shared Decision Engine (RISK blueprint §21 — 22 codes, e.g. `MODEL_CONFIDENCE_LOW`, `EXPECTED_EDGE_TOO_LOW`, `STALE_PREDICTION`, `HIGH_VOLATILITY`).

```json
{
  "decision_output": {
    "signal": "NO_TRADE",
    "reason_codes": ["CONFIDENCE_BELOW_THRESHOLD", "EDGE_BELOW_COST"]
  }
}
```

### 25.2 No Natural-Language Explanations

The MVP does NOT implement LLM-generated or templated natural-language explanations. Reason codes are sufficient for research/debugging (RISK blueprint §21) and are deterministic and versioned.

---

## 26. Contract Versioning

### 26.1 Version Identifiers

| Identifier | Scheme | Source |
|------------|--------|--------|
| `API_VERSION` | `v1` — version of the HTTP contract | This blueprint |
| `MODEL_VERSION` | `v{major}.{minor}.{patch}-{date}` | BASELINE_MODEL_BLUEPRINT.md §7 |
| `FEATURE_VERSION` | SHA-256 content hash of feature definitions | FEATURE_ENGINEERING_BLUEPRINT.md |
| `LABEL_VERSION` | Versioned target definition | LABEL_GENERATION_BLUEPRINT.md |
| `STRATEGY_VERSION` | `stg_vX.Y` — decision strategy version | RISK_DECISION_ENGINE_BLUEPRINT.md §25 |

### 26.2 API Path Versioning

**MVP decision: keep root paths** (`/predict`, `/health`, `/model/info`, `/version`) exactly as SYSTEM_ARCHITECTURE.md §5.2 defines — **no `/api/v1/` prefix in MVP**.

**Why deferred:**
- SYSTEM_ARCHITECTURE.md §5.2 already commits to the unprefixed paths; adding a prefix would contradict it
- MVP has a single internal consumer set (research + paper tooling, dashboard)
- Breaking changes are detectable via the `API_VERSION` field in `/version`

**Policy for the future:** any breaking change to the request/response contract MUST introduce a versioned path (`/api/v2/...`) while preserving `/api/v1/...` semantics for existing consumers. Non-breaking additions may extend the v1 contract.

### 26.3 Change Rules

| Change Type | Requires |
|-------------|----------|
| New optional response field | No version bump (additive) |
| Changed field semantics / removed field | New API version + path |
| New model | New MODEL_VERSION (registry) |
| New feature definitions | New FEATURE_VERSION (hash change) |
| Changed decision thresholds/rules | New STRATEGY_VERSION (RISK blueprint §25.1) |

---

## 27. Testing Strategy

> Design only — no tests implemented in this task. Aligns with NFR-TE-01..06 and SYSTEM_ARCHITECTURE §9.

### 27.1 Unit Tests

| Target | Coverage |
|--------|----------|
| Validation | Contract validation rules (Section 11) — each rule + failure mode |
| Serialization | Request/response schema round-trips, error serialization |
| Model resolver | Explicit version, default resolution, unknown version, compatibility checks |
| Decision integration | Decision Engine invoked correctly; NO_TRADE propagation |

### 27.2 Integration Tests

| Scenario | Expectation |
|----------|-------------|
| Request → prediction → decision | Full happy path returns model_output + decision_output |
| Incompatible model/feature version | 409 with correct error code |
| Missing/invalid features | 422 `FEATURE_VALIDATION_FAILED` |
| Stale data timestamp | 422 `STALE_DATA` |
| Unknown model version | 404 `MODEL_NOT_FOUND` |

### 27.3 Contract Tests

- Verify request/response schemas against the OpenAPI spec (auto-generated — Section 29).
- Verify every error response matches the shape in Section 16.1.
- Verify `/version` reports correct identifiers.

### 27.4 Regression Tests

- **Known inputs → expected outputs for a fixed model version** using frozen artifacts (a pinned model + golden feature vectors).
- Critical for the "Backtest Logic = API Logic" guarantee: the same inputs must produce identical decisions through the API path and the backtest path (Section 23.2).

---

## 28. Failure & Degradation

### 28.1 Failure Scenarios

| Scenario | Behavior |
|----------|----------|
| Model unavailable (artifact missing/corrupt) | `MODEL_NOT_FOUND` (404) for that version; other versions still serve; `/health` degraded if it was the default |
| Feature service unavailable | Not applicable in MVP — features arrive in the request (Section 12) |
| Database unavailable | Not applicable — file-based storage (ADR-0005); if the registry file is unreadable → readiness fails, `/predict` returns 503 |
| Stale data | `STALE_DATA` (422) — no inference on stale inputs |
| Invalid model (status/version) | `MODEL_VERSION_INCOMPATIBLE` (409) |
| Inference timeout | `INTERNAL_ERROR`-family timeout handling; 504 after `inference_timeout_ms` |
| Decision Engine exception | `DECISION_ENGINE_FAILED` (500) — fail closed |

### 28.2 Fail-Closed Principle

> **The service fails closed. For prediction failures, it does NOT fabricate a prediction.**

A prediction is only served when every stage (validation → resolution → inference → validation → decision) completes successfully. Partial or uncertain states produce structured errors, never partial predictions labeled as complete (PRD NFR-RL-03).

### 28.3 Degraded Availability

`/health`, `/model/info`, and `/version` remain available when `/predict` is failing for model-specific reasons — observability must not go dark during a failure.

---

## 29. API Documentation

### 29.1 Recommendation: OpenAPI-Compatible Schema

FastAPI auto-generates an OpenAPI schema from the pydantic models. This is the single source of truth for the HTTP contract.

### 29.2 Rules

| Rule | Description |
|------|-------------|
| No duplicate definitions | Do NOT hand-maintain a second API spec; generate from code |
| Schema verified by tests | Contract tests validate the generated schema (Section 27.3) |
| Accessible locally | Swagger UI / ReDoc served by FastAPI for local research use |
| Versioned | API changes reflect in the generated schema automatically |

---

## 30. Future Extensions

Reserved architecture — NOT implemented in MVP:

| Extension | Reserved For | MVP State |
|-----------|--------------|-----------|
| Streaming inference | Real-time use cases | Not implemented |
| WebSocket predictions | Push updates | Not implemented |
| Multi-model ensemble | Aggregated predictions | Single model only (RISK blueprint §17) |
| Model routing | Model selection per request/regime | Deterministic resolution only (Section 9) |
| GPU inference | Large models | CPU LR/RF only |
| Batch inference workers | Bulk predictions | Deferred (Section 15) |
| Feature store | Versioned feature serving | Client-supplied features (Section 12) |
| Online drift detection | Model decay monitoring | Audit-based offline comparison only (Section 19) |
| Agent integration | LLM/agent consumers | Out of scope (PRD §10) |

None of these are implemented. The API architecture (thin orchestrator, shared decision engine, versioned contracts) accommodates them without rewrite.

---

## 31. Acceptance Criteria

The blueprint is complete when:

| Criterion | Status |
|-----------|--------|
| Service responsibilities defined (does / must not) | ✅ |
| Endpoint contract defined (4 endpoints with schemas/status codes) | ✅ |
| Request schema exists (features + market context, no raw history) | ✅ |
| Response schema exists (model_output vs decision_output) | ✅ |
| Model-resolution strategy exists (explicit > default, locked) | ✅ |
| Compatibility checks exist (model/feature/label/schema/age) | ✅ |
| Validation rules exist (12 checks, deterministic) | ✅ |
| Error model exists (10 codes, uniform shape) | ✅ |
| Health checks exist (liveness vs readiness, no inference) | ✅ |
| Observability exists (structlog fields, no secrets) | ✅ |
| Audit trail exists (immutable JSONL prediction records) | ✅ |
| Versioning exists (5 identifiers; API_VERSION policy) | ✅ |
| Research/live separation defined (research + paper; live disabled) | ✅ |
| Backtest consistency defined (one shared decision code path) | ✅ |
| Testing strategy exists (unit/integration/contract/regression) | ✅ |
| Future extensions reserved (9 areas) | ✅ |

---

## 32. Consistency Check

### 32.1 Cross-Reference with Previous Documents

| Document | Check | Status | Notes |
|----------|-------|--------|-------|
| **PRD_MVP.md** | FR-API-01..08 (REST, /predict, /health, /model/info, validation, version in response, no auth, FastAPI/Flask) | ✅ Consistent | FastAPI locked; all endpoints/semantics preserved |
| **PRD_MVP.md** | NFR-PF-01 (<100 ms) | ✅ Consistent | Budget targets ≤ 60 ms with headroom |
| **PRD_MVP.md** | NFR-SE-04 (local only), NFR-CF (YAML), NFR-LO (structlog) | ✅ Consistent | Enforced in Sections 21/22/18 |
| **SYSTEM_ARCHITECTURE.md** | §2.9 Prediction Service (FastAPI + pydantic + structlog; endpoints) | ✅ Consistent | This blueprint elaborates, does not contradict |
| **SYSTEM_ARCHITECTURE.md** | §5.2 request/response examples (ticker + features) | ✅ Consistent | Extended additively with decision_output + market_context |
| **SYSTEM_ARCHITECTURE.md** | §4.1 layout (`src/api/`, `src/model/registry.py`) | ✅ Consistent | Module map matches |
| **DATA_ARCHITECTURE.md** | File-based storage; model_predictions table (future DB) | ✅ Consistent | MVP audit trail is JSONL (ADR-0005); DB table is Phase 2 |
| **DATA_INGESTION_BLUEPRINT.md** | Data sources/timestamps | ✅ Consistent | API consumes pre-computed features; no data-layer coupling |
| **DATA_CLEANING_VALIDATION.md** | Data quality gates | ✅ Consistent | API feature validation complements (not replaces) pipeline gates |
| **FEATURE_ENGINEERING_BLUEPRINT.md** | Feature versioning (SHA-256); 52 features; precompute-and-persist | ✅ Consistent | Feature sourcing Approach A (Section 12) |
| **LABEL_GENERATION_BLUEPRINT.md** | Classification target; 5-day horizon; label versioning | ✅ Consistent | Label version flows into responses/audit |
| **DATASET_BUILDER_BLUEPRINT.md** | Dataset/feature versioning | ✅ Consistent | API validates feature_set_version |
| **BASELINE_MODEL_BLUEPRINT.md** | §7 version scheme; §8.2 artifact structure; §8.3 registry; §8.4 loading | ✅ Consistent | Resolver/loading follow exactly |
| **TRAINING_PIPELINE_BLUEPRINT.md** | Model status lifecycle; selection gate (candidate, not deployment) | ✅ Consistent | API serves registered models only |
| **EVALUATION_BACKTESTING_BLUEPRINT.md** | Shared decision logic; no backtest≠API divergence | ✅ Consistent | Section 23 enforces single code path |
| **RISK_DECISION_ENGINE_BLUEPRINT.md** | §4 input contract; §23 shared decision module; §21 reason codes; §25 strategy versioning | ✅ Consistent | Decision outputs and reason codes reused verbatim |
| **RISK_DECISION_ENGINE_BLUEPRINT.md** | §24 research safety; §27 no-trade policy | ✅ Consistent | NO_TRADE is a 200 response; research labeling |

### 32.2 Reconciliations (additive, non-contradictory)

| Topic | Previous Doc | This Blueprint | Resolution |
|-------|-------------|----------------|------------|
| `/predict` response | SYSTEM_ARCHITECTURE §5.2: model output only | Adds `decision_output` block | Additive per ADR-0020 (Prediction/Decision separation) — model output unchanged |
| Request naming | SYSTEM_ARCHITECTURE uses `ticker`; RISK blueprint uses `instrument` | HTTP contract uses `ticker`; internal Decision Engine call maps to `instrument` | Documented mapping; no conflict at either boundary |
| Path versioning | SYSTEM_ARCHITECTURE §5.2: unprefixed paths | No `/api/v1/` prefix in MVP; policy for future | Consistent with prior architecture; deferred by design |
| `model_predictions` table | DATA_ARCHITECTURE (Phase 2) | JSONL audit trail in MVP | Consistent — DB is the future home of the same records |
| `CURRENT_STATE.md` | Referenced `INFERENCE_API_BLUEPRINT.md` before creation | Created by this task | Resolved |

### 32.3 Conflicts Found

**None.** No previous architectural decision is overridden. Two genuine additions are introduced:
1. **Inference API blueprint as a whole** (endpoint contract, request/response contracts, audit trail, mode separation) — recorded as ADR-0021.
2. **Contract versioning policy** (API_VERSION field; no path prefix in MVP; versioned paths reserved for breaking changes) — folded into ADR-0021.

---

## 33. Deliverables

| Deliverable | Status | Description |
|-------------|--------|-------------|
| `docs/INFERENCE_API_BLUEPRINT.md` | ✅ This document | Complete prediction & inference API architecture and contracts |
| `docs/CURRENT_STATE.md` | ⏳ To update | Add blueprint to documentation list; record ADR-0021 |
| `docs/DECISIONS.md` | ⏳ To update | Add ADR-0021 (Prediction & Inference API Blueprint) |

Do not modify unrelated files.

---

## 34. Stop Condition

**This document is architecture and API contract design only.**

**DO NOT:**
- Write FastAPI/Flask code
- Train models
- Connect brokers
- Build the frontend
- Implement live trading
- Deploy services
- Introduce Kubernetes
- Introduce microservices unnecessarily

**STOP after the inference API architecture and contracts are documented.**

---

## Final Report

### A. Recommended API Technology

**FastAPI** — already committed in SYSTEM_ARCHITECTURE.md §2.9 (deps: FastAPI, pydantic, structlog). Declarative pydantic validation, automatic OpenAPI docs, async, thin. Flask is workable but inferior for contracts; gRPC is overkill for a local daily-frequency research service.

### B. Endpoint List

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/predict` | Prediction + research decision |
| GET | `/health` | Liveness + readiness |
| GET | `/model/info` | Model metadata |
| GET | `/version` | Contract version introspection |

Batch prediction deferred.

### C. Request/Response Contract

**Request:** `ticker`, `timestamp`, `interval` (`1d`), `feature_set_version`, optional `model_version`, pre-computed `features` (52-vector), minimal `market_context` (current_price, recent_volatility, data_timestamp). No raw history transmitted.

**Response:** `model_output` (prediction, probabilities, confidence) **separated from** `decision_output` (signal, risk_score, position_size, reason_codes, strategy_version), plus version identifiers, `prediction_id`/`request_id`, latency. NO_TRADE is a 200.

### D. Model Resolution Strategy

Deterministic: explicit `model_version` wins; otherwise configured default (`api.default_model` → registry `active_model`). Version locked per request, echoed in response, never switched silently. Default changes require config + restart. Ongoing evaluations must pin a version.

### E. Feature Sourcing Recommendation

**Approach A — client supplies features.** Matches SYSTEM_ARCHITECTURE §2.9 and the precompute-and-persist feature model. Consistency enforced via `feature_set_version` matching `model.feature_version` (mismatch → 409). The API is a thin, validated orchestrator.

### F. Error Handling Strategy

Uniform machine-readable error object (`code`, `message`, `request_id`, `timestamp`) with 10 codes (INVALID_REQUEST, FEATURE_VALIDATION_FAILED, MODEL_NOT_FOUND, MODEL_VERSION_INCOMPATIBLE, FEATURE_VERSION_INCOMPATIBLE, STALE_DATA, PREDICTION_FAILED, DECISION_ENGINE_FAILED, RATE_LIMITED, INTERNAL_ERROR). Deterministic failures; fail closed; never fabricate predictions.

### G. Observability Strategy

structlog JSON per request: request_id, prediction_id, ticker, model/feature/strategy versions, latency_ms, status, error_code, signal. No secrets, no raw feature values. Audit trail as append-only JSONL under `predictions/audit/`.

### H. Versioning Strategy

Five identifiers: API_VERSION (`v1`), MODEL_VERSION (`v{major}.{minor}.{patch}-{date}`), FEATURE_VERSION (SHA-256 hash), LABEL_VERSION (target version), STRATEGY_VERSION (`stg_vX.Y`). MVP keeps root paths (no `/api/v1/` prefix) per SYSTEM_ARCHITECTURE §5.2; breaking changes must introduce versioned paths in the future.

### I. Research/Live Separation

Modes: RESEARCH (default) and PAPER/SIMULATION (optional). LIVE is structurally impossible in MVP — no execution code exists, `mode: live` fails at startup, `/version` and `/health` report the active mode, and decision outputs carry research-only labeling.

### J. Contradictions with Previous Documents

**None.** All 12 cross-referenced documents are consistent. Two additive changes: (1) `/predict` response extended with `decision_output` per ADR-0020; (2) contract versioning policy (API_VERSION field, deferred path prefix). `CURRENT_STATE.md` previously referenced this blueprint before it existed — now resolved. RISK_DECISION_ENGINE_BLUEPRINT.md was verified complete and consistent (32 sections + Final Report A–J, ADR-0019/0020 recorded); no changes required to it.

### K. Exact Next Recommended Task

1. **Update `CURRENT_STATE.md`** — add INFERENCE_API_BLUEPRINT.md (18 docs) and ADR-0021 (21 ADRs)
2. **Add ADR-0021 to `DECISIONS.md`** — record the Prediction & Inference API architecture decision
3. **Pre-implementation:** add the `api:` section to `config/default.yaml` per Section 22 (host, port, mode, default_model, timeouts, limits)
4. **Then:** begin Phase 2 implementation with the Data Layer (`src/data/`), per CURRENT_STATE.md — the API layer is implemented last, after data → features → labels → dataset → model → backtest layers exist, because the API depends on the registry, the shared Decision Engine, and the versioned feature pipeline.