"""Unit tests for trade simulation and equity construction (M08)."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from src.backtest.errors import DataQualityError, ExecutionError
from src.backtest.execution import (
    REASON_END,
    REASON_MAX_HOLDING,
    REASON_SELL,
    simulate,
)
from src.backtest.signals import BUY, NO_TRADE, SELL


def _frame(closes: list[float], signals: list[str], start: date = date(2025, 1, 2)) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [start + timedelta(days=index) for index in range(len(closes))],
            "close": closes,
            "signal": signals,
            "probability_UP": [0.9 if s == BUY else 0.1 for s in signals],
        }
    )


def test_sell_exit_with_costs_hand_derived():
    # closes 100..105; BUY day0, NO_TRADE days 1-2, SELL day3, flat after.
    frame = _frame([100.0, 101.0, 102.0, 103.0, 104.0], [BUY, NO_TRADE, NO_TRADE, SELL, NO_TRADE])
    result = simulate(
        frame,
        ticker="AAPL",
        signal_version="stg_v0.1",
        quantity=1.0,
        max_holding_period=5,
        cost_per_side_bps=10.0,
    )
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_price == 100.0
    assert trade.exit_price == 103.0
    assert trade.gross_pnl == pytest.approx(3.0)
    assert trade.costs == pytest.approx(0.1 + 0.103)  # 10 bps of 100 + 10 bps of 103
    assert trade.net_pnl == pytest.approx(3.0 - 0.203)
    assert trade.reason == REASON_SELL
    assert trade.holding_duration == 3
    assert trade.signal == BUY
    assert trade.signal_version == "stg_v0.1"
    assert trade.trade_number == 1

    # Equity: day0 cost -0.001; days 1-3 market returns; day4 flat.
    returns = result.equity["daily_return"].to_numpy()
    assert returns[0] == pytest.approx(-0.001)
    assert returns[1] == pytest.approx(101.0 / 100.0 - 1.0)
    assert returns[2] == pytest.approx(102.0 / 101.0 - 1.0)
    assert returns[3] == pytest.approx(103.0 / 102.0 - 1.0 - 0.001)
    assert returns[4] == pytest.approx(0.0)
    assert result.equity["equity"].iloc[0] == pytest.approx(0.999)
    assert result.equity["equity"].iloc[-1] == pytest.approx(
        (1 - 0.001) * (101 / 100) * (102 / 101) * (103 / 102 - 0.001)
    )


def test_max_holding_forces_exit():
    frame = _frame([100.0, 101.0, 102.0, 103.0], [BUY, NO_TRADE, NO_TRADE, NO_TRADE])
    result = simulate(
        frame,
        ticker="AAPL",
        signal_version="stg_v0.1",
        quantity=1.0,
        max_holding_period=3,
        cost_per_side_bps=0.0,
    )
    assert len(result.trades) == 1
    assert result.trades[0].reason == REASON_MAX_HOLDING
    assert result.trades[0].exit_price == 103.0


def test_no_pyramiding_consecutive_buys():
    frame = _frame([100.0, 101.0, 102.0, 103.0], [BUY, BUY, BUY, SELL])
    result = simulate(
        frame,
        ticker="AAPL",
        signal_version="stg_v0.1",
        quantity=1.0,
        max_holding_period=10,
        cost_per_side_bps=0.0,
    )
    assert len(result.trades) == 1
    assert result.trades[0].entry_price == 100.0
    assert result.trades[0].exit_price == 103.0


def test_open_position_force_closed_at_end():
    frame = _frame([100.0, 101.0, 102.0], [NO_TRADE, BUY, NO_TRADE])
    result = simulate(
        frame,
        ticker="AAPL",
        signal_version="stg_v0.1",
        quantity=1.0,
        max_holding_period=10,
        cost_per_side_bps=0.0,
    )
    assert len(result.trades) == 1
    assert result.trades[0].reason == REASON_END
    assert result.trades[0].entry_price == 101.0
    assert result.trades[0].exit_price == 102.0
    assert result.trades[0].holding_duration == 1


def test_no_trades_flat():
    frame = _frame([100.0, 101.0, 102.0], [NO_TRADE, NO_TRADE, NO_TRADE])
    result = simulate(
        frame,
        ticker="AAPL",
        signal_version="stg_v0.1",
        quantity=1.0,
        max_holding_period=5,
        cost_per_side_bps=10.0,
    )
    assert result.trades == ()
    assert (result.equity["equity"] == 1.0).all()


def test_unsorted_timestamps_fail_loud():
    frame = _frame([100.0, 101.0, 102.0], [BUY, NO_TRADE, SELL])
    shuffled = frame.iloc[[2, 0, 1]].reset_index(drop=True)
    with pytest.raises(DataQualityError, match="ascending"):
        simulate(
            shuffled,
            ticker="AAPL",
            signal_version="stg_v0.1",
            quantity=1.0,
            max_holding_period=5,
            cost_per_side_bps=10.0,
        )


def test_negative_price_fails_loud():
    frame = _frame([100.0, -1.0, 102.0], [BUY, NO_TRADE, SELL])
    with pytest.raises(DataQualityError, match="positive"):
        simulate(
            frame,
            ticker="AAPL",
            signal_version="stg_v0.1",
            quantity=1.0,
            max_holding_period=5,
            cost_per_side_bps=10.0,
        )


def test_invalid_quantity_fails_loud():
    frame = _frame([100.0, 101.0, 102.0], [BUY, NO_TRADE, SELL])
    with pytest.raises(ExecutionError):
        simulate(
            frame,
            ticker="AAPL",
            signal_version="stg_v0.1",
            quantity=0.0,
            max_holding_period=5,
            cost_per_side_bps=10.0,
        )


def test_invalid_signal_value_fails_loud():
    frame = _frame([100.0, 101.0, 102.0], [BUY, "SHORT", SELL])
    with pytest.raises(DataQualityError, match="signal"):
        simulate(
            frame,
            ticker="AAPL",
            signal_version="stg_v0.1",
            quantity=1.0,
            max_holding_period=5,
            cost_per_side_bps=10.0,
        )
