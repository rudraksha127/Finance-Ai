"""Built-in cost/slippage scenario study for the backtest engine (M08 research).

The evaluation interface defined by the milestone supports at least the
following named scenarios, each expressed as a concrete override of the
*active* cost model:

====================  =====  =================================================
Scenario              Role   Assumptions
====================  =====  =================================================
``BASE``              cost   The active ``backtest.costs`` configuration.
``LOW_COST``          cost   Zero-cost research bound: 0 bps per side.
``HIGH_COST``         cost   Stress bound: 25 bps brokerage + 25 bps spread
                             (50 bps per side, 100 bps round trip).
``STRESSED_SLIPPAGE`` slip.  Active brokerage/spread plus a fixed 50 bps
                             slippage component (execution-stress bound).
====================  =====  =================================================

Scenario assumptions are never *optimized* against the evaluation data —
they are fixed, documented research definitions layered on the frozen cost
model (``cost_model_version``). Every scenario reuses the exact signal,
execution, metrics, and reporting code of the static backtest, so results
differ only in the cost/slippage assumptions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.config.loader import BacktestCostConfig
from src.core.errors import StorageError

# Scenario identifiers (milestone: BASE / LOW_COST / HIGH_COST / STRESSED).
BASE = "BASE"
LOW_COST = "LOW_COST"
HIGH_COST = "HIGH_COST"
STRESSED_SLIPPAGE = "STRESSED_SLIPPAGE"

# Fixed stress values (basis points). Explicit constants so a scenario's
# assumptions are auditable; documented in EVALUATION_BACKTESTING
# IMPLEMENTATION.md.
_LOW_COST_BPS = 0.0
_HIGH_COST_BROKERAGE_BPS = 25.0
_HIGH_COST_SPREAD_BPS = 25.0
_STRESSED_SLIPPAGE_BPS = 50.0

COST_ROLE = "cost"
SLIPPAGE_ROLE = "slippage"


@dataclass(frozen=True)
class ScenarioConfig:
    """One named cost/slippage scenario as a concrete bps definition."""

    name: str
    role: str  # "cost" | "slippage"
    brokerage_bps: float
    spread_bps: float
    slippage_bps: float
    description: str

    @property
    def per_side_bps(self) -> float:
        return self.brokerage_bps + self.spread_bps + self.slippage_bps

    @property
    def round_trip_bps(self) -> float:
        return 2.0 * self.per_side_bps

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "brokerage_bps": self.brokerage_bps,
            "spread_bps": self.spread_bps,
            "slippage_bps": self.slippage_bps,
            "per_side_bps": self.per_side_bps,
            "round_trip_bps": self.round_trip_bps,
            "description": self.description,
        }


def cost_scenarios(active: BacktestCostConfig) -> tuple[ScenarioConfig, ...]:
    """Return the four built-in scenarios layered on the active cost model.

    ``BASE`` mirrors the frozen ``active`` configuration exactly; the three
    stress scenarios replace individual components while leaving the rest of
    the active model untouched.
    """
    return (
        ScenarioConfig(
            name=BASE,
            role=COST_ROLE,
            brokerage_bps=active.brokerage_bps,
            spread_bps=active.spread_bps,
            slippage_bps=active.slippage_bps,
            description="Active cost model (frozen backtest.costs)",
        ),
        ScenarioConfig(
            name=LOW_COST,
            role=COST_ROLE,
            brokerage_bps=_LOW_COST_BPS,
            spread_bps=_LOW_COST_BPS,
            slippage_bps=_LOW_COST_BPS,
            description="Zero-cost research bound (0 bps per side)",
        ),
        ScenarioConfig(
            name=HIGH_COST,
            role=COST_ROLE,
            brokerage_bps=_HIGH_COST_BROKERAGE_BPS,
            spread_bps=_HIGH_COST_SPREAD_BPS,
            slippage_bps=0.0,
            description="High-cost stress bound (50 bps per side, 100 bps round trip)",
        ),
        ScenarioConfig(
            name=STRESSED_SLIPPAGE,
            role=SLIPPAGE_ROLE,
            brokerage_bps=active.brokerage_bps,
            spread_bps=active.spread_bps,
            slippage_bps=_STRESSED_SLIPPAGE_BPS,
            description=f"Active model plus {_STRESSED_SLIPPAGE_BPS} bps fixed slippage per side",
        ),
    )


def write_scenario_outputs(
    directory: Path,
    *,
    summary: list[dict[str, Any]],
    definitions: list[dict[str, Any]],
    study_context: dict[str, Any],
) -> dict[str, Path]:
    """Persist the scenario study summary + recorded definitions.

    Each scenario's full artifact set (trade ledger, equity curve, metrics,
    report) is written separately by the engine under its own ``backtest_id``;
    this directory holds the comparison view.
    """
    try:
        directory.mkdir(parents=True, exist_ok=True)
        config_path = directory / "scenario_configs.json"
        summary_path = directory / "scenario_summary.json"
        frame = pd.DataFrame(summary)
        csv_path = directory / "scenario_summary.csv"
        tmp = csv_path.with_suffix(csv_path.suffix + ".tmp")
        frame.to_csv(tmp, index=False)
        tmp.replace(csv_path)
        for path, payload in (
            (config_path, {"study": study_context, "scenarios": definitions}),
            (summary_path, {"study": study_context, "results": summary}),
        ):
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            tmp.replace(path)
    except (OSError, ValueError, RuntimeError) as error:
        raise StorageError(f"cannot write scenario study outputs: {error}") from error
    return {"config": config_path, "summary": summary_path, "csv": csv_path}
