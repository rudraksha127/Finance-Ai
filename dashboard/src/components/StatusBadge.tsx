import type { ReactNode } from 'react'
import styles from './StatusBadge.module.css'

export type BadgeTone = 'positive' | 'negative' | 'neutral' | 'warning' | 'info'

interface StatusBadgeProps {
  tone: BadgeTone
  children: ReactNode
  /** Optional icon glyph reinforcing the tone (non-color channel). */
  icon?: string
}

const TONE_LABELS: Record<BadgeTone, string> = {
  positive: 'OK',
  negative: 'FAIL',
  neutral: 'INFO',
  warning: 'WARN',
  info: 'NOTE',
}

/** Semantic status badge. Status is always carried by TEXT, never color alone. */
export function StatusBadge({ tone, children, icon }: StatusBadgeProps) {
  return (
    <span className={`${styles.badge} ${styles[tone]}`} data-tone={tone}>
      <span className={styles.toneTag} aria-hidden="true">
        {icon ?? TONE_LABELS[tone]}
      </span>
      <span className={styles.label}>{children}</span>
    </span>
  )
}
