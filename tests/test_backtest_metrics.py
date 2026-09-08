"""Unit tests for financial metrics math (M08)."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from src.backtest.errors import MetricsError
from src.backtest.execution import Trade
from src.backtest.metrics import (
    drawdown_curve,
    financial_metrics,
    rolling_metrics,
)


def _trade(net: float, days: int = 5) -> Trade:
    entry = datetime(2025, 1, 2)
    return Trade(
        trade_id="T001",
        instrument="AAPL",
        signal_timestamp=entry,
        execution_timestamp=entry,
        signal="BUY",
        probability=0.6,
        entry_price=100.0,
        exit_timestamp=entry + timedelta(days=days),
        exit_price=100.0 + net,
        quantity=1.0,
        gross_pnl=net + 0.01,
        costs=0.01,
        net_pnl=net,
        holding_duration=days,
        reason="signal_sell",
        signal_version="stg_v0.1",
        trade_number=1,
    )


def test_cumulative_return_and_max_drawdown_hand_derived():
    returns = np.array([0.01, -0.02, 0.03])
    equity = np.cumprod(1.0 + returns)  # [1.01, 0.9898, 1.019494]
    metrics = financial_metrics(returns, equity, (), periods_per_year=252, risk_free_rate=0.0)
    assert metrics["cumulative_return"] == pytest.approx(equity[-1] - 1.0)
    assert metrics["max_drawdown"] == pytest.approx(0.9898 / 1.01 - 1.0)  # -0.02
    assert metrics["number_of_trades"] == 0
    assert metrics["win_rate"] is None
    assert metrics["sharpe_ratio"] is not None
    assert metrics["annualized_volatility"] == pytest.approx(np.std(returns, ddof=1) * np.sqrt(252))
    # gross/cost decomposition with no trades
    assert metrics["total_costs"] == 0.0
    assert metrics["turnover"] == 0.0


def test_trade_based_metrics():
    equity = np.array([1.0, 1.005])
    trades = (_trade(net=1.0), _trade(net=-0.5))
    metrics = financial_metrics(np.array([0.005, 0.005]), equity, trades)
    assert metrics["number_of_trades"] == 2
    assert metrics["win_rate"] == pytest.approx(0.5)
    assert metrics["average_win"] == pytest.approx(1.0)
    assert metrics["average_loss"] == pytest.approx(0.5)
    # Profit factor is computed on net P&L (wins/losses are net of costs)
    assert metrics["profit_factor"] == pytest.approx(1.0 / 0.5)
    assert metrics["expectancy"] == pytest.approx(0.5 * 1.0 - 0.5 * 0.5)
    # gross = net + costs: 1.01 + (-0.49) = 0.52; net = 1.0 + (-0.5) = 0.5
    assert metrics["total_gross_pnl"] == pytest.approx(0.52)
    assert metrics["total_net_pnl"] == pytest.approx(0.5)


def test_zero_variance_sharpe_is_none():
    returns = np.zeros(10)
    metrics = financial_metrics(returns, np.ones(10), (), periods_per_year=252)
    assert metrics["sharpe_ratio"] is None
    assert metrics["sortino_ratio"] is None
    assert metrics["max_drawdown"] == 0.0
    assert metrics["calmar_ratio"] is None


def test_drawdown_curve():
    equity = np.array([1.0, 1.2, 0.9, 1.1])
    dd = drawdown_curve(equity)
    assert dd[0] == 0.0
    assert dd[1] == 0.0
    assert dd[2] == pytest.approx(0.9 / 1.2 - 1.0)
    assert dd[3] == pytest.approx(1.1 / 1.2 - 1.0)


def test_rolling_metrics_window():
    frame = pd.DataFrame(
        {
            "daily_return": [0.001, 0.002, -0.001, 0.003],
            "equity": np.cumprod([1.001, 1.002, 0.999, 1.003]),
        }
    )
    rolling = rolling_metrics(frame, window=2)
    assert len(rolling) == 4
    assert pd.isna(rolling["rolling_return"].iloc[1])  # needs 2 prior observations
    assert rolling["rolling_return"].iloc[2] == pytest.approx(
        frame["equity"].iloc[2] / frame["equity"].iloc[0] - 1.0
    )


def test_empty_series_raises():
    with pytest.raises(MetricsError):
        financial_metrics(np.array([]), np.array([]), ())
