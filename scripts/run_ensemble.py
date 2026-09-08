"""CLI: build the controlled ensemble (Post-MVP Milestone 07).

Example:
    python -m scripts.run_ensemble --constituents logistic_regression_v0.3 temporal_lstm_v0.1

Diversity is measured first; weights and calibration are fitted on VALIDATION
only; the final test period is never used for any selection decision.
"""

from __future__ import annotations

import argparse
import json
import sys

from src.config.loader import load_config
from src.ensemble.engine import EnsembleBuilder


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the controlled ensemble (research).")
    parser.add_argument(
        "--constituents",
        nargs=2,
        required=True,
        metavar=("MODEL_A", "MODEL_B"),
        help="Two registered model versions to combine",
    )
    parser.add_argument("--model-version", default="ensemble_v0.1")
    parser.add_argument("--no-calibration", action="store_true", help="Skip the calibration layer")
    args = parser.parse_args()

    config = load_config()
    result = EnsembleBuilder(config).run(
        versions=tuple(args.constituents),
        model_version=args.model_version,
        use_calibration=not args.no_calibration,
    )
    payload = {
        "status": "COMPLETED",
        "model_version": result.model_version,
        "constituents": list(args.constituents),
        "weight": result.weight,
        "diversity": result.diversity,
        "calibration_version": result.calibration.get("calibration_version"),
        "validation_metrics": {
            key: result.validation_metrics[key]
            for key in ("accuracy", "f1_macro", "roc_auc_ovr_macro")
            if key in result.validation_metrics
        },
        "weight_scores": result.weight_scores,
        "model_dir": str(result.model_dir),
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
