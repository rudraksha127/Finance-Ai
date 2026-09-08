import type { Label } from '../api/types'
import styles from './ProbabilityChart.module.css'

interface ProbabilityChartProps {
  probabilities: Record<Label, number>
  /** Highlight the predicted class. */
  predicted: Label
}

const CLASSES: Label[] = ['UP', 'DOWN', 'HOLD']

/**
 * Three horizontal probability bars (§10.1). Exact numeric values remain
 * visible (§10.2 anti-certainty rules); bars never imply certainty.
 */
export function ProbabilityChart({ probabilities, predicted }: ProbabilityChartProps) {
  const total = CLASSES.reduce((sum, label) => sum + (probabilities[label] ?? 0), 0)
  return (
    <div className={styles.wrap} role="img" aria-label={`Class probabilities: ${CLASSES.map((label) => `${label} ${(probabilities[label] * 100).toFixed(1)} percent`).join(', ')}`}>
      {CLASSES.map((label) => {
        const probability = probabilities[label] ?? 0
        const percent = total > 0 ? (probability / total) * 100 : 0
        return (
          <div key={label} className={styles.row}>
            <span className={styles.classLabel}>
              {label}
              {label === predicted && <span className={styles.predictedTag}> (predicted)</span>}
            </span>
            <div
              className={styles.track}
              role="presentation"
            >
              <div
                className={`${styles.bar} ${label === predicted ? styles.predictedBar : ''}`}
                style={{ width: `${percent}%` }}
              />
            </div>
            <span className={styles.value}>{probability.toFixed(4)}</span>
          </div>
        )
      })}
      <p className={styles.note}>
        Raw model probabilities — calibration not validated; not a confidence guarantee (§34.1).
      </p>
    </div>
  )
}
