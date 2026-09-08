"""Label generation core — LABEL_GENERATION_BLUEPRINT.md.

MVP target (blueprint sections 3-7, 20):

    PRIMARY TARGET   : Direction classification (UP / DOWN / HOLD)
    HORIZON          : H trading days (default 5)
    FORMULA          : future_return = (close_{t+H} - close_t) / close_t
    RULE             : > +threshold_up -> "UP"; < -threshold_down -> "DOWN";
                       otherwise -> "HOLD"
    THRESHOLDS       : fixed 1.0% up / 1.0% down (never tuned on test data)
    RETURN           : simple return (not log)
    TIMING           : close-to-close (entry at close_t, exit at close_{t+H})

Leakage contract: the label at T uses ONLY prices at T and T+H. Missing
future observations are never fabricated — rows become
``INVALID_FUTURE_WINDOW`` and their label is NaN (blueprint section 12).

The generator NEVER mutates its input; feature values are untouched
(TEST A in the leakage suite proves this).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class LabelDistribution:
    """Class/count summary for one generated label set (blueprint section 14/15)."""

    total_rows: int
    valid_rows: int
    up_count: int
    down_count: int
    hold_count: int
    invalid_count: int
    invalid_future_window: int
    invalid_price: int
    up_pct: float
    down_pct: float
    hold_pct: float


@dataclass(frozen=True)
class LabelResult:
    """Output of one label generation run."""

    frame: pd.DataFrame  # original index + future_return / label / status columns
    distribution: LabelDistribution


VALID = "VALID"
INVALID_FUTURE_WINDOW = "INVALID_FUTURE_WINDOW"
INVALID_PRICE = "INVALID_PRICE"


def generate_labels(
    df: pd.DataFrame,
    *,
    horizon: int,
    threshold_up: float,
    threshold_down: float,
    price_column: str,
) -> LabelResult:
    """Generate direction labels for a cleaned price series.

    Args:
        df: cleaned market data with a timestamp index (ascending, unique)
            and the configured price column.
        horizon: prediction horizon H in trading days (must be > 0).
        threshold_up / threshold_down: fixed classification thresholds.
        price_column: source column for the future-return calculation
            (default ``adj_close`` — adjusted prices per blueprint 12.2).

    Returns:
        A :class:`LabelResult` with ``label`` ∈ {UP, DOWN, HOLD, NaN} and
        ``status`` ∈ {VALID, INVALID_FUTURE_WINDOW, INVALID_PRICE}.

    Raises:
        KeyError: if ``price_column`` is missing.
        ValueError: if the index is non-monotonic / duplicated, or the
            horizon is not positive.
    """
    if price_column not in df.columns:
        raise KeyError(f"missing price column {price_column!r} for label generation")
    if horizon <= 0:
        raise ValueError("label horizon must be > 0")
    if not df.index.is_monotonic_increasing:
        raise ValueError("label generation requires ascending timestamps")
    if df.index.has_duplicates:
        raise ValueError("label generation requires unique timestamps")

    price = df[price_column].astype(float)
    price_valid = price.notna() & np.isfinite(price) & (price > 0.0)

    future_price = price.shift(-horizon)
    future_available = future_price.notna() & np.isfinite(future_price) & (future_price > 0.0)

    # Future return only where BOTH current and future prices are valid
    # (division is restricted to valid rows — no inf/0-division artifacts).
    future_return = pd.Series(np.nan, index=df.index, dtype="float64")
    valid_mask = price_valid & future_available
    future_return.loc[valid_mask] = future_price.loc[valid_mask] / price.loc[valid_mask] - 1.0

    labels = pd.Series(np.nan, index=df.index, dtype=object)
    labels.loc[future_return > threshold_up] = "UP"
    labels.loc[future_return < -threshold_down] = "DOWN"
    labels.loc[(future_return >= -threshold_down) & (future_return <= threshold_up)] = "HOLD"

    status = pd.Series(VALID, index=df.index, dtype=object)
    status.loc[~price_valid] = INVALID_PRICE
    status.loc[price_valid & ~future_available] = INVALID_FUTURE_WINDOW
    # A row whose current price is invalid is INVALID_PRICE even when the
    # future observation is also missing.
    status.loc[(~price_valid) & (~future_available)] = INVALID_PRICE

    out = pd.DataFrame(index=df.index)
    out["future_price"] = future_price
    out["future_return"] = future_return
    out["label"] = labels
    out["status"] = status

    distribution = _distribution(out)
    return LabelResult(frame=out, distribution=distribution)


def _distribution(frame: pd.DataFrame) -> LabelDistribution:
    """Compute the class distribution over valid rows (blueprint section 14)."""
    total = len(frame)
    valid = frame[frame["status"] == VALID]
    labels = valid["label"]
    up = int((labels == "UP").sum())
    down = int((labels == "DOWN").sum())
    hold = int((labels == "HOLD").sum())
    invalid_count = total - len(valid)
    invalid_future = int((frame["status"] == INVALID_FUTURE_WINDOW).sum())
    invalid_price = int((frame["status"] == INVALID_PRICE).sum())
    valid_rows = len(valid)
    up_pct = up / valid_rows * 100.0 if valid_rows else 0.0
    down_pct = down / valid_rows * 100.0 if valid_rows else 0.0
    hold_pct = hold / valid_rows * 100.0 if valid_rows else 0.0
    return LabelDistribution(
        total_rows=total,
        valid_rows=valid_rows,
        up_count=up,
        down_count=down,
        hold_count=hold,
        invalid_count=invalid_count,
        invalid_future_window=invalid_future,
        invalid_price=invalid_price,
        up_pct=round(up_pct, 2),
        down_pct=round(down_pct, 2),
        hold_pct=round(hold_pct, 2),
    )
