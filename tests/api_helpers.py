"""Shared deterministic fixtures for Milestone 09 (inference API) tests.

Reuses the Milestone-08 dataset fixture (``build_backtest_fixture``) so
the API tests train a real baseline model in a tmp sandbox and exercise
the genuine artifact-loading path — no mocks for the model boundary.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from src.config.loader import AppConfig, ModelConfig
from src.model.trainer import BaselineTrainer
from tests.backtest_helpers import TICKER, build_backtest_fixture

MODEL_VERSION = "api_test_model_v1"
FEATURE_VERSION = "v0.1"
LABEL_VERSION = "v0.1"


def make_api_config(tmp_path: Path) -> AppConfig:
    """Sandboxed API config rooted in tmp_path with a trained model artifact."""
    config = build_backtest_fixture(tmp_path, n_train=80, n_val=30, n_test=25)
    BaselineTrainer(config).run(
        model_name="random_forest",
        model_version=MODEL_VERSION,
        experiment_id="exp_api_test",
    )
    return replace(
        config,
        model=ModelConfig(artifact_dir=config.model.artifact_dir),
    )


def valid_feature_vector(config: AppConfig, *, seed: int = 3) -> dict[str, float]:
    """A deterministic in-range feature vector matching the fixture distribution."""
    from src.features.registry import FEATURE_COLUMNS

    rng = np.random.default_rng(seed)
    return {name: float(round(rng.uniform(-1.2, 1.2), 6)) for name in FEATURE_COLUMNS}


def valid_request_payload(config: AppConfig, **overrides) -> dict:
    """A contract-valid /predict request body for the fixture model."""
    from datetime import datetime, timedelta, timezone

    payload = {
        "ticker": TICKER,
        "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "interval": "1d",
        "feature_set_version": FEATURE_VERSION,
        "model_version": MODEL_VERSION,
        "features": valid_feature_vector(config),
        "market_context": {
            "current_price": 185.6,
            "recent_volatility": 0.2,
            "data_timestamp": (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(),
        },
    }
    payload.update(overrides)
    return payload


def feature_frame(config: AppConfig) -> pd.DataFrame:
    """The fixture dataset's TEST split (for golden/regression vectors)."""
    return pd.read_parquet(config.data.processed_dir / "datasets" / "dataset_v0.1" / "test.parquet")
