"""Torch-free inference for the temporal LSTM (Post-MVP Milestone 06).

This module implements the LSTM forward pass in pure numpy so artifacts can
be loaded and served WITHOUT importing PyTorch. This is deliberate: on
Windows, loading torch after the backtest/API stack's scipy/sklearn DLLs
fails DLL initialization (WinError 1114). Training happens in torch
(:mod:`src.temporal.model`); inference happens here with numpy only.

The numpy forward pass is numerically equivalent to
``torch.nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)`` +
``nn.Linear`` for single-layer networks (tanh/sigmoid activations), which is
the architecture this project trains.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.model.loader import CLASSES


class TemporalArtifactError(RuntimeError):
    """Raised when a persisted temporal artifact is invalid or corrupt."""


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _lstm_forward_numpy(
    X: np.ndarray,
    *,
    weights_ih: np.ndarray,
    weights_hh: np.ndarray,
    bias_ih: np.ndarray,
    bias_hh: np.ndarray,
) -> np.ndarray:
    """Run one single-layer LSTM over ``X`` and return final hidden states.

    X: [batch, sequence_length, input_size]
    weights_ih: [4*hidden, input]; weights_hh: [4*hidden, hidden]
    Gate order matches torch: i, f, g, o.
    Returns: [batch, hidden]
    """
    hidden_size = np.atleast_2d(bias_ih).shape[1] // 4
    batch_size, sequence_length, _ = X.shape
    h = np.zeros((batch_size, hidden_size), dtype=np.float64)
    c = np.zeros((batch_size, hidden_size), dtype=np.float64)
    w_ih = weights_ih.astype(np.float64)
    w_hh = weights_hh.astype(np.float64)
    bias_ih = np.atleast_2d(bias_ih.astype(np.float64))  # torch stores 1-D biases
    bias_hh = np.atleast_2d(bias_hh.astype(np.float64))
    for step in range(sequence_length):
        x_t = X[:, step, :].astype(np.float64)  # [batch, input]
        gates = x_t @ w_ih.T + bias_ih + h @ w_hh.T + bias_hh
        i_g = _sigmoid(gates[:, 0:hidden_size])
        f_g = _sigmoid(gates[:, hidden_size : 2 * hidden_size])
        g_g = np.tanh(gates[:, 2 * hidden_size : 3 * hidden_size])
        o_g = _sigmoid(gates[:, 3 * hidden_size : 4 * hidden_size])
        c = f_g * c + i_g * g_g
        h = o_g * np.tanh(c)
    return h


class TemporalLSTMClassifier:
    """Sklearn-compatible, torch-free inference wrapper.

    Attributes match what the backtest engine inspects: ``classes_`` is the
    canonical ``("UP", "DOWN", "HOLD")`` order; ``predict_proba`` returns
    probabilities in that order for a standard per-row feature matrix.
    """

    def __init__(
        self,
        *,
        state_dict: dict[str, Any],
        config: dict[str, Any],
        feature_names: tuple[str, ...],
        scaler_mean: np.ndarray,
        scaler_scale: np.ndarray,
        warmup: np.ndarray,
    ):
        self.state_dict = state_dict
        self.config = dict(config)
        self.feature_names = tuple(feature_names)
        self.scaler_mean = np.asarray(scaler_mean, dtype=float)
        self.scaler_scale = np.asarray(scaler_scale, dtype=float)
        self.warmup = np.asarray(warmup, dtype=float)
        self.classes_ = np.asarray(CLASSES)
        self._weights: dict[str, np.ndarray] | None = None

    # ------------------------------------------------------------------
    def _materialize(self) -> dict[str, np.ndarray]:
        if self._weights is None:
            keys = ("lstm.weight_ih_l0", "lstm.weight_hh_l0", "lstm.bias_ih_l0", "lstm.bias_hh_l0")
            missing = [key for key in keys if key not in self.state_dict]
            if missing:
                raise TemporalArtifactError(
                    f"temporal artifact is missing state entries: {missing}"
                )
            if any(key.startswith("lstm.weight_hh_l1") for key in self.state_dict):
                raise TemporalArtifactError(
                    "multi-layer temporal artifacts require torch inference; "
                    "this build serves single-layer models only"
                )
            self._weights = {key: np.asarray(self.state_dict[key]) for key in keys}
        return self._weights

    def _context(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        expected = len(self.feature_names)
        if X.ndim != 2 or X.shape[1] != expected:
            raise ValueError(
                f"temporal model expects {expected} features in registry order, "
                f"received shape {X.shape}"
            )
        scaled = (X - self.scaler_mean) / self.scaler_scale
        if not np.isfinite(scaled).all():
            raise ValueError("temporal model input contains NaN/Inf after scaling")
        length = int(self.config["sequence_length"])
        if len(self.warmup) != length - 1:
            raise TemporalArtifactError(
                "persisted warm-up context has the wrong length; artifact is corrupt"
            )
        return np.vstack([self.warmup, scaled])

    # ------------------------------------------------------------------
    def predict_proba(self, X) -> np.ndarray:
        weights = self._materialize()
        context = self._context(X)
        length = int(self.config["sequence_length"])
        windows = np.stack([context[i : i + length] for i in range(context.shape[0] - length + 1)])
        if windows.shape[0] != len(X):
            raise TemporalArtifactError(
                "internal error: sequence construction did not align 1:1 with input rows"
            )
        hidden = _lstm_forward_numpy(
            windows,
            weights_ih=weights["lstm.weight_ih_l0"],
            weights_hh=weights["lstm.weight_hh_l0"],
            bias_ih=weights["lstm.bias_ih_l0"],
            bias_hh=weights["lstm.bias_hh_l0"],
        )
        logits = hidden @ np.asarray(
            self.state_dict["head.weight"], dtype=np.float64
        ).T + np.asarray(self.state_dict["head.bias"], dtype=np.float64)
        # Softmax over logits (float64 → stable, no torch dependency).
        shifted = logits - logits.max(axis=1, keepdims=True)
        exponentiated = np.exp(shifted)
        return exponentiated / exponentiated.sum(axis=1, keepdims=True)

    def predict(self, X) -> np.ndarray:
        probabilities = self.predict_proba(X)
        return self.classes_[probabilities.argmax(axis=1)]
