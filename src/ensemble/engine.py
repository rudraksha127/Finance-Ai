"""Ensemble & probability calibration (Post-MVP Milestone 07).

Answers — with measurements, not assumptions — whether the baseline and
temporal models are complementary, then implements a controlled ensemble:

- out-of-sample validation predictions of both constituents (their
  chronological VAL split; no fold ever saw its own target rows);
- explicit class-order alignment (canonical ``("UP", "DOWN", "HOLD")``,
  never inferred from column position);
- simple average and validation-derived weighted average strategies
  (constrained grid; no unrestricted optimization; final test untouched);
- Platt-style multinomial logistic calibration fitted on VALIDATION only
  and frozen before any final-test evaluation;
- a torch-free ``EnsemblePredictor`` artifact in the standard model layout
  so the existing backtest engine, registry, and API work unchanged.

Failure handling is fail-loud: version mismatches, class-order mismatches,
timestamp misalignment, and invalid probabilities raise with context.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from src.config.loader import AppConfig
from src.logging.logger import get_logger
from src.model.loader import CLASSES

logger = get_logger("ensemble.engine")

CLASS_ORDER = tuple(CLASSES)  # ("UP", "DOWN", "HOLD") — the canonical order


class EnsembleError(Exception):
    """Ensemble failure with an explicit, safe message."""


# ---------------------------------------------------------------------------
# Diversity analysis (milestone section 5/18)
# ---------------------------------------------------------------------------
def diversity_analysis(
    probabilities_a: np.ndarray,
    probabilities_b: np.ndarray,
    predictions_a: np.ndarray,
    predictions_b: np.ndarray,
) -> dict[str, float]:
    """Measure complementarity of two constituents on aligned validation rows."""
    if probabilities_a.shape != probabilities_b.shape:
        raise EnsembleError(
            f"probability shape mismatch: {probabilities_a.shape} vs {probabilities_b.shape}"
        )
    up_index = CLASS_ORDER.index("UP")
    agreement = float(np.mean(predictions_a == predictions_b))
    prob_disagreement = float(
        np.mean(np.abs(probabilities_a[:, up_index] - probabilities_b[:, up_index]))
    )
    correlation = float(
        np.corrcoef(probabilities_a[:, up_index], probabilities_b[:, up_index])[0, 1]
    )
    return {
        "prediction_agreement": round(agreement, 6),
        "mean_absolute_prob_disagreement": round(prob_disagreement, 6),
        "probability_correlation_up": round(correlation, 6),
        "diverse": bool(agreement < 0.95 and correlation < 0.98),
    }


# ---------------------------------------------------------------------------
# Weighted ensemble (section 15-17): constrained grid, validation-only
# ---------------------------------------------------------------------------
def blended_probabilities(
    probabilities_a: np.ndarray, probabilities_b: np.ndarray, weight: float
) -> np.ndarray:
    """P = weight * P_A + (1 - weight) * P_B with explicit class-order inputs."""
    if not 0.0 <= weight <= 1.0:
        raise EnsembleError(f"ensemble weight must be within [0, 1], got {weight}")
    blended = weight * probabilities_a + (1.0 - weight) * probabilities_b
    if not np.isfinite(blended).all():
        raise EnsembleError("blended probabilities contain NaN/Inf")
    return blended


def select_weight(
    probabilities_a: np.ndarray,
    probabilities_b: np.ndarray,
    labels: np.ndarray,
    *,
    candidates: tuple[float, ...] = tuple(round(0.1 * step, 1) for step in range(11)),
) -> tuple[float, dict[str, float]]:
    """Pick the weight minimizing validation multiclass log loss (constrained grid).

    The labels of aligned validation rows are the ONLY supervision used; the
    final test period is never passed here (final-test protection).
    """
    label_index = {label: index for index, label in enumerate(CLASS_ORDER)}
    try:
        y_true = np.asarray([label_index[label] for label in labels])
    except KeyError as error:
        raise EnsembleError(f"validation labels outside {CLASS_ORDER}: {error}") from error
    scores: dict[str, float] = {}
    best_weight, best_loss = None, float("inf")
    for weight in candidates:
        blended = blended_probabilities(probabilities_a, probabilities_b, weight)
        shifted = blended - blended.max(axis=1, keepdims=True)
        log_probs = shifted - np.log(np.exp(shifted).sum(axis=1, keepdims=True))
        loss = float(-log_probs[np.arange(len(y_true)), y_true].mean())
        scores[str(weight)] = round(loss, 6)
        if loss < best_loss - 1e-12:
            best_weight, best_loss = weight, loss
    if best_weight is None:
        raise EnsembleError("weight selection produced no candidate")
    return best_weight, scores


# ---------------------------------------------------------------------------
# Calibration (section 10-13): validation-only, frozen before final test
# ---------------------------------------------------------------------------
def fit_calibration(blended: np.ndarray, labels: np.ndarray) -> dict[str, Any]:
    """Fit a multinomial logistic (Platt-style) calibrator on validation rows.

    Returns the versioned calibration payload (coefficients + identity) that
    is persisted and embedded in the predictor artifact.
    """
    from sklearn.linear_model import LogisticRegression

    # Fit on the STRING labels so estimator.classes_ carries class identity
    # (fitting on indices would make the coef_order mapping meaningless).
    y_true = np.asarray(labels)
    estimator = LogisticRegression(max_iter=1000, C=1.0)
    estimator.fit(blended, y_true)
    # classes_ is alphabetical (DOWN, HOLD, UP); store the explicit mapping so
    # inference never infers class order from column position.
    coef_order = [str(label) for label in estimator.classes_]
    calibrated = estimator.predict_proba(blended)
    return {
        "calibration_version": "calibration_v0.1",
        "method": "multinomial_logistic_platt",
        "fitted_on": "validation_out_of_sample",
        "coef_order": coef_order,
        "coefficients": estimator.coef_.tolist(),
        "intercept": estimator.intercept_.tolist(),
        "fitted_at": datetime.now(timezone.utc).isoformat(),
        "diagnostics": _calibration_diagnostics(blended, calibrated, labels),
    }


def apply_calibration(blended: np.ndarray, calibration: dict[str, Any]) -> np.ndarray:
    """Apply a frozen calibration payload; unknown order fails loudly."""
    if calibration.get("method") != "multinomial_logistic_platt":
        raise EnsembleError(f"unsupported calibration method: {calibration.get('method')!r}")
    coef_order = list(calibration["coef_order"])
    coefficients = np.asarray(calibration["coefficients"], dtype=float)
    intercept = np.asarray(calibration["intercept"], dtype=float)
    columns = [blended[:, CLASS_ORDER.index(label)] for label in coef_order]
    features = np.column_stack(columns)
    logits = features @ coefficients.T + intercept
    shifted = logits - logits.max(axis=1, keepdims=True)
    exponentiated = np.exp(shifted)
    probabilities = exponentiated / exponentiated.sum(axis=1, keepdims=True)
    # Reorder from coef_order back to the canonical CLASS_ORDER.
    output = np.empty_like(probabilities)
    for source, label in enumerate(coef_order):
        output[:, CLASS_ORDER.index(label)] = probabilities[:, source]
    return output


def _calibration_diagnostics(
    raw: np.ndarray, calibrated: np.ndarray, labels: np.ndarray
) -> dict[str, float]:
    """Brier score + ECE (10 confidence bins) for raw vs calibrated."""
    label_index = {label: index for index, label in enumerate(CLASS_ORDER)}
    y_true = np.asarray([label_index[label] for label in labels])
    one_hot = np.eye(len(CLASS_ORDER))[y_true]

    def brier(probabilities: np.ndarray) -> float:
        return float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1)))

    def ece(probabilities: np.ndarray) -> float:
        confidence = probabilities.max(axis=1)
        predicted = probabilities.argmax(axis=1)
        correct = (predicted == y_true).astype(float)
        total = len(confidence)
        score = 0.0
        for bin_index in range(10):
            lower, upper = bin_index / 10.0, (bin_index + 1) / 10.0
            mask = (
                (confidence > lower) & (confidence <= upper)
                if bin_index
                else ((confidence >= lower) & (confidence <= upper))
            )
            if mask.any():
                score += mask.sum() / total * abs(correct[mask].mean() - confidence[mask].mean())
        return float(score)

    return {
        "brier_raw": round(brier(raw), 6),
        "brier_calibrated": round(brier(calibrated), 6),
        "ece_raw_10bin": round(ece(raw), 6),
        "ece_calibrated_10bin": round(ece(calibrated), 6),
    }


# ---------------------------------------------------------------------------
# Torch-free predictor artifact (section 6)
# ---------------------------------------------------------------------------
class EnsemblePredictor:
    """Sklearn-compatible ensemble wrapper persisted in ``model.joblib``.

    Embeds both constituent wrappers (the temporal wrapper is numpy-only) and
    the frozen calibration payload. ``predict`` / ``predict_proba`` follow the
    baseline estimator contract with ``classes_ = ("UP", "DOWN", "HOLD")``.
    """

    def __init__(
        self,
        *,
        constituent_a: Any,
        constituent_b: Any,
        weight: float,
        calibration: dict[str, Any],
        metadata: dict[str, Any],
    ):
        self.constituent_a = constituent_a
        self.constituent_b = constituent_b
        self.weight = float(weight)
        self.calibration = calibration
        self.metadata = dict(metadata)
        self.classes_ = np.asarray(CLASS_ORDER)

    def _probabilities(self, X) -> tuple[np.ndarray, np.ndarray]:
        probabilities_a = _aligned_probabilities(self.constituent_a, X)
        probabilities_b = _aligned_probabilities(self.constituent_b, X)
        blended = blended_probabilities(probabilities_a, probabilities_b, self.weight)
        if self.calibration:
            blended = apply_calibration(blended, self.calibration)
        if not np.isfinite(blended).all():
            raise EnsembleError("ensemble produced non-finite probabilities")
        return blended, probabilities_a

    def predict_proba(self, X) -> np.ndarray:
        blended, _ = self._probabilities(X)
        return blended

    def predict(self, X) -> np.ndarray:
        blended, _ = self._probabilities(X)
        return self.classes_[blended.argmax(axis=1)]


def _aligned_probabilities(constituent: Any, X) -> np.ndarray:
    """Get probabilities from any constituent in canonical class order."""
    probabilities = constituent.predict_proba(X)
    probabilities = np.asarray(probabilities, dtype=float)
    classes = [str(label) for label in getattr(constituent, "classes_", CLASS_ORDER)]
    if sorted(classes) != sorted(CLASS_ORDER):
        raise EnsembleError(f"constituent classes {classes} do not match {list(CLASS_ORDER)}")
    if probabilities.shape[1] != len(CLASS_ORDER):
        raise EnsembleError(f"constituent returned {probabilities.shape[1]} probability columns")
    # Explicit reordering from the constituent's classes_ to canonical order.
    columns = [probabilities[:, classes.index(label)] for label in CLASS_ORDER]
    aligned = np.column_stack(columns)
    if not np.isfinite(aligned).all():
        raise EnsembleError("constituent produced non-finite probabilities")
    sums = aligned.sum(axis=1)
    if not np.allclose(sums, 1.0, atol=1e-6):
        raise EnsembleError("constituent probability rows do not sum to 1")
    return aligned


# ---------------------------------------------------------------------------
# Builder (section 32): diversity -> weights -> calibration -> artifact
# ---------------------------------------------------------------------------
@dataclass
class EnsembleResult:
    experiment_id: str
    model_version: str
    weight: float
    diversity: dict[str, float]
    weight_scores: dict[str, float]
    calibration: dict[str, Any]
    validation_metrics: dict[str, Any]
    model_dir: Path
    experiment_dir: Path


def _load_constituents(config: AppConfig, versions: tuple[str, str]) -> tuple[Any, Any, dict, dict]:
    model_root = config.model.artifact_dir
    model_root = model_root if model_root.is_absolute() else Path.cwd() / model_root
    loaded = []
    for version in versions:
        directory = model_root / version
        artifact = directory / "model.joblib"
        metadata_path = directory / "metadata.json"
        if not artifact.exists() or not metadata_path.exists():
            raise EnsembleError(f"constituent artifact {version} not found at {directory}")
        wrapper = joblib.load(artifact)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        loaded.append((wrapper, metadata))
    (wrapper_a, metadata_a), (wrapper_b, metadata_b) = loaded
    for key in ("dataset_version", "feature_version", "label_version"):
        if str(metadata_a[key]) != str(metadata_b[key]):
            raise EnsembleError(
                f"constituent {key} mismatch: {metadata_a[key]} vs {metadata_b[key]}"
            )
    return wrapper_a, wrapper_b, metadata_a, metadata_b


def _load_validation_predictions(
    config: AppConfig, metadata_a: dict, metadata_b: dict
) -> pd.DataFrame:
    """Load both constituents' val_predictions.csv and align by timestamp."""
    experiment_root = config.model.artifact_dir / "experiments"
    experiment_root = (
        experiment_root if experiment_root.is_absolute() else Path.cwd() / experiment_root
    )
    frames = []
    for metadata in (metadata_a, metadata_b):
        path = experiment_root / metadata["experiment_id"] / "val_predictions.csv"
        if not path.exists():
            raise EnsembleError(
                f"validation predictions for {metadata['model_version']} not found at {path}"
            )
        frames.append(pd.read_csv(path))
    aligned = frames[0].merge(
        frames[1], on=["ticker", "timestamp", "label"], suffixes=("_a", "_b"), validate="one_to_one"
    )
    if aligned.empty:
        raise EnsembleError("constituent validation predictions do not align on timestamps")
    return aligned


class EnsembleBuilder:
    """Build, evaluate, and persist the controlled ensemble (validation only)."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def run(
        self,
        *,
        versions: tuple[str, str],
        model_version: str = "ensemble_v0.1",
        use_calibration: bool = True,
        experiment_id: str | None = None,
    ) -> EnsembleResult:
        wrapper_a, wrapper_b, metadata_a, metadata_b = _load_constituents(self.config, versions)
        aligned = _load_validation_predictions(self.config, metadata_a, metadata_b)

        # Aligned probability matrices in canonical class order.
        probabilities_a = aligned[[f"probability_{label}_a" for label in CLASS_ORDER]].to_numpy(
            dtype=float
        )
        probabilities_b = aligned[[f"probability_{label}_b" for label in CLASS_ORDER]].to_numpy(
            dtype=float
        )
        labels = aligned["label"].to_numpy()

        diversity = diversity_analysis(
            probabilities_a,
            probabilities_b,
            aligned["prediction_a"].to_numpy(),
            aligned["prediction_b"].to_numpy(),
        )

        # --- strategy A: simple average ---
        simple = blended_probabilities(probabilities_a, probabilities_b, 0.5)
        # --- strategy B: validation-derived weight (constrained grid) ---
        weight, weight_scores = select_weight(probabilities_a, probabilities_b, labels)

        blended = blended_probabilities(probabilities_a, probabilities_b, weight)
        calibration: dict[str, Any] = {}
        if use_calibration:
            calibration = fit_calibration(blended, labels)
            blended = apply_calibration(blended, calibration)

        metrics = self._validation_metrics(blended, labels)

        experiment_id = experiment_id or (f"ens_exp_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}")
        result = EnsembleResult(
            experiment_id=experiment_id,
            model_version=model_version,
            weight=weight,
            diversity=diversity,
            weight_scores=weight_scores,
            calibration=calibration,
            validation_metrics=metrics,
            model_dir=Path(),
            experiment_dir=Path(),
        )
        self._persist(
            result=result,
            wrapper_a=wrapper_a,
            wrapper_b=wrapper_b,
            metadata_a=metadata_a,
            metadata_b=metadata_b,
            simple_metrics=self._validation_metrics(simple, labels),
        )
        logger.info(
            "ensemble_built",
            model_version=model_version,
            weight=weight,
            diverse=diversity["diverse"],
            agreement=diversity["prediction_agreement"],
            status="COMPLETED",
        )
        return result

    # ------------------------------------------------------------------
    def _validation_metrics(self, probabilities: np.ndarray, labels: np.ndarray) -> dict[str, Any]:
        from src.model.metrics import classification_metrics

        predictions = np.asarray(CLASS_ORDER)[probabilities.argmax(axis=1)]
        return classification_metrics(labels, predictions, probabilities, CLASS_ORDER)

    def _artifact_root(self) -> Path:
        path = self.config.model.artifact_dir
        return path if path.is_absolute() else Path.cwd() / path

    def _persist(
        self,
        *,
        result: EnsembleResult,
        wrapper_a,
        wrapper_b,
        metadata_a: dict,
        metadata_b: dict,
        simple_metrics: dict[str, Any],
    ) -> None:
        model_dir = self._artifact_root() / result.model_version
        experiment_dir = self._artifact_root() / "experiments" / result.experiment_id
        try:
            if model_dir.exists():
                raise EnsembleError(f"ensemble version already exists: {result.model_version}")
            model_dir.mkdir(parents=True, exist_ok=True)
            experiment_dir.mkdir(parents=True, exist_ok=True)

            predictor = EnsemblePredictor(
                constituent_a=wrapper_a,
                constituent_b=wrapper_b,
                weight=result.weight,
                calibration=result.calibration,
                metadata={
                    "constituents": [metadata_a["model_version"], metadata_b["model_version"]],
                    "weight_strategy": "validation_logloss_grid",
                },
            )
            metadata = {
                "experiment_id": result.experiment_id,
                "model_version": result.model_version,
                "model_name": "ensemble",
                "model_type": "ensemble",
                "config_version": self.config.model.config_version,
                "dataset_version": metadata_a["dataset_version"],
                "feature_version": metadata_a["feature_version"],
                "label_version": metadata_a["label_version"],
                "constituents": [metadata_a["model_version"], metadata_b["model_version"]],
                "constituent_experiments": [
                    metadata_a["experiment_id"],
                    metadata_b["experiment_id"],
                ],
                "weight": result.weight,
                "weight_strategy": "validation_logloss_grid",
                "weight_scores": result.weight_scores,
                "simple_average_metrics": simple_metrics,
                "diversity": result.diversity,
                "calibration_version": result.calibration.get("calibration_version"),
                "metrics": result.validation_metrics,
                "training_timestamp": datetime.now(timezone.utc).isoformat(),
                "final_test_policy": (
                    "weights/calibration frozen on validation before any test evaluation"
                ),
            }
            (experiment_dir / "metadata.json").write_text(
                json.dumps(metadata, indent=2, sort_keys=True, default=str) + "\n",
                encoding="utf-8",
            )
            joblib.dump(predictor, model_dir / "model.joblib")
            (model_dir / "metadata.json").write_text(
                json.dumps(metadata, indent=2, sort_keys=True, default=str) + "\n",
                encoding="utf-8",
            )
        except (OSError, ValueError) as error:
            raise EnsembleError(f"cannot persist ensemble artifacts: {error}") from error
        result.model_dir = model_dir
        result.experiment_dir = experiment_dir
