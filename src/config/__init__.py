"""Configuration package.

Typed, environment-aware loading of YAML configuration following
ENGINEERING_CONSTITUTION.md section 5 and NFR-CF-01..05:

- base configuration: ``config/default.yaml``
- optional per-environment overlay: ``config/{environment}.yaml``
- secrets and runtime settings via environment variables only

See :mod:`src.config.loader` for the public API.
"""
