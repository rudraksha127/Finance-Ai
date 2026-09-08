/**
 * Component tests (milestone §39): MetricCard, ProbabilityChart,
 * StatusBadge, DataTable, LoadingState, ErrorState, EmptyState,
 * StaleDataBanner — plus color-independence accessibility checks (§27).
 */
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MetricCard } from './MetricCard'
import { ProbabilityChart } from './ProbabilityChart'
import { StatusBadge } from './StatusBadge'
import { DataTable } from './DataTable'
import { EmptyState, ErrorState, LoadingState, StaleDataBanner } from './States'

describe('MetricCard', () => {
  it('renders label and value', () => {
    render(<MetricCard label="Sharpe (rf = 0)" value="0.512" />)
    expect(screen.getByText('Sharpe (rf = 0)')).toBeInTheDocument()
    expect(screen.getByText('0.512')).toBeInTheDocument()
  })

  it('exposes the metric definition accessibly (not hover-only)', () => {
    render(<MetricCard label="Win rate" value="52.0%" definition="Share of trades with positive NET P&L" />)
    expect(screen.getByRole('note', { name: /win rate: share of trades/i })).toBeInTheDocument()
  })
})

describe('StatusBadge', () => {
  it('communicates status via text, not color alone (§27)', () => {
    render(<StatusBadge tone="negative">MODEL NOT FOUND</StatusBadge>)
    const badge = screen.getByText('MODEL NOT FOUND')
    expect(badge).toBeInTheDocument()
    expect(badge.parentElement).toHaveAttribute('data-tone', 'negative')
  })

  it('renders all tones with their text tag', () => {
    render(
      <>
        <StatusBadge tone="positive">ok</StatusBadge>
        <StatusBadge tone="warning">stale</StatusBadge>
      </>,
    )
    expect(screen.getByText('OK')).toBeInTheDocument()
    expect(screen.getByText('WARN')).toBeInTheDocument()
  })
})

describe('ProbabilityChart', () => {
  it('shows exact numeric values alongside bars (§10.2)', () => {
    render(
      <ProbabilityChart
        probabilities={{ UP: 0.62, DOWN: 0.25, HOLD: 0.13 }}
        predicted="UP"
      />,
    )
    expect(screen.getByText('0.6200')).toBeInTheDocument()
    expect(screen.getByText('0.2500')).toBeInTheDocument()
    expect(screen.getByText('0.1300')).toBeInTheDocument()
    expect(screen.getByText(/predicted/i)).toBeInTheDocument()
  })

  it('provides an accessible text summary of all probabilities (§27)', () => {
    render(<ProbabilityChart probabilities={{ UP: 0.5, DOWN: 0.3, HOLD: 0.2 }} predicted="UP" />)
    expect(screen.getByRole('img', { name: /up 50.0 percent.*down 30.0 percent.*hold 20.0 percent/i })).toBeInTheDocument()
  })

  it('includes the anti-certainty note (§34.1)', () => {
    render(<ProbabilityChart probabilities={{ UP: 0.9, DOWN: 0.05, HOLD: 0.05 }} predicted="UP" />)
    expect(screen.getByText(/calibration not validated/i)).toBeInTheDocument()
  })
})

describe('DataTable', () => {
  it('renders rows and paginates beyond pageSize', () => {
    const rows = Array.from({ length: 75 }, (_, index) => ({ id: String(index), name: `row-${index}` }))
    render(
      <DataTable
        rows={rows}
        rowKey={(row) => row.id}
        pageSize={50}
        columns={[
          { key: 'id', header: 'ID', render: (row) => row.id },
          { key: 'name', header: 'Name', render: (row) => row.name },
        ]}
      />,
    )
    expect(screen.getByText('row-0')).toBeInTheDocument()
    expect(screen.queryByText('row-74')).not.toBeInTheDocument()
    expect(screen.getByText(/page 1 of 2 \(75 rows\)/i)).toBeInTheDocument()
  })

  it('shows the empty message when there are no rows', () => {
    render(
      <DataTable
        rows={[]}
        rowKey={(row: { id: string }) => row.id}
        columns={[{ key: 'id', header: 'ID', render: (row) => row.id }]}
        emptyMessage="No backtests available."
      />,
    )
    expect(screen.getByText('No backtests available.')).toBeInTheDocument()
  })

  it('associates a caption with the table', () => {
    render(
      <DataTable
        rows={[{ id: '1' }]}
        rowKey={(row) => row.id}
        caption="Audited predictions, newest first."
        columns={[{ key: 'id', header: 'ID', render: (row) => row.id }]}
      />,
    )
    const table = screen.getByRole('table')
    expect(within(table).getByText(/audited predictions/i)).toBeInTheDocument()
  })
})

describe('States', () => {
  it('LoadingState exposes a polite live region', () => {
    render(<LoadingState label="Loading candles…" />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading candles…')
  })

  it('ErrorState shows code, message, and correlation id without internals (§24)', () => {
    render(
      <ErrorState message="Model version 'x' is not available" code="MODEL_NOT_FOUND" requestId="req_42" />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('MODEL_NOT_FOUND')
    expect(screen.getByText(/model version 'x' is not available/i)).toBeInTheDocument()
    expect(screen.getByText('req_42')).toBeInTheDocument()
  })

  it('EmptyState includes next-step guidance (§23)', () => {
    render(<EmptyState title="No backtests available." guidance="Run the backtest pipeline first." />)
    expect(screen.getByText('No backtests available.')).toBeInTheDocument()
    expect(screen.getByText(/run the backtest pipeline first/i)).toBeInTheDocument()
  })

  it('StaleDataBanner marks data as STALE with the last timestamp (§25)', () => {
    render(<StaleDataBanner lastTimestamp="2026-08-24" affected="price chart" />)
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('STALE DATA')
    expect(alert).toHaveTextContent('2026-08-24')
    expect(alert).toHaveTextContent('price chart')
  })
})
