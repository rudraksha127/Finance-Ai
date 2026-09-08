import styles from './MetricCard.module.css'

interface MetricCardProps {
  label: string
  /** Backend-authoritative value, pre-formatted for display. */
  value: string
  /** Metric definition shown on hover/focus (§30.2: definitions on hover). */
  definition?: string
  context?: string
}

/** Single KPI presentation. No animation, no gamified emphasis (§34.1). */
export function MetricCard({ label, value, definition, context }: MetricCardProps) {
  return (
    <div className={styles.card}>
      <div className={styles.labelRow}>
        <span className={styles.label}>{label}</span>
        {definition && (
          <span
            className={styles.infoDot}
            tabIndex={0}
            role="note"
            aria-label={`${label}: ${definition}`}
            title={definition}
          >
            i
          </span>
        )}
      </div>
      <div className={styles.value}>{value}</div>
      {context && <div className={styles.context}>{context}</div>}
    </div>
  )
}
