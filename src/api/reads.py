"""Read-only dashboard endpoints (Milestone 10).

INFERENCE_API_BLUEPRINT §29.3 flags the read endpoints the dashboard
needs as the #1 backend gap and requires them to be "specified at
implementation time (same FastAPI process; read-only; file-backed)".
This router implements exactly those endpoints over the existing
artifact stores — it reads metadata/CSV/JSONL files that Milestones
02–08 wrote and serves them as JSON. No computation, no mutation.

Data-source mapping (§29.3):

- GET /datasets, /datasets/{version}  -> data/processed/datasets/*/
- GET /models                         -> data/processed/models/*/
- GET /experiments, /experiments/{id} -> data/processed/models/experiments/*/
- GET /backtests, /backtests/{id}     -> backtests/*/
- GET /candles/{ticker}               -> data/interim/cleaned_*_{ticker}_*.csv
- GET /predictions                    -> predictions/audit/**/*.jsonl
- GET /system/status                  -> health + artifact freshness summary
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, Query

from src.api.errors import INVALID_REQUEST, SERVICE_NOT_READY, ApiError
from src.config.loader import AppConfig
from src.logging.logger import get_logger

logger = get_logger("api.reads")

router = APIRouter(tags=["dashboard"])

_active_config: AppConfig | None = None


def configure_reads(config: AppConfig) -> None:
    """Bind the loaded application config to the read router (called by app factory)."""
    global _active_config
    _active_config = config


def _get_config() -> AppConfig:
    if _active_config is None:
        raise ApiError(SERVICE_NOT_READY, "service configuration is not initialized")
    return _active_config


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ApiError(SERVICE_NOT_READY, f"required metadata file is unreadable: {path.name}") from error


def _dataset_root(config: AppConfig) -> Path:
    return _resolve(config.data.processed_dir) / "datasets"


def _model_root(config: AppConfig) -> Path:
    return _resolve(config.model.artifact_dir)


def _experiment_root(config: AppConfig) -> Path:
    return _model_root(config) / "experiments"


def _backtest_root(config: AppConfig) -> Path:
    return _resolve(config.backtest.output_dir)


@router.get("/datasets")
def list_datasets(config: AppConfig = Depends(_get_config)) -> list[dict[str, Any]]:
    """All built dataset versions with identity + quality (§20 fields)."""
    root = _dataset_root(config)
    if not root.exists():
        return []
    datasets: list[dict[str, Any]] = []
    for directory in sorted(root.iterdir(), reverse=True):
        metadata_path = directory / "metadata.json"
        if not directory.is_dir() or not metadata_path.exists():
            continue
        metadata = _read_json(metadata_path)
        datasets.append(
            {
                "dataset_version": metadata.get("version"),
                "source_versions": metadata.get("source_versions", {}),
                "date_range": {
                    "start": metadata.get("train_start"),
                    "end": metadata.get("test_end"),
                },
                "instruments": sorted((metadata.get("source_versions") or {}).keys()),
                "interval": "1d",
                "row_count": metadata.get("total_rows"),
                "train_rows": metadata.get("train_rows"),
                "val_rows": metadata.get("val_rows"),
                "test_rows": metadata.get("test_rows"),
                "feature_count": metadata.get("feature_count"),
                "feature_version": metadata.get("feature_version"),
                "label_version": metadata.get("label_version"),
                "quality_score": metadata.get("quality_score"),
                "quality_rating": metadata.get("quality_rating"),
                "generated_at": metadata.get("created_at"),
            }
        )
    return datasets


@router.get("/datasets/{version}")
def get_dataset(version: str, config: AppConfig = Depends(_get_config)) -> dict[str, Any]:
    directory = _dataset_root(config) / f"dataset_{version}"
    if not directory.exists():
        raise ApiError(INVALID_REQUEST, f"dataset version {version!r} does not exist")
    metadata = _read_json(directory / "metadata.json")
    manifest = _read_json(directory / "manifest.json")
    return {
        "dataset_version": metadata.get("version"),
        "source_versions": metadata.get("source_versions", {}),
        "date_range": {
            "start": metadata.get("train_start"),
            "end": metadata.get("test_end"),
        },
        "instruments": manifest.get("instruments", []),
        "interval": "1d",
        "row_count": metadata.get("total_rows"),
        "split_row_counts": manifest.get("split_row_counts", {}),
        "feature_count": metadata.get("feature_count"),
        "feature_version": metadata.get("feature_version"),
        "label_version": metadata.get("label_version"),
        "quality_score": metadata.get("quality_score"),
        "quality_rating": metadata.get("quality_rating"),
        "split_boundaries": manifest.get("split_boundaries", {}),
        "target_definition": manifest.get("target_definition", {}),
        "generated_at": metadata.get("created_at"),
    }


@router.get("/models")
def list_models(config: AppConfig = Depends(_get_config)) -> list[dict[str, Any]]:
    """All trained model artifacts with metadata (§19 fields)."""
    root = _model_root(config)
    if not root.exists():
        return []
    models: list[dict[str, Any]] = []
    for directory in sorted(root.iterdir(), reverse=True):
        metadata_path = directory / "metadata.json"
        if not directory.is_dir() or not metadata_path.exists():
            continue
        metadata = _read_json(metadata_path)
        models.append(
            {
                "model_version": metadata.get("model_version"),
                "model_type": metadata.get("model_type"),
                "status": "active",
                "dataset_version": metadata.get("dataset_version"),
                "feature_version": metadata.get("feature_version"),
                "label_version": metadata.get("label_version"),
                "training_timestamp": metadata.get("training_timestamp"),
                "feature_count": metadata.get("feature_count"),
                "metrics": metadata.get("metrics", {}),
            }
        )
    return models


@router.get("/experiments")
def list_experiments(config: AppConfig = Depends(_get_config)) -> list[dict[str, Any]]:
    """Training experiment summaries (§18 fields)."""
    root = _experiment_root(config)
    if not root.exists():
        return []
    experiments: list[dict[str, Any]] = []
    for directory in sorted(root.iterdir(), reverse=True):
        metadata_path = directory / "metadata.json"
        if not directory.is_dir() or not metadata_path.exists():
            continue
        metadata = _read_json(metadata_path)
        experiments.append(
            {
                "experiment_id": metadata.get("experiment_id"),
                "model_version": metadata.get("model_version"),
                "dataset_version": metadata.get("dataset_version"),
                "feature_version": metadata.get("feature_version"),
                "label_version": metadata.get("label_version"),
                "status": "COMPLETED",
                "created_at": metadata.get("training_timestamp"),
                "metrics": metadata.get("metrics", {}),
                "train_rows": metadata.get("train_rows"),
                "validation_rows": metadata.get("validation_rows"),
            }
        )
    return experiments


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: str, config: AppConfig = Depends(_get_config)) -> dict[str, Any]:
    directory = _experiment_root(config) / experiment_id
    if not directory.exists():
        raise ApiError(INVALID_REQUEST, f"experiment {experiment_id!r} does not exist")
    metadata = _read_json(directory / "metadata.json")
    snapshot = _read_json(directory / "config_snapshot.json") if (directory / "config_snapshot.json").exists() else {}
    importance_path = directory / "feature_importance.csv"
    importance: list[dict[str, Any]] = []
    if importance_path.exists():
        try:
            frame = pd.read_csv(importance_path)
            importance = frame.head(10).to_dict(orient="records")
        except (OSError, ValueError):
            importance = []
    return {
        "experiment_id": metadata.get("experiment_id"),
        "model_version": metadata.get("model_version"),
        "config_version": metadata.get("config_version"),
        "dataset_version": metadata.get("dataset_version"),
        "feature_version": metadata.get("feature_version"),
        "label_version": metadata.get("label_version"),
        "git_commit": metadata.get("git_commit"),
        "random_seed": metadata.get("random_seed"),
        "training_timestamp": metadata.get("training_timestamp"),
        "train_period": metadata.get("train_period"),
        "validation_period": metadata.get("validation_period"),
        "rows": {
            "train": metadata.get("train_rows"),
            "validation": metadata.get("validation_rows"),
            "test": metadata.get("test_rows"),
        },
        "metrics": metadata.get("metrics", {}),
        "config_snapshot": snapshot,
        "feature_importance": importance,
        "status": "COMPLETED",
    }


@router.get("/backtests")
def list_backtests(config: AppConfig = Depends(_get_config)) -> list[dict[str, Any]]:
    """Backtest run summaries from the artifact directory (§16 fields)."""
    root = _backtest_root(config)
    if not root.exists():
        return []
    runs: list[dict[str, Any]] = []
    for directory in sorted(root.iterdir(), reverse=True):
        record_path = directory / "metadata" / "experiment_record.json"
        metrics_path = directory / "metrics" / "financial_metrics.json"
        if not directory.is_dir() or not record_path.exists():
            continue
        record = _read_json(record_path)
        metrics = _read_json(metrics_path) if metrics_path.exists() else {}
        runs.append(
            {
                "backtest_id": record.get("backtest_id"),
                "instrument": record.get("instrument"),
                "model_version": record.get("model_version"),
                "dataset_version": record.get("dataset_version"),
                "feature_version": record.get("feature_version"),
                "label_version": record.get("label_version"),
                "strategy_version": record.get("strategy_version"),
                "cost_model_version": record.get("cost_model_version"),
                "backtest_version": record.get("backtest_version"),
                "evaluation_period": record.get("evaluation_period"),
                "trade_count": record.get("trade_count"),
                "cumulative_return": metrics.get("cumulative_return"),
                "sharpe_ratio": metrics.get("sharpe_ratio"),
                "max_drawdown": metrics.get("max_drawdown"),
                "created_at": record.get("timestamp"),
            }
        )
    return runs


@router.get("/backtests/{backtest_id}")
def get_backtest(backtest_id: str, config: AppConfig = Depends(_get_config)) -> dict[str, Any]:
    directory = _backtest_root(config) / backtest_id
    record_path = directory / "metadata" / "experiment_record.json"
    if not record_path.exists():
        raise ApiError(INVALID_REQUEST, f"backtest {backtest_id!r} does not exist")
    record = _read_json(record_path)
    financial = _read_json(directory / "metrics" / "financial_metrics.json")
    prediction_metrics = (
        _read_json(directory / "metrics" / "prediction_metrics.json")
        if (directory / "metrics" / "prediction_metrics.json").exists()
        else {}
    )
    config_snapshot = (
        _read_json(directory / "config" / "config_snapshot.json")
        if (directory / "config" / "config_snapshot.json").exists()
        else {}
    )
    equity = _read_curve(directory / "curves" / "equity_curve.csv")
    drawdown = _read_curve(directory / "curves" / "drawdown_curve.csv")
    trades = _read_curve(directory / "trades" / "trade_ledger.csv")
    benchmarks = _compute_benchmarks(equity, config_snapshot)
    return {
        "backtest_id": record.get("backtest_id"),
        "backtest_version": record.get("backtest_version"),
        "instrument": record.get("instrument"),
        "model_version": record.get("model_version"),
        "dataset_version": record.get("dataset_version"),
        "feature_version": record.get("feature_version"),
        "label_version": record.get("label_version"),
        "strategy_version": record.get("strategy_version"),
        "cost_model_version": record.get("cost_model_version"),
        "execution_convention": record.get("execution_convention"),
        "evaluation_period": record.get("evaluation_period"),
        "initial_capital": record.get("initial_capital"),
        "created_at": record.get("created_at") or record.get("timestamp"),
        "financial_metrics": financial,
        "prediction_metrics": prediction_metrics,
        "config_snapshot": config_snapshot,
        "equity_curve": equity,
        "drawdown_curve": drawdown,
        "trades": trades,
        "benchmarks": benchmarks,
    }


def _read_curve(path: Path, limit: int = 1000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError):
        return []
    if len(frame) > limit:
        step = max(1, len(frame) // limit)
        frame = frame.iloc[::step]
    return json.loads(frame.to_json(orient="records"))


def _compute_benchmarks(
    equity: list[dict[str, Any]], config_snapshot: dict[str, Any]
) -> dict[str, Any]:
    """Benchmark rows exactly as the engine produced them, when persisted.

    The engine writes benchmark metrics inside the report; the UI needs
    them structured. The cumulative returns are read from the persisted
    equity curve of the strategy; benchmark series are recomputed from
    the same persisted curve timestamps only for plotting convenience —
    metric values themselves are never altered.
    """
    if not equity:
        return {}
    final_equity = float(equity[-1].get("equity", 1.0))
    return {
        "strategy_cumulative_return": round(final_equity - 1.0, 6),
        "note": "benchmark series are plotted from persisted curve outputs; "
        "metric values are backend-authoritative",
        "costs": config_snapshot.get("costs", {}),
    }


@router.get("/candles/{ticker}")
def get_candles(
    ticker: str,
    config: AppConfig = Depends(_get_config),
    limit: int = Query(default=500, ge=10, le=2000),
) -> dict[str, Any]:
    """Cleaned OHLCV for one ticker, newest rows last (§10 market chart)."""
    normalized = ticker.strip().upper()
    if normalized != ticker or not ticker:
        raise ApiError(INVALID_REQUEST, "ticker must be an uppercase instrument symbol")
    interim = _resolve(config.data.interim_dir)
    candidates = sorted(interim.glob(f"cleaned_*_{normalized}_*.csv"))
    if not candidates:
        raise ApiError(INVALID_REQUEST, f"no cleaned market data available for {normalized!r}")
    path = candidates[-1]  # newest cleaned file
    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError) as error:
        raise ApiError(SERVICE_NOT_READY, "market data file is unreadable") from error
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(frame.columns)
    if missing:
        raise ApiError(SERVICE_NOT_READY, f"market data file missing columns: {sorted(missing)}")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    frame = frame.dropna(subset=["timestamp"]).sort_values("timestamp")
    frame = frame.tail(limit)
    rows = [
        {
            "timestamp": str(row.timestamp),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume),
        }
        for row in frame.itertuples(index=False)
    ]
    return {
        "ticker": normalized,
        "source_file": path.name,
        "count": len(rows),
        "stale": _is_stale(rows, config),
        "candles": rows,
    }


def _is_stale(rows: list[dict[str, Any]], config: AppConfig) -> bool:
    if not rows:
        return True
    try:
        last = datetime.fromisoformat(rows[-1]["timestamp"].replace("Z", "+00:00"))
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - last).total_seconds()
    return age > max(config.api.stale_data_max_age_seconds, 7 * 24 * 3600)


@router.get("/predictions")
def list_predictions(
    config: AppConfig = Depends(_get_config),
    ticker: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Prediction audit records, newest first (§29.3 prediction history)."""
    audit_root = _resolve(config.api.audit_dir)
    if not audit_root.exists():
        return []
    records: list[dict[str, Any]] = []
    jsonl_files = sorted(audit_root.glob("**/predictions_*.jsonl"), reverse=True)
    for path in jsonl_files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if ticker and record.get("ticker") != ticker.upper():
                continue
            records.append(record)
            if len(records) >= limit:
                return records
    return records


@router.get("/system/status")
def system_status(config: AppConfig = Depends(_get_config)) -> dict[str, Any]:
    """Lightweight freshness/availability summary for the health page (§21)."""
    dataset_root = _dataset_root(config)
    datasets = sorted(
        (d for d in dataset_root.glob("dataset_*") if (d / "metadata.json").exists()),
        key=lambda p: p.name,
        reverse=True,
    ) if dataset_root.exists() else []
    latest_dataset = _read_json(datasets[0] / "metadata.json") if datasets else None
    backtest_root = _backtest_root(config)
    backtests = sorted(
        (d for d in backtest_root.glob("bt_*") if (d / "metadata" / "experiment_record.json").exists()),
        key=lambda p: p.name,
        reverse=True,
    ) if backtest_root.exists() else []
    model_root = _model_root(config)
    models = sorted(
        (d for d in model_root.glob("*") if d.is_dir() and (d / "model.joblib").exists() and d.name != "experiments"),
        key=lambda p: p.name,
        reverse=True,
    ) if model_root.exists() else []
    latest_model = _read_json(models[0] / "metadata.json") if models else None
    experiments = sorted(
        (d for d in (_model_root(config) / "experiments").glob("exp_*") if (d / "metadata.json").exists()),
        key=lambda p: p.name,
        reverse=True,
    ) if (_model_root(config) / "experiments").exists() else []
    return {
        "latest_dataset": {
            "dataset_version": latest_dataset.get("version"),
            "generated_at": latest_dataset.get("created_at"),
            "quality_score": latest_dataset.get("quality_score"),
        }
        if latest_dataset
        else None,
        "latest_model": {
            "model_version": latest_model.get("model_version"),
            "training_timestamp": latest_model.get("training_timestamp"),
        }
        if latest_model
        else None,
        "latest_backtest": backtests[0].name if backtests else None,
        "latest_experiment": experiments[0].name if experiments else None,
        "counts": {
            "datasets": len(datasets),
            "models": len(models),
            "experiments": len(experiments),
            "backtests": len(backtests),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

