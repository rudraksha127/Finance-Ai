"""Historical data source adapter contract.

The contract isolates provider specifics:

- :class:`FetchParams` — a normalized request (instrument, range, interval)
- :class:`FetchedData` — a provider-neutral result: simple record dicts
  with ``timestamp`` (ISO-8601 date string), ``open``/``high``/``low``/
  ``close``/``volume`` numerics and optional ``adj_close``
- :class:`HistoricalDataSource` — the adapter interface

Every adapter is responsible for provider-specific concerns *inside*
the adapter only: endpoint selection, authentication, HTTP status
handling, response-shape parsing, and converting provider timestamps
to UTC dates. The ingestion engine and downstream stages operate
solely on :class:`FetchedData` + the domain layer (``src.core``).

Error behavior: adapters raise the typed errors from
:mod:`src.data.sources.errors` so the engine can separate transient
(retryable) from permanent failures.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol


@dataclass(frozen=True)
class FetchParams:
    """A normalized historical fetch request."""

    instrument: str  # canonical ticker, e.g. "AAPL"
    start: date  # inclusive
    end: date  # inclusive
    interval: str = "1d"  # one of 1d | 1wk | 1mo


@dataclass(frozen=True)
class FetchedData:
    """Provider-neutral result of one fetch operation."""

    source: str  # adapter identifier, e.g. "yahoo_finance"
    symbol: str  # canonical ticker as requested
    interval: str
    start: date  # echoed request bounds (inclusive)
    end: date
    records: tuple[Mapping[str, Any], ...]  # provider-neutral rows
    dropped_count: int = 0  # provider rows skipped inside the adapter (null OHLC)


class HistoricalDataSource(Protocol):
    """Contract every historical source adapter implements."""

    @property
    def name(self) -> str:
        """Stable adapter identifier (e.g. ``yahoo_finance``)."""

    def fetch(self, params: FetchParams) -> FetchedData:
        """Fetch the requested range.

        Raises:
            SourceError subclasses for provider failures (see
            ``src.data.sources.errors``). Transient failures declare
            ``retryable=True``.
        """
