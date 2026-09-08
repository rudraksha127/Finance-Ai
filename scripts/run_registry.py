"""Developer CLI for the model registry (Post-MVP Milestone 04).

    python -m scripts.run_registry --list
    python -m scripts.run_registry --show <model_version>
    python -m scripts.run_registry --promote <candidate> [--dry-run]
    python -m scripts.run_registry --rollback <target> [--dry-run]

Exit codes: 0 success, 1 registry error, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from src.config.loader import AppEnvironment, load_config
from src.core.errors import ConfigError
from src.logging.logger import configure_from_config, get_logger
from src.registry.engine import ModelRegistry, RegistryError

ENVIRONMENTS = sorted(env.value for env in AppEnvironment)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_registry", description="Model registry operations.")
    parser.add_argument("--list", action="store_true", help="List registered models")
    parser.add_argument("--show", metavar="MODEL_VERSION", help="Show one model record")
    parser.add_argument("--promote", metavar="CANDIDATE", help="Promote an APPROVED candidate")
    parser.add_argument("--rollback", metavar="TARGET", help="Roll back to a previous model")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show the plan without changing state"
    )
    parser.add_argument("--reason", default="", help="Audit reason")
    parser.add_argument("--env", choices=ENVIRONMENTS, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        config = load_config(AppEnvironment(args.env) if args.env else None)
    except ConfigError as error:
        print(f"configuration error: {error.message}", file=sys.stderr)
        return 2
    configure_from_config(config)
    get_logger("registry.cli")
    registry = ModelRegistry(config)

    try:
        if args.list:
            models = registry.list_models()
            print(
                json.dumps(
                    [
                        {
                            "model_version": m.model_version,
                            "status": m.status,
                            "dataset_version": m.dataset_version,
                            "feature_version": m.feature_version,
                            "label_version": m.label_version,
                            "registered_at": m.registered_at,
                            "activated_at": m.activated_at,
                        }
                        for m in models
                    ],
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.show:
            record = registry.get_model(args.show)
            print(json.dumps(record.__dict__, indent=2, sort_keys=True, default=str))
            return 0
        if args.promote:
            plan = registry.promote_model(args.promote, dry_run=args.dry_run, reason=args.reason)
            print(json.dumps(plan, indent=2, sort_keys=True, default=str))
            return 0
        if args.rollback:
            plan = registry.rollback_model(args.rollback, dry_run=args.dry_run, reason=args.reason)
            print(json.dumps(plan, indent=2, sort_keys=True, default=str))
            return 0
        parser.error("one of --list/--show/--promote/--rollback is required")
        return 2
    except RegistryError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
