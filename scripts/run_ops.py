"""Developer CLI for the observability & operations center (P05).

    python -m scripts.run_ops --snapshot
    python -m scripts.run_ops --acknowledge <event_id>
    python -m scripts.run_ops --resolve <event_id>

Exit codes: 0 success, 2 usage error. A CRITICAL system status is still
reported as exit 0 (it is an operational fact, not a CLI failure).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from src.config.loader import AppEnvironment, load_config
from src.core.errors import ConfigError
from src.logging.logger import configure_from_config, get_logger
from src.operations.engine import OperationsEngine

ENVIRONMENTS = sorted(env.value for env in AppEnvironment)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_ops", description="Operations center commands.")
    parser.add_argument("--snapshot", action="store_true", help="Build the system health snapshot")
    parser.add_argument("--acknowledge", metavar="EVENT_ID")
    parser.add_argument("--resolve", metavar="EVENT_ID")
    parser.add_argument("--env", choices=ENVIRONMENTS, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        config = load_config(AppEnvironment(args.env) if args.env else None)
    except ConfigError as error:
        print(f"configuration error: {error.message}", file=sys.stderr)
        return 2
    configure_from_config(config)
    logger = get_logger("ops.cli")
    engine = OperationsEngine(config)

    if args.acknowledge:
        print(
            json.dumps(
                {
                    "event_id": args.acknowledge,
                    "acknowledged": engine.acknowledge_event(args.acknowledge),
                }
            )
        )
        return 0
    if args.resolve:
        print(
            json.dumps({"event_id": args.resolve, "resolved": engine.resolve_event(args.resolve)})
        )
        return 0
    if args.snapshot:
        snapshot = engine.snapshot()
        payload = asdict_pretty(snapshot)
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        logger.info("ops_snapshot", system_status=snapshot.system_status)
        return 0
    parser.error("one of --snapshot/--acknowledge/--resolve is required")
    return 2


def asdict_pretty(snapshot):
    """JSON-friendly dict for the snapshot."""
    return {
        "generated_at": snapshot.generated_at,
        "system_status": snapshot.system_status,
        "overrides": snapshot.overrides,
        "components": [
            {
                "component": c.component,
                "status": c.status,
                "last_success": c.last_success,
                "last_failure": c.last_failure,
                "last_run": c.last_run,
                "error_count": c.error_count,
                "warning_count": c.warning_count,
                "detail": c.detail,
            }
            for c in snapshot.components
        ],
        "data_freshness": snapshot.data_freshness,
        "model_health": snapshot.model_health,
        "drift_status": snapshot.drift_status,
        "open_alerts": [
            {
                "event_id": e.event_id,
                "component": e.component,
                "event_type": e.event_type,
                "severity": e.severity,
                "occurrence_count": e.occurrence_count,
                "message": e.message,
            }
            for e in snapshot.open_alerts
        ],
    }


if __name__ == "__main__":
    sys.exit(main())
