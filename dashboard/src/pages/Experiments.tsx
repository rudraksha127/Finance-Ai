import { useState } from 'react'
import { api } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { DataTable } from '../components/DataTable'
import { StatusBadge } from '../components/StatusBadge'
import { ErrorState, EmptyState, LoadingState } from '../components/States'
import styles from './Experiments.module.css'

interface ExperimentRow {
  experiment_id: string
  model_version: string
  dataset_version: string
  feature_version: string
  label_version: string
  status: string
  created_at: string
  accuracy: number | null
  f1_macro: number | null
}

function toRow(record: {
  experiment_id: string
  model_version: string
  dataset_version: string
  feature_version: string
  label_version: string
  status: string
  created_at: string
  metrics: Record<string, unknown>
}): ExperimentRow {
  const metrics = record.metrics as Record<string, number | null>
  return {
    ...record,
    accuracy: metrics.accuracy ?? null,
    f1_macro: metrics.f1_macro ?? null,
  }
}

/**
 * Experiments (§18): list + detail. Comparison is only allowed when the
 * dataset/feature/label versions match — otherwise a ComparabilityNotice
 * explains exactly why (§18 rule).
 */
export default function Experiments() {
  const list = useFetch(() => api.experiments(), [])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const detail = useFetch(
    () => (selectedId ? api.experiment(selectedId) : Promise.resolve(null)),
    [selectedId],
  )

  const rows = (list.data ?? []).map(toRow)
  const d = detail.data
  const comparableWith = d
    ? rows.filter(
        (row) =>
          row.experiment_id !== d.experiment_id &&
          row.dataset_version === d.dataset_version &&
          row.feature_version === d.feature_version &&
          row.label_version === d.label_version,
      )
    : []

  return (
    <div className="page">
      <h1 className="page-title">Experiments</h1>
      <p className="page-context">Training runs recorded by the experiment pipeline.</p>

      {list.loading && <LoadingState />}
      {list.error && (
        <ErrorState message={list.error} code={list.errorCode ?? undefined} requestId={list.requestId} onRetry={list.reload} />
      )}
      {list.data && list.data.length === 0 && (
        <EmptyState
          title="No experiments yet."
          guidance="Train a baseline first: python -m scripts.run_model --model logistic_regression (see README)."
        />
      )}

      {rows.length > 0 && (
        <section className="section" aria-label="Experiment list">
          <DataTable
            caption="Training experiments, newest first."
            rows={rows}
            rowKey={(row) => row.experiment_id}
            columns={[
              { key: 'id', header: 'Experiment', render: (row) => <code>{row.experiment_id}</code> },
              { key: 'model', header: 'Model', render: (row) => row.model_version },
              { key: 'dataset', header: 'Dataset', render: (row) => row.dataset_version },
              { key: 'accuracy', header: 'Val accuracy', render: (row) => row.accuracy?.toFixed(4) ?? '—' },
              { key: 'f1', header: 'F1 (macro)', render: (row) => row.f1_macro?.toFixed(4) ?? '—' },
              { key: 'status', header: 'Status', render: (row) => <StatusBadge tone={row.status === 'COMPLETED' ? 'positive' : 'warning'}>{row.status}</StatusBadge> },
              { key: 'created', header: 'Created', render: (row) => row.created_at?.slice(0, 19).replace('T', ' ') },
              {
                key: 'actions',
                header: 'Actions',
                render: (row) => (
                  <button type="button" onClick={() => setSelectedId(row.experiment_id)}>
                    Inspect
                  </button>
                ),
              },
            ]}
          />
        </section>
      )}

      {d && (
        <section className="card" aria-label="Experiment detail">
          <h2 className="section-title">
            Experiment <code>{d.experiment_id}</code>
          </h2>
          <div className={styles.meta}>
            <div><strong>Model:</strong> <code>{d.model_version}</code></div>
            <div><strong>Dataset:</strong> <code>{d.dataset_version}</code></div>
            <div><strong>Features:</strong> <code>{d.feature_version}</code> ({d.rows.train}/{d.rows.validation}/{d.rows.test} rows)</div>
            <div><strong>Labels:</strong> <code>{d.label_version}</code></div>
            <div><strong>Seed:</strong> <code>{d.random_seed}</code></div>
            <div><strong>Git commit:</strong> <code>{d.git_commit}</code></div>
            <div><strong>Training period:</strong> {d.train_period.start?.slice(0, 10)} → {d.train_period.end?.slice(0, 10)}</div>
            <div><strong>Validation period:</strong> {d.validation_period.start?.slice(0, 10)} → {d.validation_period.end?.slice(0, 10)}</div>
          </div>

          <h3 className={styles.compareTitle}>Comparable experiments</h3>
          {comparableWith.length === 0 ? (
            <p className={styles.notice}>
              No other experiment shares this experiment's dataset/feature/label versions — side-by-side
              comparison would not be valid (different data assumptions). Comparison is disabled rather than shown misleadingly.
            </p>
          ) : (
            <ul className={styles.compareList}>
              {comparableWith.map((row) => (
                <li key={row.experiment_id}>
                  <code>{row.experiment_id}</code> — accuracy {row.accuracy?.toFixed(4) ?? '—'} vs this{' '}
                  {(d.metrics as Record<string, number>).accuracy?.toFixed(4) ?? '—'}
                </li>
              ))}
            </ul>
          )}

          {d.feature_importance.length > 0 && (
            <>
              <h3 className={styles.compareTitle}>Feature importance (top 10, descriptive not causal)</h3>
              <DataTable
                rows={d.feature_importance}
                rowKey={(row) => String(row.rank)}
                pageSize={10}
                columns={[
                  { key: 'rank', header: 'Rank', render: (row) => row.rank },
                  { key: 'feature', header: 'Feature', render: (row) => <code>{row.feature}</code> },
                  { key: 'importance', header: 'Importance', render: (row) => row.importance.toFixed(6) },
                ]}
              />
            </>
          )}
        </section>
      )}
    </div>
  )
}
