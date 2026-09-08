"""Logging package.

Structured logging foundation built on ``structlog``
(ENGINEERING_CONSTITUTION.md section 4, PRD NFR-LO-01..05):

- JSON output by default (``format: json``), console rendering for dev
- ISO-8601 UTC timestamps, log level, module, message, context values
- DEBUG / INFO / WARNING / ERROR / CRITICAL levels
- no secrets, no ``print()`` in production code

See :mod:`src.logging.logger` for the public API.
"""
