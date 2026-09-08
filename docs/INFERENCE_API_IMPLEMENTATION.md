# Inference API Implementation

Milestone 09 implements the approved research-only prediction service per
`docs/INFERENCE_API_BLUEPRINT.md` (ADR-0029). FastAPI serves the four
blueprint endpoints; the decision logic is the shared Milestone-08 module.

## Service architecture

```
HTTP request
  -> pydantic schema (layer 1)
  -> semantic validation: timestamps, interval, instrument, staleness (layer 2)
  -> feature-set validation: names, count, NaN/Inf (layer 3)
  -> model resolution + compatibility (layer 4, blueprint §9/§10)
  -> model inference (M07 artifact, scaler applied for LR)
  -> prediction validation (finite probabilities, known class)
  -> shared Decision Engine (src/backtest/signals.py + risk/reason wrapper)
  -> audit record (append-only JSONL)
  -> response
```

Fail-closed: any stage failure returns a structured error; a prediction is
never fabricated (blueprint §28.2).

## Endpoints (root paths per blueprint §26.2)

| Method | Path | Purpose | Success | Notable errors |
|--------|------|---------|---------|----------------|
| POST | `/predict` | One prediction + decision | 200 | 400 `INVALID_REQUEST`, 404 `MODEL_NOT_FOUND`, 409 `*_INCOMPATIBLE`, 422 `FEATURE_VALIDATION_FAILED`/`STALE_DATA`, 500 `PREDICTION_FAILED`, 503 `SERVICE_NOT_READY` |
| GET | `/health` | Liveness + readiness | 200 ok / 503 degraded | — |
| GET | `/ready` | Structured readiness checks | 200 / 503 with `checks` | — |
| GET | `/model/info` | Model metadata (`?model_version=` optional) | 200 | 404, 503 |
| GET | `/version` | Contract version identifiers | 200 | — |

The milestone prompt suggested `/api/v1/` paths; the blueprint explicitly
defers the prefix (§26.2, SYSTEM_ARCHITECTURE §5.2 commits to root paths),
so the blueprint is authoritative. `API_VERSION: v1` is reported by
`/version` and in every audit record.

## Request/response contract

Request (blueprint §7): `ticker`, `timestamp`, `interval` (`1d` only),
`feature_set_version`, optional `model_version`, `features` (exactly the
52 registered features), `market_context` (`current_price` required,
`recent_volatility` optional, `data_timestamp` required for the staleness
check). Extra fields are rejected (`extra="forbid"`).

Response (blueprint §8): `prediction_id`, `request_id`, `status`
(`success` | `no_trade`), `model_output` (prediction, probabilities,
confidence, `expected_return: null` — the classification model provides
no return estimate), `decision_output` (signal, risk_score, reason_codes,
strategy_version, position_size), `model` block, `features_used`,
`inference_time_ms`, and `audit_written` (false ⇒ served but NOT
persisted to the audit trail — milestone §27).

MODEL OUTPUT and DECISION OUTPUT are separate objects (ADR-0020).

## Model resolution and compatibility

Explicit `model_version` wins; otherwise `api.default_model`; otherwise
the newest artifact directory (deterministic, never random). Before
inference the resolver verifies: training status, feature-version match,
feature-name/count schema, and label-version match against the configured
`dataset.label_version`. Failures map to `MODEL_NOT_FOUND` (404),
`MODEL_VERSION_INCOMPATIBLE` (409), `FEATURE_VERSION_INCOMPATIBLE` (409),
or `FEATURE_VALIDATION_FAILED` (422). No hidden conversion is attempted.

Models load eagerly at startup (default) and lazily per requested version
into a bounded LRU cache (`api.model_cache_size`, default 2). Artifacts
are never mutated; there is no hot-swapping.

## Decision Engine integration

Signal generation calls `src.backtest.signals.generate_signals` — the
exact module the backtest engine uses — with the same YAML thresholds
(`backtest.signal.*`). The API adds only the normalized research risk
score (RISK blueprint §20: volatility 0.25 / uncertainty 0.25 / model
confidence 0.10 weights; liquidity, regime, and drawdown components are
unavailable to a stateless request and documented as limitations) and the
§21 reason codes. A regression test asserts API signal == backtest signal
for identical probabilities.

## Audit trail

Append-only JSONL at `predictions/audit/{YYYY}/{MM}/{DD}/predictions_{date}.jsonl`
with the blueprint §19.1 fields plus latency, `api_version`, and `mode`.
If the write fails, the prediction is still served but
`audit_written: false` and the failure is logged (`prediction_audit_failed`) —
never silently reported as audited.

## Configuration (`api:` section, blueprint §22)

`host` (127.0.0.1), `port` (8000), `mode` (`research`|`paper`; `live`
fails at startup), `default_model`, `inference_timeout_ms`,
`max_request_size_kb`, `rate_limit_per_minute`, `audit_dir`,
`model_cache_size`, `stale_data_max_age_seconds` (300).

## Commands

```bash
.venv/Scripts/python.exe -m scripts.run_api                  # start (config api.host/port)
ENVIRONMENT=development .venv/Scripts/python.exe -m scripts.run_api --port 8000
```

OpenAPI: `http://127.0.0.1:8000/docs` (auto-generated; no separate spec).

## Test strategy and results

43 tests in `tests/test_api_unit.py` + `tests/test_api_endpoints.py`
(fixtures in `tests/conftest.py` + `tests/api_helpers.py`), all offline:

- Unit: schema validation (extra fields, bad ticker, NaN price), resolver
  (explicit/default/unknown/empty), compatibility (feature/label
  mismatches), LRU cache, decision integration incl. the shared-logic
  regression test and risk-score monotonicity.
- Endpoints: happy path + contract, deterministic replay (regression),
  all blueprint error codes, staleness, audit record contents, audit
  failure ⇒ `audit_written: false`, degraded `/health`/`/ready` (503)
  with observability endpoints still up, OpenAPI contract, golden vector,
  and a structural test that no order/execution/broker route exists.

Full suite: **500 passing** (457 pre-M09 + 43).

## Local verification (executed 2026-09-07)

- Service started on 127.0.0.1 (research mode, real `random_forest_v0.2`).
- `/health` 200 ok, `/ready` all checks true, `/version` reports v1/v0.2.
- Controlled `/predict` with a real feature vector from dataset v0.2:
  200, `prediction: DOWN`, probabilities sum to 1, `signal: SELL`,
  `risk_score: 0.292`, reason codes present, `audit_written: true`.
- Audit record verified on disk with all §19.1 fields.
- Negative paths verified live: lowercase ticker → 400 `INVALID_REQUEST`;
  feature-version mismatch → 409; unknown model → 404; stale
  `data_timestamp` (7h old) → 422 `STALE_DATA`.
- Latency (50 sequential requests, client-measured): median 7.4 ms,
  p95 8.7 ms, max 11.8 ms — development measurements only, far under the
  100 ms PRD budget.

## Known limitations

- Root paths (no `/api/v1` prefix) — per blueprint §26.2; breaking changes
  will introduce versioned paths.
- No authentication — localhost-only research service (PRD FR-API-07).
- Risk score uses 3 of 6 blueprint components (stateless request).
- `expected_return` is always null (classification MVP).
- Replay caching (blueprint §20.2) is not implemented; determinism is.
- No rate limiting middleware (config knob reserved, default off).
- Live trading is structurally impossible: no broker SDK, no order
  endpoints, no execution module exists.
