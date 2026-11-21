# Finance AI / MPFM Research Log

This is the chronological audit trail for research findings, decisions, experiment outcomes and next actions. Append entries; do not erase negative findings.

## 2026-11-17 — Initial research consolidation on GitHub

### Scope consolidated

- Identified the existing repository as the canonical engineering source: rudraksha127/Finance-Ai.
- Read the repository README, document index, CURRENT_STATE, data-ingestion blueprint, data architecture, baseline implementation and evaluation/backtesting implementation.
- Established a separate docs/research workspace so the new MPFM research does not overwrite original MVP and post-MVP implementation reports.
- Recorded the prediction-first Finance AI objective and the distinction between Finance AI product, research platform, MPFM architecture and broker integration plane.
- Recorded the D0 → D1 → D2 → D3 → D4 sequence and the parallel ontology/licensing/baseline-research tracks.
- Kept the exact G01–G13 wording unresolved rather than inventing names not present in the repository material reviewed.

### Repository evidence recorded

- Original MVP historical source: Yahoo Finance; supported intervals documented as 1d, 1wk and 1mo. No real-time feed or live broker execution in the MVP.
- Original ingestion blueprint lists Polygon.io, Alpha Vantage WebSocket and IEX Cloud for future live feeds; NewsAPI / SEC EDGAR / RSS for news; CBOE / Yahoo options / Polygon for options; FRED / World Bank / IMF for macro; Twitter API / StockTwits / Reddit for sentiment. All are placeholders in the original blueprint, not integrated sources.
- Post-MVP repository reports document autonomous ingestion, drift detection, retraining, registry, observability, temporal LSTM, ensemble/calibration and point-in-time multimodal data.
- LSTM and ensemble candidates were not promoted. The ensemble macro-F1 regressed relative to its constituents. Static signal runs at the documented threshold generated no trades; one recorded LR walk-forward was negative versus buy-and-hold.
- No approved licensed fundamentals/news source was recorded for the multimodal implementation. Experiments A–D were deliberately not run on synthetic fixtures.

### External documentation review

Official documentation pages reviewed on 2026-11-17:

- Upstox Developer API and V3 market data / historical candle docs.
- Zerodha Kite Connect product page and V3 historical data docs.
- DhanHQ V2 live feed, historical data and market quote docs.
- Angel One SmartAPI streaming and historical API docs.
- FYERS V3 market-data and historical-data docs.
- Groww Trade API live-data and historical-candles docs.
- NSE Data Sharing & Usage Policy.

Key finding: all six broker brands in the Finance AI UI concept have official developer/API material surfaced in this review, but that does not establish that the repository has integrated them or that their account APIs grant broad redistribution rights. The market-data and broker/account planes must remain separate. Data-use permissions need written verification.

### Decisions preserved

1. Prediction remains the primary project objective.
2. Basic market prediction must be philosophy-independent; philosophy and mandate are optional context/variants, not a replacement for market forecasting.
3. D0 → D1 → D2 → D3 → D4 remains the development sequence.
4. Philosophy ontology, licensing and baseline research can proceed in parallel.
5. Multimodal learning follows a reliable point-in-time financial foundation.
6. Synthetic fixtures can test engineering semantics but cannot support real-market predictive claims.
7. Data rights, availability timestamps and negative experimental outcomes must remain visible in research records.

### Next research actions

- Formalize the target/horizon contract and experiment register.
- Map exact D0–D4 acceptance tasks from the original detailed backlog.
- Shortlist one primary licensed market-data source and one reconciliation source.
- Obtain data training, retention, display and redistribution permission evidence.
- Expand the baseline comparison to multiple instruments and regimes.
- Formalize Candidate B and FSMD, then conduct prior-art and falsifiable-experiment review.


## 2026-11-17 — Finance AI Research Planning project chat analyzed

### Source and limitations

- Analyzed the shared project-context conversation titled **Finance AI Research Planning**, shown with timestamp 2026-11-16 14:47.
- The visible user prompts explicitly requested deep research, analysis of trader/investor philosophies (Buffett, Harshad Mehta and Ravi Bhaskar), development of new algorithms/model training, and deep research into the Multi-Philosophy Foundation Model.
- The complete verbatim chat could not be opened through the available project-file search in this session. The analysis records visible prompts and decisions preserved in the shared project capsule; it does not claim line-by-line transcript completeness.

### Additional project decisions preserved

- The work originated from 13 research gaps G01–G13; exact gap definitions/status text still needs recovery.
- Work was classified as closed, requiring development, or dependent on external approval.
- Development order is D0 → D1 → D2 → D3 → D4.
- Philosophy ontology, licensing and baseline research can proceed in parallel.
- Multimodal learning is deferred until point-in-time financial foundations are reliable.
- Historical data rights / real data ingestion block valid real-market validation.
- Institutional approval and external patent/FTO specialist review are dependencies.
- Candidate B novelty, foundation-pretraining advantage and compositional generalization on actual markets remain unproven.

### Development workstreams recorded

Engineering foundation; security master; corporate-action engine; fundamental intelligence; financial feature engine; baseline engine; Financial State Encoder; philosophy and mandate intelligence; risk and decision engine; integrated MPFM experiments.

The exact workstream-to-D0–D4 mapping was not preserved in the available source excerpt, so it remains unresolved rather than guessed.

### Follow-up

- Added [FINANCE_AI_CHAT_ANALYSIS.md](FINANCE_AI_CHAT_ANALYSIS.md) with source boundary, visible prompts, preserved decisions, interpretation and missing-source checklist.
- Reconciled the chat context with the existing MPFM master, prediction research ledger and development backlog.
- Recover the original G01–G13 list and full D0–D4 task cards from the complete chat/source attachments before treating the research ledger as fully source-complete.


## 2026-11-17 — MPFM Phase 1 financial world-modeling research consolidated

### Source material and literature checked

- Incorporated the user's research notes sections 61–66 covering financial world modeling, TFWM/Market-1T, financial augmentations, multimodal fusion and mandate-conditioned representation learning.
- Verified the primary paper: Merchant et al., *Towards Financial World Modeling*, arXiv:2610.09048.
- Checked the TFWM code/results README and Market-1T data-pipeline README.
- Verified the September 2026 multimodal-finance survey, DOI 10.1016/j.inffus.2026.104249.

### Evidence clarifications

- TFWM's principal table is 15-minute cross-sectional Rank IC averaged across 32 evaluation months, not UP/DOWN accuracy or strategy returns.
- Its multihead supervised representation recorded Rank IC 0.0311 (return), 0.0941 (volatility) and 0.2455 (spread); standalone spread specialist recorded 0.2517.
- The paper reports month contributions of 97.2%, 98.9% and 99.9% of observed variation for return, volatility and spread tasks in its variance decomposition.
- Market-1T is built from consolidated U.S. NBBO quote state and SIP trade reports at one-second resolution; its 11 fields do not constitute full L2/L3 depth or participant identity.
- The TFWM README described a released sample (July 2019–December 2020, 230,025 ticker-days) and noted that complete open hosting was still being worked on at the time checked. Code MIT licensing must not be mistaken for data/weights permission.

### MPFM research decisions proposed

1. Separate state encoder, market-dynamics model and decision/execution evaluation.
2. Begin with price-taker market evolution plus a separate execution model; HFT market impact requires a separate action-conditioned branch and licensed depth/event data.
3. Test shared return/volatility representation with specialist spread/liquidity capacity.
4. Build financially constrained augmentation contracts and regime-aware contrastive-learning experiments.
5. Test hybrid reliability-gated multimodal fusion with availability-time controls.
6. Treat mandate conditioning as structured conditioning, not voting trader-personality agents; keep the base market forecast philosophy-independent.

### New research artifact

- Added [FINANCIAL_WORLD_MODELING_PHASE1.md](FINANCIAL_WORLD_MODELING_PHASE1.md) with paper results, data access caveats, architecture, augmentation/fusion/mandate designs, risks and WM-01–WM-09 experiment proposals.
- Linked it from the research index, MPFM master and prediction-model research ledger.

No MPFM experiment was run as part of this documentation update.


## 2026-11-21 — Personal multi-market trading-intelligence vision clarified

### User's clarified product intent

- Finance AI is intended as a personal system for research and testing first.
- It should monitor Indian and relevant global markets, including NSE, BSE and MCX, and combine technical analysis, fundamentals, news/announcements, derivatives information, liquidity and aggregated crowd/positioning evidence.
- Its key user-facing outcome is a disciplined trade candidate: possible entry conditions, invalidation/stop, exit conditions, risk/size constraints and an explicit no-trade result when evidence is weak.
- Multiple specialist models/strategies may run in the background, but their outputs must be calibrated, regime-aware and evaluated after realistic costs. An unstructured majority vote is not acceptable.
- The user's HFT reference is recorded, but true HFT is separated from retail/API algorithmic trading and AI-assisted decision support. Retail broker APIs and browser dashboards must not be represented as exchange-colocated HFT infrastructure.
- Crowd behaviour must be described using observable aggregate proxies (e.g. order-flow imbalance, depth, OI changes, volume profile, breadth and public participant reports), not as access to the identities or exact actions of every market participant.

### System-design document added

- Added [FINANCE_AI_TRADING_SYSTEM_DESIGN.md](FINANCE_AI_TRADING_SYSTEM_DESIGN.md).
- It specifies data access/governance, canonical market events, specialist model families, strategy/signal contracts, risk and execution controls, broker capability adapters, paper/shadow/manual/live modes, an isolated HFT feasibility lane, validation methodology and an implementation roadmap.
- This is a proposed architecture. It does not claim that any new source, model, broker integration, strategy, order execution or HFT infrastructure has been implemented or validated.

### Official source review (2026-11-21)

- SEBI's retail-algo circular is dated 2025-02-04; SEBI's 2025-09-30 implementation extension states the framework applies to all stock brokers from 2026-04-01.
- NSE's 2025-05-05 implementation standards include static-IP/API-key and operational controls; exact client/category requirements must be confirmed with the broker and current exchange rules.
- Upstox's current documentation lists NSE/BSE/MCX instruments and publishes retail order API rate limits (10 req/s for regular algos; 50 req/s for SEBI-registered algos, with additional period limits).
- Groww's current Trading API documentation states that API trading is supported for cash and F&O, while commodity/MCX API trading is not currently supported.
- NSE and MCX publish separate exchange market-data feed products and usage conditions. NSE's non-display policy explicitly covers use of market data in algorithmic trading calculations; broker API access is not assumed to confer exchange-wide data rights.
- TradingView's charting library does not supply market data; an integrator must connect an entitled data source.
- Open-source candidates recorded for due diligence: NautilusTrader, QuantConnect LEAN, FinRL/FinRL-X, FinGPT/FinNLP and TimesFM. Their suitability and licenses must be checked individually; for example, TimesFM 3.0 default weights are identified by the repository as non-commercial/non-production.
- Order-flow research includes published work on deep order-flow imbalance using granular Nasdaq limit-order-book data. Transfer to NSE/MCX is an open empirical question.

### Decisions / guardrails

1. Begin with research, backtesting, replay, paper/shadow and manual-approval workflows. Do not enable live orders merely because a model emits a signal.
2. Treat HFT as a separate feasibility track requiring tick/order-book rights, specialized connectivity/latency infrastructure, venue approvals and a demonstrated cost-adjusted edge.
3. Use exchange-agnostic internal schemas and capability-aware broker adapters; verify segment, depth, rate-limit, account and data rights per provider.
4. Separate forecast quality, strategy decision quality, execution quality, net economic performance and operational reliability.
5. Retain the existing repository's implemented status as documented; this new design does not turn the research-only FastAPI MVP into a live trading system.


## 2026-11-21 — HFT systems, market microstructure and open-source ecosystem research

### Scope reviewed

- Reviewed the complete recursive Finance-Ai main tree at SHA 88d56d6ef5f7b12c2bdaffe38618ca74cb01585 (332 entries, 280 files, no truncation).
- Inspected selected source and design areas covering historical ingestion, instrument registry, feature registry, point-in-time multimodal joins, backtest execution, walk-forward validation, API decision/orchestration, model registry, retraining, risk and current-state documentation.
- Reviewed public technology/market-making disclosures from Optiver, HRT, Jane Street, IMC, Jump Trading and Virtu.
- Inspected core README/tree/source/docs paths in NautilusTrader, HftBacktest, ABIDES, LEAN, Hummingbot and FinRL-X; reviewed Qlib and QuestDB project material.

### Repository findings preserved

- The existing repository is a Python research backend with React/Vite dashboard, not a complete low-latency trading platform.
- The MVP source path is historical Yahoo-style daily/weekly/monthly data; live Indian depth/tick feeds are not established.
- Current backtest execution is long-only, fixed one-unit, close-to-close and cost-simplified. It is not an order-book/queue/latency-aware HFT simulator.
- The current prediction API is 1d-only and refuses live mode; no broker order execution gateway is present in the inspected MVP.
- The existing point-in-time data layer, feature/dataset versioning, leakage controls, registry, drift and controlled retraining should be preserved.
- PostgreSQL is still a deferred target per the existing ADR; no database rewrite is implied.
- Public OSS and company material has been separated from proprietary firm internals and from claims about our own implementation.

### Open-source shortlist

- NautilusTrader: event-driven trading engine, risk/portfolio/execution lifecycle and backtest/live architecture reference; LGPL-3.0 needs review.
- HftBacktest: specialist market replay, L2/L3, queue, latency and fee model reference; MIT; explicitly no market impact in its replay model.
- ABIDES: agent-based, discrete-event market simulation; BSD 3-Clause; synthetic assumptions need calibration.
- LEAN: event-driven backtesting, execution and risk interfaces; Apache-2.0.
- Hummingbot: exchange connector/order executor and recovery-test patterns; Apache-2.0, primarily digital-asset venues.
- FinRL-X: modular portfolio/strategy-weight research; Apache-2.0.
- Qlib: quant research and factor/workflow reference; MIT.
- QuestDB, DuckDB/Polars/Arrow/Parquet and Kafka/NATS/Aeron are optional infrastructure candidates, not simultaneous mandatory dependencies.

### HFT firm engineering patterns inferred from public material

- Data, pricing/alpha, risk and execution are interdependent platform capabilities.
- Research infrastructure, reproducibility, model robustness and production feedback loops matter as much as model architecture.
- Low-latency networking, C++/Rust/OCaml, FPGA/ASIC and co-location are specialist choices that require a proven strategy and measured bottleneck.
- Market making is not the same as directional price prediction: pricing, spread, inventory, adverse selection and quote/execution control need distinct treatment.

### Indian market-data and compliance boundary

- NSE publicly offers L1/L2/L3/tick-by-tick products with distinct market-depth semantics and multicast/leased-line delivery.
- NSE market-data usage and redistribution are controlled by policy/subscription agreements; broker API access is not an automatic non-display or redistribution licence.
- SEBI retail algo framework and exchange/broker implementation processes must be verified before any automated order path.
- These are data-rights and operational gates, not software integration details.

### Decisions and next actions

1. Keep D0 → D1 → D2 → D3 → D4 unchanged.
2. Keep Finance AI prediction-first; do not claim HFT capability or profitability.
3. Maintain HFT as a separate research/feasibility lane.
4. Prepare a source entitlement register, canonical event schema and OSS licence/version scorecard.
5. Only after licensed depth/tick data arrives, create a bounded microstructure POC with simple baselines and explicit queue/latency/market-impact assumptions.
6. Later evaluate HftBacktest/ABIDES for research and NautilusTrader for an isolated paper execution-engine integration.
7. Preserve the distinction between source-level code review, public-firm evidence, proposed design and implemented functionality.


## 2026-11-21 — NautilusTrader compatibility and HftBacktest POC design

### Exact Finance AI interface files reopened

- `src/data/sources/base.py` and `src/data/sources/yahoo.py`: historical-only provider contract; intervals documented as 1d/1wk/1mo and records are OHLCV-style.
- `src/data/instruments.py`: current ticker identity record is minimal (ticker, active flag, optional exchange and first_seen).
- `src/backtest/signals.py`: deterministic BUY / SELL / NO_TRADE from UP/DOWN probabilities.
- `src/api/schemas.py` and `src/api/orchestrator.py`: inference API interval is 1d only; current API mode live is refused.
- `src/api/decision.py`: one-unit placeholder position size for a non-NO_TRADE signal.
- `src/backtest/execution.py`: long-only fixed quantity, close-to-close, single position and fixed bps costs.
- `docs/DECISIONS.md`, `docs/ENGINEERING_CONSTITUTION.md`, `docs/CURRENT_STATE.md`: Python-first MVP, file-backed storage, dependency constraints, prediction/decision/execution separation and current research-only state.

### NautilusTrader compatibility finding

- Current docs describe a Rust core with Python/PyO3 control and custom Python DataClient/ExecutionClient adapters.
- The custom adapter contract includes typed event publication, instrument provider/factory registration, order command outcomes, venue/client order ID correlation, order/fill/position reports and reconciliation.
- The current official adapter list reviewed has no NSE/BSE/MCX or Indian retail broker adapters.
- A custom India adapter is possible in principle but Finance AI would own data semantics, broker-specific order handling, reconciliation, tests and maintenance.
- No direct BUY → submit_order mapping is acceptable. A versioned forecast/strategy-intent contract and independent risk policy must sit between them.
- Proposed an isolated no-credentials runtime spike, canonical instrument mapping, ForecastEvent custom-data mapping and deterministic mock lifecycle tests.

### HftBacktest compatibility finding

- Current HftBacktest documentation describes an 8-field NumPy event schema with event flags, exchange timestamp, local receive timestamp, price, quantity and optional L3 order ID.
- The current Finance AI daily OHLCV contract lacks the order-book updates, event timestamps, local receive time, sequence semantics and order identifiers needed for queue/latency replay.
- HftBacktest documents risk-averse and probability-based queue progression.
- Its replay assumes the recorded market is immutable and does not simulate market impact.
- Proposed a staged HFT-POC-00 to HFT-POC-04 program: source admissibility, microstructure baselines, model comparisons, latency/queue sensitivity and strategy micro-simulation.

### Indian feed capability clarification

- NSE's public feed page describes L1 best bid/ask, L2 up to five levels, L3 up to twenty levels and tick-by-tick full-order-book data; feed delivery is multicast over dedicated leased-line connectivity.
- MCX's public feed material describes real-time L1 touchline and L2 up to five best bid/ask levels.
- Do not equate 20-level market-by-price data with order-by-order L3 IDs. Obtain the exact feed data dictionary before claiming HftBacktest L3 compatibility.
- Exchange feed permissions, non-display use and storage/training rights are separate from broker API access.

### Decision and next actions

1. Keep Finance AI research and instrument identity authoritative.
2. Do not replace the current backtest engine; keep any event-driven simulator as a separately versioned comparison.
3. Run only a no-broker-credential Nautilus compatibility spike until a separate integration decision is approved.
4. Keep HftBacktest blocked on lawful depth/tick data and timestamp/event semantics.
5. Preserve D0 → D1 → D2 → D3 → D4 sequence.
6. No new dependency, broker integration, live order capability or HFT capability is marked implemented.


## 2026-11-21 — Autonomous multi-agent orchestration deep research and execution plan

### User objective clarified

- Build an autonomous multi-agent system for Finance AI / MPFM that can research, analyse, run approved experiments, monitor work, and contribute to engineering continuously (24/7).
- Agents should have specialist expertise and bounded independent execution; they should not depend on a human to assign every small subtask.
- The system must preserve existing MPFM research integrity, D0 → D1 → D2 → D3 → D4 order, source licensing, model-promotion gates and separation of prediction from execution.

### Existing implementation boundary rechecked

- The current repository has an operations/health subsystem, autonomous data-pipeline and retraining workflows, drift detection, model registry and research pipeline.
- These are useful deterministic foundations but are not a general LLM multi-agent runtime.
- No multi-agent registry, durable LLM task orchestration, agent identity/permission service, sandboxed autonomous code worker or 24/7 agent control plane was evidenced in the inspected repository snapshot.
- This is proposed architecture only; no agent runtime or worker was implemented in this research update.

### Current framework research

- Temporal Python SDK: selected as the recommended durable workflow backbone because workflow event history supports replay/recovery; external side effects and nondeterministic work such as LLM calls, API calls, database queries and file I/O belong in Activities. Activities should be idempotent under retries. Local CLI development server is suitable for the first prototype; production requires Temporal Cloud or a properly operated self-hosted service.
- Microsoft Agent Framework: selected as the initial specialist-agent framework candidate. Its Python orchestration package reached 1.0 on 2026-07-08, with sequential, concurrent, group-chat, handoff and Magentic patterns documented as stable. Provider support includes multiple hosted and local model ecosystems, but tool/structured-output capabilities differ by provider.
- Magentic should be used only for bounded open-ended research with explicit max rounds, fan-out, budgets and stop conditions; Microsoft documentation cautions that behaviour outside the original Magentic-One design has not been fully tested.
- OpenAI Agents SDK: retained as an alternative for agents requiring its own tools, handoffs, sessions, guardrails, HITL approvals, tracing and testing; it is not selected as a second default orchestration framework.
- LiteLLM: optional future provider gateway for shared routing, budgets, rate limits and fallbacks. First create an internal ModelGateway interface; avoid nested retry loops.
- Ray, Kafka, NATS, Aeron, Kubernetes, multiple databases and vector stores are not first-phase dependencies. Add only when a measured workload needs them.

### Recommended architecture

1. Temporal owns durable workflows, timers/schedules, retry/cancellation, task queues, parent-child workflow lineage and recovery.
2. Microsoft Agent Framework supplies specialist reasoning/collaboration inside bounded activities/workflow steps.
3. Finance AI owns canonical task contracts, agent registry, tool permissions, model budgets, evidence quality, D0–D4 linkage and project truth.
4. Separate worker queues isolate research, review, data checks, experiment compute, model training, code sandbox and read-only monitoring workloads.
5. Existing MPFM pipeline, model registry, backtester, feature store/contracts and dashboard remain authoritative.
6. Workflow state, task working context, curated knowledge and experiment evidence are four distinct memory categories; agent conversation history is not the system of record.
7. Start with eight agent roles: Director, Literature/OSS Scout, Data/Point-in-Time Auditor, Quant/Algorithm Researcher, Experiment Operator, Engineering Agent, Independent Critic/Evaluator and Security/Risk Guardian.
8. Start with deterministic task graphs. Permit dynamic delegation only under maximum depth, fan-out, budget, deadline and approved-agent constraints.

### Security research

- Reviewed CERT-In AI Security Auditing Guidelines v1.0 dated 2026-11-04, especially Sections 9.7 and 9.9.
- Controls include unique identities, authorised objectives, approved tools, least privilege, action limits, human approvals for consequential actions, protected execution logs, emergency interruption, credential revocation, authenticated agent-to-agent communication, bounded delegation, memory/context isolation, recursive delegation and cascading-failure controls.
- External web pages, repository content, news and tool output are untrusted evidence, never higher-priority instructions.
- Initial autonomy is A0–A3: read-only observation/research, approved experiments and sandboxed branch/PR changes. Merge, deployment, secrets/entitlement changes, model promotion and financial actions remain protected/human-controlled.
- Research agents must have no broker credentials and no ability to place, cancel or modify live orders.
- OWASP Agentic Applications 2026 and OWASP GenAI LLM Top 10 2026 are added as ongoing security references.

### Execution programme proposed

- A0: architecture, role charters, task/result schemas, permission matrix, budgets and threat model.
- A1: one durable read-only research workflow with two or three specialist agents and an independent critic; test restart/resume, evidence and cancellation.
- A2: concurrent/sequential task graphs, provenance, duplicate-work detection and bounded dynamic delegation.
- A3: scheduled/event-triggered 24/7 workers, queue isolation, observability, budgets and kill switches.
- A4: sandboxed engineering agent with isolated branch, tests, independent review and PR-only output.
- A5: integration with existing MPFM D0–D4, dataset, backtest, model registry and research-log APIs.
- A6: production resilience, redundant workers on separate failure domains, backups, security and recovery drills, load tests and runbooks.

### Initial proof-of-concept workflows

1. Open-source compatibility/licence assessment with exact repository commit and evidence.
2. Reproducible approved quant experiment using a frozen dataset/configuration and independent metric verification.
3. Safe engineering contribution on an isolated branch, with sandbox tests and a human-controlled PR merge.

### New research artifact

- Added [MPFM_AUTONOMOUS_MULTI_AGENT_EXECUTION_BLUEPRINT.md](MPFM_AUTONOMOUS_MULTI_AGENT_EXECUTION_BLUEPRINT.md).
- Added the document to the research index.
- The blueprint contains framework comparisons, recommended three-plane architecture, eight initial agent roles, typed task lifecycle, 24/7 activation design, memory/evidence model, model routing/budgeting, CERT-In/OWASP security boundaries, failure-injection tests, proposed repository structure and A0–A6 implementation stages.

### Current decision

Build one durable, observable, restartable, budgeted and secure research workflow before creating a large agent swarm. The initial goal is proven task completion and evidence traceability, not maximum agent count or nonstop LLM activity. No agent runtime, new dependency, live feed, live execution path or production deployment is marked implemented.


## 2026-11-21 — Backend-first model research and benchmark programme

### User's clarified priority

- The primary technical focus for the autonomous research organisation is backend models, algorithm design, quantitative experiments, accuracy/precision/recall/F1 and the wider benchmark suite.
- Agents should read recent and relevant financial ML papers, reproduce their baselines, extract limitations, design better hypotheses, implement them and independently validate every result.
- The goal is a top-quality, evidence-backed backend—not more agents, more documentation or larger models for their own sake.

### Primary papers reviewed in this research pass

- FinVerse: Financial Time-Series Benchmark (arXiv:2608.03259, 4 August 2026): 116,897 financial series / 171.1M observations in the data artifact; evaluated subset 60,232 series / 17.4M observations; 43 public TSFMs; 11 metric families and 78 metrics. Its results separate point-wise, cross-sectional ranking and portfolio performance; different metrics favour different models.
- Pretrained Time-Series Foundation Models for Financial Return Forecasting (arXiv:2606.27100, 25 June 2026): compares TimesFM-2.5, Moirai-2.0, Chronos and others against neural models on five US equities. Pretrained models lead 8/10 task-level rankings, but gains over zero-return/random-walk are small and statistically significant superiority is reported only in two comparisons under the paper's one-sided Diebold–Mariano test. Asset-specific iTransformer wins demonstrate no universal pretrained-model advantage.
- Towards Financial World Modeling / TFWM (arXiv:2610.09048, 6 October 2026): Market-1T and 18 representation strategies. The supervised multihead model reports Rank IC 0.0311 return, 0.0941 volatility and 0.2455 spread; separate specialist spread model reports 0.2517. Shared representation helped return/volatility in the stated experiment but showed task spillover for spread.
- TensorLOB (arXiv:2611.02866, 2 November 2026): structure-preserving tensor architecture for LOB data. On FI-2010, reports weighted F1 of 82.5 / 72.2 / 77.4 / 79.1 at 10 / 20 / 50 / 100 event horizons. The paper uses ten trading days and three seeds; some baselines collapse to majority stationary class. Treat this as a promising preprint result requiring independent replication, not an Indian-market result.
- TailDART (arXiv:2611.09176, 6 November 2026): compact 2.68M-parameter TSFM using grouped-query attention and a Johnson SU distribution head. Reports up to 48.1% inference-latency reduction vs Lag-Llama and a 0.668 ms daily forecast step in its setup. This is model-only latency on its benchmark, not feed-to-decision latency; pretraining/data-overlap and domain-transfer limits must be checked.
- LiT: Limit Order Book Transformer (Frontiers in AI, 2025): Binance L2 top-20 book data, roughly one million LOB snapshots, structured temporal patches and transformer+LSTM. At 300 ms–1,000 ms horizon it reports precision 66.20, recall 68.34, F1 66.40 and accuracy 68.34. The paper also shows zero-shot deterioration under month-to-month distribution shift and improvement from fine-tuning; crypto results do not establish NSE transfer.
- Evaluation Integrity in ML for Finance (SSRN working paper, 20 July 2026): review/checklist covering leakage, PBO, Deflated Sharpe, purged/combinatorial cross-validation and multiple-testing issues.
- FinCast (ACM CIKM 2025): added as prior art for financial time-series foundation modelling; no numerical result was adopted without a fully inspected table and reproduction conditions.

### New research conclusions

1. Accuracy/F1 alone is not an adequate benchmark for a finance system. Use point-wise, cross-sectional ranking, portfolio, probabilistic, calibration, statistical and runtime views.
2. Pretrained time-series foundation models are candidates/priors, not assumed alpha engines; random-walk and strong local models remain mandatory comparators.
3. Multi-task representation can benefit related targets but specialised capacity may be needed for spread/liquidity.
4. Order-book modelling should preserve time, side, level and attribute structure where valid depth/event data exist; do not fabricate L2/L3 data from OHLCV.
5. Compact model efficiency matters, but reported inference latency must be separated from data decode, feature calculation, queueing, risk and end-to-end feed-to-decision latency.
6. Calibration, selective prediction and explicit NO TRADE behaviour are first-class capabilities.
7. The documented Finance AI LR/RF ensemble regressed; do not assume simple averaging or majority voting will work.
8. All candidate improvements require multi-instrument/regime evaluation, untouched test data, statistical uncertainty and cost-aware portfolio tests.

### Proposed MPFM algorithm hypotheses

- RC-MTFSM: regime-conditioned multi-task financial state model, sharing useful return/volatility structure while retaining specialist liquidity/spread heads.
- SPT-LOB: structure-preserving tensor order-book model with low-rank interactions and a compact temporal block.
- RGEE: reliability- and regime-gated expert ensemble using chronological out-of-fold predictions.
- CSFA: calibrated selective forecasting and abstention when uncertainty/data quality/costs dominate.
- DHT-FH: heavy-tail probabilistic forecast head using quantile/Student-t/Johnson SU candidates.
- DSA: drift-aware safe adaptation with candidate evaluation and rollback.

All six are research hypotheses; none is claimed to be novel, implemented or better until prior-art and controlled experiments are completed.

### Benchmark programme established

- Classification: confusion matrix, accuracy, balanced accuracy, per-class precision/recall/F1, macro-F1, weighted-F1, MCC, ROC-AUC and PR-AUC where applicable.
- Regression/direction: MAE, RMSE, MASE, relative MAE, directional hit ratio, Rank IC/ICIR.
- Probabilistic: log loss/NLL, Brier, ECE, reliability diagrams, pinball loss, CRPS and interval coverage.
- Volatility/risk: QLIKE, volatility error, VaR coverage and tail diagnostics.
- Portfolio: net returns, Sharpe, Sortino, Calmar, maximum drawdown, turnover, exposure, slippage, fees, capacity and fill metrics.
- Statistical validation: Diebold–Mariano where appropriate, block bootstrap, multiple-testing correction, Deflated Sharpe and PBO/CPCV when the design supports them.
- Runtime: model-only and end-to-end P50/P95/P99/P99.9 latency, throughput, cold start, memory and hardware details.

### New research artifact

- Added [MPFM_MODEL_RESEARCH_AND_BENCHMARK_ROADMAP.md](MPFM_MODEL_RESEARCH_AND_BENCHMARK_ROADMAP.md).
- Updated the research index and MPFM Research Master.
- The roadmap defines six model research hypotheses, six model benchmark tracks, 12 model/benchmark agent roles and MBR-00 to MBR-09 experiments.

### Immediate decision

Start with MBR-00 and MBR-01: re-establish the existing Finance AI baseline, add zero-return/random-walk and strong classical comparators, compute the full metric suite and expand the untouched out-of-sample protocol. Do not begin advanced MPFM model experiments until data, target, benchmark and baseline contracts are stable. Preserve D0 → D1 → D2 → D3 → D4 and existing data-rights dependencies.


## 2026-11-21 — Modular production-oriented system architecture and engineering disciplines

### User's architecture requirement clarified

- All research, open-source findings and model benchmarks must inform the actual Finance AI / MPFM system design, not remain isolated papers or experiments.
- The system must be modular and deliberately apply DSA, OOP/OOPM, OOAD, Computer Networks, Operating Systems, DBMS, distributed systems, system design, security, testing and reliability engineering.
- The real-world objective is correct operation under data/network/worker/model failures, predictable performance, maintainability and safe evolution—not only high predictive scores.

### Existing repository architecture audited

- Reopened SYSTEM_ARCHITECTURE.md, ARCHITECTURE_PRINCIPLES.md, ENGINEERING_CONSTITUTION.md, DATA_ARCHITECTURE.md, DECISIONS.md and CURRENT_STATE.md.
- Existing standards already specify Python-first design, typed public interfaces, loose coupling, high cohesion, no circular dependencies, pure/deterministic transformations where possible, chronological data splits, data lineage, structured logging, tests, PR review and architecture decision records.
- Existing accepted ADRs include Python as the primary MVP language (ADR-0002), file-backed CSV/Parquet MVP storage (ADR-0005), no cloud/external dependencies for the MVP (ADR-0007), chronological data splitting (ADR-0004), and structured logging (ADR-0006).
- Existing SYSTEM_ARCHITECTURE.md describes the original MVP and ARCHITECTURE_PRINCIPLES.md describes the original layers. They are not a complete target architecture for expanded live multi-market and autonomous-agent scope.
- The new target-state blueprint preserves existing ADRs; a new database, cloud service, Rust/C++ path or broker integration requires measured justification and a new/superseding ADR.

### External engineering research used

- AWS Well-Architected Framework six pillars: operational excellence, security, reliability, performance efficiency, cost optimisation and sustainability.
- C4 model: context, container, component and code-level architecture views.
- Microsoft bounded-context and event-driven architecture guidance.
- AWS transactional outbox, retry/backoff and circuit-breaker patterns.
- Google SRE service-level objectives and four golden monitoring signals (latency, traffic, errors, saturation).
- Python concurrency documentation distinguishing I/O-bound asyncio, threads, processes and free-threaded runtime considerations.
- OpenTelemetry semantic conventions for consistent traces/metrics/logs.
- NIST SSDF SP 800-218 and OWASP application/agent security guidance.

### Architecture decisions proposed

1. Start with a modular monolith, explicit bounded contexts and ports/adapters; extract services only when a measured performance, isolation, scaling or operational requirement justifies it.
2. Separate product/control, real-time market-data/decision, research/model, autonomous-agent and platform-engineering planes.
3. Define module ownership for source entitlement, security master, market data, market state, corporate actions, PIT data, features, datasets, model research/registry, inference, decision/risk, backtesting, future execution, agent orchestration and application API.
4. Use OOP/OOPM/OOAD to encode invariants through entities, value objects, immutable events, application services, ports/adapters and explicit state machines; use SOLID/design patterns when they reduce actual coupling.
5. Apply DSA based on event workloads: hash maps, ring buffers, incremental rolling statistics, monotonic deques, heaps, ordered price levels and bounded queues. Use property/performance tests and profile before low-level optimisation.
6. Apply OS/CN principles: isolate CPU/GPU work, keep blocking calls off the market event loop, use bounded backpressure, separate exchange/receive/availability timestamps, detect sequence gaps, recover subscriptions and handle retries/idempotency/circuit breakers.
7. Apply DBMS/distributed-systems principles: raw append-only data, transactional metadata where required, unique constraints, idempotent consumers, outbox for database/event dual writes, explicit consistency and reconciliation.
8. Keep training, inference, decision/risk and future execution separate; LLM agents must not be on the market tick hot path.
9. Define SLIs/SLOs, failure injection, replay, contract/property/integration/soak/security/performance tests, observability, backups and recovery procedures before production claims.
10. Maintain D0 → D1 → D2 → D3 → D4 unchanged; the architecture is a cross-cutting quality contract, not a replacement backlog.

### New research artifact

- Added [MPFM_MODULAR_SYSTEM_ARCHITECTURE_AND_ENGINEERING_BLUEPRINT.md](MPFM_MODULAR_SYSTEM_ARCHITECTURE_AND_ENGINEERING_BLUEPRINT.md).
- Updated the research index, MPFM Research Master and Development Backlog with the blueprint and its engineering acceptance rules.
- The blueprint covers planes, bounded contexts, module contracts, OOAD/OOP/DSA/CN/OS/DBMS mapping, reliability, telemetry, security, testing, data architecture, proposed folder structure and D0–D4 migration gates.

### Implementation status

This is a proposed target architecture and research update only. No code module, database, cloud dependency, message broker, broker adapter, Rust/C++ hot path or production deployment was added by this update. Existing MVP ADRs remain in force until an explicit ADR change is accepted.
