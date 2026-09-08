"""Unit tests for signal generation and threshold research (M08)."""

from __future__ import annotations

import pandas as pd
import pytest

from src.backtest.errors import DataQualityError
from src.backtest.signals import BUY, NO_TRADE, SELL, generate_signals, threshold_sensitivity


def _frame(up: list[float], down: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "probability_UP": up,
            "probability_DOWN": down,
            "probability_HOLD": [1.0 - u - d for u, d in zip(up, down)],
        }
    )


def test_buy_sell_no_trade_rules():
    frame = _frame([0.60, 0.30, 0.10], [0.20, 0.60, 0.30])
    signals = generate_signals(frame, buy_threshold=0.55, sell_threshold=0.55)
    assert list(signals) == [BUY, SELL, NO_TRADE]


def test_exact_tie_prefers_buy():
    frame = _frame([0.60, 0.50], [0.60, 0.50])
    signals = generate_signals(frame, buy_threshold=0.55, sell_threshold=0.55)
    assert list(signals) == [BUY, NO_TRADE]  # tie -> BUY; below thresholds -> NO_TRADE


def test_threshold_boundaries():
    frame = _frame([0.55, 0.5499], [0.10, 0.10])
    signals = generate_signals(frame, buy_threshold=0.55, sell_threshold=0.55)
    assert list(signals) == [BUY, NO_TRADE]  # >= buys, strictly below does not


def test_missing_probability_raises():
    with pytest.raises(DataQualityError):
        generate_signals(
            pd.DataFrame({"probability_UP": [0.5]}), buy_threshold=0.55, sell_threshold=0.55
        )


def test_non_finite_probability_raises():
    frame = _frame([float("nan"), 0.6], [0.1, 0.1])
    with pytest.raises(DataQualityError):
        generate_signals(frame, buy_threshold=0.55, sell_threshold=0.55)


def test_threshold_sensitivity_hand_derived():
    # 4 rows; UP labels on rows 0 and 1; p_up = [0.9, 0.7, 0.3, 0.2]
    frame = pd.DataFrame(
        {
            "probability_UP": [0.9, 0.7, 0.3, 0.2],
            "label": ["UP", "UP", "DOWN", "HOLD"],
        }
    )
    rows = threshold_sensitivity(frame, thresholds=(0.5, 0.75))
    assert rows[0]["threshold"] == 0.5
    assert rows[0]["signal_count"] == 2
    assert rows[0]["signal_frequency"] == 0.5
    assert rows[0]["signal_accuracy"] == pytest.approx(1.0)
    assert rows[0]["precision"] == pytest.approx(1.0)
    assert rows[1]["signal_count"] == 1
    assert rows[1]["precision"] == pytest.approx(1.0)
    assert rows[1]["signal_accuracy"] == pytest.approx(1.0)


def test_threshold_sensitivity_no_signals():
    frame = pd.DataFrame({"probability_UP": [0.1, 0.2], "label": ["UP", "DOWN"]})
    rows = threshold_sensitivity(frame, thresholds=(0.9,))
    assert rows[0]["signal_count"] == 0
    assert rows[0]["signal_accuracy"] is None
    assert rows[0]["precision"] is None
