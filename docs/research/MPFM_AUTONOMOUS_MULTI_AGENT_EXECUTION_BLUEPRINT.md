# MPFM Autonomous Multi-Agent System — Deep Research & Execution Blueprint

**Research date:** 2026-11-21  
**Repository:** `rudraksha127/Finance-Ai`  
**Status:** Proposed architecture and execution plan; no multi-agent runtime is claimed as implemented  
**Parent product:** Finance AI  
**Research/model platform:** MPFM  
**Priority constraint:** preserve the agreed D0 → D1 → D2 → D3 → D4 development order

> This blueprint extends the existing MPFM research workspace. It does not replace the existing Finance AI pipeline, data contracts, model registry, backtesting, dashboard or research standards. All agent capabilities described here are proposed until implemented and tested.

---

## 1. Executive decision

Build an **Autonomous Research & Engineering Control Plane** as a new subsystem alongside the existing Finance AI research platform.

The system should make progress continuously through event-triggered and scheduled work, but it must not run every agent continuously or let an LLM control infrastructure without deterministic constraints.

### Recommended architecture

1. **Temporal** is the durable workflow/execution backbone: task lifecycle, timers, retries, cancellation, signals, worker queues and recovery.
2. **Microsoft Agent Framework for Python** is the initial agent-reasoning and collaboration candidate: specialist agents, structured outputs, sequential/concurrent workflows, handoffs and bounded manager-led collaboration.
3. A small **Finance AI agent adapter layer** owns provider selection, role contracts, tool policy, budgets, evidence requirements and normalized results. Agent framework APIs must not leak into core MPFM domain contracts.
4. Existing **Finance AI research services** remain authoritative for datasets, feature versions, training, backtests, model registry, drift and operations.
5. A new **agent control plane** stores agent/task identities, permissions, approvals, budgets, schedules, run metadata and audit references.
6. A **sandboxed worker plane** executes research, data analysis and code changes in separate permission domains.
7. A **shared evidence plane** stores source references, code commits, experiment IDs, test reports and reviewed research artifacts.

### Key design decision

Use deterministic code/workflows to control task order, permissions, budgets, retries and completion criteria. Use LLM agents only for tasks that benefit from language reasoning, hypothesis generation, source interpretation, planning or code synthesis.

Do not use an unrestricted group chat as the whole control system.

---

## 2. What already exists in Finance AI and what does not

The current repository already documents substantial research and engineering infrastructure:

- Historical ingestion, cleaning, data-quality checks and corporate-action adjustment support.
- 52 approved MVP features and versioned feature definitions.
- UP/DOWN/HOLD label generation and immutable versioned datasets.
- Logistic Regression and Random Forest baselines.
- Chronological train/validation/test separation and walk-forward backtesting.
- Temporal LSTM and ensemble/calibration experiments.
- Incremental data pipeline, drift monitoring, retraining gates, model registry and operations reporting.
- Point-in-time multimodal data contracts with availability-time semantics.
- Research-only FastAPI prediction API and React dashboard.
- Existing research hub, MPFM master, prediction research ledger, D0–D4 backlog, HFT/open-source reviews and trading-system design.

**Not evidenced as implemented in the current repository snapshot:**

- Persistent LLM-agent runtime.
- Multi-agent delegation and authenticated agent identities.
- Durable agent task queue and workflow history.
- Agent-specific permissions and tool policies.
- Agent memory/evidence lifecycle and poisoning controls.
- Independent agent-evaluation harness.
- Sandboxed autonomous code-editing workers.
- 24/7 task scheduling and recovery for LLM agents.
- Agent control-tower UI.

The existing operations/health and automated model-retraining subsystems are useful foundations, but they are not a general autonomous LLM-agent orchestration system. Preserve them and integrate through explicit APIs/events; do not build a second competing monitoring or model registry.

Repository evidence:
- `README.md`
- `docs/CURRENT_STATE.md`
- `docs/MVP_INTEGRATION_QA_REPORT.md`
- `docs/research/MPFM_RESEARCH_MASTER.md`
- `docs/research/DEVELOPMENT_BACKLOG.md`
- `docs/research/RESEARCH_LOG.md`

The documented AAPL model results are weak and candidates were not promoted. Autonomous agents must preserve negative results and must never present more automation as more predictive capability.

---

## 3. Research findings: framework and infrastructure comparison

### 3.1 Durable workflow orchestration — Temporal

**Recommended backbone.**

Temporal separates Workflow definitions, Activity execution and Worker processes. Workflow history is persisted and replayed to reconstruct state after worker failures. Activities are the place for external I/O and non-deterministic work such as API calls, database access, file operations and LLM invocations. Activities should be idempotent because retry policies can repeat attempts; heartbeats can preserve progress for long-running activities.

Use it for:
- Durable multi-step research jobs.
- Schedule and timer-driven recurring work.
- Worker queues and workload isolation.
- Retry, timeout, cancellation and pause/resume.
- Parent/child research workflows.
- Human approval signals.
- Recovery after process or host failure.
- Versioned workflows and controlled rollout.

Do not place LLM calls, web requests, database I/O or random/time-dependent decisions directly in a replayed Workflow definition. Put them in Activities and record their outputs.

Local development can begin with the Temporal CLI development server. Production requires Temporal Cloud or a properly operated self-hosted Temporal Service. Production worker guidance recommends separate task queues for distinct workloads and at least two workers per shared always-on queue, on separate hosts, when high availability is required.

Official references:
- https://docs.temporal.io/develop/python
- https://docs.temporal.io/workflows
- https://docs.temporal.io/tasks
- https://docs.temporal.io/activities
- https://docs.temporal.io/workflow-definition
- https://docs.temporal.io/production-deployment
- https://docs.temporal.io/best-practices/worker

### 3.2 Agent reasoning/orchestration — Microsoft Agent Framework

**Recommended initial agent framework candidate.**

As of the 8 July 2026 announcement, the Python `agent-framework-orchestrations` package reached 1.0. Its stable orchestration patterns include:
- Sequential.
- Concurrent.
- Group chat.
- Handoff.
- Magentic (manager-led dynamic collaboration).

The framework provides lower-level workflow executors/edges/events as well as higher-level orchestration builders. Python provider documentation lists OpenAI, Azure OpenAI, Microsoft Foundry, Anthropic, Ollama, Amazon Bedrock, Google Gemini, Mistral and other integrations. Provider capabilities are not identical; tool support, structured output and hosted capabilities vary by provider.

Recommended use:
- Define a specialist agent with a constrained role and structured output.
- Run independent source-research agents concurrently.
- Run an explicit sequential review pipeline.
- Use handoff only where a specialist legitimately owns the next step.
- Use Magentic only for bounded, open-ended research where dynamic replanning adds value.

Important caveat: Microsoft documentation says Magentic's behaviour outside the original Magentic-One design is not fully tested. Do not make it the unrestricted root controller for every production operation. Set explicit maximum rounds, task count, spend, tool permissions, deadline and stop conditions.

Official references:
- https://devblogs.microsoft.com/agent-framework/agent-frameworks-orchestration-patterns-reach-1-0/
- https://learn.microsoft.com/en-us/agent-framework/overview/
- https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/
- https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/magentic
- https://learn.microsoft.com/en-us/agent-framework/agents/providers/
- https://github.com/microsoft/agent-framework/tree/main/python/samples

### 3.3 OpenAI Agents SDK — supported alternative, not a second default framework

The OpenAI Agents SDK offers agent definitions, tools, handoffs, sessions, guardrails, human approval interruptions, tracing and tests. Its current Python session documentation lists SQLite, Redis, SQLAlchemy, MongoDB, Dapr and encrypted-session options. Tool guardrails can validate/block calls; approvals can pause runs and resume from serialized run state.

Use it as an alternative when the project chooses an OpenAI-native runtime for a given agent family or needs the SDK-specific sandbox/session/trace features. Do not run both this SDK and Microsoft Agent Framework as two parallel orchestration systems by default.

Official references:
- https://openai.github.io/openai-agents-python/agents/
- https://openai.github.io/openai-agents-python/multi_agent/
- https://openai.github.io/openai-agents-python/guardrails/
- https://openai.github.io/openai-agents-python/human_in_the_loop/
- https://openai.github.io/openai-agents-python/sessions/
- https://openai.github.io/openai-agents-python/tracing/
- https://openai.github.io/openai-agents-python/testing/

### 3.4 LiteLLM — optional model gateway

LiteLLM can provide a unified gateway with deployment routing, load balancing, retries/fallbacks, per-key/team/user rate limits and budgets. Budget reservation can account for concurrent usage before a provider call. This is useful when several agent roles use different model providers.

Recommendation:
- First implement a small internal `ModelGateway` interface and provider contract tests.
- Do not make LiteLLM mandatory for the first local prototype.
- Add LiteLLM only when central provider routing, budgets or operational policy become a real requirement.
- Ensure there is one clearly owned retry/fallback policy; avoid nested retry loops across workflow, gateway and provider SDK.

Official references:
- https://docs.litellm.ai/docs/proxy/architecture
- https://docs.litellm.ai/docs/proxy/users
- https://docs.litellm.ai/docs/router/learn/reliability
- https://docs.litellm.ai/docs/routing

### 3.5 Execution and compute tools

- Docker/Podman isolated containers: first code-execution sandbox.
- Existing Python scripts and tests: reused by experiment workers.
- GitHub branch/commit/pull-request APIs: controlled code contribution path.
- Ray: consider only if CPU/GPU experiment workloads require distributed scheduling beyond separate worker queues. Ray retries and task/actor failure behaviour must be configured deliberately.
- PostgreSQL: candidate for agent registry, permissions, approvals, task metadata and operational records when concurrent multi-worker state requires transactions. Keep large experiment outputs in existing Parquet/artifact storage.
- Redis: optional cache/short-lived coordination only after a measured need; not the sole durable task record.
- Kafka/NATS/Aeron: not required for initial agent orchestration. Temporal task queues and typed APIs are sufficient initially.

References:
- https://docs.ray.io/en/latest/ray-core/tasks.html
- https://docs.ray.io/en/latest/ray-core/actors.html
- https://docs.temporal.io/production-deployment

### 3.6 Framework decision matrix

| Requirement | Temporal | Microsoft Agent Framework | OpenAI Agents SDK | LiteLLM |
|---|---|---|---|---|
| Durable long-running workflows | Primary strength | Workflow/checkpoint features; not the selected system-wide durability backbone | Run-state/session persistence; not the selected global workflow engine | Not its role |
| Specialist agent reasoning | Calls agent activities | Primary strength | Primary strength | Routes model calls |
| Concurrent agent collaboration | Via child workflows/activities | Built-in concurrent workflow | Code/agent orchestration patterns | Not its role |
| Dynamic manager delegation | Implement as bounded activity | Magentic pattern | LLM orchestration/handoffs | Not its role |
| Pause/resume/retry | Durable workflow history, signals and activity retry | Workflow checkpoints/HITL capabilities | Run state/approval interruptions | Provider-call retry/fallback only |
| Provider breadth | Not an LLM framework | Broad documented provider set | Provider integrations; evaluate current provider support | Broad model gateway |
| Recommended role | System workflow backbone | Initial specialist-agent framework | Alternative for selected agent family | Optional later gateway |

**Final selection:** Temporal + Microsoft Agent Framework, with an internal model-provider interface. OpenAI Agents SDK remains an alternative, not a parallel default. LiteLLM is optional.

---

## 4. Target system architecture

Separate the architecture into three planes.

### A. Control plane

Owns:
- Agent registry and agent identities.
- Task creation, classification and assignment.
- Workflow graphs, schedules, dependencies and deadlines.
- Tool policy and permission evaluation.
- Model/provider selection, cost limits and concurrency limits.
- Human approvals, pause/cancel/kill-switch.
- Agent run metadata, audit events and final status.
- D0–D4 backlog linkage and task priority.

Main services:
- Agent API.
- Research Director / Planner.
- Temporal service and workflow definitions.
- Agent Registry / Policy Service.
- Scheduler / Event Router.
- Model Gateway adapter.
- Approval API.

### B. Worker/execution plane

Run isolated worker pools:
- `research-literature`: papers, documentation, prior art.
- `research-data`: data contracts, source quality, point-in-time validation.
- `quant-research`: algorithms, statistical analysis and model hypotheses.
- `experiment-cpu`: backtesting, feature benchmarks and CPU experiments.
- `model-training-gpu`: model training only when approved and resources exist.
- `engineering-sandbox`: code analysis, isolated edits, tests and pull-request preparation.
- `review-security`: independent review, prompt-injection and permission tests.
- `market-monitor`: read-only feed/service health and event-trigger generation.

Each queue gets a dedicated concurrency, timeout, retry and priority policy. A slow model-training job must not starve research-review tasks. A live market monitor must not wait behind a long literature task.

### C. Evidence and data plane

Use each store for one clear purpose:
- Temporal event history: workflow progress and recovery.
- Relational application database: agent registry, task records, approvals, budgets, permissions, run summaries and audit references.
- Existing Parquet/CSV artifacts: financial datasets, experiment outputs and reproducible analysis.
- Git: source code, versioned prompts/configuration, approved research documents and change history.
- Artifact storage: large logs, datasets, reports, test evidence and code execution outputs.
- Curated knowledge index: searchable summaries/metadata for accepted research; source documents remain authoritative.

Agent conversation memory is not the system of record. It must never silently override code, data, experiment results, approved decisions or security policy.

### Logical flow

```text
Event / schedule / user objective
             |
             v
Agent API -> Policy check -> Temporal Workflow
                              |
                              v
                      Planner activity
                              |
                     bounded task plan
                              |
                dependency + budget checks
                              |
                 parallel/sequential queues
                              |
                  specialist agent workers
                              |
                     evidence artifacts
                              |
                 independent reviewer(s)
                              |
                  deterministic validators
                              |
             +----------------+----------------+
             |                |                |
          ACCEPTED          REVISE           BLOCKED
             |                |                |
       publish result     bounded retry     dependency event
             |
      update research ledger / Git PR / dashboard
```

---

## 5. Agent organisation: start with eight roles, not 25

Do not create dozens of independent agents before validating the workflow. Begin with eight role contracts. A role can have several worker replicas; a replica is not a new agent identity.

| Initial role | Responsibility | Allowed outputs |
|---|---|---|
| 1. Research Director | Clarify objective, decompose tasks, assign approved specialists, track completion | Task plan, dependencies, stop/continue decision |
| 2. Literature & OSS Scout | Search papers, official docs, repositories and licences | Source dossier, prior-art map, reuse recommendations |
| 3. Data & Point-in-Time Auditor | Check source eligibility, timestamps, instrument mapping and leakage | Data-quality report, blockers, acceptance evidence |
| 4. Quant/Algorithm Researcher | Propose algorithms, derive features, build baselines and falsifiable hypotheses | Technical design, pseudocode, benchmark plan |
| 5. Experiment Operator | Execute approved scripts/backtests in controlled datasets and compute environments | Experiment run IDs, metrics, logs and artifact references |
| 6. Engineering Agent | Inspect repository, make scoped changes in an isolated branch and run tests | Diff, tests, PR; never direct main-branch modification |
| 7. Independent Critic/Evaluator | Challenge methodology, inspect evidence, rerun/recalculate where possible | Review verdict, defects, reproducibility result |
| 8. Security/Risk Guardian | Enforce tool and data permissions, review risky operations and monitor policy events | Allow/deny/escalate decision and audit evidence |

Later role families can be split into technical-analysis, microstructure, fundamentals, news/macro, philosophy ontology, mandate, model architecture and performance-engineering specialists.

### Role contract requirements

Every registered agent must have:
- Stable `agent_id` and versioned role definition.
- Single clear domain objective and explicit non-objectives.
- Approved model/provider set and model capability requirements.
- Allowed tools, data scopes and network destinations.
- Input and output JSON schemas.
- Maximum reasoning turns and delegated subtasks.
- Token/cost budget, wall-clock timeout and concurrency cap.
- Required citations/evidence and confidence/uncertainty reporting.
- Stop conditions and escalation conditions.
- Evaluation suite and versioned prompt/configuration.
- Owner, last review date and active/disabled state.

A role prompt is not an access-control system. Permissions must be enforced by APIs, sandbox and policy service.

---

## 6. Task contracts and lifecycle

### 6.1 Standard task envelope

Each task should be a typed, versioned record with at least:

| Field | Purpose |
|---|---|
| `task_id` | Unique immutable task ID |
| `parent_task_id` | Delegation lineage |
| `project_id` / `d_code` | MPFM project and D0–D4 linkage |
| `objective` | One measurable task outcome |
| `scope` / `non_goals` | Prevent scope drift |
| `agent_role` / `agent_version` | Assigned worker identity and configuration |
| `input_refs` | Versioned documents, code, datasets or event references |
| `allowed_tools` | Policy-approved capabilities |
| `data_entitlements` | Explicitly permitted sources and usage |
| `acceptance_criteria` | Testable definition of done |
| `dependency_ids` | Required prior tasks |
| `idempotency_key` | Prevent duplicate side effects |
| `deadline` / `timeout` | Bound task lifetime |
| `budget` | Model tokens, spend, compute and tool-call limits |
| `risk_tier` | Research/read-only/code-write/deploy/financial action |
| `status` | Current lifecycle state |
| `result_refs` | Immutable output evidence references |

### 6.2 Task state machine

```text
CREATED
  -> TRIAGED
  -> PLANNED
  -> POLICY_CHECKED
  -> QUEUED
  -> RUNNING
  -> VALIDATING
  -> ACCEPTED

Alternative terminal or waiting states:
REJECTED
BLOCKED
AWAITING_APPROVAL
CANCELLED
TIMED_OUT
FAILED
SUPERSEDED
```

A task is not accepted because an agent says “done”. Acceptance requires its specified validator: tests, source verification, experiment rerun, review or approval.

### 6.3 Delegation rules

- A task may be decomposed only within a configured maximum depth, fan-out and total budget.
- Each child task receives only the data and tools needed for that subtask.
- Child agents do not inherit the parent's credentials or permissions.
- Agents cannot create unbounded children or recursively delegate the same objective.
- Duplicate objectives are detected by task fingerprint and active-task index.
- A parent can cancel child workflows and revoke their short-lived credentials.
- Conflicting findings remain separate until a reviewer resolves them; do not overwrite one result with a majority vote.

---

## 7. Core autonomous workflows to implement

### Workflow A — Research question to validated report

1. User or schedule creates a research objective.
2. Director produces a structured plan and explicit acceptance criteria.
3. Policy service checks scope, tools, data permissions, cost and maximum fan-out.
4. Literature/OSS, data and baseline agents work independently where dependencies permit.
5. Director consolidates evidence references and identifies unresolved questions.
6. Quant researcher proposes falsifiable experiments and baseline comparisons.
7. Experiment operator runs only approved jobs against versioned datasets.
8. Independent Critic checks methods, code, metrics and leakage controls.
9. Deterministic validator checks required evidence and reproducibility.
10. Approved output is published as a research artifact/PR; research log is updated.

### Workflow B — Open-source reuse assessment

1. Scout finds candidate repositories and exact commits.
2. Licence agent records the exact licence, transitive dependencies and separate model/data terms.
3. Architecture agent maps required capability to current Finance AI contracts.
4. Engineering agent proposes adapter boundaries and a minimal integration spike.
5. Critic compares behaviour and tests against upstream source.
6. Security guardian checks dependency, secret, network and code-execution risks.
7. A human approves dependency additions or licence-sensitive adoption.

### Workflow C — Autonomous engineering contribution

1. Task selects one narrowly scoped issue.
2. Engineering agent creates an isolated branch/worktree.
3. Agent receives a read-only repository snapshot plus an explicit write scope.
4. Code execution occurs in an ephemeral container without production secrets.
5. Tests, type checks, lint and security scans execute.
6. Independent code reviewer inspects diff and test evidence.
7. Agent opens a pull request.
8. Human or protected branch policy controls merge.
9. CI reruns tests against the actual PR commit.

### Workflow D — Model experiment / baseline improvement

1. Researcher writes hypothesis, target, horizon and dataset contract.
2. Data auditor validates point-in-time eligibility and split correctness.
3. Experiment operator executes pre-registered run.
4. Evaluator verifies metrics and checks no test-set feedback.
5. Cost-aware evaluator compares prediction quality and strategy outcomes separately.
6. Registry retains candidate status; no automatic promotion based only on novelty or agent recommendation.
7. Negative findings are recorded.

### Workflow E — 24/7 operational monitoring

- Always-on non-LLM monitors detect feed gaps, stale data, worker health, scheduler delays, task queue backlog, failed jobs, resource saturation and model/data drift.
- Event router raises a structured event.
- Policy rules decide whether the event warrants an agent workflow.
- Agent investigates only the permitted scope.
- If critical services or credentials are affected, deterministic circuit breakers and human escalation take precedence over LLM reasoning.
- Recovery actions are idempotent, bounded and audited.

---

## 8. 24/7 scheduling: continuous does not mean constant LLM calls

Use three activation patterns.

### 8.1 Continuous deterministic services

Run continuously:
- Worker processes.
- Temporal service.
- Task/queue health monitor.
- Market-data quality and freshness monitor.
- System health and resource monitor.
- Security/audit event collector.

These are ordinary deterministic services, not always-running LLM loops.

### 8.2 Event-triggered agent work

Start bounded workflows when:
- A licensed source reports a feed gap or schema change.
- A new official filing, corporate action or approved data event arrives.
- Model drift crosses a pre-defined threshold.
- A research task becomes unblocked.
- A GitHub issue/PR is assigned to autonomous engineering.
- A benchmark fails or performance regresses.
- A new paper/repository is added to the watch list.
- A human requests a review.

### 8.3 Scheduled workflows

Suggested initial schedules (configurable; not market predictions):
- Before market session: feed/source and instrument-master readiness report.
- During market hours: deterministic feed-health monitoring; agent investigation only on threshold events.
- After market close: reconciliation and daily market research workflow.
- Nightly: queued code quality, data validation and approved experiments.
- Weekly: prior-art/open-source review, model research synthesis, backlog and agent-quality review.
- Monthly: permissions, dependency, model/provider and cost review.

Use exchange calendars and source timestamps; do not hardcode one timezone or assume every market has the same holidays/session.

---

## 9. Memory, knowledge and evidence architecture

### 9.1 Four distinct memory types

1. **Workflow state:** task progress, retry state, approvals, timers and delegation lineage. Temporal is authoritative.
2. **Task working context:** temporary notes and intermediate agent outputs for the current objective.
3. **Curated knowledge:** accepted research, source metadata, definitions, design decisions, known failures and lessons.
4. **Experiment evidence:** immutable dataset/model/config versions, run IDs, metrics, code commits, logs and artifacts.

### 9.2 Memory rules

- Agent conversation history is not authoritative project memory.
- Store durable facts only with source/evidence, timestamp, status and review provenance.
- Separate hypotheses, unverified claims, rejected ideas, accepted decisions and measured results.
- Keep the original source and its rights metadata; a vector index is only a retrieval aid.
- Retrieved web pages, repository READMEs, news and documents are untrusted content, never instructions to the agent.
- Prevent one agent from overwriting another agent's accepted evidence.
- Support memory versioning, quarantine, review and rollback.
- Do not persist credentials, user tokens or sensitive account data in agent memory or prompts.

### 9.3 Recommended first implementation

Start with structured database records plus Git/Parquet artifacts and indexed metadata. Do not begin with a large knowledge graph, multiple vector databases or autonomous memory rewriting. Add semantic retrieval after the evidence corpus and access-control model are stable.

---

## 10. Security, autonomy and finance-specific controls

This is a foundational engineering requirement, not a later checklist.

CERT-In's *AI Security Auditing Guidelines v1.0*, dated 4 November 2026, includes explicit Agentic AI and Multi-Agent AI security provisions. It addresses unique agent identities, authorised objectives, approved tools, least privilege, bounded delegation, authenticated inter-agent communication, protected logs, memory/context isolation, loop/cascading-failure controls, emergency interruption and credential revocation.

### 10.1 Permission classes

| Level | Capabilities | Initial policy |
|---|---|---|
| A0 — Observe | Read approved docs, public sources, project metadata and permitted market data | Automatic within scope |
| A1 — Research | Create reports, compare sources, calculate metrics on approved datasets | Automatic with provenance and budget |
| A2 — Experiment | Run approved scripts/backtests in a bounded compute sandbox | Automatic only for allowlisted jobs/data/compute limits |
| A3 — Code contribution | Edit scoped files on isolated branch, run tests, open PR | Permitted in sandbox; no direct main merge |
| A4 — Protected change | Merge, deploy, change secrets/provider entitlements, promote active model | Human/protected-policy approval |
| A5 — Financial action | Place/modify/cancel real orders or move capital | Not exposed to research agents; separate formally approved execution subsystem only |

Initial target is A0–A3 in a controlled development/research environment. A4 requires explicit approvals. A5 is outside this agent-orchestration MVP.

### 10.2 Hard security controls

- Unique machine identity per agent role/worker; no shared universal credentials.
- Short-lived scoped tokens with explicit expiry and revocation.
- Tool allowlist enforced outside the LLM.
- Separate read-only source tools from write-capable engineering tools.
- Network egress allowlist for sandboxes; block metadata services and arbitrary internal network access.
- Ephemeral isolated containers for code execution; no production credentials mounted.
- Read-only main branch; branch-scoped writes and PR-only output.
- File path allowlists and output-size limits.
- No shell tool for research agents unless a specific sandboxed tool is approved.
- External retrieved content is untrusted; defend against indirect prompt injection.
- Tool arguments and outputs validated against schemas and policy.
- Inter-agent messages authenticated and validated; child agents never inherit caller privileges.
- Prevent recursive delegation, task storms, retry storms and resource exhaustion.
- Immutable or tamper-evident audit trail for decisions, delegations, tool use, approvals and external side effects.
- Agent-specific and workflow-wide kill switch.
- Credential revocation, worker quarantine, rollback and safe restart controls.
- Secrets handled only through an approved secrets manager/runtime injection, never in prompts or source code.
- Dataset/model/dependency provenance and integrity hashes.
- Separate development, test, research and production credentials/environments.

### 10.3 Prompt-injection boundary

The system will ingest web pages, market news, filings, repository issues, source code and third-party documents. Any such content can contain malicious or misleading instructions.

Controls:
- Tool outputs are typed data, not policy.
- Higher-priority instructions and permissions are enforced outside the model.
- Retrieved source text is wrapped/labeled as untrusted evidence.
- A web/research agent cannot turn a source instruction into a shell command or secret request.
- A code agent cannot access secrets merely because a repository file requests them.
- Sensitive actions are validated and approved by a separate policy component.

### 10.4 India-specific security evidence

CERT-In AI Security Auditing Guidelines v1.0 (4 November 2026) specifically require documented agent identity/objectives/tools/limits, least privilege, appropriate approval gates, reconstructable execution logs, emergency interruption and credential revocation for agentic systems. Multi-agent controls include authenticated communication, bounded delegation, memory isolation, loop/cascading-failure tests and emergency suspension.

Source:
https://www.cert-in.org.in/Downloader?fileName=CIGU-2026-0004.pdf&pageid=6&type=2

Also review:
- OWASP Top 10 for Agentic Applications 2026: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- OWASP GenAI LLM Top 10 2026: https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/

These references inform engineering controls; applicability and any formal compliance conclusion must be assessed by competent security/legal professionals.

---

## 11. Model routing, costs and resource scheduling

### 11.1 Model tier by task

| Work type | Appropriate model class | Reason |
|---|---|---|
| Task classification, metadata extraction | Small/low-cost model or deterministic rules | High volume, bounded output |
| Literature synthesis and open-ended research | Strong reasoning model | Source comparison and multi-hop reasoning |
| Code writing/refactoring | Coding-capable model in isolated sandbox | Tool use and repository context |
| Independent code/research review | Separate reviewer model/configuration | Reduce self-review and correlated error |
| Quantitative computation | Python/C++/Rust deterministic code | Numerical correctness and reproducibility |
| Live tick feature calculation | Compiled/deterministic feature engine | LLMs are not suitable for per-event hot paths |

Use a provider-neutral `ModelGateway` contract with:
- Provider/model/version.
- Task category and required capability.
- Maximum input/output tokens.
- Hard budget and rate limit.
- Timeout and cancellation.
- Retry/fallback policy.
- Structured output schema.
- Data sensitivity classification.
- Logged latency, cost and usage.

Provider capabilities differ. For example, the Microsoft Agent Framework provider matrix documents that Ollama supports function tools but not all hosted tools available through OpenAI/Foundry. Test structured output, tool calling, cancellation, context size and error behaviour per model/provider instead of assuming interchangeability.

### 11.2 Budget hierarchy

Set limits at:
- Global daily/monthly platform budget.
- Department/queue budget.
- Agent-role budget.
- Task budget.
- Individual model-call token cap.
- CPU/GPU runtime and memory limits.
- Maximum parallel tasks and spawned children.
- Maximum retries and total workflow duration.

Every task should reserve budget before starting expensive work and reconcile the reserved amount against actual usage. Stop or downgrade work when the limit is reached; do not let retries bypass a budget.

### 11.3 Queue isolation

Initial queue names:
- `agent-planning`
- `agent-research`
- `agent-review`
- `agent-data-quality`
- `agent-experiment-cpu`
- `agent-model-training`
- `agent-engineering-sandbox`
- `agent-market-monitor`

Do not start Kafka, NATS, Aeron, Ray, Kubernetes and several databases together. Begin with Temporal task queues, a local development environment and bounded worker processes. Add distributed compute/storage only when a measured workload requires it.

---

## 12. Agent quality and system acceptance metrics

Agent count and conversation volume are not success measures.

### 12.1 Task quality

- Objective completion rate.
- Acceptance rate after independent review.
- Rework and rejection rate.
- Source correctness and citation coverage.
- Unsupported-claim rate.
- Experiment reproducibility.
- Code test pass rate and escaped defect rate.
- Mean time to resolve a blocked task.
- Duplicate-task rate and duplicate side-effect rate.

### 12.2 Runtime quality

- Workflow completion/failure/timeout rate.
- Recovery success after worker restart.
- Queue wait and execution duration.
- Activity retry count and retry exhaustion.
- Worker crash/restart frequency.
- Cancellation and kill-switch effectiveness.
- p50/p95/p99 task durations by workload class.
- Provider/model errors, token use, cost and rate-limit incidents.
- Resource saturation and GPU hours.

### 12.3 Research quality

- Percentage of findings linked to primary sources.
- Percentage of claims with dates/version/provenance.
- Percentage of experiments using approved point-in-time datasets.
- Leakage-test pass rate.
- Reproduction rate by independent evaluator.
- Number of hypotheses rejected with evidence (not a negative KPI).
- Improvement over strong baselines on untouched out-of-sample periods.
- Incremental value after transaction costs, when strategy evaluation is relevant.

### 12.4 Required failure-injection tests

1. Kill a worker halfway through an LLM/research task; task resumes from durable state without losing accepted evidence.
2. Re-deliver an Activity/task; idempotency prevents duplicate issue, commit, report or experiment side effect.
3. Make a provider time out repeatedly; retries are bounded and the task enters a controlled failure/escalation state.
4. Exhaust the task/model/department budget; no alternate retry path exceeds the limit.
5. Inject a malicious instruction into a web page/repository README; it cannot change tool permissions or request secrets.
6. Attempt child-agent privilege escalation; policy denies it.
7. Create recursive delegation; maximum depth/fan-out controls stop it.
8. Create conflicting research outputs; both remain traceable until review.
9. Trigger emergency pause; active child workflows cancel and write-capable tools are disabled.
10. Restart the orchestration service; persisted workflow/task state remains recoverable.
11. Run a code agent against a malicious repository; sandbox isolation prevents access to secrets/internal services.
12. Attempt an unauthorized model promotion or financial action; no protected tool exists for the agent or the policy layer denies it.

---

## 13. Implementation sequence

This is the proposed autonomous-system build sequence. It is an additive subsystem and must not bypass the MPFM D0 → D4 dependencies.

### A0 — Architecture and contract freeze

Deliver:
- Agent charter and initial eight role definitions.
- Task/result JSON schemas.
- Tool permission matrix.
- Risk-tier and autonomy-level matrix.
- Temporal workflow definitions at design level.
- Evidence, memory and audit data model.
- Threat model and prompt-injection scenarios.
- Cost and compute budget policy.
- Open-source licence/provider review.

Exit gate: a human can understand every agent's objective, tools, data scope, budget, output and maximum actions.

### A1 — One durable research workflow (no autonomous coding)

Build one vertical slice:
- Start a research task through an API/CLI.
- Temporal creates a durable workflow.
- Planner creates a bounded plan.
- Two or three read-only specialist agents run independent source research.
- Outputs are structured and carry evidence URLs/source timestamps.
- Critic validates citations, claims and missing evidence.
- Workflow stores report and audit trail.
- Worker restart/resume and cancellation tests pass.

This validates the orchestration substrate before adding a large number of agents.

### A2 — Multi-agent task graph and evidence registry

Add:
- Concurrent and sequential subtask patterns.
- Parent/child dependency tracking.
- Typed result contracts and provenance.
- Accepted/rejected/uncertain evidence states.
- Bounded manager-led replanning.
- Duplicate-work detection.
- Research log and GitHub artifact publishing through a controlled adapter.

Exit gate: two independent agents can research the same scoped topic, while the evaluator can reconcile their evidence and identify disagreements.

### A3 — Durable 24/7 scheduling and operations

Add:
- Event-driven workflow triggers.
- Exchange-calendar-aware schedules.
- Queue priorities and per-queue worker policies.
- Retry/backoff, timeout, heartbeat and cancellation.
- Worker health, queue backlog and provider monitoring.
- Dashboard for agent/task state.
- Global pause and per-agent disable.
- Model/token/compute budgets.

Exit gate: a scheduled job and event-triggered job survive worker/service interruption and do not create duplicate side effects.

### A4 — Sandboxed engineering agent

Add:
- Read-only repository inspection.
- Isolated branch/worktree.
- Container execution with explicit file/network scope.
- Unit/integration/lint/security test runner.
- Independent code review agent.
- PR creation only.
- CI verification on PR commit.
- Human-controlled merge.

Exit gate: malicious or incorrect code changes cannot reach protected branches or deployment without approval.

### A5 — MPFM research operations integration

Connect agents to approved existing tools:
- Existing data-quality and pipeline status.
- Feature/dataset manifests.
- Baseline model and walk-forward workflows.
- Experiment registry and model registry read operations.
- Research backlog D0–D4.
- Documentation and Research Log updates.

Agents can propose and run only approved experiments. Candidate models remain candidates; model promotion retains existing gate semantics.

Exit gate: every agent-initiated experiment has a reproducible dataset, code, configuration, model and result lineage.

### A6 — Production resilience and controlled scale

Only after A1–A5:
- Operate a production-grade Temporal service (managed or self-hosted).
- Run redundant workers on separate failure domains for always-on queues.
- Back up databases and artifacts; rehearse restoration.
- Add secrets manager, signed artifacts and SBOM/AI-BOM where applicable.
- Add central traces, metrics, logs and alerts.
- Load test under realistic concurrency/provider limits.
- Review security, data rights and operational runbooks.
- Conduct scheduled kill-switch, credential-revocation and rollback drills.

Do not label the platform 24/7 production-ready merely because a local development worker stays running.

---

## 14. Proposed repository structure

Add a clean subsystem without moving existing research modules:

```text
src/
  agents/
    domain/
      task.py
      agent.py
      evidence.py
      policy.py
      result.py
    registry/
      definitions.py
      loader.py
    orchestration/
      temporal_client.py
      workflows/
        research_workflow.py
        engineering_workflow.py
        experiment_workflow.py
        scheduled_workflow.py
      activities/
        agent_activity.py
        evidence_activity.py
        github_activity.py
        experiment_activity.py
    framework/
      base_agent.py
      microsoft_agent_framework.py
      model_gateway.py
      structured_outputs.py
    policies/
      permissions.py
      budgets.py
      network_allowlist.py
      approval.py
    tools/
      research_read.py
      repository_read.py
      dataset_read.py
      experiment_run.py
      github_pr.py
    memory/
      task_context.py
      evidence_index.py
      accepted_knowledge.py
    observability/
      telemetry.py
      audit.py
      metrics.py
  agent_workers/
    research_worker.py
    review_worker.py
    experiment_worker.py
    engineering_worker.py
    monitoring_worker.py

config/
  agents/
    roles.yaml
    model_routes.yaml
    tool_policies.yaml
    schedules.yaml
    budgets.yaml

tests/
  agents/
    unit/
    workflow/
    security/
    fault_injection/
    evaluations/

docs/
  research/
    MPFM_AUTONOMOUS_MULTI_AGENT_EXECUTION_BLUEPRINT.md
```

This is a proposed target tree. Do not create every file before the first vertical slice is proven. Start with the smallest files required by A0/A1 and expand by tested need.

### Proposed APIs

- `POST /api/agents/tasks` — submit a scoped task.
- `GET /api/agents/tasks/{task_id}` — read lifecycle/status.
- `POST /api/agents/tasks/{task_id}/cancel` — request cancellation.
- `POST /api/agents/tasks/{task_id}/approval` — record an authorised approval/rejection.
- `GET /api/agents/registry` — read enabled agent roles.
- `GET /api/agents/runs/{run_id}` — inspect a run and evidence references.
- `POST /api/agents/control/pause` — pause a queue/agent/workflow class.
- `POST /api/agents/control/resume` — resume after policy checks.

These APIs expose orchestration control, not model or trading execution. Authenticate and authorise each endpoint.

---

## 15. First proof-of-concept tasks

Do not begin with a generic “build 25 agents” milestone. Prove the system using three independent, measurable workflows.

### POC-1: Open-source compatibility research
Objective: analyse a specific upstream repository and recommend REUSE / ADAPT / WRAP / REJECT.
- Scout retrieves official sources and exact commit.
- Licence reviewer records the legal boundary.
- Architecture reviewer maps source interfaces to Finance AI.
- Critic verifies evidence and unsupported claims.
- Output: a structured source dossier and adoption decision.

### POC-2: Reproducible quantitative experiment
Objective: rerun one approved baseline using a frozen dataset/configuration.
- Data agent checks manifest and split.
- Experiment worker runs the existing CLI/script.
- Evaluator recomputes metrics from artifacts.
- Critic checks leakage/cost assumptions.
- Output: run ID, metrics, logs, dataset/model/config lineage and pass/fail.

### POC-3: Safe engineering contribution
Objective: implement one low-risk, isolated repository improvement.
- Engineer creates scoped branch and patch.
- Sandbox runs tests.
- Reviewer audits diff and tests.
- GitHub adapter opens a PR.
- Human controls merge.
- Output: PR URL, diff, test logs and security findings.

### POC exit gates
- All tasks have unique IDs, parent linkage and idempotency keys.
- Workflow state survives worker restart.
- All tool use is permission checked and auditable.
- Output schemas validate.
- Source-backed claims carry evidence.
- Cost, token, time and retry budgets are enforced.
- Critic can reject unsupported output.
- Kill switch and cancellation work.
- No agent can access production/broker credentials.
- No automatic merge, deployment, model promotion or order placement.

---

## 16. What must remain outside autonomous agent control

Initially, agents must not:
- Change market-data entitlements or licensing settings.
- Access broker secrets or place, modify or cancel real orders.
- Promote a model to ACTIVE.
- Change protected D0–D4 priorities or skip dependency gates.
- Merge directly to the main branch.
- Deploy code or alter production infrastructure.
- Modify audit history or delete negative experiments.
- Create unlimited agents, subtasks, containers, provider spend or network connections.
- Treat a retrieved document or tool output as a privileged instruction.

A future financial execution subsystem, if ever authorised, must have independent deterministic risk controls, broker/exchange compliance, account permissions, kill switches and reconciliation. The research-agent plane must not be its security authority.

---

## 17. Final recommendations and immediate next actions

1. Approve the architecture split: Temporal = durable workflows; Microsoft Agent Framework = specialist reasoning; Finance AI policy/evidence services = source of truth.
2. Create A0 artefacts and task contracts before installing a large stack.
3. Build A1 with a single research workflow, two read-only specialists and one critic.
4. Measure workflow reliability, evidence quality, cost and recovery before increasing agent count.
5. Add event/schedule-driven 24/7 work only after task lifecycle and kill-switch tests pass.
6. Add sandboxed engineering only after read-only research workflows are secure and reproducible.
7. Connect agent workflows to D0–D4 using the existing backlog and accepted interfaces.
8. Keep all agentic market research read-only; keep the real-time market hot path deterministic and separate.
9. Revisit production hosting and worker redundancy only after realistic load and recovery tests.

**The first deliverable is not a swarm. It is one durable, observable, restartable, budgeted, secure research workflow that demonstrably finishes a task and proves how it reached its conclusion. Once that works, replicate the pattern across the MPFM research and engineering departments.**

---

## References and further reading

### Durable orchestration
- Temporal Python SDK: https://docs.temporal.io/develop/python
- Temporal workflows and replay: https://docs.temporal.io/workflows
- Temporal tasks: https://docs.temporal.io/tasks
- Temporal activities and idempotency: https://docs.temporal.io/activities
- Temporal deterministic workflow requirements: https://docs.temporal.io/workflow-definition
- Temporal production deployment: https://docs.temporal.io/production-deployment
- Temporal worker deployment/performance: https://docs.temporal.io/best-practices/worker

### Agent frameworks
- Microsoft Agent Framework orchestration 1.0 announcement (8 July 2026): https://devblogs.microsoft.com/agent-framework/agent-frameworks-orchestration-patterns-reach-1-0/
- Microsoft Agent Framework overview: https://learn.microsoft.com/en-us/agent-framework/overview/
- Orchestration patterns: https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/
- Magentic orchestration: https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/magentic
- Model providers: https://learn.microsoft.com/en-us/agent-framework/agents/providers/
- Python samples: https://github.com/microsoft/agent-framework/tree/main/python/samples
- OpenAI Agents SDK: https://openai.github.io/openai-agents-python/
- OpenAI Agents SDK handoffs/orchestration: https://openai.github.io/openai-agents-python/multi_agent/
- OpenAI Agents SDK guardrails: https://openai.github.io/openai-agents-python/guardrails/
- OpenAI Agents SDK human approval: https://openai.github.io/openai-agents-python/human_in_the_loop/
- OpenAI Agents SDK sessions: https://openai.github.io/openai-agents-python/sessions/

### Model gateway / compute
- LiteLLM gateway architecture: https://docs.litellm.ai/docs/proxy/architecture
- LiteLLM budgets: https://docs.litellm.ai/docs/proxy/users
- LiteLLM retries/fallbacks: https://docs.litellm.ai/docs/router/learn/reliability
- Ray tasks: https://docs.ray.io/en/latest/ray-core/tasks.html
- Ray actors: https://docs.ray.io/en/latest/ray-core/actors.html

### Security
- CERT-In AI Security Auditing Guidelines v1.0 (4 November 2026): https://www.cert-in.org.in/Downloader?fileName=CIGU-2026-0004.pdf&pageid=6&type=2
- OWASP Top 10 for Agentic Applications 2026: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- OWASP GenAI LLM Top 10 2026: https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/

### Existing Finance AI research
- MPFM research hub: https://github.com/rudraksha127/Finance-Ai/tree/main/docs/research
- MPFM Research Master: https://github.com/rudraksha127/Finance-Ai/blob/main/docs/research/MPFM_RESEARCH_MASTER.md
- Development Backlog: https://github.com/rudraksha127/Finance-Ai/blob/main/docs/research/DEVELOPMENT_BACKLOG.md
- Research Log: https://github.com/rudraksha127/Finance-Ai/blob/main/docs/research/RESEARCH_LOG.md
- HFT/Open-source ecosystem: https://github.com/rudraksha127/Finance-Ai/blob/main/docs/research/HFT_SYSTEMS_AND_OPEN_SOURCE_ECOSYSTEM_RESEARCH.md
- Personal trading system design: https://github.com/rudraksha127/Finance-Ai/blob/main/docs/research/FINANCE_AI_TRADING_SYSTEM_DESIGN.md


---

## 18. User-priority clarification: backend model research is the primary mission

The user's primary focus is the backend: models, algorithms, accuracy/precision/recall/F1 and the complete quantitative benchmark suite. The autonomous organisation must therefore be model-research-led. General documentation, UI work and agent conversation volume are secondary.

The detailed programme is maintained in [MPFM_MODEL_RESEARCH_AND_BENCHMARK_ROADMAP.md](MPFM_MODEL_RESEARCH_AND_BENCHMARK_ROADMAP.md). It includes a paper review through 2026-11-21, model hypotheses, benchmark metrics, baseline families and experiment IDs MBR-00 to MBR-09.

### 18.1 Dedicated model-research workstream

The Research Director should prioritise these specialist roles:

1. **Latest Paper Scout:** discover recent primary papers, conference/journal publications, preprints, code and benchmark releases; record publication date, status and exact sources.
2. **Paper Methodology Extractor:** extract dataset, universe, label/target, horizon, split, architecture, compute, metrics, result tables, limitations and code availability.
3. **Benchmark/Data Auditor:** verify point-in-time correctness, data rights, instrument universe, leakage, class distribution and split validity.
4. **Baseline Reproduction Engineer:** reproduce naive, classical ML, tree, deep temporal and foundation-model baselines under one frozen contract.
5. **Algorithm Researcher:** formulate new falsifiable hypotheses from observed limitations and prior art.
6. **Model Implementation Engineer:** implement candidate models in scoped branches; add unit, numerical parity and inference tests.
7. **Experiment Scheduler:** run bounded training/sweeps under queue, hardware, token and wall-clock budgets.
8. **Metric/Statistical Evaluator:** independently recompute metrics from prediction artifacts and run statistical/uncertainty checks.
9. **Robustness/Adversarial Reviewer:** test regime shifts, unseen instruments, missing data, class imbalance and threshold sensitivity.
10. **Performance Engineer:** profile feature computation, model inference, serialization, queueing and end-to-end latency.
11. **Model Promotion Reviewer:** decide candidate status using the predefined data, leakage, forecast, calibration, robustness, economic and runtime gates.

These are role contracts, not a requirement to host eleven separate large models. Worker replicas may implement roles while maintaining isolated permissions and outputs.

### 18.2 Required benchmark outputs

Every model experiment must report the relevant metrics, not only the metrics that make it look good:

- Classification: accuracy, balanced accuracy, per-class precision/recall/F1, macro-F1, weighted-F1, MCC, confusion matrix, ROC-AUC and PR-AUC where applicable.
- Regression/direction: MAE, RMSE, MASE, relative MAE, directional hit ratio and Rank IC/ICIR.
- Probabilistic: log loss/NLL, Brier, ECE, reliability curves, pinball loss, CRPS and interval coverage.
- Volatility/risk: QLIKE, realised-volatility error and tail-risk coverage.
- Portfolio: net return, Sharpe, Sortino, Calmar, drawdown, turnover, costs, slippage, capacity and fill metrics.
- Statistical evidence: Diebold–Mariano where appropriate, block bootstrap, multiple-testing correction, Deflated Sharpe and PBO/CPCV when applicable.
- Runtime: P50/P95/P99/P99.9, throughput, cold start, peak memory and separate model-only versus full event-to-decision latency.

The evaluator must include majority-class and zero-return/random-walk baselines. Accuracy and weighted-F1 alone are not sufficient for class-imbalanced market labels.

### 18.3 Agent-to-experiment execution contract

The agent workflow for a new model should be:

```text
Latest paper / observed weakness
             |
             v
Methodology and prior-art extraction
             |
             v
Data / target / benchmark contract audit
             |
             v
Baseline reproduction
             |
             v
Falsifiable algorithm hypothesis
             |
             v
Implementation on isolated branch
             |
             v
Frozen experiment / bounded sweep
             |
             v
Independent metric recomputation
             |
             v
Statistical + robustness + latency review
             |
             v
Candidate / Reject / Revise / More data
```

No agent may declare an algorithm better because one score increased. It must show the baseline, per-class impact, calibration, statistical uncertainty, regime coverage and economic/runtime implications relevant to the claim.

### 18.4 Immediate priority

The first model tasks are MBR-00 and MBR-01 from the model roadmap:
- Re-establish the existing Finance AI baseline from a new immutable run manifest.
- Add zero-return/random-walk and strong classical comparators.
- Produce the full classification/calibration report.
- Define a new untouched evaluation period and expand to additional instruments where licensed data permits.

Only after these tasks should the system move to advanced MPFM model hypotheses. The agreed D0 → D1 → D2 → D3 → D4 sequence and point-in-time/data-rights gates remain authoritative.
