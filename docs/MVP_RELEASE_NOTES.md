# MVP RELEASE NOTES — Finance AI

> **MVP Version:** 0.1.0 · **Date:** 2026-09-08 · **Status: GO (research-only)**
> Derived from `docs/MVP_INTEGRATION_QA_REPORT.md` (authoritative QA source).

---

## Supported Capabilities (all verified 2026-09-08)

| Capability | Entry point |
|------------|-------------|
| Historical OHLCV ingestion (Yahoo Finance, `1d`/`1wk`/`1mo`, idempotent, journaled) | `python -m scripts.run_ingest` |
| Cleaning & quality (validation rules, corporate actions, 0–100 score, audit trail) | `src.cleaning.pipeline.CleaningPipeline` |
| Feature engineering (52 approved features, versioned Parquet, leakage-tested) | `python -m scripts.run_features` |
| Label generation (UP/DOWN/HOLD, 5-day horizon, ±1% fixed thresholds) | `python -m scripts.run_labels` |
| Dataset builder (chronological splits, DVAL checks, immutable versioned snapshots) | `python -m scripts.run_dataset` |
| Baseline training (logistic regression + random forest, experiment artifacts) | `python -m scripts.run_model` |
| Backtesting (static + walk-forward, costs/slippage, benchmarks, scenario study) | `python -m scripts.run_backtest` |
| Inference API (research-only FastAPI: `/predict`, `/health`, `/ready`, `/model/info`, `/version`) | `python -m scripts.run_api` |
| Research dashboard (React 19 + Vite; 8 pages over read endpoints) | `cd dashboard && npm run dev` |

## Exact Verified Versions (research run 2026-09-08)

| Artifact | Version |
|----------|---------|
| Feature set | `v0.3` (hash `c44261d3…`) |
| Label set | `v0.3` (hash `eeaba92a…`) |
| Dataset | `v0.3` (hash `5e07c142…`, 799 rows: 559/119/121) |
| Models | `logistic_regression_v0.3`, `random_forest_v0.3` |
| Strategy / backtest | `stg_v0.1` / `v0.1` |
| API contract | `v1` |
| Runtime | Python 3.11.15 · Node 24.18.0 |

## Known Limitations

- **Research-only.** No order/execution code exists; `mode: live` refuses to boot.
- Yahoo Finance is an unofficial endpoint; availability/format may change.
- Daily bars only; single-process, file-based storage (ADR-0005).
- Baseline models show honest weak predictive performance
  (ROC-AUC ≈ 0.48–0.54 on the real TEST split) — this is the approved
  baseline, not a production signal.
- Walk-forward on real data produced −7.5% net (17 trades) — reported as-is.
- Repository has no commits yet; reproducibility rests on artifact
  checksums + config snapshots.

## Reproducibility Instructions

```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
# then run the verified workflow (docs/MVP_INTEGRATION_QA_REPORT.md §18):
python -m scripts.run_ingest --ticker AAPL --start 2026-08-24 --end 2026-09-04
python -m scripts.run_features --ticker AAPL --feature-version v0.3
python -m scripts.run_labels --ticker AAPL --label-version v0.3
python -m scripts.run_dataset --ticker AAPL --feature-version v0.3 --label-version v0.3 --output-version v0.3
python -m scripts.run_model --model logistic_regression --dataset-version v0.3 --feature-version v0.3 --label-version v0.3 --model-version logistic_regression_v0.3
python -m scripts.run_backtest --ticker AAPL --dataset-version v0.3 --feature-version v0.3 --label-version v0.3 --model-version logistic_regression_v0.3 --split test
python -m scripts.run_api
```

Same inputs → byte-stable dataset (verified: identical `version_hash` on
rebuild); deterministic predictions and backtests (fixed seed 42,
conflict-protected artifacts).

## Research-Only Warning

All outputs (predictions, signals, risk scores, backtests) are research
artifacts for pipeline validation. They are not investment advice, not
production predictions, and must not be used for live trading.

## Post-MVP Roadmap

1. **P01** Autonomous data ingestion & incremental dataset growth — COMPLETE
2. **P02** Data & model drift detection engine — COMPLETE
3. **P03** Autonomous retraining & candidate evaluation — COMPLETE
4. **P04** Model registry & safe promotion — COMPLETE
5. **P05** Observability & operations center — COMPLETE
6. **P06** Temporal intelligence model (LSTM) — COMPLETE (registered CANDIDATE)
7. **P07** Model ensemble & probability calibration — COMPLETE (ensemble CANDIDATE, not promoted)
8. **P08** Multimodal finance intelligence (fundamentals + events, point-in-time) — COMPLETE (fixture-only external data; experiments await a licensed source)
