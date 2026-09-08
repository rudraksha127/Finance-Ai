/**
 * Contract types mirroring the backend OpenAPI schemas
 * (INFERENCE_API_BLUEPRINT §7/§8/§16 + dashboard read endpoints §29.3).
 * The backend is authoritative; the UI never recomputes these values (§29.1).
 */

export type Signal = 'BUY' | 'SELL' | 'NO_TRADE'
export type Label = 'UP' | 'DOWN' | 'HOLD'
export type Mode = 'research' | 'paper'

export interface MarketContext {
  current_price: number
  recent_volatility?: number | null
  data_timestamp: string
}

export interface PredictionRequest {
  request_id?: string
  ticker: string
  timestamp: string
  interval: string
  feature_set_version: string
  model_version?: string | null
  features: Record<string, number>
  market_context: MarketContext
}

export interface ModelInfoBlock {
  model_version: string
  model_type: string
  feature_version: string
  label_version: string
}

export interface ModelOutput {
  prediction: Label
  probabilities: Record<Label, number>
  confidence: number
  expected_return: number | null
}

export interface DecisionOutput {
  signal: Signal
  confidence: number
  expected_return: number | null
  risk_score: number
  position_size: number | null
  reason_codes: string[]
  strategy_version: string
}

export interface PredictionResponse {
  prediction_id: string
  request_id: string
  status: 'success' | 'no_trade'
  ticker: string
  inference_timestamp: string
  inference_time_ms: number
  model: ModelInfoBlock
  model_output: ModelOutput
  decision_output: DecisionOutput
  features_used: string[]
  audit_written: boolean
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    request_id: string | null
    timestamp: string
  }
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  model_loaded: boolean
  model_version: string | null
  uptime_seconds: number
  mode: Mode
}

export interface ReadyResponse {
  status: 'ready' | 'not_ready'
  checks: Record<string, boolean>
}

export interface VersionResponse {
  api_version: string
  model_version: string | null
  feature_version: string
  label_version: string
  strategy_version: string
  mode: Mode
}

export interface ModelInfoResponse {
  model_version: string
  model_type: string
  status: string
  trained_at: string | null
  feature_version: string
  label_version: string
  dataset_version: string
  feature_count: number
  metrics: Record<string, unknown>
}

export interface DatasetSummary {
  dataset_version: string
  source_versions: Record<string, string>
  date_range: { start: string | null; end: string | null }
  instruments: string[]
  interval: string
  row_count: number
  train_rows?: number
  val_rows?: number
  test_rows?: number
  feature_count: number
  feature_version: string
  label_version: string
  quality_score: number
  quality_rating: string
  generated_at: string
}

export interface DatasetDetail extends DatasetSummary {
  split_row_counts: Record<string, number>
  split_boundaries: Record<string, string>
  target_definition: Record<string, unknown>
}

export interface ModelSummary {
  model_version: string
  model_type: string
  status: string
  dataset_version: string
  feature_version: string
  label_version: string
  training_timestamp: string
  feature_count: number
  metrics: Record<string, unknown>
}

export interface ExperimentSummary {
  experiment_id: string
  model_version: string
  dataset_version: string
  feature_version: string
  label_version: string
  status: string
  created_at: string
  metrics: Record<string, unknown>
  train_rows: number
  validation_rows: number
}

export interface ExperimentDetail extends ExperimentSummary {
  config_version: string
  git_commit: string
  random_seed: number
  train_period: { start: string | null; end: string | null }
  validation_period: { start: string | null; end: string | null }
  rows: { train: number; validation: number; test: number }
  config_snapshot: Record<string, unknown>
  feature_importance: Array<{ feature: string; importance: number; rank: number }>
}

export interface BacktestSummary {
  backtest_id: string
  instrument: string
  model_version: string | null
  dataset_version: string
  feature_version: string
  label_version: string
  strategy_version: string
  cost_model_version: string
  backtest_version: string | null
  evaluation_period: { start: string | null; end: string | null }
  trade_count: number
  cumulative_return: number | null
  sharpe_ratio: number | null
  max_drawdown: number | null
  created_at: string
}

export interface Candle {
  timestamp: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface CandlesResponse {
  ticker: string
  source_file: string
  count: number
  stale: boolean
  candles: Candle[]
}

export interface PredictionAuditRecord {
  prediction_id: string
  request_id: string
  ticker: string
  input_timestamp: string
  data_timestamp: string
  model_version: string
  feature_version: string
  strategy_version: string
  prediction: Label
  probabilities: Record<Label, number>
  confidence: number
  signal: Signal
  risk_score: number
  reason_codes: string[]
  inference_timestamp: string
  latency_ms?: number
}

export interface SystemStatus {
  latest_dataset: { dataset_version: string; generated_at: string; quality_score: number } | null
  latest_model: { model_version: string; training_timestamp: string } | null
  latest_backtest: string | null
  latest_experiment: string | null
  counts: { datasets: number; models: number; experiments: number; backtests: number }
  generated_at: string
}

export interface BacktestDetail {
  backtest_id: string
  backtest_version: string | null
  instrument: string
  model_version: string | null
  dataset_version: string
  feature_version: string
  label_version: string
  strategy_version: string
  cost_model_version: string
  execution_convention: string
  evaluation_period: { start: string | null; end: string | null }
  initial_capital: number | null
  created_at: string
  financial_metrics: Record<string, number | null>
  prediction_metrics: Record<string, unknown>
  config_snapshot: Record<string, unknown>
  equity_curve: Array<{ timestamp: string; equity: number; drawdown: number; daily_return: number }>
  drawdown_curve: Array<{ timestamp: string; drawdown: number }>
  trades: Array<Record<string, unknown>>
  benchmarks: Record<string, unknown>
}
