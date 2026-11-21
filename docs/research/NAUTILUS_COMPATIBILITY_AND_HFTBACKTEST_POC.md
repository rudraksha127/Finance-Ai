# NautilusTrader Compatibility Audit and HftBacktest Microstructure POC

**Research date:** 2026-11-21  
**Repository:** rudraksha127/Finance-Ai  
**Scope:** Source-level compatibility analysis and proposed experiments only  
**Implementation status:** No execution engine, Indian venue adapter or HFT model was added by this document.

> Purpose: decide how Finance AI could use NautilusTrader and HftBacktest without replacing the existing MPFM research foundation, fabricating support for Indian venues, or bypassing the agreed D0 → D1 → D2 → D3 → D4 sequence.

---

## 1. Executive decision

### 1.1 Recommendation

Do not replace the current Finance AI research pipeline with NautilusTrader. Do not wire HftBacktest into the daily backtesting path yet.

Use a two-engine, bounded evaluation strategy:

1. Keep Finance AI as the canonical research, data-governance, point-in-time feature, model-training, prediction, experiment/model-registry and MPFM platform.
2. Evaluate NautilusTrader as an isolated event-driven trading/execution engine that could consume approved Finance AI forecasts and canonical market events.
3. Evaluate HftBacktest as a specialist microstructure replay laboratory only after acquiring suitable historical depth/trade events with usable exchange and local receive timestamps.
4. Keep ABIDES as a separate synthetic agent-interaction/world-model research tool. Do not merge synthetic agent outcomes with empirical market-data results.
5. Keep all new execution work in backtest, replay, paper, shadow or manual-approval modes until data route, permission, operational and compliance gates are independently accepted.

### 1.2 Candidate role matrix

| Component | Recommended responsibility | Do not use it for |
|---|---|---|
| Finance AI / MPFM | Financial data governance, point-in-time datasets, forecasting, financial state learning, experiment/model registry, predictive research | Pretending to be a low-latency venue gateway |
| NautilusTrader | Event-driven strategy runtime, portfolio/order state, risk and execution lifecycle, paper/sandbox execution, reconciliation interfaces | Replacing Finance AI research/data contracts or proving alpha |
| HftBacktest | Tick/depth replay, feed/order latency experiments, queue-position and fill sensitivity studies | Live Indian broker execution or market-impact ground truth |
| ABIDES | Controlled multi-agent market simulation and counterfactual hypotheses | Empirical validation or real-market PnL claims |
| Finance AI web/API | Research control plane, forecasts, human-readable explanations, approvals and operations | Time-critical hot-path execution |

### 1.3 Adoption status

| Candidate | Status after this review |
|---|---|
| NautilusTrader | Leading event-driven architecture candidate; isolated integration spike only |
| HftBacktest | Leading queue/latency replay candidate; wait for suitable permitted event data |
| ABIDES | Research-only simulator candidate |
| Current Finance AI backtest | Preserve as the historical baseline; expand only through separately tested execution-model versions |
| Indian live data/broker integration | Not established by this review |
| Live order execution | Not authorized or implemented |

---

## 2. Exact Finance AI interface audit

The following current repository files were reopened and inspected for this compatibility pass.

### 2.1 Existing data-source contract

Source: src/data/sources/base.py

The current source protocol is historical and deliberately small:

- FetchParams: instrument, start, end, interval.
- Supported interval type is documented as 1d | 1wk | 1mo.
- FetchedData: source name, canonical ticker, interval, requested date range, tuple of record mappings and dropped count.
- HistoricalDataSource.fetch(params) returns provider-neutral historical records.
- Records contain ISO date timestamps and OHLCV values, with optional adjusted close.

This is suitable for historical bar ingestion, but does not express:

- Quote ticks or trade ticks.
- Incremental order-book deltas or full snapshots.
- Exchange sequence numbers.
- Exchange and local receive timestamps at sub-second resolution.
- Bid/ask depth levels, order IDs or aggressor-side semantics.
- Feed-gap recovery and snapshot/delta synchronization state.
- Order acknowledgements, fill events or execution reports.

**Compatibility conclusion:** do not overload HistoricalDataSource to become the real-time feed protocol. Add separate contracts for streaming market data, historical event data and execution reports. Preserve the current historical adapter boundary.

### 2.2 Existing instrument identity contract

Source: src/data/instruments.py

The present InstrumentRecord contains only:

- ticker
- is_active
- optional exchange
- first_seen

The registry is file-backed and idempotent by ticker. The docstring explicitly describes it as a minimal subset of the future data architecture.

It is not sufficient as a multi-market instrument master. A production-capable identity contract must also handle:

- Stable Finance AI instrument_id.
- Exchange, segment, currency and instrument class.
- ISIN or other authoritative security identifier, where available.
- Symbol and venue-token mapping history.
- Trading status and valid-from/valid-to times.
- Tick size, lot size, multiplier, quantity/price precision.
- Expiry, strike, option type, underlying and contract generation for derivatives.
- Trading calendar/session template.
- Corporate-action and symbol-change lineage.
- Provider provenance and last-verification timestamp.

**Compatibility conclusion:** NautilusTrader Instrument objects should be generated from an authoritative Finance AI instrument master through a dedicated mapping layer. Do not treat a provider symbol/token as canonical identity. Broker tokens are provider-specific aliases.

### 2.3 Existing prediction-to-signal contract

Sources: src/backtest/signals.py, src/api/decision.py, src/api/orchestrator.py

Current decision behavior:

- BUY when P(UP) >= buy_threshold and P(UP) >= P(DOWN).
- SELL when P(DOWN) >= sell_threshold and P(DOWN) > P(UP).
- Otherwise NO_TRADE.
- The tie-break is explicit and deterministic.
- The API prediction interval is 1d only.
- The response can expose a placeholder position_size=1.0 for non-NO_TRADE results.
- The API mode live is deliberately refused by the current service.
- The current forecast is classification-probability output, not a complete expected-return distribution, target-price model or order policy.

This signal contract is a model-research interface, not a broker order command.

**Compatibility conclusion:** do not translate BUY directly to submit_order(). Insert a separate strategy-intent contract that carries model/version lineage, horizon, forecast distribution (when available), signal expiry, evidence and uncertainty. Then apply strategy policy and risk checks before creating any order proposal.

### 2.4 Existing backtest execution contract

Sources: src/backtest/execution.py, src/backtest/engine.py

The current simulator explicitly implements:

- Long-only LONG/FLAT position states.
- Fixed quantity and one position at a time.
- Entry at the close of the signal day.
- Exit at the close of the exit day.
- SELL or maximum holding-period exit, with documented precedence.
- Fixed per-side basis-point cost assumption.
- End-of-period force close.
- A trade ledger and daily equity series.

It is not an order lifecycle engine. It does not model:

- Order acknowledgement/rejection/timeout.
- Partial fills and residual leaves quantity.
- Cancel/replace state transitions.
- Market depth consumption.
- Order queue position.
- Feed and order latency.
- Broker/exchange reconciliation.
- Multiple concurrently working orders.
- Order-level market impact or capacity.

**Compatibility conclusion:** retain the existing simulator as the frozen historical baseline. A later event-driven execution engine must have its own version, reports and acceptance criteria. Do not silently replace the baseline execution convention.

### 2.5 Existing architecture and engineering constraints

Sources: docs/DECISIONS.md, docs/ENGINEERING_CONSTITUTION.md, docs/CURRENT_STATE.md

Relevant accepted constraints:

- Python is the primary language for the current project (ADR-0002).
- The MVP uses file-backed CSV/Parquet rather than a live transactional database (ADR-0005).
- The MVP originally restricted cloud/external dependencies (ADR-0007).
- Prediction, decision and execution are separate concerns (ADR-0020).
- Point-in-time availability and leakage controls are non-negotiable in the research layer.
- The agreed development priority remains D0 → D1 → D2 → D3 → D4.
- The recovered backlog does not preserve a reliable one-to-one mapping of every subsystem to the D0–D4 codes; this document does not invent one.

NautilusTrader or HftBacktest integration therefore requires a new, explicit architecture decision after an isolated proof of compatibility. This research note does not supersede accepted ADRs.

---

## 3. NautilusTrader: what maps cleanly and what needs engineering

Official documentation describes NautilusTrader as a Rust core with a Python/PyO3 control surface. The Python layer supports configuration, user components and integration with the Python ecosystem; the Rust core owns domain types, engines, nodes, cache, portfolio, message bus and adapter/runtime components.

### 3.1 Conceptual mapping

| Finance AI capability/interface | NautilusTrader component or contract | Mapping effort | Notes |
|---|---|---:|---|
| Provider-neutral historical bars | DataClient / historical request and Bar data types | Medium | A source adapter must convert provider data into valid instrument/bar definitions |
| Future streaming trades/quotes/depth | DataClient and typed market-data events | High | Feed sequence, source timestamp, receive timestamp, gap recovery and entitlement metadata need explicit handling |
| Finance AI instrument master | InstrumentProvider + Nautilus Instrument definitions | High | Add a stable identity mapper; exchange/broker symbol tokens remain aliases |
| Finance AI feature/model prediction | CustomData / actor/strategy input | Medium | Do not force model forecasts into quote or trade data types |
| Current BUY/SELL/NO_TRADE | Strategy policy input | Medium | Signal becomes a candidate intent, not automatically an order |
| Finance AI risk policy | Custom portfolio/risk policy plus Nautilus RiskEngine | High | Engine risk checks complement, but do not replace, project-specific capital, daily-loss and strategy policy gates |
| Order submission/modification/cancel | ExecutionClient | High | A custom India broker adapter would need exact command and order-event semantics |
| Broker positions, order book and fills | ExecutionClient report methods and reconciliation | High | Must reconcile ambiguous outcomes, duplicates, partial fills and external orders |
| Historical backtesting | Nautilus backtest engine | Medium | New execution assumptions must be compared against current Finance AI baseline |
| Research dashboard | Existing React/Vite application | Low/Medium | Dashboard should consume read APIs and audit results, not own engine state |

### 3.2 Why custom adapters are possible

Current official NautilusTrader documentation describes a Python adapter interface:

- A custom package can subclass DataClient for data subscriptions and historical requests.
- A custom package can subclass ExecutionClient for order commands, account updates and reconciliation reports.
- The custom adapter can register factories/configurations with a LiveNode.
- It can run alongside official adapters without rebuilding NautilusTrader.
- Python clients communicate with the Rust engine through typed objects and the node's Python event loop.
- An independent Rust/PyO3 package is another option later, but should not be the initial path without a measured reason.

This is a useful integration path: Finance AI could retain Python orchestration and use NautilusTrader's Rust engine under the documented Python adapter contract.

Official references:

- Python API/runtime: https://nautilustrader.io/docs/latest/concepts/python/
- Python custom adapter interface: https://nautilustrader.io/docs/latest/developer_guide/python_adapters/
- Adapter concepts: https://nautilustrader.io/docs/latest/concepts/adapters/
- Adapter developer guide: https://nautilustrader.io/docs/latest/developer_guide/adapters/
- Architecture: https://nautilustrader.io/docs/latest/concepts/architecture/

### 3.3 India venue/broker support gap

The official adapter list reviewed for this study includes adapters for venues/providers such as Binance, Bybit, Coinbase, Deribit, Interactive Brokers, Kraken, OKX, Databento and Tardis. It does not list NSE, BSE, MCX, Upstox, Angel One, Zerodha, Dhan or Groww as official adapters.

That does not prevent an independently written adapter, but it means Finance AI would own:

- API change tracking and maintenance.
- Authentication/token lifecycle.
- Instrument/contract mapping.
- WebSocket/REST data transport.
- Market-session and exchange-specific semantics.
- Order-type/quantity/price validation.
- Rate limits and error classification.
- Order acknowledgement and fill correlation.
- Reconnect, replay and recovery.
- Startup and periodic account/order/position reconciliation.
- Broker-specific testing and operational support.

**Do not infer adapter support from the fact that a broker has an HTTP/WebSocket API.** It must satisfy NautilusTrader's actual typed data, execution and reconciliation contract.

### 3.4 Required adapter split

Do not create one giant IndianBrokerAdapter that mixes all venues and providers.

Proposed adapter boundaries:

1. FinanceAIHistoricalDataClient — historical bars/events from approved research sources.
2. NSEMarketDataClient — exchange-approved NSE market data, with data level/capability in configuration.
3. BSEMarketDataClient — only after an authorized feed and schema are selected.
4. MCXMarketDataClient — commodity contracts, feed-level capability and exchange calendar semantics.
5. UpstoxExecutionClient, AngelOneExecutionClient, etc. — separate account/order adapters, each with a broker capability manifest.
6. PaperExecutionClient — deterministic paper simulation for adapter and lifecycle tests.

Exchange market data and broker execution should remain separate. A broker account connection must not silently become the market-data source for all research.

### 3.5 Proposed capability manifest

For each adapter/account/segment, record a machine-readable manifest:

- market_data: trades, quotes, bars, L1/L2/L3/tick-by-tick, depth size, historical lookback.
- execution: order types, time-in-force, modify/cancel, bracket/conditional support, fractional/lot rules.
- account: balances, margin, positions, order book, trade book.
- limits: requests/sec, subscriptions, instruments/connection, order limits and session restrictions.
- timestamps: exchange timestamp, provider timestamp, local receive timestamp, sequence number.
- identity: instrument token mapping, contract master and refresh policy.
- rights: display, non-display algorithmic use, storage, training, derived use and redistribution.
- tested_release: adapter version, broker API version, test date and known limitations.

A feature may only be used when the manifest says it is supported and the relevant permission has been recorded.

---

## 4. NautilusTrader integration spike: exact scope and acceptance

### 4.1 POC-NTR-00 — isolated dependency and runtime spike

**Goal:** verify that the current supported Finance AI Python environment can coexist with a pinned NautilusTrader release in a separate environment/package.

Tasks:

- Pin one NautilusTrader version and Python/runtime version.
- Record OS, CPU, Python ABI, wheel availability and transitive dependency footprint.
- Start and dispose a single backtest node.
- Register one minimal custom data type and one deterministic strategy.
- Feed a small synthetic/fixture event set.
- Verify deterministic callbacks, timestamps and clean teardown.
- Run no live connection and no broker credentials.

Acceptance:

- Reproducible lockfile/environment manifest.
- No changes to current Finance AI dependencies or runtime.
- Event callback order is deterministic for the fixed fixture.
- Node disposal and sequential node recreation pass.
- The result can be run in CI or a documented isolated environment.

### 4.2 POC-NTR-01 — Finance AI canonical instrument mapping

**Goal:** map one canonical Finance AI instrument to one Nautilus instrument definition.

Tasks:

- Define the Finance AI canonical instrument ID and venue/symbol alias.
- Map asset class, currency, tick size, lot size, multiplier, precision and trading calendar.
- Verify symbol/token remapping is versioned and as-of date aware.
- Validate a derivative contract with expiry/strike/option type only after a real contract-master source is approved.

Acceptance:

- One identity maps consistently across historical and synthetic event fixtures.
- Duplicate aliases do not create duplicate canonical instruments.
- Invalid tick/lot/precision/expiry is rejected.
- Mapping history can reproduce the instrument definition used by an old backtest.

### 4.3 POC-NTR-02 — Finance AI forecast as custom event data

**Goal:** pass a frozen Finance AI forecast into a Nautilus strategy without confusing it with market data.

Proposed ForecastEvent fields:

| Field | Meaning |
|---|---|
| forecast_id | Stable unique forecast identity |
| instrument_id | Canonical Finance AI instrument identity |
| forecast_ts | Time the forecast was produced |
| asof_ts | Latest information-availability cutoff used by the forecast |
| horizon | Explicit horizon and target interval |
| model_id / model_version | Exact model lineage |
| dataset_version / feature_version | Research lineage |
| target_definition_version | Exact target/label contract |
| class_probabilities | Optional calibrated UP/DOWN/SIDEWAYS probabilities |
| expected_return_distribution | Optional distribution/quantiles; absent until implemented and validated |
| volatility_forecast | Optional forecast |
| uncertainty/calibration_id | Reliability/calibration lineage |
| signal | BUY/SELL/NO_TRADE candidate output |
| expires_at | Hard signal expiry |
| quality_flags | Stale, degraded, out-of-distribution, incomplete-input etc. |

Acceptance:

- Forecast is rejected when as-of time is in the future, stale, or version lineage is missing.
- Duplicate forecast IDs are idempotently ignored.
- Expired forecast cannot produce a new trade intent.
- Model/version/data lineage remains visible in the strategy and audit record.
- Missing optional outputs stay missing; do not fabricate expected return or volatility.

### 4.4 POC-NTR-03 — deterministic strategy and mock execution

**Goal:** prove event and order lifecycle compatibility without an external broker.

Use only deterministic fixtures and mock/paper execution:

- Forecast event triggers candidate intent.
- Separate strategy policy validates direction, horizon and expiry.
- Risk engine validates instrument and order constraints.
- Mock execution client produces acknowledgement, partial fill, fill, cancel or reject.
- Position/portfolio state updates from events.
- The same sequence can be replayed and audited.

Acceptance test cases:

1. Order accepted and fully filled.
2. Order accepted and partially filled.
3. Partial fill followed by cancel of remainder.
4. Local validation rejection before submission.
5. Venue rejection after submission.
6. Timeout with unknown result followed by report/stream reconciliation.
7. Duplicate fill report.
8. Out-of-order status and fill updates.
9. Process restart with active order and position recovery.
10. Order/position mismatch detected and quarantined.
11. Kill-switch prevents all new order commands.
12. Signal expiry before submission prevents order creation.

### 4.5 POC-NTR-04 — compare event-driven backtest to current Finance AI backtest

Use the same signal timestamps and target data in both engines where semantics can be aligned.

Compare:

- Signal count and timestamps.
- Entry/exit timing.
- Gross PnL.
- Brokerage/fees/spread/slippage.
- Partial fills and unfilled orders.
- Position/equity trajectories.
- Drawdown and trade ledger.
- Reasons for every divergence.

The purpose is not to force the engines to produce identical results. It is to document differences and establish a controlled, versioned execution-model change.

**NTR adoption gate:** only recommend adoption if the isolated POC proves meaningful value in order lifecycle, data replay, strategy simulation or reconciliation that cannot be achieved more safely/economically by a smaller in-house extension.

---

## 5. HftBacktest: exact data requirements

HftBacktest is not a generic OHLCV backtester. It is designed for event-level market replay, feed/order latency and order-queue-aware fill simulation.

### 5.1 Documented input schema

The current documentation describes an eight-field NumPy structured event array:

| Field | Meaning | Finance AI source requirement |
|---|---|---|
| ev | Event-type and flag bit field | Explicit mapping of depth update, trade, clear and snapshot events |
| exch_ts | Exchange event timestamp | Authoritative exchange timestamp if included in the licensed feed |
| local_ts | Local receive timestamp | Captured timestamp at the actual feed receiver |
| px | Price | Decimal precision and tick-size mapping |
| qty | Quantity | Correct quantity/lot semantics |
| order_id | Order ID, for L3 Market-by-Order data | Only if source legally supplies genuine order IDs |
| ival | Reserved integer field | Preserve only with documented source semantics |
| faval | Reserved float field | Preserve only with documented source semantics |

Official docs: https://hftbacktest.readthedocs.io/en/latest/data.html

The project also documents validation pitfalls:

- Local timestamps must be in correct order.
- local_ts - exch_ts is used for feed latency and therefore depends on valid clock synchronization.
- Exchange timestamps may not be in the same order as local receive timestamps.
- A feed event received later can carry an earlier exchange event timestamp.

Do not sort away these distinctions. Preserve both clocks and apply documented event-processing semantics.

### 5.2 Required source data

Minimum for a bar/quote-level intraday model:

- Exchange timestamp and local receive timestamp.
- Instrument and venue.
- Best bid/ask and sizes.
- Trade price/size and aggressor side, if supplied or reliably inferred.
- Session, sequence and data-quality markers.

Minimum for L2 replay:

- Initial depth snapshot.
- Incremental bid/ask price-level changes.
- Add/update/delete/clear semantics.
- Sequence numbers or enough protocol state to detect missing updates.
- Exchange and local receive timestamps.
- Tick size, lot size and instrument mapping.
- Trade events.

Minimum for L3 queue research:

- Genuine market-by-order event stream with order identifiers.
- Add, modify, cancel and execution events.
- Correct ordering and event semantics.
- Full or well-defined book initialization.
- Timestamp and sequence integrity.

Do not synthesize order IDs from L2 price levels. L2 market-by-price data is not L3 market-by-order data.

### 5.3 India-specific feed capability

The public exchange feed descriptions create different research ceilings:

- NSE publicly lists L1, L2, L3 and tick-by-tick products. L1 is best bid/ask; L2 is up to five best bid/ask levels; L3 is up to twenty best bid/ask levels; tick-by-tick is described as the full order book. Real-time delivery is multicast over a dedicated leased-line circuit.
- MCX publicly lists real-time L1 and L2: L1 touchline best bid/ask; L2 includes up to five best bid and five best ask levels. The cited public material does not establish an L3 order-by-order product.

Sources:

- NSE: https://www.nse.in/static/market-data/real-time-data-subscription
- MCX: https://classic.mcxindia.com/technology/datafeed
- MCX FAQ: https://www.mcxindia.com/faq/technology-services

Important: "full order book" or "20 levels" must not be silently equated with a market-by-order feed carrying individual order IDs. Before any HftBacktest L3 study, obtain the exact subscribed packet/schema documentation and confirm the supplied event granularity with the exchange/vendor.

### 5.4 Data licensing and permissions

Record written permissions for each dataset before acquisition/use:

- Research and backtesting.
- Algorithmic/non-display use.
- Model training and feature derivation.
- Local storage and retention duration.
- Historical reprocessing and backup.
- Derived features/outputs.
- Internal display.
- Redistribution or external display (not assumed).
- Access by software vendors/subprocessors, if any.
- Whether an instrument, exchange segment and product are included.

Market-data licensing is separate from the open-source license of HftBacktest or NautilusTrader. A broker API key does not establish exchange-wide data rights.

---

## 6. HftBacktest POC experiment programme

### 6.1 POC-HFT-00 — source-data admissibility and integrity

**Question:** do we have a lawful and technically reconstructible event feed?

Tests:

- Source agreement and permitted-use metadata attached to the dataset manifest.
- Instrument/contract mapping complete.
- Exchange/local timestamp units and timezone semantics confirmed.
- Feed sequence gaps and snapshot recovery tested.
- No negative/impossible price or quantity.
- Tick/lot precision checked.
- Duplicate, reordered and late events identified.
- Book reconstructed from snapshot + incremental events.
- Independent sample reconciliation against source/vendor reference output.

Acceptance: every interval has explicit quality status. A dataset with missing sequence ranges or invalid clock relation cannot be used in a queue/latency claim.

### 6.2 POC-HFT-01 — baseline microstructure features

Do not start with deep learning. Establish interpretable baselines first.

Candidate features:

- Mid-price and micro-price.
- Bid-ask spread in price and ticks.
- Top-of-book and multi-level depth imbalance.
- Order-flow imbalance (OFI).
- Signed trade flow / trade imbalance, only where aggressor-side semantics are defensible.
- Depth slope and liquidity concentration.
- Quote update intensity and cancellation intensity, only where the event feed exposes those operations.
- Short-horizon realized volatility and price-change intensity.
- Time-of-day/session features.
- Feed staleness and event-rate quality flags.

Candidate targets should be registered separately:

- Mid-price change after a specified number of events or supported time interval.
- Directional class with a neutral threshold.
- Return magnitude/quantiles.
- Spread/liquidity change.
- Volatility change.
- Fill probability/time-to-fill (only in the execution/queue experiment).

Do not force one target definition across NSE equities, index derivatives and MCX commodity contracts.

### 6.3 POC-HFT-02 — simple model comparison

Same dataset, same timestamps, same target and same chronological folds:

1. Persistence / no-change baseline.
2. Mid-price momentum baseline.
3. Linear/logistic regression on OFI and spread/depth.
4. Regularized tree/gradient-boosted baseline.
5. Simple stationary order-flow feature model.
6. Neural sequence model only after simple baselines and data-validity gates.

The 2023 paper "Deep order flow imbalance: Extracting alpha at multiple horizons from the limit order book" reports results on 115 Nasdaq stocks using granular order-book information. It found that neural models on stationary order-flow-derived inputs could outperform most models on raw order-book states in that study. This motivates a testable hypothesis, not a transfer claim for NSE/MCX.

Paper: https://onlinelibrary.wiley.com/doi/full/10.1111/mafi.12413

### 6.4 POC-HFT-03 — latency and queue sensitivity

Use measured data where available:

- Feed latency distribution from exchange and local receive timestamps.
- Order entry latency from request to venue/exchange processing timestamp, if provided.
- Order response latency from venue acknowledgement to local receipt.
- If only broker request/ack latency is available, label it as broker round-trip latency; do not call it exchange gateway latency.
- Queue model A: conservative risk-averse queue progression.
- Queue model B: probability-based queue progression.
- Fee model: maker/taker and direction-specific costs, using a date-versioned India fee schedule.
- Stress: observed p50/p95/p99 and multiples/perturbations of measured latency; do not invent a "realistic" latency constant.

HftBacktest documents RiskAverseQueueModel (queue advances on trades at the price) and probability-based queue models (queue position can advance on trades or decreases in displayed quantity, with an attempt to avoid double counting).

Official reference: https://hftbacktest.readthedocs.io/en/latest/reference/queue_models.html

### 6.5 POC-HFT-04 — strategy micro-simulation

Only after POC-HFT-00 to POC-HFT-03 pass:

- Compare signal-only directional strategy against an execution-aware strategy.
- If market-making is studied, model reservation price, spread, inventory skew, volatility and adverse selection separately.
- Include order placement, cancel/replace, time-in-force and queue assumptions.
- Measure partial-fill rate, fill time, adverse selection, inventory exposure and net economics.
- Stress spread widening, feed gaps, queue-model uncertainty, high volatility and order latency.
- Run identical strategies across conservative and optimistic simulation assumptions and report the full range.

A market replay simulator cannot establish the impact of our own orders on other market participants unless it has a separate, credible market-impact model. HftBacktest explicitly states that its replayed market is not changed by the hypothetical order and that market impact is not considered. Its own documentation says the assumption is that the strategy is small enough not to impact the market; discrepancies must be studied in real deployment context.

Official reference: https://hft.readthedocs.io/en/latest/order_fill.html

### 6.6 Mandatory experiment report

Every run must persist:

- Data vendor/source and legal-use reference.
- Raw dataset checksum and schema version.
- Instrument/contract master version.
- Feed/event coverage and sequence gap report.
- Exchange/local clock and latency diagnostics.
- Feature/target versions.
- Model and strategy code versions.
- Training/validation/test date/event boundaries.
- Queue/latency/fee/fill model names and parameters.
- Gross and net results.
- Fill rate, cancel/reject/partial-fill counts.
- Spread, realized spread, implementation shortfall and adverse selection.
- Net PnL and drawdown.
- Capacity/participation sensitivity.
- Regime and time-of-day breakdown.
- Failed runs and excluded data intervals.
- Confidence intervals / robustness protocol where enough observations exist.
- Explicit conclusion: PASS_FOR_NEXT_RESEARCH_STAGE, INCONCLUSIVE or REJECTED.

No fixed profitability threshold should be invented before the target, market, costs, sample size and risk budget are defined. A model must not be accepted because one fold or one backtest is profitable.

---

## 7. Critical simulator differences

| Question | NautilusTrader | HftBacktest | ABIDES |
|---|---|---|---|
| Primary purpose | Event-driven trading runtime and backtest/live engine | High-frequency market replay and execution-fill simulation | Agent-based market simulation |
| Market data | Multiple typed market-data forms; adapters | Tick/depth/trade events, L2 MBP and L3 MBO where available | Simulated exchange/order-book and agent messages |
| Latency | Event/live systems; simulation clock and configurable timing/fill assumptions | Explicit feed/order latency models | Configurable agent/exchange/network latency |
| Queue modelling | Fill model and queue-volume assumptions, depending on data/configuration | Conservative and probability queue models | Emerges from exchange agent/order-book and agent interactions |
| Market impact | Historical book is immutable in backtest; not full self-impact simulation | Explicitly no market impact in historical replay | Potentially modeled through interacting agents, but only under calibrated assumptions |
| Execution lifecycle | Strong order/portfolio/risk/reconciliation architecture | Specialized replay backtester with specific live prototypes | Research simulation, not production broker gateway |
| Finance AI use | Potential later execution runtime | Specialist microstructure experiment tool | Counterfactual/agent research |

References:

- NautilusTrader architecture: https://nautilustrader.io/docs/latest/concepts/architecture/
- NautilusTrader fill models: https://nautilustrader.io/docs/latest/concepts/backtesting/fill-models/
- HftBacktest queue models: https://hft.readthedocs.io/en/latest/reference/queue_models.html
- HftBacktest order fill: https://hft.readthedocs.io/en/latest/order_fill.html
- ABIDES: https://github.com/abides-sim/abides

---

## 8. Updated target integration architecture

~~~mermaid
flowchart TB
  subgraph FI["FINANCE AI / MPFM — RESEARCH AUTHORITY"]
    SRC["Approved historical / live source adapters"]
    MASTER["Canonical security & contract master"]
    EVENT["Canonical event archive + point-in-time store"]
    FEAT["Feature / microstructure feature engines"]
    MODEL["MPFM forecast models"]
    EXP["Experiments / model registry / validation"]
    SIGNAL["Versioned forecast & strategy-intent contract"]
  end

  subgraph MICRO["SPECIALIST REPLAY LAB"]
    HBT["HftBacktest"]
    DATAQ["Queue / latency / fee sensitivity"]
    AB["ABIDES (separate synthetic lane)"]
  end

  subgraph EXEC["EVENT-DRIVEN EXECUTION POC — ISOLATED"]
    ADAPTER["Custom Nautilus data adapter"]
    INST["Nautilus instrument provider"]
    BUS["Data engine / cache / message bus"]
    STRAT["Strategy policy / execution algorithm"]
    RISK["Independent risk gateway"]
    OMS["Order & execution engine"]
    PAPER["Paper / mock execution client"]
    REC["Reconciliation / event ledger"]
  end

  subgraph UI["FINANCE AI CONTROL PLANE"]
    DASH["Existing research dashboard"]
    APPROVE["Manual approval / operational controls"]
    AUDIT["Forecast-to-fill audit view"]
  end

  SRC --> MASTER
  MASTER --> EVENT
  SRC --> EVENT
  EVENT --> FEAT --> MODEL
  MODEL --> EXP
  EXP --> SIGNAL

  EVENT --> HBT --> DATAQ
  EVENT --> AB

  EVENT --> ADAPTER
  MASTER --> INST
  ADAPTER --> BUS
  INST --> BUS
  SIGNAL --> STRAT
  BUS --> STRAT --> RISK --> OMS --> PAPER --> REC

  SIGNAL --> DASH
  REC --> AUDIT
  DASH --> APPROVE --> RISK
~~~

**Separation rule:** HftBacktest and ABIDES are research/simulation lanes. They do not submit broker orders. NautilusTrader is only a future isolated execution-plane candidate. Finance AI remains the authority for instrument identity, point-in-time lineage, forecast provenance and experiment results.

---

## 9. Work package sequence and dependencies

This is a detailed candidate sequence for the tool evaluation. It does not replace or reorder the already-agreed D0 → D1 → D2 → D3 → D4 backlog.

| Work package | Work | Dependency | Output |
|---|---|---|---|
| WP-01 | Pin existing Finance AI baseline and preserve current backtest outputs | Current repository snapshot and tests | Baseline manifest |
| WP-02 | Canonical instrument contract design | D1/security-master work; official source schema | Instrument mapping proposal |
| WP-03 | Canonical event envelope design | D1/point-in-time foundation and data rights | Event schema + timestamp policy |
| WP-04 | Nautilus isolated runtime spike | Python compatibility and license review | Reproducible spike report |
| WP-05 | Nautilus instrument and custom-data mapping | WP-02, WP-04 | Instrument + ForecastEvent mapper |
| WP-06 | Mock execution/reconciliation spike | WP-04, order contract design | Lifecycle proof and fault-test report |
| WP-07 | HftBacktest data-admissibility review | Written feed rights and data dictionary | Source approval and conversion spec |
| WP-08 | Event reconstruction and integrity validation | WP-07 plus data capture | Quality-approved HftBacktest dataset |
| WP-09 | Simple order-flow baseline experiment | WP-08 | Baseline experiment card/report |
| WP-10 | Queue/latency/fee sensitivity | WP-09 and measured latency inputs | Robustness report |
| WP-11 | Strategy micro-simulation | WP-10, pre-registered hypothesis | Execution-aware simulation report |
| WP-12 | Adoption decision | Results, maintenance, license, security and operational cost | Adopt / defer / reject ADR proposal |

Parallel preparation is allowed only when it does not bypass dependencies. The D0 → D4 development order remains authoritative.

---

## 10. Go / no-go gates

### NautilusTrader POC go criteria

- Pinned release installs reproducibly without changing the current Finance AI runtime.
- Custom data can carry Finance AI forecast lineage without abusing market-data classes.
- Canonical instrument mapping is deterministic.
- Mock execution lifecycle covers unknown outcomes, partial fills, duplicate/out-of-order events and reconciliation.
- The existing Finance AI backtest remains unchanged and its results are still reproducible.
- A measurable benefit is demonstrated over an in-house adapter/state-machine alternative.
- LGPL-3.0 use and distribution implications have been reviewed before adoption.

### HftBacktest POC go criteria

- Source licence and intended algorithmic/training use are documented.
- Data dictionary confirms exact depth/order event semantics.
- Exchange and local timestamps are trustworthy and clock diagnostics are available.
- Snapshot/delta reconstruction and event sequence integrity pass.
- The event feed has sufficient depth granularity for the selected queue model.
- At least one simple non-neural baseline can be reproduced.
- Model/strategy remains useful under queue/latency/fee sensitivity.
- Market impact and order-size assumptions are explicitly bounded.
- No claim of L3 support unless genuine order-by-order IDs and event semantics are supplied.

### Stop conditions

Reject or defer the experiment if:

- Data rights prohibit the intended use.
- The feed lacks timestamps/sequence semantics needed for latency claims.
- Depth data is incomplete or unreconstructible.
- Results rely on future information or incorrect session alignment.
- The apparent edge disappears under plausible queue/cost/latency perturbations.
- The strategy cannot be reconciled with paper/shadow operational outcomes.
- Adoption would violate existing architecture constraints without an approved ADR.

---

## 11. Research questions to resolve next

1. Which provider can supply NSE tick-by-tick/order-book data suitable for research, training, local retention and non-display use?
2. Does that feed include market-by-price depth only, or actual market-by-order events with individual order IDs?
3. What exact MCX data level is available for the intended product and subscriber category? Public material describes only L1/L2 real-time levels.
4. What timestamp precision, exchange sequence and local receive-time capture can be retained?
5. Can a retail broker adapter supply the complete order/fill/position/report state required for safe reconciliation?
6. Which segment/broker/API route is approved for the required retail algo workflow under current SEBI/exchange rules?
7. What is the smallest market and horizon where microstructure data has a plausible edge after all costs?
8. Does NautilusTrader deliver enough incremental value to justify its operational and LGPL review burden?
9. What is our order size relative to displayed depth and traded volume, and when is price-taker replay no longer a defensible approximation?
10. Can paper/shadow data be used to calibrate fill and latency assumptions without claiming it represents the full exchange route?

---

## 12. Final recommendation

**Preserve Finance AI as the research and predictive-intelligence authority. Evaluate NautilusTrader as an optional event-driven execution subsystem. Use HftBacktest as a specialist replay laboratory only when the correct licensed data exists.**

Immediate next engineering output should be the canonical instrument/event schema and the adapter capability/entitlement register under the accepted D0 → D1 → D2 → D3 → D4 programme. In parallel, a no-broker-credential Nautilus runtime spike can validate Python compatibility. HftBacktest should remain blocked until an actual permitted depth/tick dataset is available.

Do not choose infrastructure because a leading HFT firm uses similar technology. Choose it only when our measured data, strategy, latency, risk and operational requirements justify it.
