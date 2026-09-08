"""Structured logging foundation (structlog).

Policy (ENGINEERING_CONSTITUTION.md section 4):

- log levels: DEBUG (dev), INFO (progress), WARNING (data issues),
  ERROR (failures), plus CRITICAL for unrecoverable failures
- every log line carries: timestamp (ISO-8601 UTC), level, module,
  event message, and caller-supplied context values
- renderers: ``json`` (default, machine-readable) or ``console``
- nothing sensitive is ever logged by this module; callers are
  responsible for not passing secrets as context
"""

from __future__ import annotations

import logging
import sys
from typing import TextIO

import structlog

from src.config.loader import AppConfig
from src.core.errors import ConfigError

# stdlib numeric levels, shared with the filtering wrapper.
LEVEL_NUMBERS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_configured = False


def parse_log_level(level: str) -> int:
    """Map a level name (``DEBUG``..``CRITICAL``) to its numeric value.

    Raises:
        ValueError: for unknown level names.
    """
    try:
        return LEVEL_NUMBERS[level.upper()]
    except KeyError:
        raise ValueError(
            f"unknown log level {level!r}: expected one of {sorted(LEVEL_NUMBERS)}"
        ) from None


def configure_logging(
    *,
    level: str = "INFO",
    log_format: str = "json",
    stream: TextIO = sys.stdout,
) -> None:
    """Configure the global structlog processor chain.

    Args:
        level: Minimum level name (``DEBUG``..``CRITICAL``).
        log_format: ``json`` for machine-readable output, ``console``
            for human-readable development output.
        stream: Output stream (defaults to stdout). Provided so tests
            can capture output deterministically.

    Raises:
        ValueError: if ``level`` or ``log_format`` is unsupported.
    """
    numeric_level = parse_log_level(level)
    if log_format not in {"json", "console"}:
        raise ValueError(f"unknown log format {log_format!r}: expected 'json' or 'console'")

    renderer: structlog.types.Processor
    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    # Re-configuring is safe and idempotent: structlog replaces the
    # active processor chain each call. stdlib logging is left at its
    # default level so it does not swallow anything unexpectedly.
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(file=stream),
        cache_logger_on_first_use=True,
    )
    global _configured
    _configured = True


def configure_from_config(config: AppConfig, *, stream: TextIO = sys.stdout) -> None:
    """Configure logging from an :class:`AppConfig`.

    Raises:
        ConfigError: if the config's logging values are invalid
            (defensive — ``load_config`` validates them already).
    """
    try:
        configure_logging(
            level=config.logging.level, log_format=config.logging.format, stream=stream
        )
    except ValueError as error:
        raise ConfigError(str(error)) from error


def get_logger(name: str = "finance_ai") -> structlog.stdlib.BoundLogger:
    """Return a bound logger carrying the module/service name.

    The ``module`` context key is added so every line is attributable
    without relying on global logger-name plumbing.
    """
    return structlog.get_logger().bind(module=name)


def is_configured() -> bool:
    """Report whether :func:`configure_logging` has run at least once."""
    return _configured
