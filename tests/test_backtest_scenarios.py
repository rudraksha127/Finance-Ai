"""Tests for the built-in cost/slippage scenario study (M08 research extension).

Covers the scenario definitions (BASE mirrors the active cost model, stress
bounds are fixed and ordered) and the end-to-end study run: identical
deterministic execution across scenarios, cost monotonicity, and persisted
summary artifacts with the scenario recorded in each run's metadata.
"""

from __future__ import annotations

import json

import pytest

from src.backtest.engine import BacktestEngine
from src.backtest.scenarios import (
    BASE,
    HIGH_COST,
    LOW_COST,
    STRESSED_SLIPPAGE,
    cost_scenarios,
)
from src.config.loader import BacktestCostConfig
from src.model.trainer import BaselineTrainer
from tests.backtest_helpers import TICKER, build_backtest_fixture

SCENARIO_ORDER = (BASE, LOW_COST, HIGH_COST, STRESSED_SLIPPAGE)


def _train(config) -> str:
    result = BaselineTrainer(config).run(
        model_name="random_forest",
        model_version="baseline_rf_scenarios_test",
        experiment_id="exp_scenarios_test",
    )
    return result.model_version


def _by_name(scenarios):
    return {scenario.name: scenario for scenario in scenarios}


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------
def test_base_scenario_mirrors_active_cost_model():
    active = BacktestCostConfig(brokerage_bps=7.0, spread_bps=3.0, slippage_bps=2.0)
    scenarios = _by_name(cost_scenarios(active))
    base = scenarios[BASE]
    assert base.per_side_bps == active.per_side_bps == 12.0
    assert (base.brokerage_bps, base.spread_bps, base.slippage_bps) == (7.0, 3.0, 2.0)


def test_all_four_scenarios_present_in_documented_order():
    scenarios = cost_scenarios(BacktestCostConfig())
    assert [scenario.name for scenario in scenarios] == list(SCENARIO_ORDER)
    roles = {scenario.name: scenario.role for scenario in scenarios}
    assert roles[LOW_COST] == "cost" and roles[HIGH_COST] == "cost"
    assert roles[STRESSED_SLIPPAGE] == "slippage"


def test_stress_bounds_are_fixed_and_ordered():
    active = BacktestCostConfig(brokerage_bps=5.0, spread_bps=5.0, slippage_bps=0.0)
    scenarios = _by_name(cost_scenarios(active))
    assert scenarios[LOW_COST].per_side_bps == 0.0
    assert scenarios[HIGH_COST].per_side_bps == 50.0
    assert scenarios[STRESSED_SLIPPAGE].per_side_bps == 60.0  # active 10 + 50 slippage
    per_side = {name: scenarios[name].per_side_bps for name in SCENARIO_ORDER}
    assert per_side[LOW_COST] <= per_side[BASE] < per_side[HIGH_COST] < per_side[STRESSED_SLIPPAGE]


# ---------------------------------------------------------------------------
# End-to-end study
# ---------------------------------------------------------------------------
def test_scenario_study_runs_end_to_end_with_cost_monotonicity(tmp_path):
    config = build_backtest_fixture(tmp_path, n_train=80, n_val=30, n_test=25)
    model_version = _train(config)
    study = BacktestEngine(config).run_scenarios(
        ticker=TICKER,
        model_version=model_version,
        split="test",
        backtest_id="bt_scen_test",
    )

    assert [row["scenario"] for row in study.rows] == list(SCENARIO_ORDER)
    # Deterministic execution: cost changes never change the trade set.
    trade_counts = {row["scenario"]: row["number_of_trades"] for row in study.rows}
    assert len(set(trade_counts.values())) == 1

    total_costs = {row["scenario"]: row["total_costs"] for row in study.rows}
    total_net = {row["scenario"]: row["total_net_pnl"] for row in study.rows}
    if trade_counts[BASE] > 0:
        # Same trades -> higher per-side costs mean strictly higher costs and
        # strictly lower net P&L.
        assert total_costs[LOW_COST] <= total_costs[BASE] < total_costs[HIGH_COST]
        assert total_costs[STRESSED_SLIPPAGE] > total_costs[BASE]
        assert total_net[LOW_COST] >= total_net[BASE] > total_net[HIGH_COST]
        assert total_net[STRESSED_SLIPPAGE] < total_net[BASE]
    else:
        assert all(value == 0.0 for value in total_costs.values())

    # Each scenario's cost-model version records the scenario name.
    experiment_record = json.loads(
        (
            study.output_dir.parent
            / f"bt_scen_test__{HIGH_COST}"
            / "metadata"
            / "experiment_record.json"
        ).read_text(encoding="utf-8")
    )
    assert experiment_record["cost_model_version"].endswith("__high_cost")

    # Scenario metadata lives in the study directory.
    config_path = study.paths["config"]
    summary_path = study.paths["summary"]
    assert config_path.exists() and summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert len(summary["results"]) == 4
    assert summary["study"]["model_version"] == model_version
    assert summary["study"]["ticker"] == TICKER


def test_scenario_study_rejects_missing_model(tmp_path):
    config = build_backtest_fixture(tmp_path, n_train=60, n_val=20, n_test=15)
    from src.backtest.errors import BacktestError

    with pytest.raises(BacktestError):
        BacktestEngine(config).run_scenarios(
            ticker=TICKER,
            model_version="does_not_exist_v9.9",
            split="test",
            backtest_id="bt_scen_missing_model",
        )


def test_config_snapshot_records_scenario_costs(tmp_path):
    """Scenario config_snapshot must reflect the scenario, not the base model."""
    config = build_backtest_fixture(tmp_path, n_train=60, n_val=20, n_test=15)
    model_version = _train(config)
    study = BacktestEngine(config).run_scenarios(
        ticker=TICKER,
        model_version=model_version,
        split="test",
        backtest_id="bt_scen_snapshot",
    )
    snapshot_path = (
        study.output_dir.parent
        / f"bt_scen_snapshot__{HIGH_COST}"
        / "config"
        / "config_snapshot.json"
    )
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["costs"]["per_side_bps"] == 50.0
    assert snapshot["costs"]["brokerage_bps"] == 25.0
    assert snapshot["costs"]["slippage_bps"] == 0.0
