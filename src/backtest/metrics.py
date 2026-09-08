"""Metrics engine for the backtest (M08).

Computes the core financial metrics defined in EVALUATION_BACKTESTING
BLUEPRINT section 15 (mathematical definitions table) from the daily
strategy returns, equity curve, and trade ledger. Trade P&L is net of
transaction costs; metrics are N/A (None) rather than fabricated when
the inputs do not support them (e.g., zero trades, zero variance).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.backtest.errors import MetricsError
from src.backtest.execution import Trade


def _downside_deviation(returns: np.ndarray, periods_per_year: int) -> float:
    """Semi-deviation of returns (standard Sortino denominator)."""
    negative = np.minimum(returns, 0.0)
    return float(np.sqrt(np.mean(negative**2)) * np.sqrt(periods_per_year))


def financial_metrics(
    daily_returns: np.ndarray,
    equity: np.ndarray,
    trades: tuple[Trade, ...],
    *,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
) -> dict[str, Any]:
    """Compute all section-15 metrics; None means 'not applicable'."""
    if len(daily_returns) == 0 or len(equity) == 0:
        raise MetricsError("cannot compute metrics on an empty return series")
    if np.any(~np.isfinite(daily_returns)) or np.any(~np.isfinite(equity)):
        raise MetricsError("cannot compute metrics on non-finite returns/equity")
    if periods_per_year <= 0:
        raise MetricsError("periods_per_year must be positive")

    n_days = len(daily_returns)
    cumulative_return = float(equity[-1] - 1.0)
    annualized_return = (
        float((1.0 + cumulative_return) ** (periods_per_year / n_days) - 1.0)
        if n_days > 0
        else None
    )
    volatility = float(np.std(daily_returns, ddof=1) * np.sqrt(periods_per_year))
    sharpe = (annualized_return - risk_free_rate) / volatility if volatility > 0 else None
    downside = _downside_deviation(daily_returns, periods_per_year)
    sortino = (annualized_return - risk_free_rate) / downside if downside > 0 else None

    running_max = np.maximum.accumulate(equity)
    max_drawdown = float(np.min(equity / running_max - 1.0))
    calmar = annualized_return / abs(max_drawdown) if max_drawdown < 0 else None

    n_trades = len(trades)
    win_rate = avg_win = avg_loss = profit_factor = expectancy = None
    avg_holding_days = None
    if n_trades:
        # Win/loss classification and profit factor use NET P&L (after costs),
        # consistent with the blueprint section 15.2 note.
        net = np.array([trade.net_pnl for trade in trades], dtype=float)
        wins = net[net > 0]
        losses = net[net < 0]
        win_rate = float(len(wins) / n_trades)
        avg_win = float(wins.mean()) if len(wins) else None
        avg_loss = float(abs(losses.mean())) if len(losses) else None
        total_wins = float(wins.sum()) if len(wins) else 0.0
        total_losses = float(abs(losses.sum())) if len(losses) else 0.0
        profit_factor = total_wins / total_losses if total_losses > 0 else None
        if win_rate is not None and avg_win is not None and avg_loss is not None:
            expectancy = win_rate * avg_win - (1.0 - win_rate) * avg_loss
        avg_holding_days = float(np.mean([trade.holding_duration for trade in trades]))

    total_gross = float(sum(trade.gross_pnl for trade in trades))
    total_costs = float(sum(trade.costs for trade in trades))
    total_net = float(sum(trade.net_pnl for trade in trades))

    return {
        "cumulative_return": round(cumulative_return, 6),
        "annualized_return": round(annualized_return, 6) if annualized_return is not None else None,
        "annualized_volatility": round(volatility, 6),
        "sharpe_ratio": round(sharpe, 6) if sharpe is not None else None,
        "sortino_ratio": round(sortino, 6) if sortino is not None else None,
        "max_drawdown": round(max_drawdown, 6),
        "calmar_ratio": round(calmar, 6) if calmar is not None else None,
        "win_rate": round(win_rate, 6) if win_rate is not None else None,
        "average_win": round(avg_win, 6) if avg_win is not None else None,
        "average_loss": round(avg_loss, 6) if avg_loss is not None else None,
        "profit_factor": round(profit_factor, 6) if profit_factor is not None else None,
        "expectancy": round(expectancy, 6) if expectancy is not None else None,
        "number_of_trades": n_trades,
        "turnover": round(2 * n_trades / n_days, 6),
        "avg_holding_period_days": (
            round(avg_holding_days, 6) if avg_holding_days is not None else None
        ),
        "total_gross_pnl": round(total_gross, 6),
        "total_costs": round(total_costs, 6),
        "total_net_pnl": round(total_net, 6),
        "cost_decomposition": {
            "per_side_bps": None,  # filled by the engine with the cost model
            "round_trip_bps": None,
            "note": "net P&L already includes entry+exit costs per trade",
        },
    }


def rolling_metrics(
    equity: pd.DataFrame, *, window: int, periods_per_year: int = 252
) -> pd.DataFrame:
    """Rolling returns / volatility / Sharpe over the equity series."""
    if "equity" not in equity:
        raise MetricsError("rolling metrics require an equity column")
    curve = equity.copy()
    returns = pd.Series(curve["daily_return"].to_numpy(dtype=float))
    rolling = pd.DataFrame(index=curve.index)
    rolling["rolling_return"] = curve["equity"] / curve["equity"].shift(window) - 1.0
    rolling["rolling_volatility"] = returns.rolling(window).std(ddof=1) * np.sqrt(periods_per_year)
    rolling["rolling_sharpe"] = (
        returns.rolling(window).mean()
        / returns.rolling(window).std(ddof=1)
        * np.sqrt(periods_per_year)
    )
    return rolling


def drawdown_curve(equity: np.ndarray) -> np.ndarray:
    """Percentage below running peak: equity/running_max - 1."""
    running_max = np.maximum.accumulate(equity)
    return equity / running_max - 1.0


def prediction_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    """Classification metrics on the evaluation-period predictions."""
    from src.model.metrics import classification_metrics

    if "prediction" not in frame or "label" not in frame:
        raise MetricsError("prediction metrics require prediction and label columns")
    probabilities = frame[[f"probability_{c}" for c in ("UP", "DOWN", "HOLD")]].to_numpy(
        dtype=float
    )
    return classification_metrics(
        frame["label"].to_numpy(),
        frame["prediction"].to_numpy(),
        probabilities,
        ("UP", "DOWN", "HOLD"),
    )
