# MULTIMODAL FINANCE DATA IMPLEMENTATION (Post-MVP Milestone 08)

Status: IMPLEMENTED (research-only). Extends the intelligence layer with
company fundamentals and time-aligned events/news under STRICT point-in-time
correctness. No live trading, no LLM, no rewrite of the market pipeline.

---

## 1. Modalities implemented

| Modality | Status | Source |
|---|---|---|
| Market data | existing (unchanged) | Yahoo Finance adapter (Milestone 02) |
| Fundamentals | abstraction + deterministic fixture | no licensed provider approved |
| Events / news | abstraction + deterministic fixture | no licensed provider approved |

**Source policy (milestone section 12)**: only approved/legal sources may be
used and none is currently licensed for fundamentals or news. The milestone
therefore implements the full ingestion abstraction with deterministic
offline fixtures and documents this limitation. The fixture format IS the
normalized source contract: wiring a licensed provider later means adding one
adapter, not redesigning this layer. No arbitrary web scraping is performed.

## 2. Point-in-time methodology (the central rule)

Every external record carries four timestamps
(`src/multimodal/contracts.py`):

- `event_timestamp` — when the economic event occurred;
- `publication_timestamp` — when the information became public;
- `ingestion_timestamp` — when our system received it;
- `availability_timestamp` — **the join key** for model eligibility.

Event time is never treated as publication time. Example encoded in the
reference fixture: fiscal quarter Q4-2023 ends 2023-12-31 but is published
2024-01-04 18:30 — a prediction on 2024-01-03 must not see it.

**Temporal reliability classes**: `RELIABLE` (explicit publication timestamp
with timezone) → eligible at the exact publication instant; `DAY_ONLY`
(timezone declared but unknown offset) → eligible only from the START of the
NEXT day (never assume a morning release, section 19); `INSUFFICIENT` (no
trustworthy publication time) → never eligible. No silent interpretation of
ambiguous timestamps (section 20); original timestamp/timezone are preserved.

## 3. As-of join methodology

`src/multimodal/asoof.py` answers "what did we know at T?":

- eligibility: `effective_availability(record) <= T` only;
- deterministic ordering: latest availability, then `source_identifier`,
  then `record_id` (never dictionary order);
- fundamentals: latest eligible filing carried forward — never forward-filled
  before publication (section 22);
- event windows: the small justified MVP set {1, 3, 7 days}, backward-looking
  from T only (section 23); `hours_since_last_event` completes the event
  features;
- entity isolation: records join only on the resolved instrument ticker;
  other instruments' records are never visible (section 21).

## 4. Feature additions (`feature_set_v0.2`)

- Fundamentals (carried forward as-of): `revenue`, `operating_income`,
  `net_income`, `eps`, `total_assets`, `total_liabilities`, `cash`,
  `total_debt`, `free_cash_flow`, `shares_outstanding`;
- Derived ratios: `debt_ratio` (liabilities/assets), `margin`
  (net_income/revenue), `has_fundamentals` (0/1 availability flag);
- Event features: `events_1d`, `events_3d`, `events_7d`,
  `hours_since_last_event`.

Missing modality → NaN + `has_fundamentals=0` — never fabricated (section 41).
Market features pass through untouched; v0.1 is not mutated (section 32).

**Deferred by design**: sentiment (section 15 — no validated model approved;
factual events are more reproducible) and embeddings (section 16 — compact
derived features preferred for the MVP; no vector database).

## 5. Leakage controls — mandatory tests, all passing

| Test | Result |
|---|---|
| A — publication-time (post-T record invisible at T) | PASS |
| B — future news does not change historical features | PASS |
| C — future filing does not change historical fundamentals | PASS |
| D — as-of query returns only availability ≤ T | PASS |
| E — dataset extension leaves historical rows identical | PASS |
| F — same-day timing (16:30 publication invisible at 14:00) | PASS |
| Controlled fixture (12:00 news usable at 15:00; 17:00 news and next-day filing not) | PASS |

## 6. Deduplication and restatements

- **Dedup (section 29)**: exact `source_identifier` first; then a content
  fingerprint (instrument + event_type + event day + first 8 headline
  tokens) removes cross-source duplicates, keeping the earliest publication.
  Limitation documented: near-duplicates with different wording are NOT
  detected (no fuzzy matching in the MVP).
- **Restatements (section 30)**: policy = "first publication is truth".
  Restatements are new records with their own availability timestamps;
  as-of joins make them invisible before their publication, so historical
  training rows are never retroactively rewritten. The policy and affected
  periods are reported by `restatement_policy()`.

## 7. Experiments (section 33/34) — honest data limitation

Experiments A–D (market-only / +fundamentals / +events / combined) require a
real fundamentals/events history. With fixture-only external data (a handful
of records over days, not years), any measured comparison would be
statistically meaningless. **No experiment metrics are reported** — running
them on fixtures would fabricate results, which this project forbids. The
integration chain (source → normalize → as-of → features → numeric model
input matrix) IS verified by tests, so experiments run mechanically once a
licensed source provides real history.

## 8. Compatibility

- **Training/backtest**: multimodal columns are additive features; the
  existing dataset builder, trainer, and backtest engine consume them
  unchanged once a dataset containing them exists (no second ML system).
- **Inference**: as-of logic is available for historical inference; the API
  is unchanged and never exposes future reports/articles (section 38).
- **Offline research mode (section 39)**: everything runs from stored
  fixture records; no network access at inference/backtest time.
- **Drift monitoring**: external feature columns are ordinary numeric
  features — the existing drift engine can monitor them (including
  missingness) without new infrastructure (section 47).
- **Autonomous pipeline (section 48)**: external batches normalize through
  the same boundary; the scheduler is unchanged.
- **Registry (section 50)**: any multimodal model registers through the
  existing lifecycle as CANDIDATE; no automatic activation.

## 9. Known limitations

1. No licensed fundamentals/news source — fixture-only external data; no
   experimental conclusions are drawn from it.
2. Survivorship/universe bias is not addressed (single-instrument MVP);
   documented per section 31.
3. Dedup is fingerprint-based; paraphrased duplicates pass through.
4. DAY_ONLY records lose intraday granularity by design (conservative).
5. Sentiment and embeddings deferred; revisit with an approved model/source.

## 10. Files

- `src/multimodal/contracts.py` — timestamps, reliability, taxonomy;
- `src/multimodal/asoof.py` — as-of joins, windows, carry-forward;
- `src/multimodal/sources.py` — normalization, dedup, fixtures, batch
  metadata, restatement policy;
- `src/multimodal/features.py` — `feature_set_v0.2` assembly;
- `data/external/fixtures/multimodal_reference.json` — controlled fixture;
- `tests/test_multimodal.py` — 20 tests incl. all mandatory leakage tests.

Research-only. No live trading functionality exists anywhere in this milestone.
