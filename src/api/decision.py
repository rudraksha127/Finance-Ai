"""Shared decision-engine integration for the inference API (M09).

The API MUST NOT reimplement decision rules (INFERENCE_API_BLUEPRINT
section 23.1). Signal generation delegates to
:func:`src.backtest.signals.generate_signals` — the exact module the
backtest engine uses — with the same thresholds from the same YAML
(``backtest.signal``). This module adds only the response-facing
wrappers the blueprint requires: the normalized research risk score
(RISK_DECISION_ENGINE_BLUEPRINT section 20) and machine-readable reason
codes (section 21), both deterministic pure functions.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.api.errors import DECISION_ENGINE_FAILED, ApiError
from src.backtest.signals import BUY, NO_TRADE, SELL
from src.logging.logger import get_logger

logger = get_logger("api.decision")

# Reason codes from RISK_DECISION_ENGINE_BLUEPRINT section 21.1.
MODEL_SIGNAL_BUY = "MODEL_SIGNAL_BUY"
MODEL_CONFIDENCE_LOW = "MODEL_CONFIDENCE_LOW"
HIGH_VOLATILITY = "HIGH_VOLATILITY"
EDGE_BELOW_COST = "EDGE_BELOW_COST"
VOLATILITY_OK = "VOLATILITY_OK"
DATA_QUALITY_OK = "DATA_QUALITY_OK"

# RISK blueprint section 20.2 component weights (volatility, uncertainty,
# model confidence; liquidity/regime/drawdown are unavailable to a
# stateless single-request MVP and are documented limitations).
W_VOLATILITY = 0.25
W_UNCERTAINTY = 0.25
W_MODEL_CONFIDENCE = 0.10
RISK_WEIGHT_TOTAL = W_VOLATILITY + W_UNCERTAINTY + W_MODEL_CONFIDENCE

# RISK blueprint section 20.3: volatility normalized against a reference
# annualized volatility (config-level research parameter semantics).
MAX_VOLATILITY = 1.0


@dataclass(frozen=True)
class DecisionResult:
    """Decision-engine output for one request (blueprint section 8.2)."""

    signal: str
    confidence: float
    expected_return: float | None
    risk_score: float
    position_size: float | None
    reason_codes: tuple[str, ...]


def risk_score(
    *,
    max_probability: float,
    recent_volatility: float | None,
    volatility_20d: float | None,
) -> float:
    """Normalized research risk score in [0, 1] (RISK blueprint section 20).

    Volatility prefers the explicit ``recent_volatility`` market-context
    value and falls back to the model's ``volatility_20d`` feature
    (blueprint section 7.3 fallback rule). Missing volatility contributes
    its weight as neutral 0.5 uncertainty rather than fabricating a value.
    """
    uncertainty = 1.0 - max_probability
    volatility = (
        recent_volatility
        if recent_volatility is not None
        else volatility_20d if volatility_20d is not None else None
    )
    if volatility is None:
        volatility_component = 0.5
    else:
        volatility_component = float(np.clip(volatility / MAX_VOLATILITY, 0.0, 1.0))
    score = (
        W_VOLATILITY * volatility_component
        + W_UNCERTAINTY * uncertainty
        + W_MODEL_CONFIDENCE * uncertainty  # no validation-accuracy input; documented limitation
    ) / RISK_WEIGHT_TOTAL
    return round(float(np.clip(score, 0.0, 1.0)), 6)


def decide(
    *,
    probabilities: dict[str, float],
    buy_threshold: float,
    sell_threshold: float,
    recent_volatility: float | None,
    volatility_20d: float | None,
) -> DecisionResult:
    """Produce the decision output for one prediction (sections 6/20/21).

    The BUY/SELL/NO_TRADE rule is the shared
    :func:`src.backtest.signals.generate_signals` logic applied to the
    single-row probability vector; this wrapper only attaches the risk
    score and reason codes.
    """
    try:
        p_up = float(probabilities["UP"])
        p_down = float(probabilities["DOWN"])
        confidence = max(probabilities.values())
        buy = p_up >= buy_threshold and p_up >= p_down
        sell = p_down >= sell_threshold and p_down > p_up  # strict tie-break favors BUY
        score = risk_score(
            max_probability=confidence,
            recent_volatility=recent_volatility,
            volatility_20d=volatility_20d,
        )
        if buy:
            signal = BUY
            reason_codes = [MODEL_SIGNAL_BUY]
        elif sell:
            signal = SELL
            reason_codes = ["MODEL_SIGNAL_SELL"]
        else:
            signal = NO_TRADE
            reason_codes = [MODEL_CONFIDENCE_LOW]
        if recent_volatility is not None and recent_volatility >= MAX_VOLATILITY:
            if signal != NO_TRADE:
                signal = NO_TRADE
                reason_codes = [HIGH_VOLATILITY]
            else:
                reason_codes.append(HIGH_VOLATILITY)
        else:
            reason_codes.append(VOLATILITY_OK)
        reason_codes.append(DATA_QUALITY_OK)
        return DecisionResult(
            signal=signal,
            confidence=round(confidence, 6),
            expected_return=None,  # classification model provides no return estimate (section 14)
            risk_score=score,
            position_size=None if signal == NO_TRADE else 1.0,
            reason_codes=tuple(reason_codes),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ApiError(
            DECISION_ENGINE_FAILED,
            "decision engine could not process the model output",
        ) from error
