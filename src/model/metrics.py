"""Classification metrics for baseline model experiments."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.preprocessing import label_binarize

from src.model.loader import CLASSES


def classification_metrics(y_true, y_pred, probabilities, probability_classes) -> dict[str, Any]:
    """Calculate multiclass metrics with stable class ordering."""
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=CLASSES, zero_division=0
    )
    metrics: dict[str, Any] = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_macro": float(precision.mean()),
        "recall_macro": float(recall.mean()),
        "f1_macro": float(f1.mean()),
        "precision": {label: float(value) for label, value in zip(CLASSES, precision)},
        "recall": {label: float(value) for label, value in zip(CLASSES, recall)},
        "f1": {label: float(value) for label, value in zip(CLASSES, f1)},
        "support": {label: int(value) for label, value in zip(CLASSES, support)},
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=CLASSES).tolist(),
        "prediction_distribution": {
            label: int((np.asarray(y_pred) == label).sum()) for label in CLASSES
        },
    }
    if probabilities is not None and set(y_true) == set(CLASSES):
        # sklearn requires an ordered ``labels`` argument; CLASSES is the
        # semantic ordering (UP/DOWN/HOLD), so sort it for metric calls and
        # reorder the probability columns to match.
        ordered = sorted(CLASSES)
        columns = [list(probability_classes).index(label) for label in ordered]
        binarized = label_binarize(np.asarray(y_true), classes=ordered)
        try:
            metrics["roc_auc_ovr_macro"] = float(
                roc_auc_score(y_true, probabilities[:, columns], labels=ordered, multi_class="ovr")
            )
        except ValueError:
            metrics["roc_auc_ovr_macro"] = None
        # One-vs-rest macro PR-AUC (average precision), same applicability rule
        # as ROC-AUC: requires all classes present and probability output.
        try:
            metrics["pr_auc_ovr_macro"] = float(
                average_precision_score(binarized, probabilities[:, columns], average="macro")
            )
        except ValueError:
            metrics["pr_auc_ovr_macro"] = None
    else:
        metrics["roc_auc_ovr_macro"] = None
        metrics["pr_auc_ovr_macro"] = None
    return metrics
