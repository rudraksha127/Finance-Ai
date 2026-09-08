"""Ingestion-specific typed vocabulary."""

from __future__ import annotations

from enum import Enum


class IngestionStatus(str, Enum):
    """Lifecycle of a single ingestion run (per ticker).

    Mirrors DATA_INGESTION_BLUEPRINT.md section 2.3 plus the explicit
    statuses required by the milestone:

    - ``CREATED`` — run record created, work not started
    - ``RUNNING`` — pipeline executing
    - ``COMPLETED`` — all fetched rows persisted; nothing failed
    - ``PARTIAL`` — some rows were rejected/conflicted but others persisted
    - ``FAILED`` — nothing persisted (fetch or validation failed)
    """

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
