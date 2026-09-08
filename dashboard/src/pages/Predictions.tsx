import { useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { PredictionResponse, PredictionAuditRecord } from '../api/types'
import { useFetch } from '../hooks/useFetch'
import { ProbabilityChart } from '../components/ProbabilityChart'
import { StatusBadge } from '../components/StatusBadge'
import { DataTable } from '../components/DataTable'
import { ErrorState, LoadingState } from '../components/States'
import styles from './Predictions.module.css'

const SIGNAL_TONES = {
  BUY: 'positive',
  SELL: 'info',
  NO_TRADE: 'neutral',
} as const

function riskBand(score: number): { label: string; tone: 'positive' | 'info' | 'warning' | 'negative' } {
  if (score < 0.3) return { label: 'LOW RISK', tone: 'positive' }
  if (score < 0.6) return { label: 'MEDIUM RISK', tone: 'info' }
  if (score < 0.8) return { label: 'HIGH RISK', tone: 'warning' }
  return { label: 'VERY HIGH RISK', tone: 'negative' }
}

/**
 * Prediction view (§9): MODEL OUTPUT and DECISION OUTPUT are separate
 * sections (§9.3 hard rule). Probabilities show exact values (§10.2);
 * risk status is never color-only (§11.2); reason codes are shown as-is
 * (§12.1).
 */
export default function Predictions() {
  const audit = useFetch(() => api.predictions(undefined, 50), [])
  const [selected, setSelected] = useState<PredictionAuditRecord | null>(null)
  const [live, setLive] = useState<PredictionResponse | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<{ message: string; code: string; requestId: string | null } | null>(null)

  // Default the detail panel to the newest audited prediction so the
  // MODEL/DECISION separation is visible without an extra click.
  useEffect(() => {
    if (!selected && !live && audit.data && audit.data.length > 0) {
      setSelected(audit.data[0])
    }
  }, [audit.data, selected, live])

  const runPrediction = async () => {
    setRunning(true)
    setError(null)
    try {
      // The dashboard does not compute features; it replays the most recent
      // audited feature vector through the live endpoint for demonstration.
      const history = await api.predictions(undefined, 1)
      const latest = history[0]
      if (!latest) {
        setError({
          message: 'No audited prediction available to replay. Run a prediction via the API first (see README).',
          code: 'NO_PREDICTION_HISTORY',
          requestId: null,
        })
        return
      }
      const response = await api.predict({
        ticker: latest.ticker,
        timestamp: new Date().toISOString(),
        interval: '1d',
        feature_set_version: latest.feature_version,
        model_version: latest.model_version,
        features: {},
        market_context: {
          current_price: 1,
          data_timestamp: latest.data_timestamp,
        },
      })
      setLive(response)
    } catch (err) {
      if (err instanceof ApiError) {
        setError({ message: err.message, code: err.code, requestId: err.requestId })
      } else {
        setError({ message: 'Unexpected client error', code: 'CLIENT_ERROR', requestId: null })
      }
    } finally {
      setRunning(false)
    }
  }

  const shown = live
    ? {
        prediction_id: live.prediction_id,
        ticker: live.ticker,
        prediction: live.model_output.prediction,
        probabilities: live.model_output.probabilities,
        signal: live.decision_output.signal,
        risk_score: live.decision_output.risk_score,
        reason_codes: live.decision_output.reason_codes,
        model_version: live.model.model_version,
        feature_version: live.model.feature_version,
        strategy_version: live.decision_output.strategy_version,
        input_timestamp: live.inference_timestamp,
        inference_timestamp: live.inference_timestamp,
        confidence: live.model_output.confidence,
        data_timestamp: live.inference_timestamp,
        request_id: live.request_id,
        latency_ms: live.inference_time_ms,
      }
    : selected

  const band = shown ? riskBand(shown.risk_score) : null

  return (
    <div className="page">
      <h1 className="page-title">Predictions</h1>
      <p className="page-context">Model output vs decision output — never merged (ADR-0020).</p>

      <section className={`section ${styles.actions}`}>
        <button type="button" onClick={runPrediction} disabled={running}>
          {running ? 'Running…' : 'Run live prediction (replay latest audited input)'}
        </button>
        <span className="muted">
          The dashboard never computes features or decisions; it visualizes backend responses (§29.1).
        </span>
      </section>

      {error && <ErrorState message={error.message} code={error.code} requestId={error.requestId} />}

      {shown && (
        <div className={styles.detailGrid}>
          <section className="card" aria-label="Model output">
            <h2>MODEL OUTPUT</h2>
            <p className="secondary">
              Predicted class: <strong>{shown.prediction}</strong> · confidence (P of predicted class){' '}
              <strong>{shown.confidence?.toFixed(4)}</strong>
            </p>
            <ProbabilityChart probabilities={shown.probabilities} predicted={shown.prediction} />
          </section>

          <section className="card" aria-label="Decision output">
            <h2>DECISION OUTPUT</h2>
            <div className={styles.decisionRow}>
              <StatusBadge tone={SIGNAL_TONES[shown.signal]}>
                {shown.signal === 'BUY' ? '▲' : shown.signal === 'SELL' ? '▼' : '■'} {shown.signal}
              </StatusBadge>
              {band && (
                <StatusBadge tone={band.tone}>
                  {band.label} · score {shown.risk_score.toFixed(3)}
                </StatusBadge>
              )}
            </div>
            <h3 className={styles.reasonsTitle}>Reason codes</h3>
            <ul className={styles.reasonList}>
              {shown.reason_codes.map((code) => (
                <li key={code}>
                  <code>{code}</code>
                </li>
              ))}
            </ul>
          </section>

          <section className="card" aria-label="Metadata" style={{ gridColumn: '1 / -1' }}>
            <h2>METADATA</h2>
            <dl className={styles.metadata}>
              <div>
                <dt>Model version</dt>
                <dd><code>{shown.model_version}</code></dd>
              </div>
              <div>
                <dt>Feature version</dt>
                <dd><code>{shown.feature_version}</code></dd>
              </div>
              <div>
                <dt>Strategy version</dt>
                <dd><code>{shown.strategy_version}</code></dd>
              </div>
              <div>
                <dt>Prediction as-of</dt>
                <dd>{shown.input_timestamp}</dd>
              </div>
              <div>
                <dt>Inference timestamp</dt>
                <dd>{shown.inference_timestamp}</dd>
              </div>
              <div>
                <dt>Request ID</dt>
                <dd><code>{shown.request_id}</code></dd>
              </div>
            </dl>
          </section>
        </div>
      )}

      <section className="section" aria-label="Prediction history">
        <h2 className="section-title">Prediction history (audit trail)</h2>
        {audit.loading && <LoadingState />}
        {audit.error && (
          <ErrorState message={audit.error} code={audit.errorCode ?? undefined} requestId={audit.requestId} onRetry={audit.reload} />
        )}
        {audit.data && (
          <DataTable
            caption="Audited predictions, newest first. Values are backend-authoritative."
            rows={audit.data}
            rowKey={(record) => record.prediction_id}
            columns={[
              { key: 'ticker', header: 'Ticker', render: (record) => record.ticker },
              { key: 'prediction', header: 'Prediction', render: (record) => record.prediction },
              { key: 'p_up', header: 'P(UP)', render: (record) => record.probabilities.UP?.toFixed(4) ?? '—' },
              { key: 'signal', header: 'Signal', render: (record) => record.signal },
              { key: 'risk', header: 'Risk score', render: (record) => record.risk_score.toFixed(3) },
              { key: 'time', header: 'Inference time (UTC)', render: (record) => record.inference_timestamp.slice(0, 19).replace('T', ' ') },
              {
                key: 'actions',
                header: 'Actions',
                render: (record) => (
                  <button type="button" onClick={() => { setSelected(record); setLive(null) }}>
                    Inspect
                  </button>
                ),
              },
            ]}
          />
        )}
        {audit.data && audit.data.length === 0 && (
          <p className="muted">No predictions recorded yet — start the API and submit a /predict request (see README).</p>
        )}
      </section>
    </div>
  )
}
