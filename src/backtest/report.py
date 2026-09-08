"""Report generator for the backtest engine (M08).

Writes every output required by EVALUATION_BACKTESTING_BLUEPRINT
section 27 into ``{output_dir}/{backtest_id}/`` with the documented
directory layout. Writes are atomic (temp file + rename) and the
report is human- and machine-readable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.backtest.errors import ReportError
from src.logging.logger import get_logger

logger = get_logger("backtest.report")


def write_json(path: Path, payload: Any) -> None:
    """Atomically write a JSON payload (sorted keys for stable diffs)."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    """Atomically write a CSV frame."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp, index=False)
    tmp.replace(path)


def write_backtest_outputs(
    output_dir: Path,
    *,
    backtest_id: str,
    predictions: pd.DataFrame,
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    financial: dict[str, Any],
    prediction_metrics: dict[str, Any],
    cost_adjusted: dict[str, Any],
    experiment_record: dict[str, Any],
    config_snapshot: dict[str, Any],
    report_markdown: str,
) -> dict[str, Path]:
    """Persist the full backtest artifact set; returns written paths."""
    directory = output_dir / backtest_id
    try:
        for sub in ("predictions", "trades", "curves", "metrics", "config", "metadata", "report"):
            (directory / sub).mkdir(parents=True, exist_ok=True)

        write_csv(directory / "predictions" / "test_predictions.csv", predictions)
        write_csv(directory / "trades" / "trade_ledger.csv", trades)
        write_csv(directory / "curves" / "equity_curve.csv", equity)
        write_csv(
            directory / "curves" / "drawdown_curve.csv",
            equity[["timestamp", "drawdown"]],
        )
        write_json(directory / "metrics" / "financial_metrics.json", financial)
        write_json(directory / "metrics" / "prediction_metrics.json", prediction_metrics)
        write_json(directory / "metrics" / "cost_adjusted.json", cost_adjusted)
        write_json(directory / "config" / "config_snapshot.json", config_snapshot)
        write_json(directory / "metadata" / "experiment_record.json", experiment_record)
        report_path = directory / "report" / "backtest_report.md"
        tmp = report_path.with_suffix(".tmp")
        tmp.write_text(report_markdown, encoding="utf-8")
        tmp.replace(report_path)
    except (OSError, ValueError, RuntimeError) as error:
        raise ReportError(
            f"cannot write backtest outputs for {backtest_id}: {error}",
            context={"backtest_id": backtest_id, "output_dir": str(directory)},
        ) from error

    paths = {
        "predictions": directory / "predictions" / "test_predictions.csv",
        "trade_ledger": directory / "trades" / "trade_ledger.csv",
        "equity_curve": directory / "curves" / "equity_curve.csv",
        "drawdown_curve": directory / "curves" / "drawdown_curve.csv",
        "financial_metrics": directory / "metrics" / "financial_metrics.json",
        "prediction_metrics": directory / "metrics" / "prediction_metrics.json",
        "cost_adjusted": directory / "metrics" / "cost_adjusted.json",
        "config_snapshot": directory / "config" / "config_snapshot.json",
        "experiment_record": directory / "metadata" / "experiment_record.json",
        "report": directory / "report" / "backtest_report.md",
    }
    logger.info(
        "backtest_outputs_written",
        backtest_id=backtest_id,
        output_dir=str(directory),
        status="COMPLETED",
    )
    return paths
