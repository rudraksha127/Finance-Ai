"""Evaluation & walk-forward backtesting engine (Milestone 08)."""

from __future__ import annotations

from src.backtest.data import BacktestData, load_backtest_data
from src.backtest.engine import BacktestEngine, BacktestResult
from src.backtest.errors import (
    BacktestError,
    DataQualityError,
    EmptyTestSetError,
    ExecutionError,
    MetricsError,
    ReportError,
    WalkForwardError,
)
from src.backtest.walkforward import Fold, WalkForwardResult, WalkForwardRunner, generate_folds

__all__ = [
    "BacktestData",
    "BacktestEngine",
    "BacktestError",
    "BacktestResult",
    "DataQualityError",
    "EmptyTestSetError",
    "ExecutionError",
    "Fold",
    "MetricsError",
    "ReportError",
    "WalkForwardError",
    "WalkForwardResult",
    "WalkForwardRunner",
    "generate_folds",
    "load_backtest_data",
]
