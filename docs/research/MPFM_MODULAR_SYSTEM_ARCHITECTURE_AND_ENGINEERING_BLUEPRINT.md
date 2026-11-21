# MPFM Production-Oriented Modular System Architecture & Engineering Blueprint

**Architecture research date:** 2026-11-21  
**Repository:** `rudraksha127/Finance-Ai`  
**Product:** Finance AI  
**Research/model platform:** MPFM  
**Architecture status:** Proposed target architecture; not yet implemented or production-validated  
**Existing implementation priority:** D0 → D1 → D2 → D3 → D4

> This blueprint explains how to use the model research, open-source reviews and autonomous-agent research when designing and implementing the real system. It preserves the current MVP architecture and its accepted ADRs. Target-state decisions require explicit ADRs, incremental implementation and acceptance tests.

---

## 1. Mission and engineering objective

Finance AI / MPFM must be engineered as a **modular, testable, observable, fault-tolerant financial intelligence platform**. The goal is not merely to produce strong model scores or a familiar trading interface. The system must continue to behave correctly when feeds are delayed, events are duplicated or out of order, a worker crashes, a provider rate-limits requests, a model degrades, a database is unavailable or an external dependency changes its contract.

The system has two equally important quality objectives:

### A. Intelligence quality
- Predictive accuracy and class-wise precision/recall/F1 where classification is suitable.
- Regression, ranking, probabilistic and volatility quality where those are the correct targets.
- Calibration, uncertainty and principled abstention.
- Generalisation across instruments, regimes and time periods.
- Incremental improvement over strong, reproducible baselines.
- Robustness after costs and realistic execution assumptions where an economic claim is made.

### B. System quality
- Correctness and data integrity.
- Reliability and graceful failure.
- Predictable latency and throughput.
- Security, privacy and data-rights enforcement.
- Maintainability and testability.
- Recoverability and observability.
- Reproducibility and controlled model promotion.
- Cost efficiency and ability to evolve without rewrites.

A high F1 score is not sufficient if the model sees leaked data, an old feature schema or a stale quote. A fast model is not useful if the feed handler loses events. A strong research candidate is not a production model until model, data, risk and operational gates pass.

---

## 2. Existing repository facts and design constraints

The following are source-derived from the current repository documentation reviewed for this blueprint.

### 2.1 Existing architecture and standards

The repository already documents:
- Python-first backend engineering, with Python 3.10+ in ADR-0002 and Python 3.11.15 in the September 2026 MVP QA environment.
- Typed public interfaces, single responsibility, module boundaries and a no-circular-import rule.
- A layered data → processing → feature → dataset → model → evaluation → API → UI architecture.
- Abstract interfaces / Protocol types for decoupling.
- Chronological time-series splits and zero-tolerance future-leakage rules.
- Deterministic transformations and reproducible seeds/configurations.
- Immutable raw data, source lineage, quality validation and versioned artifacts.
- YAML configuration, structured logging with structlog and environment-variable secrets.
- Minimum test-coverage and full-suite-before-merge requirements.
- PR-based Git change management and architecture decision records.

Sources: `docs/ENGINEERING_CONSTITUTION.md`, `docs/ARCHITECTURE_PRINCIPLES.md`, `docs/SYSTEM_ARCHITECTURE.md`, `docs/DECISIONS.md`.

### 2.2 Accepted MVP decisions that must not be silently broken

| ADR | Current decision | Target-state consequence |
|---|---|---|
| ADR-0002 | Python is the primary language for all MVP components | Keep Python as the default. Any Rust/C++ hot path needs profiling evidence and a superseding ADR. |
| ADR-0005 | File-based CSV/Parquet storage for MVP; no database | Preserve the working MVP. Introduce a transactional DB only under a measured concurrency/consistency requirement and a new ADR. |
| ADR-0007 | No cloud/external dependencies in MVP | Keep MVP local and reproducible. Add cloud/provider dependencies only in a separately approved target stage. |
| ADR-0004 | Chronological splits only | Remains mandatory for time-series model evaluation. |
| ADR-0006 | structlog structured logging | Preserve consistent structured logs; add traces/metrics as cross-cutting instrumentation. |
| ADR-0020 | Prediction, decision and execution are separate concerns | Preserve this boundary. Model outputs must never be direct broker commands. |

The existing `docs/SYSTEM_ARCHITECTURE.md` describes the Finance AI MVP; it is not a complete target-state blueprint for the expanded live-data, multi-market and agentic platform. This document adds a target-state design without rewriting historical MVP evidence or claiming that proposed modules exist.

### 2.3 Existing capabilities to preserve

- Historical ingestion and immutable raw storage.
- Cleaning and quality gates.
- Corporate-action adjustment support.
- Feature registry and 52 approved MVP features.
- Labels, versioned datasets and chronological splits.
- Baseline training, walk-forward backtesting and metrics.
- Model registry, candidate promotion/rollback and audit.
- Drift monitoring, retraining controls and operations health.
- Point-in-time multimodal data contracts and availability-time joins.
- Research API and React dashboard.

The previous AAPL experiments were weak and some candidate models were not promoted. These results remain evidence, not defects to hide. A new architecture cannot turn an unproven model into a reliable signal.

---

## 3. Architecture decision: modular monolith first, selective process separation

### 3.1 Recommended architecture style

Begin with a **modular monolith** organised around explicit domain boundaries, dependency rules and ports/adapters. Deploy separate processes only where isolation, performance, scaling, operational risk or different compute requirements justify them.

This avoids two opposite failures:
- A big ball of mud with unrestricted cross-module imports and shared mutable state.
- Premature microservices that require distributed tracing, network retries, service discovery, deployment automation, data consistency and operational ownership before the domain boundaries are understood.

Microservices are a possible later deployment topology, not the initial code-organisation strategy. A service should become independently deployable only when it has a clear bounded context, stable contract, independent scaling or isolation requirement, separate operational ownership and a measured reason to pay the distributed-systems cost.

Reference: Martin Fowler's monolith-first discussion and Microsoft's bounded-context definition for microservices:
- https://martinfowler.com/bliki/MonolithFirst.html
- https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/microservices

### 3.2 Architectural patterns

Use selectively:
- **Domain-Driven Design (DDD):** bounded contexts and explicit domain vocabulary.
- **Hexagonal / Ports and Adapters:** domain and application logic do not depend on vendor SDKs, databases or web frameworks.
- **Layered architecture:** domain → application → infrastructure/interface.
- **Event-driven architecture:** asynchronous propagation of market, data, research and operations events.
- **CQRS where justified:** command-side state changes and query-side dashboard/analytics views may have different models; do not split every CRUD endpoint into CQRS.
- **Transactional outbox:** when a DB transaction must reliably publish an event.
- **Saga/workflow orchestration:** for multi-step processes spanning independently persisted systems.
- **State machines:** feed connection, model lifecycle, task lifecycle and eventual order lifecycle.
- **Bulkhead, timeout, retry with jitter, circuit breaker and backpressure:** isolate failures and prevent cascades.
- **Strangler migration:** replace or extract a module gradually while the old interface remains stable.

Do not adopt Event Sourcing, CQRS, microservices, Kubernetes or a message broker as universal requirements. Each must solve a demonstrated problem.

References:
- Event-driven architecture: https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/event-driven
- AWS patterns catalogue: https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/
- Transactional outbox: https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html
- Retry/backoff: https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/retry-backoff.html
- Circuit breaker: https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/circuit-breaker.html

---

## 4. System context and planes

Keep these planes distinct. They interact through versioned contracts and controlled APIs/events.

### 4.1 Product/control plane

Responsibilities:
- User authentication, authorisation and session.
- Watchlists, preferences, portfolio views and research workspace.
- Dashboard, charts, alerts and reports.
- API gateway / application API.
- User approvals and administrative controls.
- Read-optimised query models.

It must not own market-data truth or call training code directly.

### 4.2 Real-time market-data and decision plane

Responsibilities:
- Licensed feed adapters.
- Event decoding, sequence tracking, timestamping and gap recovery.
- Instrument/security identity resolution.
- Market state and order-book reconstruction where data supports it.
- Streaming/incremental feature calculation.
- Lightweight, approved model inference.
- Forecast validation and uncertainty checks.
- Deterministic decision/risk evaluation.
- Later, separately approved paper/live execution and reconciliation.

This plane is performance-sensitive. It must not synchronously call LLMs, run large training jobs, query a research warehouse or wait for a dashboard.

### 4.3 Research and model plane

Responsibilities:
- Historical and point-in-time data.
- Data quality, labels, features and versioned datasets.
- Baselines, model training, hyperparameter search and experiments.
- Backtests, statistical tests and robustness evaluation.
- Model artifacts, registry, drift and candidate evaluation.
- Model packaging, promotion and rollback evidence.

It is compute-heavy and can operate asynchronously. Research jobs must not starve the market-event path.

### 4.4 Autonomous agent plane

Responsibilities:
- Research planning, literature review and prior-art analysis.
- Task decomposition and delegation.
- Approved experiment orchestration.
- Scoped engineering contributions and PR creation.
- Independent critique and evidence checks.
- Research document/index updates.

The agent plane interacts through approved tool APIs. It must not receive unrestricted database credentials, production secrets or broker order credentials.

### 4.5 Platform engineering plane

Cross-cutting:
- Configuration and secrets.
- Identity and policy enforcement.
- Logging, metrics, tracing and profiling.
- CI/CD, dependency and licence scanning.
- Backups, restore and disaster-recovery.
- Health checks, feature flags, kill switches and incident runbooks.

---

## 5. Bounded contexts and module ownership

Each module owns its domain rules and data contract. Other modules use public interfaces rather than importing private internals.

| Bounded context | Core responsibility | Owns | Main outputs |
|---|---|---|---|
| Source & Entitlement | Provider adapters and permitted-use metadata | Provider identity, product, entitlements, rate-limit policy | Normalised source events / access decisions |
| Reference Data / Security Master | Instrument identity and contract lifecycle | Canonical instrument IDs, symbol aliases, exchange/segment, tick/lot/multiplier, expiry, calendar | Versioned instrument definitions |
| Market Data Ingestion | Receive, decode and validate raw events | Feed sessions, sequence state, raw event provenance | Canonical market events |
| Market State | Maintain current state from ordered events | Quote/trade/book/bar state and recovery checkpoints | Market snapshots and state changes |
| Corporate Actions | Splits, dividends, symbol/contract changes and adjustments | Action event lineage and adjustment versions | Point-in-time adjusted histories |
| Point-in-Time Data | As-of availability and source reliability | Publication/ingestion/availability timestamps, revisions, provenance | PIT observations and join results |
| Feature Engine | Batch and streaming causal features | Feature definitions, formulas, versions and state | Feature vectors / feature-set manifests |
| Dataset & Label Engine | Build research-ready targets and datasets | Target definitions, horizons, splits, hashes | Immutable dataset versions |
| Model Research | Training and experiment orchestration | Experiment specs, training runs and candidate artifacts | Model artifacts and metrics |
| Model Registry | Model lifecycle and compatibility | Version, artifact hash, dataset/feature/label lineage, status | Approved model reference |
| Inference | Load approved models and compute forecasts | Model runtime/cache and inference contract | Forecast events |
| Decision & Risk | Turn forecasts into constrained trade candidates | Strategy policy, risk constraints and exposure state | Trade intent or NO_TRADE |
| Execution / OMS (later) | Order lifecycle and venue/broker protocol | Order IDs, state transitions, fills, cancels, reconciliation | Execution events and reports |
| Backtesting & Replay | Reconstruct historical outcomes | Simulation assumptions and run manifests | Metrics, ledgers and reports |
| Agent Orchestration | Durable multi-agent research and engineering workflow | Agent tasks, budgets, approvals and workflow history | Evidence-backed tasks and PRs |
| API / Application | Product endpoints and user-facing views | API schema and user-facing read/write operations | UI-facing responses |
| Observability / Audit | System health, traces, metrics and security audit | Operational signals and audit event references | Alerts, health state and audit evidence |

### Module ownership rules

1. Each bounded context owns writes to its own state.
2. Cross-context access uses a public application API, repository port or versioned event schema.
3. No direct import of another module's private package.
4. No cross-module database table mutation.
5. No global mutable singletons for live market state.
6. All events carry identity, version, source and timestamp metadata.
7. A module can be unit-tested without starting unrelated modules.
8. Shared kernel types must stay small and stable: IDs, timestamps, money/price units, event envelopes and error categories only.

---

## 6. Internal module structure: OOAD and OOPM in practice

Use a consistent structure per bounded context when the context has meaningful complexity:

```text
market_data/
  domain/
    entities.py
    value_objects.py
    events.py
    policies.py
    exceptions.py
  application/
    commands.py
    queries.py
    services.py
    handlers.py
    ports.py
  infrastructure/
    providers/
    persistence/
    transport/
    clock.py
  interfaces/
    api.py
    cli.py
  tests/
    unit/
    contract/
    integration/
```

Do not create empty folders or one class per function merely to look object-oriented. Small modules can remain simple.

### 6.1 OOAD modelling artefacts

For each important context create:
- Use-case diagram: actor, goal and system boundary.
- C4 system context and container diagram.
- Component diagram for the bounded context.
- Sequence diagram for critical flows.
- State machine for lifecycle-heavy objects.
- ER/data model for owned persistence.
- Deployment diagram for processes, networks and failure domains.
- ADR for decisions with major trade-offs.

Use C4 zoom levels—context, container, component and code—rather than a single giant architecture diagram:
https://c4model.com/

### 6.2 Domain modelling rules

Distinguish:
- **Entity:** identity and lifecycle matter (Instrument, DatasetVersion, ModelArtifact, Order).
- **Value object:** immutable value defined by its contents (Price, Quantity, Currency, TimeRange, FeatureVersion).
- **Domain event:** an immutable fact that occurred (MarketEventReceived, DatasetPublished, ModelApproved, FeedGapDetected).
- **Domain service:** domain operation that does not naturally belong to one entity (CorporateActionAdjustmentPolicy).
- **Application service:** coordinates a use case and ports (PublishDataset, PromoteCandidate).
- **Infrastructure adapter:** implements a port using a provider, database or network protocol.

Use composition over inheritance; favour small, explicit interfaces. Use inheritance only where substitutability is real and testable.

### 6.3 SOLID / GRASP application

- SRP: provider adapter handles one provider protocol; feature formula does not also persist datasets.
- OCP: add a new provider or model behind an interface without rewriting the domain.
- LSP: an adapter must honour the full source contract, not return partial fake capabilities.
- ISP: separate HistoricalDataSource, LiveMarketDataSource, DepthDataSource and BrokerExecutionPort.
- DIP: application/domain rules depend on ports; adapters depend inward on contracts.
- High cohesion / low coupling: module has one business capability and minimal public API.
- Information expert: domain state owner enforces its own invariant.
- Controller: application handler receives use-case commands and coordinates services without owning domain calculations.

Do not over-abstract a stable, simple piece of code. Abstraction must reduce change coupling or enable a real test/integration boundary.

---

## 7. DSA as an explicit performance design tool

DSA is not only interview preparation. It determines memory layout, per-event work, latency and throughput.

| Problem | Candidate structure/algorithm | Expected complexity | Design constraint |
|---|---|---:|---|
| Instrument lookup | Hash map keyed by canonical InstrumentId | O(1) average lookup | Bound memory; avoid mutable symbol as key |
| Recent tick history | Fixed-capacity ring buffer | O(1) append; O(1) indexed access | Define overflow/drop policy explicitly |
| Rolling sum/count/mean | Incremental accumulators | O(1) update | Handle numerical drift and window eviction |
| Rolling variance | Stable online algorithm (e.g. Welford with a tested rolling variant) | O(1) update | Test numerical stability and rebase policy |
| Rolling max/min | Monotonic deque | O(1) amortised update | Expire indices by window and preserve order |
| Fixed-depth book | Compact arrays / price-level slots where feed semantics permit | Often O(1) by level | Do not confuse market-by-price with market-by-order |
| Dynamic price levels | Ordered map / balanced tree / B-tree | O(log L) update/search | Choose based on actual depth and update pattern |
| Top-K instruments/signals | Heap / partial selection | O(N log K) or O(N) selection | Tie-break deterministically |
| Scheduled jobs/timeouts | Min-heap priority queue | O(log N) insert/remove | Monotonic time; cancellation strategy |
| Duplicate detection | Hash set / bounded dedupe window | O(1) average | Retention and restart semantics explicit |
| Producer-consumer event flow | Bounded queue; SPSC only for strict single-producer/single-consumer path | O(1) push/pop typical design | Backpressure and ownership are mandatory |

### Algorithm-specific rules

- Build incremental features so each event updates only affected state; do not recompute the whole historical frame on every tick.
- Use integer tick units or fixed-point/decimal representations for exchange prices and quantities where exact tick precision is required; convert to floating point only at model boundaries with an explicit conversion policy.
- Use deterministic tie-breaking for rankings, queues and selection.
- Bound memory and event history; unbounded collections are not permitted in long-running services.
- Benchmark using representative event distributions, not only synthetic uniform input.
- Validate fast implementations against a slower reference implementation for numerical parity.
- Use property-based tests for ring buffers, rolling windows, book updates, deduplication and event ordering.
- Complexity notation is a starting estimate; cache locality, allocations and contention must be profiled.

### DSA anti-patterns

- Sorting the full instrument universe for every market event.
- Recalculating every rolling indicator from scratch.
- Creating one thread/async task per tick.
- Unbounded queues between a fast producer and slow consumer.
- Global locks around the complete feature or inference pipeline.
- Using a complex lock-free structure without profiling and concurrency proof.

---

## 8. OS and concurrency engineering

The operating system is part of the architecture. Process, thread, memory, scheduler, filesystem and network behaviour affect real latency and reliability.

### 8.1 Workload isolation

| Workload | Initial execution model | Reason |
|---|---|---|
| Broker/vendor WebSocket I/O | Async I/O event loop or bounded I/O workers | Many network waits; avoid blocking the loop |
| CPU-heavy feature/replay jobs | Separate processes or compiled code after profiling | Avoid starving the market path |
| Model training / hyperparameter sweeps | Dedicated CPU/GPU worker processes | Resource isolation and long runtimes |
| Model inference | Separate bounded worker/runtime based on measured latency | Stable model loading and memory control |
| Agent LLM calls | Separate Temporal worker queues | Unpredictable latency and provider throttling |
| Dashboard/API reads | Web application worker pool | User traffic must not block feed processing |

The current repository uses Python 3.11.15 in its documented QA environment and has a Python-first ADR. Do not assume optional free-threaded Python behaviour applies to this runtime. Python's `asyncio` is useful for I/O-bound concurrency; CPU-bound work needs deliberate process/thread/compiled-runtime decisions and benchmarking. Official Python docs explain the distinction:
- https://docs.python.org/3/library/concurrency.html
- https://docs.python.org/3/library/asyncio-threading.html

### 8.2 OS rules

- Never block a market-feed event loop with disk writes, network calls or model training.
- Apply bounded queues and queue-depth metrics at every producer-consumer boundary.
- Define overload policy: slow consumer, drop non-critical derived event, pause source if supported, spill to durable buffer or declare system degraded. Never silently discard a required event.
- Use graceful shutdown: stop admission, drain/flush bounded work, persist checkpoints, close sockets, release locks and exit.
- Use process supervision and health checks; restart only after state recovery checks.
- Bound CPU, RAM, file descriptors, disk, GPU memory and concurrent processes.
- Handle out-of-memory and process crash as explicit failure scenarios.
- Use monotonic clocks for elapsed-time/timeout measurement; retain wall-clock and exchange timestamps for event semantics.
- Consider CPU affinity, NUMA, huge pages, NIC queue placement and kernel-bypass only after a measured latency bottleneck and approved infrastructure design.
- Avoid shared mutable state across worker processes; use explicit ownership and messages.

---

## 9. Computer Networks and distributed-systems engineering

Network calls fail, arrive late, duplicate, time out or return after the caller has lost state. Treat the network as an unreliable dependency.

### 9.1 Source protocol distinction

| Source/interface | Likely mechanism | Engineering considerations |
|---|---|---|
| Retail broker market stream | WebSocket over TCP | Authentication expiry, heartbeat, rate limits, reconnect, subscription replay, sequence/freshness checks |
| Direct exchange multicast feed | UDP multicast over authorised connectivity where contracted | Packet sequencing, loss detection, redundant paths, snapshot/recovery protocol, clock and NIC engineering |
| Historical REST API | HTTPS/TCP | Backfill windows, pagination, rate limits, partial responses, exponential backoff with jitter |
| Internal service-to-service | HTTP/gRPC or internal event transport | Deadlines, authentication, schema version, retries, circuit breakers, idempotency |
| Research object/artifact store | File/object API | Checksums, multipart integrity, atomic publication and retention policy |

Do not assume WebSocket broker data has the same depth, latency or completeness as an exchange multicast product.

### 9.2 Timestamp and sequence model

Every market observation should retain separate fields:
- Exchange/provider event timestamp.
- Local receive timestamp.
- Ingestion/persistence timestamp.
- Availability timestamp (when the model was permitted/able to use the observation).
- Source sequence number/event ID where supplied.
- Clock-quality and timestamp-source metadata.

Use exchange timestamps for market chronology, local monotonic clock for local elapsed latency, and availability time for point-in-time model joins. Never collapse them into one `timestamp`.

### 9.3 Network fault handling

- Explicit connection state machine: DISCONNECTED → CONNECTING → AUTHENTICATED → SUBSCRIBED → LIVE → DEGRADED → RECOVERING.
- Heartbeats and freshness thresholds.
- Sequence-gap and out-of-order detection.
- Reconnect with exponential backoff and jitter.
- Subscription restoration after reconnect.
- Snapshot + delta synchronisation where supported.
- Rate-limit and retry policy per provider.
- Deadlines and request timeouts.
- Circuit breaker for repeated provider failure.
- Bulkheads so one slow source cannot block all sources.
- Idempotent consumers for duplicate delivery.
- Dead-letter/quarantine path for malformed or repeatedly failing events.
- TLS for external network links; service identity and least-privilege authentication for internal control APIs.

Do not promise end-to-end “exactly once” just by selecting a broker. Prefer durable event identity, at-least-once delivery where appropriate, deduplication and idempotent state transitions.

### 9.4 Distributed consistency patterns

- Transactional outbox when a committed DB change must reliably publish an event.
- Idempotency keys for externally visible side effects.
- Optimistic concurrency/version checks for competing updates.
- Saga/Temporal workflow for long-running multi-step processes.
- Reconciliation for state that can diverge from a provider or broker.
- Explicit UNKNOWN / RECONCILIATION_REQUIRED states for uncertain external outcomes.

A network timeout after sending an order or changing a provider subscription is not proof that the operation failed.

---

## 10. DBMS and data architecture

Use different storage types for different access patterns; do not force all data into one database.

### 10.1 Proposed storage responsibilities

| Data class | Initial/current approach | Target candidate when justified |
|---|---|---|
| Immutable raw historical market data | Existing local CSV/Parquet and manifests | Partitioned Parquet/object store with immutable metadata |
| Large research datasets/features | Existing versioned Parquet | Parquet + Arrow; DuckDB/Polars for local analytics if benchmarked |
| Transactional metadata | Existing files/JSONL in MVP | PostgreSQL or equivalent relational store after concurrency/transaction requirement |
| Agent tasks/approvals/workflow metadata | New structured store via A0/A1 design | Relational DB + Temporal workflow history |
| Current in-memory market state | Not implemented in MVP | Process-local bounded memory/cache with rebuild/replay path |
| Logs/metrics/traces | Existing structured logs and operations records | OpenTelemetry-compatible telemetry backend |
| Model binaries/checkpoints | Existing artifact directories | Immutable artifact store with checksum and lineage |

### 10.2 DBMS principles

- Use unique constraints for idempotency and canonical identities.
- Use foreign keys and domain validation where relationships are transactional.
- Use transactions for state transitions that must be atomic.
- Define indexes from actual query patterns, not by guessing.
- For time-series data, evaluate partitioning by time and possibly instrument/venue based on query and ingestion workload.
- Keep raw data append-only; corrections are new versioned records or explicit correction events, not invisible overwrites.
- Keep model/feature/dataset metadata and their hashes linked.
- Maintain backups and test restore rather than assuming backups work.
- Avoid storing large tick payloads in a transactional database until measured requirements justify it.
- Cache is derived and rebuildable; it is not the sole source of truth.
- Avoid EAV for high-frequency features without measured proof that it suits query and storage patterns; prefer typed/versioned feature contracts and columnar artifacts where appropriate.

### 10.3 Consistency and data lineage

Each important output should trace to:
- Source provider and entitlement reference.
- Source payload/event IDs and timestamps.
- Instrument-master version.
- Corporate-action version.
- Data-quality report.
- Feature-set version.
- Dataset hash and split manifest.
- Model code commit and artifact checksum.
- Configuration and seed.
- Evaluation run and cost assumptions.

This lineage is required for both scientific reproducibility and operational debugging.

---

## 11. ML/model serving and real-time algorithm architecture

Keep training, inference and decision-making separate.

### 11.1 Training/research path

```text
Licensed point-in-time data
  -> reference data + corporate actions
  -> immutable raw archive
  -> validation / quality
  -> causal batch features
  -> labels / target contracts
  -> versioned datasets
  -> baseline / candidate training
  -> calibration + robustness + statistical tests
  -> model registry (CANDIDATE)
  -> independent promotion gate
```

### 11.2 Real-time inference path

```text
Market event
  -> source/schema/sequence/freshness validation
  -> canonical instrument resolution
  -> current market-state update
  -> incremental feature update
  -> approved model inference
  -> forecast + calibrated uncertainty
  -> deterministic decision/risk policy
  -> forecast/decision event to product UI
```

### 11.3 Strict separation

- Training never runs inside the market-event loop.
- LLM agents do not run synchronously per tick.
- Feature computation is deterministic and versioned.
- Batch and streaming feature implementations must share mathematical definitions and pass parity tests.
- Inference loads only an approved model artifact and matching feature schema.
- Model outputs include model version, target, horizon, issue time, calibration state and data-quality status.
- NO_TRADE/ABSTAIN is valid when inputs are stale, missing, out of distribution or risk rules fail.
- Decision/risk policy is deterministic and separately tested; model output cannot bypass it.
- Paper/shadow evaluation precedes any future live execution.

### 11.4 Model research integration

The model roadmap's candidate algorithms—RC-MTFSM, SPT-LOB, RGEE, CSFA, DHT-FH and DSA—must each have:
- A bounded module/interface.
- A common prediction/feature contract.
- A baseline and ablation definition.
- Dataset and target version.
- Metrics relevant to the task.
- Calibration/uncertainty analysis.
- Runtime and memory profile.
- Independent robustness review.

The architecture must allow one model family to be replaced without rewriting market data, risk, UI or portfolio modules.

---

## 12. API and application architecture

### Backend
- FastAPI may remain the current application API technology.
- Request/response schemas are versioned and validated.
- API handlers call application use cases, not model internals or database tables directly.
- Use authentication/authorisation for any non-local environment.
- Add pagination, query limits, rate limits and request IDs.
- Keep dashboard read queries separate from commands that mutate state.
- Public API DTOs are separate from internal domain entities.

### Frontend
- Existing React/Vite application remains the product UI foundation.
- UI consumes typed API contracts.
- UI never connects directly to raw market-data providers or loads model binaries.
- Live market views use push/event subscriptions appropriate to the product; historical dashboards use query APIs.
- Show data freshness, source status, model version, uncertainty and stale-data/NO_TRADE state explicitly.

### API versioning and compatibility
- Backward-compatible additive changes preferred.
- Breaking contract changes require a new version and migration plan.
- Provider-specific data is normalised behind adapters but unique fields remain accessible through typed extensions.
- Schema compatibility tests run before adapter deployment.

---

## 13. Reliability, fault tolerance and operations

Use the AWS Well-Architected pillars—operational excellence, security, reliability, performance efficiency, cost optimisation and sustainability—as a review checklist, not as a vendor prescription.

Reference: https://docs.aws.amazon.com/wellarchitected/latest/framework/the-pillars-of-the-framework.html

### 13.1 Reliability patterns

- Timeouts on every network call.
- Bounded retries with exponential backoff and jitter.
- Circuit breakers for repeated remote failure.
- Bulkheads between provider, training, agent and UI workloads.
- Bounded queues and explicit backpressure.
- Idempotent event processing and side effects.
- Checkpoints and replayable event history.
- Graceful shutdown and restart recovery.
- Health, readiness and liveness checks with distinct meanings.
- Safe degradation: stale data must be labelled and cannot silently be treated as current.
- Disaster-recovery and restore drills.
- Reconciliation when internal state is uncertain.

### 13.2 Observability

Instrument the four golden signals:
- Latency.
- Traffic.
- Errors.
- Saturation.

Also instrument domain-specific indicators:

**Market-data**
- Feed connection state and uptime.
- Event rate and last-received age.
- Sequence gaps, duplicates and out-of-order count.
- Snapshot recovery count.
- Subscription coverage and entitlement failures.
- Queue depth and consumer lag.

**Features and models**
- Feature calculation time.
- Batch/streaming feature parity errors.
- Missingness and out-of-distribution flags.
- Model load time and inference latency.
- Prediction throughput and failure rate.
- Calibration/drift and prediction distribution.

**Research and agents**
- Experiment queue depth and run duration.
- Reproduction success and test failure.
- Dataset/model lineage completeness.
- Agent task completion, rejection, retry and spend.
- Sandbox/worker health.

**API/UI**
- Request count, latency, error rate and saturation.
- WebSocket connection state and update lag.
- API schema and data freshness.

Use histograms and P50/P95/P99/P99.9, not only average latency. OpenTelemetry semantic conventions can standardise trace/metric/log attributes across components.

References:
- Google SRE SLOs: https://sre.google/sre-book/service-level-objectives/
- Google SRE monitoring: https://sre.google/sre-book/monitoring-distributed-systems/
- OpenTelemetry semantic conventions: https://opentelemetry.io/docs/concepts/semantic-conventions/

### 13.3 Define SLOs from requirements, not guesses

Candidate SLI/SLO families:
- Market feed freshness by source/segment.
- Event loss/gap detection and recovery duration.
- Feature update latency.
- Model inference latency and availability.
- Prediction API availability and error rate.
- Data pipeline success and recovery time.
- Research workflow recovery and completion.
- Data-quality gate false-accept rate.

Target numbers must be agreed after feed/vendor SLA, instrument universe, event rate, user expectations and hardware are known. A target such as “99.99%” or “under 1 ms” should not be inserted without a measurable workload and an operating budget.

---

## 14. Security and financial safety architecture

Use NIST Secure Software Development Framework as a lifecycle reference, alongside threat modelling and current CERT-In/OWASP agent-security material.

References:
- NIST SP 800-218 SSDF: https://csrc.nist.gov/pubs/sp/800/218/final
- OWASP ASVS: https://owasp.org/www-project-application-security-verification-standard/
- OWASP Top 10 for Agentic Applications 2026: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- CERT-In AI Security Auditing Guidelines v1.0 (4 November 2026): https://www.cert-in.org.in/Downloader?fileName=CIGU-2026-0004.pdf&pageid=6&type=2

### Security requirements

- Unique identities and least privilege.
- Secrets manager/runtime secret injection; never secrets in prompt, code, Git or logs.
- TLS for external links and authenticated service identity internally.
- RBAC/ABAC for user and agent permissions.
- Input validation and schema validation at every boundary.
- Dependency lockfiles, licence and vulnerability scans, SBOM.
- Container isolation for code/experiment agents.
- Restricted network egress for workers/sandboxes.
- Audit trails for model promotion, agent delegation, data use and future execution.
- Encryption in transit and at rest where applicable.
- Backup protection and restore validation.
- Rate limits and abuse detection.
- Prompt-injection defence: retrieved content is untrusted data, not policy.
- No research agent gets broker execution credentials.
- Any future order-routing system has independent deterministic risk gates, limits, kill switch and reconciliation.

### Data rights are architecture concerns

Each source adapter must carry an entitlement record identifying allowed market, segment, fields, display/non-display use, model training, retention, derived data and redistribution. The data entitlement policy is checked before ingestion and before downstream use. A technically accessible feed is not proof that all intended uses are licensed.

---

## 15. Testing architecture: make every layer independently verifiable

### 15.1 Test levels

| Test level | Purpose | Example |
|---|---|---|
| Unit | Pure domain logic | Price rounding, label rules, feature formula |
| Property-based | Invariants over many generated inputs | Order-book invariants, ring-buffer wraparound |
| Contract | Adapters honour interface/schema | Vendor event maps to canonical quote |
| Component | Module works against fake ports | Feature Engine with in-memory event source |
| Integration | Real module boundaries work together | Feed → normalizer → state → feature |
| Replay/determinism | Same event log reproduces same state | Rebuild order book after restart |
| ML evaluation | No leakage and correct metrics | Chronological split, point-in-time join |
| Performance | Latency/throughput/memory under workload | Tick bursts, instrument fan-out |
| Soak | Long-running stability | Memory growth, sockets, reconnect cycles |
| Fault injection | Recovery is correct | Kill worker, disconnect feed, fail DB |
| Security | Permission and isolation | Prompt injection, IDOR, secret leakage, egress |
| Acceptance | End-to-end user outcome | Display fresh forecast with lineage and risk state |

### 15.2 Critical invariants to test

- Raw data is not mutated.
- Exchange and receive timestamps remain distinct.
- Sequence gaps are detected and do not silently produce a healthy book.
- The book never violates bid/ask/quantity/tick invariants for a valid source contract.
- No future information enters features.
- Batch and streaming feature implementations are equivalent within declared tolerances.
- Model input schema/version exactly matches artifact requirements.
- A model cannot load if dataset/config/schema compatibility checks fail.
- Failed candidate promotion does not replace the active model.
- Duplicate event delivery does not duplicate state transitions or side effects.
- Feed reconnect rebuilds state from snapshot/checkpoint correctly.
- Stale or uncertain state results in degraded/abstain behaviour.
- Model/API failure does not stop raw event capture where the architecture permits independent recording.
- Agent workers cannot access forbidden tools, secrets or network destinations.
- Main branch cannot be modified by the autonomous engineering worker.
- Backup restore reproduces a verified data/metadata state.

### 15.3 CI gates

Each PR should run:
1. Formatting and lint.
2. Static typing and import/dependency boundary checks.
3. Unit and property tests.
4. Contract/component tests.
5. Integration tests relevant to changed contexts.
6. Data/model leakage tests if the change affects ML paths.
7. Dependency and secret scans.
8. Build/package verification.
9. Performance regression tests for critical code.
10. Human review for protected architecture/security/model changes.

Coverage is one quality signal; it does not replace invariant testing or realistic integration tests.

---

## 16. Engineering concepts mapped to Finance AI

This table is the learning-to-implementation map for DSA, OOPM, OOAD, CN, OS and other engineering subjects.

| Engineering subject | Actual use inside Finance AI / MPFM |
|---|---|
| DSA | Market-state lookup, ring buffers, order-book structures, heaps, queues, rolling features and top-K selection |
| OOP / OOPM | Domain entities, value objects, composition, interfaces, encapsulated invariants and lifecycle models |
| OOAD | Use cases, class/component/sequence/state diagrams, bounded contexts and design reviews |
| SOLID / Design Patterns | Adapter, Strategy, Factory, Repository, State, Observer/Publisher, Decorator and dependency inversion where justified |
| DBMS | Transactions, keys, indexes, partitioning, concurrency, isolation, audit and data lineage |
| Computer Networks | TCP/WebSocket/UDP/multicast, sequence/gap recovery, TLS, timeouts, retries and network latency |
| Operating Systems | Processes/threads, scheduling, memory, locks, IPC, file descriptors, graceful shutdown and resource isolation |
| Distributed Systems | Idempotency, retries, outbox, sagas, reconciliation, eventual consistency, fault isolation and recovery |
| Software Engineering | Requirements, modularity, code review, CI, change control, versioning and maintenance |
| System Design | Capacity, throughput, latency budgets, boundaries, failure domains, scalability and deployment |
| Algorithms / Numerical Methods | Rolling features, stable online statistics, optimisation, calibration and numerical parity |
| Statistics / Econometrics | Walk-forward validation, uncertainty, calibration, statistical testing and multiple-testing control |
| ML / Deep Learning | Model architectures, training, inference, feature contracts, drift and model lifecycle |
| Security Engineering | Threat models, identity, least privilege, secret handling, supply chain and audit |
| SRE / DevOps | SLIs/SLOs, monitoring, incident response, deployment, rollback, backups and recovery |
| Financial Engineering | Market microstructure, corporate actions, costs, position/risk, liquidity and execution constraints |

The rule is practical: every important architecture choice should identify which engineering principle it uses, what problem it solves, how it is tested and what trade-off it introduces.

---

## 17. Proposed repository target structure

This is a target direction, not a mandate to create every folder immediately. Add structure only when a bounded context is implemented.

```text
src/
  shared_kernel/
    ids.py
    timestamps.py
    money.py
    events.py
    errors.py

  contexts/
    source_entitlements/
      domain/ application/ infrastructure/
    reference_data/
      domain/ application/ infrastructure/
    market_data/
      domain/ application/ infrastructure/
    market_state/
      domain/ application/ infrastructure/
    corporate_actions/
      domain/ application/ infrastructure/
    point_in_time/
      domain/ application/ infrastructure/
    features/
      domain/ application/ infrastructure/
    datasets/
      domain/ application/ infrastructure/
    model_research/
      domain/ application/ infrastructure/
    model_registry/
      domain/ application/ infrastructure/
    inference/
      domain/ application/ infrastructure/
    decision_risk/
      domain/ application/ infrastructure/
    backtesting/
      domain/ application/ infrastructure/
    execution/                 # future, separately gated
      domain/ application/ infrastructure/
    agent_orchestration/
      domain/ application/ infrastructure/
    application_api/
      http/ websocket/ schemas/

  platform/
    config/
    logging/
    telemetry/
    security/
    persistence/
    runtime/
    feature_flags/

  processes/
    api_server.py
    market_feed_worker.py
    inference_worker.py
    research_worker.py
    agent_worker.py

tests/
  unit/
  property/
  contract/
  integration/
  replay/
  performance/
  soak/
  fault_injection/
  security/
  ml_validation/

docs/
  architecture/
    c4/
    sequence/
    state/
    adr/
```

Keep existing modules and scripts stable while migrating behind contracts. Do not make a giant directory restructure part of the first architecture task.

---

## 18. Deployment strategy and technology selection

### 18.1 Initial deployment topology

Start with a single repository and a small set of runtime processes:

1. API/UI backend process.
2. Market-data collector process when a live source is approved.
3. Inference/market-state process when latency and isolation require it.
4. Research/experiment worker process.
5. Temporal agent worker processes when A1/A3 orchestration is implemented.

Local development can use direct process execution or Docker Compose when required. Do not add Kubernetes before multi-node scheduling, autoscaling, resilience or operational requirements justify it.

### 18.2 Language strategy

- Python remains the default for existing research, features, dataset and model training.
- Async I/O for network-bound collectors and orchestration where it simplifies the workload.
- Multiprocessing/separate worker processes for CPU/GPU-bound training and replay.
- Rust/C++ only for measured, latency-critical paths where Python fails a defined SLO and a new ADR approves the change.
- Typed cross-language contracts and numerical-equivalence tests are mandatory if a compiled component is introduced.

### 18.3 Technology choices must follow workload tests

| Need | Candidate | Adoption trigger |
|---|---|---|
| Historical analytics | Parquet + DuckDB/Polars | Measured scan/runtime/memory improvement |
| Transactional metadata | PostgreSQL | Concurrent state and transaction requirements exceed file-backed design |
| Time-series serving | QuestDB/other candidate | Live ingest/query workload is measured and justified |
| Durable agent workflows | Temporal | A1 proves durable workflow requirement |
| Agent reasoning | Microsoft Agent Framework candidate | A1 evaluation validates required provider/tool behaviours |
| Cross-service telemetry | OpenTelemetry | Process/service boundaries require trace correlation |
| Event broker | Kafka/NATS/Aeron candidate | Independent durable consumers or throughput/latency needs justify it |
| Container orchestration | Kubernetes | Multi-node deployment and operational scale justify its cost |

Never adopt several overlapping tools simultaneously without separate use cases.

---

## 19. Migration plan that preserves D0 → D4

The engineering architecture supports the existing dependency sequence. It does not replace it.

### Foundation stage — architecture and contracts

- Reconcile current source code with documentation.
- Freeze module ownership and import/dependency rules.
- Define canonical IDs, timestamps, money/price units and event envelopes.
- Create C4 context/container diagrams and component/sequence/state diagrams for critical flows.
- Define test tiers, data lineage and operational metrics.
- Record target changes as ADRs.

Exit: every new module has owner, interface, dependencies, error model, tests and data contract.

### D0 — engineering foundation / security master

- Keep existing engineering standards.
- Introduce canonical instrument identity and provider mapping.
- Separate provider adapter protocols for historical bars, live events and depth.
- Establish event envelope, timestamps, schema version and entitlement checks.
- Enforce module dependency graph and typed contracts.

Exit: one instrument/source path can be ingested and validated without provider details leaking into domain logic.

### D1 — point-in-time data and feature foundation

- Corporate actions and reference data.
- Reliable source timestamps/availability.
- Data quality, replay and raw immutability.
- Batch/streaming feature definitions and parity.
- Strong multi-instrument baselines.

Exit: reproducible point-in-time feature/dataset outputs with a complete lineage manifest.

### D2 — model and financial state engineering

- Baseline benchmark programme.
- Model family interfaces.
- Financial State Encoder and task heads as candidate research components.
- Independent experiment/evaluation pipeline.
- Model artifacts, runtime profile and compatibility gates.

Exit: candidate model is reproducible, better than declared baselines on pre-registered metrics, and robust enough for its scope.

### D3 — decision/risk and philosophy/mandate contexts

- Structured forecast and decision contracts.
- Risk policy and explicit NO_TRADE.
- Philosophy ontology and mandate conditioning as downstream/optional variants.
- Human-readable rationale backed by model evidence.

Exit: decision logic cannot alter raw forecasts or bypass risk constraints.

### D4 — integrated evaluation and system hardening

- End-to-end event replay and controlled paper/shadow modes.
- Latency/load/soak and fault-injection tests.
- Security review, data-rights review and recovery drills.
- Integration of approved external adapters/engines.
- Operational readiness review and rollback plan.

Exit: all target capabilities have acceptance evidence; no untested live execution capability is enabled.

Parallel work on licensing, baseline research, ontology, prior art and security can continue without bypassing dependencies.

---

## 20. Required engineering artefacts per module

Before a module is implemented, it should have:

1. Requirement and owner.
2. Context/role definition and explicit non-goals.
3. C4 component/sequence/state diagram where useful.
4. Input/output schema and version.
5. Dependency list and allowed import graph.
6. Data ownership and consistency model.
7. Error taxonomy and retry/timeout policy.
8. Performance/resource budget.
9. Security/data-rights classification.
10. Unit, property, contract, integration and failure tests.
11. Observability/SLI definitions.
12. ADR for significant trade-offs.
13. Rollback/migration plan if existing behaviour changes.

A module is complete only when implementation, tests, docs, telemetry and operational behaviour all match the contract.

---

## 21. Architecture review checklist

Before merge or release, ask:

### Correctness
- Are domain invariants explicit?
- Are timestamps/timezones/availability semantics unambiguous?
- Are duplicate, late and out-of-order inputs handled?
- Can the same event replay reproduce state?
- Is the system fail-closed when data are stale or corrupt?

### Modularity
- Does each context own its state and rules?
- Are interfaces stable and provider-neutral?
- Are imports acyclic?
- Does a change remain local to one module?
- Is a new service genuinely necessary?

### Performance
- What is the measured workload and complexity?
- What is P50/P95/P99/P99.9 latency?
- Are allocations, locks, queues or network calls the bottleneck?
- Is memory bounded?
- Does overload create backpressure rather than silent loss?

### Reliability
- What if a worker/provider/database crashes?
- Are retries bounded and operations idempotent?
- Can state rebuild from durable inputs?
- Are recovery objectives and restore procedures tested?
- Are health states and SLOs measurable?

### Security and governance
- Is access least-privilege?
- Are secrets protected?
- Are provider data rights valid for the intended use?
- Are dependencies and licences reviewed?
- Can an agent or model bypass controls?

### ML quality
- Is the target appropriate?
- Are baselines strong and evaluation splits valid?
- Are metrics complete and independently recomputed?
- Is the model calibrated and robust?
- Does the model add value after costs?
- Is model inference parity verified after optimisation?

---

## 22. External engineering references

### Architecture and modularity
- C4 model: https://c4model.com/
- Martin Fowler, Monolith First: https://martinfowler.com/bliki/MonolithFirst.html
- Microsoft microservices and bounded contexts: https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/microservices
- Microsoft event-driven architecture: https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/event-driven

### Reliability and distributed systems
- AWS Well-Architected pillars: https://docs.aws.amazon.com/wellarchitected/latest/framework/the-pillars-of-the-framework.html
- AWS transactional outbox: https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html
- AWS retry with backoff: https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/retry-backoff.html
- AWS circuit breaker: https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/circuit-breaker.html
- Google SRE Service Level Objectives: https://sre.google/sre-book/service-level-objectives/
- Google SRE Monitoring Distributed Systems: https://sre.google/sre-book/monitoring-distributed-systems/

### Runtime and observability
- Python concurrency: https://docs.python.org/3/library/concurrency.html
- Python asyncio/threading: https://docs.python.org/3/library/asyncio-threading.html
- OpenTelemetry semantic conventions: https://opentelemetry.io/docs/concepts/semantic-conventions/

### Security
- NIST SSDF SP 800-218: https://csrc.nist.gov/pubs/sp/800/218/final
- OWASP ASVS: https://owasp.org/www-project-application-security-verification-standard/
- OWASP Agentic Applications 2026: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- CERT-In AI Security Auditing Guidelines v1.0: https://www.cert-in.org.in/Downloader?fileName=CIGU-2026-0004.pdf&pageid=6&type=2

---

## 23. Final architecture decisions proposed for review

1. Use modular monolith and bounded contexts as the initial code architecture.
2. Keep the existing Python research pipeline; do not rewrite it.
3. Separate real-time market processing, research/training, agent orchestration and product/control workloads by process when isolation or performance requires it.
4. Adopt ports/adapters and dependency inversion for provider, storage, model and broker integrations.
5. Use event-driven flows for asynchronous market/research/operations events, with sequence, idempotency, backpressure and replay.
6. Use Parquet for immutable research datasets and defer transactional DB adoption until measured requirements justify it.
7. Separate model training, inference, decision/risk and eventual execution.
8. Use DSA structures based on actual event workload and complexity; profile before low-level optimisation.
9. Use Python concurrency appropriately; isolate CPU/GPU work and keep blocking work off the market event loop.
10. Define SLIs/SLOs, fault-injection tests and recovery behaviour before claiming production readiness.
11. Keep security, data rights, auditability and model lineage as cross-cutting architecture requirements.
12. Preserve D0 → D1 → D2 → D3 → D4 and update architecture through ADRs, not undocumented code changes.

**The target is not maximum architectural complexity. It is the simplest modular design that can meet the measured requirements today and evolve safely as data volume, model complexity, market coverage and operational risk increase.**
