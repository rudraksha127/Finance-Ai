"""Developer CLI to generate a label set (Milestone 05).

Computes direction labels (UP/DOWN/HOLD) from a cleaned interim CSV
(Milestone-03 output) using the approved target: 5-trading-day horizon,
simple future return on the adjusted close, fixed +/-1% thresholds
(LABEL_GENERATION_BLUEPRINT.md). Persists a versioned, conflict-protected
Parquet label set under ``data/processed/labels/``.

Usage (from the repository root):

    python -m scripts.run_labels --ticker AAPL
    python -m scripts.run_labels --ticker MSFT --source data/interim/cleaned_20250315_MSFT_daily.csv
    python -m scripts.run_labels --ticker AAPL --horizon 5 --label-version v0.1

Options:

    --ticker           Canonical ticker (e.g. AAPL or BRK.B).
    --interval         1d | 1wk | 1mo (default: config ingestion.interval).
    --source           Cleaned interim CSV (default: latest cleaned file).
    --horizon          Prediction horizon in trading days (default: config
                       dataset.label_window = 5).
    --label-version    Label-set version (default: config dataset.label_version).
    --env              development | testing | production.

Exit codes: 0 success, 1 generation/persistence failure, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from src.config.loader import load_config
from src.core.enums import AppEnvironment, MarketInterval, values_of
from src.core.errors import ConfigError, FinanceAIError
from src.labels.engine import LabelEngine
from src.logging.logger import configure_from_config, get_logger

MARKET_INTERVALS = sorted(values_of(MarketInterval))
ENVIRONMENTS = sorted(values_of(AppEnvironment))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_labels",
        description="Generate the UP/DOWN/HOLD label set for one ticker.",
    )
    parser.add_argument("--ticker", required=True, help="Canonical ticker, e.g. AAPL")
    parser.add_argument(
        "--interval",
        default=None,
        choices=MARKET_INTERVALS,
        help="Candle interval (default: config ingestion.interval)",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Cleaned interim CSV (default: latest cleaned file for the ticker)",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=None,
        help="Prediction horizon in trading days (default: config dataset.label_window)",
    )
    parser.add_argument(
        "--label-version",
        default=None,
        help="Label-set version (default: config dataset.label_version)",
    )
    parser.add_argument("--env", default=None, choices=ENVIRONMENTS, help="Environment")
    args = parser.parse_args(argv)

    try:
        environ = {**os.environ, "ENVIRONMENT": os.environ.get("ENVIRONMENT", "development")}
        config = load_config(AppEnvironment(args.env) if args.env else None, environ=environ)
    except ConfigError as error:
        print(f"error: {error.message}", file=sys.stderr)
        return 2
    configure_from_config(config)

    log = get_logger("run_labels")
    try:
        engine = LabelEngine(config)
        result = engine.run(
            args.ticker,
            args.interval or config.ingestion.interval,
            source=Path(args.source) if args.source else None,
            label_version=args.label_version,
            horizon=args.horizon,
        )
    except FinanceAIError as error:
        log.error("label_generation_failed", error=error.message, context=error.context)
        return 1

    dist = result.distribution
    summary = {
        "ticker": result.ticker,
        "interval": result.interval,
        "label_version": result.label_version,
        "version_hash": result.version_hash,
        "horizon": result.horizon,
        "thresholds": {"up": result.threshold_up, "down": result.threshold_down},
        "source_file": str(result.source_file),
        "source_checksum": result.source_checksum,
        "distribution": {
            "total_rows": dist.total_rows,
            "valid_rows": dist.valid_rows,
            "up": dist.up_count,
            "down": dist.down_count,
            "hold": dist.hold_count,
            "up_pct": dist.up_pct,
            "down_pct": dist.down_pct,
            "hold_pct": dist.hold_pct,
            "invalid": dist.invalid_count,
            "invalid_future_window": dist.invalid_future_window,
            "invalid_price": dist.invalid_price,
        },
        "balance_warnings": list(result.balance_warnings),
        "output_file": str(result.output_file),
        "duration_ms": result.duration_ms,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    log.info("label_generation_ok", **summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
