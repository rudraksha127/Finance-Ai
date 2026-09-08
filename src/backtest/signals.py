"""Signal generator for the backtest engine (M08).

Converts model probabilities into deterministic signals
(EVALUATION_BACKTESTING_BLUEPRINT section 7, RISK_DECISION_ENGINE
section 6):

    BUY      -> P(UP)   >= buy_threshold   (and P(UP) >= P(DOWN))
    SELL     -> P(DOWN) >= sell_threshold  (and P(DOWN) > P(UP))
    NO_TRADE -> otherwise

The MVP position model is long-only (section 13), so SELL means "exit /
stay flat". Thresholds are research parameters selected on validation
data only; the final test set is never used to tune them (section 7.3).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.backtest.errors import DataQualityError
from src.logging.logger import get_logger

logger = get_logger("backtest.signals")

BUY = "BUY"
SELL = "SELL"
NO_TRADE = "NO_TRADE"
SIGNALS = (BUY, SELL, NO_TRADE)


@dataclass(frozen=True)
class SignalConfig:
    """Frozen signal thresholds (research parameters, never hardcoded)."""

    buy_threshold: float = 0.55
    sell_threshold: float = 0.55


def generate_signals(
    frame: pd.DataFrame,
    *,
    buy_threshold: float,
    sell_threshold: float,
) -> pd.Series:
    """Return a BUY/SELL/NO_TRADE series aligned with ``frame`` rows."""
    if "probability_UP" not in frame or "probability_DOWN" not in frame:
        raise DataQualityError("signal generation requires probability_UP/probability_DOWN columns")
    p_up = frame["probability_UP"].to_numpy(dtype=float)
    p_down = frame["probability_DOWN"].to_numpy(dtype=float)
    if not np.isfinite(p_up).all() or not np.isfinite(p_down).all():
        raise DataQualityError("signal generation requires finite probabilities")

    buy = (p_up >= buy_threshold) & (p_up >= p_down)
    sell = (p_down >= sell_threshold) & (p_down > p_up)  # strict tie-break favors BUY
    signals = np.where(buy, BUY, np.where(sell, SELL, NO_TRADE))
    return pd.Series(signals, index=frame.index, name="signal")


def threshold_sensitivity(
    frame: pd.DataFrame,
    *,
    thresholds: list[float] | tuple[float, ...],
) -> list[dict]:
    """Sweep BUY thresholds on validation data (blueprint section 7.4).

    ``frame`` must carry ``probability_UP`` and the true ``label`` column.
    Returns rows with signal count, signal accuracy (P(UP) given BUY),
    signal frequency, and precision — for threshold research ONLY.
    """
    if "label" not in frame:
        raise DataQualityError("threshold sensitivity requires a true label column")
    total = len(frame)
    rows: list[dict] = []
    for threshold in thresholds:
        triggered = frame["probability_UP"] >= threshold
        count = int(triggered.sum())
        accuracy = None
        precision = None
        if count:
            accuracy = float((frame.loc[triggered, "label"] == "UP").mean())
            tp = int(((frame.loc[triggered, "label"] == "UP")).sum())
            precision = tp / count
        rows.append(
            {
                "threshold": float(threshold),
                "signal_count": count,
                "signal_accuracy": accuracy,
                "signal_frequency": count / total if total else None,
                "precision": precision,
            }
        )
    return rows


def predicted_class_probability(frame: pd.DataFrame, signal: str) -> pd.Series:
    """Probability of the class that triggered the signal (for the ledger)."""
    if signal == BUY:
        return frame["probability_UP"]
    if signal == SELL:
        return frame["probability_DOWN"]
    return pd.Series(np.nan, index=frame.index)
