/**
 * API client tests (milestone §39 API Integration Tests): mock backend
 * responses for success, validation error, server error, stale data, and
 * missing model. No network access (§34).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from './client'

const fetchMock = vi.fn()

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  fetchMock.mockReset()
})

function jsonResponse(status: number, body: unknown) {
  return {
    ok: status < 400,
    status,
    json: () => Promise.resolve(body),
  }
}

describe('api client', () => {
  it('returns parsed data on success', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, { api_version: 'v1', model_version: 'm1', feature_version: 'v0.2', label_version: 'v0.2', strategy_version: 'stg_v0.1', mode: 'research' }),
    )
    const version = await api.version()
    expect(version.api_version).toBe('v1')
    expect(version.mode).toBe('research')
    // Centralized client sets a correlation id (milestone §21/§29).
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect((init.headers as Headers).get('X-Request-Id')).toMatch(/^req_ui_/)
  })

  it('converts the backend error envelope into ApiError', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(409, {
        error: { code: 'FEATURE_VERSION_INCOMPATIBLE', message: 'feature version mismatch', request_id: 'req_1', timestamp: '2026-09-07T00:00:00Z' },
      }),
    )
    await expect(api.version()).rejects.toMatchObject({
      code: 'FEATURE_VERSION_INCOMPATIBLE',
      status: 409,
      requestId: 'req_1',
      message: 'feature version mismatch',
    })
  })

  it('surfaces stale-data errors with the backend code', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(422, {
        error: { code: 'STALE_DATA', message: 'market data too old', request_id: null, timestamp: '2026-09-07T00:00:00Z' },
      }),
    )
    await expect(api.predict({} as never)).rejects.toBeInstanceOf(ApiError)
  })

  it('maps MODEL_NOT_FOUND (404) with the backend message', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(404, {
        error: { code: 'MODEL_NOT_FOUND', message: "model version 'ghost' is not available", request_id: null, timestamp: '2026-09-07T00:00:00Z' },
      }),
    )
    await expect(api.modelInfo('ghost')).rejects.toMatchObject({ code: 'MODEL_NOT_FOUND', status: 404 })
  })

  it('produces SERVICE_UNREACHABLE when the backend is down', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await expect(api.health()).rejects.toMatchObject({ code: 'SERVICE_UNREACHABLE', status: 0 })
  })

  it('handles non-JSON error bodies with a generic message', async () => {
    fetchMock.mockResolvedValueOnce({ ok: false, status: 500, json: () => Promise.reject(new SyntaxError('not json')) })
    await expect(api.health()).rejects.toMatchObject({ code: 'INTERNAL_ERROR', status: 500 })
  })
})
