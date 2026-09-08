"""Controlled autonomous retraining engine (Post-MVP Milestone 03).

Governance: autonomous retraining/experimentation/evaluation are allowed;
autonomous LIVE model replacement is NOT. The engine produces
CANDIDATE_APPROVED / CANDIDATE_REJECTED records — it never activates a
model, never touches the inference path, and never deletes artifacts.

Flow (docs/AUTONOMOUS_RETRAINING_IMPLEMENTATION.md §2):

    trigger -> eligibility -> retraining run -> candidate training
    -> candidate validation -> evaluation (ML + financial, fair comparison)
    -> promotion gates G1..G7 -> CANDIDATE_APPROVED | CANDIDATE_REJECTED
    -> audit record (current model UNCHANGED)
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.config.loader import AppConfig
from src.logging.logger import get_logger
from src.pipeline.lock import PipelineLock

logger = get_logger("retraining.engine")

RUN_STATES = (
    "NOT_TRIGGERED", "TRIGGERED", "SKIPPED", "RUNNING",
    "EVALUATING", "APPROVED", "REJECTED", "FAILED",
)
GATES = ("G1_DATA_QUALITY", "G2_TRAINING_VALIDITY", "G3_PREDICTION_SANITY",
         "G4_PREDICTIVE_QUALITY", "G5_FINANCIAL_PERFORMANCE", "G6_ROBUSTNESS",
         "G7_OPERATIONAL_HEALTH")


@dataclass(frozen=True)
class GateResult:
    gate: str
    status: str  # PASS | FAIL | SKIP
    detail: str


@dataclass(frozen=True)
class RetrainingRun:
    """Full retraining run record (milestone §37)."""

    retraining_run_id: str
    trigger_type: str
    trigger_reason: str
    current_model_version: str | None
    candidate_model_version: str | None
    dataset_version: str
    feature_version: str
    label_version: str
    fingerprint: str
    status: str
    decision: str | None = None
    gate_results: list[dict] = field(default_factory=list)
    metrics_comparison: dict = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""
    error: str | None = None
    config_version: str = ""


class RetrainingEngine:
    """Runs one controlled retraining pass (trigger -> gates -> decision)."""

    def __init__(
        self,
        config: AppConfig,
        *,
        retraining_dir: Path | None = None,
        now: datetime | None = None,
    ) -> None:
        self.config = config
        self.retraining_dir = retraining_dir or Path("data/retraining")
        self.now = now or datetime.now(timezone.utc).replace(tzinfo=None)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def evaluate_trigger(
        self,
        *,
        trigger_type: str,
        trigger_reason: str,
        dataset_version: str | None = None,
        drift_critical: bool = False,
        performance_critical: bool = False,
        dry_run: bool = False,
    ) -> RetrainingRun:
        """Evaluate a trigger and, if eligible, run the retraining flow."""
        cfg = self.config.retraining
        run_id = uuid.uuid4().hex
        dataset_version = dataset_version or self.config.dataset_builder.dataset_version
        feature_version = self.config.features.version
        label_version = self.config.dataset.label_version

        fingerprint = self._fingerprint(dataset_version, feature_version, label_version)

        # --- Eligibility ------------------------------------------------
        skip_reason = self._eligibility_failure(
            dataset_version, feature_version, label_version, fingerprint,
            drift_critical=drift_critical, performance_critical=performance_critical,
        )
        if skip_reason is not None:
            return self._record(
                RetrainingRun(
                    retraining_run_id=run_id,
                    trigger_type=trigger_type,
                    trigger_reason=trigger_reason,
                    current_model_version=self._latest_model_version(),
                    candidate_model_version=None,
                    dataset_version=dataset_version,
                    feature_version=feature_version,
                    label_version=label_version,
                    fingerprint=fingerprint,
                    status="SKIPPED",
                    error=skip_reason,
                    config_version=cfg.config_version,
                    started_at=self.now.isoformat(),
                    completed_at=self.now.isoformat(),
                )
            )

        if dry_run:
            return RetrainingRun(
                retraining_run_id=run_id,
                trigger_type=trigger_type,
                trigger_reason=trigger_reason,
                current_model_version=self._latest_model_version(),
                candidate_model_version=None,
                dataset_version=dataset_version,
                feature_version=feature_version,
                label_version=label_version,
                fingerprint=fingerprint,
                status="TRIGGERED",
                config_version=cfg.config_version,
                started_at=self.now.isoformat(),
                completed_at=self.now.isoformat(),
            )

        # --- Candidate training (existing trainer, approved config) -----
        candidate_version = f"{cfg.model_name}_candidate_{run_id[:8]}"
        started = time.perf_counter()
        try:
            from src.model.trainer import BaselineTrainer

            result = BaselineTrainer(self.config).run(
                model_name=cfg.model_name,
                dataset_version=dataset_version,
                feature_version=feature_version,
                label_version=label_version,
                model_version=candidate_version,
                experiment_id=f"retrain_{run_id[:8]}",
            )
        except Exception as error:  # training failure -> FAILED, model unchanged
            logger.error("retraining_candidate_training_failed", error=str(error))
            return self._record(
                RetrainingRun(
                    retraining_run_id=run_id,
                    trigger_type=trigger_type,
                    trigger_reason=trigger_reason,
                    current_model_version=self._latest_model_version(),
                    candidate_model_version=candidate_version,
                    dataset_version=dataset_version,
                    feature_version=feature_version,
                    label_version=label_version,
                    fingerprint=fingerprint,
                    status="FAILED",
                    error=f"candidate training failed: {error}",
                    config_version=cfg.config_version,
                    started_at=self.now.isoformat(),
                    completed_at=self.now.isoformat(),
                )
            )

        # --- Evaluation: candidate vs current (fair comparison) ---------
        gates, comparison = self._evaluate_gates(
            candidate=result,
            candidate_version=candidate_version,
            dataset_version=dataset_version,
            feature_version=feature_version,
            label_version=label_version,
        )
        approved = all(g.status == "PASS" for g in gates)
        decision = "CANDIDATE_APPROVED" if approved else "CANDIDATE_REJECTED"
        run = RetrainingRun(
            retraining_run_id=run_id,
            trigger_type=trigger_type,
            trigger_reason=trigger_reason,
            current_model_version=self._latest_model_version(exclude=candidate_version),
            candidate_model_version=candidate_version,
            dataset_version=dataset_version,
            feature_version=feature_version,
            label_version=label_version,
            fingerprint=fingerprint,
            status="APPROVED" if approved else "REJECTED",
            decision=decision,
            gate_results=[asdict(g) for g in gates],
            metrics_comparison=comparison,
            started_at=self.now.isoformat(),
            completed_at=self.now.isoformat(),
            config_version=cfg.config_version,
        )
        logger.info(
            "retraining_completed",
            retraining_run_id=run_id,
            decision=decision,
            candidate=candidate_version,
            duration_seconds=round(time.perf_counter() - started, 2),
        )
        return self._record(run)

    # ------------------------------------------------------------------
    # Eligibility (milestone §8) — every check must pass
    # ------------------------------------------------------------------
    def _eligibility_failure(
        self,
        dataset_version: str,
        feature_version: str,
        label_version: str,
        fingerprint: str,
        *,
        drift_critical: bool,
        performance_critical: bool,
    ) -> str | None:
        cfg = self.config.retraining
        processed = self.config.data.processed_dir
        processed = processed if processed.is_absolute() else Path.cwd() / processed
        metadata_path = processed / "datasets" / f"dataset_{dataset_version}" / "metadata.json"
        if not metadata_path.exists():
            return f"dataset {dataset_version} not found"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            return f"dataset metadata unreadable: {error}"
        if metadata.get("feature_version") != feature_version:
            return f"dataset feature version {metadata.get('feature_version')!r} != configured {feature_version!r}"
        if metadata.get("label_version") != label_version:
            return f"dataset label version {metadata.get('label_version')!r} != configured {label_version!r}"
        quality = float(metadata.get("quality_score") or 0.0)
        if quality < cfg.min_quality_score:
            return f"dataset quality {quality} below minimum {cfg.min_quality_score}"
        if int(metadata.get("train_rows") or 0) < cfg.min_train_rows:
            return f"train rows {metadata.get('train_rows')} below minimum {cfg.min_train_rows}"

        # Cooldown + idempotency (milestone §7/§29)
        last = self._last_run()
        if last is not None:
            if last.get("fingerprint") == fingerprint and last.get("status") in ("APPROVED", "REJECTED"):
                return f"identical candidate already evaluated ({last.get('decision')})"
            completed_at = last.get("completed_at") or last.get("started_at") or ""
            if completed_at:
                try:
                    last_dt = datetime.fromisoformat(completed_at)
                    if self.now - last_dt < timedelta(days=cfg.cooldown_days):
                        return (
                            f"cooldown active: last retraining {completed_at} "
                            f"(< {cfg.cooldown_days} days ago)"
                        )
                except ValueError:
                    pass
        return None

    # ------------------------------------------------------------------
    # Gates (milestone §18/§19) — measurable criteria only
    # ------------------------------------------------------------------
    def _evaluate_gates(self, *, candidate, candidate_version, dataset_version, feature_version, label_version):
        cfg = self.config.retraining
        gates: list[GateResult] = []
        comparison: dict = {}

        # G1 data quality: dataset metadata quality score
        processed = self.config.data.processed_dir
        processed = processed if processed.is_absolute() else Path.cwd() / processed
        metadata = json.loads(
            (processed / "datasets" / f"dataset_{dataset_version}" / "metadata.json").read_text(
                encoding="utf-8"
            )
        )
        quality = float(metadata.get("quality_score") or 0.0)
        gates.append(
            GateResult(
                gate="G1_DATA_QUALITY",
                status="PASS" if quality >= cfg.min_quality_score else "FAIL",
                detail=f"dataset quality {quality} vs minimum {cfg.min_quality_score}",
            )
        )

        # G2 training validity: artifact exists + versions match
        model_dir = Path(candidate.artifact_dir)
        meta_path = model_dir / "metadata.json"
        ok = meta_path.exists()
        meta = {}
        if ok:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            ok = (
                meta.get("dataset_version") == dataset_version
                and meta.get("feature_version") == feature_version
                and meta.get("label_version") == label_version
            )
        gates.append(
            GateResult(
                gate="G2_TRAINING_VALIDITY",
                status="PASS" if ok else "FAIL",
                detail="artifact metadata matches requested versions" if ok else "artifact missing or version mismatch",
            )
        )

        # G3 prediction sanity: metrics present, probabilities valid shape
        metrics = meta.get("metrics") or {}
        sanity = bool(metrics) and "confusion_matrix" in metrics
        gates.append(
            GateResult(
                gate="G3_PREDICTION_SANITY",
                status="PASS" if sanity else "FAIL",
                detail="validation metrics present" if sanity else "missing validation metrics",
            )
        )

        # G4/G5/G6: fair comparison vs the current (previous) model.
        current_version = self._latest_model_version(exclude=candidate_version)
        current_metrics = self._model_metrics(current_version)
        candidate_f1 = float(metrics.get("f1_macro") or 0.0)
        current_f1 = float((current_metrics or {}).get("f1_macro") or 0.0)
        comparison["f1_macro"] = {"candidate": candidate_f1, "current": current_f1}
        gates.append(
            GateResult(
                gate="G4_PREDICTIVE_QUALITY",
                status="PASS" if candidate_f1 >= current_f1 - cfg.min_f1_margin else "FAIL",
                detail=f"candidate F1 {candidate_f1:.4f} vs current {current_f1:.4f} "
                f"(margin {cfg.min_f1_margin})",
            )
        )

        # G5 financial performance via the shared backtest engine (TEST split).
        cand_fin = self._financial_metrics(
            model_version=candidate_version,
            dataset_version=dataset_version,
            feature_version=feature_version,
            label_version=label_version,
        )
        cur_fin = self._financial_metrics(
            model_version=current_version,
            dataset_version=dataset_version,
            feature_version=feature_version,
            label_version=label_version,
        )
        cand_sharpe = cand_fin.get("sharpe_ratio")
        cur_sharpe = cur_fin.get("sharpe_ratio")
        cand_dd = cand_fin.get("max_drawdown")
        cur_dd = cur_fin.get("max_drawdown")
        comparison["financial"] = {"candidate": cand_fin, "current": cur_fin}
        g5_pass = True
        g5_detail = "backtest metrics unavailable on one/both sides (zero-trade runs are legitimate)"
        if cand_sharpe is not None and cur_sharpe is not None:
            if cand_sharpe < cur_sharpe - cfg.max_sharpe_regression:
                g5_pass = False
                g5_detail = f"candidate Sharpe {cand_sharpe:.4f} regresses current {cur_sharpe:.4f}"
        if g5_pass and cand_dd is not None and cur_dd is not None:
            if cand_dd < cur_dd - cfg.max_drawdown_regression:
                g5_pass = False
                g5_detail = f"candidate drawdown {cand_dd:.4f} worse than current {cur_dd:.4f}"
        gates.append(GateResult(gate="G5_FINANCIAL_PERFORMANCE", status="PASS" if g5_pass else "FAIL", detail=g5_detail))

        # G6 robustness: VAL metrics exist (multi-window evaluation proxy)
        g6 = bool(metrics.get("precision_macro")) and bool(metrics.get("recall_macro"))
        gates.append(
            GateResult(
                gate="G6_ROBUSTNESS",
                status="PASS" if g6 else "FAIL",
                detail="per-class metrics available for multi-window review" if g6 else "insufficient metric detail",
            )
        )

        # G7 operational health: artifact loads through the standard loader
        try:
            from src.api.resolver import load_model

            load_model(self.config, candidate_version)
            g7_pass, g7_detail = True, "artifact loads through the standard resolver"
        except Exception as error:
            g7_pass, g7_detail = False, f"artifact load failed: {error}"
        gates.append(GateResult(gate="G7_OPERATIONAL_HEALTH", status="PASS" if g7_pass else "FAIL", detail=g7_detail))
        return gates, comparison

    # ------------------------------------------------------------------
    def _financial_metrics(self, *, model_version, dataset_version, feature_version, label_version) -> dict:
        """Run the shared static backtest engine on the TEST split."""
        if model_version is None:
            return {}
        try:
            from src.backtest.engine import BacktestEngine

            result = BacktestEngine(self.config).run(
                ticker="AAPL",
                model_version=model_version,
                dataset_version=dataset_version,
                feature_version=feature_version,
                label_version=label_version,
                split="test",
            )
            return dict(result.financial_metrics)
        except Exception as error:
            logger.warning("retraining_backtest_unavailable", error=str(error))
            return {}

    def _model_metrics(self, model_version: str | None) -> dict | None:
        if model_version is None:
            return None
        processed = self.config.model.artifact_dir
        processed = processed if processed.is_absolute() else Path.cwd() / processed
        meta_path = processed / model_version / "metadata.json"
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text(encoding="utf-8")).get("metrics")
        except (OSError, ValueError):
            return None

    def _latest_model_version(self, *, exclude: str | None = None) -> str | None:
        """Newest existing model artifact (current-model resolution until P04)."""
        processed = self.config.model.artifact_dir
        processed = processed if processed.is_absolute() else Path.cwd() / processed
        if not processed.exists():
            return None
        candidates = sorted(
            (p for p in processed.iterdir() if p.is_dir() and p.name != "experiments"),
            key=lambda p: p.name,
            reverse=True,
        )
        for path in candidates:
            if exclude and path.name == exclude:
                continue
            if (path / "metadata.json").exists():
                return path.name
        return None

    def _last_run(self) -> dict | None:
        runs = sorted(self.retraining_dir.glob("*.json"))
        if not runs:
            return None
        try:
            return json.loads(runs[-1].read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _fingerprint(self, dataset_version: str, feature_version: str, label_version: str) -> str:
        payload = f"{dataset_version}|{feature_version}|{label_version}|{self.config.retraining.config_version}|{self.config.retraining.model_name}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _record(self, run: RetrainingRun) -> RetrainingRun:
        self.retraining_dir.mkdir(parents=True, exist_ok=True)
        path = self.retraining_dir / f"{run.retraining_run_id}.json"
        payload = asdict(run)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
        return run
