"""Developer CLI to generate a feature dataset (Milestone 04).

Computes all 52 approved MVP features from a cleaned interim CSV
(Milestone-03 output), validates them (FVAL-*), and persists a
versioned, conflict-protected Parquet dataset under
``data/processed/features/`` (FEATURE_ENGINEERING_BLUEPRINT.md).

Usage (from the repository root):

    python -m scripts.run_features --ticker AAPL
    python -m scripts.run_features --ticker MSFT --source data/interim/cleaned_20250315_MSFT_daily.csv
    python -m scripts.run_features --ticker AAPL --feature-version v0.1

Options:

    --ticker            Canonical ticker (e.g. AAPL or BRK.B).
    --interval          1d | 1wk | 1mo (default: ingestion.interval from config).
    --source            Cleaned interim CSV; defaults to the latest cleaned
                        file for the ticker.
    --feature-version   Feature-set version (default: features.version from
                        config, currently v0.1).
    --env               development | testing | production.

Exit codes: 0 success, 1 validation/persistence failure, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from src.config.loader import load_config
from src.core.enums import AppEnvironment, MarketInterval, values_of
from src.core.errors import ConfigError, FinanceAIError
from src.features.engine import FeatureEngine
from src.logging.logger import configure_from_config, get_logger

MARKET_INTERVALS = sorted(values_of(MarketInterval))
ENVIRONMENTS = sorted(values_of(AppEnvironment))

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_features",
        description="Generate the 52-feature MVP dataset for one ticker.",
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
        "--feature-version",
        default=None,
        help="Feature-set version (default: config features.version)",
    )
    parser.add_argument("--env", default=None, choices=ENVIRONMENTS, help="Environment")
    args = parser.parse_args(argv)

    try:
        config = load_config(
            AppEnvironment(args.env) if args.env else None,
            environ=_env_with_defaults(),
        )
    except ConfigError as error:
        print(f"error: {error.message}", file=sys.stderr)
        return 2
    configure_from_config(config)

    log = get_logger("run_features")
    try:
        engine = FeatureEngine(config)
        result = engine.run(
            args.ticker,
            args.interval or config.ingestion.interval,
            source=Path(args.source) if args.source else None,
            feature_version=args.feature_version,
        )
    except FinanceAIError as error:
        log.error("feature_generation_failed", error=error.message, context=error.context)
        return 1

    summary = {
        "ticker": result.ticker,
        "interval": result.interval,
        "feature_set_version": result.feature_set_version,
        "version_hash": result.version_hash,
        "source_file": str(result.source_file),
        "source_checksum": result.source_checksum,
        "row_count": result.row_count,
        "feature_count": result.feature_count,
        "warmup_rows": result.warmup_rows,
        "validation": {
            "total": result.validation.total_features,
            "valid": result.validation.valid_features,
            "errors": len(result.validation.errors),
            "warnings": len(result.validation.warnings),
            "duplicate_pairs": len(result.validation.duplicate_pairs),
        },
        "output_file": str(result.output_file),
        "duration_ms": result.duration_ms,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    log.info("feature_generation_ok", **summary)
    return 0


def _env_with_defaults() -> dict[str, str]:
    """Config loader reads ``ENVIRONMENT``; default to development."""
    import os

    return {**os.environ, "ENVIRONMENT": os.environ.get("ENVIRONMENT", "development")}


if __name__ == "__main__":
    sys.exit(main())
