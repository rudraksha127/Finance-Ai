# Market Data & Broker Integration Research

**Reviewed:** 2026-11-17  
**Scope:** source inventory, current official broker API documentation and data-rights boundaries.  
**Important:** this is technical due diligence, not confirmation that any account has been connected or that any provider has granted redistribution rights.

## 1. Existing source implementation and historical plan

### Implemented in the original MVP

| Source | Data | Recorded status |
|---|---|---|
| Yahoo Finance chart endpoint | Historical OHLCV, adjusted close and corporate-action-related fields | Implemented in the MVP adapter |
| Trading calendar | Exchange sessions, holidays and early closes | Calendar abstraction documented; see data-ingestion blueprint |
| Index series such as S&P 500, NASDAQ and Dow | Market/benchmark context | Referenced as data-architecture inputs; verify exact ingestion status before calling integrated |

The README documents Yahoo intervals 1d, 1wk and 1mo only. It does not provide the MVP with an intraday or real-time feed. Yahoo is described in the repository as an unofficial endpoint whose availability/format may change.

### Sources recorded as future extension points in the original ingestion blueprint

| Extension | Historical candidate sources | Intended data | Original status |
|---|---|---|---|
| Live WebSocket | Polygon.io, Alpha Vantage WebSocket, IEX Cloud | Trades, quotes, one-minute OHLCV | Placeholder; not in MVP |
| News and filings | NewsAPI, SEC EDGAR, RSS feeds | Headlines, articles, press releases, filings | Placeholder |
| Options | CBOE, Yahoo Finance Options, Polygon.io | Calls, puts, strikes, expiries, implied volatility | Placeholder |
| Macro | FRED, World Bank, IMF | GDP, CPI, rates, unemployment | Placeholder |
| Social sentiment | Twitter API, StockTwits, Reddit | Sentiment and social volume | Placeholder |
| Indian historical equities | NSE historical data | Daily Indian equity OHLCV | Listed as future/disabled in the original source blueprint |

These are historical candidates from the repository blueprint, not live integrations. Provider products, API names, access rules and commercial terms must be re-verified before implementation.

## 2. Official broker API documentation review

The Finance AI product concept previously displayed six broker connections: Upstox, Angel One, Zerodha, Dhan, FYERS and Groww. The screenshot/design establishes intended product scope only; it does not prove that any broker integration is implemented.

The following capabilities were visible in the official documentation reviewed on 2026-11-17:

| Broker | Official API evidence reviewed | Market-data / integration capabilities visible in docs | Important qualification |
|---|---|---|---|
| Upstox | [Developer API overview](https://upstox.com/developer/api-documentation/), [Market Data Feed V3](https://upstox.com/developer/api-documentation/v3/get-market-data-feed/), [Historical Candle V3](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/) | WebSocket market feed, historical candles, quotes, option-chain and other market-information endpoints; portfolio/orders/account endpoints are also documented | Older V2 historical/feed pages are marked deprecated or discontinued; implement against current V3 documentation, not stale endpoints |
| Zerodha | [Kite Connect product/API page](https://www.zerodha.com/products/api/), [Kite Connect V3 docs](https://kite.trade/docs/connect/v3/), [Historical candles](https://kite.trade/docs/connect/v3/historical/) | Live WebSocket streaming, historical candle API, orders, portfolio and account functions | Product page distinguishes Personal and Connect tiers; the reviewed page lists ₹500/month for Connect with realtime WebSocket and historical candles. Re-check current plan/terms before build |
| Dhan | [DhanHQ V2 docs](https://dhanhq.co/docs/v2/), [Live Market Feed](https://dhanhq.co/docs/v2/live-market-feed/), [Historical Data](https://dhanhq.co/docs/v2/historical-data/), [Market Quote](https://dhanhq.co/docs/v2/market-quote/) | WebSocket live feed; REST LTP/OHLC/depth snapshots; daily and intraday historical candles; derivatives data | V2 docs describe up to five WebSocket connections per user and up to 5,000 instruments per connection; intraday history is requested in bounded ranges (90 days per request in the reviewed doc) |
| Angel One | [SmartAPI docs](https://smartapi.angelone.in/docs), [Historical API response structure](https://smartapi.angelone.in/docs/ResponseStructure), [Market Data docs](https://smartapi.angelone.in/docs/MarketData) | WebSocket Streaming 2.0; historical candles across equity, index, futures/options and commodity segments; historical OI endpoint is documented for live F&O contracts | Reviewed WebSocket docs specify up to three concurrent connections per client code. Historical API also applies maximum date windows per request |
| FYERS | [FYERS API V3 overview](https://fyers.in/api-docs/v3/getting-started/), [Market Data APIs](https://fyers.in/api-docs/v3/api/market-data/), [Historical data](https://fyers.in/api-docs/v3/api/market-data/historical-data), [Historical data guide](https://fyers.in/api-docs/v3/getting-started/guides/work-with-historical-market-data) | Data WebSocket for live quotes/depth/tick streams; separate account/order event WebSocket; quotes, depth, option/futures chains and historical candles | History availability differs by plan and resolution; confirm current plan, seconds data and expired F&O entitlements before sizing experiments |
| Groww | [Groww Trade API docs](https://groww.in/trade-api/docs), [Live Data](https://groww.in/trade-api/docs/curl/live-data), [Historical Data](https://groww.in/trade-api/docs/curl/historical-data), [Changelog](https://groww.in/trade-api/docs/curl/changelog) | Live quote/OHLC snapshots; historical candles; the API surface also documents orders, portfolio, instruments and derivative data | The old historical range endpoint is marked deprecated. Use the current historical-candles method documented by Groww and verify interval/history limits |

This matrix records what the provider documentation describes. It is not a feature certification, SLA comparison or entitlement assessment. Before selecting a broker for production, verify authentication/token lifecycle, app approval, rate limits, instrument masters, websocket reconnect semantics, order permissions, API costs, data retention policy and account ownership requirements.

## 3. Two separate integration planes

Do not collapse these into one generic “broker/data API” adapter.

### A. Broker/account plane

Responsible for user-authorized access to:

- Authentication and token lifecycle.
- User profile and account identity.
- Funds, margins and charges.
- Holdings, positions and P&L.
- Order placement, modification, cancellation and status.
- Broker-specific live portfolio/order events.
- User-scoped market data where the broker's terms permit it.

Each broker needs its own adapter and explicit capability matrix. Read-only account access, market-data access and order execution are separate permission scopes. Order execution must remain disabled until the project has a separate risk, authorization, audit and kill-switch design.

### B. Market-data plane

Responsible for research-grade data across the supported universe:

- Historical prices and corporate actions.
- Live trades/quotes and intraday bars.
- Market depth and order-book snapshots where licensed.
- Index/sector/benchmark series.
- Options chain, implied volatility and open interest.
- Fundamentals and corporate filings.
- Macro releases.
- News and event records.
- Social/sentiment data only if licensing and quality justify it.

Use independent provider adapters and normalize data to a common schema. A broker's account API must not be assumed to provide an unrestricted data feed for all Finance AI users.

## 4. Data-rights gate

The reviewed [NSE Data Sharing & Usage Policy](https://betanseapi.nseindia.com/static/market-data/nse-data-policy) states that market-data use, transmission and dissemination are governed by the relevant agreements and end-user restrictions, and that redistribution is not permitted except as provided in the relevant agreement. It also restricts using market data to create financial indices or instruments without separate licensing.

Therefore, before any production feed is selected, record:

1. Source/provider and exact product/API.
2. Exchange, segment, instrument and data fields.
3. Whether the entitlement is personal, developer, internal research, commercial display or redistribution.
4. Permitted users, concurrent users and devices.
5. Historical retention and derived-data rules.
6. Real-time display, delayed display and derived analytics permissions.
7. Whether data can be used for model training, feature storage and backtesting.
8. Whether data or derived values can be exposed to end users or third parties.
9. Fees, renewal, audit, attribution and termination obligations.
10. Written approval/contract evidence and renewal date.

Do not scrape around a provider restriction or use a broker's user token as a substitute for commercial market-data permission. Obtain qualified legal review for licensing and contractual interpretation.

## 5. Point-in-time ingestion requirements

The existing multimodal implementation establishes four timestamps:

- Event time: when the underlying event happened.
- Publication time: when the provider made it public.
- Ingestion time: when our system received/stored it.
- Availability time: earliest time the record was actually available to the prediction process.

Availability time is the controlling timestamp for as-of joins. A historical record must not appear in the model input before it was available in the real world. Revisions/restatements must be represented as new versions with their own availability timestamps.

Additional requirements for market streams:

- Preserve exchange/provider timestamps and receive timestamps separately.
- Store sequence numbers or provider event IDs where available.
- Detect gaps, duplicate/out-of-order events and stale subscriptions.
- Persist raw payloads immutably when contract terms permit.
- Normalize timezone and exchange session using an exchange calendar.
- Reconcile live ticks into candles using documented interval boundaries.
- Preserve source, instrument identifier, currency, session and entitlement metadata.
- Monitor delayed/stale data separately from model confidence.
- Do not treat a missing update as an unchanged price without a freshness rule.

## 6. Provider selection process

Do not choose a source based on marketing claims alone. Score candidates against:

- Coverage of the intended Indian and/or global instrument universe.
- Historical depth and intraday resolution.
- Point-in-time corporate actions and instrument-master quality.
- Options/OI/depth coverage if required by the prediction task.
- Publication/availability timestamps and correction history.
- Uptime, latency, rate limits and websocket reconnect behaviour.
- Cost per instrument, request, user and data entitlement.
- Model-training, retention, display and redistribution rights.
- Contractual clarity and operational support.

For the first real-market pilot, choose one primary licensed source and one independently verified reconciliation source. Avoid premature integration of all six brokers into the research ingestion path.

## 7. Current gaps and decisions

| Item | Status |
|---|---|
| Yahoo historical adapter for the MVP | Implemented, limited to documented daily/weekly/monthly intervals |
| Real-time feed in the original MVP | Not implemented |
| Indian broker product concept (six brokers) | UI/design scope only |
| Official API capabilities of the six brokers | Documentation reviewed; no code integration implied |
| Licensed market-wide data source | Not yet evidenced as approved in the repository |
| Licensed point-in-time fundamentals/news source | Not approved in the existing multimodal implementation report |
| Exchange redistribution rights | Must be contractually verified |
| Historical data rights for model training and retention | Blocking dependency to resolve |
| Broker order execution | Not part of the research-only MVP |

## 8. Next actions

1. Collect actual user/account and commercial use requirements before picking broker and market-data providers.
2. Obtain written data-rights/retention/redistribution clarification for each shortlisted source.
3. Build a capability and entitlement register per provider.
4. Select one licensed source for a controlled research pilot and one source for reconciliation.
5. Verify historical coverage, timestamps, corrections, corporate actions and instrument-master quality with a small acceptance dataset.
6. Only after acceptance, schedule broad universe ingestion and real-market MPFM experiments.

## 9. Source notes

All provider URLs above are official documentation/product pages reviewed on 2026-11-17. Product capability, prices, limits and terms can change; re-check the linked source and save a dated snapshot before implementation or purchase.


## 10. Market-1T and TFWM research reference (reviewed 2026-11-17)

The MPFM Phase 1 work uses [Market-1T](https://github.com/fin-ai-lab/market-1t) and [Towards Financial World Modeling / TFWM](https://github.com/fin-ai-lab/tfwm) as research references.

Market-1T is described by the paper as nearly one trillion one-second aggregates of U.S.-traded equities from 2008–2025, built from consolidated SIP quote/trade data and NBBO state. The 11 fields are best bid price/size, best ask price/size, OHLC, VWAP, traded volume and trade count. This is top-of-book plus trade aggregation; it is not full L2/L3 depth or participant-identity data.

The TFWM README, when reviewed on 2026-11-17, described a sample from July 2019 to December 2020 (230,025 ticker-days) and stated that full open dataset hosting was being worked on with Massive. The Market-1T pipeline documents access to Massive flat files and S3 credentials/plan requirements. Verify current dataset-card, model-card and provider terms before attempting reproduction. The code repository's MIT license does not by itself establish the data or pretrained-weight license.

Market-1T is a U.S.-equity reference, not a ready-made NSE/BSE feed. An Indian reproduction requires locally valid exchange calendars, instrument identity, session rules, tick sizes, corporate actions, timestamps, permitted data rights and (for HFT) the actual order-depth/event fields supplied by the licensed source.

Detailed architecture and experiment implications are documented in [FINANCIAL_WORLD_MODELING_PHASE1.md](FINANCIAL_WORLD_MODELING_PHASE1.md).
