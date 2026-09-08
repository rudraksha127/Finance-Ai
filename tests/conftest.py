"""Shared pytest fixtures for the Milestone 09 API tests."""

from __future__ import annotations

try:
    import lightgbm  # noqa: F401
except ImportError:
    pass

from pathlib import Path

import pytest

from src.api.orchestrator import ServiceState, build_service_state
from tests.api_helpers import make_api_config


@pytest.fixture()
def api_state(tmp_path: Path) -> ServiceState:
    """Fully initialized ServiceState backed by a real trained model."""
    from dataclasses import replace

    config = make_api_config(tmp_path)
    config = replace(config, api=replace(config.api, audit_dir=tmp_path / "audit"))
    return build_service_state(config)


@pytest.fixture()
def api_client(api_state: ServiceState):
    """FastAPI TestClient over the real sandboxed service state."""
    from fastapi.testclient import TestClient

    import src.api.app as app_module
    from src.api.app import create_app

    app = create_app(api_state.config)
    original_state = app_module.STATE
    app_module.STATE = api_state
    try:
        yield TestClient(app)
    finally:
        app_module.STATE = original_state
