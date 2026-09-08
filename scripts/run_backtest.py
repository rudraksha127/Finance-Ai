"""Developer CLI for the evaluation & backtesting engine (M08).

Static backtest of a trained baseline over a frozen evaluation period::

    python -m scripts.run_backtest --ticker AAPL --model-version logistic_regression_v0.1

Expanding-window walk-forward (trains a fresh baseline per fold)::

    python -m scripts.run_backtest --ticker AAPL --walk-forward --model random_forest
"""

from __future__ import annotations

import argparse
import json
import sys

from src.backtest.engine import BacktestEngine
from src.backtest.errors import BacktestError
from src.backtest.walkforward import WalkForwardRunner
from src.config.loader import load_config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backtest a baseline model over a frozen period (static) "
        "or expanding-window walk-forward folds.",
    )
    parser.add_argument("--ticker", required=True, help="Canonical ticker, e.g. AAPL")
    parser.add_argument(
        "--dataset-version", default=None, help="Dataset snapshot (default: config)"
    )
    parser.add_argument("--feature-version", default=None, help="Feature-set version")
    parser.add_argument("--label-version", default=None, help="Label-set version")
    parser.add_argument(
        "--model-version",
        default=None,
        help="Trained model artifact version (static mode)",
    )
    parser.add_argument(
        "--split",
        default="test",
        choices=("test", "val", "train"),
        help="Dataset split to evaluate (default: test)",
    )
    parser.add_argument(
        "--walk-forward",
        action="store_true",
        help="Run expanding-window walk-forward instead of a static backtest",
    )
    parser.add_argument(
        "--scenarios",
        action="store_true",
        help="Run the built-in cost/slippage scenario study "
        "(BASE/LOW_COST/HIGH_COST/STRESSED_SLIPPAGE; static, requires --model-version)",
    )
    parser.add_argument(
        "--model",
        default="logistic_regression",
        choices=("logistic_regression", "random_forest", "lightgbm", "xgboost"),
        help="Model trained per walk-forward fold",
    )
    parser.add_argument("--train-window", type=int, default=None)
    parser.add_argument("--test-window", type=int, default=None)
    parser.add_argument("--step", type=int, default=None)
    parser.add_argument("--no-purge", action="store_true", help="Disable label-overlap purging")
    parser.add_argument("--backtest-id", default=None, help="Fixed backtest id (reproducibility)")
    parser.add_argument(
        "--env",
        default=None,
        choices=("development", "production", "testing"),
        help="Configuration environment (default: ENVIRONMENT variable, then development)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = load_config(environment=args.env)
        if args.scenarios:
            if not args.model_version:
                print(
                    "scenario study requires --model-version "
                    "(or use --walk-forward to train per fold)",
                    file=sys.stderr,
                )
                return 2
            study = BacktestEngine(config).run_scenarios(
                ticker=args.ticker,
                model_version=args.model_version,
                dataset_version=args.dataset_version,
                feature_version=args.feature_version,
                label_version=args.label_version,
                backtest_id=args.backtest_id,
                split=args.split,
            )
            summary = {
                "backtest_id": study.study_id,
                "mode": "scenarios",
                "ticker": study.ticker,
                "model_version": study.model_version,
                "base_cost_model_version": study.base_cost_model_version,
                "scenario_count": len(study.rows),
                "scenarios": list(study.rows),
                "output_dir": str(study.output_dir),
            }
        elif args.walk_forward:
            result = WalkForwardRunner(config).run(
                ticker=args.ticker,
                model_name=args.model,
                dataset_version=args.dataset_version,
                feature_version=args.feature_version,
                label_version=args.label_version,
                train_window=args.train_window,
                test_window=args.test_window,
                step=args.step,
                purge=not args.no_purge,
                backtest_id=args.backtest_id,
            )
            summary = {
                "backtest_id": result.backtest_id,
                "mode": "walkforward",
                "ticker": result.ticker,
                "model": result.model_name,
                "folds": len(result.folds),
                "trades": sum(len(r.trades) for r in result.folds),
                "cumulative_return": result.overall_financial_metrics["cumulative_return"],
                "sharpe_ratio": result.overall_financial_metrics["sharpe_ratio"],
                "max_drawdown": result.overall_financial_metrics["max_drawdown"],
                "output_dir": str(result.output_dir),
            }
        else:
            if not args.model_version:
                print(
                    "static backtest requires --model-version "
                    "(or use --walk-forward to train per fold)",
                    file=sys.stderr,
                )
                return 2
            result = BacktestEngine(config).run(
                ticker=args.ticker,
                model_version=args.model_version,
                dataset_version=args.dataset_version,
                feature_version=args.feature_version,
                label_version=args.label_version,
                backtest_id=args.backtest_id,
                split=args.split,
            )
            summary = {
                "backtest_id": result.backtest_id,
                "mode": "static",
                "ticker": result.ticker,
                "model_version": result.model_version,
                "trades": len(result.trades),
                "cumulative_return": result.financial_metrics["cumulative_return"],
                "sharpe_ratio": result.financial_metrics["sharpe_ratio"],
                "max_drawdown": result.financial_metrics["max_drawdown"],
                "benchmark_buy_and_hold": result.benchmarks["buy_and_hold"]["cumulative_return"],
                "output_dir": str(result.output_dir),
            }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    except (BacktestError, ValueError, OSError) as error:
        print(json.dumps({"error": str(error), "category": type(error).__name__}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
