"""Multimodal feature generation (Post-MVP Milestone 08).

Combines market features (existing registry) with point-in-time fundamental
and event features. The market columns pass through untouched; the external
columns are produced by :func:`src.multimodal.asoof.asof_frame` from records
whose availability <= each row timestamp. No future information is used —
proven by the mandatory leakage tests in tests/test_multimodal.py.

Sentiment is DEFERRED (milestone section 15): events and factual information
are more reproducible than an opaque sentiment score, and no validated
sentiment model is approved for this project. Embeddings are likewise deferred
(section 16) — compact derived event features are preferred for the MVP.

Fundamental features are the controlled subset from FUNDAMENTAL_FIELDS plus
derived ratios (debt ratio, current ratio proxy, margin). Missing modality
behavior: when no filing is eligible yet, fundamental fields are NaN and the
``has_fundamentals`` flag is 0 — never fabricated (section 41).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.multimodal.asoof import asof_frame
from src.multimodal.contracts import ExternalRecord
from src.multimodal.sources import FUNDAMENTAL_FIELDS

MULTIMODAL_FEATURE_VERSION = "feature_set_v0.2"

EVENT_FEATURES = (
    "events_1d",
    "events_3d",
    "events_7d",
    "hours_since_last_event",
)
FUNDAMENTAL_FEATURES = FUNDAMENTAL_FIELDS + (
    "debt_ratio",
    "margin",
    "has_fundamentals",
)


def build_multimodal_features(
    market_frame: pd.DataFrame,
    records: list[ExternalRecord],
    *,
    instrument: str,
) -> pd.DataFrame:
    """Attach point-in-time external features to a market feature frame.

    The market frame must contain the standard ``timestamp`` column and the
    registered market features. External columns are computed per row from
    eligible-only records (availability <= row timestamp).
    """
    if market_frame.empty:
        raise ValueError("market frame is empty")
    if "timestamp" not in market_frame.columns:
        raise ValueError("market frame must contain a 'timestamp' column")

    timestamps = pd.DatetimeIndex(pd.to_datetime(market_frame["timestamp"]))
    external = asof_frame(
        records,
        instrument=instrument,
        timestamps=timestamps,
        fundamental_fields=FUNDAMENTAL_FIELDS,
    ).set_index("timestamp")

    output = market_frame.copy()
    for column in FUNDAMENTAL_FIELDS + EVENT_FEATURES:
        if column in external.columns:
            output[column] = external[column].to_numpy()
        else:
            output[column] = np.nan

    # Derived fundamental ratios (controlled MVP subset, section 9).
    assets = pd.to_numeric(output["total_assets"], errors="coerce")
    liabilities = pd.to_numeric(output["total_liabilities"], errors="coerce")
    revenue = pd.to_numeric(output["revenue"], errors="coerce")
    net_income = pd.to_numeric(output["net_income"], errors="coerce")
    with np.errstate(divide="ignore", invalid="ignore"):
        output["debt_ratio"] = np.where(assets > 0, liabilities / assets, np.nan)
        output["margin"] = np.where(revenue != 0, net_income / revenue, np.nan)
    output["has_fundamentals"] = output["revenue"].notna().astype(int)
    return output


def multimodal_feature_columns() -> tuple[str, ...]:
    """External feature columns added by this milestone (for drift/registry)."""
    return FUNDAMENTAL_FEATURES + EVENT_FEATURES
