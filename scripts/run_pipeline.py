"""Developer CLI for the autonomous data pipeline (Post-MVP Milestone 01).

Manual trigger using the SAME engine code path as a scheduled run
(milestone section 28 — no duplicated workflows):

    python -m scripts.run_pipeline --instrument AAPL
    python -m scripts.run_pipeline --instrument AAPL --from 2026-09-01 --to 2026-09-05
    python -m scripts.run_pipeline --instrument AAPL --dry-run

Scheduled execution is OS cron invoking this exact command (section 9 of
docs/AUTONOMOUS_DATA_PIPELINE_IMPLEMENTATION.md). Exit codes:
0 success (or empty/idempotent run), 1 FAILED/PARTIAL, 2 usage/config error.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from src.config.loader import AppEnvironment, load_config
from src.core.errors import ConfigError
from src.logging.logger import configure_from_config, get_logger
from src.pipeline.engine import PipelineEngine

ENVIRONMENTS = sorted(env.value for env in AppEnvironment)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_pipeline",
        description="Run one controlled incremental data pipeline pass "
        "(ingest -> clean -> features -> labels -> dataset -> quality gate).",
    )
    parser.add_argument("--instrument", required=True, help="Canonical ticker, e.g. AAPL")
    parser.add_argument("--interval", default=None, help="1d | 1wk | 1mo (default: config)")
    parser.add_argument(
        "--from", dest="start", default=None, help="Inclusive start date (YYYY-MM-DD)"
    )
    parser.add_argument("--to", dest="end", default=None, help="Inclusive end date (YYYY-MM-DD)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the plan (watermark, range, stages) without writing anything",
    )
    parser.add_argument("--env", choices=ENVIRONMENTS, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        config = load_config(AppEnvironment(args.env) if args.env else None)
    except ConfigError as error:
        print(f"configuration error: {error.message}", file=sys.stderr)
        return 2
    configure_from_config(config)
    logger = get_logger("pipeline.cli")
    logger.info(
        "pipeline_cli_start",
        instrument=args.instrument,
        interval=args.interval,
        start=args.start,
        end=args.end,
        dry_run=args.dry_run,
        environment=config.environment.value,
    )

    engine = PipelineEngine(config)
    result = engine.run(
        args.instrument,
        interval=args.interval,
        start=args.start,
        end=args.end,
        dry_run=args.dry_run,
    )
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "instrument": result.instrument,
                "interval": result.interval,
                "status": result.status,
                "pipeline_config_version": result.pipeline_config_version,
                "requested_range": list(result.requested_range or (None, None)),
                "stages": [
                    {
                        "name": s.name,
                        "status": s.status,
                        "records_processed": s.records_processed,
                        "errors": s.errors,
                    }
                    for s in result.stages
                ],
                "dataset_version": result.dataset_version,
                "dataset_hash": result.dataset_hash,
                "error": result.error,
                "warnings": result.warnings,
                "end_watermark": (
                    result.end_watermark.last_successful_timestamp if result.end_watermark else None
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if result.status == "COMPLETED":
        return 0
    if result.status in ("FAILED", "PARTIAL"):
        return 1
    return 0  # SKIPPED (lock held / nothing to do) is not a failure


if __name__ == "__main__":
    sys.exit(main())
