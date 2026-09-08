"""Shared deterministic helpers for data-layer tests (Milestone 02).

All providers here are scripted fakes — the ordinary test suite never
touches the network (per the milestone test-data rules).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.config.loader import (
    AppConfig,
    DataConfig,
    IngestionConfig,
    IngestionRetryConfig,
    LoggingConfig,
    ProjectConfig,
)
from src.core.enums import AppEnvironment
from src.data.sources.base import FetchedData, FetchParams
from src.data.sources.errors import SourceError


def make_app_config(
    raw_dir: Path,
    *,
    interval: str = "1d",
    max_retries: int = 3,
    base_delay_s: float = 1.0,
    max_delay_s: float = 60.0,
    retry_429_delay_s: float = 60.0,
    delay_between_requests_ms: int = 0,
    continue_on_failure: bool = True,
) -> AppConfig:
    """Build a valid :class:`AppConfig` rooted under ``tmp_path``."""
    base = raw_dir.parent
    return AppConfig(
        environment=AppEnvironment.TESTING,
        project=ProjectConfig(name="finance-ai-test", version="0.1.0"),
        data=DataConfig(
            raw_dir=raw_dir,
            interim_dir=base / "interim",
            processed_dir=base / "processed",
            external_dir=base / "external",
        ),
        logging=LoggingConfig(level="INFO", format="json"),
        ingestion=IngestionConfig(
            interval=interval,
            delay_between_requests_ms=delay_between_requests_ms,
            continue_on_failure=continue_on_failure,
            retry=IngestionRetryConfig(
                max_retries=max_retries,
                base_delay_s=base_delay_s,
                max_delay_s=max_delay_s,
                retry_429_delay_s=retry_429_delay_s,
            ),
        ),
    )


def candle_records(
    count: int,
    *,
    first_day: date = date(2025, 1, 2),
    base_price: float = 100.0,
    step: float = 1.0,
    volume: int = 1_000_000,
) -> tuple[dict[str, Any], ...]:
    """Deterministic, domain-valid OHLCV records for ``count`` consecutive days.

    Weekends are not skipped: these are *fixtures*, not a trading
    calendar (the trading-calendar domain is a later milestone).
    """
    records = []
    for offset in range(count):
        day = first_day + timedelta(days=offset)
        open_ = base_price + step * offset
        close = open_ + step  # rising series
        high = max(open_, close) + 0.5
        low = min(open_, close) - 0.5
        records.append(
            {
                "timestamp": day.isoformat(),
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "adj_close": close,
                "volume": volume + offset * 1000,
            }
        )
    return tuple(records)


def fetched(
    symbol: str,
    start: date,
    end: date,
    records: tuple[Mapping[str, Any], ...],
    *,
    interval: str = "1d",
    source: str = "fake_source",
) -> FetchedData:
    return FetchedData(
        source=source,
        symbol=symbol,
        interval=interval,
        start=start,
        end=end,
        records=records,
    )


class FakeSource:
    """Scripted :class:`HistoricalDataSource` for engine tests.

    ``outcomes`` is a queue: each ``fetch`` pops the next entry. An
    entry may be an exception (raised to the engine) or a
    :class:`FetchedData` (returned). An exhausted queue raises a plain
    :class:`SourceError` (an unscripted call is a test bug).
    """

    name = "fake_source"

    def __init__(self, *outcomes: Any) -> None:
        self.outcomes: list[Any] = list(outcomes)
        self.calls: list[FetchParams] = []

    def fetch(self, params: FetchParams) -> FetchedData:
        self.calls.append(params)
        if not self.outcomes:
            raise SourceError(f"FakeSource({self.name}) has no scripted outcome for {params}")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome
