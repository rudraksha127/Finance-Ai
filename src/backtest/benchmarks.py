"""Benchmark strategies for the backtest (M08).

MVP benchmarks (EVALUATION_BACKTESTING_BLUEPRINT section 17):
buy-and-hold and zero-trade (cash). Both use the same evaluation
period and the same per-side cost model as the strategy, so the
comparison is apples-to-apples (section 17.3).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.backtest.errors import MetricsError
from src.backtest.metrics import financial_metrics


def _equity_from_returns(daily_returns: np.ndarray) -> np.ndarray:
    if np.any(~np.isfinite(daily_returns)):
        raise MetricsError("benchmark returns must be finite")
    return np.cumprod(1.0 + daily_returns)


def buy_and_hold_series(closes: np.ndarray, *, cost_per_side_bps: float) -> np.ndarray:
    """Daily returns of holding from first close to last close.

    Pays one round trip of costs (entry on day 0, exit on the last day)
    so it is compared on the same cost basis as the strategy.
    """
    closes = np.asarray(closes, dtype=float)
    if len(closes) < 2:
        raise MetricsError("buy-and-hold requires at least two price observations")
    if np.any(closes <= 0) or np.any(~np.isfinite(closes)):
        raise MetricsError("buy-and-hold requires positive, finite prices")
    returns = np.zeros(len(closes), dtype=float)
    returns[1:] = closes[1:] / closes[:-1] - 1.0
    cost_frac = cost_per_side_bps / 10_000.0
    returns[0] -= cost_frac
    returns[-1] -= cost_frac
    return returns


def zero_trade_series(n_days: int) -> np.ndarray:
    """Always flat: zero return every day."""
    if n_days <= 0:
        raise MetricsError("zero-trade benchmark requires at least one day")
    return np.zeros(n_days, dtype=float)


def benchmark_metrics(
    closes: np.ndarray,
    *,
    n_days: int,
    cost_per_side_bps: float,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
) -> dict[str, dict[str, Any]]:
    """Compute comparable metrics for both MVP benchmarks."""
    buy_hold_returns = buy_and_hold_series(closes, cost_per_side_bps=cost_per_side_bps)
    cash_returns = zero_trade_series(n_days)
    return {
        "buy_and_hold": financial_metrics(
            buy_hold_returns,
            _equity_from_returns(buy_hold_returns),
            (),
            periods_per_year=periods_per_year,
            risk_free_rate=risk_free_rate,
        ),
        "zero_trade": financial_metrics(
            cash_returns,
            _equity_from_returns(cash_returns),
            (),
            periods_per_year=periods_per_year,
            risk_free_rate=risk_free_rate,
        ),
    }


def benchmark_equity_curves(
    closes: np.ndarray, *, n_days: int, cost_per_side_bps: float
) -> dict[str, np.ndarray]:
    """Equity curves for the two benchmarks (same period as the strategy)."""
    return {
        "buy_and_hold": _equity_from_returns(
            buy_and_hold_series(closes, cost_per_side_bps=cost_per_side_bps)
        ),
        "zero_trade": _equity_from_returns(zero_trade_series(n_days)),
    }
