"""CLI: train the temporal LSTM model (Post-MVP Milestone 06).

Examples:
    python -m scripts.run_temporal --ticker AAPL
    python -m scripts.run_temporal --ticker AAPL --sequence-length-experiment 5 10 20

The sequence-length experiment trains one model version per length using
VALIDATION metrics only for comparison (the final test set is never used for
selection) and records every run as a separate experiment artifact.
"""

from __future__ import annotations

import argparse
import json
import sys

from src.config.loader import load_config
from src.logging.logger import get_logger
from src.temporal.model import TemporalTrainer

logger = get_logger("temporal.cli")


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the temporal LSTM model (research).")
    parser.add_argument("--dataset-version", default=None)
    parser.add_argument("--feature-version", default=None)
    parser.add_argument("--label-version", default=None)
    parser.add_argument("--model-version", default=None)
    parser.add_argument(
        "--sequence-length-experiment",
        nargs="*",
        type=int,
        default=None,
        help="Train one candidate per sequence length (validation-only comparison).",
    )
    args = parser.parse_args()

    config = load_config()
    trainer = TemporalTrainer(config)
    lengths = args.sequence_length_experiment or [None]
    results = []
    for length in lengths:
        model_version = args.model_version
        if length is not None and len(lengths) > 1:
            base = (args.model_version or config.temporal.model_version).rsplit("_v", 1)
            model_version = f"{base[0]}_seq{length}_v0.1"
        result = trainer.run(
            dataset_version=args.dataset_version,
            feature_version=args.feature_version,
            label_version=args.label_version,
            model_version=model_version,
            sequence_length=length,
        )
        results.append(result)

    payload = {
        "status": "COMPLETED",
        "runs": [
            {
                "experiment_id": result["experiment_id"],
                "model_version": result["model_version"],
                "sequence_length": result["sequence_length"],
                "metrics": result["metrics"],
                "artifact_dir": str(config.model.artifact_dir / result["model_version"]),
            }
            for result in results
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if len(results) > 1:
        logger.info(
            "sequence_length_experiment_completed",
            candidates=len(results),
            note="selection must use validation metrics only; final test untouched",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
