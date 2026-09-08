import { NavLink, Outlet } from 'react-router-dom'
import { useFetch } from '../hooks/useFetch'
import { api } from '../api/client'
import styles from './AppShell.module.css'

const NAV_ITEMS: ReadonlyArray<{ to: string; label: string; end?: boolean }> = [
  { to: '/', label: 'Overview', end: true },
  { to: '/market', label: 'Market Explorer' },
  { to: '/predictions', label: 'Predictions' },
  { to: '/backtests', label: 'Backtests' },
  { to: '/experiments', label: 'Experiments' },
  { to: '/models', label: 'Models' },
  { to: '/datasets', label: 'Datasets' },
  { to: '/system', label: 'System Health' },
]

/**
 * Global shell (§6): persistent RESEARCH MODE badge (§6.2 — a LIVE badge
 * must not exist), model/version indicator, footer disclaimer on every page.
 */
export function AppShell() {
  const version = useFetch(() => api.version(), [])
  const health = useFetch(() => api.health(), [])

  const mode = version.data?.mode ?? health.data?.mode ?? 'research'
  const modelVersion = version.data?.model_version ?? health.data?.model_version ?? null
  const strategyVersion = version.data?.strategy_version

  return (
    <div className={styles.shell}>
      <header className={styles.topBar}>
        <span className={styles.modeBadge}>{mode === 'paper' ? 'PAPER SIMULATION' : 'RESEARCH MODE'}</span>
        <span className={styles.versionInfo}>
          {modelVersion ? (
            <NavLink to="/models" className={styles.modelLink}>
              {modelVersion}
              {strategyVersion ? ` · ${strategyVersion}` : ''}
            </NavLink>
          ) : (
            <span className={styles.noModel}>no model loaded</span>
          )}
        </span>
        <span className={styles.apiVersion} title="API contract version">
          API {version.data?.api_version ?? 'v1'}
        </span>
      </header>
      <div className={styles.body}>
        <nav className={styles.sidebar} aria-label="Primary">
          <ul>
            {NAV_ITEMS.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) => (isActive ? styles.active : styles.navLink)}
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <main className={styles.main} id="main-content">
          <Outlet />
        </main>
      </div>
      <footer className={styles.footer}>
        Research &amp; simulation only — not financial advice. This dashboard produces research signals; it cannot place orders.
      </footer>
    </div>
  )
}
