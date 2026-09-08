import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'

export interface FetchState<T> {
  data: T | null
  loading: boolean
  error: string | null
  errorCode: string | null
  requestId: string | null
  reload: () => void
}

/**
 * Predictable fetch behavior (milestone §32): one request per mount/dep
 * change, no polling loops, captured error envelope fields for the
 * ErrorState component.
 */
export function useFetch<T>(fetchFn: () => Promise<T>, deps: unknown[] = []): FetchState<T> {
  const [state, setState] = useState<Omit<FetchState<T>, 'reload'>>({
    data: null,
    loading: true,
    error: null,
    errorCode: null,
    requestId: null,
  })
  const [tick, setTick] = useState(0)
  const fetchRef = useRef(fetchFn)
  fetchRef.current = fetchFn

  useEffect(() => {
    let cancelled = false
    setState((prev) => ({ ...prev, loading: true, error: null, errorCode: null }))
    fetchRef
      .current()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null, errorCode: null, requestId: null })
      })
      .catch((error: unknown) => {
        if (cancelled) return
        if (error instanceof ApiError) {
          setState({
            data: null,
            loading: false,
            error: error.message,
            errorCode: error.code,
            requestId: error.requestId,
          })
        } else {
          setState({
            data: null,
            loading: false,
            error: 'Unexpected client error',
            errorCode: 'CLIENT_ERROR',
            requestId: null,
          })
        }
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { ...state, reload }
}
