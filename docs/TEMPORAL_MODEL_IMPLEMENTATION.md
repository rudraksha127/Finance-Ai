# TEMPORAL MODEL IMPLEMENTATION (Post-MVP Milestone 06)

Status: IMPLEMENTED (research-only). This document is the authoritative record of the
temporal model added in Post-MVP Milestone 06. It reuses the existing dataset contracts,
feature versions, label versions, evaluation framework, experiment tracking, model
registry, and backtest engine. No second ML system was created.

---

## 1. Selected architecture and rationale

**Selected: LSTM (compact, single-layer).**

| Criterion | LSTM assessment |
|---|---|
| Sequence modelling | Gated recurrence captures multi-day context; adequate for daily bars |
| Training complexity | Small (thousands of parameters), trains in seconds on CPU |
| Dataset requirements | Works with ~800 rows; Transformers need far more data to beat recurrence |
| Compute requirements | CPU-only training is practical; no GPU required |
| Interpretability | Limited (documented honestly; no fabricated attention explanations) |
| Overfitting risk | Lower than a Transformer at this sample size; controlled with early stopping + dropout |
| MVP suitability | Smallest defensible architecture that genuinely consumes sequences |

Rejected for this milestone: GRU (marginal saving, LSTM is the reference recurrence
architecture), TCN (dilated convolutions need longer histories to shine),
Transformer (quadratic attention, high overfitting risk at ~550 training sequences).

## 2. Sequence construction

At time T (a dataset row):

```
sequence = feature rows [T-L+1 ... T]        (L = sequence_length)
target   = label at row T                    (encodes Y(T+H); produced by the label engine)
```

- The target contract is **identical to the baseline**: the label column at row T.
  No new target was created.
- Sequences are built strictly **within one split** (train/val/test separately), so no
  sequence crosses a split boundary (leakage Test D).
- The first `L-1` rows of each split are **context-only** and yield no sequence.

## 3. Sequence length

Configuration-driven (`temporal.sequence_length`). A small controlled experiment was run
over `{5, 10, 20}` (section 8 of this document). Selection used **validation metrics only**.

## 4. Temporal leakage rule (mandatory)

For a sequence ending at T: **allowed = observations <= T; forbidden = T+1 and later.**

The builder never uses centered windows, future rows, future-fill, or future
normalization. Enforced by `src/temporal/sequence.py` and proven by tests:

- **Test A — future mutation**: mutating rows after T leaves sequences ending at T unchanged.
- **Test B — dataset extension**: appending future rows leaves earlier sequences identical.
- **Test C — boundary**: the first sequence uses exactly L rows.
- **Test D — split isolation**: sequences are built per split; none crosses a boundary.

## 5. Normalization

`StandardScaler` is **fit on TRAIN rows only**, then applied to validation and test.
The fitted scaler is persisted inside the model artifact. Never fit on all data.

## 6. Input shape and feature order

- Contract: `[batch, sequence_length, feature_count]`.
- Feature order comes from the versioned dataset's `feature_names.json`, which is
  validated against `FEATURE_COLUMNS` by the existing dataset loader. The artifact
  stores `feature_names`, `sequence_length`, and `input_dimension`; inference rejects
  any matrix with a different width or non-finite values (fail loudly, no silent
  feature-order changes).

## 7. Training configuration (defaults, config-driven)

| Parameter | Default | Notes |
|---|---|---|
| `sequence_length` | 10 | two trading weeks of daily bars |
| `hidden_size` | 32 | compact |
| `num_layers` | 1 | single-layer LSTM |
| `dropout` | 0.0 | single layer → LSTM dropout unused; head has no hidden layer |
| `batch_size` | 32 | |
| `max_epochs` | 100 | hard cap |
| `patience` | 10 | early stopping on validation loss |
| `learning_rate` | 1e-3 | Adam |
| `weight_decay` | 0.0 | no blind regularization |
| seed | `model.random_seed` | torch + numpy seeded; single-threaded torch for determinism |

- **Loss**: `CrossEntropyLoss` on class indices (multi-class UP/DOWN/HOLD). Class
  imbalance handling reuses the approved baseline strategy (none) — no synthetic
  oversampling (milestone section 26).
- **Early stopping** monitors **validation loss only**; the final test set is never
  monitored (section 17).
- **Checkpointing**: the best-validation-loss state dict is checkpointed per epoch to
  `models/experiments/<exp_id>/checkpoint.pt` with `{epoch, val_loss, dataset_version,
  feature_version, label_version}`; the best checkpoint — not the final epoch — is
  restored before evaluation and persistence (section 18).

## 8. Sequence-length experiment (validation only)

Run over L ∈ {5, 10, 20} with identical data/config on dataset v0.3 (AAPL daily):

| Sequence length | Val accuracy | Val f1_macro | Val ROC-AUC (OvR macro) |
|---|---|---|---|
| 5 | 0.3613 | 0.2716 | 0.4731 |
| **10 (selected)** | **0.3697** | **0.2953** | **0.4569** |
| 20 | 0.3445 | 0.2649 | 0.4390 |

Selection criterion: validation macro-F1 → **L=10 selected**. The final test set was
not used for this choice (milestone section 36). All three candidates were persisted
as separate experiment artifacts (`temporal_lstm_seq5_v0.1`, `temporal_lstm_v0.1`,
`temporal_lstm_seq20_v0.1`).

## 9. Artifact and model version

- Model version: `temporal_lstm_v0.1` (distinct namespace; never overwrites
  `logistic_regression_v0.3` / `random_forest_v0.3`).
- Artifact layout mirrors the baseline exactly so the existing registry, backtest
  engine, and API work unchanged:
  `models/temporal_lstm_v0.1/{model.joblib, metadata.json}` plus the experiment
  directory with `config_snapshot.json`, `val_predictions.csv`, `checkpoint.pt`,
  `report.md`.
- `model.joblib` contains a **sklearn-compatible wrapper**
  (`TemporalLSTMClassifier`) exposing `predict`, `predict_proba`, and
  `classes_ = ("UP", "DOWN", "HOLD")` in the canonical order shared by the API,
  backtest, and calibration layers.

## 10. Inference-context policy (documented decision)

Training/validation sequences are built strictly within their split. For **inference on
a period after training** (e.g. the test split), the wrapper prepends the final `L-1`
**scaled validation rows** persisted in the artifact as warm-up context. These rows are
strictly earlier than every predicted timestamp (milestone section 8 allows observations
<= T) and their labels are never used. Without this buffer the first L-1 evaluation rows
would be unpredictable; fabricating their outputs is not allowed.

## 11. Comparison with baseline

The temporal model is evaluated with the **same** target, horizon, dataset period,
feature version, label version, evaluation protocol, and cost/slippage assumptions as
the baseline. Predictive metrics come from the shared `classification_metrics`;
financial metrics come from the **existing backtest engine** (no new backtester).
The ablation (single-row baseline vs sequence input on identical rows) is recorded in
the experiment artifacts. No single-metric promotion: the temporal model is registered
as **CANDIDATE** and is not activated automatically.

## 12. Interpretability

Temporal model interpretability is **limited**. No attention visualisations or
fabricated feature attributions are produced. The baseline's coefficient/importance
table remains the interpretable reference.

## 13. Compute requirements

- CPU-only training is fully supported and is what the verification runs use.
- Optional single-GPU acceleration is possible through PyTorch's default device
  selection but is **not required** and never silently assumed.
- Tests use a tiny deterministic fixture and do not require a GPU.

## 14. Failure handling

Explicit failures (never silent substitution): insufficient sequence length, invalid
feature count/order, NaN/Inf inputs, missing/invalid labels, incompatible artifact,
checkpoint persistence failure. All raise typed errors with context.

## 15. Known limitations

- ~550 training sequences is small for a neural model; results are expected to be
  modest and are reported honestly.
- Deep-learning nondeterminism across hardware is documented; same seed + same
  machine reproduces materially equivalent results.
- Calibration of temporal probabilities is evaluated in the ensemble/calibration
  milestone (Post-MVP 07), not silently altered here.
- Research-only. No live trading, no automatic activation, no strategy changes.
