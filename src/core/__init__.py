"""Core foundation package.

Shared, cross-cutting primitives used by every layer of the MVP:

- ``errors``: foundational exception hierarchy
- ``enums``: typed domain vocabulary fixed by the approved architecture
- ``validation``: reusable data validation primitives
- ``models``: foundational domain types (Instrument, Candle)
- ``storage``: raw / interim / processed storage layout

These modules contain no business logic beyond what the approved
architecture fixes. Heavier engines (ingestion, cleaning, features,
labels, datasets, models) live in their own layers.
"""
