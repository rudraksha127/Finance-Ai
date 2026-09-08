import { useState } from 'react'
import { api } from '../api/client'
import type { BacktestSummary } from '../api/types'
import { useFetch } from '../hooks/useFetch'
import { EquityChart, DrawdownChart } from '../components/charts'
import { DataTable } from '../components/DataTable'
import { MetricCard } from '../components/MetricCard'
import { ErrorState, EmptyState, LoadingState } from '../components/States'
import styles from './Backtests.module.css'

function formatMetric(value: number | null | undefined, digits = 4, suffix = ''): string {
  return value === null || value === undefined ? '—' : `${value.toFixed(digits)}${suffix}`
}

/**
 * Backtest view (§13/§14): full identity panel, metrics as produced by
 * the engine (net of costs, Sharpe rf=0, annualization 252d), equity/
 * drawdown curves plotted not recomputed, benchmark comparison with
 * identical periods.
 */
export default function Backtests() {
  const list = useFetch(() => api.backtests(), [])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const activeId = selectedId ?? list.data?.[0]?.backtest_id ?? null
  const detail = useFetch(
    () => (activeId ? api.backtest(activeId) : Promise.resolve(null)),
    [activeId],
  )

  const d = detail.data

  return (
    <div className="page">
      <h1 className="page-title">Backtests</h1>
      <p className="page-context">Simulated, net-of-cost research results. Not a performance claim (§34.2).</p>

      {list.loading && <LoadingState />}
      {list.error && (
        <ErrorState message={list.error} code={list.errorCode ?? undefined} requestId={list.requestId} onRetry={list.reload} />
      )}
      {list.data && list.data.length === 0 && (
        <EmptyState
          title="No backtests available."
          guidance="Run the backtest pipeline first: python -m scripts.run_backtest --ticker AAPL --model-version <model> (see README)."
        />
      )}

      {list.data && list.data.length > 0 && (
        <>
          <section className={`section ${styles.selector}`} aria-label="Backtest selection">
            <label htmlFor="backtest-select">Backtest run</label>
            <select
              id="backtest-select"
              value={activeId ?? ''}
              onChange={(event) => setSelectedId(event.target.value)}
            >
              {list.data.map((run) => (
                <option key={run.backtest_id} value={run.backtest_id}>
                  {run.backtest_id} ({run.instrument}, {run.created_at?.slice(0, 10)})
                </option>
              ))}
            </select>
          </section>

          {detail.loading && <LoadingState label="Loading backtest detail…" />}
          {detail.error && (
            <ErrorState
              message={detail.error}
              code={detail.errorCode ?? undefined}
              requestId={detail.requestId}
              onRetry={detail.reload}
            />
          )}

          {d && (
            <>
              <section className="card section" aria-label="Experiment identity">
                <h2 className="section-title">Experiment identity</h2>
                <dl className={styles.identity}>
                  <div><dt>Backtest ID</dt><dd><code>{d.backtest_id}</code></dd></div>
                  <div><dt>Model</dt><dd><code>{d.model_version ?? 'walk-forward (per fold)'}</code></dd></div>
                  <div><dt>Dataset</dt><dd><code>{d.dataset_version}</code></dd></div>
                  <div><dt>Features</dt><dd><code>{d.feature_version}</code></dd></div>
                  <div><dt>Labels</dt><dd><code>{d.label_version}</code></dd></div>
                  <div><dt>Strategy</dt><dd><code>{d.strategy_version}</code></dd></div>
                  <div><dt>Cost model</dt><dd><code>{d.cost_model_version}</code></dd></div>
                  <div><dt>Execution</dt><dd>{d.execution_convention}</dd></div>
                  <div>
                    <dt>Evaluation period</dt>
                    <dd>{d.evaluation_period.start?.slice(0, 10)} → {d.evaluation_period.end?.slice(0, 10)}</dd>
                  </div>
                </dl>
              </section>

              <section className="section" aria-label="Performance metrics">
                <h2 className="section-title">Performance (net of costs)</h2>
                <div className="card-grid">
                  <MetricCard label="Cumulative return" value={formatMetric(d.financial_metrics.cumulative_return as number, 4)} definition="Total return over the evaluation period, net of transaction costs." />
                  <MetricCard label="Sharpe (rf = 0)" value={formatMetric(d.financial_metrics.sharpe_ratio as number, 3)} definition="Annualized return over annualized volatility; risk-free rate 0 (EVAL §15.2)." />
                  <MetricCard label="Sortino (rf = 0)" value={formatMetric(d.financial_metrics.sortino_ratio as number, 3)} definition="Annualized return over downside deviation." />
                  <MetricCard label="Max drawdown" value={formatMetric(d.financial_metrics.max_drawdown as number, 4)} definition="Largest peak-to-trunk equity decline over the period." />
                  <MetricCard label="Win rate" value={d.financial_metrics.win_rate === null || d.financial_metrics.win_rate === undefined ? '—' : `${((d.financial_metrics.win_rate as number) * 100).toFixed(1)}%`} definition="Share of trades with positive NET P&L (after costs)." />
                  <MetricCard label="Profit factor" value={formatMetric(d.financial_metrics.profit_factor as number, 3)} definition="Gross wins / gross losses on net P&L (EVAL §15.2)." />
                  <MetricCard label="Turnover" value={formatMetric(d.financial_metrics.turnover as number, 3)} definition="2 × trades / days (round trips per day)." />
                  <MetricCard label="Trades" value={String(d.financial_metrics.number_of_trades ?? '—')} definition="Number of completed round trips." context={`annualized, ${String(d.config_snapshot.annualization ?? 252)}d`} />
                </div>
              </section>

              <section className="section card" aria-label="Equity curve">
                <h2 className="section-title">Equity curve</h2>
                <EquityChart points={d.equity_curve} />
              </section>

              <section className="section card" aria-label="Drawdown curve">
                <h2 className="section-title">Drawdown</h2>
                <DrawdownChart points={d.drawdown_curve} />
              </section>

              <section className="section" aria-label="Benchmark comparison">
                <h2 className="section-title">Benchmark comparison (same period, same cost basis)</h2>
                <p className="muted" style={{ fontSize: 'var(--text-xs)' }}>
                  {String(d.benchmarks.note ?? '')}
                </p>
                <DataTable
                  caption="Benchmark comparison over the identical evaluation period."
                  rows={Object.entries(d.benchmarks).filter(([, v]) => typeof v !== 'object').map(([key, value]) => ({ key, value: String(value) }))}
                  rowKey={(row) => row.key}
                  columns={[
                    { key: 'key', header: 'Benchmark', render: (row) => row.key },
                    { key: 'value', header: 'Value', render: (row) => row.value },
                  ]}
                />
              </section>

              <section className="section" aria-label="Trade ledger">
                <h2 className="section-title">Trade ledger (net P&L after costs)</h2>
                <DataTable
                  rows={d.trades}
                  rowKey={(row) => String(row.trade_id)}
                  pageSize={25}
                  emptyMessage="No trades in this backtest (zero-trade run)."
                  columns={[
                    { key: 'id', header: 'Trade', render: (row) => String(row.trade_id) },
                    { key: 'entry', header: 'Entry', render: (row) => String(row.execution_timestamp).slice(0, 10) },
                    { key: 'entry_price', header: 'Entry price', render: (row) => Number(row.entry_price).toFixed(2) },
                    { key: 'exit', header: 'Exit', render: (row) => String(row.exit_timestamp).slice(0, 10) },
                    { key: 'exit_price', header: 'Exit price', render: (row) => Number(row.exit_price).toFixed(2) },
                    { key: 'gross', header: 'Gross P&L', render: (row) => Number(row.gross_pnl).toFixed(4) },
                    { key: 'costs', header: 'Costs', render: (row) => Number(row.costs).toFixed(4) },
                    { key: 'net', header: 'Net P&L', render: (row) => Number(row.net_pnl).toFixed(4) },
                    { key: 'reason', header: 'Exit reason', render: (row) => String(row.reason) },
                  ]}
                />
              </section>
            </>
          )}
        </>
      )}
    </div>
  )
}

export type { BacktestSummary }
