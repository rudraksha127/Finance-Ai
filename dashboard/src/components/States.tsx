import { StatusBadge } from './StatusBadge'
import styles from './States.module.css'

/** Component-level loading (§22): never a full-page blocker for one panel. */
export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className={styles.loading} role="status" aria-live="polite">
      <span className={styles.spinner} aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

interface ErrorStateProps {
  /** Human-readable message; never stack traces or internals (§24). */
  message: string
  /** Backend error code, e.g. MODEL_NOT_FOUND. */
  code?: string
  /** Correlation id for debugging (§24). */
  requestId?: string | null
  onRetry?: () => void
}

/** Structured error display with correlation id (§24). */
export function ErrorState({ message, code, requestId, onRetry }: ErrorStateProps) {
  return (
    <div className={styles.error} role="alert">
      <StatusBadge tone="negative">{code ?? 'ERROR'}</StatusBadge>
      <p className={styles.errorText}>{message}</p>
      {requestId && (
        <p className={styles.requestId}>
          Request ID: <code>{requestId}</code>
        </p>
      )}
      {onRetry && (
        <button type="button" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}

interface EmptyStateProps {
  title: string
  /** Tell the user what they can do next (§23). */
  guidance?: string
}

/** Meaningful empty state with next-step guidance (§23). */
export function EmptyState({ title, guidance }: EmptyStateProps) {
  return (
    <div className={styles.empty}>
      <p className={styles.emptyTitle}>{title}</p>
      {guidance && <p className={styles.emptyGuidance}>{guidance}</p>}
    </div>
  )
}

interface StaleDataBannerProps {
  /** Last available data timestamp (backend-authoritative). */
  lastTimestamp: string
  /** Which component/area is affected (§25). */
  affected: string
}

/** STALE DATA banner — clearly not current (§25). */
export function StaleDataBanner({ lastTimestamp, affected }: StaleDataBannerProps) {
  return (
    <div className={styles.stale} role="alert">
      <StatusBadge tone="warning" icon="STALE">
        STALE DATA
      </StatusBadge>
      <span>
        Last available: <code>{lastTimestamp}</code> · Affected: {affected}
      </span>
    </div>
  )
}
