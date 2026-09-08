"""Drift statistics (P02) — PSI, KS, distribution summaries, severity.

All functions are pure and deterministic (reproducibility, milestone §33).

Threshold strategy (documented in docs/DRIFT_DETECTION_IMPLEMENTATION.md §2):
- PSI < 0.10 GREEN, 0.10-0.25 YELLOW, > 0.25 RED (industry-standard bands)
- KS p < 0.01 flags YELLOW (with Benjamini-Hochberg FDR across features)
- Minimum current-window size below which results are INSUFFICIENT_DATA
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

# Per-milestone magic thresholds; config-driven at the engine level.
PSI_GREEN_MAX = 0.10
PSI_YELLOW_MAX = 0.25
MIN_SAMPLE = 30


@dataclass(frozen=True)
class FeatureDrift:
    """Drift summary for one feature."""

    feature: str
    psi: float
    ks_statistic: float | None
    ks_pvalue: float | None
    ref_mean: float
    cur_mean: float
    ref_std: float
    cur_std: float
    ref_missing: float  # fraction
    cur_missing: float
    severity: str  # GREEN | YELLOW | RED | INSUFFICIENT_DATA


def _psi(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index between two numeric samples.

    Bins are built on the pooled quantiles so both samples share the same
    edges (avoids empty-reference-bin division). Ties are handled by
    integer binning on a shared rounded scale.
    """
    ref = np.asarray(reference, dtype=float)
    cur = np.asarray(current, dtype=float)
    ref = ref[np.isfinite(ref)]
    cur = cur[np.isfinite(cur)]
    if len(ref) == 0 or len(cur) == 0:
        return float("inf")
    pooled = np.concatenate([ref, cur])
    if np.allclose(np.min(pooled), np.max(pooled)):  # constant feature
        return 0.0
    edges = np.quantile(pooled, np.linspace(0, 1, bins + 1))
    edges = np.unique(edges)
    if len(edges) < 2:
        return 0.0
    ref_hist, _ = np.histogram(ref, bins=edges)
    cur_hist, _ = np.histogram(cur, bins=edges)
    ref_pct = ref_hist / max(len(ref), 1) + 1e-6
    cur_pct = cur_hist / max(len(cur), 1) + 1e-6
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def _severity_from_psi(psi: float, n_current: int) -> str:
    if n_current < MIN_SAMPLE:
        return "INSUFFICIENT_DATA"
    if psi >= PSI_YELLOW_MAX:
        return "RED"
    if psi >= PSI_GREEN_MAX:
        return "YELLOW"
    return "GREEN"


def _ks(feature_ref: np.ndarray, feature_cur: np.ndarray) -> tuple[float | None, float | None]:
    ref = feature_ref[np.isfinite(feature_ref)]
    cur = feature_cur[np.isfinite(feature_cur)]
    if len(ref) < 5 or len(cur) < 5:
        return None, None
    try:
        stat, p = ks_2samp(ref, cur)
        return float(stat), float(p)
    except ValueError:
        return None, None


def feature_drift(
    reference: pd.DataFrame, current: pd.DataFrame, features: list[str]
) -> list[FeatureDrift]:
    """Compute per-feature drift between two aligned windows.

    ``reference``/``current`` are DataFrames of feature columns only.
    Returns one FeatureDrift per feature, sorted by descending PSI.
    """
    results: list[FeatureDrift] = []
    for feature in features:
        if feature not in reference.columns or feature not in current.columns:
            continue
        ref = reference[feature].to_numpy(dtype=float, na_value=np.nan)
        cur = current[feature].to_numpy(dtype=float, na_value=np.nan)
        ref_valid = ref[np.isfinite(ref)]
        cur_valid = cur[np.isfinite(cur)]
        psi = _psi(ref, cur)
        stat, p = _ks(ref, cur)
        results.append(
            FeatureDrift(
                feature=feature,
                psi=round(psi, 4),
                ks_statistic=round(stat, 4) if stat is not None else None,
                ks_pvalue=round(p, 6) if p is not None else None,
                ref_mean=round(float(np.nanmean(ref)) if len(ref_valid) else float("nan"), 4),
                cur_mean=round(float(np.nanmean(cur)) if len(cur_valid) else float("nan"), 4),
                ref_std=round(float(np.nanstd(ref)) if len(ref_valid) > 1 else float("nan"), 4),
                cur_std=round(float(np.nanstd(cur)) if len(cur_valid) > 1 else float("nan"), 4),
                ref_missing=round(float(np.isnan(ref).mean()), 4),
                cur_missing=round(float(np.isnan(cur).mean()), 4),
                severity=_severity_from_psi(psi, len(cur_valid)),
            )
        )
    return sorted(results, key=lambda r: r.psi, reverse=True)


def missingness_drift(
    reference: pd.DataFrame, current: pd.DataFrame, features: list[str]
) -> FeatureDrift | None:
    """Single aggregated missingness signal (milestone §13)."""
    if not features:
        return None
    ref_missing = float(reference[features].isna().mean().mean())
    cur_missing = float(current[features].isna().mean().mean())
    delta = cur_missing - ref_missing
    severity = "GREEN" if delta < 0.02 else ("YELLOW" if delta < 0.10 else "RED")
    return FeatureDrift(
        feature="__aggregate_missingness__",
        psi=round(abs(delta) * 100, 4),
        ks_statistic=None,
        ks_pvalue=None,
        ref_mean=round(ref_missing, 4),
        cur_mean=round(cur_missing, 4),
        ref_std=0.0,
        cur_std=0.0,
        ref_missing=round(ref_missing, 4),
        cur_missing=round(cur_missing, 4),
        severity=severity,
    )


def prediction_drift(ref_probs: np.ndarray, cur_probs: np.ndarray, n_classes: int = 3) -> str:
    """Prediction-distribution drift severity from class-probability vectors.

    Uses PSI on the predicted-class proportions (UP/DOWN/HOLD).
    """
    ref_classes = np.argmax(ref_probs, axis=1) if ref_probs.ndim == 2 else ref_probs
    cur_classes = np.argmax(cur_probs, axis=1) if cur_probs.ndim == 2 else cur_probs
    ref_pct = np.bincount(ref_classes, minlength=n_classes) / max(len(ref_classes), 1)
    cur_pct = np.bincount(cur_classes, minlength=n_classes) / max(len(cur_classes), 1)
    ref_pct = ref_pct + 1e-6
    cur_pct = cur_pct + 1e-6
    psi = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
    return _severity_from_psi(psi, len(cur_classes))


def performance_status(baseline_accuracy: float, current_accuracy: float, n_current: int) -> str:
    """Performance degradation status (milestone §18/§19).

    Rules: WARNING when accuracy drops >= 5pp below baseline with >= 30
    samples; CRITICAL when >= 10pp below with >= 60 samples. Below the
    minimum sample -> INSUFFICIENT_DATA. Persistence (2 consecutive checks)
    is enforced at the engine level.
    """
    if n_current < MIN_SAMPLE:
        return "INSUFFICIENT_DATA"
    drop = baseline_accuracy - current_accuracy
    if drop >= 0.10 and n_current >= 60:
        return "CRITICAL"
    if drop >= 0.05:
        return "WARNING"
    return "GREEN"


def fdr_correct(pvalues: list[float | None]) -> list[float | None]:
    """Benjamini-Hochberg FDR correction (milestone §12).

    None entries (missing KS) pass through unchanged.
    """
    valid_idx = [i for i, p in enumerate(pvalues) if p is not None]
    if not valid_idx:
        return pvalues
    out = list(pvalues)
    vals = sorted((pvalues[i], i) for i in valid_idx)
    n = len(vals)
    for rank, (p, i) in enumerate(vals, start=1):
        q = p * n / rank
        out[i] = round(min(q, 1.0), 6)
    # enforce monotonicity (largest q = min of suffix)
    for k in range(n - 2, -1, -1):
        out[vals[k][1]] = min(out[vals[k][1]], out[vals[k + 1][1]]) or out[vals[k][1]]
    return out
