/**
 * Page tests (milestone §39): each route renders correctly against mocked
 * backend responses, including error and empty states. No network (§34).
 */
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Overview from './Overview'
import Predictions from './Predictions'
import Backtests from './Backtests'
import Models from './Models'
import Datasets from './Datasets'
import SystemHealth from './SystemHealth'
import { api } from '../api/client'

vi.mock('../api/client', () => ({
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      public code: string,
      message: string,
      public requestId: string | null,
    ) {
      super(message)
    }
  },
  api: {
    version: vi.fn(),
    health: vi.fn(),
    ready: vi.fn(),
    modelInfo: vi.fn(),
    predict: vi.fn(),
    datasets: vi.fn(),
    dataset: vi.fn(),
    models: vi.fn(),
    experiments: vi.fn(),
    experiment: vi.fn(),
    backtests: vi.fn(),
    backtest: vi.fn(),
    candles: vi.fn(),
    predictions: vi.fn(),
    systemStatus: vi.fn(),
  },
}))

const mockedApi = vi.mocked(api)

function renderAt(element: React.ReactElement, path = '/') {
  return render(<MemoryRouter initialEntries={[path]}>{element}</MemoryRouter>)
}

const VERSION = {
  api_version: 'v1',
  model_version: 'random_forest_v0.2',
  feature_version: 'v0.2',
  label_version: 'v0.2',
  strategy_version: 'stg_v0.1',
  mode: 'research' as const,
}

const HEALTH = {
  status: 'ok' as const,
  model_loaded: true,
  model_version: 'random_forest_v0.2',
  uptime_seconds: 120.5,
  mode: 'research' as const,
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedApi.version.mockResolvedValue(VERSION)
  mockedApi.health.mockResolvedValue(HEALTH)
})

describe('Overview', () => {
  it('renders the seven summary cards with backend values', async () => {
    mockedApi.systemStatus.mockResolvedValue({
      latest_dataset: { dataset_version: 'v0.2', generated_at: '2026-09-05T10:00:00Z', quality_score: 95.98 },
      latest_model: { model_version: 'random_forest_v0.2', training_timestamp: '2026-09-05T11:00:00Z' },
      latest_backtest: 'bt_1',
      latest_experiment: 'exp_1',
      counts: { datasets: 2, models: 4, experiments: 6, backtests: 3 },
      generated_at: '2026-09-07T00:00:00Z',
    })
    mockedApi.predictions.mockResolvedValue([])
    mockedApi.backtests.mockResolvedValue([])
    renderAt(<Overview />)
    await waitFor(() => expect(screen.getByText('random_forest_v0.2')).toBeInTheDocument())
    expect(screen.getByText('v0.2')).toBeInTheDocument()
    expect(screen.getByText('System health')).toBeInTheDocument()
  })

  it('shows an error state when the backend is unreachable', async () => {
    mockedApi.systemStatus.mockRejectedValue(
      new (await import('../api/client')).ApiError(0, 'SERVICE_UNREACHABLE', 'Cannot reach the Finance AI API.', 'req_x'),
    )
    mockedApi.predictions.mockResolvedValue([])
    mockedApi.backtests.mockResolvedValue([])
    renderAt(<Overview />)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByText(/cannot reach the finance ai api/i)).toBeInTheDocument()
  })
})

describe('Predictions', () => {
  it('separates MODEL OUTPUT from DECISION OUTPUT (§9.3)', async () => {
    mockedApi.predictions.mockResolvedValue([
      {
        prediction_id: 'pred_1',
        request_id: 'req_1',
        ticker: 'AAPL',
        input_timestamp: '2026-09-07T00:00:00Z',
        data_timestamp: '2026-09-07T00:00:00Z',
        model_version: 'random_forest_v0.2',
        feature_version: 'v0.2',
        strategy_version: 'stg_v0.1',
        prediction: 'DOWN',
        probabilities: { UP: 0.24, DOWN: 0.63, HOLD: 0.13 },
        confidence: 0.63,
        signal: 'SELL',
        risk_score: 0.29,
        reason_codes: ['MODEL_SIGNAL_SELL', 'VOLATILITY_OK'],
        inference_timestamp: '2026-09-07T01:00:00Z',
      },
    ])
    renderAt(<Predictions />)
    await waitFor(() => expect(screen.getByText('MODEL OUTPUT')).toBeInTheDocument())
    expect(screen.getByText('DECISION OUTPUT')).toBeInTheDocument()
    expect(screen.getAllByText('0.6300').length).toBeGreaterThan(0)
    expect(screen.getByText('MODEL_SIGNAL_SELL')).toBeInTheDocument()
  })

  it('shows risk as text, not color alone (§14)', async () => {
    mockedApi.predictions.mockResolvedValue([
      {
        prediction_id: 'pred_1',
        request_id: 'req_1',
        ticker: 'AAPL',
        input_timestamp: '2026-09-07T00:00:00Z',
        data_timestamp: '2026-09-07T00:00:00Z',
        model_version: 'm',
        feature_version: 'v0.2',
        strategy_version: 'stg_v0.1',
        prediction: 'UP',
        probabilities: { UP: 0.9, DOWN: 0.05, HOLD: 0.05 },
        confidence: 0.9,
        signal: 'BUY',
        risk_score: 0.85,
        reason_codes: ['MODEL_SIGNAL_BUY'],
        inference_timestamp: '2026-09-07T01:00:00Z',
      },
    ])
    renderAt(<Predictions />)
    await waitFor(() => expect(screen.getByText(/VERY HIGH RISK/i)).toBeInTheDocument())
  })
})

describe('Backtests', () => {
  it('shows the empty state with guidance when no backtests exist (§23)', async () => {
    mockedApi.backtests.mockResolvedValue([])
    renderAt(<Backtests />)
    await waitFor(() => expect(screen.getByText(/no backtests available/i)).toBeInTheDocument())
    expect(screen.getByText(/run the backtest pipeline first/i)).toBeInTheDocument()
  })

  it('renders metrics with net-of-cost labeling (§30.2)', async () => {
    mockedApi.backtests.mockResolvedValue([
      {
        backtest_id: 'bt_1',
        instrument: 'AAPL',
        model_version: 'random_forest_v0.2',
        dataset_version: 'v0.2',
        feature_version: 'v0.2',
        label_version: 'v0.2',
        strategy_version: 'stg_v0.1',
        cost_model_version: 'cost_v0.1',
        backtest_version: 'v0.1',
        evaluation_period: { start: '2026-03-04', end: '2026-08-24' },
        trade_count: 5,
        cumulative_return: -0.075,
        sharpe_ratio: -0.4,
        max_drawdown: -0.11,
        created_at: '2026-09-05T12:00:00Z',
      },
    ])
    mockedApi.backtest.mockResolvedValue({
      backtest_id: 'bt_1',
      backtest_version: 'v0.1',
      instrument: 'AAPL',
      model_version: 'random_forest_v0.2',
      dataset_version: 'v0.2',
      feature_version: 'v0.2',
      label_version: 'v0.2',
      strategy_version: 'stg_v0.1',
      cost_model_version: 'cost_v0.1',
      execution_convention: 'close_to_close',
      evaluation_period: { start: '2026-03-04', end: '2026-08-24' },
      initial_capital: 1.0,
      created_at: '2026-09-05T12:00:00Z',
      financial_metrics: { cumulative_return: -0.075, sharpe_ratio: -0.4, max_drawdown: -0.11, win_rate: null, number_of_trades: 5 },
      prediction_metrics: {},
      config_snapshot: { annualization: 252 },
      equity_curve: [
        { timestamp: '2026-03-04', equity: 1.0, drawdown: 0, daily_return: 0 },
        { timestamp: '2026-03-05', equity: 1.01, drawdown: 0, daily_return: 0.01 },
      ],
      drawdown_curve: [
        { timestamp: '2026-03-04', drawdown: 0 },
        { timestamp: '2026-03-05', drawdown: 0 },
      ],
      trades: [],
      benchmarks: { note: 'persisted values' },
    })
    renderAt(<Backtests />)
    await waitFor(() => expect(screen.getByText(/performance \(net of costs\)/i)).toBeInTheDocument())
    expect(screen.getByText('Sharpe (rf = 0)')).toBeInTheDocument()
    expect(screen.getByText('bt_1')).toBeInTheDocument()
  })
})

describe('Models', () => {
  it('lists model versions with validation metrics (§19)', async () => {
    mockedApi.models.mockResolvedValue([
      {
        model_version: 'random_forest_v0.2',
        model_type: 'ensemble',
        status: 'active',
        dataset_version: 'v0.2',
        feature_version: 'v0.2',
        label_version: 'v0.2',
        training_timestamp: '2026-09-05T11:00:00Z',
        feature_count: 52,
        metrics: { accuracy: 0.342, f1_macro: 0.26 },
      },
    ])
    renderAt(<Models />)
    await waitFor(() => expect(screen.getByText('random_forest_v0.2')).toBeInTheDocument())
    expect(screen.getByText('ACTIVE')).toBeInTheDocument()
    expect(screen.getByText('0.3420')).toBeInTheDocument()
  })
})

describe('Datasets', () => {
  it('lists dataset identity + quality (§20)', async () => {
    mockedApi.datasets.mockResolvedValue([
      {
        dataset_version: 'v0.2',
        source_versions: { AAPL: '1b243a1b901d' },
        date_range: { start: '2023-01-02', end: '2026-08-24' },
        instruments: ['AAPL'],
        interval: '1d',
        row_count: 795,
        feature_count: 52,
        feature_version: 'v0.2',
        label_version: 'v0.2',
        quality_score: 95.98,
        quality_rating: 'excellent',
        generated_at: '2026-09-05T10:00:00Z',
      },
    ])
    renderAt(<Datasets />)
    await waitFor(() => expect(screen.getAllByText('v0.2').length).toBeGreaterThan(0))
    expect(screen.getByText(/EXCELLENT/i)).toBeInTheDocument()
    expect(screen.getByText('795')).toBeInTheDocument()
  })
})

describe('SystemHealth', () => {
  it('renders readiness checks with text status (§21)', async () => {
    mockedApi.ready.mockResolvedValue({
      status: 'ready',
      checks: { config_loaded: true, model_available: true, default_model_loaded: true, audit_dir_writable: true },
    })
    mockedApi.systemStatus.mockResolvedValue({
      latest_dataset: { dataset_version: 'v0.2', generated_at: '2026-09-05T10:00:00Z', quality_score: 95.98 },
      latest_model: { model_version: 'random_forest_v0.2', training_timestamp: '2026-09-05T11:00:00Z' },
      latest_backtest: 'bt_1',
      latest_experiment: 'exp_1',
      counts: { datasets: 2, models: 4, experiments: 6, backtests: 3 },
      generated_at: '2026-09-07T00:00:00Z',
    })
    renderAt(<SystemHealth />)
    await waitFor(() => expect(screen.getByText('CONFIG LOADED')).toBeInTheDocument())
    expect(screen.getByText('MODEL AVAILABLE')).toBeInTheDocument()
    expect(screen.getByText('Latest dataset')).toBeInTheDocument()
  })

  it('shows an error state when the health API is unreachable (§24)', async () => {
    mockedApi.ready.mockResolvedValue({ status: 'ready', checks: {} })
    mockedApi.systemStatus.mockResolvedValue({
      latest_dataset: null,
      latest_model: null,
      latest_backtest: null,
      latest_experiment: null,
      counts: { datasets: 0, models: 0, experiments: 0, backtests: 0 },
      generated_at: '2026-09-07T00:00:00Z',
    })
    mockedApi.health.mockRejectedValue(
      new (await import('../api/client')).ApiError(0, 'SERVICE_UNREACHABLE', 'Cannot reach the Finance AI API.', 'req_9'),
    )
    renderAt(<SystemHealth />)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })
})
