/**
 * Centralized API client (milestone §29). All backend access goes through
 * this module — components never fetch directly. Converts the backend's
 * standardized error envelope (INFERENCE_API_BLUEPRINT §16.1) into a typed
 * ApiError and threads a request id through every call.
 */
import type {
  ApiErrorBody,
  BacktestDetail,
  BacktestSummary,
  CandlesResponse,
  DatasetDetail,
  DatasetSummary,
  ExperimentDetail,
  ExperimentSummary,
  HealthResponse,
  ModelInfoResponse,
  ModelSummary,
  PredictionAuditRecord,
  PredictionRequest,
  PredictionResponse,
  ReadyResponse,
  SystemStatus,
  VersionResponse,
} from './types'

/** Base URL: same-origin `/api` in dev (Vite proxy) or VITE_API_BASE override. */
const BASE_URL = import.meta.env.VITE_API_BASE ?? '/api'

export class ApiError extends Error {
  readonly code: string
  readonly requestId: string | null
  readonly status: number

  constructor(status: number, code: string, message: string, requestId: string | null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
  }
}

function newRequestId(): string {
  return `req_ui_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const requestId = newRequestId()
  const headers = new Headers(init?.headers)
  headers.set('X-Request-Id', requestId)
  if (init?.body) headers.set('Content-Type', 'application/json')

  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, { ...init, headers })
  } catch {
    // Network-level failure (backend down) — no details leaked, actionable message.
    throw new ApiError(0, 'SERVICE_UNREACHABLE', 'Cannot reach the Finance AI API. Is the backend running?', requestId)
  }

  if (!response.ok) {
    let code = 'INTERNAL_ERROR'
    let message = `Request failed with status ${response.status}`
    let remoteRequestId: string | null = null
    try {
      const body = (await response.json()) as ApiErrorBody
      if (body?.error) {
        code = body.error.code
        message = body.error.message
        remoteRequestId = body.error.request_id
      }
    } catch {
      // Non-JSON error body: keep the generic message.
    }
    throw new ApiError(response.status, code, message, remoteRequestId ?? requestId)
  }
  return (await response.json()) as T
}

export const api = {
  // Prediction + contract endpoints (M09)
  predict(body: PredictionRequest): Promise<PredictionResponse> {
    return request<PredictionResponse>('/predict', { method: 'POST', body: JSON.stringify(body) })
  },
  health(): Promise<HealthResponse> {
    return request<HealthResponse>('/health')
  },
  ready(): Promise<ReadyResponse> {
    return request<ReadyResponse>('/ready')
  },
  modelInfo(modelVersion?: string): Promise<ModelInfoResponse> {
    const query = modelVersion ? `?model_version=${encodeURIComponent(modelVersion)}` : ''
    return request<ModelInfoResponse>(`/model/info${query}`)
  },
  version(): Promise<VersionResponse> {
    return request<VersionResponse>('/version')
  },

  // Read-only dashboard endpoints (UI_UX_BLUEPRINT §29.3)
  datasets(): Promise<DatasetSummary[]> {
    return request<DatasetSummary[]>('/datasets')
  },
  dataset(version: string): Promise<DatasetDetail> {
    return request<DatasetDetail>(`/datasets/${encodeURIComponent(version)}`)
  },
  models(): Promise<ModelSummary[]> {
    return request<ModelSummary[]>('/models')
  },
  experiments(): Promise<ExperimentSummary[]> {
    return request<ExperimentSummary[]>('/experiments')
  },
  experiment(id: string): Promise<ExperimentDetail> {
    return request<ExperimentDetail>(`/experiments/${encodeURIComponent(id)}`)
  },
  backtests(): Promise<BacktestSummary[]> {
    return request<BacktestSummary[]>('/backtests')
  },
  backtest(id: string): Promise<BacktestDetail> {
    return request<BacktestDetail>(`/backtests/${encodeURIComponent(id)}`)
  },
  candles(ticker: string, limit = 500): Promise<CandlesResponse> {
    return request<CandlesResponse>(`/candles/${encodeURIComponent(ticker)}?limit=${limit}`)
  },
  predictions(ticker?: string, limit = 50): Promise<PredictionAuditRecord[]> {
    const params = new URLSearchParams({ limit: String(limit) })
    if (ticker) params.set('ticker', ticker)
    return request<PredictionAuditRecord[]>(`/predictions?${params.toString()}`)
  },
  systemStatus(): Promise<SystemStatus> {
    return request<SystemStatus>('/system/status')
  },
}
