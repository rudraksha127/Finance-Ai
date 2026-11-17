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
