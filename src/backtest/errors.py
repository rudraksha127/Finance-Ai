"""Typed error taxonomy for the evaluation & backtesting engine (M08).

Follows ENGINEERING_CONSTITUTION section 3: failures are explicit, never
silently swallowed. The backtest engine reuses the dataset/model error
hierarchy for version and schema problems (``src.model.errors``); this
module defines the backtest-specific categories.
"""

from __future__ import annotations

from typing import Any


class BacktestError(Exception):
    """Base class for all backtest-engine errors."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}


class DataQualityError(BacktestError):
    """A data-quality gate check failed (EVALUATION_BACKTESTING_BLUEPRINT section 3).

    The backtest must abort — never proceed with degraded data.
    """


class EmptyTestSetError(BacktestError):
    """The evaluation period contains no rows after filtering."""


class ExecutionError(BacktestError):
    """Trade simulation reached an invalid state (bad price, position, timing)."""


class MetricsError(BacktestError):
    """A financial metric could not be computed from the given inputs."""


class ReportError(BacktestError):
    """Backtest outputs could not be written to disk."""


class WalkForwardError(BacktestError):
    """Walk-forward fold generation or execution failed."""
