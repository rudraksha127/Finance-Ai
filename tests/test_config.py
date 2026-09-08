"""Tests for src/config/loader.py — typed, environment-aware configuration."""

from pathlib import Path

import pytest

from src.config.loader import load_config
from src.core.enums import AppEnvironment
from src.core.errors import ConfigError

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_CONFIG_DIR = Path(__file__).resolve().parent / "fixtures" / "config"


def _write(tmp_path: Path, filename: str, content: str) -> Path:
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    return path


def _minimal_default_yaml() -> str:
    """A complete, schema-valid default.yaml for isolated failure tests."""
    return (
        "project:\n"
        "  name: minimal\n"
        "  version: '1.0'\n"
        "data:\n"
        "  raw_dir: data/raw\n"
        "  interim_dir: data/interim\n"
        "  processed_dir: data/processed\n"
        "  external_dir: data/external\n"
        "  default_format: csv\n"
    )


class TestRealRepositoryConfig:
    """The shipped config/default.yaml must load cleanly."""

    def test_default_config_loads(self):
        config = load_config(environment=AppEnvironment.DEVELOPMENT)
        assert config.environment is AppEnvironment.DEVELOPMENT
        assert config.project.name == "finance-ai-mvp"
        assert config.project.version == "0.1.0"
        assert config.data.default_format == "csv"
        assert config.logging.level == "INFO"
        assert config.logging.format == "json"

    def test_data_paths_resolve_relative_to_repo_root(self):
        config = load_config(environment=AppEnvironment.DEVELOPMENT)
        assert config.data.raw_dir == REPO_ROOT / "data" / "raw"
        assert config.data.processed_dir == REPO_ROOT / "data" / "processed"
        assert config.data.interim_dir == REPO_ROOT / "data" / "interim"


class TestEnvironmentOverlay:
    """config/{environment}.yaml overlays default.yaml via deep merge."""

    def test_testing_overlay_merges_and_overrides(self):
        config = load_config(environment=AppEnvironment.TESTING, config_dir=FIXTURE_CONFIG_DIR)
        # Overridden by testing.yaml:
        assert config.data.raw_dir == FIXTURE_CONFIG_DIR.parent / "data" / "fixture_testing_raw"
        assert config.logging.level == "DEBUG"
        # Unchanged by testing.yaml (deep-merge behavior):
        assert config.project.name == "finance-ai-fixture"
        assert config.data.processed_dir == FIXTURE_CONFIG_DIR.parent / "data" / "fixture_processed"

    def test_missing_environment_overlay_uses_default_only(self):
        # No development.yaml exists in the fixture dir → default only.
        config = load_config(environment=AppEnvironment.DEVELOPMENT, config_dir=FIXTURE_CONFIG_DIR)
        assert config.environment is AppEnvironment.DEVELOPMENT
        assert config.data.raw_dir == FIXTURE_CONFIG_DIR.parent / "data" / "fixture_raw"
        assert config.logging.level == "INFO"


class TestEnvironmentVariables:
    """ENVIRONMENT selects the overlay; LOG_LEVEL/LOG_FORMAT override keys."""

    def test_environment_from_env_var(self):
        environ = {"ENVIRONMENT": "testing"}
        config = load_config(config_dir=FIXTURE_CONFIG_DIR, environ=environ)
        assert config.environment is AppEnvironment.TESTING
        assert config.logging.level == "DEBUG"

    def test_environment_defaults_to_development(self):
        config = load_config(config_dir=FIXTURE_CONFIG_DIR, environ={})
        assert config.environment is AppEnvironment.DEVELOPMENT

    def test_log_level_env_override(self):
        environ = {"LOG_LEVEL": "WARNING"}
        config = load_config(config_dir=FIXTURE_CONFIG_DIR, environ=environ)
        assert config.logging.level == "WARNING"

    def test_log_format_env_override(self):
        environ = {"LOG_FORMAT": "console"}
        config = load_config(config_dir=FIXTURE_CONFIG_DIR, environ=environ)
        assert config.logging.format == "console"

    def test_invalid_environment_var_raises(self):
        environ = {"ENVIRONMENT": "banana"}
        with pytest.raises(ConfigError, match="invalid environment"):
            load_config(config_dir=FIXTURE_CONFIG_DIR, environ=environ)


class TestConfigFailures:
    """Missing or invalid configuration fails loudly with ConfigError."""

    def test_missing_default_raises(self, tmp_path):
        with pytest.raises(ConfigError, match="not found"):
            load_config(config_dir=tmp_path, environ={})

    def test_malformed_yaml_raises(self, tmp_path):
        _write(tmp_path, "default.yaml", "project: [unclosed\n")
        with pytest.raises(ConfigError, match="invalid YAML"):
            load_config(config_dir=tmp_path, environ={})

    def test_non_mapping_root_raises(self, tmp_path):
        _write(tmp_path, "default.yaml", "- just\n- a\n- list\n")
        with pytest.raises(ConfigError, match="must be a mapping"):
            load_config(config_dir=tmp_path, environ={})

    def test_missing_required_project_name_raises(self, tmp_path):
        _write(tmp_path, "default.yaml", "project:\n  version: '1.0'\n")
        with pytest.raises(ConfigError, match=r"project\.name"):
            load_config(config_dir=tmp_path, environ={})

    def test_invalid_log_level_raises(self, tmp_path):
        _write(
            tmp_path,
            "default.yaml",
            _minimal_default_yaml() + "logging:\n  level: LOUD\n  format: json\n",
        )
        with pytest.raises(ConfigError, match=r"logging\.level"):
            load_config(config_dir=tmp_path, environ={})

    def test_invalid_log_format_raises(self, tmp_path):
        _write(
            tmp_path,
            "default.yaml",
            _minimal_default_yaml() + "logging:\n  level: INFO\n  format: xml\n",
        )
        with pytest.raises(ConfigError, match=r"logging\.format"):
            load_config(config_dir=tmp_path, environ={})

    def test_invalid_data_format_raises(self, tmp_path):
        _write(
            tmp_path,
            "default.yaml",
            _minimal_default_yaml().replace("default_format: csv", "default_format: xlsx"),
        )
        with pytest.raises(ConfigError, match=r"data\.default_format"):
            load_config(config_dir=tmp_path, environ={})

    def test_env_log_level_invalid_raises(self, tmp_path):
        _write(tmp_path, "default.yaml", _minimal_default_yaml())
        with pytest.raises(ConfigError):
            load_config(config_dir=tmp_path, environ={"LOG_LEVEL": "SHOUT"})
