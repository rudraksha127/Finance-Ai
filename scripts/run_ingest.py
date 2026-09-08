"""Developer CLI to trigger historical market-data ingestion (Milestone 02).

Fetches OHLCV candles for one ticker through the configured source
(Yahoo Finance in this milestone), validates and normalizes them, then
persists them to the raw tier with a per-run metadata journal record
(DATA_INGESTION_BLUEPRINT.md). Re-running the same range is safe: rows
already stored with identical values are skipped, never duplicated.

Usage (from the repository root):

    python -m scripts.run_ingest --ticker AAPL --start 2025-01-01 --end 2025-03-31
    python -m scripts.run_ingest --ticker BRK.B --start 2024-06-01 --end 2024-12-31 --interval 1wk

Options:

    --ticker    Canonical ticker (uppercase, e.g. AAPL or BRK.B).
    --start     Inclusive start date (YYYY-MM-DD).
    --end       Inclusive end date (YYYY-MM-DD).
    --interval  1d | 1wk | 1mo (default: ingestion.interval from config).
    --env       development | testing | production (default: ENVIRONMENT
                variable, then development).

Source settings (timeout, retries, pacing) come from the ``ingestion``
configuration section. No credentials are used by the Yahoo adapter.

Exit codes: 0 success (COMPLETED or idempotent re-run), 1 the run
FAILED or only PARTIAL rows persisted, 2 usage/configuration error.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from src.config.loader import load_config
from src.core.enums import AppEnvironment, MarketInterval, values_of
from src.core.errors import ConfigError, ValidationError
from src.core.validation import validate_interval, validate_ticker
from src.data.engine import IngestionEngine
from src.data.enums import IngestionStatus
from src.data.metadata import IngestionMetadata
from src.data.sources.base import FetchParams, HistoricalDataSource
from src.data.sources.yahoo import YahooFinanceSource
from src.logging.logger import configure_from_config, get_logger

MARKET_INTERVALS = sorted(values_of(MarketInterval))
ENVIRONMENTS = sorted(values_of(AppEnvironment))

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _parse_date(raw: str, argument: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise SystemExit(
            f"error: {argument} must be an ISO date (YYYY-MM-DD), got {raw!r}"
        ) from None


def _build_source(config) -> HistoricalDataSource:
    """Composition root: map the configured source name to its adapter."""
    if config.ingestion.source == "yahoo_finance":
        return YahooFinanceSource(timeout_s=config.ingestion.request_timeout_s)
    raise ConfigError(
        f"no adapter implemented for configured ingestion.source {config.ingestion.source!r}"
    )


def _summary(record: IngestionMetadata) -> dict:
    """Collapse the metadata record to a compact machine-readable summary."""
    return {
        "ingestion_id": record.ingestion_id,
        "ticker": record.ticker,
        "interval": record.interval,
        "source": record.source,
        "requested_range": [record.requested_start, record.requested_end],
        "actual_range": [record.actual_first_timestamp, record.actual_last_timestamp],
        "status": record.ingestion_status,
        "fetched": record.fetched_record_count,
        "persisted": record.persisted_record_count,
        "skipped_duplicates": record.skipped_duplicate_count,
        "rejected": record.rejected_count,
        "conflicts": record.conflict_count,
        "retry_attempts": record.retry_attempts,
        "error_category": record.error_category,
        "error_message": record.error_message,
        "file": record.file_path,
        "checksum": record.checksum,
        "environment": record.environment,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_ingest",
        description="Fetch, validate, and store historical OHLCV candles (file-based MVP).",
    )
    parser.add_argument("--ticker", required=True, help="Canonical ticker, e.g. AAPL or BRK.B")
    parser.add_argument("--start", required=True, metavar="YYYY-MM-DD", help="Inclusive start date")
    parser.add_argument("--end", required=True, metavar="YYYY-MM-DD", help="Inclusive end date")
    parser.add_argument(
        "--interval",
        choices=MARKET_INTERVALS,
        default=None,
        help=f"Bar interval (default: config ingestion.interval, one of {MARKET_INTERVALS})",
    )
    parser.add_argument(
        "--env",
        choices=ENVIRONMENTS,
        default=None,
        help="Configuration environment (default: ENVIRONMENT variable, then development)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    # ---- Configuration + logging --------------------------------------
    try:
        environment = AppEnvironment(args.env) if args.env else None
        config = load_config(environment=environment)
    except ConfigError as error:
        print(f"configuration error: {error.message}", file=sys.stderr)
        return 2

    configure_from_config(config)
    logger = get_logger("ingestion.cli")
    logger.info(
        "cli_ingestion_start",
        ticker=args.ticker,
        start=args.start,
        end=args.end,
        interval=args.interval or config.ingestion.interval,
        environment=config.environment.value,
    )

    # ---- Validate inputs early (fail fast, never silently coerce) -----
    try:
        ticker = validate_ticker(args.ticker)
        interval = validate_interval(args.interval or config.ingestion.interval)
    except ValidationError as error:
        print(f"invalid request: {error.message}", file=sys.stderr)
        return 2

    start = _parse_date(args.start, "--start")
    end = _parse_date(args.end, "--end")
    if end < start:
        print(f"invalid request: --end {args.end} precedes --start {args.start}", file=sys.stderr)
        return 2

    # ---- Run the pipeline ----------------------------------------------
    try:
        source = _build_source(config)
    except ConfigError as error:
        print(f"configuration error: {error.message}", file=sys.stderr)
        return 2

    engine = IngestionEngine(source, config, logger=logger)
    params = FetchParams(instrument=ticker, start=start, end=end, interval=interval)
    record = engine.run_ticker(params)

    summary = _summary(record)
    print(json.dumps(summary, indent=2, sort_keys=True))

    if record.ingestion_status == IngestionStatus.FAILED.value:
        print(
            f"ingestion FAILED ({record.error_category}): {record.error_message}",
            file=sys.stderr,
        )
        return 1
    if record.ingestion_status == IngestionStatus.PARTIAL.value:
        print(
            "ingestion PARTIAL: some rows were rejected or conflicted with stored data; "
            "see the journal record for counts",
            file=sys.stderr,
        )
        return 1
    logger.info(
        "cli_ingestion_finished",
        status=record.ingestion_status,
        ticker=record.ticker,
        persisted=record.persisted_record_count,
        skipped_duplicates=record.skipped_duplicate_count,
        duration_ms=round(record.duration_ms, 1),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
