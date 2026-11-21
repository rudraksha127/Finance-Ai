# HFT Systems, Market-Microstructure Engineering and Open-Source Ecosystem Research

**Research date:** 2026-11-21  
**Repository reviewed:** rudraksha127/Finance-Ai, main  
**Repository tree SHA reviewed:** 88d56d6ef5f7b12c2bdaffe38618ca74cb01585d  
**Research status:** Public-source engineering study and architecture recommendations. No new trading strategy or HFT capability is claimed as implemented.

> **Scope and epistemic boundary:** Proprietary HFT firms do not publish their complete internal systems. This research reverse-engineers publicly documented principles, code structures and operating patterns from company material, academic work, exchange documentation and open-source repositories. It does not claim access to confidential firm architecture, strategy code, execution logic or infrastructure. Public company claims are evidence of what those firms disclose, not independent verification of their performance.

---

## 1. Executive conclusions

### 1.1 The core finding

A sophisticated trading firm is not simply a predictive model connected to a broker API. The public material reviewed consistently describes an integrated operating system across:

1. Market data acquisition, normalization, quality and distribution.
2. Quantitative research, price discovery, feature construction and prediction.
3. Strategy-specific decision logic, quoting and/or portfolio construction.
4. Pre-trade risk, inventory/exposure controls and trading-state management.
5. Execution algorithms, order lifecycle and venue connectivity.
6. Post-trade accounting, reconciliation, surveillance and operational monitoring.
7. A feedback loop that turns live outcomes into new research, models and system improvements.

Optiver publicly describes data, pricing, risk and execution systems, as well as research infrastructure, low-latency C++ systems, FPGA hardware and high-throughput data platforms. HRT describes deep learning in production, low signal-to-noise data, overfitting risk, distribution shifts, adversarial adaptation and real-time processing of millions of bursty irregular events. Jane Street publicly describes OCaml as a primary engineering platform used across trading systems, automation, monitoring and research. IMC describes in-house software and FPGA infrastructure. Jump describes co-located compute, proprietary network infrastructure, custom ASIC/FPGA work, large-scale compute and simulation.

**What this means for Finance AI:** The important lesson is system integration and feedback quality, not copying the word HFT or prematurely adopting FPGAs. Our first objective remains a reliable, point-in-time, multi-market predictive research platform. HFT-style microstructure and execution should be a separate research/engineering lane.

### 1.2 Recommended strategic split

| Lane | Primary question | Priority |
|---|---|---|
| Finance AI / MPFM predictive intelligence | What is likely to happen across instruments and horizons, with calibrated uncertainty? | Primary |
| Market microstructure research | What does order flow, liquidity, spread, queue and short-horizon market state reveal? | Research lane after appropriate data |
| Execution engineering | Can a valid strategy be executed at realistic prices, sizes and latency? | Separate subsystem after prediction and data foundations |
| HFT feasibility | Is a latency-sensitive strategy economically, legally and technically feasible on a permitted venue route? | Feasibility study only; not a current implementation target |

Do not merge the predictive model, mandate logic, risk engine and execution engine into one model or one service.

---

## 2. How public HFT firms describe their operating model

### 2.1 Public-source comparison

| Firm | What its own public material says | Engineering inference for our design |
|---|---|---|
| Optiver | Data, pricing, risk and execution systems underpin trading and research. It also identifies research infrastructure/systematic ML, low-latency C++, FPGA and high-throughput data platforms. It describes tight researcher-engineer-trader collaboration and blast-radius containment. | Treat market data, pricing/alpha, risk and execution as separate but tightly integrated components. Research infrastructure and production reliability are first-class capabilities. |
| Hudson River Trading (HRT) | Deep learning is core to part of its trading. It explicitly calls out low signal-to-noise, overfitting, distribution shifts, adaptive/adversarial participants and processing millions of irregular events under ultra-low-latency constraints. It describes substantial GPU compute. | Research must prioritize robust out-of-sample evidence, drift and adversarial adaptation. Model inference throughput and data loading are systems problems, not just model architecture problems. |
| Jane Street | Its technology page describes OCaml as its primary technology across trading systems, systems automation, monitoring and research. Its engineering material highlights low-latency networking, distributed systems and performance engineering. | Strong typed interfaces, state correctness, observability and performance engineering are core. Language choice follows architecture and team expertise; using OCaml solely because Jane Street does is not justified. |
| IMC | Describes in-house software, mission-critical trading infrastructure, AI/ML investment and FPGA hardware as a latency/capacity component. | Separate general-purpose research/software systems from specialized hardware acceleration. FPGA is a late optimization for measured bottlenecks, not an MVP dependency. |
| Jump Trading | Describes research data centers, co-located compute near exchanges, custom ASIC/FPGA, proprietary network infrastructure, systems in C++, Python, Go and Rust, and storage/simulation/analytics for trading and AI research. | Data centers, networking, simulation and research compute are part of the same engineering system. Co-location is a venue/infrastructure commitment, not a Python library feature. |
| Virtu | Describes automated market making and post-trade processes, with global market-making, execution, liquidity and analytics technology. | Post-trade workflows and market structure matter alongside quote generation and order placement. |

Sources:

- Optiver: https://www.optiver.com/what-we-do/technology/
- Optiver overview: https://www.optiver.com/what-we-do/
- HRT machine learning: https://www.hudsonrivertrading.com/machine-learning/
- Jane Street technology: https://www.janestreet.com/technology/
- Jane Street low-latency engineer role: https://www.janestreet.com/join-jane-street/position/6254435002/
- IMC technology: https://www.imc.com/in/what-we-do/technology
- IMC research-to-strategy overview: https://www.imc.com/in/what-we-do
- Jump technology: https://www.jumptrading.com/technology
- Virtu market making: https://www.virtu.com/market-making/

### 2.2 The common operating loop

The public descriptions support this high-level operating pattern:

~~~text
Market / venue observations
        |
        v
Market-data capture and validation
        |
        v
Canonical instrument + event-time state
        |
        v
Pricing / alpha / state estimation
        |
        v
Strategy policy and inventory / portfolio context
        |
        v
Pre-trade risk and limits
        |
        v
Execution algorithm and venue adapter
        |
        v
Acknowledgements, fills, rejects, cancels
        |
        v
Post-trade reconciliation, PnL and surveillance
        |
        v
Research feedback, model updates and system improvements
~~~

This is a public-information synthesis, not a claim that every firm uses the same internal sequence or implementation.

### 2.3 Market making is not merely directional prediction

A market maker may continuously quote both sides of the book. A simplified conceptual structure is:

- Estimate a fair or reservation price.
- Adjust it for short-horizon alpha/forecast.
- Skew it for inventory and risk.
- Widen or narrow the half-spread for volatility, adverse selection, fees and market conditions.
- Respect price, size, position, exposure and venue constraints.
- Reassess/cancel/replace as new data arrives.

A simplified form shown in HftBacktest's market-making example is:

~~~text
reservation_price = mid_price + alpha_weight * forecast - inventory_weight * inventory_risk
bid_price = reservation_price - half_spread
ask_price = reservation_price + half_spread
~~~

The example is useful for learning the decomposition; it is not a profitable strategy specification. Finance AI should not turn an investor philosophy into a quote engine or treat a predicted UP/DOWN class as a complete market-making policy.

### 2.4 What we cannot infer

- A public careers page does not disclose a firm's full software architecture.
- A stated FPGA or GPU investment does not tell us the exact strategy using it.
- The same firm may operate market making, execution services, systematic investing and other businesses with different stacks.
- A public result, scale statement or marketing claim is not an independently audited strategy-performance result.
- We should not copy presumed proprietary logic or claim that an open-source stack reproduces a leading firm's edge.

---

## 3. HFT architecture: hot path and research/control path

### 3.1 Hot path

A low-latency execution path may contain the following logical stages:

1. Network/NIC receives exchange market-data packets; timestamp and sequence metadata are preserved.
2. Feed handler decodes the venue protocol and validates sequence continuity.
3. Order-book builder applies snapshots and deltas, detects gaps and requests recovery where supported.
4. State/feature engine calculates bounded, deterministic microstructure features.
5. Strategy logic evaluates pricing, alpha, inventory and quote/order changes.
6. Pre-trade risk checks validate trading state, instrument rules, size, notional, limits and rate constraints.
7. Execution gateway submits, modifies or cancels orders.
8. Order/execution reports update the local order and position state.
9. Reconciliation compares local state with venue/broker reports and resolves uncertainty.

Key engineering principles for a future hot path:

- Avoid synchronous database queries, LLM calls, slow external HTTP requests or blocking UI work.
- Keep market-data, strategy and execution state explicit and versioned.
- Make sequence gaps, stale data, clock uncertainty and disconnects first-class faults.
- Bound queues and work per event; define what happens under overload.
- Separate event timestamps, local receive timestamps and order request/acknowledgement timestamps.
- Measure end-to-end latency distributions, not only average latency.
- Preserve deterministic event replay for debugging and research.
- Fail closed when the system cannot establish trustworthy market or order state.

These are proposed engineering principles. They are not a description of any one firm's confidential implementation.

### 3.2 Research, data and control path

The research path can be slower and compute-heavy:

- Immutable event capture and historical archive.
- Data-quality and corporate-action processing.
- Instrument/security master and market-calendar resolution.
- Feature generation and point-in-time joins.
- Training, walk-forward validation and model comparison.
- Microstructure simulation and event replay.
- Experiment tracking, model registration and promotion controls.
- Monitoring, drift, incident review and post-trade analysis.

The hot path consumes approved, versioned artifacts from the research path. It should not execute arbitrary training code or dynamic research notebooks.

### 3.3 Separate model roles

| Component | Input | Output | Must not do |
|---|---|---|---|
| Financial state encoder | Causal market and approved external observations | Financial state representation | Submit or manage orders |
| Forecast/alpha model | State and target/horizon context | Expected return, direction, volatility, liquidity or distributional forecast | Decide account permissions |
| Mandate/strategy adapter | Forecasts + structured mandate | Candidate exposure, target weights or trade intent | Rewrite base forecast probabilities |
| Portfolio/inventory controller | Positions, cash, exposure, risk budget, candidate intents | Allowed target inventory/exposure | Invent market data |
| Pre-trade risk engine | Account, order, instrument, limits, live state | Allow, resize, reject or halt | Optimize alpha |
| Execution algorithm | Approved intent, market state, venue constraints | Child-order plan and lifecycle actions | Change the underlying forecast |
| Broker/exchange adapter | Typed commands and venue state | Acks, fills, cancels, rejects and reports | Own strategy policy |
| Reconciliation | Local event ledger + venue reports | Resolved order/position/account state or an unresolved incident | Silently assume unknown orders succeeded |

---

## 4. Direct audit of the Finance-Ai repository

### 4.1 Repository evidence

The recursive Git tree for main was reviewed at SHA 88d56d6ef5f7b12c2bdaffe38618ca74cb01585. It returned 332 entries without truncation:

| Inventory | Count observed |
|---|---:|
| Files | 280 |
| Directories | 52 |
| Python files | 166 |
| Markdown documents | 48 |
| TSX / React files | 19 |
| Files under tests/ | 52 |
| Python files under src/ | 101 |

This is a tree inventory, not proof that every line in all 280 files was manually inspected. The following core source areas and design documents were inspected directly.

### 4.2 Existing strengths to preserve

| Existing component | Evidence in code/docs | Assessment |
|---|---|---|
| Historical ingestion | Historical source abstraction, Yahoo adapter, ingestion journal, retries, normalization and immutable CSV merge | Useful research foundation; data resolution/source scope remains limited |
| Cleaning and data quality | Cleaning, validation, corporate-action-related processing, audits and quality gates | Preserve; expand only with better source coverage and instrument metadata |
| Feature engineering | Canonical feature registry, 52 approved MVP features, formula/metadata/version structure and leakage tests | Strong declarative foundation; not order-book microstructure features |
| Labels and datasets | Future-window labels, immutable versioned datasets, chronological splits, hashes and manifests | Preserve target versioning and strict temporal boundaries |
| Baseline and temporal models | Logistic Regression, Random Forest, LightGBM/XGBoost support in configured training/backtesting paths, temporal LSTM candidate | Research machinery exists; actual model value remains weak/unproven |
| Walk-forward evaluation | Expanding-window folds, per-fold training and overlap purge | Useful but currently built around daily/periodic observations and simplified execution |
| Model registry | Checksum/version records, explicit states, one active-model invariant, promotion/rollback | Preserve as a research artifact control plane; evaluate transactional durability before multi-process production |
| Drift/retraining/operations | Drift events, candidate retraining gates, operations snapshot and monitoring lifecycle | Valuable foundation for controlled research operations |
| Multimodal point-in-time layer | Availability-time joins, reliability classes, conservative DAY_ONLY eligibility and missing values as NaN | Particularly important; do not bypass with naïve joins |
| Research dashboard and API | React/Vite dashboard, FastAPI read/predict surface | Good control/visualization plane; not a low-latency execution path |

### 4.3 Current hard limitations found in source

1. **Source resolution:** the implemented historical adapter is Yahoo-oriented and the documented intervals are daily/weekly/monthly. No production NSE/BSE/MCX live feed or full depth/tick ingestion was established in the repository.
2. **Instrument master:** the inspected registry is a minimal file-backed ticker identity record with limited fields. It is not yet a complete multi-venue security/derivative contract master with ISIN, segment, expiry, strike, option type, lot size, tick size, multiplier, trading status, mapping history and corporate-action lineage.
3. **Storage:** original MVP uses CSV/Parquet/file-backed artifacts. PostgreSQL appears as a Phase-2 target/reference in the docs, not an implemented transactional/time-series database.
4. **Execution simulator:** src/backtest/execution.py explicitly models long-only LONG/FLAT, fixed one-unit quantity, one position, close-to-close fills at the signal-day close, a five-row holding cap, and fixed per-side basis-point costs. This is a research simplification, not an intraday order-book or queue-aware exchange simulator.
5. **Cost realism:** the existing scenario runner tests named fixed cost/slippage scenarios; it does not establish a market-impact model, queue priority, partial-fill dynamics or exchange latency.
6. **Prediction API:** src/api/orchestrator.py currently restricts the MVP interval to 1d; src/api/decision.py uses classification probabilities to create BUY/SELL/NO_TRADE. It returns no model-estimated expected return, and position sizing is a placeholder value. The API explicitly refuses live mode.
7. **Order management:** no broker order state machine or production order execution gateway is present in the existing MVP. The model registry is not an order-management system.
8. **External data:** point-in-time fundamental/news abstractions and fixtures exist, but CURRENT_STATE records no licensed provider approved for real fundamentals/news experiments. Real-data experiments must remain blocked until data rights and availability timestamps are established.
9. **HFT data:** no full depth/market-by-order historical dataset, exchange packet feed handler or queue-reconstruction pipeline is established.
10. **HFT operational infrastructure:** no exchange co-location, multicast feed handler, kernel-bypass networking, dedicated order gateway or venue reconciliation process is established.

The repository's own research ledger records weak AAPL classification results, candidates not promoted, zero trades in some static tests and a negative walk-forward result in one documented run. Those results must remain visible; an execution framework upgrade cannot convert weak alpha evidence into a profitable strategy.

### 4.4 Existing architecture decisions constrain tool adoption

- ADR-0002 records Python as the primary language.
- ADR-0005 records file-based MVP storage and explicitly defers database adoption.
- ADR-0007 records a minimal-dependency / no cloud-external-dependency posture for the MVP.
- ADR-0020 separates prediction, decision and execution.
- The current research workspace records D0 → D1 → D2 → D3 → D4 as the agreed development order.
- Exact one-to-one D-code allocation of every subsystem is not reliably preserved; do not invent it.
- Philosophy ontology, licensing and baseline research can continue in parallel.
- Multimodal model training follows a trustworthy point-in-time foundation.

**Recommendation:** Do not add all infrastructure components in one large rewrite. Preserve the existing pipeline and introduce adapters and services only when an acceptance test requires them.

---

## 5. Open-source repository deep review

The following repositories were inspected at README, directory-tree and selected source-file level. “Inspected” below means the named architecture files/components were reviewed; it does not mean every file in those large projects was audited line by line.

### 5.1 NautilusTrader — strongest architecture reference for a shared event-driven trading engine

Repository: https://github.com/nautechsystems/nautilus_trader  
License: LGPL-3.0; review the exact licence and linking/distribution implications before embedding or distributing derivatives.

**Why it matters**

NautilusTrader is a Rust-native engine with Python as a control/orchestration layer. The same core architecture supports backtest, sandbox and live contexts. It is built around a kernel, data engine, message bus, cache, trader, portfolio, risk engine and execution engine.

**Source paths inspected**

- docs/concepts/architecture.md
- docs/concepts/live.md
- docs/concepts/message_bus.md
- docs/concepts/backtesting/fill-models.md
- docs/concepts/backtesting/execution-flow.md
- docs/concepts/backtesting/data-and-venues.md
- crates/risk/src/engine/mod.rs
- crates/risk/src/engine/config.rs
- crates/live/src/execution/manager.rs
- crates/model/src/orderbook/analysis.rs
- crates/model/src/orderbook/book.rs
- crates/trading/src/examples/strategies/orderbook_imbalance/strategy.rs
- crates/adapters/binance/src/
- crates/adapters/interactive_brokers/

**Architectural patterns worth learning**

- Explicit data-client and execution-client adapters.
- A central kernel lifecycle and typed message boundaries.
- In-memory indexed cache for instruments, accounts, orders and positions.
- Separate risk engine between strategy commands and execution.
- Submission/acknowledgement/fill/cancel/reject state handling.
- Portfolio and position accounting driven by events.
- Reconciliation of local state against venue reports.
- One strategy implementation can be used across historical/sandbox/live contexts, while live-mode differences remain explicit.

**Critical caveat**

Backtest/live code reuse does not mean their behaviour is identical. Live systems introduce transport failures, external venue activity, clock/timing differences, persistence failures and reconciliation. In addition, NautilusTrader documents that its historical order book remains immutable after a simulated fill; liquidity-consumption settings and fill models control some replay assumptions, but historical replay cannot know how a real hypothetical order would alter other participants' behaviour.

**Finance AI fit**

- Strong reference for the future Execution Plane, typed order lifecycle, risk gateway, portfolio state, venue adapters and deterministic event-driven replay.
- Could be evaluated as an isolated engine in a later proof of concept.
- Do not replace the MPFM research pipeline or model registry with NautilusTrader.
- Do not introduce LGPL-linked runtime code into Finance AI before a licence review and a Python/Rust integration spike.
- No Indian exchange or Indian broker adapter was established by this code review. The existence of international adapters is not proof of NSE/BSE/MCX support.

### 5.2 HftBacktest — strongest specialist reference for HFT replay assumptions

Repository: https://github.com/nkaz001/hftbacktest  
License: MIT.

**Why it matters**

HftBacktest focuses on market-data replay for HFT and market making. Its documented features include tick-by-tick processing, L2 market-by-price and L3 market-by-order book reconstruction, feed/order latency models, queue-position models, fee models and multi-asset/multi-exchange simulations. It also has a Rust implementation/live prototype for specific crypto venues.

**Source paths inspected**

- README.rst
- docs/latency_models.rst
- docs/debugging_backtesting_and_live_discrepancies.rst
- hftbacktest/src/backtest/models/queue.rs
- hftbacktest/src/backtest/models/latency.rs
- hftbacktest/src/backtest/models/fee.rs
- hftbacktest/src/backtest/proc/local.rs
- hftbacktest/src/backtest/proc/l3_local.rs
- hftbacktest/src/live/bot.rs
- examples/4_latency.py
- examples/5_backtest.py
- examples/Impact of Order Latency.ipynb
- examples/Probability Queue Models.ipynb
- examples/Level-3 Backtesting.ipynb

**Important mechanics**

HftBacktest separates at least three latency concepts:

1. Feed latency: exchange event time to local receive time.
2. Order-entry latency: local order request to matching-engine processing.
3. Order-response latency: matching-engine processing to local acknowledgement/report receipt.

Its queue models estimate quantity ahead of the simulated order. The conservative queue model advances only when trades happen at that price. Probability-based queue models also estimate how cancellations/depth reductions move the order through the queue, while attempting to avoid double-counting changes already represented by trades.

**Critical limitation explicitly documented by the project**

HftBacktest is a market-data replay simulator: the hypothetical order does not modify the recorded market. No market impact is simulated. Its own documentation says the approach assumes the simulated order is small enough not to move the market and that live discrepancies must be measured and incorporated. Some partial-fill cases can remain unrealistic because replayed market depth and trades cannot change.

**Finance AI fit**

- Use it to learn about latency-aware replay, queue priority, L2/L3 data, fee models and market-making experiments.
- Use it as a specialist benchmark if we later acquire suitable historical order-book data.
- It is not a replacement for real exchange simulation when our orders materially affect liquidity.
- Its current live examples are crypto-specific (not evidence of NSE support).
- Do not wire it into the daily MPFM evaluation loop merely because it is called an HFT backtester.

### 5.3 ABIDES — agent-based exchange/market simulation research

Repository: https://github.com/abides-sim/abides  
License: BSD 3-Clause.

**Why it matters**

ABIDES is a discrete-event, agent-based simulator for market applications. Its README describes simulations of tens of thousands of trading agents interacting with an exchange agent, configurable pairwise network latencies and a message design informed by published NASDAQ ITCH/OUCH protocols.

**Source paths inspected**

- Kernel.py
- agent/ExchangeAgent.py
- agent/TradingAgent.py
- util/OrderBook.py
- model/LatencyModel.py
- agent/execution/ExecutionAgent.py
- agent/execution/TWAPExecutionAgent.py
- agent/execution/VWAPExecutionAgent.py
- agent/execution/POVExecutionAgent.py
- config/marketreplay.py
- config/execution.py

**Research value**

- Simulate interactions among heterogeneous agents instead of replaying a fixed historical tape only.
- Study the effect of network/processing delays and different participant behaviours.
- Prototype TWAP/VWAP/POV execution agents and market-replay agents.
- Explore strategic feedback and price formation under controlled, synthetic assumptions.

**Limitations**

ABIDES is a research simulation environment. Its synthetic agent behaviour is only as valid as the assumptions and calibration behind those agents. It does not supply licensed Indian market data, actual broker connectivity or real order fills. A successful ABIDES simulation is not proof of real-market profitability.

**Finance AI fit**

Use it for later agent-interaction and counterfactual research, particularly the MPFM world-model lane. Keep synthetic simulation findings clearly separated from empirical market-data validation.

### 5.4 QuantConnect LEAN — broad event-driven trading framework

Repository: https://github.com/QuantConnect/Lean  
License: Apache-2.0.

**Source areas inspected**

- Engine/AlgorithmManager.cs
- Engine/DataFeeds/
- Algorithm/Execution/
- Algorithm/Risk/
- Algorithm.Framework/Execution/
- Algorithm.Framework/Risk/
- Brokerages/DefaultOrderBook.cs
- Common/Interfaces/IDataQueueHandler.cs

**Patterns worth studying**

- Data-feed and subscription interfaces.
- Time-synchronized event processing.
- Execution model interface and order-event lifecycle.
- Pluggable composite risk models.
- Portfolio construction, position targets and execution model boundaries.
- Regression tests for brokerage, order and risk behaviours.

LEAN is a broader algorithmic-trading engine, not an HFT market-replay specialist. Its interfaces and test patterns are more directly useful than copying its entire C# engine into the current Python codebase.

### 5.5 Hummingbot — connector and order-executor reference

Repository: https://github.com/hummingbot/hummingbot  
License: Apache-2.0.

**Source areas inspected**

- hummingbot/core/data_type/order_book_tracker.py
- hummingbot/connector/exchange/binance/binance_api_order_book_data_source.py
- hummingbot/strategy_v2/executors/
- position_executor/position_executor.py
- twap_executor/twap_executor.py
- arbitrage_executor/
- xemm_executor/
- tests for partial fills, slippage escalation, recovery paths and terminal exposure

**Patterns worth studying**

- Venue-specific order-book data-source adapters.
- Normalized order-book tracking and connector boundaries.
- Reusable order lifecycle executors for position, TWAP, arbitrage, grid and cross-exchange execution.
- Recovery and fault-oriented tests.

**Limitations**

Hummingbot is primarily an exchange/broker connector and strategy framework oriented toward digital-asset venues. Its connector coverage must not be mistaken for NSE/BSE/MCX broker coverage. Treat it as a reference for connector resilience and order lifecycle design, not as the main Finance AI architecture.

### 5.6 FinRL-X — modular quantitative portfolio/strategy reference

Repository: https://github.com/AI4Finance-Foundation/FinRL-Trading  
License: Apache-2.0.

**Design studied**

The README describes a weight-centric contract: strategy stages produce target portfolio weights, which are passed through allocation/timing/risk transformations before backtesting or execution. Its visible architecture separates data, strategy, backtest and execution concerns.

**Code paths inspected**

- src/strategies/base_strategy.py
- src/backtest/backtest_engine.py
- src/strategies/adaptive_rotation/risk_manager.py
- src/strategies/execution_engine.py

**Finance AI fit**

This is useful for studying portfolio-level strategy composition and a consistent strategy-to-execution interface. It is not an HFT engine and its README performance/paper-trading figures are project-reported results, not independent validation of its methods or a transferable performance expectation.

### 5.7 Microsoft Qlib — quantitative alpha research and experiment framework

Repository: https://github.com/microsoft/qlib  
License: MIT.

Qlib positions itself as an AI-oriented quant research platform covering supervised learning, market dynamics modeling and reinforcement learning, with data processing, model training and backtesting workflows.

**Finance AI fit**

- Study factor and alpha research workflows, dataset abstractions, benchmarks and reproducible experiments.
- Compare its research organisation to our existing feature registry, dataset versioning and walk-forward pipeline.
- Reuse ideas or selected components only after a gap analysis. Qlib is not an order gateway or an Indian exchange data entitlement.

### 5.8 Comparison summary

| Project | Main strength | Best role in our project | Main caveat | Initial decision |
|---|---|---|---|---|
| NautilusTrader | Integrated event-driven trading engine, risk, portfolio, execution, adapters and replay | Execution-plane architecture reference / later isolated POC | LGPL-3.0; not proof of Indian venue support; replay assumptions remain | Study deeply; no immediate adoption |
| HftBacktest | L2/L3 replay, latency and queue models | HFT/microstructure benchmark | No market impact in replay; current live examples are crypto | Strong later specialist tool |
| ABIDES | Agent-based exchange and network-latency simulation | MPFM world-model/counterfactual research | Synthetic environment; model calibration required | Research-only |
| LEAN | Modular algorithmic event engine and interfaces | Backtest/strategy/risk lifecycle design | Broad engine, not specialist HFT queue replay | Study patterns |
| Hummingbot | Venue connectors and order executors | Connector/order-state test patterns | Primarily digital-asset venue ecosystem | Selective reference |
| FinRL-X | Portfolio-weight composition and AI quant research | Strategy/portfolio interface ideas | Author-reported experiments do not validate MPFM | Research reference |
| Qlib | Factor research, datasets, ML workflows | Alpha research/benchmark ideas | Not a real-time market-data or execution system | Study/benchmark selectively |

---

## 6. Open-source infrastructure ecosystem: what each layer needs

Do not choose every tool listed here. Select the smallest stack that satisfies measured workload and operational requirements.

### 6.1 Data formats and local research compute

| Technology | Role | Recommendation |
|---|---|---|
| Apache Parquet | Compressed columnar historical data format | Continue as the versioned research archive format |
| Apache Arrow | In-memory columnar interchange across Python/Rust/C++/analytics | Adopt at system boundaries when profiling shows serialization/copy overhead |
| Polars | Rust-backed DataFrame compute | Benchmark against Pandas for large multi-instrument/tick transformations; do not rewrite working code without evidence |
| DuckDB | Embedded analytical SQL over Parquet/Arrow | Good local research/query engine candidate; does not replace an OLTP account/order database |
| QuestDB | Open-source time-series SQL database with Parquet/Arrow interoperability | Candidate for live time-series ingestion/queries only after tick/event workload and operational need are measured |

**Practical split**

- Immutable historical archives: partitioned Parquet files with manifests, checksums and data-rights metadata.
- Research analytics: Pandas/Polars/DuckDB over Arrow/Parquet.
- Live operational time-series serving: benchmark QuestDB against the actual workload before adoption.
- Relational account, security master, order and compliance state: evaluate a transactional SQL database in a separate architecture decision; the MVP intentionally deferred PostgreSQL.

QuestDB's repository and site identify Apache-2.0 licensing and describe Parquet, Arrow and SQL support: https://github.com/questdb/questdb and https://questdb.com/.

### 6.2 Event transport, messaging and replay

| Technology | Best role | Use when | Do not confuse with |
|---|---|---|---|
| Apache Kafka | Durable event log, high-throughput distribution, independent consumers and replay | Several ingestion/research/analytics consumers need retained ordered event streams | Nanosecond in-process strategy calls |
| NATS | Lightweight service messaging, request/reply and pub/sub; JetStream adds persistence | Control-plane services and operational coordination need a simple messaging fabric | Exchange multicast feed handling |
| Aeron | High-performance UDP/multicast/IPC transport and recording/replay tools | A later measured low-latency path justifies specialized transport | A complete order-management/risk system |

**Recommendation:** Start with direct typed interfaces/in-process event flow and append-only event capture. If multiple durable consumers appear, evaluate Kafka. If a lightweight operational service bus is needed, evaluate NATS. Aeron belongs to a later low-latency feasibility lane. Do not operate Kafka + NATS + Aeron at once without clearly separated requirements.

References:
- Kafka: https://kafka.apache.org/documentation/
- NATS: https://docs.nats.io/concepts/what-is-nats
- Aeron: https://aeron.io/docs/

### 6.3 Time-series and analytical storage

- QuestDB is a viable open-source time-series candidate for high-volume time-stamped observations and SQL access. Verify the exact release, configuration, recovery and operational profile before committing.
- ClickHouse is a strong analytical column-store candidate for broad scans, grouped research queries and long historical event analysis. It should not be confused with a matching engine.
- DuckDB is suitable for local research and Parquet queries without creating another service dependency.
- PostgreSQL remains a possible transactional metadata/order/account store, subject to the already-recorded Phase-2 decision and requirements.

**Do not install three databases as a default stack.** Define a workload test first: event rate, batch size, retention, query shape, concurrency, recovery objective, storage footprint and write/read isolation.

### 6.4 Experiment tracking, feature serving and model deployment

| Technology | Potential role | Recommendation |
|---|---|---|
| MLflow | Experiment parameters, metrics, artifacts and model lifecycle tracking | Benchmark as an optional research UI/tracking layer; keep current registry's safety invariants authoritative until parity is proven |
| Feast | Offline/online feature retrieval and point-in-time feature joins | Study only if feature consumers and serving scale out; preserve our stricter availability-time/reliability semantics |
| Prometheus + Grafana | Metrics, alerting and operational dashboards | Useful when live services and feed/latency health become operational |
| OpenTelemetry | Cross-service traces, metrics and logs | Consider for distributed components, not as a mandatory dependency for current single-process research MVP |

The current repository already implements its own feature and model versioning, point-in-time joins, registry transitions and audit records. Do not create duplicate sources of truth. Integrate only when a real gap is established.

### 6.5 Low-level performance tools

Potential later subjects include:

- Linux CPU affinity, NUMA locality, huge pages, NIC queues and hardware timestamps.
- eBPF/perf-based profiling, flame graphs, cache-miss and branch-mispredict analysis.
- DPDK or other kernel-bypass approaches where permitted and supported by hardware.
- C++/Rust hot-path components and Python as the research/control plane.
- FPGA/ASIC development only after a proven algorithmic edge and a measured software bottleneck.

These are engineering options, not current Finance AI dependencies. The cost/benefit case depends on latency targets, market access, hardware, colocation and staff capability.

---

## 7. Market-data requirements: NSE and India are a real gating boundary

### 7.1 Market-data levels are not interchangeable

NSE publicly describes paid real-time feed levels including:

- Level 1: best bid and best ask.
- Level 2: up to five best bid/ask levels.
- Level 3: up to twenty best bid/ask levels.
- Tick-by-tick: full order-book data.

The published page states that online real-time data is delivered in multicast format over a dedicated leased-line circuit. This is materially different from receiving a quote snapshot from a retail broker WebSocket.

Official source: https://www.nse.in/static/market-data/real-time-data-subscription

### 7.2 Required capability separation

| Capability | Data requirement | Why |
|---|---|---|
| Daily/swing prediction | Point-in-time OHLCV, corporate actions, instrument master, calendar and approved fundamentals | Direction/return/regime forecasts over slower horizons |
| Intraday prediction | Reliable intraday bars or trades/quotes, timestamp precision, gaps and market-session handling | Shorter horizons; sensitivity to stale data and execution costs |
| Order-flow / liquidity prediction | Quote/trade events and suitable depth (L2/L3/tick) | Imbalance, spread dynamics, depth changes and short-horizon liquidity |
| Queue/fill prediction | Event-level depth/order history, trade flow and order/ack timestamps where available | Queue position and fill probability |
| Market-impact modelling | Executed volume, depth, order size, volatility, venue state and strategy participation | Estimate price response and capacity |

Do not manufacture Level 2/3 data by resampling OHLCV or infer queue priority from top-of-book snapshots.

### 7.3 Data permissions are independent of API connectivity

The NSE Data Sharing & Usage Policy covers display, non-display, use and redistribution. The policy describes subscriptions and agreements that specify intended use, handling and restrictions; it also states that redistribution is not automatically allowed.

Official source: https://www.nseindia.in/static/market-data/nse-data-policy

For every vendor or broker data route, record:

- Historical depth and backfill availability.
- Live feed resolution and update frequency.
- Exchange timestamp and local receive timestamp availability.
- Non-display algorithmic use permission.
- Training and model-development permission.
- Raw event retention and derived-feature retention rights.
- Internal use vs external display rights.
- Redistribution, derived-data and derived-index restrictions.
- Whether a specific exchange segment and instrument family are included.
- Commercial and renewal terms.

A broker's account API, market-data entitlement and exchange data licence are separate questions. No code adapter can grant missing legal rights.

### 7.4 Retail API trading is not HFT infrastructure

SEBI issued the safer retail algo participation circular on 2025-02-04 and subsequently extended implementation timelines on 2025-09-30. The extension states that the February 2025 framework and exchange operational modalities apply to all stock brokers from 2026-04-01. NSE's current algo pages refer to broker/exchange registration and application processes, including later 2026 circulars.

Sources:
- SEBI circular: https://www.sebi.gov.in/legal/circulars/feb-2025/safer-participation-of-retail-investors-in-algorithmic-trading_91614.html
- SEBI timeline extension: https://www.sebi.gov.in/sebi_data/attachdocs/sep-2025/1759232056254.pdf
- NSE algo/DST information: https://www.nseindia.com/static/trade/platform-services-non-neat-decision-support-tools-algorithm-trading

Before any broker automation, re-check the current broker's API onboarding and exchange/SEBI process with the broker and qualified counsel. The project should remain research/paper-only until this is verified. This section is technical due diligence, not legal advice.

---

## 8. A deeper evaluation of HFT backtesting and microstructure research

### 8.1 Why an order-book simulator is not ground truth

Market replay can use recorded book/quote/trade events but cannot directly observe how a hypothetical order would have changed other participants' actions. Two examples from the reviewed frameworks:

- HftBacktest explicitly states that its replay does not change the historical market and therefore does not simulate market impact.
- NautilusTrader explicitly documents immutable historical books and exposes liquidity-consumption and fill-model controls; its docs warn that recorded book data cannot show how a simulated order would have changed the market.

This creates different levels of simulator credibility:

| Simulation class | What it can study | What it cannot establish by itself |
|---|---|---|
| Bar-based backtest | Broad signal and portfolio logic | Intrabar ordering, spread/queue and realistic fill timing |
| Quote/trade replay | Quote response, trade event sequence and some spread-aware logic | Full queue position when event data is incomplete |
| L2/L3 market replay | Depth, queue estimates, order-book state, latency and more granular fills | Actual market response to our hypothetical order; true capacity |
| Agent-based simulation | Controlled participant interactions and counterfactual market dynamics | Reality unless agents are calibrated and validated against real observations |
| Paper/shadow/live controlled evaluation | Actual interface timing, rejects, fills and operational discrepancies | Long-horizon statistical profitability without sufficient observations |

### 8.2 Research metrics for microstructure models

In addition to prediction metrics, a microstructure/strategy experiment should report:

- Mid-price movement after 100 ms / 1 s / 5 s / 30 s or other justified horizons.
- Order-flow imbalance and depth imbalance.
- Spread and realized spread.
- Queue position estimate and its uncertainty.
- Fill probability and time-to-fill.
- Partial-fill frequency and unfilled/cancelled quantity.
- Adverse selection conditional on fill.
- Effective spread and implementation shortfall.
- Maker/taker ratio, fees, taxes and exchange charges.
- Cancel/replace rate, message rate and reject rate.
- Net PnL by instrument, session, volatility and liquidity regime.
- Capacity and market participation rate.
- Latency median, p95, p99, p99.9, jitter and dropped/gapped event rate.

A high-frequency signal with high gross predictive accuracy may still lose after fees, spread, queue priority, missed fills, stale feed and adverse selection.

### 8.3 Order-flow research is promising but data-dependent

The 2023 paper “Deep order flow imbalance: Extracting alpha at multiple horizons from the limit order book” uses granular Nasdaq order-book data from 115 stocks and reports that stationary order-flow-derived inputs can outperform models trained directly on raw order-book states in its study.

Source: https://onlinelibrary.wiley.com/doi/full/10.1111/mafi.12413

This is a research hypothesis to test, not transferable proof for Indian instruments. Reproduce with legally acquired NSE data, a fixed set of horizons and strong non-neural baselines before considering deeper models.

### 8.4 HftBacktest versus ABIDES versus NautilusTrader

Use each for the question it is designed to study:

- HftBacktest: How sensitive is an order/market-making strategy to feed latency, order latency, queue assumptions and historical L2/L3 replay?
- ABIDES: How do heterogeneous agents interact under controlled assumptions about their information, actions and network delays?
- NautilusTrader: How should event-driven strategy, risk, portfolio, broker/exchange adapter, backtest and live lifecycle interfaces be structured?

They are complementary references, not interchangeable engines.

---

## 9. Proposed Finance AI / MPFM target architecture

### 9.1 Logical modules

~~~text
A. MARKET AND REFERENCE DATA PLANE
   Provider entitlement registry
   Exchange/broker source adapters
   Instrument/security/contract master
   Corporate actions + trading calendars
   Feed sequence, timestamp and gap validation
   Immutable raw event archive

B. CANONICAL EVENT AND STATE PLANE
   Canonical trades, quotes, bars, depth and external events
   Event-time / receive-time / availability-time semantics
   Order-book reconstruction (only where licensed depth exists)
   Event replay and snapshots

C. RESEARCH AND FEATURE PLANE
   Cleaning and quality gates
   Point-in-time feature engine
   Microstructure feature engine
   Dataset/label/target versioning
   Experiment registry and reproducibility

D. MPFM PREDICTIVE INTELLIGENCE
   Financial State Encoder
   Specialist heads: return, direction, volatility, liquidity, regime
   Market-dynamics/world-model research
   Philosophy / mandate adapters (optional downstream)
   Forecast distributions and calibration

E. DECISION AND RISK PLANE
   Strategy intent / target exposure
   Account, portfolio and inventory state
   Pre-trade checks and risk limits
   NO_TRADE / reject / reduce / halt controls

F. EXECUTION PLANE (LATER)
   Order Management System
   Execution algorithms: market/limit/TWAP/VWAP/POV etc.
   Venue/broker adapters
   Order/fill/reject event ledger
   Reconciliation and post-trade analytics

G. CONTROL AND OPERATIONS PLANE
   Audit and experiment lineage
   Service/market-data/latency observability
   Drift, model health and data-quality monitoring
   Emergency stop and trading-state control
~~~

### 9.2 Canonical event schema — minimum proposal

Every event should be traceable and reconstructible. A generic envelope should include:

| Field | Purpose |
|---|---|
| event_id | Stable unique event identity |
| event_type | TRADE, QUOTE, BOOK_DELTA, BOOK_SNAPSHOT, BAR, CORPORATE_ACTION, NEWS, ORDER_ACK, FILL, CANCEL, REJECT, etc. |
| source_id / source_version | Provider and adapter provenance |
| venue / segment | Exchange and segment |
| instrument_id | Canonical Finance AI instrument identity |
| exchange_timestamp | Venue event timestamp, if supplied |
| receive_timestamp | Local capture timestamp |
| availability_timestamp | When the observation is legally/technically available to the model |
| sequence_number | Source/venue sequence identity, when supplied |
| schema_version | Contract version |
| payload | Typed event body |
| quality_flags | Gap, stale, delayed, incomplete, corrected or inferred flags |
| entitlement_reference | Link to source/data-use permission record |

Do not collapse exchange time, ingestion time and model availability time into one timestamp. The current multimodal code's availability-time join semantics must be preserved.

### 9.3 Instrument master expansion

The current instrument registry is too small for multi-market equities + derivatives. A later canonical instrument contract should support:

- Stable internal instrument_id and historical symbol mapping.
- Exchange, segment, market, currency and country.
- ISIN or other authoritative security identifier where available.
- Instrument class and trading status.
- Tick size, lot size, multiplier, quantity/price precision.
- Expiry, strike, option type, underlying and contract generation for derivatives.
- Valid-from / valid-to and source provenance.
- Corporate action and symbol-change lineage.
- Trading calendar and session template.
- Broker-specific instrument token mappings, kept separate from canonical identity.

This should be designed in the existing Security Master / D1-related work rather than patched independently into every model.

### 9.4 Order-management contract

When an execution system is eventually designed, represent every order with immutable identity and an explicit state lifecycle. A possible state graph:

~~~text
INTENT_CREATED
   -> RISK_APPROVED
   -> SUBMITTING
   -> ACKNOWLEDGED
   -> PARTIALLY_FILLED <-> PARTIALLY_FILLED
   -> FILLED

Other terminal/exception states:
REJECTED
CANCEL_PENDING -> CANCELLED
REPLACE_PENDING -> REPLACED / REJECTED
EXPIRED
UNKNOWN_OUTCOME -> RECONCILIATION_REQUIRED
RECONCILED
~~~

The UNKNOWN_OUTCOME state is essential: a network timeout after submit must not be treated as proof that the venue rejected or accepted the order. Query/reconcile using stable client order identifiers and venue reports before retrying. Duplicate submissions must be controlled through idempotency and explicit state.

This is a future design contract, not an implemented Finance AI OMS.

---

## 10. Recommended tool strategy for this repository

### 10.1 What to keep

- Python for the existing research and orchestration plane.
- Current feature registry, dataset versioning, leakage tests, point-in-time joins, model registry, retraining gates and research API.
- Parquet/Arrow-oriented historical artifacts.
- Existing FastAPI + React/Vite dashboard as the control/visualization plane.
- Current file-backed design until a database requirement has been justified and approved.

### 10.2 What to add only after proof

| Capability gap | First candidate to evaluate | Trigger for evaluation |
|---|---|---|
| Large Parquet research scans | DuckDB and Polars | Pandas memory/runtime becomes a measured bottleneck |
| Live time-series query/ingestion | QuestDB | Licensed event feed and concurrent live queries arrive |
| Durable multi-consumer event stream | Kafka | Independent ingestion, feature, analytics and recording consumers require retained replay |
| Lightweight service messaging | NATS | Several services need operational command/event routing |
| Low-latency IPC/multicast transport | Aeron | A real co-location / latency feasibility case and measured transport bottleneck exist |
| Unified event-driven order/backtest engine | NautilusTrader isolated POC | Prediction and data foundations pass; execution lifecycle scope is approved |
| Specialist HFT replay | HftBacktest | Licensed L2/L3 history and queue/latency experiment are available |
| Agent-based market simulation | ABIDES | Calibrated synthetic participant/counterfactual experiments are needed |
| Quant research factor workflows | Qlib | A controlled benchmark shows value beyond our current experiments |
| Experiment dashboard/tracking | MLflow | Existing experiment artifact discovery/comparison is inadequate |
| Feature serving | Feast | Multiple production consumers require offline/online serving and we can prove preservation of our availability-time semantics |

### 10.3 Explicit non-recommendations at this stage

- Do not migrate the complete platform to Rust or C++ now.
- Do not replace the MPFM model research with FinRL/FinRL-X.
- Do not adopt NautilusTrader and HftBacktest as two competing full platforms.
- Do not treat Hummingbot as an Indian market gateway.
- Do not put LLM calls in a deterministic execution hot path.
- Do not start Kafka, NATS, Aeron, PostgreSQL, QuestDB, ClickHouse and MLflow together.
- Do not move to FPGA/ASIC/kernel-bypass until a measured latency-sensitive strategy and its economic case exist.
- Do not run multimodal or world-model experiments on synthetic fixtures and report them as real-market evidence.
- Do not permit a model to bypass the independent risk engine.

### 10.4 Licence and dependency controls

| Project | Repository licence visible in reviewed material | Note |
|---|---|---|
| NautilusTrader | LGPL-3.0 | Obtain legal review for embedding/linking, distribution and modifications |
| HftBacktest | MIT | Keep attribution/licence obligations; market data has separate licensing |
| ABIDES | BSD 3-Clause | Preserve notices; synthetic data/agent assumptions still require documentation |
| LEAN | Apache-2.0 | Preserve licence/NOTICE requirements |
| Hummingbot | Apache-2.0 | Preserve licence/NOTICE requirements |
| FinRL-X | Apache-2.0 | Model weights/data and third-party dependencies need separate review |
| Qlib | MIT | Review any model/data artifacts separately |
| QuestDB | Apache-2.0 | Confirm the exact community/enterprise feature boundary in the selected release |

Open-source software rights do not grant market-data rights, exchange permissions, broker API access or rights to model weights/datasets distributed separately from the source code. Run a software bill of materials and a dependency licence scan before production distribution.

---

## 11. Implementation and research sequence

This work must respect the already-confirmed development order D0 → D1 → D2 → D3 → D4. This document does not infer a one-to-one allocation of every module to each D-code because the recovered backlog does not preserve that mapping reliably.

### Stage A — architecture and feasibility, in parallel with the approved backlog where non-blocking

1. Maintain a source/entitlement register for each exchange, vendor and broker.
2. Create an OSS evaluation ledger with exact repository, version/commit, licence, dependencies, supported data granularity, market adapters, test evidence and integration cost.
3. Reproduce simple order-flow features and non-neural baselines on public/authorized data only.
4. Define the initial prediction horizons and target contract separately from execution.
5. Draft a canonical market-event and instrument schema; validate it against the existing code and data-rights constraints.
6. Keep patent/FTO/licensing work with the required legal specialist.

### Stage B — build on D0 → D4 foundations

- Preserve the user's D0 → D4 sequence.
- Expand the point-in-time/security/corporate-action foundation according to the accepted backlog.
- Continue philosophy ontology, licensing and baseline research in parallel where dependencies permit.
- Add intraday and microstructure capabilities only after data rights, instruments and timestamp semantics are accepted.
- Keep MPFM representation/world-model experiments later than the reliable point-in-time foundation.

### Stage C — isolated microstructure POC

Only after licensed data is available:

1. Select one instrument family and one session/calendar.
2. Capture a small, complete L1/L2/L3 or tick dataset with rights recorded.
3. Validate sequence gaps, timestamps, book reconstruction and event replay.
4. Establish simple baselines: mid-price return, spread, depth imbalance, order-flow imbalance and volatility.
5. Compare linear/logistic models, tree models and simple temporal baselines.
6. Use HftBacktest to stress feed/order latency, queue and fee assumptions; quantify the no-market-impact boundary.
7. Optionally use ABIDES to test a calibrated, clearly labelled agent-interaction hypothesis.
8. Reject any apparent edge that disappears under reasonable queue, cost, latency or regime perturbations.

### Stage D — event-driven execution proof of concept

Only after strategy value and legal route are established:

1. Benchmark an isolated NautilusTrader integration against the existing research/paper API.
2. Map canonical Finance AI instrument identity into engine instrument definitions.
3. Define a strict order-intent contract and independent pre-trade risk gateway.
4. Implement one permitted adapter in paper/sandbox mode only.
5. Test submit, ack, partial fill, cancel, replace, reject, timeout, reconnect, restart and reconciliation.
6. Compare simulator fills with paper/shadow outcomes and document discrepancy.
7. Require a separate legal, operational and risk approval before any live pilot.

### Acceptance gates before an execution engine can be called production-ready

- Licensed data and broker/exchange route confirmed in writing.
- No gaps or silent data corruption in the accepted test corpus.
- Instrument precision/lot/expiry/tick-size checks enforced.
- Feed disconnect and recovery behaviour tested.
- Order idempotency and unknown-outcome reconciliation tested.
- Partial fills and order state transitions tested.
- Pre-trade notional, position, loss, exposure and rate limits tested.
- Emergency disable / cancel-all / trading halt tested.
- Independent end-to-end audit ledger exists.
- Shadow/paper discrepancies are within pre-registered tolerances.
- No forecast or execution profitability claim without robust out-of-sample and operational evidence.

---

## 12. Open research questions

1. Which Indian-market data vendor can legally provide enough historical L2/L3/tick depth for research, replay, training and retention?
2. Does our intended initial user workflow actually need HFT, or is a slower, cost-aware predictive system economically more plausible?
3. Which market and horizon have enough stable signal after realistic costs?
4. Can order-flow features add incremental predictive value over our existing price/volume baselines?
5. How much do results depend on queue assumptions, feed latency and execution timing?
6. What market-impact model is credible for our intended order size and participation rate?
7. Which event-driven execution engine can be integrated without compromising our point-in-time research contracts and data provenance?
8. What exact broker/exchange approval and operating controls apply to the selected personal/API trading route?
9. Which OSS licences and model/data licences fit the project's intended future use?
10. Can a simulated market/world model be calibrated well enough to support counterfactual claims, or will it remain a controlled research tool only?

---

## 13. Current decision register

| ID | Decision | Status |
|---|---|---|
| HFT-01 | Finance AI remains a prediction-first multi-market intelligence platform; HFT is a separate lane | Proposed recommendation |
| HFT-02 | Keep prediction, mandate, risk and execution boundaries separate | Consistent with accepted architecture decisions |
| HFT-03 | Preserve D0 → D1 → D2 → D3 → D4 sequence | Previously confirmed |
| HFT-04 | Do not adopt a new execution engine before data rights, target scope and isolated integration proof | Proposed recommendation |
| HFT-05 | NautilusTrader is the leading event-driven execution architecture candidate to evaluate | Research shortlist only |
| HFT-06 | HftBacktest is the leading specialist market-replay/queue/latency candidate | Research shortlist only |
| HFT-07 | ABIDES is an agent-based simulation reference, not production execution | Research shortlist only |
| HFT-08 | Qlib/FinRL-X are quant research references, not replacements for MPFM | Research shortlist only |
| HFT-09 | Keep the current Parquet/file-backed research foundation until a measured workload justifies a database | Consistent with current ADR; revisit through ADR |
| HFT-10 | Do not claim HFT capability, real-market microstructure validation or profitability from the current repository | Required status discipline |

## 14. Primary source register

### Company operating model and technology

- Optiver — https://www.optiver.com/what-we-do/technology/
- Optiver — https://www.optiver.com/what-we-do/
- Hudson River Trading — https://www.hudsonrivertrading.com/machine-learning/
- Jane Street — https://www.janestreet.com/technology/
- Jane Street low-latency engineering — https://www.janestreet.com/join-jane-street/position/6254435002/
- IMC — https://www.imc.com/in/what-we-do/technology
- Jump Trading — https://www.jumptrading.com/technology
- Virtu — https://www.virtu.com/market-making/

### Open-source repositories and documentation

- NautilusTrader — https://github.com/nautechsystems/nautilus_trader
- NautilusTrader architecture — https://nautilustrader.io/docs/latest/concepts/architecture/
- NautilusTrader backtesting — https://nautilustrader.io/docs/latest/concepts/backtesting/
- NautilusTrader fill models — https://nautilustrader.io/docs/latest/concepts/backtesting/fill-models/
- HftBacktest — https://github.com/nkaz001/hftbacktest
- HftBacktest latency — https://hftbacktest.readthedocs.io/en/latest/latency_models.html
- HftBacktest order fill — https://hftbacktest.readthedocs.io/en/latest/order_fill.html
- ABIDES — https://github.com/abides-sim/abides
- LEAN — https://github.com/QuantConnect/Lean
- Hummingbot — https://github.com/hummingbot/hummingbot
- FinRL-X — https://github.com/AI4Finance-Foundation/FinRL-Trading
- Qlib — https://github.com/microsoft/qlib
- QuestDB — https://github.com/questdb/questdb
- NATS — https://docs.nats.io/
- Aeron — https://aeron.io/docs/
- Apache Kafka — https://kafka.apache.org/documentation/

### Academic and Indian-market references

- Deep order flow imbalance — https://onlinelibrary.wiley.com/doi/full/10.1111/mafi.12413
- NSE real-time data — https://www.nse.in/static/market-data/real-time-data-subscription
- NSE Data Sharing & Usage Policy — https://www.nseindia.in/static/market-data/nse-data-policy
- SEBI retail algo circular — https://www.sebi.gov.in/legal/circulars/feb-2025/safer-participation-of-retail-investors-in-algorithmic-trading_91614.html
- SEBI implementation timeline extension — https://www.sebi.gov.in/sebi_data/attachdocs/sep-2025/1759232056254.pdf
- NSE algo / decision-support information — https://www.nseindia.com/static/trade/platform-services-non-neat-decision-support-tools-algorithm-trading

---

## 15. Final engineering recommendation

**Do not build an HFT clone first. Build the foundation that makes a trading system trustworthy.**

The immediate priority remains the agreed D0 → D1 → D2 → D3 → D4 programme and its point-in-time financial foundation. In parallel, use this research to prepare a canonical event schema, data entitlement ledger, OSS integration scorecard and one bounded microstructure research specification.

When the data, permission, signal and economic case exist, run two isolated proofs:

1. HftBacktest/ABIDES for microstructure and simulation research.
2. NautilusTrader for event-driven execution architecture and paper lifecycle.

Only a measured result should decide whether any component is adopted. Our target is not to collect the largest number of technologies; it is to assemble the smallest reliable system whose forecasts, decisions, fills and operational state can all be independently explained and reproduced.
