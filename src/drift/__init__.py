"""Drift detection engine package (Post-MVP Milestone 02).

Monitoring only: detects data/feature/label/prediction/performance/
missingness drift and records events. It never retrains models, replaces
artifacts, or changes thresholds.
"""

__all__ = ["engine", "metrics"]
