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
