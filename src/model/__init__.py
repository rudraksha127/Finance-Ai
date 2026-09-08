"""Approved baseline-model training and experiment artifacts."""

try:
    import lightgbm  # noqa: F401
except ImportError:
    pass

from src.model.trainer import BaselineTrainer, TrainingResult

__all__ = ["BaselineTrainer", "TrainingResult"]
