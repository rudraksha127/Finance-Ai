"""Multimodal finance intelligence (Post-MVP Milestone 08)."""

from src.multimodal.contracts import EventType, ExternalRecord, TemporalReliability
from src.multimodal.features import (
    MULTIMODAL_FEATURE_VERSION,
    build_multimodal_features,
    multimodal_feature_columns,
)
from src.multimodal.sources import deduplicate, load_fixture, normalize_batch

__all__ = [
    "MULTIMODAL_FEATURE_VERSION",
    "EventType",
    "ExternalRecord",
    "TemporalReliability",
    "build_multimodal_features",
    "deduplicate",
    "load_fixture",
    "multimodal_feature_columns",
    "normalize_batch",
]
