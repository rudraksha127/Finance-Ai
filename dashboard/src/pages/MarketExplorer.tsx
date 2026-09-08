import { useState } from 'react'
import { api } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { PriceChart } from '../components/charts'
import { ErrorState, LoadingState, StaleDataBanner } from '../components/States'
import styles from './MarketExplorer.module.css'

/**
 * Market Explorer (§8): instrument selector + price/volume chart from
 * backend-authoritative cleaned data. No invented market values (§10).
 */
export default function MarketExplorer() {
  const [ticker, setTicker] = useState('AAPL')
  const [limit, setLimit] = useState(250)
  const candles = useFetch(() => api.candles(ticker, limit), [ticker, limit])

  const data = candles.data

  return (
    <div className="page">
      <h1 className="page-title">Market Explorer</h1>
      <p className="page-context">Cleaned OHLCV from the interim data tier — backend-authoritative values.</p>

      <div className={styles.controls}>
        <label htmlFor="ticker-select">Instrument</label>
        <select id="ticker-select" value={ticker} onChange={(event) => setTicker(event.target.value)}>
          <option value="AAPL">AAPL</option>
        </select>
        <label htmlFor="range-select">Range</label>
        <select id="range-select" value={limit} onChange={(event) => setLimit(Number(event.target.value))}>
          <option value={60}>60 sessions</option>
          <option value={250}>250 sessions</option>
          <option value={500}>500 sessions</option>
          <option value={1000}>1000 sessions</option>
        </select>
        <span className="muted">Interval: 1d (MVP)</span>
      </div>

      {data?.stale && (
        <StaleDataBanner
          lastTimestamp={data.candles.length ? data.candles[data.candles.length - 1].timestamp.slice(0, 10) : 'unknown'}
          affected="Market Explorer price chart"
        />
      )}

      {candles.loading && <LoadingState label="Loading candles…" />}
      {candles.error && (
        <ErrorState
          message={candles.error}
          code={candles.errorCode ?? undefined}
          requestId={candles.requestId}
          onRetry={candles.reload}
        />
      )}
      {data && data.candles.length === 0 && (
        <p className="muted">No data for this instrument — run the ingestion pipeline first (see README).</p>
      )}
      {data && data.candles.length > 0 && (
        <section className="card" aria-label="Price chart">
          <PriceChart candles={data.candles} stale={false} />
          <p className="muted" style={{ fontSize: 'var(--text-xs)' }}>
            Source: <code>{data.source_file}</code> · {data.count} candles · close prices, cleaned tier
          </p>
        </section>
      )}
    </div>
  )
}
