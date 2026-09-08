"""Data cleaning & quality engine (Milestone 03).

Implements the approved DATA_CLEANING_VALIDATION.md pipeline for the
file-based MVP (ADR-0005):

    raw CSV → validate (explicit per-rule reasons) → clean (dedup, fix,
    missing-fill) → corporate-action adjustment → normalize → quality
    score → write interim tier (raw never modified) → audit trail

Module layout:

    io.py        — tolerant raw-CSV reader, interim-writer, hashing
    validation.py— VAL-* rule engine with per-row explicit reasons
    cleaning.py  — duplicate removal, OHLC fix, missing-data strategies
    actions.py   — corporate-action backward adjustment (split/bonus/dividend)
    quality.py   — 0-100 score (completeness/validity/consistency/freshness/uniqueness)
    audit.py     — transformation log + audit records (JSONL + per-run JSON)
    pipeline.py  — orchestration (stage state machine)

Validation primitives and domain types from ``src.core`` are reused;
cleaning input is the raw-tier CSV produced by Milestone 02, which is
never written to by this pipeline.
"""

from __future__ import annotations

from . import audit, cleaning, io, pipeline, quality, validation  # noqa: F401
from .pipeline import CleaningPipeline, PipelineResult

__all__ = ["CleaningPipeline", "PipelineResult"]
