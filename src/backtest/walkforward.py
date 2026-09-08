"""Expanding-window walk-forward evaluation (M08).

Implements EVALUATION_BACKTESTING_BLUEPRINT section 8 (expanding window,
MVP defaults 252/21/21), section 9 (purge of overlapping-label training
rows; embargo 0 for daily data), and section 30 (each fold trains a
fresh baseline model on train-only data and backtests the fold test
window with the shared decision/execution rules via
``BacktestEngine.run_static``). No fold ever sees future rows: train
rows are strictly before the fold test window and overlapping labels are
purged.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from src.backtest.data import BacktestData, load_backtest_data
from src.backtest.engine import BacktestEngine, BacktestResult
from src.backtest.errors import WalkForwardError
from src.backtest.metrics import financial_metrics, prediction_metrics
from src.backtest.report import write_csv, write_json
from src.config.loader import AppConfig, ModelSpec
from src.logging.logger import get_logger

logger = get_logger("backtest.walkforward")


@dataclass(frozen=True)
class Fold:
    """One expanding-window fold expressed as row index ranges."""

    number: int
    train_start: int
    train_end: int  # exclusive
    test_start: int
    test_end: int  # exclusive
    train_rows_before_purge: int
    train_rows_after_purge: int
    test_rows: int


def generate_folds(
    n_rows: int,
    *,
    train_window: int,
    test_window: int,
    step: int,
    min_train_rows: int = 10,
) -> list[Fold]:
    """Generate expanding-window folds over a chronologically sorted series."""
    if n_rows < train_window + test_window:
        raise WalkForwardError(
            "not enough history for even one walk-forward fold",
            context={
                "n_rows": n_rows,
                "train_window": train_window,
                "test_window": test_window,
                "required": train_window + test_window,
            },
        )
    folds: list[Fold] = []
    number = 1
    train_end = train_window
    while train_end + test_window <= n_rows:
        folds.append(
            Fold(
                number=number,
                train_start=0,
                train_end=train_end,
                test_start=train_end,
                test_end=train_end + test_window,
                train_rows_before_purge=train_end,
                train_rows_after_purge=train_end,
                test_rows=test_window,
            )
        )
        number += 1
        train_end += step
    if not folds:
        raise WalkForwardError("no walk-forward folds could be generated")
    return folds


def _make_estimator(config: AppConfig, model_name: str, spec: ModelSpec):
    params = dict(spec.params)
    params.setdefault("random_state", config.model.random_seed)
    if spec.name == "logistic_regression":
        return LogisticRegression(**params)
    if spec.name == "random_forest":
        params.setdefault("n_jobs", config.model.n_jobs)
        return RandomForestClassifier(**params)
    if spec.name == "lightgbm":
        from lightgbm import LGBMClassifier

        params.setdefault("n_jobs", config.model.n_jobs)
        params.setdefault("verbose", -1)
        return LGBMClassifier(**params)
    if spec.name == "xgboost":
        from src.model.wrappers import XGBoostClassifierWrapper

        params.setdefault("n_jobs", config.model.n_jobs)
        return XGBoostClassifierWrapper(**params)
    raise WalkForwardError(f"unsupported model {spec.name!r}")


def _model_spec(config: AppConfig, model_name: str) -> ModelSpec:
    for spec in config.model.models:
        if spec.name == model_name:
            return spec
    raise WalkForwardError(f"model {model_name!r} is not configured")


@dataclass(frozen=True)
class WalkForwardResult:
    """Aggregated walk-forward outcome plus per-fold backtests."""

    backtest_id: str
    ticker: str
    model_name: str
    folds: list[BacktestResult]
    overall_equity: pd.DataFrame
    overall_financial_metrics: dict[str, Any]
    overall_prediction_metrics: dict[str, Any]
    fold_summaries: list[dict[str, Any]]
    output_dir: Path
    paths: dict[str, Path]


class WalkForwardRunner:
    """Train-per-fold and evaluate the frozen strategy across folds."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.engine = BacktestEngine(config)

    def run(
        self,
        *,
        ticker: str,
        model_name: str = "logistic_regression",
        dataset_version: str | None = None,
        feature_version: str | None = None,
        label_version: str | None = None,
        train_window: int | None = None,
        test_window: int | None = None,
        step: int | None = None,
        purge: bool | None = None,
        embargo_rows: int | None = None,
        backtest_id: str | None = None,
    ) -> WalkForwardResult:
        dataset_version = dataset_version or self.config.dataset_builder.dataset_version
        feature_version = feature_version or self.config.features.version
        label_version = label_version or self.config.dataset.label_version
        wf = self.config.backtest.walkforward
        train_window = train_window or wf.train_window
        test_window = test_window or wf.test_window
        step = step or wf.step
        purge = wf.purge if purge is None else purge
        embargo_rows = wf.embargo_rows if embargo_rows is None else embargo_rows

        data = load_backtest_data(
            self.config.data.processed_dir,
            self.config.data.interim_dir,
            ticker=ticker,
            dataset_version=dataset_version,
            feature_version=feature_version,
            label_version=label_version,
            split=None,
        )
        history = data.rows.reset_index(drop=True)
        folds = generate_folds(
            len(history),
            train_window=train_window,
            test_window=test_window,
            step=step,
        )
        spec = _model_spec(self.config, model_name)

        fold_results: list[BacktestResult] = []
        fold_summaries: list[dict[str, Any]] = []
        for fold in folds:
            result, purged = self._run_fold(
                data=data,
                history=history,
                fold=fold,
                model_name=model_name,
                spec=spec,
                purge=purge,
                embargo_rows=embargo_rows,
                backtest_id=backtest_id,
            )
            fold_results.append(result)
            fold_summaries.append(
                {
                    "fold": fold.number,
                    "train_rows_before_purge": fold.train_rows_before_purge,
                    "train_rows_after_purge": fold.train_rows_before_purge - purged,
                    "purged_rows": purged,
                    "test_rows": fold.test_rows,
                    "trades": len(result.trades),
                    "cumulative_return": result.financial_metrics["cumulative_return"],
                    "sharpe_ratio": result.financial_metrics["sharpe_ratio"],
                    "max_drawdown": result.financial_metrics["max_drawdown"],
                }
            )

        overall = self._aggregate(
            backtest_id=backtest_id or f"bt_wf_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}",
            data=data,
            model_name=model_name,
            fold_results=fold_results,
            fold_summaries=fold_summaries,
            train_window=train_window,
            test_window=test_window,
            step=step,
            purge=purge,
            embargo_rows=embargo_rows,
        )
        logger.info(
            "walkforward_completed",
            backtest_id=overall.backtest_id,
            ticker=ticker,
            folds=len(folds),
            trades=sum(len(r.trades) for r in fold_results),
            cumulative_return=overall.overall_financial_metrics["cumulative_return"],
            sharpe=overall.overall_financial_metrics["sharpe_ratio"],
            status="COMPLETED",
        )
        return overall

    # ------------------------------------------------------------------
    def _run_fold(
        self,
        *,
        data: BacktestData,
        history: pd.DataFrame,
        fold: Fold,
        model_name: str,
        spec: ModelSpec,
        purge: bool,
        embargo_rows: int,
        backtest_id: str | None,
    ) -> tuple[BacktestResult, int]:
        train = history.iloc[fold.train_start : fold.train_end].copy()
        test = history.iloc[fold.test_start : fold.test_end].copy()
        if test.empty:
            raise WalkForwardError(f"fold {fold.number} test window is empty")

        purged = 0
        if purge:
            test_start_ts = pd.to_datetime(test["timestamp"]).min()
            overlap = pd.to_datetime(train["target_timestamp"]) >= test_start_ts
            purged = int(overlap.sum())
            train = train[~overlap].reset_index(drop=True)
        if embargo_rows > 0:
            keep = max(0, len(train) - embargo_rows)
            purged += len(train) - keep
            train = train.iloc[:keep].reset_index(drop=True)
        if len(train) < 10:
            raise WalkForwardError(
                f"fold {fold.number} has insufficient training rows after purge "
                f"({len(train)} < 10)"
            )
        if train["label"].nunique() < 2:
            raise WalkForwardError(f"fold {fold.number} training labels collapse to a single class")

        from src.features.registry import FEATURE_COLUMNS

        X_train = train[list(FEATURE_COLUMNS)].to_numpy(dtype=float)
        y_train = train["label"].to_numpy()
        X_test = test[list(FEATURE_COLUMNS)].to_numpy(dtype=float)
        scaler = StandardScaler() if model_name == "logistic_regression" else None
        train_values = scaler.fit_transform(X_train) if scaler else X_train
        test_values = scaler.transform(X_test) if scaler else X_test
        estimator = _make_estimator(self.config, model_name, spec)
        try:
            estimator.fit(train_values, y_train)
            predictions = estimator.predict(test_values)
            probabilities = estimator.predict_proba(test_values)
        except (ValueError, RuntimeError) as error:
            raise WalkForwardError(f"fold {fold.number} training failed: {error}") from error

        classes = list(getattr(estimator, "classes_", ("UP", "DOWN", "HOLD")))
        frame = test.copy()
        frame["prediction"] = predictions
        for label in ("UP", "DOWN", "HOLD"):
            frame[f"probability_{label}"] = probabilities[:, classes.index(label)]

        fold_data = BacktestData(
            ticker=data.ticker,
            rows=frame,
            prices=data.prices,
            dataset_version=data.dataset_version,
            feature_version=data.feature_version,
            label_version=data.label_version,
            price_source=data.price_source,
            source_checksum=data.source_checksum,
        )
        fold_id = f"{backtest_id or 'bt_wf'}/fold_{fold.number:02d}"
        result = self.engine.run_static(
            fold_data,
            frame,
            model_version=f"walkforward_{model_name}_fold{fold.number}",
            backtest_id=fold_id,
        )
        return result, purged

    # ------------------------------------------------------------------
    def _aggregate(
        self,
        *,
        backtest_id: str,
        data: BacktestData,
        model_name: str,
        fold_results: list[BacktestResult],
        fold_summaries: list[dict[str, Any]],
        train_window: int,
        test_window: int,
        step: int,
        purge: bool,
        embargo_rows: int,
    ) -> WalkForwardResult:
        wf = self.config.backtest
        output_dir = wf.output_dir if wf.output_dir.is_absolute() else Path.cwd() / wf.output_dir
        directory = output_dir / backtest_id

        # Chained overall equity from concatenated fold daily returns.
        fold_returns = [
            result.equity["daily_return"].to_numpy(dtype=float) for result in fold_results
        ]
        overall_returns = np.concatenate(fold_returns) if fold_returns else np.zeros(0)
        overall_equity = np.cumprod(1.0 + overall_returns)
        running_max = np.maximum.accumulate(overall_equity)
        equity_frame = pd.DataFrame(
            {
                "timestamp": [ts for result in fold_results for ts in result.equity["timestamp"]],
                "daily_return": overall_returns,
                "equity": overall_equity,
                "drawdown": overall_equity / running_max - 1.0,
            }
        )
        all_trades = tuple(trade for result in fold_results for trade in result.trades)
        overall_financial = financial_metrics(
            overall_returns,
            overall_equity,
            all_trades,
            periods_per_year=wf.annualization,
            risk_free_rate=wf.risk_free_rate,
        )
        overall_financial["cost_decomposition"] = {
            "per_side_bps": wf.costs.per_side_bps,
            "round_trip_bps": wf.costs.round_trip_bps,
            "cost_model_version": wf.cost_model_version,
        }

        pred_frames = [
            result.predictions.assign(fold=index + 1) for index, result in enumerate(fold_results)
        ]
        overall_predictions = pd.concat(pred_frames, ignore_index=True)
        overall_prediction_metrics = prediction_metrics(overall_predictions)

        trade_frames = [
            _trade_frame(result.trades, fold=index + 1) for index, result in enumerate(fold_results)
        ]
        overall_trades = (
            pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
        )

        record = {
            "backtest_id": backtest_id,
            "backtest_version": wf.backtest_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "instrument": data.ticker,
            "mode": "walkforward",
            "model_name": model_name,
            "dataset_version": data.dataset_version,
            "feature_version": data.feature_version,
            "label_version": data.label_version,
            "strategy_version": wf.strategy_version,
            "cost_model_version": wf.cost_model_version,
            "initial_capital": wf.initial_capital,
            "walk_forward": {
                "enabled": True,
                "method": "expanding",
                "train_window": train_window,
                "test_window": test_window,
                "step": step,
                "purge": purge,
                "embargo_rows": embargo_rows,
                "fold_count": len(fold_results),
            },
            "fold_summaries": fold_summaries,
            "overall_financial_metrics": overall_financial,
            "overall_prediction_metrics": overall_prediction_metrics,
            "code_version": "unversioned",
            "environment": {"python": platform.python_version(), "pandas": pd.__version__},
        }
        config_snapshot = self.engine._config_snapshot()
        config_snapshot["walkforward"] = {
            "train_window": train_window,
            "test_window": test_window,
            "step": step,
            "purge": purge,
            "embargo_rows": embargo_rows,
        }

        paths: dict[str, Path] = {}
        try:
            for sub in (
                "predictions",
                "trades",
                "curves",
                "metrics",
                "config",
                "metadata",
                "report",
            ):
                (directory / sub).mkdir(parents=True, exist_ok=True)
            write_csv(directory / "predictions" / "fold_predictions.csv", overall_predictions)
            if not overall_trades.empty:
                write_csv(directory / "trades" / "fold_trade_ledger.csv", overall_trades)
            write_csv(directory / "curves" / "equity_curve.csv", equity_frame)
            write_csv(
                directory / "curves" / "drawdown_curve.csv", equity_frame[["timestamp", "drawdown"]]
            )
            write_json(directory / "metrics" / "financial_metrics.json", overall_financial)
            write_json(
                directory / "metrics" / "prediction_metrics.json", overall_prediction_metrics
            )
            write_json(directory / "config" / "config_snapshot.json", config_snapshot)
            write_json(directory / "metadata" / "experiment_record.json", record)
            (directory / "report" / "backtest_report.md").write_text(
                _report(record, fold_summaries), encoding="utf-8"
            )
            paths = {
                "predictions": directory / "predictions" / "fold_predictions.csv",
                "trade_ledger": directory / "trades" / "fold_trade_ledger.csv",
                "equity_curve": directory / "curves" / "equity_curve.csv",
                "financial_metrics": directory / "metrics" / "financial_metrics.json",
                "experiment_record": directory / "metadata" / "experiment_record.json",
                "report": directory / "report" / "backtest_report.md",
            }
        except (OSError, ValueError, RuntimeError) as error:
            raise WalkForwardError(f"cannot write walk-forward outputs: {error}") from error

        return WalkForwardResult(
            backtest_id=backtest_id,
            ticker=data.ticker,
            model_name=model_name,
            folds=tuple(fold_results),
            overall_equity=equity_frame,
            overall_financial_metrics=overall_financial,
            overall_prediction_metrics=overall_prediction_metrics,
            fold_summaries=fold_summaries,
            output_dir=directory,
            paths=paths,
        )


def _trade_frame(trades, *, fold: int) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame({"fold": []})
    frame = pd.DataFrame([trade.__dict__ for trade in trades])
    frame.insert(0, "fold", fold)
    return frame


def _report(record: dict, fold_summaries: list[dict[str, Any]]) -> str:
    import json

    return "\n".join(
        [
            f"# Walk-forward backtest report `{record['backtest_id']}`",
            "",
            "> Research artifact only. Not financial advice; not a live trading system.",
            "",
            f"- Instrument: `{record['instrument']}`",
            f"- Model (trained per fold): `{record['model_name']}`",
            f"- Dataset: `{record['dataset_version']}` | Features: `{record['feature_version']}` | Labels: `{record['label_version']}`",
            f"- Strategy: `{record['strategy_version']}` | Cost model: `{record['cost_model_version']}`",
            (
                f"- Walk-forward: expanding, train {record['walk_forward']['train_window']} / "
                f"test {record['walk_forward']['test_window']} / step {record['walk_forward']['step']}, "
                f"purge={record['walk_forward']['purge']}, "
                f"embargo={record['walk_forward']['embargo_rows']}"
            ),
            "",
            "## Folds",
            "",
            "```json",
            json.dumps(fold_summaries, indent=2, sort_keys=True),
            "```",
            "",
            "## Overall financial metrics",
            "",
            "```json",
            json.dumps(record["overall_financial_metrics"], indent=2, sort_keys=True, default=str),
            "```",
            "",
            "## Limitations",
            "- Each fold trains a fresh baseline on train-only data; no fold sees future rows.",
            "- Close-to-close execution, long-only, fixed quantity (MVP simplifications).",
            "- Backtests do not guarantee future performance; no profitability claim is made.",
            "",
        ]
    )
