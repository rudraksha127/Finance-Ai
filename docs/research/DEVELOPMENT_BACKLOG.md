# MPFM Development Backlog & Dependency Plan

**Priority sequence confirmed:** D0 → D1 → D2 → D3 → D4  
**Last consolidated:** 2026-11-17

This document preserves the agreed order and parallel tracks. The recovered project notes list the subsystem work but do not preserve a reliable one-to-one assignment of every subsystem to D0, D1, D2, D3 or D4. Therefore, this page does not fabricate exact task-to-code mapping. Update the D-code allocation when the original detailed backlog is available.

## 1. Execution order

| Priority | Rule | Status |
|---|---|---|
| D0 | Execute first | Ordered; detailed acceptance criteria to be linked |
| D1 | Execute after D0 foundations are accepted | Ordered |
| D2 | Execute after D1 dependencies are satisfied | Ordered |
| D3 | Execute after D2 dependencies are satisfied | Ordered |
| D4 | Execute after D3; complete integrated validation | Ordered |

Do not parallelize dependent implementation in a way that bypasses the agreed D0 → D4 sequence.

## 2. Identified development workstreams

The complete subsystem inventory to allocate across the D0–D4 packages is:

1. Engineering foundation and shared contracts.
2. Security master and instrument identity.
3. Corporate-action engine.
4. Point-in-time fundamental intelligence.
5. Financial feature engine.
6. Baseline prediction engine.
7. Point-in-time Financial State Encoder.
8. Philosophy ontology and philosophy intelligence.
9. Mandate encoder/intelligence.
10. Risk and decision engine.
11. Integrated MPFM experiments and end-to-end evaluation.

These workstreams are the recovered scope. Their detailed task cards, acceptance tests and D0–D4 mapping must be maintained in the implementation tracker rather than inferred from the list order.

## 3. Parallel work allowed

The following tracks can proceed while the dependency-ordered development work advances:

- Philosophy ontology research and formalization.
- Data licensing, historical rights and provider due diligence.
- Baseline-model research and experimental design.
- Candidate B novelty and prior-art review.
- Patent/FTO review with an external legal specialist.
- Security, privacy, governance and data-retention requirements.

Parallel research must produce artifacts that can be integrated into the ordered development sequence. It must not be mislabeled as implemented engineering.

## 4. Multimodal sequencing constraint

Multimodal learning is not the first implementation priority. First make the point-in-time financial foundation reliable: security identity, corporate actions, timestamps, historical prices, data quality, causal financial features and baseline evaluation.

Fundamentals/news integrations can be prepared behind provider interfaces, but real experiments remain blocked until licensed historical sources and availability timestamps are available. Sentiment and embeddings remain deferred until the base point-in-time system is trustworthy.

## 5. External dependencies / blockers

| Dependency | Blocks | Required evidence |
|---|---|---|
| Historical market-data rights | Real-market model training and broad backtesting | Written permitted-use, retention and training rights |
| Real market-data ingestion | Market-wide validation and streaming experiments | Provider acceptance test, source timestamps, coverage and gap checks |
| Fundamentals/news licensing | Multimodal A–D experiments | Licensed historical archive with publication/availability timestamps |
| Exchange redistribution rights | User-facing data display and downstream sharing | Contract/entitlement approval for the exact use |
| Institutional approval | Work requiring institutional permission | Written approval and scope |
| Patent/FTO legal review | Any patentability/FTO conclusion | External specialist review |

## 6. Engineering acceptance gates

Each workstream should define:

- Input/output contracts and schema versions.
- Data lineage and availability-time semantics.
- Failure and retry behaviour.
- Idempotency and immutable audit requirements.
- Leakage and temporal-boundary tests.
- Unit, integration and failure-injection tests.
- Reproducible acceptance experiment.
- Operational observability and rollback.
- Documentation and implementation-status update.

No item is complete solely because its interface or UI exists.

## 7. Immediate order of operations

1. Continue with D0, then D1, D2, D3 and D4 without changing the agreed sequence.
2. Keep licensing, ontology and baseline research running in parallel.
3. Close the data-rights dependency before real-market experiments that require those sources.
4. Do not move to multimodal model training until the point-in-time financial foundation passes acceptance.
5. At D4, run integrated MPFM experiments under the controlled protocol in [MPFM Research Master](MPFM_RESEARCH_MASTER.md) and [Prediction Model Research](PREDICTION_MODEL_RESEARCH.md).


## 8. Modular architecture and engineering quality gates

The modular system architecture is a cross-cutting design constraint for every D0–D4 workstream. It does not change the confirmed dependency order or infer a missing task-to-D-code mapping.

Before a D0–D4 module is considered accepted, it must have:

- A bounded-context owner, responsibility and non-goals.
- Versioned input/output contracts and dependency/import boundaries.
- Data ownership, timestamp/availability semantics and lineage.
- Explicit algorithms/data structures and a complexity/performance rationale where workload-sensitive.
- Failure, timeout, retry, idempotency and recovery behaviour.
- Security, permissions and data-rights classification.
- Unit, property, contract, integration and relevant fault/performance tests.
- Observability, audit trail and measurable acceptance criteria.
- ADR for material architecture or dependency changes.

Reference blueprint: [MPFM Modular System Architecture & Engineering Blueprint](MPFM_MODULAR_SYSTEM_ARCHITECTURE_AND_ENGINEERING_BLUEPRINT.md).

Keep the initial architecture modular and independently testable; do not split modules into microservices or introduce databases, brokers, compiled hot paths or cloud services without a specific workload, measured need, migration plan and ADR. Existing MVP decisions remain in force until explicitly superseded.
