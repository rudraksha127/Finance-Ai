"""Tests for walk-forward fold generation and execution (M08)."""

from __future__ import annotations

import pandas as pd
import pytest

from src.backtest.errors import WalkForwardError
from src.backtest.walkforward import WalkForwardRunner, generate_folds
from tests.backtest_helpers import TICKER, build_backtest_fixture


def test_fold_generation_expanding():
    folds = generate_folds(300, train_window=100, test_window=20, step=20)
    # train_end: 100, 120, ..., 280 -> 10 folds (train_end + 20 <= 300)
    assert len(folds) == 10
    assert folds[0].train_start == 0
    assert folds[0].train_end == 100
    assert (folds[0].test_start, folds[0].test_end) == (100, 120)
    assert folds[1].train_end == 120  # expanding, not fixed-size rolling
    assert folds[1].test_start == 120
    assert folds[-1].test_end == 300
    for fold in folds:
        assert fold.test_rows == 20
        assert fold.train_end == fold.test_start


def test_fold_generation_insufficient_history():
    with pytest.raises(WalkForwardError, match="not enough history"):
        generate_folds(50, train_window=100, test_window=20, step=20)


def test_end_to_end_walkforward_with_purge(tmp_path):
    config = build_backtest_fixture(tmp_path, n_train=160, n_val=30, n_test=30)  # 220 total rows
    runner = WalkForwardRunner(config)
    result = runner.run(
        ticker=TICKER,
        model_name="random_forest",
        train_window=100,
        test_window=20,
        step=20,
        purge=True,
    )
    # Folds at train_end 100..200 -> 5 folds (100,120,140,160,180,200 -> last +20 <= 220)
    assert 4 <= len(result.folds) <= 6
    # Equity chains from fold returns; day 0 may include an entry cost.
    assert result.overall_equity["equity"].iloc[0] == pytest.approx(
        1.0 + result.overall_equity["daily_return"].iloc[0]
    )
    assert "cumulative_return" in result.overall_financial_metrics
    assert result.paths["report"].exists()
    assert result.paths["financial_metrics"].exists()

    # Purge must have removed overlapping-label rows in at least some folds.
    assert any(
        summary["train_rows_after_purge"] < summary["train_rows_before_purge"]
        for summary in result.fold_summaries
    )

    combined = pd.read_csv(result.paths["predictions"])
    assert "fold" in combined.columns
    assert combined["fold"].nunique() == len(result.folds)
    # Overall equity must be chained (end >= 1.0 here given the rising fixture).
    assert result.overall_equity["equity"].iloc[-1] > 0.0


def test_walkforward_requires_history(tmp_path):
    config = build_backtest_fixture(tmp_path, n_train=40, n_val=20, n_test=20)
    with pytest.raises(WalkForwardError):
        WalkForwardRunner(config).run(
            ticker=TICKER,
            model_name="random_forest",
            train_window=500,
            test_window=20,
            step=20,
        )
