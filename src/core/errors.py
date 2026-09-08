"""Foundational exception hierarchy for Finance AI.

Error categories required by the milestone and the engineering
constitution (never swallow exceptions, fail loudly):

- :class:`FinanceAIError` — base class for all application errors
- :class:`ConfigError` — invalid or missing configuration
- :class:`ValidationError` — a value failed validation
- :class:`StorageError` — a file-storage operation failed

A ``DatabaseError`` category is intentionally NOT implemented:
the MVP is file-based (ADR-0005, DECISIONS.md). A database error
category will be added with the Phase-2 PostgreSQL migration.
"""

from __future__ import annotations

from typing import Any


class FinanceAIError(Exception):
    """Base class for all Finance AI domain errors.

    Carries an optional structured ``context`` dict so callers can
    attach machine-readable detail (config key, row index, offending
    value, ...) without string-parsing the message.
    """

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}


class ConfigError(FinanceAIError):
    """Configuration is missing, malformed, or contains invalid values."""


class ValidationError(FinanceAIError):
    """A value failed one or more validation rules."""


class StorageError(FinanceAIError):
    """A file-storage operation failed (missing tier, I/O error, ...)."""
