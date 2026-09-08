"""Data layer — historical market-data ingestion.

Implements the ingestion pipeline approved in
``docs/DATA_INGESTION_BLUEPRINT.md`` for the file-based MVP
(ADR-0005): fetch from a source adapter, validate, normalize into
domain candles, persist to the immutable-by-append raw tier, and
record per-run metadata.

Module layout:
    sources/     — source adapter contract + the Yahoo Finance adapter
    normalize.py — provider-neutral record → domain candle conversion
    store.py     — raw-tier (ticker, interval) CSV store with dedup
    metadata.py  — per-run ingestion metadata journal
    instruments.py — file-backed instrument registry (ticker identity)
    engine.py    — orchestration: retries, pipeline stages, statuses

Validation primitives and the domain models (``Candle``,
``Instrument``) come from ``src.core`` (Milestone 01).
"""
