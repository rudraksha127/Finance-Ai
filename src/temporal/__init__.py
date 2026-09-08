"""Temporal intelligence model (Post-MVP Milestone 06).

Imports are lazy so that loading a torch-free inference artifact
(:mod:`src.temporal.inference`) never pulls PyTorch into serving processes
(Windows DLL conflict mitigation; see inference.py).
"""
