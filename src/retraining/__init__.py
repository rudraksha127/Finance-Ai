"""Controlled autonomous retraining package (Post-MVP Milestone 03).

Produces evaluated model candidates (CANDIDATE_APPROVED/REJECTED) via
triggers, eligibility checks, promotion gates, and audit records. It never
activates a model, never touches the inference path, and never deletes
artifacts (activation is Post-MVP Milestone 04's registry responsibility).
"""

__all__ = ["engine"]
