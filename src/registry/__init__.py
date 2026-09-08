"""Model registry package (Post-MVP Milestone 04).

Single source of truth for model lifecycle and the ACTIVE model. Safe
promotion/rollback with integrity checks, atomic activation, audit trail,
and concurrency protection. No automatic live deployment.
"""

__all__ = ["engine"]
