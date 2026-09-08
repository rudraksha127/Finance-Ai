"""Developer CLI for approved baseline model training.

Examples:

    python -m scripts.run_model --model logistic_regression
    python -m scripts.run_model --model random_forest --dataset-version v0.1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence

from src.config.loader import AppEnvironment, load_config
from src.core.errors import ConfigError, FinanceAIError
from src.logging.logger import configure_from_config, get_logger
from src.model.trainer import BaselineTrainer


def main(argv: Sequence[str] | None = None) -> int:
    """Run one configured baseline experiment and print its result."""
    parser = argparse.ArgumentParser(
        prog="run_model",
        description="Train an approved baseline model on an immutable dataset.",
    )
    parser.add_argument(
        "--model",
        default="logistic_regression",
        choices=("logistic_regression", "random_forest", "lightgbm", "xgboost"),
    )
    parser.add_argument("--dataset-version", default=None)
    parser.add_argument("--feature-version", default=None)
    parser.add_argument("--label-version", default=None)
    parser.add_argument("--model-version", default=None)
    parser.add_argument("--experiment-id", default=None)
    parser.add_argument("--env", choices=("development", "testing", "production"))
    args = parser.parse_args(argv)

    try:
        config = load_config(
            AppEnvironment(args.env) if args.env else None,
            environ={**os.environ, "ENVIRONMENT": os.environ.get("ENVIRONMENT", "development")},
        )
    except ConfigError as error:
        print(f"error: {error.message}", file=sys.stderr)
        return 2
    configure_from_config(config)
    log = get_logger("run_model")
    try:
        result = BaselineTrainer(config).run(
            model_name=args.model,
            dataset_version=args.dataset_version,
            feature_version=args.feature_version,
            label_version=args.label_version,
            model_version=args.model_version,
            experiment_id=args.experiment_id,
        )
    except FinanceAIError as error:
        log.error("baseline_training_failed", error=error.message, context=error.context)
        return 1
    print(
        json.dumps(
            {
                "experiment_id": result.experiment_id,
                "model_version": result.model_version,
                "config_version": result.config_version,
                "dataset_version": result.dataset_version,
                "feature_version": result.feature_version,
                "label_version": result.label_version,
                "metrics": result.metrics,
                "artifact_dir": str(result.artifact_dir),
                "experiment_dir": str(result.experiment_dir),
                "training_seconds": result.training_seconds,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
