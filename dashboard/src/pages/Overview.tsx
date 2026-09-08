import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { MetricCard } from '../components/MetricCard'
import { StatusBadge } from '../components/StatusBadge'
import { ErrorState, LoadingState } from '../components/States'
import styles from './Overview.module.css'

/**
 * Overview (§7): answers "what is the system doing right now" with 7
 * intentionally-limited cards (§7.3).
 */
export default function Overview() {
  const version = useFetch(() => api.version(), [])
  const health = useFetch(() => api.health(), [])
  const status = useFetch(() => api.systemStatus(), [])
  const predictions = useFetch(() => api.predictions(undefined, 1), [])
  const backtests = useFetch(() => api.backtests(), [])

  const latestPrediction = predictions.data?.[0] ?? null
  const latestBacktest = backtests.data?.[0] ?? null
  const dataset = status.data?.latest_dataset ?? null
  const model = status.data?.latest_model ?? null

  return (
    <div className="page">
      <h1 className="page-title">Overview</h1>
      <p className="page-context">System status, active model, and latest research artifacts.</p>

      {version.error && <ErrorState message={version.error} code={version.errorCode ?? undefined} requestId={version.requestId} onRetry={version.reload} />}
      {status.error && (
        <ErrorState
          message={status.error}
          code={status.errorCode ?? undefined}
          requestId={status.requestId}
          onRetry={status.reload}
        />
      )}
      {version.loading && <LoadingState label="Loading contract versions…" />}

      {version.data && (
        <>
          <section className={`card-grid ${styles.grid}`} aria-label="System summary">
            <MetricCard
              label="System health"
              value={health.data?.status ?? 'unknown'}
              definition="Liveness + readiness of the inference API (/health)."
              context={health.data ? `uptime ${Math.round(health.data.uptime_seconds)}s · mode ${health.data.mode}` : undefined}
            />
            <MetricCard
              label="Active model"
              value={model?.model_version ?? version.data.model_version ?? '—'}
              definition="Model currently served by the API (explicit > configured default > newest artifact)."
              context={model ? `trained ${model.training_timestamp?.slice(0, 10) ?? 'unknown'}` : undefined}
            />
            <MetricCard
              label="Active dataset"
              value={dataset?.dataset_version ?? '—'}
              definition="Latest immutable dataset version built by the dataset builder."
              context={dataset ? `quality ${dataset.quality_score}` : undefined}
            />
            <MetricCard
              label="Latest prediction"
              value={latestPrediction ? `${latestPrediction.ticker} ${latestPrediction.prediction}` : '—'}
              definition="Most recent audited model prediction (audit trail)."
              context={
                latestPrediction
                  ? `signal ${latestPrediction.signal} · P(UP) ${latestPrediction.probabilities.UP?.toFixed(2)}`
                  : undefined
              }
            />
            <MetricCard
              label="Latest backtest"
              value={latestBacktest?.backtest_id ?? '—'}
              definition="Most recent backtest run in the backtest artifact store."
              context={
                latestBacktest
                  ? `net return ${(latestBacktest.cumulative_return ?? 0).toFixed(4)} · ${latestBacktest.trade_count} trades`
                  : undefined
              }
            />
            <MetricCard
              label="Data freshness"
              value={dataset?.generated_at ? dataset.generated_at.slice(0, 10) : 'unknown'}
              definition="When the latest dataset version was generated."
              context={dataset ? 'dataset build timestamp (UTC)' : 'no dataset built yet'}
            />
            <MetricCard
              label="Latest training"
              value={model?.training_timestamp ? model.training_timestamp.slice(0, 10) : '—'}
              definition="When the latest model artifact was trained."
              context={status.data ? `${status.data.counts.experiments} experiments recorded` : undefined}
            />
          </section>

          <section className={`section ${styles.links}`} aria-label="Quick navigation">
            <StatusBadge tone={health.data?.status === 'ok' ? 'positive' : 'warning'}>
              {health.data?.status === 'ok' ? 'API READY' : 'API DEGRADED'}
            </StatusBadge>
            <nav aria-label="Detail pages">
              <Link to="/system">System Health</Link> · <Link to="/models">Models</Link> ·{' '}
              <Link to="/datasets">Datasets</Link> · <Link to="/backtests">Backtests</Link> ·{' '}
              <Link to="/predictions">Predictions</Link>
            </nav>
          </section>
        </>
      )}
    </div>
  )
}
