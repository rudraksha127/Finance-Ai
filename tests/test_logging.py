"""Tests for src/logging/logger.py — structlog foundation.

Each test configures logging with its own stream so output is captured
deterministically regardless of structlog's process-global state.
"""

import io
import json
from pathlib import Path

import pytest

from src.config.loader import load_config
from src.core.enums import AppEnvironment
from src.logging.logger import (
    configure_from_config,
    configure_logging,
    get_logger,
    is_configured,
    parse_log_level,
)

FIXTURE_CONFIG_DIR = Path(__file__).resolve().parent / "fixtures" / "config"


def _capture_json(level: str = "INFO") -> dict:
    stream = io.StringIO()
    configure_logging(level=level, log_format="json", stream=stream)
    logger = get_logger("tests.logging")
    logger.info("hello world", ticker="AAPL", confidence=0.72)
    return json.loads(stream.getvalue().strip())


class TestJsonOutput:
    def test_log_line_contains_required_fields(self):
        record = _capture_json()
        assert record["event"] == "hello world"
        assert record["level"] == "info"
        assert record["module"] == "tests.logging"
        assert record["ticker"] == "AAPL"
        assert record["confidence"] == 0.72
        assert "timestamp" in record

    def test_timestamp_is_iso_utc(self):
        record = _capture_json()
        # ISO-8601 with 'Z' suffix (UTC) produced by TimeStamper(utc=True).
        assert record["timestamp"].endswith("Z")
        assert "T" in record["timestamp"]


class TestLevelFiltering:
    def test_info_is_filtered_when_warning_configured(self):
        stream = io.StringIO()
        configure_logging(level="WARNING", log_format="json", stream=stream)
        get_logger("tests.logging").info("should be hidden")
        assert stream.getvalue() == ""

    def test_warning_and_critical_are_emitted_at_warning_level(self):
        stream = io.StringIO()
        configure_logging(level="WARNING", log_format="json", stream=stream)
        logger = get_logger("tests.logging")
        logger.warning("watch out")
        logger.critical("catastrophic")
        lines = [json.loads(line) for line in stream.getvalue().strip().splitlines()]
        assert [line["level"] for line in lines] == ["warning", "critical"]

    def test_error_is_emitted_at_info_level(self):
        stream = io.StringIO()
        configure_logging(level="INFO", log_format="json", stream=stream)
        get_logger("tests.logging").error("failure")
        record = json.loads(stream.getvalue().strip())
        assert record["level"] == "error"
        assert record["event"] == "failure"


class TestConsoleFormat:
    def test_console_renderer_prints_readable_message(self):
        stream = io.StringIO()
        configure_logging(level="INFO", log_format="console", stream=stream)
        get_logger("tests.logging").info("human readable event")
        assert "human readable event" in stream.getvalue()


class TestInvalidArguments:
    def test_unknown_level_raises_value_error(self):
        with pytest.raises(ValueError, match="unknown log level"):
            configure_logging(level="LOUD")

    def test_unknown_format_raises_value_error(self):
        with pytest.raises(ValueError, match="unknown log format"):
            configure_logging(log_format="xml")

    def test_parse_log_level_returns_stdlib_numbers(self):
        assert parse_log_level("debug") == 10
        assert parse_log_level("WARNING") == 30
        assert parse_log_level("CRITICAL") == 50

    def test_parse_log_level_rejects_unknown(self):
        with pytest.raises(ValueError):
            parse_log_level("VERBOSE")


class TestConfigDrivenSetup:
    def test_configure_from_config(self):
        config = load_config(environment=AppEnvironment.TESTING, config_dir=FIXTURE_CONFIG_DIR)
        stream = io.StringIO()
        configure_from_config(config, stream=stream)
        assert is_configured()
        # Fixture testing.yaml sets logging.level=DEBUG and format=json,
        # so an ERROR line is emitted as JSON.
        get_logger("tests.logging").error("from config")
        record = json.loads(stream.getvalue().strip())
        assert record["event"] == "from config"
        assert record["level"] == "error"

    def test_invalid_config_level_raises_config_error(self):
        from dataclasses import replace

        from src.config.loader import LoggingConfig
        from src.core.errors import ConfigError

        config = load_config(environment=AppEnvironment.TESTING, config_dir=FIXTURE_CONFIG_DIR)
        broken = replace(config, logging=LoggingConfig(level="LOUD", format="json"))
        with pytest.raises(ConfigError):
            configure_from_config(broken)
