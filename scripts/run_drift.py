"""Developer CLI for the drift detection engine (Post-MVP Milestone 02).

Manual drift check (the same code path a scheduled cron run would use):

    python -m scripts.run_drift --instrument AAPL
    python -m scripts.run_drift --instrument AAPL --model random_forest_v0.3

Resolve an open drift event (manual resolution, milestone section 30):

    python -m scripts.run_drift --resolve <event_id>

Exit codes: 0 HEALTHY/COMPLETED, 1 drift detected or FAILED, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from src.config.loader import AppEnvironment, load_config
from src.core.errors import ConfigError
from src.drift.engine import DriftEngine
from src.logging.logger import configure_from_config, get_logger

ENVIRONMENTS = sorted(env.value for env in AppEnvironment)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_drift",
        description="Run a drift check (data/feature/prediction/performance) "
        "against the stored reference window.",
    )
    parser.add_argument("--instrument", default=None, help="Ticker, e.g. AAPL")
    parser.add_argument("--model", dest="model_version", default=None)
    parser.add_argument("--feature-version", default=None)
    parser.add_argument("--reference", default=None, help="Reference window size (rows)")
    parser.add_argument("--current", default=None, help="Current window size (rows)")
    parser.add_argument("--resolve", default=None, metavar="EVENT_ID", help="Resolve an open event")
    parser.add_argument("--env", choices=ENVIRONMENTS, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        config = load_config(AppEnvironment(args.env) if args.env else None)
    except ConfigError as error:
        print(f"configuration error: {error.message}", file=sys.stderr)
        return 2
    configure_from_config(config)
    get_logger("drift.cli")

    engine = DriftEngine(config)

    if args.resolve:
        resolved = engine.resolve_event(args.resolve)
        print(json.dumps({"event_id": args.resolve, "resolved": resolved}))
        return 0 if resolved else 1

    if not args.instrument:
        parser.error("--instrument is required unless --resolve is used")

    reference_size = int(args.reference) if args.reference else None
    current_size = int(args.current) if args.current else None
    engine = DriftEngine(
        config,
        reference_size=reference_size or engine.reference_size,
        current_size=current_size or engine.current_size,
    )
    report = engine.run_check(
        args.instrument,
        model_version=args.model_version,
        feature_version=args.feature_version,
    )
    print(
        json.dumps(
            {
                "run_id": report.run_id,
                "status": report.status,
                "health": report.health,
                "reference_window": list(report.reference_window),
                "current_window": list(report.current_window),
                "features_checked": len(report.feature_drifts),
                "prediction_severity": report.prediction_severity,
                "performance_status": report.performance_status,
                "insufficient_data": report.insufficient_data,
                "events": [
                    {
                        "event_id": e.event_id,
                        "type": e.event_type,
                        "severity": e.severity,
                        "metric": e.metric,
                        "observed": e.observed_value,
                        "baseline": e.baseline_value,
                        "occurrence_count": e.occurrence_count,
                    }
                    for e in report.events
                ],
                "top_drifted": [
                    {"feature": d.feature, "psi": d.psi, "severity": d.severity}
                    for d in report.feature_drifts[:10]
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if report.status == "FAILED":
        return 1
    return 0 if report.health == "HEALTHY" else 1


if __name__ == "__main__":
    sys.exit(main())
