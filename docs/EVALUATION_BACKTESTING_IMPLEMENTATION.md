# EVALUATION & BACKTESTING ENGINE — IMPLEMENTATION (Milestone 08)

> **Status:** Implemented
> **Date:** 2026-09-05
> **Architecture source:** `docs/EVALUATION_BACKTESTING_BLUEPRINT.md` (all
> sections), `docs/RISK_DECISION_ENGINE_BLUEPRINT.md` (signal thresholds,
> ADR-0019), `docs/BASELINE_MODEL_BLUEPRINT.md` (model artifacts, M07)
> **Parent milestone:** 08 — Evaluation & Walk-Forward Backtesting

This document records the implemented evaluation + backtesting engine for
the file-based MVP (ADR-0005). It is the implementation companion to
`EVALUATION_BACKTESTING_BLUEPRINT.md`; the architecture was followed and
only a few ambiguous points were pinned down (see "Clarifications").

---

## 1. Objective

Implement the engine that answers *"does the trained model have genuine
out-of-sample predictive value under realistic market assumptions?"* with
five separated layers (blueprint section 2): data quality, prediction
quality, signal quality, strategy/backtest performance, robustness
(walk-forward). A good classification score is **not** treated as trading
profitability — ML metrics and financial metrics are kept separate and
both are reported.

## 2. Module map (blueprint section 30)

| Module | File | Responsibility |
|--------|------|----------------|
| Errors | `src/backtest/errors.py` | `BacktestError` taxonomy (data quality, empty test, execution, metrics, report, walk-forward) |
| Data Adapter | `src/backtest/data.py` | Loads a validated dataset split (or full history) and attaches close prices from the cleaned interim tier matched by the dataset's recorded `source_versions` checksum |
| Prediction Adapter | `src/backtest/prediction.py` | Loads a versioned M07 model artifact (`model.joblib` + optional `scaler.joblib` + `metadata.json`), verifies dataset/feature/label versions match, generates probabilities |
| Signal Generator | `src/backtest/signals.py` | Probabilities → BUY / SELL / NO_TRADE (thresholds from config); validation-only threshold-sensitivity research helper |
| Execution Simulator + Position Manager + P&L | `src/backtest/execution.py` | Close-to-close long-only simulation, max-holding enforcement, per-side costs, trade ledger, daily equity construction |
| Metrics Engine | `src/backtest/metrics.py` | All blueprint §15 financial metrics + rolling curves + prediction metrics (reuses `src/model/metrics.py`) |
| Benchmarks | `src/backtest/benchmarks.py` | Buy-and-hold and zero-trade benchmarks on the same period and cost basis |
| Report Generator | `src/backtest/report.py` | Atomic writes of the blueprint §27 output set |
| Engine | `src/backtest/engine.py` | Orchestrator + shared `run_static` pipeline (also used per walk-forward fold) |
| Walk-Forward | `src/backtest/walkforward.py` | Expanding-window folds (252/21/21 defaults), per-fold training, label-overlap purge |
| CLI | `scripts/run_backtest.py` | `--walk-forward` flag; static mode requires `--model-version` |

## 3. Frozen strategy rules (blueprint §§10–14)

- **Position model:** LONG/FLAT only; fixed quantity 1 unit; one position
  at a time, no pyramiding.
- **Signal rules:** `BUY` when `P(UP) >= buy_threshold` (and `P(UP) >=
  P(DOWN)`); `SELL` when `P(DOWN) >= sell_threshold` (and `P(DOWN) >
  P(UP)` — exact ties favor BUY); otherwise `NO_TRADE`. Defaults 0.55 /
  0.55 per ADR-0019.
- **Entry:** signal = BUY while FLAT, at the close of the signal day.
- **Exit:** SELL, or max holding period reached (default 5 trading rows,
  matching the label horizon); max-holding exit takes precedence over a
  same-day SELL. Any position still open at the end of the evaluation
  period is force-closed at the final close so the ledger fully accounts
  for P&L (`reason = end_of_backtest`).
- **Stop-loss / take-profit:** none (MVP simplification, §14.3).
- **Execution convention:** close-to-close (§10.2) — entry `close_T`,
  exit `close_{exit day}`. Documented simplification; next-day-open is a
  future enhancement.

## 4. Cost model (blueprint §§11–12)

- Per side: brokerage 5 bps + spread 5 bps (combined spread+slippage
  bucket) = **10 bps per side, 20 bps round trip** (PRD FR-BT-03).
- Entry cost is charged on the entry day, exit cost on the exit day.
- `cost_model_version = cost_v0.1`; all components configurable in
  `config/default.yaml` → `backtest.costs`.
- Gross vs net: net is the primary metric; `metrics/cost_adjusted.json`
  reports gross cumulative return, net cumulative return, and total
  costs (§11.3).

## 5. Financial metrics (blueprint §15)

Cumulative return, annualized return (252 days), annualized volatility,
Sharpe (risk-free = 0), Sortino, max drawdown, Calmar, win rate,
average win/loss, profit factor, expectancy, turnover, trade count,
average holding period. Trade P&L and win/loss classification are **net
of costs**. Metrics that cannot be computed are `None`/`N/A`, never
fabricated (e.g., Sharpe with zero variance, win rate with zero trades).

## 6. Benchmarks (blueprint §17)

`buy_and_hold` (holds first-close to last-close, pays one round trip of
the same per-side cost) and `zero_trade` (always cash). Metrics computed
by the same engine so comparisons are apples-to-apples.

## 7. Data quality gate (blueprint §3, §31)

Fail-loud checks before and during evaluation: dataset version/schema/
checksum validation (reused from `src/model/loader.py`); price source
must exist and its SHA-256 prefix must match the dataset's
`source_versions` record; prices positive and ascending; every
evaluation row must have an entry close at `T` and an exit close at
`target_timestamp` (no silent skipping); signals validated; no sorting
of unsorted input; no non-finite values anywhere.

## 8. Walk-forward (blueprint §§8–9)

- Expanding window (data-efficient MVP choice), defaults train 252 /
  test 21 / step 21, all configurable.
- Each fold trains a fresh baseline (same config/seed as M07) on the
  train-only rows and backtests the fold test window through the shared
  `run_static` pipeline — one model per fold, never reusing a model that
  saw future data.
- **Purge:** training rows whose `target_timestamp >= fold_test_start`
  are removed (their forward-looking labels overlap the fold test
  period). Purged counts are recorded per fold.
- **Embargo:** 0 for MVP daily data (§9.3); configurable.
- Outputs per fold (`backtests/{id}/fold_NN/…`) plus aggregated
  `fold_predictions.csv`, `fold_trade_ledger.csv`, chained equity curve,
  overall metrics, and fold summaries.

## 9. Outputs (blueprint §27)

`backtests/{backtest_id}/{predictions|trades|curves|metrics|config|metadata|report}/`
with `test_predictions.csv`, `trade_ledger.csv`, `equity_curve.csv`,
`drawdown_curve.csv`, `financial_metrics.json`, `prediction_metrics.json`,
`cost_adjusted.json`, `config_snapshot.json`, `experiment_record.json`,
`backtest_report.md`. The experiment record carries full reproducibility
metadata (§29): all versions, strategy/cost-model versions, execution
convention, evaluation period, price source checksum, code version,
environment. `backtests/` is gitignored.

## 10. Usage

```bash
# Static backtest of a trained model over the dataset TEST split
python -m scripts.run_backtest --ticker AAPL --model-version random_forest_v0.1

# Expanding-window walk-forward (trains a fresh model per fold)
python -m scripts.run_backtest --ticker AAPL --walk-forward --model random_forest

# Built-in cost/slippage scenario study (static)
python -m scripts.run_backtest --ticker AAPL --model-version random_forest_v0.1 --scenarios
```

The scenario study (`src/backtest/scenarios.py`) re-runs the exact static
pipeline under four fixed research definitions layered on the frozen cost
model — `BASE` (active config), `LOW_COST` (0 bps/side), `HIGH_COST`
(50 bps/side), `STRESSED_SLIPPAGE` (active + 50 bps slippage/side). Data
and predictions are loaded once; trade sets are therefore identical across
scenarios and results differ only in cost/slippage assumptions, so the
comparison isolates cost sensitivity. Each scenario gets its own run
artifacts (cost-model version suffixed `__{scenario}`) and the comparison
is written to `backtests/{study_id}/scenario_summary.{json,csv}`.
Scenario assumptions are research constants, never tuned against the
evaluation data (slippage/threshold sensitivity remain research tasks).

## 11. Testing

31 backtest tests + 6 scenario-study tests: signal rules + threshold
sensitivity; hand-derivable trade simulation (costs, exit reasons,
no-pyramiding, force-close, fail-loud conditions); financial-metric math
(drawdown, PF, win-rate, rolling curves); end-to-end engine runs over a
trained model with output and version-mismatch checks; walk-forward fold
math, purge accounting, and a small end-to-end run; scenario definitions
(BASE mirrors config, stress bounds ordered) and study monotonicity
(identical trade sets, costs ordered by per-side bps). **Full suite: 445
passing**, black + ruff clean.

## 12. Clarifications (small, documented; no architecture change)

| Ambiguity | Resolution |
|-----------|------------|
| §13.3 vs §14.2 exit wording | SELL exits immediately; NO_TRADE (HOLD) holds until SELL or max holding. Matches §13.3's detailed table and the "5-day exit after label period regardless" rule. |
| Profit factor basis | Computed on **net** P&L, consistent with §15.2's net-based win/loss classification. |
| Open position at period end | Force-closed at the final close (`end_of_backtest`) so the ledger fully accounts for P&L. |
| Buy-and-hold costs | Pays one round trip of the same per-side cost so benchmark vs strategy comparison shares cost assumptions (§17.3). |
| Scenario cost versions | Scenario runs suffix the frozen cost-model version with `__{scenario}` so artifacts stay identifiable without mutating `cost_v0.1`. |

## 13. Known limitations

- Close-to-close execution is a documented simplification (§10.2).
- Long-only, single instrument, fixed quantity, no stop-loss/take-profit.
- The initial milestone demo ran on a deterministic synthetic fixture;
  a later real-data end-to-end run (AAPL 2023–2026, 892 Yahoo rows,
  features/labels/dataset/models at version v0.2) produced honest weak
  baselines (validation accuracy ≈ 0.32–0.36) and zero-trade static
  backtests at the 0.55 signal threshold — no performance claim is made.
- Statistical significance, regime robustness, and threshold/slippage
  research remain research tasks on real data; the built-in scenario
  study covers cost and slippage stress bounds.

## 14. Files

New: `src/backtest/{__init__,errors,data,prediction,signals,execution,metrics,benchmarks,report,engine,walkforward,scenarios}.py`, `scripts/run_backtest.py`, `tests/{backtest_helpers,test_backtest_signals,test_backtest_execution,test_backtest_metrics,test_backtest_engine,test_backtest_walkforward,test_backtest_scenarios}.py`.
Modified: `config/default.yaml` (`backtest:` section incl. `backtest_version`
and `initial_capital`), `src/config/loader.py` (typed `BacktestConfig`),
`.gitignore` (`backtests/`), `CURRENT_STATE.md`, `DECISIONS.md` (ADR-0028).

### 14.1 Audit additions (2026-09-07)

A specification audit against the Milestone 08 prompt found the engine
blueprint-complete except for two metadata fields: `backtest_version`
(milestone §30/§31) and `initial_capital` (milestone §26). Both are now
first-class `backtest:` configuration keys (validated, defaults `v0.1` /
`1.0`) and are recorded in every static and walk-forward experiment
record and configuration snapshot. The blueprint's own §28.1 trade-ledger
field list remains the authoritative ledger contract and was already
satisfied.
