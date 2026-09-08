"""
Finance AI — Source Package

All modules follow the architecture defined in docs/ARCHITECTURE_PRINCIPLES.md.

Foundation (implemented in Milestone 01):
    core/       — Errors, typed domain vocabulary, validation primitives,
                  domain models (Instrument, Candle), storage layout
    config/     — Typed, environment-aware YAML configuration
    logging/    — Structured logging (structlog)

Layers (later milestones):
    data/       — Data ingestion and storage
    processing/ — Data cleaning and validation
    features/   — Feature engineering
    dataset/    — Dataset assembly and splitting
    model/      — Model training and inference
    evaluation/ — Backtesting and metrics
    api/        — Prediction serving (future)
"""
