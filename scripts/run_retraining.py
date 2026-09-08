"""Developer CLI for controlled autonomous retraining (Post-MVP Milestone 03).

Manual trigger using the SAME workflow as a scheduled trigger:

    python -m scripts.run_retraining --reason "monthly schedule" --dataset v0.3

Dry run (plan only — no training, no state change):

    python -m scripts.run_retraining --dry-run

Exit codes: 0 success/approved/skip, 1 rejected/failed, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from src.config.loader import AppEnvironment, load_config
from src.core.errors import ConfigError
from src.logging.logger import configure_from_config, get_logger
from src.retraining.engine import RetrainingEngine

ENVIRONMENTS = sorted(env.value for env in AppEnvironment)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_retraining",
        description="Run one controlled retraining pass: trigger -> eligibility -> "
        "candidate training -> evaluation -> promotion gates -> decision.",
    )
    parser.add_argument("--reason", default="manual trigger", help="Trigger reason")
    parser.add_argument("--dataset", dest="dataset_version", default=None, help="Dataset version")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without training")
    parser.add_argument("--env", choices=ENVIRONMENTS, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        config = load_config(AppEnvironment(args.env) if args.env else None)
    except ConfigError as error:
        print(f"configuration error: {error.message}", file=sys.stderr)
        return 2
    configure_from_config(config)
    logger = get_logger("retraining.cli")
    logger.info(
        "retraining_cli_start",
        reason=args.reason,
        dataset=args.dataset_version,
        dry_run=args.dry_run,
        environment=config.environment.value,
    )

    engine = RetrainingEngine(config)
    run = engine.evaluate_trigger(
        trigger_type="manual",
        trigger_reason=args.reason,
        dataset_version=args.dataset_version,
        dry_run=args.dry_run,
    )
    print(
        json.dumps(
            {
                "retraining_run_id": run.retraining_run_id,
                "trigger_type": run.trigger_type,
                "trigger_reason": run.trigger_reason,
                "current_model_version": run.current_model_version,
                "candidate_model_version": run.candidate_model_version,
                "dataset_version": run.dataset_version,
                "feature_version": run.feature_version,
                "label_version": run.label_version,
                "fingerprint": run.fingerprint,
                "status": run.status,
                "decision": run.decision,
                "gate_results": run.gate_results,
                "metrics_comparison": run.metrics_comparison,
                "error": run.error,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if run.status in ("FAILED",):
        return 1
    if run.decision == "CANDIDATE_REJECTED":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
