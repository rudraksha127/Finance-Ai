"""Model wrappers for third-party gradient boosting libraries.

Provides clean scikit-learn compatible estimator interfaces for XGBoost
supporting string class labels (UP, DOWN, HOLD) and seamless serialization.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier


class XGBoostClassifierWrapper(BaseEstimator, ClassifierMixin):
    """Wrap XGBClassifier to seamlessly handle string targets (UP, DOWN, HOLD)."""

    def __init__(self, **params: Any) -> None:
        self.params = dict(params)
        self._model = XGBClassifier(**self.params)
        self._encoder = LabelEncoder()
        self.classes_: np.ndarray | None = None
        self.feature_importances_: np.ndarray | None = None

    def fit(self, X: Any, y: Any, **fit_params: Any) -> XGBoostClassifierWrapper:
        """Fit the label encoder and the underlying XGBoost model."""
        y_array = np.asarray(y)
        y_encoded = self._encoder.fit_transform(y_array)
        self.classes_ = np.asarray(self._encoder.classes_)
        self._model.fit(X, y_encoded, **fit_params)
        self.feature_importances_ = getattr(self._model, "feature_importances_", None)
        return self

    def predict(self, X: Any) -> np.ndarray:
        """Predict classes mapped back to original string labels."""
        preds_encoded = self._model.predict(X)
        return self._encoder.inverse_transform(preds_encoded)

    def predict_proba(self, X: Any) -> np.ndarray:
        """Predict class probabilities."""
        return self._model.predict_proba(X)

    def get_params(self, deep: bool = True) -> dict[str, Any]:
        """Return parameters for scikit-learn cloning/inspection."""
        return dict(self.params)

    def set_params(self, **params: Any) -> XGBoostClassifierWrapper:
        """Set parameters on wrapper and underlying model."""
        self.params.update(params)
        self._model.set_params(**params)
        return self
