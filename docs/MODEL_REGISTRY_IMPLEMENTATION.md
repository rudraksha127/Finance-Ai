# MODEL REGISTRY IMPLEMENTATION — Finance AI

> **Post-MVP Milestone 04 — Model Registry & Safe Model Promotion**
> **Date:** 2026-09-08 · **Status:** Implemented
> Companion to `docs/AUTONOMOUS_RETRAINING_IMPLEMENTATION.md`. The registry
> is the single source of truth for "What model is currently active?".

---

## 1. Scope

Implemented: model registry records with full version identity, lifecycle
state machine (`TRAINED → CANDIDATE → VALIDATING → APPROVED → ACTIVE →
ARCHIVED`, plus `REJECTED`), invalid-transition rejection, active-model
uniqueness (at most one ACTIVE), artifact integrity checks, compatibility
checks (feature/label/strategy), explicit promotion + rollback + archival
workflows, activation audit records, `get_active_model()` /
`get_model(version)` resolution, concurrency protection, and CLI commands
(`promote-model`, `rollback-model`, both with dry-run).

NOT implemented: automatic live deployment (disabled by default), broker
integration, live trading, strategy modification.

## 2. Safety Principles

- The ACTIVE model is **explicitly registered** — never "newest file",
  never "latest timestamp".
- `REJECTED → ACTIVE` is impossible (state machine enforces).
- Activation is atomic: if any check fails or the write fails, the
  previous ACTIVE model remains ACTIVE.
- Rollback verifies the target artifact's integrity before activation.
- Every activation/rollback/archival writes an audit record answering
  "Why is this model active?".

## 3. Storage (file-based, ADR-0005)

```
data/processed/models/registry/
├── registry.json          # model records {model_version: ModelRecord}
├── audit.jsonl            # append-only activation/rollback records
└── locks/promotion.lock   # concurrency protection
```

Model records reference: model_version, model_type, status,
artifact_dir, artifact checksum (SHA-256 of model.joblib), dataset/
feature/label versions, config version, experiment_id, timestamps
(registered/approved/activated), and metrics snapshot.

## 4. Lifecycle & Transitions

```
TRAINED → CANDIDATE → VALIDATING → APPROVED → ACTIVE → ARCHIVED
                    ↘ REJECTED
```

Valid transitions are an explicit map; anything else raises
`RegistryTransitionError`. At most one model may be ACTIVE per registry;
activating B archives the previously active A (audit records both).

## 5. Promotion Workflow

`promote(candidate)` performs, in order:
1. candidate exists and status == APPROVED (auto-advances
   CANDIDATE→VALIDATING→APPROVED via `approve_model` when appropriate)
2. artifact integrity (exists, loads, checksum matches record)
3. compatibility (feature/label versions vs configured inference contract)
4. rollback availability (previous ACTIVE model recorded)
5. atomic activation: new record ACTIVE, previous → ARCHIVED, audit row
   appended, lock held for the whole transaction

Failure at any step → activation aborted, previous ACTIVE unchanged.

## 6. Inference Integration

`get_active_model()` is the single authoritative resolver. The inference
API continues to resolve its configured default; after P04, operators
promote a candidate and the API's configured `api.default_model` (or the
registry query) picks up the ACTIVE model on restart/reload. Automatic
hot-swap is deliberately NOT implemented (MVP favors correctness).

## 7. CLI

```bash
# Inspect
python -m scripts.run_registry --list
python -m scripts.run_registry --show <model_version>

# Promote (dry-run shows the planned transition without changing state)
python -m scripts.run_registry --promote <candidate_version> --dry-run
python -m scripts.run_registry --promote <candidate_version>

# Rollback to a previously active model
python -m scripts.run_registry --rollback <target_version>
```

## 8. Testing

- Registry: registration, duplicate rejection, status transitions,
  active-model uniqueness.
- Promotion: valid candidate, invalid candidate, incompatible feature
  version, corrupted artifact.
- Activation: atomicity, concurrency (lock), failure recovery.
- Rollback: valid, missing artifact, incompatible target.
- Resolver: `get_active_model()`, `get_model(version)`.
- Audit: activation, rollback, archival records.
- **Critical safety test:** a candidate that fails evaluation/gates/
  integrity can never become ACTIVE; activation failure preserves the
  previous ACTIVE model.
- **Regression test:** promote B → active B; rollback A → active A;
  `get_model(B)` still resolves (history preserved).

## 9. Limitations

- Single deployment context (one ACTIVE model) — multi-context support is
  future work.
- Activation takes effect on API restart/reload; no zero-downtime hot swap.
- Checksums cover model.joblib; metadata.json is validated by content
  (versions) rather than hash.
