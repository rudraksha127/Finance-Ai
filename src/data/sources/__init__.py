"""Source adapters for historical market data.

Provider-specific parsing and HTTP behavior is isolated behind the
:class:`~src.data.sources.base.HistoricalDataSource` contract so the
rest of the ingestion pipeline never sees provider formats
(DATA_INGESTION_BLUEPRINT.md sections 1 and 5).

Implemented adapters:
    yahoo  — Yahoo Finance chart API (MVP historical source)
"""
