import { api } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { DataTable } from '../components/DataTable'
import { StatusBadge } from '../components/StatusBadge'
import { ErrorState, EmptyState, LoadingState } from '../components/States'

/**
 * Models page (§19): model registry view — version, type, status, dataset/
 * feature/label versions, training timestamp, validation metrics. No
 * filesystem paths or credentials are exposed.
 */
export default function Models() {
  const models = useFetch(() => api.models(), [])

  return (
    <div className="page">
      <h1 className="page-title">Models</h1>
      <p className="page-context">Trained model artifacts served by the inference API.</p>

      {models.loading && <LoadingState />}
      {models.error && (
        <ErrorState message={models.error} code={models.errorCode ?? undefined} requestId={models.requestId} onRetry={models.reload} />
      )}
      {models.data && models.data.length === 0 && (
        <EmptyState
          title="No model registered."
          guidance="Train a baseline first: python -m scripts.run_model --model logistic_regression (see README)."
        />
      )}

      {models.data && models.data.length > 0 && (
        <section className="section" aria-label="Model list">
          <DataTable
            caption="Model artifacts, newest first. Metrics are validation metrics from the training experiment."
            rows={models.data}
            rowKey={(model) => model.model_version}
            columns={[
              { key: 'version', header: 'Model version', render: (model) => <code>{model.model_version}</code> },
              { key: 'type', header: 'Type', render: (model) => model.model_type },
              { key: 'status', header: 'Status', render: (model) => <StatusBadge tone="positive">{model.status.toUpperCase()}</StatusBadge> },
              { key: 'dataset', header: 'Dataset', render: (model) => model.dataset_version },
              { key: 'features', header: 'Features', render: (model) => `${model.feature_version} (${model.feature_count})` },
              { key: 'labels', header: 'Labels', render: (model) => model.label_version },
              { key: 'trained', header: 'Trained (UTC)', render: (model) => model.training_timestamp?.slice(0, 19).replace('T', ' ') },
              {
                key: 'accuracy',
                header: 'Val accuracy',
                render: (model) => {
                  const metrics = model.metrics as Record<string, number | null>
                  return metrics.accuracy?.toFixed(4) ?? '—'
                },
              },
              {
                key: 'f1',
                header: 'F1 (macro)',
                render: (model) => {
                  const metrics = model.metrics as Record<string, number | null>
                  return metrics.f1_macro?.toFixed(4) ?? '—'
                },
              },
            ]}
          />
          <p className="muted" style={{ fontSize: 'var(--text-xs)' }}>
            ML metrics do not imply trading profitability (TRAINING_PIPELINE_BLUEPRINT metric separation).
          </p>
        </section>
      )}
    </div>
  )
}
