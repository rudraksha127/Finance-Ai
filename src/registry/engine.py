"""Model registry & safe promotion (Post-MVP Milestone 04).

Single source of truth for "What model is currently active?". The ACTIVE
model is explicitly registered — never inferred from file timestamps.

Lifecycle: TRAINED -> CANDIDATE -> VALIDATING -> APPROVED -> ACTIVE ->
ARCHIVED (plus REJECTED). Invalid transitions are rejected. At most one
model is ACTIVE. Activation is atomic: on any failure the previous ACTIVE
model remains ACTIVE. Every transition writes an append-only audit record.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.config.loader import AppConfig
from src.logging.logger import get_logger
from src.pipeline.lock import PipelineLock

logger = get_logger("registry.engine")

STATUSES = ("TRAINED", "CANDIDATE", "VALIDATING", "APPROVED", "ACTIVE", "REJECTED", "ARCHIVED")

# Explicit transition map; anything else is invalid (milestone §8).
TRANSITIONS: dict[str, tuple[str, ...]] = {
    "TRAINED": ("CANDIDATE",),
    "CANDIDATE": ("VALIDATING", "REJECTED"),
    "VALIDATING": ("APPROVED", "REJECTED"),
    "APPROVED": ("ACTIVE",),
    "ACTIVE": ("ARCHIVED",),
    "REJECTED": (),
    "ARCHIVED": (),
}


class RegistryError(Exception):
    """Registry failure with a safe, explicit message."""


class RegistryTransitionError(RegistryError):
    pass


@dataclass(frozen=True)
class ModelRecord:
    """Registry record for one model version (milestone §7)."""

    model_version: str
    model_type: str
    status: str
    artifact_dir: str
    artifact_checksum: str | None
    dataset_version: str
    feature_version: str
    label_version: str
    config_version: str
    experiment_id: str | None = None
    registered_at: str = ""
    approved_at: str | None = None
    activated_at: str | None = None
    updated_at: str = ""
    metrics: dict | None = None


@dataclass(frozen=True)
class AuditRecord:
    """Activation/rollback audit entry (milestone §22)."""

    audit_id: str
    action: str  # PROMOTE | ROLLBACK | ARCHIVE | REGISTER | APPROVE | REJECT
    model_version: str
    previous_active: str | None
    new_active: str | None
    reason: str
    actor: str
    timestamp: str
    success: bool


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


class ModelRegistry:
    """File-backed model registry with atomic promotion/rollback."""

    def __init__(self, config: AppConfig, *, registry_dir: Path | None = None) -> None:
        processed = config.model.artifact_dir
        processed = processed if processed.is_absolute() else Path.cwd() / processed
        self.registry_dir = registry_dir or (processed / "registry")
        self.records_path = self.registry_dir / "registry.json"
        self.audit_path = self.registry_dir / "audit.jsonl"
        self.locks_dir = self.registry_dir / "locks"
        self.config = config

    # ------------------------------------------------------------------
    # Core I/O
    # ------------------------------------------------------------------
    def _read_records(self) -> dict[str, ModelRecord]:
        if not self.records_path.exists():
            return {}
        raw = json.loads(self.records_path.read_text(encoding="utf-8"))
        return {name: ModelRecord(**record) for name, record in raw.items()}

    def _write_records(self, records: dict[str, ModelRecord]) -> None:
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        payload = {name: asdict(record) for name, record in records.items()}
        tmp = self.records_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.records_path)

    def _audit(self, record: AuditRecord) -> None:
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")

    # ------------------------------------------------------------------
    # Registration & lifecycle
    # ------------------------------------------------------------------
    def register_model(
        self,
        model_version: str,
        *,
        model_type: str,
        dataset_version: str,
        feature_version: str,
        label_version: str,
        config_version: str,
        experiment_id: str | None = None,
        metrics: dict | None = None,
        status: str = "TRAINED",
    ) -> ModelRecord:
        """Register an existing trained artifact (checksum computed here)."""
        records = self._read_records()
        if model_version in records:
            raise RegistryError(f"model {model_version!r} already registered")
        artifact_dir = self._artifact_dir(model_version)
        model_file = artifact_dir / "model.joblib"
        if not model_file.exists():
            raise RegistryError(f"artifact for {model_version!r} not found at {artifact_dir}")
        record = ModelRecord(
            model_version=model_version,
            model_type=model_type,
            status=status,
            artifact_dir=str(artifact_dir),
            artifact_checksum=self._checksum(model_file),
            dataset_version=dataset_version,
            feature_version=feature_version,
            label_version=label_version,
            config_version=config_version,
            experiment_id=experiment_id,
            registered_at=_now(),
            updated_at=_now(),
            metrics=metrics,
        )
        records[model_version] = record
        self._write_records(records)
        self._audit(
            AuditRecord(
                audit_id=uuid.uuid4().hex, action="REGISTER", model_version=model_version,
                previous_active=self._active_version(records), new_active=None,
                reason="registered", actor="registry", timestamp=_now(), success=True,
            )
        )
        logger.info("model_registered", model_version=model_version, status=status)
        return record

    def transition(self, model_version: str, to_status: str, *, reason: str = "") -> ModelRecord:
        """Apply one lifecycle transition (validated against the map)."""
        records = self._read_records()
        record = records.get(model_version)
        if record is None:
            raise RegistryError(f"model {model_version!r} not registered")
        if to_status not in TRANSITIONS.get(record.status, ()):
            raise RegistryTransitionError(
                f"invalid transition {record.status} -> {to_status} for {model_version!r}"
            )
        updated = ModelRecord(
            **{
                **asdict(record),
                "status": to_status,
                "updated_at": _now(),
                "approved_at": _now() if to_status == "APPROVED" else record.approved_at,
                "activated_at": _now() if to_status == "ACTIVE" else record.activated_at,
            }
        )
        records[model_version] = updated
        self._write_records(records)
        self._audit(
            AuditRecord(
                audit_id=uuid.uuid4().hex,
                action=to_status,
                model_version=model_version,
                previous_active=self._active_version(records) if to_status != "ACTIVE" else None,
                new_active=model_version if to_status == "ACTIVE" else None,
                reason=reason or f"transition to {to_status}",
                actor="registry",
                timestamp=_now(),
                success=True,
            )
        )
        logger.info("model_transition", model_version=model_version, to_status=to_status)
        return updated

    def approve_model(self, model_version: str, *, reason: str = "approved") -> ModelRecord:
        """Walk the legal transition path from the current status to APPROVED.

        Handles TRAINED -> CANDIDATE -> VALIDATING -> APPROVED and any subset
        already applied (e.g. a model already at VALIDATING). Raises
        RegistryTransitionError when the path to APPROVED is illegal (e.g.
        the model is REJECTED or ARCHIVED).
        """
        record = self.get_model(model_version)
        visited = set()
        while record.status != "APPROVED":
            if record.status in visited:
                raise RegistryTransitionError(
                    f"cannot reach APPROVED from {record.status!r} for {model_version!r}"
                )
            visited.add(record.status)
            options = TRANSITIONS.get(record.status, ())
            if "APPROVED" in options:
                record = self.transition(model_version, "APPROVED", reason=reason)
            elif "VALIDATING" in options:
                record = self.transition(model_version, "VALIDATING", reason=reason)
            elif "CANDIDATE" in options:
                record = self.transition(model_version, "CANDIDATE", reason=reason)
            else:
                raise RegistryTransitionError(
                    f"cannot reach APPROVED from {record.status!r} for {model_version!r}"
                )
        return record

    # ------------------------------------------------------------------
    # Promotion & rollback (milestone §16/§20)
    # ------------------------------------------------------------------
    def promote_model(self, model_version: str, *, dry_run: bool = False, reason: str = "") -> dict:
        """Promote an APPROVED candidate to ACTIVE (atomic; previous archived)."""
        lock = PipelineLock(self.locks_dir / "promotion.lock")
        if not lock.acquire():
            raise RegistryError("another promotion is in progress")
        try:
            return self._promote_locked(model_version, dry_run=dry_run, reason=reason)
        finally:
            lock.release()

    def _promote_locked(self, model_version: str, *, dry_run: bool, reason: str) -> dict:
        records = self._read_records()
        record = records.get(model_version)
        if record is None:
            raise RegistryError(f"candidate {model_version!r} not registered")
        previous_active = self._active_version(records)
        plan = {
            "candidate": model_version,
            "candidate_status": record.status,
            "previous_active": previous_active,
            "integrity": self._integrity(record),
            "compatible": self._compatible(record),
        }
        if dry_run:
            plan["would_activate"] = (
                record.status == "APPROVED" and plan["integrity"] and plan["compatible"]
            )
            return plan

        # Required checks (milestone §14): every check must pass.
        if record.status != "APPROVED":
            raise RegistryError(
                f"candidate {model_version!r} status is {record.status}, expected APPROVED"
            )
        if not plan["integrity"]:
            raise RegistryError(f"artifact integrity check failed for {model_version!r}")
        if not plan["compatible"]:
            raise RegistryError(
                f"candidate {model_version!r} is incompatible with the inference contract "
                f"(feature {record.feature_version} vs configured "
                f"{self.config.features.version}, label {record.label_version} vs "
                f"{self.config.dataset.label_version})"
            )

        # Atomic activation: mutate all records, write once.
        updated_records = dict(records)
        updated_records[model_version] = ModelRecord(
            **{**asdict(record), "status": "ACTIVE", "activated_at": _now(), "updated_at": _now()}
        )
        if previous_active is not None:
            prev = records[previous_active]
            updated_records[previous_active] = ModelRecord(
                **{**asdict(prev), "status": "ARCHIVED", "updated_at": _now()}
            )
        self._write_records(updated_records)
        self._audit(
            AuditRecord(
                audit_id=uuid.uuid4().hex, action="PROMOTE", model_version=model_version,
                previous_active=previous_active, new_active=model_version,
                reason=reason or "promoted to ACTIVE", actor="registry",
                timestamp=_now(), success=True,
            )
        )
        logger.info(
            "model_promoted", candidate=model_version, previous_active=previous_active
        )
        plan["activated"] = True
        return plan

    def rollback_model(self, target_version: str, *, dry_run: bool = False, reason: str = "") -> dict:
        """Roll back to a previously active model (integrity-checked)."""
        lock = PipelineLock(self.locks_dir / "promotion.lock")
        if not lock.acquire():
            raise RegistryError("another promotion is in progress")
        try:
            records = self._read_records()
            target = records.get(target_version)
            if target is None:
                raise RegistryError(f"rollback target {target_version!r} not registered")
            if target.status not in ("ARCHIVED", "ACTIVE"):
                raise RegistryError(
                    f"rollback target {target_version!r} has status {target.status}; "
                    "only ARCHIVED/ACTIVE models can be restored"
                )
            current_active = self._active_version(records)
            plan = {
                "target": target_version,
                "current_active": current_active,
                "integrity": self._integrity(target),
            }
            if dry_run:
                plan["would_activate"] = bool(plan["integrity"])
                return plan
            if not plan["integrity"]:
                raise RegistryError(
                    f"rollback target {target_version!r} failed integrity check; "
                    "refusing to activate an unverified artifact"
                )
            updated_records = dict(records)
            updated_records[target_version] = ModelRecord(
                **{**asdict(target), "status": "ACTIVE", "activated_at": _now(), "updated_at": _now()}
            )
            if current_active is not None and current_active != target_version:
                prev = records[current_active]
                updated_records[current_active] = ModelRecord(
                    **{**asdict(prev), "status": "ARCHIVED", "updated_at": _now()}
                )
            self._write_records(updated_records)
            self._audit(
                AuditRecord(
                    audit_id=uuid.uuid4().hex, action="ROLLBACK", model_version=target_version,
                    previous_active=current_active, new_active=target_version,
                    reason=reason or "rollback", actor="registry",
                    timestamp=_now(), success=True,
                )
            )
            logger.info("model_rollback", target=target_version, previous_active=current_active)
            plan["activated"] = True
            return plan
        finally:
            lock.release()

    # ------------------------------------------------------------------
    # Resolution (milestone §29/§30)
    # ------------------------------------------------------------------
    def get_active_model(self) -> ModelRecord:
        active = self._active_version(self._read_records())
        if active is None:
            raise RegistryError("no ACTIVE model registered")
        return self._read_records()[active]

    def get_model(self, model_version: str) -> ModelRecord:
        records = self._read_records()
        record = records.get(model_version)
        if record is None:
            raise RegistryError(f"model {model_version!r} not registered")
        return record

    def list_models(self) -> list[ModelRecord]:
        return sorted(self._read_records().values(), key=lambda r: r.model_version)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _active_version(self, records: dict[str, ModelRecord]) -> str | None:
        actives = [name for name, r in records.items() if r.status == "ACTIVE"]
        if len(actives) > 1:
            raise RegistryError(
                f"registry invariant violated: multiple ACTIVE models {actives}"
            )
        return actives[0] if actives else None

    def _artifact_dir(self, model_version: str) -> Path:
        processed = self.config.model.artifact_dir
        processed = processed if processed.is_absolute() else Path.cwd() / processed
        return processed / model_version

    def _checksum(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _integrity(self, record: ModelRecord) -> bool:
        """Artifact exists, loads, and checksum matches the record."""
        model_file = Path(record.artifact_dir) / "model.joblib"
        if not model_file.exists():
            return False
        if record.artifact_checksum and self._checksum(model_file) != record.artifact_checksum:
            return False
        try:
            import joblib

            joblib.load(model_file)
            return True
        except Exception as error:
            logger.warning("registry_artifact_load_failed", error=str(error))
            return False

    def _compatible(self, record: ModelRecord) -> bool:
        """Feature/label versions must match the configured inference contract."""
        return (
            record.feature_version == self.config.features.version
            and record.label_version == self.config.dataset.label_version
        )