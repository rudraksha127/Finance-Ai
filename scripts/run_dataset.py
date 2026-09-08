"""Developer CLI to build a training dataset (Milestone 06).

Aligns persisted feature sets (Milestone 04) with label sets (Milestone
05) on exact (ticker, timestamp), drops warm-up/invalid rows (recorded),
splits chronologically into TRAIN/VAL/TEST, and persists an immutable,
versioned dataset under ``data/processed/datasets/dataset_{version}/``
(DATASET_BUILDER_BLUEPRINT.md).

Usage (from the repository root):

    python -m scripts.run_dataset
    python -m scripts.run_dataset --ticker AAPL --ticker MSFT
    python -m scripts.run_dataset --feature-version v0.1 --label-version v0.1 --output-version v0.1
    python -m scripts.run_dataset --start 2025-01-01 --end 2025-12-31

Options:

    --ticker            Repeatable; restrict instruments (default: every
                        ticker with both a persisted feature + label set).
    --feature-version   Feature-set version (default: config features.version).
    --label-version     Label-set version (default: config dataset.label_version).
    --output-version    Dataset (output) version (default: config
                        dataset_builder.dataset_version).
    --interval          1d | 1wk | 1mo (default: config ingestion.interval).
    --start / --end     Inclusive ISO observation range filter (optional).
    --env               development | testing | production.

Exit codes: 0 success (or identical immutable rebuild no-op), 1 build
failure (validation/version mismatch/persistence), 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence

from src.config.loader import load_config
from src.core.enums import AppEnvironment, MarketInterval, values_of
from src.core.errors import ConfigError, FinanceAIError
from src.dataset.builder import DatasetBuilder
from src.logging.logger import configure_from_config, get_logger

MARKET_INTERVALS = sorted(values_of(MarketInterval))
ENVIRONMENTS = sorted(values_of(AppEnvironment))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_dataset",
        description="Build a versioned training dataset from features + labels.",
    )
    parser.add_argument(
        "--ticker",
        action="append",
        default=None,
        help="Instrument to include (repeatable; default: all with both artifacts)",
    )
    parser.add_argument("--feature-version", default=None, help="Feature-set version")
    parser.add_argument("--label-version", default=None, help="Label-set version")
    parser.add_argument("--output-version", default=None, help="Dataset version")
    parser.add_argument(
        "--interval",
        default=None,
        choices=MARKET_INTERVALS,
        help="Candle interval (default: config ingestion.interval)",
    )
    parser.add_argument("--start", default=None, help="Inclusive start (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="Inclusive end (YYYY-MM-DD)")
    parser.add_argument("--env", default=None, choices=ENVIRONMENTS, help="Environment")
    args = parser.parse_args(argv)

    try:
        environ = {**os.environ, "ENVIRONMENT": os.environ.get("ENVIRONMENT", "development")}
        config = load_config(AppEnvironment(args.env) if args.env else None, environ=environ)
    except ConfigError as error:
        print(f"error: {error.message}", file=sys.stderr)
        return 2
    configure_from_config(config)

    log = get_logger("run_dataset")
    try:
        builder = DatasetBuilder(config)
        result = builder.run(
            tickers=args.ticker,
            feature_version=args.feature_version,
            label_version=args.label_version,
            dataset_version=args.output_version,
            interval=args.interval,
            start=args.start,
            end=args.end,
        )
    except FinanceAIError as error:
        log.error("dataset_build_failed", error=error.message, context=error.context)
        return 1

    summary = {
        "dataset_version": result.dataset_version,
        "version_hash": result.version_hash,
        "tickers": list(result.tickers),
        "feature_version": result.feature_version,
        "label_version": result.label_version,
        "interval": result.interval,
        "requested_range": list(result.requested_range),
        "actual_range": list(result.actual_range),
        "rows": {
            "input": result.input_rows,
            "dropped_warmup": result.dropped_warmup,
            "dropped_invalid_label": result.dropped_invalid_label,
            "invalid_rows": result.dropped_invalid_label,
            "missing_feature_count": result.missing_feature_count,
            "missing_label_count": result.missing_label_count,
            "dropped_unmatched": result.dropped_unmatched,
            "dropped_out_of_range": result.dropped_out_of_range,
            "final": result.total_rows,
        },
        "splits": result.split_rows,
        "validation": {
            "checks_run": result.validation.checks_run,
            "checks_passed": result.validation.checks_passed,
            "errors": len(result.validation.errors),
            "warnings": len(result.validation.warnings),
        },
        "quality": {
            "score": result.quality.score,
            "rating": result.quality.rating,
        },
        "output_dir": str(result.dataset_dir),
        "duration_ms": result.duration_ms,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    log.info("dataset_build_ok", **summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
