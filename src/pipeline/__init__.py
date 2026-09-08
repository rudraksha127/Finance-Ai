"""Controlled autonomous data-growth pipeline for Finance AI MVP.

This package is intentionally thin at the post-MVP stage:
it orchestrates existing domain engines (ingestion, cleaning, features,
labels, dataset builder) instead of reimplementing them.

Scope for this milestone:
- scheduled / manual pipeline runs
- watermark based incremental ingestion
- stage tracking and run observability
- dataset growth through new immutable dataset versions

Out of scope here:
- autonomous model retraining
- model promotion / registry actions
- live trading integration
"""

__all__ = []
