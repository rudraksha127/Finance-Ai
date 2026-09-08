"""Execution simulator, position manager, and P&L calculator (M08).

Implements the frozen MVP strategy wrapper
(EVALUATION_BACKTESTING_BLUEPRINT sections 10-14):

- Long-only positions (LONG/FLAT), fixed quantity 1 unit, one position
  at a time (no pyramiding).
- Close-to-close execution: entry at close of the signal day, exit at
  close of the exit day (documented MVP simplification, section 10.2).
- Exit on SELL, or when the max holding period (default 5 trading rows,
  matching the label horizon) is reached; max-holding exit takes
  precedence over a same-day SELL.
- Transaction costs per side in bps (default 10 bps/side, 20 bps round
  trip), charged on the entry day and the exit day.
- Any position still open at the end of the evaluation period is
  force-closed at the final close so the ledger fully accounts for P&L.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from src.backtest.errors import DataQualityError, ExecutionError
from src.backtest.signals import BUY, SELL, SIGNALS
from src.logging.logger import get_logger

logger = get_logger("backtest.execution")

REASON_SELL = "signal_sell"
REASON_MAX_HOLDING = "max_holding_period_expired"
REASON_END = "end_of_backtest"


@dataclass(frozen=True)
class Trade:
    """One simulated round trip (research artifact, not a live order)."""

    trade_id: str
    instrument: str
    signal_timestamp: datetime
    execution_timestamp: datetime
    signal: str
    probability: float
    entry_price: float
    exit_timestamp: datetime
    exit_price: float
    quantity: float
    gross_pnl: float
    costs: float
    net_pnl: float
    holding_duration: int
    reason: str
    signal_version: str
    trade_number: int


@dataclass(frozen=True)
class SimulationResult:
    """Ledger plus the daily strategy return/equity series."""

    trades: tuple[Trade, ...]
    equity: pd.DataFrame  # columns: timestamp, daily_return, equity, drawdown
    active_days: np.ndarray  # bool array: position held on day i
    cost_charges: np.ndarray  # cost fraction deducted on each day (gross reconstruction)
    n_days: int


def _validate_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"timestamp", "close", "signal"}
    missing = required - set(frame.columns)
    if missing:
        raise DataQualityError(f"simulation requires columns: {sorted(missing)}")
    signals = set(frame["signal"].unique())
    if not signals.issubset(set(SIGNALS)):
        raise DataQualityError(f"invalid signal values: {sorted(signals)}")
    close = pd.to_numeric(frame["close"], errors="coerce")
    if close.isna().any() or not (close > 0).all():
        raise DataQualityError("simulation requires positive, non-NaN close prices")
    timestamps = pd.to_datetime(frame["timestamp"], errors="coerce")
    if timestamps.isna().any():
        raise DataQualityError("simulation requires valid timestamps")
    if not timestamps.is_monotonic_increasing:
        raise DataQualityError("simulation requires ascending timestamps (no silent sort)")
    output = frame.copy()
    output["timestamp"] = timestamps
    output["close"] = close
    return output


def simulate(
    frame: pd.DataFrame,
    *,
    ticker: str,
    signal_version: str,
    quantity: float,
    max_holding_period: int,
    cost_per_side_bps: float,
) -> SimulationResult:
    """Simulate the frozen strategy over a chronologically sorted frame.

    ``frame`` must carry ``timestamp``, ``close`` and ``signal`` columns
    (the latter produced by :func:`src.backtest.signals.generate_signals`).
    """
    frame = _validate_frame(frame)
    if frame.empty:
        raise ExecutionError("cannot simulate an empty evaluation period")
    if quantity <= 0:
        raise ExecutionError("position quantity must be positive (blueprint section 31)")
    if max_holding_period <= 0:
        raise ExecutionError("max holding period must be positive")
    if cost_per_side_bps < 0:
        raise ExecutionError("cost per side must be non-negative")

    n = len(frame)
    cost_frac = cost_per_side_bps / 10_000.0
    timestamps = frame["timestamp"].to_numpy()
    closes = frame["close"].to_numpy(dtype=float)
    signals = frame["signal"].to_numpy()
    daily_return = np.zeros(n, dtype=float)
    cost_charges = np.zeros(n, dtype=float)

    trades: list[Trade] = []
    position: dict | None = None
    trade_number = 0

    for index in range(n):
        if position is None:
            if signals[index] == BUY:
                trade_number += 1
                position = {
                    "entry_index": index,
                    "entry_ts": timestamps[index],
                    "entry_price": closes[index],
                    "probability": float(frame["probability_UP"].iloc[index]),
                    "trade_number": trade_number,
                }
                daily_return[index] -= cost_frac
                cost_charges[index] += cost_frac
            continue

        held = index - position["entry_index"]
        reason = None
        if held >= max_holding_period:
            reason = REASON_MAX_HOLDING
        elif signals[index] == SELL:
            reason = REASON_SELL
        if reason is None:
            continue

        exit_price = closes[index]
        entry_price = position["entry_price"]
        gross = (exit_price - entry_price) * quantity
        costs = cost_frac * (entry_price + exit_price) * quantity
        net = gross - costs
        trades.append(
            Trade(
                trade_id=f"T{trade_number:03d}",
                instrument=ticker,
                signal_timestamp=position["entry_ts"],
                execution_timestamp=position["entry_ts"],
                signal=BUY,
                probability=position["probability"],
                entry_price=entry_price,
                exit_timestamp=timestamps[index],
                exit_price=exit_price,
                quantity=quantity,
                gross_pnl=round(gross, 6),
                costs=round(costs, 6),
                net_pnl=round(net, 6),
                holding_duration=_holding_days(timestamps[index], position["entry_ts"]),
                reason=reason,
                signal_version=signal_version,
                trade_number=position["trade_number"],
            )
        )
        daily_return[index] -= cost_frac
        cost_charges[index] += cost_frac
        position = None

    # Force-close any position still open at the end of the period.
    if position is not None:
        last = n - 1
        exit_price = closes[last]
        entry_price = position["entry_price"]
        gross = (exit_price - entry_price) * quantity
        costs = cost_frac * (entry_price + exit_price) * quantity
        net = gross - costs
        trades.append(
            Trade(
                trade_id=f"T{position['trade_number']:03d}",
                instrument=ticker,
                signal_timestamp=position["entry_ts"],
                execution_timestamp=position["entry_ts"],
                signal=BUY,
                probability=position["probability"],
                entry_price=entry_price,
                exit_timestamp=timestamps[last],
                exit_price=exit_price,
                quantity=quantity,
                gross_pnl=round(gross, 6),
                costs=round(costs, 6),
                net_pnl=round(net, 6),
                holding_duration=_holding_days(timestamps[last], position["entry_ts"]),
                reason=REASON_END,
                signal_version=signal_version,
                trade_number=position["trade_number"],
            )
        )
        daily_return[last] -= cost_frac
        cost_charges[last] += cost_frac

    # Position-active days: entry at close of day e earns returns for days e+1..x.
    active = np.zeros(n, dtype=bool)
    for trade in trades:
        entry_index = int(np.where(timestamps == trade.execution_timestamp)[0][0])
        exit_index = int(np.where(timestamps == trade.exit_timestamp)[0][0])
        start, stop = entry_index + 1, exit_index
        if start <= stop:
            active[start : stop + 1] = True

    for index in range(1, n):
        if active[index]:
            daily_return[index] += closes[index] / closes[index - 1] - 1.0

    equity = np.cumprod(1.0 + daily_return)
    running_max = np.maximum.accumulate(equity)
    drawdown = equity / running_max - 1.0
    curve = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(timestamps).strftime("%Y-%m-%dT%H:%M:%S"),
            "daily_return": daily_return,
            "equity": equity,
            "drawdown": drawdown,
        }
    )
    return SimulationResult(
        trades=tuple(trades),
        equity=curve,
        active_days=active,
        cost_charges=cost_charges,
        n_days=n,
    )


def _holding_days(exit_ts, entry_ts) -> int:
    """Calendar days between exit and entry (datetime64-safe)."""
    return int(pd.Timedelta(exit_ts - entry_ts).days)
