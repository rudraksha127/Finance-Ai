import { api } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { DataTable } from '../components/DataTable'
import { StatusBadge } from '../components/StatusBadge'
import { ErrorState, EmptyState, LoadingState } from '../components/States'

function qualityTone(score: number): 'positive' | 'info' | 'warning' | 'negative' {
  if (score >= 90) return 'positive'
  if (score >= 70) return 'info'
  if (score >= 50) return 'warning'
  return 'negative'
}

/**
 * Datasets page (§20): dataset identity + quality so researchers can see
 * exactly what data produced a model.
 */
export default function Datasets() {
  const datasets = useFetch(() => api.datasets(), [])

  return (
    <div className="page">
      <h1 className="page-title">Datasets</h1>
      <p className="page-context">Immutable dataset versions with full lineage and quality gates.</p>

      {datasets.loading && <LoadingState />}
      {datasets.error && (
        <ErrorState message={datasets.error} code={datasets.errorCode ?? undefined} requestId={datasets.requestId} onRetry={datasets.reload} />
      )}
      {datasets.data && datasets.data.length === 0 && (
        <EmptyState
          title="No datasets built."
          guidance="Build one first: python -m scripts.run_dataset --ticker AAPL (see README)."
        />
      )}

      {datasets.data && datasets.data.length > 0 && (
        <section className="section" aria-label="Dataset list">
          <DataTable
            caption="Dataset versions, newest first."
            rows={datasets.data}
            rowKey={(dataset) => dataset.dataset_version}
            columns={[
              { key: 'version', header: 'Version', render: (dataset) => <code>{dataset.dataset_version}</code> },
              { key: 'instruments', header: 'Instruments', render: (dataset) => dataset.instruments.join(', ') },
              { key: 'range', header: 'Date range', render: (dataset) => `${dataset.date_range.start?.slice(0, 10) ?? '—'} → ${dataset.date_range.end?.slice(0, 10) ?? '—'}` },
              { key: 'rows', header: 'Rows', render: (dataset) => String(dataset.row_count) },
              { key: 'features', header: 'Features', render: (dataset) => String(dataset.feature_count) },
              { key: 'labels', header: 'Label version', render: (dataset) => dataset.label_version },
              {
                key: 'quality',
                header: 'Quality',
                render: (dataset) => (
                  <StatusBadge tone={qualityTone(dataset.quality_score)}>
                    {dataset.quality_score.toFixed(1)} · {dataset.quality_rating.toUpperCase()}
                  </StatusBadge>
                ),
              },
              { key: 'generated', header: 'Generated', render: (dataset) => dataset.generated_at?.slice(0, 10) },
            ]}
          />
          <p className="muted" style={{ fontSize: 'var(--text-xs)' }}>
            Source checksums: {datasets.data.map((dataset) => Object.entries(dataset.source_versions).map(([ticker, hash]) => `${ticker}:${hash.slice(0, 8)}`).join(', '))}
          </p>
        </section>
      )}
    </div>
  )
}
