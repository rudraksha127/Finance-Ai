import { api } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { StatusBadge } from '../components/StatusBadge'
import { MetricCard } from '../components/MetricCard'
import { ErrorState, LoadingState } from '../components/States'
import styles from './SystemHealth.module.css'

/**
 * System Health (§21): API status, model availability, data freshness,
 * latest pipeline activity. Every value comes from a backend endpoint —
 * nothing is faked.
 */
export default function SystemHealth() {
  const health = useFetch(() => api.health(), [])
  const ready = useFetch(() => api.ready(), [])
  const status = useFetch(() => api.systemStatus(), [])

  return (
    <div className="page">
      <h1 className="page-title">System Health</h1>
      <p className="page-context">Live status from /health, /ready, and /system/status.</p>

      {health.loading && <LoadingState label="Checking API health…" />}
      {health.error && (
        <ErrorState
          message={health.error}
          code={health.errorCode ?? undefined}
          requestId={health.requestId}
          onRetry={health.reload}
        />
      )}

      {health.data && (
        <section className="section" aria-label="API status">
          <h2 className="section-title">API status</h2>
          <div className="card-grid">
            <MetricCard
              label="Liveness (/health)"
              value={health.data.status.toUpperCase()}
              definition="Process is running and the default model is loaded."
              context={`uptime ${Math.round(health.data.uptime_seconds)}s · mode ${health.data.mode}`}
            />
            <MetricCard
              label="Model loaded"
              value={health.data.model_loaded ? 'YES' : 'NO'}
              definition="Default model artifact loaded into memory at startup."
              context={health.data.model_version ?? undefined}
            />
          </div>
        </section>
      )}

      {ready.data && (
        <section className="section" aria-label="Readiness checks">
          <h2 className="section-title">Readiness checks (/ready)</h2>
          <ul className={styles.checks}>
            {Object.entries(ready.data.checks).map(([check, passed]) => (
              <li key={check}>
                <StatusBadge tone={passed ? 'positive' : 'negative'}>{check.replace(/_/g, ' ').toUpperCase()}</StatusBadge>
              </li>
            ))}
          </ul>
        </section>
      )}
      {ready.error && (
        <ErrorState message={ready.error} code={ready.errorCode ?? undefined} requestId={ready.requestId} onRetry={ready.reload} />
      )}

      {status.error && (
        <ErrorState message={status.error} code={status.errorCode ?? undefined} requestId={status.requestId} onRetry={status.reload} />
      )}

      {status.data && (
        <section className="section" aria-label="Pipeline activity">
          <h2 className="section-title">Pipeline activity</h2>
          <div className="card-grid">
            <MetricCard
              label="Latest dataset"
              value={status.data.latest_dataset?.dataset_version ?? '—'}
              definition="Most recent immutable dataset version."
              context={status.data.latest_dataset ? `quality ${status.data.latest_dataset.quality_score} · built ${status.data.latest_dataset.generated_at?.slice(0, 10)}` : 'none built yet'}
            />
            <MetricCard
              label="Latest training"
              value={status.data.latest_model?.model_version ?? '—'}
              definition="Most recent trained model artifact."
              context={status.data.latest_model?.training_timestamp?.slice(0, 10)}
            />
            <MetricCard
              label="Latest backtest"
              value={status.data.latest_backtest ?? '—'}
              definition="Most recent backtest run directory."
            />
            <MetricCard
              label="Artifact counts"
              value={`${status.data.counts.datasets}d / ${status.data.counts.models}m / ${status.data.counts.experiments}e / ${status.data.counts.backtests}b`}
              definition="datasets / models / experiments / backtests currently stored."
            />
          </div>
        </section>
      )}
    </div>
  )
}
