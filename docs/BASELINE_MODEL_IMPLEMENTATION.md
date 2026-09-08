# Baseline Model Implementation

Milestone 07 implements the approved scikit-learn baseline training pipeline.
It consumes immutable Dataset Builder snapshots and trains either logistic
regression or random forest classifiers for the `UP`/`DOWN`/`HOLD` target.

## Training flow

1. Load and integrity-check the requested dataset snapshot.
2. Validate the dataset, feature registry, target classes, and feature/label
   versions.
3. Use the persisted TRAIN split for fitting and VALIDATION for model feedback.
   The TEST split is validated and recorded but never used for fitting or
   configuration decisions.
4. Fit `StandardScaler` on TRAIN only for logistic regression. Random forest
   uses the original feature values.
5. Train the configured estimator with random seed `42` and `n_jobs=1`.
6. Persist predictions, metrics, feature importance, and reproducibility
   metadata.

The configured baseline values are conservative: logistic regression uses
`C=1.0`, `lbfgs`, `l2`, and `max_iter=1000`; random forest uses 100 trees,
`max_depth=10`, `min_samples_split=5`, and `min_samples_leaf=2`.

## Command

```bash
python -m scripts.run_model --model logistic_regression --dataset-version v0.1
python -m scripts.run_model --model random_forest --dataset-version v0.1
```

Feature and label versions default to `config/default.yaml` and can be
specified explicitly. Existing model versions are never overwritten.

## Artifacts

Model artifacts are stored under
`data/processed/models/{model_version}/`. Each model directory contains the
serialized estimator, optional scaler, and metadata. Each run receives a
unique experiment directory under
`data/processed/models/experiments/{experiment_id}/` containing:

- `metadata.json`
- `config_snapshot.json`
- `model.joblib` and optional `scaler.joblib`
- `val_predictions.csv`
- `confusion_matrix.csv`
- `feature_importance.csv`
- `report.md`

## Metrics and limitations

The report records accuracy, macro precision, macro recall, macro F1,
class-wise metrics, confusion matrix, prediction distribution, and
multiclass one-vs-rest ROC-AUC and PR-AUC when all classes occur in
validation. Ranking metrics are `null` (explicitly not applicable) rather
than silently omitted when a class is absent or probabilities are
unavailable.
Coefficient magnitude and tree impurity importance are descriptive, not
causal, and are not used for automatic feature removal. The pipeline does not
claim trading profitability and does not implement backtesting, calibration,
inference serving, or hyperparameter optimization.

## Reproducibility

Every experiment records model, dataset, feature, label, and configuration
versions, the git commit of the training checkout (when available;
`unknown` in a repository without commits), random seed, split periods, row
counts, package versions, and the training timestamp. Re-running with the
same dataset, configuration, and seed produces materially equivalent
predictions; experiment IDs remain unique.
