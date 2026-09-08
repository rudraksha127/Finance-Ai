"""Backtest engine orchestrator (M08).

Chains the eight blueprint modules (EVALUATION_BACKTESTING_BLUEPRINT
section 30): Data Adapter -> Prediction Adapter -> Signal Generator ->
Execution Simulator -> Position Manager -> P&L Calculator -> Metrics
Engine -> Report Generator. The static engine evaluates one frozen
evaluation period; the walk-forward driver (``walkforward.py``) reuses
:meth:`BacktestEngine.run_static` per fold.
"""

from __future__ import annotations

import platform
import time
import uuid
from dataclasses import dataclass
from dataclasses import replace as _replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.backtest.benchmarks import benchmark_metrics
from src.backtest.data import BacktestData, load_backtest_data
from src.backtest.errors import EmptyTestSetError
from src.backtest.execution import Trade, simulate
from src.backtest.metrics import financial_metrics, prediction_metrics
from src.backtest.prediction import load_model_predictions
from src.backtest.report import write_backtest_outputs
from src.backtest.scenarios import cost_scenarios, write_scenario_outputs
from src.backtest.signals import generate_signals
from src.config.loader import AppConfig, BacktestCostConfig
from src.logging.logger import get_logger

logger = get_logger("backtest.engine")


@dataclass(frozen=True)
class BacktestResult:
    """Machine-readable outcome of one backtest run."""

    backtest_id: str
    ticker: str
    model_version: str | None
    strategy_version: str
    cost_model_version: str
    dataset_version: str
    feature_version: str
    label_version: str
    predictions: pd.DataFrame
    trades: tuple[Trade, ...]
    equity: pd.DataFrame
    financial_metrics: dict[str, Any]
    prediction_metrics: dict[str, Any]
    benchmarks: dict[str, dict[str, Any]]
    cost_adjusted: dict[str, Any]
    experiment_record: dict[str, Any]
    output_dir: Path
    paths: dict[str, Path]


@dataclass(frozen=True)
class ScenarioStudyResult:
    """Outcome of a cost/slippage scenario study (one row per scenario)."""

    study_id: str
    ticker: str
    model_version: str
    dataset_version: str
    feature_version: str
    label_version: str
    base_cost_model_version: str
    rows: tuple[dict, ...]
    output_dir: Path
    paths: dict[str, Path]


class BacktestEngine:
    """Deterministic, fail-loud backtesting of the frozen MVP strategy."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Static evaluation-period backtest
    # ------------------------------------------------------------------
    def run(
        self,
        *,
        ticker: str,
        model_version: str,
        dataset_version: str | None = None,
        feature_version: str | None = None,
        label_version: str | None = None,
        backtest_id: str | None = None,
        split: str = "test",
    ) -> BacktestResult:
        """Backtest one trained model over one frozen evaluation period."""
        dataset_version = dataset_version or self.config.dataset_builder.dataset_version
        feature_version = feature_version or self.config.features.version
        label_version = label_version or self.config.dataset.label_version
        started = time.perf_counter()
        data = load_backtest_data(
            self.config.data.processed_dir,
            self.config.data.interim_dir,
            ticker=ticker,
            dataset_version=dataset_version,
            feature_version=feature_version,
            label_version=label_version,
            split=split,
        )
        predictions = load_model_predictions(
            data,
            model_version=model_version,
            model_dir=self.config.model.artifact_dir,
        )
        result = self.run_static(
            data,
            predictions.frame,
            model_version=model_version,
            backtest_id=backtest_id,
        )
        logger.info(
            "backtest_completed",
            backtest_id=result.backtest_id,
            ticker=ticker,
            model_version=model_version,
            dataset_version=dataset_version,
            trades=len(result.trades),
            cumulative_return=result.financial_metrics["cumulative_return"],
            sharpe=result.financial_metrics["sharpe_ratio"],
            duration_seconds=round(time.perf_counter() - started, 4),
            status="COMPLETED",
        )
        return result

    # ------------------------------------------------------------------
    # Cost/slippage scenario study (research; static evaluation period)
    # ------------------------------------------------------------------
    def run_scenarios(
        self,
        *,
        ticker: str,
        model_version: str,
        dataset_version: str | None = None,
        feature_version: str | None = None,
        label_version: str | None = None,
        backtest_id: str | None = None,
        split: str = "test",
    ) -> ScenarioStudyResult:
        """Run BASE/LOW_COST/HIGH_COST/STRESSED_SLIPPAGE on one evaluation period.

        Data and predictions are loaded once; each scenario re-runs the exact
        static pipeline with a frozen cost override so results differ only in
        the cost/slippage assumptions (blueprint sensitivity sections).
        Scenario configurations are fixed research definitions, never tuned
        against the evaluation data.
        """
        dataset_version = dataset_version or self.config.dataset_builder.dataset_version
        feature_version = feature_version or self.config.features.version
        label_version = label_version or self.config.dataset.label_version
        base = self.config.backtest
        data = load_backtest_data(
            self.config.data.processed_dir,
            self.config.data.interim_dir,
            ticker=ticker,
            dataset_version=dataset_version,
            feature_version=feature_version,
            label_version=label_version,
            split=split,
        )
        predictions = load_model_predictions(
            data,
            model_version=model_version,
            model_dir=self.config.model.artifact_dir,
        )
        scenarios = cost_scenarios(base.costs)
        study_id = backtest_id or (
            f"bt_scen_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
        )
        rows: list[dict] = []
        for scenario in scenarios:
            scenario_costs = BacktestCostConfig(
                brokerage_bps=scenario.brokerage_bps,
                spread_bps=scenario.spread_bps,
                slippage_bps=scenario.slippage_bps,
            )
            scenario_backtest = _replace(
                base,
                costs=scenario_costs,
                cost_model_version=f"{base.cost_model_version}__{scenario.name.lower()}",
            )
            scenario_config = _replace(self.config, backtest=scenario_backtest)
            result = BacktestEngine(scenario_config).run_static(
                data,
                predictions.frame,
                model_version=model_version,
                backtest_id=f"{study_id}__{scenario.name}",
            )
            metrics = result.financial_metrics
            rows.append(
                {
                    "scenario": scenario.name,
                    "role": scenario.role,
                    "cost_model_version": scenario_backtest.cost_model_version,
                    "per_side_bps": scenario.per_side_bps,
                    "round_trip_bps": scenario.round_trip_bps,
                    "number_of_trades": metrics["number_of_trades"],
                    "win_rate": metrics["win_rate"],
                    "cumulative_return": metrics["cumulative_return"],
                    "annualized_return": metrics["annualized_return"],
                    "sharpe_ratio": metrics["sharpe_ratio"],
                    "max_drawdown": metrics["max_drawdown"],
                    "total_gross_pnl": metrics["total_gross_pnl"],
                    "total_costs": metrics["total_costs"],
                    "total_net_pnl": metrics["total_net_pnl"],
                    "gross_cumulative_return": result.cost_adjusted["gross_cumulative_return"],
                    "run_output_dir": str(result.output_dir / result.backtest_id),
                }
            )
        output_root = (
            base.output_dir if base.output_dir.is_absolute() else Path.cwd() / base.output_dir
        )
        study_dir = output_root / study_id
        study_context = {
            "backtest_id": study_id,
            "ticker": ticker,
            "model_version": model_version,
            "dataset_version": data.dataset_version,
            "feature_version": data.feature_version,
            "label_version": data.label_version,
            "base_cost_model_version": base.cost_model_version,
            "base_costs": {
                "brokerage_bps": base.costs.brokerage_bps,
                "spread_bps": base.costs.spread_bps,
                "slippage_bps": base.costs.slippage_bps,
                "per_side_bps": base.costs.per_side_bps,
                "round_trip_bps": base.costs.round_trip_bps,
            },
            "split": split,
            "evaluation_period": data.test_period,
        }
        paths = write_scenario_outputs(
            study_dir,
            summary=rows,
            definitions=[scenario.to_dict() for scenario in scenarios],
            study_context=study_context,
        )
        logger.info(
            "scenario_study_completed",
            study_id=study_id,
            ticker=ticker,
            model_version=model_version,
            scenarios=len(rows),
            status="COMPLETED",
        )
        return ScenarioStudyResult(
            study_id=study_id,
            ticker=ticker,
            model_version=model_version,
            dataset_version=data.dataset_version,
            feature_version=data.feature_version,
            label_version=data.label_version,
            base_cost_model_version=base.cost_model_version,
            rows=tuple(rows),
            output_dir=study_dir,
            paths=paths,
        )

    # ------------------------------------------------------------------
    # Shared static pipeline (also used per walk-forward fold)
    # ------------------------------------------------------------------
    def run_static(
        self,
        data: BacktestData,
        frame: pd.DataFrame,
        *,
        model_version: str | None,
        backtest_id: str | None = None,
    ) -> BacktestResult:
        """Run signals -> simulation -> metrics -> benchmarks -> outputs."""
        backtest = self.config.backtest
        if frame.empty:
            raise EmptyTestSetError(
                "evaluation period contains no rows",
                context={"ticker": data.ticker},
            )
        frame = frame.copy()
        frame["signal"] = generate_signals(
            frame,
            buy_threshold=backtest.signal.buy_threshold,
            sell_threshold=backtest.signal.sell_threshold,
        )
        simulation = simulate(
            frame,
            ticker=data.ticker,
            signal_version=backtest.strategy_version,
            quantity=backtest.position.quantity,
            max_holding_period=backtest.position.max_holding_period,
            cost_per_side_bps=backtest.costs.per_side_bps,
        )

        financial = financial_metrics(
            simulation.equity["daily_return"].to_numpy(dtype=float),
            simulation.equity["equity"].to_numpy(dtype=float),
            simulation.trades,
            periods_per_year=backtest.annualization,
            risk_free_rate=backtest.risk_free_rate,
        )
        financial["cost_decomposition"] = {
            "per_side_bps": backtest.costs.per_side_bps,
            "round_trip_bps": backtest.costs.round_trip_bps,
            "brokerage_bps": backtest.costs.brokerage_bps,
            "spread_bps": backtest.costs.spread_bps,
            "slippage_bps": backtest.costs.slippage_bps,
            "cost_model_version": backtest.cost_model_version,
        }

        pred_metrics = prediction_metrics(frame)

        gross_daily = (
            simulation.equity["daily_return"].to_numpy(dtype=float) + simulation.cost_charges
        )
        gross_equity = np.cumprod(1.0 + gross_daily)
        cost_adjusted = {
            "cost_model_version": backtest.cost_model_version,
            "per_side_bps": backtest.costs.per_side_bps,
            "round_trip_bps": backtest.costs.round_trip_bps,
            "gross_cumulative_return": round(float(gross_equity[-1] - 1.0), 6),
            "net_cumulative_return": round(float(simulation.equity["equity"].iloc[-1] - 1.0), 6),
            "total_costs_currency": financial["total_costs"],
            "note": "net return is the primary metric; gross shown for reference only "
            "(blueprint section 11.3)",
        }

        closes = frame["close"].to_numpy(dtype=float)
        benches = benchmark_metrics(
            closes,
            n_days=len(frame),
            cost_per_side_bps=backtest.costs.per_side_bps,
            periods_per_year=backtest.annualization,
            risk_free_rate=backtest.risk_free_rate,
        )

        backtest_id = backtest_id or (
            f"bt_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
        )
        experiment_record = self._experiment_record(
            backtest_id=backtest_id,
            data=data,
            model_version=model_version,
            simulation=simulation,
            financial=financial,
        )
        config_snapshot = self._config_snapshot()

        report_markdown = self._report(
            backtest_id=backtest_id,
            data=data,
            model_version=model_version,
            simulation=simulation,
            financial=financial,
            pred_metrics=pred_metrics,
            benchmarks=benches,
            cost_adjusted=cost_adjusted,
        )

        output_dir = (
            backtest.output_dir
            if backtest.output_dir.is_absolute()
            else Path.cwd() / backtest.output_dir
        )
        paths = write_backtest_outputs(
            output_dir,
            backtest_id=backtest_id,
            predictions=self._predictions_output(frame),
            trades=_trades_dataframe(simulation.trades),
            equity=simulation.equity,
            financial=financial,
            prediction_metrics=pred_metrics,
            cost_adjusted=cost_adjusted,
            experiment_record=experiment_record,
            config_snapshot=config_snapshot,
            report_markdown=report_markdown,
        )

        return BacktestResult(
            backtest_id=backtest_id,
            ticker=data.ticker,
            model_version=model_version,
            strategy_version=backtest.strategy_version,
            cost_model_version=backtest.cost_model_version,
            dataset_version=data.dataset_version,
            feature_version=data.feature_version,
            label_version=data.label_version,
            predictions=frame,
            trades=simulation.trades,
            equity=simulation.equity,
            financial_metrics=financial,
            prediction_metrics=pred_metrics,
            benchmarks=benches,
            cost_adjusted=cost_adjusted,
            experiment_record=experiment_record,
            output_dir=output_dir,
            paths=paths,
        )

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------
    def _predictions_output(self, frame: pd.DataFrame) -> pd.DataFrame:
        columns = [
            "ticker",
            "timestamp",
            "label",
            "future_return",
            "target_timestamp",
            "prediction",
            "probability_UP",
            "probability_DOWN",
            "probability_HOLD",
            "signal",
        ]
        return frame[[column for column in columns if column in frame.columns]].copy()

    def _experiment_record(
        self,
        *,
        backtest_id: str,
        data: BacktestData,
        model_version: str | None,
        simulation,
        financial: dict[str, Any],
    ) -> dict[str, Any]:
        backtest = self.config.backtest
        return {
            "backtest_id": backtest_id,
            "backtest_version": backtest.backtest_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "instrument": data.ticker,
            "model_version": model_version,
            "dataset_version": data.dataset_version,
            "feature_version": data.feature_version,
            "label_version": data.label_version,
            "strategy_version": backtest.strategy_version,
            "cost_model_version": backtest.cost_model_version,
            "execution_convention": backtest.execution_convention,
            "initial_capital": backtest.initial_capital,
            "evaluation_period": data.test_period,
            "price_source": str(data.price_source),
            "source_checksum": data.source_checksum,
            "walk_forward": {"enabled": False, "fold": None},
            "purge": {"enabled": False, "rows_removed": 0},
            "embargo_rows": 0,
            "trade_count": len(simulation.trades),
            "financial_metrics": financial,
            "code_version": "unversioned",
            "environment": {
                "python": platform.python_version(),
                "pandas": pd.__version__,
                "numpy": np.__version__,
            },
        }

    def _config_snapshot(self) -> dict[str, Any]:
        backtest = self.config.backtest
        return {
            "backtest_version": backtest.backtest_version,
            "strategy_version": backtest.strategy_version,
            "cost_model_version": backtest.cost_model_version,
            "execution_convention": backtest.execution_convention,
            "initial_capital": backtest.initial_capital,
            "signal": {
                "buy_threshold": backtest.signal.buy_threshold,
                "sell_threshold": backtest.signal.sell_threshold,
            },
            "position": {
                "quantity": backtest.position.quantity,
                "max_holding_period": backtest.position.max_holding_period,
            },
            "costs": {
                "brokerage_bps": backtest.costs.brokerage_bps,
                "spread_bps": backtest.costs.spread_bps,
                "slippage_bps": backtest.costs.slippage_bps,
                "per_side_bps": backtest.costs.per_side_bps,
                "round_trip_bps": backtest.costs.round_trip_bps,
            },
            "annualization": backtest.annualization,
            "risk_free_rate": backtest.risk_free_rate,
        }

    def _report(
        self,
        *,
        backtest_id: str,
        data: BacktestData,
        model_version: str | None,
        simulation,
        financial: dict[str, Any],
        pred_metrics: dict[str, Any],
        benchmarks: dict[str, dict[str, Any]],
        cost_adjusted: dict[str, Any],
    ) -> str:
        backtest = self.config.backtest
        rows = [
            f"# Backtest report `{backtest_id}`",
            "",
            "> Research artifact only. Not financial advice; not a live trading system.",
            "",
            "## 1. Experiment identity",
            f"- Backtest ID: `{backtest_id}`",
            f"- Instrument: `{data.ticker}`",
            f"- Strategy version: `{backtest.strategy_version}`",
            f"- Cost model: `{backtest.cost_model_version}`",
            "",
            "## 2. Model",
            f"- Model version: `{model_version}`",
            "",
            "## 3. Dataset",
            f"- Dataset: `{data.dataset_version}` | Features: `{data.feature_version}` | Labels: `{data.label_version}`",
            f"- Price source: `{data.price_source.name}` (checksum `{data.source_checksum}`)",
            "",
            "## 4. Evaluation period",
            f"- Start: `{data.test_period['start']}` | End: `{data.test_period['end']}`",
            "- Execution convention: close-to-close (MVP simplification)",
            "",
            "## 5. Strategy rules",
            f"- BUY when P(UP) >= {backtest.signal.buy_threshold}; SELL (exit) when P(DOWN) >= {backtest.signal.sell_threshold}",
            f"- Position: long-only, quantity {backtest.position.quantity}, max holding {backtest.position.max_holding_period} rows",
            "- Exit on SELL, max holding, or end of period. No stop-loss/take-profit (MVP).",
            "",
            "## 6. Cost assumptions",
            f"- Per side: {backtest.costs.per_side_bps} bps (brokerage {backtest.costs.brokerage_bps} + spread {backtest.costs.spread_bps} + slippage {backtest.costs.slippage_bps})",
            f"- Round trip: {backtest.costs.round_trip_bps} bps",
            "",
            "## 7. Prediction metrics",
            "```json",
            _json(pred_metrics),
            "```",
            "",
            "## 8. Trading metrics",
            "```json",
            _json(
                {
                    k: financial[k]
                    for k in (
                        "number_of_trades",
                        "win_rate",
                        "average_win",
                        "average_loss",
                        "profit_factor",
                        "expectancy",
                        "turnover",
                        "avg_holding_period_days",
                    )
                }
            ),
            "```",
            "",
            "## 9. Risk metrics",
            "```json",
            _json(
                {
                    k: financial[k]
                    for k in (
                        "cumulative_return",
                        "annualized_return",
                        "annualized_volatility",
                        "sharpe_ratio",
                        "sortino_ratio",
                        "max_drawdown",
                        "calmar_ratio",
                    )
                }
            ),
            "```",
            "",
            "## 10. Benchmark comparison",
            "```json",
            _json(
                {
                    "strategy": financial,
                    "buy_and_hold": benchmarks["buy_and_hold"],
                    "zero_trade": benchmarks["zero_trade"],
                }
            ),
            "```",
            "",
            "## 11. Cost-adjusted results",
            "```json",
            _json(cost_adjusted),
            "```",
            "",
            "## 12. Limitations",
            "- Close-to-close execution is a simplification; real execution would use next-day open.",
            "- Long-only, single instrument, fixed quantity; no stop-loss/take-profit.",
            "- Simulated execution/costs may differ from real execution; backtests do not guarantee future performance.",
            "- ML metrics (section 7) do not imply trading profitability.",
            "",
            "## 13. Conclusion",
            "See the machine-readable outputs in this directory for the full result set.",
            "No profitability claim is made from this research artifact.",
            "",
        ]
        return "\n".join(rows)


def _json(payload: Any) -> str:
    import json

    return json.dumps(payload, indent=2, sort_keys=True, default=str)


def _trades_dataframe(trades: tuple[Trade, ...]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame(
            columns=[
                "trade_id",
                "instrument",
                "signal_timestamp",
                "execution_timestamp",
                "signal",
                "probability",
                "entry_price",
                "exit_timestamp",
                "exit_price",
                "quantity",
                "gross_pnl",
                "costs",
                "net_pnl",
                "holding_duration",
                "reason",
                "signal_version",
                "trade_number",
            ]
        )
    return pd.DataFrame([trade.__dict__ for trade in trades])
