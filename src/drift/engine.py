"""Drift detection engine (P02) — monitoring only.

OBSERVE -> MEASURE -> COMPARE -> CLASSIFY -> RECORD -> ALERT.
Compares a REFERENCE window (trusted baseline) against a CURRENT window
(recent data) over features, labels, predictions, and performance; records
drift events with deduplication and a resolution lifecycle; never retrains,
replaces models, or changes thresholds.

Storage (file-based, ADR-0005): data/monitoring/{events.jsonl, runs/, summaries/}.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.config.loader import AppConfig
from src.drift.metrics import (
    FeatureDrift,
    fdr_correct,
    feature_drift,
    missingness_drift,
    performance_status,
    prediction_drift,
)
from src.logging.logger import get_logger

logger = get_logger("drift.engine")

CONFIG_VERSION = "drift-config-v0.1"
DEFAULT_REFERENCE_SIZE = 500
DEFAULT_CURRENT_SIZE = 120
DEFAULT_MIN_WINDOW = 100
DEFAULT_COOLDOWN_CHECKS = 12


@dataclass(frozen=True)
class DriftEvent:
    """Standardized drift-event record (milestone §20)."""

    event_id: str
    event_timestamp: str
    event_type: str  # DATA_DRIFT | FEATURE_DRIFT | LABEL_DRIFT | PREDICTION_DRIFT | PERFORMANCE_DRIFT | MISSINGNESS_DRIFT
    severity: str  # INFO | WARNING | CRITICAL
    metric: str
    observed_value: float | str | None
    baseline_value: float | str | None
    threshold: float | None
    reference_window: str
    current_window: str
    affected_features: list[str] = field(default_factory=list)
    model_version: str | None = None
    dataset_version: str | None = None
    status: str = "OPEN"  # OPEN | ACKNOWLEDGED | RESOLVED
    fingerprint: str = ""
    first_seen: str = ""
    last_seen: str = ""
    occurrence_count: int = 1


@dataclass(frozen=True)
class MonitoringRun:
    """One drift-check execution record (milestone §35)."""

    monitor_run_id: str
    started_at: str
    completed_at: str
    reference_window: str
    current_window: str
    model_version: str | None
    features_checked: int
    tests_run: int
    warnings: int
    critical_events: int
    status: str  # COMPLETED | FAILED | INSUFFICIENT_DATA
    config_version: str = CONFIG_VERSION
    error: str | None = None


@dataclass(frozen=True)
class DriftReport:
    """Aggregated result of one drift check."""

    run_id: str
    status: str
    reference_window: tuple[str, str]
    current_window: tuple[str, str]
    feature_drifts: tuple[FeatureDrift, ...]
    missingness: FeatureDrift | None
    prediction_severity: str | None
    performance_status: str | None
    health: str  # HEALTHY | DEGRADED | CRITICAL | UNKNOWN
    events: tuple[DriftEvent, ...]
    insufficient_data: bool


class DriftEngine:
    """Runs one drift check for an instrument against stored artifacts."""

    def __init__(
        self,
        config: AppConfig,
        *,
        monitoring_dir: Path | None = None,
        now: datetime | None = None,
        reference_size: int = DEFAULT_REFERENCE_SIZE,
        current_size: int = DEFAULT_CURRENT_SIZE,
        min_window: int = DEFAULT_MIN_WINDOW,
        cooldown_checks: int = DEFAULT_COOLDOWN_CHECKS,
    ) -> None:
        self.config = config
        self.monitoring_dir = monitoring_dir or Path("data/monitoring")
        self.now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        self.reference_size = reference_size
        self.current_size = current_size
        self.min_window = min_window
        self.cooldown_checks = cooldown_checks

    # ------------------------------------------------------------------
    def run_check(
        self,
        instrument: str,
        *,
        model_version: str | None = None,
        dataset_version: str | None = None,
        feature_version: str | None = None,
        label_version: str | None = None,
        reference_frame: pd.DataFrame | None = None,
        current_frame: pd.DataFrame | None = None,
        reference_predictions: np.ndarray | None = None,
        current_predictions: np.ndarray | None = None,
        baseline_accuracy: float | None = None,
        current_accuracy: float | None = None,
    ) -> DriftReport:
        """Run one drift check.

        Frames are optional feature DataFrames (test injection); when
        omitted, the engine loads the latest persisted feature artifacts
        for the instrument and splits them into reference/current windows.
        """
        from src.features import storage as feature_storage
        from src.features.registry import FEATURE_COLUMNS

        started = time.perf_counter()
        run_id = uuid.uuid4().hex
        events: list[DriftEvent] = []
        insufficient = False

        if current_frame is None or reference_frame is None:
            fversion = feature_version or self.config.features.version
            path = feature_storage.feature_file_path(
                self.config.data.processed_dir, fversion, instrument
            )
            if not path.exists():
                return self._failed_report(
                    run_id, f"no feature artifact for {instrument} ({fversion})"
                )
            frame = feature_storage.read_features(path)
            if len(frame) < self.min_window + 10:
                insufficient = True
            reference_frame = frame.iloc[: max(len(frame) - self.current_size, 1)]
            current_frame = frame.iloc[-self.current_size :]

        if reference_frame is None or current_frame is None:
            features = [c for c in FEATURE_COLUMNS if c in reference_frame.columns]
        else:
            # Injected frames (tests/CLI): use the numeric columns common to
            # both windows so custom feature sets are supported.
            common = [c for c in reference_frame.columns if c in current_frame.columns]
            features = [c for c in common if pd.api.types.is_numeric_dtype(reference_frame[c])]
        drifts = feature_drift(reference_frame, current_frame, features)

        # FDR correction across KS p-values (milestone §12).
        pvals = [d.ks_pvalue for d in drifts]
        corrected = fdr_correct(pvals)
        drifts = [
            (
                d
                if p is None or c is None or c >= 0.05 or d.severity == "INSUFFICIENT_DATA"
                else FeatureDrift(
                    feature=d.feature,
                    psi=d.psi,
                    ks_statistic=d.ks_statistic,
                    ks_pvalue=c,
                    ref_mean=d.ref_mean,
                    cur_mean=d.cur_mean,
                    ref_std=d.ref_std,
                    cur_std=d.cur_std,
                    ref_missing=d.ref_missing,
                    cur_missing=d.cur_missing,
                    severity="YELLOW" if d.severity == "GREEN" else d.severity,
                )
            )
            for d, p, c in zip(drifts, pvals, corrected)
        ]

        missingness = missingness_drift(reference_frame, current_frame, features)

        # --- Events: feature drift (YELLOW/RED only) -------------------
        for d in drifts:
            if d.severity in ("YELLOW", "RED"):
                events.append(
                    self._event(
                        event_type="FEATURE_DRIFT",
                        severity="CRITICAL" if d.severity == "RED" else "WARNING",
                        metric=f"psi:{d.feature}",
                        observed=d.psi,
                        baseline=0.0,
                        threshold=0.10 if d.severity == "YELLOW" else 0.25,
                        reference_window=f"n={len(reference_frame)}",
                        current_window=f"n={len(current_frame)}",
                        affected_features=[d.feature],
                        model_version=model_version,
                        dataset_version=dataset_version,
                    )
                )
        if missingness is not None and missingness.severity in ("YELLOW", "RED"):
            events.append(
                self._event(
                    event_type="MISSINGNESS_DRIFT",
                    severity="CRITICAL" if missingness.severity == "RED" else "WARNING",
                    metric="missing_rate_delta",
                    observed=missingness.cur_missing,
                    baseline=missingness.ref_missing,
                    threshold=0.02 if missingness.severity == "YELLOW" else 0.10,
                    reference_window=f"n={len(reference_frame)}",
                    current_window=f"n={len(current_frame)}",
                    affected_features=features,
                    model_version=model_version,
                    dataset_version=dataset_version,
                )
            )

        # --- Prediction drift ------------------------------------------
        pred_severity: str | None = None
        if reference_predictions is not None and current_predictions is not None:
            pred_severity = prediction_drift(reference_predictions, current_predictions)
            if pred_severity in ("YELLOW", "RED"):
                events.append(
                    self._event(
                        event_type="PREDICTION_DRIFT",
                        severity="CRITICAL" if pred_severity == "RED" else "WARNING",
                        metric="prediction_class_psi",
                        observed=pred_severity,
                        baseline="GREEN",
                        threshold=0.10,
                        reference_window=f"n={len(reference_predictions)}",
                        current_window=f"n={len(current_predictions)}",
                        affected_features=[],
                        model_version=model_version,
                        dataset_version=dataset_version,
                    )
                )

        # --- Performance monitoring -------------------------------------
        perf_status: str | None = None
        if baseline_accuracy is not None and current_accuracy is not None:
            perf_status = performance_status(
                baseline_accuracy, current_accuracy, len(current_frame)
            )
            if perf_status in ("WARNING", "CRITICAL"):
                events.append(
                    self._event(
                        event_type="PERFORMANCE_DRIFT",
                        severity="CRITICAL" if perf_status == "CRITICAL" else "WARNING",
                        metric="directional_accuracy_delta",
                        observed=current_accuracy,
                        baseline=baseline_accuracy,
                        threshold=0.05 if perf_status == "WARNING" else 0.10,
                        reference_window=f"n={len(reference_frame)}",
                        current_window=f"n={len(current_frame)}",
                        affected_features=[],
                        model_version=model_version,
                        dataset_version=dataset_version,
                    )
                )

        # --- Deduplicate + persist --------------------------------------
        deduped = self._deduplicate(events)
        self._persist_events(deduped)

        health = self._health(deduped, insufficient)
        report = DriftReport(
            run_id=run_id,
            status="INSUFFICIENT_DATA" if insufficient else "COMPLETED",
            reference_window=(str(reference_frame.index.min()), str(reference_frame.index.max())),
            current_window=(str(current_frame.index.min()), str(current_frame.index.max())),
            feature_drifts=tuple(drifts),
            missingness=missingness,
            prediction_severity=pred_severity,
            performance_status=perf_status,
            health=health,
            events=tuple(deduped),
            insufficient_data=insufficient,
        )
        self._persist_run(run_id, report, model_version, len(features), started)
        self._persist_summary(report, model_version, dataset_version)
        return report

    # ------------------------------------------------------------------
    def _event(
        self,
        *,
        event_type: str,
        severity: str,
        metric: str,
        observed,
        baseline,
        threshold,
        reference_window: str,
        current_window: str,
        affected_features=None,
        model_version=None,
        dataset_version=None,
    ) -> DriftEvent:
        ts = self.now.isoformat()
        fingerprint = f"{event_type}:{metric}:{severity}"
        return DriftEvent(
            event_id=uuid.uuid4().hex,
            event_timestamp=ts,
            event_type=event_type,
            severity=severity,
            metric=metric,
            observed_value=observed,
            baseline_value=baseline,
            threshold=threshold,
            reference_window=reference_window,
            current_window=current_window,
            affected_features=list(affected_features or []),
            model_version=model_version,
            dataset_version=dataset_version,
            fingerprint=fingerprint,
            first_seen=ts,
            last_seen=ts,
        )

    def _deduplicate(self, events: list[DriftEvent]) -> list[DriftEvent]:
        """Merge repeated fingerprints into occurrence counts (milestone §29)."""
        existing: dict[str, DriftEvent] = {}
        if (self.monitoring_dir / "events.jsonl").exists():
            for line in (
                (self.monitoring_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
            ):
                if not line.strip():
                    continue
                raw = json.loads(line)
                if raw.get("status") == "OPEN":
                    existing[raw["fingerprint"]] = DriftEvent(**raw)
        merged: list[DriftEvent] = []
        for event in events:
            prior = existing.get(event.fingerprint)
            if prior is not None:
                updated = DriftEvent(
                    **{
                        **asdict(prior),
                        "last_seen": event.event_timestamp,
                        "occurrence_count": prior.occurrence_count + 1,
                    }
                )
                merged.append(updated)
                existing.pop(event.fingerprint)
            else:
                merged.append(event)
        return merged

    def _persist_events(self, events: list[DriftEvent]) -> None:
        if not events:
            return
        self.monitoring_dir.mkdir(parents=True, exist_ok=True)
        path = self.monitoring_dir / "events.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(asdict(event), sort_keys=True) + "\n")
        for event in events:
            logger.info(
                "drift_event_recorded",
                event_type=event.event_type,
                severity=event.severity,
                metric=event.metric,
                occurrence_count=event.occurrence_count,
            )

    def _persist_run(self, run_id, report, model_version, features_checked, started) -> None:
        runs_dir = self.monitoring_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        record = MonitoringRun(
            monitor_run_id=run_id,
            started_at=self.now.isoformat(),
            completed_at=self.now.isoformat(),
            reference_window=f"{report.reference_window[0]}..{report.reference_window[1]}",
            current_window=f"{report.current_window[0]}..{report.current_window[1]}",
            model_version=model_version,
            features_checked=features_checked,
            tests_run=features_checked + 2,
            warnings=sum(1 for e in report.events if e.severity == "WARNING"),
            critical_events=sum(1 for e in report.events if e.severity == "CRITICAL"),
            status=report.status,
        )
        (runs_dir / f"{run_id}.json").write_text(
            json.dumps(asdict(record), indent=2, sort_keys=True), encoding="utf-8"
        )

    def _persist_summary(self, report, model_version, dataset_version) -> None:
        summaries = self.monitoring_dir / "summaries"
        summaries.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": self.now.isoformat(),
            "health": report.health,
            "status": report.status,
            "model_version": model_version,
            "dataset_version": dataset_version,
            "open_critical": sum(
                1 for e in report.events if e.severity == "CRITICAL" and e.status == "OPEN"
            ),
            "open_warning": sum(
                1 for e in report.events if e.severity == "WARNING" and e.status == "OPEN"
            ),
            "top_drifted_features": [
                {"feature": d.feature, "psi": d.psi, "severity": d.severity}
                for d in report.feature_drifts[:5]
            ],
        }
        (summaries / "latest.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )

    def _health(self, events: list[DriftEvent], insufficient: bool) -> str:
        if insufficient and not events:
            return "UNKNOWN"
        if any(e.severity == "CRITICAL" for e in events):
            return "CRITICAL"
        if any(e.severity == "WARNING" for e in events):
            return "DEGRADED"
        return "HEALTHY"

    def _failed_report(self, run_id: str, error: str) -> DriftReport:
        return DriftReport(
            run_id=run_id,
            status="FAILED",
            reference_window=("", ""),
            current_window=("", ""),
            feature_drifts=(),
            missingness=None,
            prediction_severity=None,
            performance_status=None,
            health="UNKNOWN",
            events=(),
            insufficient_data=False,
        )

    # ------------------------------------------------------------------
    def resolve_event(self, event_id: str) -> bool:
        """Manually resolve an open event (milestone §30)."""
        path = self.monitoring_dir / "events.jsonl"
        if not path.exists():
            return False
        lines = path.read_text(encoding="utf-8").splitlines()
        updated = []
        found = False
        for line in lines:
            if not line.strip():
                continue
            raw = json.loads(line)
            if raw.get("event_id") == event_id and raw.get("status") == "OPEN":
                raw["status"] = "RESOLVED"
                found = True
            updated.append(json.dumps(raw, sort_keys=True))
        if found:
            path.write_text("\n".join(updated) + "\n", encoding="utf-8")
        return found
