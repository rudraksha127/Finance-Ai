# UI/UX BLUEPRINT — Finance AI MVP Dashboard

> Complete UI/UX architecture for the Finance AI research + model evaluation platform.
> This is a RESEARCH / MODEL EVALUATION platform — NOT a live trading platform.
> This document is UX/UI research + design specification only. No frontend code.

---

## Table of Contents

1. [Primary Objective](#1-primary-objective)
2. [Create Documents](#2-create-documents)
3. [Product UX Principle](#3-product-ux-principle)
4. [Primary User](#4-primary-user)
5. [Information Architecture](#5-information-architecture)
6. [Global App Shell](#6-global-app-shell)
7. [Home / Overview Screen](#7-home--overview-screen)
8. [Market Explorer](#8-market-explorer)
9. [Prediction View](#9-prediction-view)
10. [Probability Visualization](#10-probability-visualization)
11. [Risk Visualization](#11-risk-visualization)
12. [Signal Explanation](#12-signal-explanation)
13. [Backtest Screen](#13-backtest-screen)
14. [Benchmark Comparison](#14-benchmark-comparison)
15. [Experiment Comparison](#15-experiment-comparison)
16. [Model Registry / Model View](#16-model-registry--model-view)
17. [Dataset View](#17-dataset-view)
18. [System Health](#18-system-health)
19. [Status System](#19-status-system)
20. [Design System](#20-design-system)
21. [Color System](#21-color-system)
22. [Responsive Design](#22-responsive-design)
23. [Accessibility](#23-accessibility)
24. [Interaction Design](#24-interaction-design)
25. [Table Design](#25-table-design)
26. [Loading / Empty / Error States](#26-loading--empty--error-states)
27. [Data Freshness UX](#27-data-freshness-ux)
28. [Research Mode Safety](#28-research-mode-safety)
29. [API → UI Contract](#29-api--ui-contract)
30. [Backtest → UI Contract](#30-backtest--ui-contract)
31. [Design Component Hierarchy](#31-design-component-hierarchy)
32. [Frontend Technology Recommendation](#32-frontend-technology-recommendation)
33. [Performance](#33-performance)
34. [Responsible Data Presentation](#34-responsible-data-presentation)
35. [Figma / Design Handoff](#35-figma--design-handoff)
36. [Page Inventory](#36-page-inventory)
37. [MVP User Flows](#37-mvp-user-flows)
38. [UX Acceptance Criteria](#38-ux-acceptance-criteria)
39. [Consistency Check](#39-consistency-check)
40. [Deliverables](#40-deliverables)
41. [Stop Condition](#41-stop-condition)

---

## 1. Primary Objective

Design a professional research dashboard that lets a user:

1. Inspect market data
2. Inspect model predictions
3. Understand prediction confidence
4. Inspect decision/risk outputs
5. Run and review backtests
6. Compare experiments
7. Inspect dataset/model versions
8. Monitor data/model quality
9. Understand why a signal was produced
10. Identify failures or anomalies

**UI priorities:**

| Priority | Meaning |
|----------|---------|
| **Clarity** | One screen answers one question; no decoration over data |
| **Research usability** | Fast access to versions, timestamps, and metadata — reproducibility is a UI feature |
| **Information hierarchy** | Prediction > decision > context, not the reverse |
| **Fast scanning** | Tables and badges beat prose |
| **Trust** | Every number is traceable to a version and a timestamp |
| **Explainability** | Reason codes are first-class UI citizens, never hidden |
| **Consistency** | One status taxonomy, one visual language, one data-freshness rule |
| **Accessibility** | WCAG AA; information never conveyed by color alone |

---

## 2. Create Documents

| Deliverable | Status |
|-------------|--------|
| `docs/UI_UX_BLUEPRINT.md` | ✅ This document — single authoritative UI/UX specification |
| `docs/UI_COMPONENT_SPEC.md` | ⏸ Folded into Sections 20, 21, 31 of this document |
| `docs/DASHBOARD_INFORMATION_ARCHITECTURE.md` | ⏸ Folded into Sections 5, 6, 36 of this document |

**Decision: one comprehensive document instead of three.** The component spec and IA are fully specified inside this blueprint (Sections 5, 6, 20, 21, 31, 36). Separate files would duplicate content and split maintenance across three documents in a doc-only architecture phase. This matches the established pattern of one authoritative blueprint per domain.

**Update:** `CURRENT_STATE.md` and `DECISIONS.md` (genuine architectural decisions only).

---

## 3. Product UX Principle

**The interface must never imply "prediction = guaranteed future result."**

### 3.1 Required Language

| Use | Avoid |
|-----|-------|
| Prediction | Guaranteed |
| Probability | Certain |
| Expected Return | Sure Profit |
| Risk | 100% Accurate |
| Signal | Risk-free |
| Historical Performance | Proven Strategy |

### 3.2 Presentation Rules

- All probabilities displayed as probabilities (`P(UP) = 0.62`), never as implied certainty.
- All performance figures labeled `Historical (simulated)` where they come from backtests.
- Expected return labeled `Model expected return (estimate)`.
- The word "Signal" always refers to the Decision Engine output (BUY/SELL/HOLD/NO_TRADE), never "advice".
- Every page footer carries the research disclaimer: **"Research & simulation only — not financial advice."**

---

## 4. Primary User

### 4.1 Primary Persona: Technical Researcher / ML Engineer

Investigating a financial prediction model. Wants to answer:

- What did the model predict, and with what probability?
- Why did the Decision Engine act or abstain?
- Which dataset/features/labels produced this model?
- How did the strategy perform historically, net of costs?
- Is the current model/data healthy?

### 4.2 Secondary Users

| User | Primary Need |
|------|--------------|
| Quant researcher | Signal quality, sensitivity, benchmark comparison |
| Developer | System health, error visibility, API contract sanity |
| Product owner | High-level status: is the pipeline working, what changed |

**Do NOT optimize the MVP for casual retail traders.** No big profit banners, no "signals feed", no action-oriented marketing patterns.

---

## 5. Information Architecture

### 5.1 Navigation Candidates Evaluated

The example list (Dashboard / Market Explorer / Predictions / Backtests / Experiments / Models / Datasets / System Health) was not copied blindly. Each candidate was checked against the 10 objectives in Section 1 and PRD FR-DB-01..06.

| Candidate | Kept? | Justification |
|-----------|-------|---------------|
| Overview (home) | ✅ | Answers "what is the system doing right now" (PRD FR-DB-01, US-07) |
| Market Explorer | ✅ | Objective 1 (inspect market data) needs a dedicated charting surface |
| Predictions | ✅ | Objectives 2, 3, 4, 9 — dedicated prediction + decision explanation |
| Backtests | ✅ | Objectives 5 — PRD FR-DB-02/03 require backtest metrics + equity curve |
| Experiments | ✅ | Objective 6 (compare experiments) — TRAINING_PIPELINE_BLUEPRINT domain |
| Models | ✅ | PRD FR-DB-04 (model info) — registry/metadata view |
| Datasets | ✅ | Objective 7 (version identity) — reproducibility requires dataset traceability |
| System Health | ✅ | Objectives 8, 10 — lightweight status page |
| Settings | ❌ | No user settings in MVP; config is YAML (researcher edits files) |

**Every page maps to a distinct backend domain object** (instrument market data, prediction/decision, backtest run, experiment run, model version, dataset version, system status). Merging any two would create overloaded pages that violate fast-scanning.

### 5.2 Final MVP Navigation (8 items)

```
Overview
Market Explorer
Predictions
Backtests
Experiments
Models
Datasets
System Health
```

Flat, single-level navigation. No nested menus in MVP.

---

## 6. Global App Shell

### 6.1 Shell Layout

```
┌────────────────────────────────────────────────────────────────────┐
│ TOP BAR                                                            │
│  [◧ RESEARCH MODE]  Active model v1.0.0-20260904 · As of 2026-09-04 │
│  [notifications ▾]                                  [Docs ↗]       │
├──────────┬─────────────────────────────────────────────────────────┤
│ SIDEBAR  │  PAGE                                                   │
│ Overview │  ┌───────────────────────────────────────────────────┐  │
│ Market   │  │ Page title + context line                        │  │
│ Explorer │  │ (e.g., "Random Forest · dataset v1.2 · ...")     │  │
│ Predict- │  │                                                   │  │
│ ions     │  │            [page content]                        │  │
│ Backtests│  │                                                   │  │
│ Experim. │  └───────────────────────────────────────────────────┘  │
│ Models   │  ALERT AREA (inline, contextual)                        │
│ Datasets │                                                         │
│ System   │                                                         │
│ Health   │                                                         │
├──────────┴─────────────────────────────────────────────────────────┤
│ FOOTER: Research & simulation only — not financial advice          │
└────────────────────────────────────────────────────────────────────┘
```

### 6.2 Shell Elements

| Element | Content | Rule |
|---------|---------|------|
| **Sidebar** | 8 nav items, active state, collapsed tooltips on tablet | Always visible on desktop |
| **Top bar — mode indicator** | `RESEARCH MODE` badge (amber, not green) | **Persistent on every screen.** If PAPER/SIMULATION mode is enabled, show `PAPER SIMULATION`. A LIVE mode badge must not exist in MVP (§28) |
| **Top bar — version indicator** | Active model + strategy version, e.g. `model v1.0.0-20260904 · stg_v0.1` | Click → Models page; always matches the last `/predict` response served |
| **Top bar — time context** | `As of <timestamp>` — global data-freshness anchor | See §27; updates from latest system health poll |
| **Notifications/error area** | Compact bell with count → drawer listing WARNING/ERROR events | Drawn from System Health events; never silent |
| **Page title** | Title + one-line context (versions, instrument, period) | Consistent pattern on every page |
| **Footer** | Research disclaimer | On every page (§3.2) |

---

## 7. Home / Overview Screen

### 7.1 Purpose

Answer within seconds: *What is the system doing? Which model is active? How is it performing? Are there errors? What changed recently?*

### 7.2 Layout (top to bottom)

```
1. Status strip        → System health summary (API · model · data · latest run)
2. Left column:
   ┌ Active Model ────────────────┐
   │ model v1.0.0-20260904         │
   │ random_forest · trained date  │
   │ validation acc 0.54 · backtest Sharpe 1.42  [View →]   │
   ├ Latest Prediction ────────────┤
   │ AAPL · P(UP) 0.62 · signal NO_TRADE          [View →]  │
   ├ Data Quality ─────────────────┤
   │ dataset v1.2 · quality 96/100 · last ingest <date>     │
   └───────────────────────────────┘
3. Right column:
   ┌ Recent Model Performance (simulated) ─┐
   │ mini equity curve (strategy vs buy-hold)             │
   └──────────────────────────────────────┘
   ┌ Recent Activity (experiments/backtests/system) ─┐
   │ table: type · id · status · time                │
   └───────────────────────────────────────────────┘
```

### 7.3 High-Level Cards (7, intentionally limited)

| Card | Source (API addition §29) | Empty behavior |
|------|---------------------------|----------------|
| Active Model | `/model/info` | "No model registered" |
| Dataset Version | datasets list (latest) | "No dataset built" |
| Latest Prediction | predictions audit (latest) | "No predictions yet" |
| Recent Model Performance | backtests list (latest) | "Run a backtest first" |
| Data Quality | quality report (latest dataset) | "No quality report" |
| Last Training Run | experiments list (latest) | "No experiments yet" |
| System Health | `/health` + system status | — |

**No KPI explosion:** maximum 7 cards, each click-through to its owning page. Cards show status badges (§19) prominently.

---

## 8. Market Explorer

### 8.1 Purpose

Analytical market view for one instrument: price context + where the model made predictions + what the decisions were.

### 8.2 Screen Anatomy

| Zone | Content |
|------|---------|
| **Toolbar** | Instrument selector, interval (`1d` only in MVP), time range (All / 5Y / 1Y / 6M / 3M / 1M / 21D), overlay toggles |
| **Main chart** | Price (line or candlestick), synchronized X-axis |
| **Overlay layers** | Volume (sub-pane), selected indicators (e.g., volatility band, moving average) — off by default |
| **Prediction layer** | Prediction markers at their timestamps; marker opens the Prediction View for that (ticker, timestamp) |
| **Signal layer** | Decision markers (BUY-entry / EXIT / NO_TRADE flags) drawn from decision log |
| **Detail panel** | On selection: probabilities, confidence, risk score, reason codes, model/feature versions |

### 8.3 Progressive Disclosure Rules

| Data | Default | Why |
|------|---------|-----|
| Price | Visible | Core context |
| Volume | Visible (sub-pane) | Standard |
| Indicators | Hidden (toggled) | Do not overload — max ~2 overlays on at once |
| Prediction markers | Visible (subtle) | Core research object |
| Decision markers | Visible (subtle) | Explains what the system did |
| Full prediction detail | On click | Detail belongs to Prediction View |

**Synchronized timestamps:** hovering anywhere sets one global cursor time used by chart, sub-panes, and detail panel.

---

## 9. Prediction View

### 9.1 Purpose

The canonical answer to: *what did the model say, and what should be done?*

### 9.2 Screen Anatomy (single instrument + timestamp)

```
Instrument & context
  AAPL · 2026-09-04 · prediction_id pred_... · data as of 2026-09-04 09:30 UTC

┌──────────────── MODEL OUTPUT ────────────────┐  ┌── DECISION OUTPUT ──────────────┐
│ P(UP)    0.62  ████████████░░░░░░░░           │  │ Signal      NO_TRADE            │
│ P(DOWN)  0.23  ████░░░░░░░░░░░░░░░░           │  │ Risk score  0.61 (moderate)     │
│ P(HOLD)  0.15  ███░░░░░░░░░░░░░░░░░           │  │ Position    — (none)            │
│ Predicted class: UP                          │  │                                 │
│ Confidence: 0.62 (P of predicted class)      │  │ Reason codes:                   │
│ Expected return: — (not provided by model)   │  │  • CONFIDENCE_BELOW_THRESHOLD    │
│ Calibration: not yet validated ⚠             │  │  • EDGE_BELOW_COST               │
└──────────────────────────────────────────────┘  └─────────────────────────────────┘

Metadata panel
  model_version · feature_version · label_version · strategy_version
  prediction_timestamp · inference_timestamp · data_timestamp
  [Open in Market Explorer]  [Open prediction audit record]
```

### 9.3 Hard UI Rule: MODEL OUTPUT ≠ DECISION OUTPUT

The two zones are visually separated by a labeled divider — **MODEL OUTPUT** (what the model says) vs **DECISION OUTPUT** (what the system did with it, per ADR-0020 and INFERENCE_API_BLUEPRINT §8). They may never be merged or presented as one "prediction verdict."

### 9.4 Field Mapping (INFERENCE_API_BLUEPRINT §8)

| UI zone | Response field | Display |
|---------|----------------|---------|
| Model output | `model_output.probabilities` | Probability visualization (§10) |
| Model output | `model_output.prediction` | "Predicted class: X" |
| Model output | `model_output.confidence` | "Confidence: 0.62 = P(predicted class)" |
| Model output | `model_output.expected_return` | Estimate or "—" (null is honest) |
| Decision output | `decision_output.signal` | Signal badge with glyph (§12) |
| Decision output | `decision_output.risk_score` | Risk indicator (§11) |
| Decision output | `decision_output.position_size` | Size or "none" |
| Decision output | `decision_output.reason_codes` | Reason-code list (§12) |
| Identity | `model.*`, `prediction_id`, `inference_timestamp` | Metadata panel |

**Null handling:** null `expected_return`, null `position_size`, and NO_TRADE must render as "—"/"none" — never as 0, which would falsify meaning.

---

## 10. Probability Visualization

### 10.1 Recommended Visualization: Three Horizontal Bars

One horizontal bar per class (UP / DOWN / HOLD), each labeled with its value.

```
UP     0.62  ██████████████████████░░░░░░░░░░░░░░░░░░  62%
DOWN   0.23  ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  23%
HOLD   0.15  █████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  15%
        sum = 1.00 (calibrated model probabilities)
```

**Why bars over alternatives:**

| Option | Verdict | Reason |
|--------|---------|--------|
| Horizontal bars | ✅ **MVP** | Fastest scan; supports exact value + percent; no implied geometry |
| Compact probability chart (donut/pie) | ❌ | Slices imply parts of a whole in a way users misread as shares/certainty |
| Probability distribution (density) | ⏸ Future | Only meaningful with model uncertainty output, which MVP models do not provide |

### 10.2 Anti-Certainty Rules

- Bars are **neutral gray with a single accent** on the predicted class — do NOT color UP green / DOWN red inside this chart (color coding probabilities invites "good/bad" reading; the label is what matters).
- Show the class label and the decimal probability on every bar.
- Show the predicted class as `Predicted class: UP` text, not by implication.
- When calibration is unvalidated (no calibration evaluation on validation data — EVALUATION_BACKTESTING_BLUEPRINT §5.2), show the notice: `Calibration: not yet validated — treat probabilities as model scores`.

---

## 11. Risk Visualization

### 11.1 Risk Indicator Design

```
Risk score: 0.61   MODERATE   ◐ (glyph: half-filled shield)

[Low] [Moderate] [High]        ← segmented scale; marker at 0.61
                                ← score value shown numerically
```

| Element | Display |
|---------|---------|
| Risk score | Number (0.00–1.00) — authoritative backend value |
| Risk level | Text label: `Low` / `Moderate` / `High` / `Invalid / Unavailable` |
| Segmented scale | 3 segments with marker — never a vague dial |
| Context chips | Volatility, model uncertainty, regime (when the decision record provides them) |
| Risk flags | Reason codes that triggered caution (e.g., `HIGH_VOLATILITY`) |

### 11.2 Semantic States (never color alone)

| State | Color token | Text/glyph reinforcement |
|-------|-------------|--------------------------|
| Low | `--color-risk-low` (calm blue/teal) | "Low", ◔ |
| Moderate | `--color-risk-moderate` (amber) | "Moderate", ◐ |
| High | `--color-risk-high` (red) | "High", ◑ |
| Invalid / Unavailable | `--color-neutral` (gray) | "Invalid / Unavailable", ⊘ |

### 11.3 Scope Note

Risk score comes from the Decision Engine (RISK_DECISION_ENGINE_BLUEPRINT §20) and is a *research* risk estimate. It is labeled `Research risk estimate`, never "your risk".

---

## 12. Signal Explanation

### 12.1 Rule: Show Actual Reason Codes

The UI renders the machine-readable reason codes returned by the backend — it never invents natural-language explanations (INFERENCE_API_BLUEPRINT §25, RISK_DECISION_ENGINE_BLUEPRINT §21).

### 12.2 Signal Badge + Reason Panel

```
Signal:  NO_TRADE          [no-trade glyph: ⊘]

Why (reason codes from the Decision Engine):
  1. CONFIDENCE_BELOW_THRESHOLD   P(predicted class) = 0.48 < min 0.50
  2. EDGE_BELOW_COST              expected net edge 8 bps < minimum 15 bps
```

| Signal | Glyph + text | Never rendered as |
|--------|--------------|-------------------|
| BUY | ▲ BUY (research entry) | A recommendation to buy |
| SELL | ▼ SELL (exit/research short) | A recommendation to sell |
| HOLD | ■ HOLD | Advice |
| NO_TRADE | ⊘ NO_TRADE | Failure/error — abstention is a valid result (200) |

Each code renders as a badge; hovering explains the code's meaning from a static definition map (maintained next to the code list in RISK_DECISION_ENGINE_BLUEPRINT §21). No LLM, no prose generation.

---

## 13. Backtest Screen

### 13.1 Purpose

Professional backtest review page: identity, performance, risk, and evidence — all traceable.

### 13.2 Identity Panel (full, from experiment metadata)

| Field | Example |
|-------|---------|
| Backtest ID | `bt_20260904_153000` |
| Experiment ID | `exp_20260904_140000` |
| Model version | `v1.0.0-20260904` |
| Dataset version | `v1.2` |
| Feature version | `feat_3f9a...` |
| Label version | `label_v0.1` |
| Strategy version | `stg_v0.1` |
| Evaluation period | `2024-01-01 → 2024-12-31 (252 trading days)` |
| Cost assumptions | `20 bps round-trip (10 bps/side incl. 5 bps slippage)` |
| Execution convention | `close-to-close (documented simplification)` |

### 13.3 Performance Metrics Grid

**Primary row (always visible):**

| Metric | Example |
|--------|---------|
| Cumulative Return | 9.8% |
| Sharpe Ratio | 1.42 |
| Max Drawdown | −9.1% |

**Secondary grid (expandable):** Sortino, Calmar, annualized return/volatility, win rate, profit factor, expectancy, average win/loss, number of trades, turnover, avg holding period — exactly the EVALUATION_BACKTESTING_BLUEPRINT §15 set. All metrics render from `financial_metrics.json`; the frontend never recomputes.

### 13.4 Visualizations

| Chart | Data source (EVAL §16/§27) | Notes |
|-------|----------------------------|-------|
| Equity curve | `curves/equity_curve.csv` | Strategy vs benchmark overlay; log scale; y-label "Hypothetical $1.00 starting value" |
| Drawdown curve | `curves/drawdown_curve.csv` | Negative axis; horizontal reference at max drawdown |
| Returns distribution | computed from equity returns (server-side, in metrics JSON) | Histogram, net-of-cost |
| Trade statistics | `trades/trade_ledger.csv` | Win/loss split, P&L by trade (Table §25) |

**Metric definition note (§30):** hovering any metric name shows its definition/formula from the backend metric catalog — definitions are not reinterpreted in the UI.

---

## 14. Benchmark Comparison

### 14.1 MVP Benchmarks (EVALUATION_BACKTESTING_BLUEPRINT §17)

| Benchmark | Always shown | Label |
|-----------|--------------|-------|
| Model strategy | ✅ | `Strategy (model v1.0.0-20260904)` |
| Buy-and-Hold | ✅ | `Buy & Hold (AAPL)` |
| Zero-Trade (Cash) | ✅ | `Zero-trade (cash)` |

### 14.2 Comparison Table

```
Strategy              Cum Ret   Ann Ret   Sharpe   Max DD   Trades
Strategy (RF)          9.8%      4.9%     1.42    −9.1%     120
Buy & Hold (AAPL)      8.2%      4.1%     0.65    −14.3%     1
Zero-trade (cash)      0.0%      0.0%      —        0.0%     0
```

| Rule | Detail |
|------|--------|
| Exact same period | Evaluation-period dates are printed above the table; comparison is only valid within one backtest |
| No rescaling | Every curve normalized to its own $1.00 start; no axis tricks, no "beating the market" claims |
| Zero-trade | Trade-based cells render `—` (N/A) per EVAL §15.2, never 0 |

Chart: equity curves overlaid on the same log-scaled axis, three labeled series with distinct dash patterns + legend — color is not the only differentiator.

---

## 15. Experiment Comparison

### 15.1 Purpose

Compare Experiment A vs Experiment B across dataset/features/labels/model/config/metrics — but **only when evaluation assumptions are compatible**.

### 15.2 Compatibility Gate (before any numbers render)

The UI computes a **comparability key** from backend metadata (TRAINING_PIPELINE_BLUEPRINT §19, EVALUATION_BACKTESTING_BLUEPRINT §23):

| Dimension | Compatible when |
|-----------|-----------------|
| Dataset version | identical |
| Feature version | identical |
| Label version | identical |
| Split boundaries | identical evaluation period |
| Cost assumptions | identical |
| Metric protocol | identical |

**If any key differs:** comparison is blocked with an explicit explanation panel listing *which dimension differs and why comparison is invalid* — never a silent grayed-out chart.

```
⚠ Cannot compare: evaluation assumptions differ
   exp_A: dataset v1.1 · label_v0.1 · costs 20 bps
   exp_B: dataset v1.2 · label_v0.2 · costs 10 bps
   Differing: dataset version, label version, cost assumptions
```

### 15.3 Comparison Layout (side by side)

| Block | Content |
|-------|---------|
| Identity | experiment IDs, model versions, status badges |
| Configuration | model type, hyperparameters (from config snapshot), seed |
| Prediction metrics (validation) | accuracy, macro F1, per-class precision/recall (ML metrics — TRAINING §17) |
| Financial metrics (backtest) | Sharpe, drawdown, net return (financial metrics — TRAINING §17) |
| Divergence callouts | equal / better / worse flags computed client-side from the two authoritative values |

**Metric separation is enforced visually:** ML metrics (validation) and financial metrics (backtest) appear in labeled sections and are never mixed in one scoreboard (TRAINING_PIPELINE_BLUEPRINT §17).

---

## 16. Model Registry / Model View

### 16.1 Scope

A **MODEL INFORMATION page** — not an automated model registry UI. No promotion, no deployment actions (TRAINING_PIPELINE_BLUEPRINT §20.4: the gate produces a candidate, never a deployment).

### 16.2 Model Detail Panel

| Field | Source |
|-------|--------|
| Model version | registry metadata (`v1.0.0-20260904`) |
| Model type | `logistic_regression` / `random_forest` |
| Training date / created by | experiment record |
| Dataset / feature / label versions | registry metadata (BASELINE_MODEL_BLUEPRINT §7.3) |
| Validation metrics (ML) | experiment record — labeled *Validation* |
| Backtest metrics (financial) | latest backtest — labeled *Backtest (simulated)* |
| Status badges | facet badges (§19) |

### 16.3 Status Facets — Never One Ambiguous Badge

A model has **three distinct backend statuses** that must not be collapsed:

| Facet | Backend values | UI badge |
|-------|----------------|----------|
| Pipeline status | CREATED / RUNNING / COMPLETED / FAILED / INVALIDATED (TRAINING §12) | colored + textual |
| Registry status | active / deprecated / archived (BASELINE §7.3) | colored + textual |
| Gate outcome | PASS / REJECT / INCONCLUSIVE / NEEDS_MORE_DATA (TRAINING §20) | colored + textual |

The page shows all three facets when present (e.g., `COMPLETED · active · PASS`), because "model is valid" is a conjunction, not one label. **The UI deliberately does NOT introduce the taxonomy "Candidate/Validated/Rejected/Archived"** — that terminology does not exist in the backend (consistency finding, §39).

### 16.4 Model List Table

Columns: version · type · pipeline status · registry status · gate · trained at · validation acc · [View]. Read-only.

---

## 17. Dataset View

### 17.1 Purpose

Let a researcher identify exactly which dataset produced a model.

### 17.2 Dataset Detail Panel

| Field | Source |
|-------|--------|
| Dataset version | `v1.2` (semantic, DATASET_BUILDER_BLUEPRINT) |
| Source period | min–max timestamp |
| Instruments | list/count |
| Interval | `1d` |
| Row count | total rows |
| Feature count / version | 52 features · `feat_3f9a...` |
| Label version | `label_v0.1` |
| Data quality score | 0–100 + dimension breakdown (completeness/validity/consistency/freshness/uniqueness — DATA_CLEANING_VALIDATION) |
| Missing-data summary | per-column gaps |
| Generation timestamp | builder run time |

### 17.3 Traceability Line

`dataset v1.2 → feature set feat_3f9a… → model v1.0.0-20260904 → backtest bt_...`

A visible lineage line connecting the four views — the reproducibility contract made visible.

---

## 18. System Health

### 18.1 Purpose

Lightweight status page (not an enterprise observability dashboard).

### 18.2 Status Blocks

| Block | Shows | Source |
|-------|-------|--------|
| API status | up/down, uptime, mode | `/health` |
| Model availability | loaded model version / degraded | `/health` |
| Data freshness | latest data timestamp vs expected (trading day) | system status (API addition) |
| Latest ingestion | run id, rows, result | ingestion metadata |
| Data quality | latest dataset quality score | quality report |
| Latest training run | experiment id, status, duration | experiment records |
| Latest backtest | backtest id, status | backtest records |
| Errors & warnings | recent ERROR/WARNING events with timestamps | system event log |

### 18.3 Event List

A reverse-chronological table of system events: `type (RUN/INGEST/BACKTEST/API) · id · status · message · timestamp`. Warnings/errors carry the status taxonomy (§19) and are the source for the top-bar notification area.

---

## 19. Status System

### 19.1 One Taxonomy, Two Layers

**Layer 1 — UI status vocabulary (visual).** Every status has a text label + glyph + color; no ambiguous visual states.

| UI status | Text + glyph | Meaning |
|-----------|--------------|---------|
| SUCCESS | ✓ ok | Completed as expected |
| RUNNING | ⟳ running | In progress |
| WARNING | ⚠ warning | Succeeded with caveats |
| ERROR | ✕ error | Failed |
| STALE | ◷ stale | Data/model older than expected |
| UNKNOWN | ? unknown | State cannot be determined |
| COMPLETED / FAILED | ✓ / ✕ | Terminal pipeline outcomes |

**Layer 2 — domain statuses (data).** Rendered *as data* with Layer-1 visuals, never replaced by them: pipeline CREATED/RUNNING/COMPLETED/FAILED/INVALIDATED, registry active/deprecated/archived, gate PASS/REJECT/INCONCLUSIVE/NEEDS_MORE_DATA, decision signal BUY/SELL/HOLD/NO_TRADE (§12).

### 19.2 Badge Rules

- Every badge = colored chip **with text** (never color-only dot).
- STALE outranks SUCCESS in display (data shown as stale cannot also look current).
- ERROR outranks WARNING outranks RUNNING.

---

## 20. Design System

Analytical readability first — nothing chosen for trendiness.

| System | Specification |
|--------|---------------|
| **Typography** | System sans stack: `-apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`. Mono for all versions/IDs/timestamps/numbers: `ui-monospace, "Cascadia Mono", Consolas, monospace`. Type scale (px): 12 (caption/labels), 13 (table), 14 (body), 16 (emphasis), 20 (page title), 24 (panel title), 32 (overview hero). Line-height 1.5 text / 1.3 headings. **`font-variant-numeric: tabular-nums` on every numeric cell** |
| **Spacing** | 4 px base scale: 4 / 8 / 12 / 16 / 24 / 32 / 48. Dense research density by default (13 px tables, 8 px gutters) |
| **Border radius** | 2 px chips/badges, 4 px inputs/cards, 6 px modals. Sharp = data, soft = chrome. No pill-shaped everything |
| **Surface / elevation** | Flat light surfaces (`--surface-0/1/2`), 1 px borders, elevation only for popovers/modals/drawers (shadow token set). Charts on `--surface-0` |
| **Iconography** | Small inline SVG set (16/20 px) + geometric glyphs (▲▼■⊘◐⚠✓✕⟳◷). No icon font dependency; glyphs used for signal/status non-color reinforcement |
| **Charts** | One library (ECharts, §32). Consistent axis styling, always labeled axes, chart title + data source line, download-as-image not in MVP |
| **Tables** | §25 |
| **Badges** | §19 — text + color + glyph |
| **Buttons** | Quiet default / primary accent only for main page actions (Run backtest, Refresh). **No green "go trade" primary** |
| **Forms** | Minimal: instrument picker, date/range pickers, compare-selector. Labels always visible; validation inline |
| **Tooltips** | Used for: metric definitions, reason-code meanings, truncated metadata. Delay 300 ms; dismiss on Esc |
| **Empty states** | §26 |
| **Loading states** | §26 |
| **Error states** | §26 |

---

## 21. Color System

### 21.1 Semantic Roles (tokens, not component colors)

| Token role | Used for |
|------------|----------|
| `--color-text-primary / secondary / muted` | hierarchy |
| `--color-surface-0/1/2`, `--color-border` | layout |
| `--color-accent` | links, focus, primary actions, active nav |
| `--color-success / warning / error / info` | status badges (§19) |
| `--color-risk-low / moderate / high` | risk indicator (§11) |
| `--color-signal-action` (buy), `--color-signal-exit` (sell), `--color-signal-neutral` (hold), `--color-signal-none` (no-trade) | signal badges |
| `--color-chart-series-1..6`, `--color-chart-benchmark` | multi-series charts |
| `--color-stale` | staleness |

### 21.2 Color ≠ Meaning (non-color reinforcement)

| Context | Reinforcement |
|---------|---------------|
| BUY / SELL | ▲ / ▼ glyphs + text |
| Risk | Low/Moderate/High text + shield glyph |
| Performance | values shown as signed numbers (`+9.8%` / `−9.1%`) — never color-coded alone |
| Status | §19 text badges |

### 21.3 Accessibility & Contrast

- WCAG 2.1 AA: ≥ 4.5:1 body text, ≥ 3:1 large text/UI components.
- Semantic colors selected from a red-green **colorblind-safe** palette (blue/teal/amber/violet where possible); UP/DOWN never rely on green/red alone.
- Chart series distinguishable by dash pattern + legend beyond hue.

### 21.4 Theme Recommendation: Light by Default

**MVP default: light theme.** Rationale: analytical text readability, WCAG contrast margins, PDF/report sharing, print consistency, and the research-not-trading product stance. **Dark theme is NOT in MVP**; the token layer is theme-ready (`:root` / `[data-theme="dark"]`) so dark can be added later without component changes.

---

## 22. Responsive Design

| Breakpoint | Behavior |
|------------|----------|
| **Desktop (≥ 1280 px)** | Primary target — full sidebar, all panels, all charts |
| **Tablet (768–1279 px)** | Collapsed sidebar (icons), single-column stack, charts retained |
| **Mobile (< 768 px)** | Subset only: Overview, Prediction, Backtest summary, System Health |

**Mobile rules:** cards above charts; charts become summary numbers + a simplified sparkline; tables collapse to key columns; never attempt full experiment comparison or full market charting on mobile.

Explicitly out of MVP mobile scope: Experiment comparison, full Market Explorer, full Backtest detail.

---

## 23. Accessibility

| Area | Requirement |
|------|-------------|
| **Contrast** | WCAG 2.1 AA as specified in §21.3 |
| **Keyboard navigation** | All interactive elements reachable/operable via keyboard; visible `:focus-visible` ring (2 px accent) on every control |
| **Charts** | Charts are not the only representation: every chart has a data table or summary (equity curve → key metrics; probability bars → numeric bars text) and aria-label |
| **Screen reader labels** | `aria-label` on icon-only buttons, badges announce text (not color), status regions use `role="status"`/`aria-live="polite"` for async updates |
| **Non-color indicators** | §21.2 glyphs + text everywhere |
| **Font sizes** | Body ≥ 13 px tables / 14 px text minimums; zoom must not break layout |
| **Reduced motion** | `prefers-reduced-motion`: disable chart transitions/sparkline animations |
| **Tables** | Proper headers (`<th scope>`), sort indicators announced |

---

## 24. Interaction Design

| Interaction | MVP Behavior |
|-------------|--------------|
| Instrument selection | Combobox with known instruments from backend; search by ticker; persists in URL/state |
| Time range changes | Instant client-side range on loaded series (server returns full available window once per instrument) |
| Chart zoom | DataZoom/brush on time axis; always shows current window dates in the axis |
| Filtering | Table filters per column type (status, version, date range); reset affordance visible |
| Sorting | All sortable columns sortable; persisted per page |
| Model selection | Model page only — selection never changes what a historical prediction record shows (audit immutability) |
| Experiment comparison | Two-column picker → compatibility gate (§15) |
| Expanding details | Accordion/row expansion for secondary metrics and metadata; progressive disclosure |
| Viewing metadata | Hover tooltip or "ⓘ Metadata" panel; full metadata always reachable within 1 click |

**Progressive disclosure rule:** critical info (signal, probabilities, status, versions, freshness) is always visible; secondary detail (formulas, config snapshots, reason-code definitions) is one interaction away. Never hide critical info behind hover-only.

---

## 25. Table Design

### 25.1 Tables in the product

| Table | Core columns |
|-------|--------------|
| **Predictions (audit)** | prediction_id · ticker · as-of · signal · P(UP) · risk · model · strategy · status |
| **Trades** | trade_id · entry/exit timestamps · signal · entry/exit price · net_pnl · costs · holding · reason (EVAL §28 ledger fields) |
| **Experiments** | experiment_id · model · dataset · status · created · validation acc |
| **Models** | version · type · pipeline status · registry status · gate · trained at |
| **Datasets** | version · period · rows · features · label version · quality score |

### 25.2 Table rules

| Rule | Spec |
|------|------|
| Columns | Fixed set per table (§25.1); no infinite columns — detail in row expansion |
| Sorting | On all numeric/date columns; one sort at a time MVP |
| Filtering | Status filter chips + free-text search on IDs/tickers |
| Pagination | 50 rows/page default (100 max); page size control; no infinite scroll in MVP |
| Row expansion | Expandable row reveals secondary metadata + link to owning page (e.g., trade → backtest) |
| Status display | §19 badge in dedicated column |
| Scanability | Versions/IDs/timestamps in mono, tabular-nums; right-aligned numbers; consistent date format `YYYY-MM-DD HH:MM UTC` |

---

## 26. Loading / Empty / Error States

Every major screen defines four states. No generic "Something went wrong."

| State | Component | Content |
|-------|-----------|---------|
| **Loading** | `LoadingState` | Skeleton blocks matching final layout (no spinners alone); initial page load target < 1 s (§33) |
| **Empty** | `EmptyState` | Why it's empty + what to do: "No backtests yet — run a backtest from the CLI pipeline, then refresh" |
| **Error** | `ErrorState` | Error code (backend error model), affected component, retry action, link to System Health |
| **Stale** | `StaleDataBanner` | `STALE DATA` + last-update timestamp + expected freshness + affected component (§27) |

**State contract per page:** Overview, Market Explorer, Prediction, Backtest, Experiments, Models, Datasets, System Health each declare all four states in §36 page inventory.

---

## 27. Data Freshness UX

### 27.1 Global Rule

**Never present stale market information as current.**

### 27.2 Stale Detection & Display

| Element | Behavior |
|---------|----------|
| Detection | Server-side staleness check (INFERENCE_API_BLUEPRINT §11 `STALE_DATA`) OR client freshness check against `As of` context |
| Banner | `◷ STALE DATA — last update 2026-09-03 21:00 UTC (expected within 1 trading day)` |
| Affected component | Banner states which view/table/chart is affected |
| Actions | `Refresh` + link to System Health |
| Granularity | Per instrument (market data) and per dataset (feature/label freshness) — never one global mute |

### 27.3 Placement

- Global `As of` in the top bar (shell-level anchor).
- Per-view banners when the view's data is stale even if other views are current.
- Prediction records older than their validity window render the signal as EXPIRED/NO_TRADE per the decision log — never as a current signal.

---

## 28. Research Mode Safety

### 28.1 Hard Rule

MVP ships **RESEARCH mode only** (optionally PAPER/SIMULATION). A future live mode is structurally absent — matching the backend, where `mode: live` fails at startup (INFERENCE_API_BLUEPRINT §24).

### 28.2 UI Exclusions (must NOT exist in MVP)

- Place Order / Execute Trade / Buy Now / Sell Now buttons
- Any order form, broker connection panel, or portfolio view
- Live P&L badges, live risk alerts, "trade" CTAs
- A green "LIVE" indicator of any kind

### 28.3 UI Inclusions

| Element | Where |
|---------|-------|
| Persistent `RESEARCH MODE` badge | Global top bar, every screen (§6) |
| `PAPER SIMULATION` badge when paper mode enabled | Global top bar |
| Footer disclaimer | Every page |
| "Simulated" labeling on all backtest-derived numbers | Backtest, Benchmark, Experiments, Overview cards |
| Read-only data actions only | Refresh, run-backtest trigger (via CLI pipeline), view — all research actions |

There is no accidental path to broker execution because no execution UI or execution endpoint exists in the product (PRD §10; ADR-0020).

---

## 29. API → UI Contract

### 29.1 Rule

- The frontend **displays authoritative backend values only**; it never recomputes metrics, probabilities, risk, or decisions.
- Where a value is derived for display (percent formatting, sort, comparability key), the derivation is presentational and documented.

### 29.2 Existing Endpoints (INFERENCE_API_BLUEPRINT §6)

| UI surface | Endpoint | Response fields used |
|------------|----------|----------------------|
| Global model indicator | `GET /model/info` | model_version, model_type, trained_at, metrics |
| Global version indicator | `GET /version` | api_version, model_version, feature_version, label_version, strategy_version, mode |
| Global health status | `GET /health` | status, model_loaded, model_version, uptime_seconds, mode |
| Prediction View | `POST /predict` (or replayed audit record) | full response contract §8 (model_output + decision_output) |

### 29.3 GAPS — Required Read-Only API Additions (documented, not invented)

The dashboard cannot be built on the four prediction endpoints alone (System Health, Market Explorer, Predictions history, Backtests, Experiments, Models list, Datasets all need read access to backend records). PRD FR-DB-05 requires the dashboard to read from the API, not directly from models/files. **These additions do not exist yet in INFERENCE_API_BLUEPRINT and must be specified at implementation time** (same FastAPI process; read-only; file-backed):

| Needed by UI | Proposed read endpoint (to be specified) | Backing store |
|--------------|------------------------------------------|---------------|
| Market chart | `GET /candles/{ticker}` (range params) | cleaned OHLCV (data/processed) |
| Prediction audit/history | `GET /predictions` (ticker, date range) | `predictions/audit/*.jsonl` |
| Backtest list/detail | `GET /backtests`, `GET /backtests/{backtest_id}` | `backtests/{id}/**` (metrics JSON, curves CSV, ledger) |
| Experiments | `GET /experiments`, `GET /experiments/{id}` | `experiments/{id}/**` |
| Models | `GET /models` (+ extend `/model/info`) | `models/registry/registry.json` |
| Datasets | `GET /datasets`, `GET /datasets/{version}` | dataset metadata + quality report |
| System status | `GET /system/status` (+ events) | ingestion/training/backtest logs |

**These are flagged as the #1 backend gap in §39 and the Final Report.** Until they exist, the Overview, Market, Predictions-history, Backtests, Experiments, Models, Datasets, and System Health pages have no data source; the Prediction View and health/version indicators are the only UI surfaces fully backed by today's contract.

---

## 30. Backtest → UI Contract

### 30.1 Rule

The UI displays backtest outputs as produced by the EVALUATION_BACKTESTING_BLUEPRINT engine. **No alteration or reinterpretation.**

| Backtest fact | UI shows | Backend source |
|---------------|----------|----------------|
| Metric values | as-is, with definition on hover | `metrics/financial_metrics.json`, `metrics/prediction_metrics.json` |
| Exact evaluation period | printed on screen | experiment record |
| Cost assumptions | printed (20 bps round-trip default) | config snapshot |
| Benchmark identity | Buy & Hold / Zero-Trade / Strategy, labeled | metrics + curves files |
| Equity/drawdown series | plotted, not recomputed | `curves/*.csv` |
| Trades | ledger table with net P&L after costs | `trades/trade_ledger.csv` |
| Experiment identity | full identity panel | `metadata/experiment_record.json` |
| Gross vs net | gross/net shown separately when available | cost-decomposition JSON |

### 30.2 Metric semantics enforced in UI copy

- Trade P&L is **net of costs** (EVAL §15.2).
- Sharpe uses risk-free rate 0 — the UI prints `Sharpe (rf = 0)`.
- Annualization 252 days — the UI prints `(annualized, 252d)`.
- No-trade cases: trade metrics render `—` (N/A), never 0 (EVAL §15.2).

---

## 31. Design Component Hierarchy

| Component | Purpose | Where used |
|-----------|---------|------------|
| `AppShell` | Sidebar + top bar + alert area + footer | every page |
| `Navigation` | 8 items, active state | AppShell |
| `ModeBadge` | RESEARCH MODE / PAPER SIMULATION | AppShell top bar |
| `MetricCard` | Label + value + source + click-through | Overview, Backtest |
| `StatusBadge` | §19 two-layer statuses | tables, cards, lists |
| `ProbabilityChart` | three horizontal bars (§10) | Prediction View |
| `RiskIndicator` | number + level + scale (§11) | Prediction View |
| `ReasonCodeList` | code badges + definitions (§12) | Prediction View |
| `PriceChart` | instrument series + overlays + markers | Market Explorer |
| `EquityChart` | strategy vs benchmark curves | Backtest |
| `DrawdownChart` | negative series + max-DD reference | Backtest |
| `ReturnsHistogram` | distribution of net daily returns | Backtest |
| `DataTable` | §25 columns/sort/filter/pagination | audit, trades, experiments, models, datasets |
| `VersionBadge` | mono chip for model/feature/label/strategy/dataset | identity panels, tables |
| `ExperimentCard` | identity + status + mini metrics | Experiments |
| `MetadataPanel` | key-value version/identity display | Prediction, Backtest, Model, Dataset |
| `AlertBanner` | WARNING/ERROR/STALE contextual | per-view |
| `EmptyState` | why + next action | every page |
| `ErrorState` | code + retry + health link | every page |
| `LoadingState` | skeleton layout | every page |
| `ComparabilityNotice` | experiment compare blocker (§15) | Experiments |

Component specs (props/data/behavior) are part of this document's Sections 20/21/25/26/31 — sufficient for a design tool handoff (§35) and future component implementation.

---

## 32. Frontend Technology Recommendation

### 32.1 Evaluation

| Option | Strengths | Weaknesses | MVP fit |
|--------|-----------|------------|---------|
| **React + Vite + TypeScript SPA** | Component model matches this spec; typed contracts; Vite is fast/simple; huge ecosystem | Node toolchain + build step in a Python repo | ✅ **RECOMMENDED** |
| Next.js | SSR/SEO, file routing | Server infra unnecessary for a local authenticated-less research app | ❌ Overkill |
| Server-rendered (Jinja2/HTMX in FastAPI) | No Node; single language | Painful for the interactive comparison/chart states in this spec | ⚠️ Workable but weaker |

**Recommendation: Vite + React + TypeScript single-page app**, served as static assets by the FastAPI backend (same origin, no CORS in production use), data via the read endpoints (§29). This is a **genuine architectural refinement** of SYSTEM_ARCHITECTURE.md §2.11/§4.1, where the Dashboard was a placeholder Python module — recorded in DECISIONS.md (ADR-0022). FR-DB-05 (dashboard reads from API, not models) is preserved.

**Minimum dependency set (deliberately small):**
- `react`, `react-dom`
- `react-router-dom` — 8 flat pages, deep links per page
- `echarts` — charts (§32.2)
- No state-management library (component state + fetch)
- No CSS framework — design tokens via CSS custom properties + CSS Modules (§32.3)
- No HTTP library beyond `fetch` (a ~50-line typed client)

### 32.2 Charting Recommendation: ECharts

| Library | Verdict | Rationale |
|---------|---------|-----------|
| **ECharts** | ✅ **MVP** | One library covers line/candlestick/bar/histogram + dataZoom + crosshair; canvas performance at 10 y of daily data; tree-shakeable; no extra React binding required |
| Chart.js | ⚠️ | Fine but weaker multi-pane/time-series tooling |
| Recharts | ⚠️ | SVG, React-native; okay for simple charts, thin for financial time series |
| Plotly | ⚠️ | Powerful but heavy bundle and notebook aesthetic |
| TradingView lightweight-charts | ⏸ Future | Best-in-class price charting; defer — one chart library in MVP |

### 32.3 Styling Recommendation: CSS Modules + Design Tokens

| Option | Verdict |
|--------|---------|
| **CSS Modules + CSS custom properties (tokens)** | ✅ **MVP** — zero-config in Vite, scoped, token-driven (§21) |
| Tailwind CSS | ⚠️ | Utility conventions can fight a tokenized design system; adds toolchain; reconsider if the team standardizes on it |
| CSS-in-JS | ❌ | Runtime cost, unnecessary |

**Explicitly avoided:** component UI kits (MUI/Ant/Chakra) and dashboard templates — unnecessary frameworks for a bespoke research UI (spec: avoid unnecessary UI frameworks).

---

## 33. Performance

### 33.1 MVP Targets (configurable, not premature optimization)

| Target | Value |
|--------|-------|
| Initial page load (Overview) | < 1 s on localhost |
| Route navigation | instant (SPA, lazy route chunks) |
| Bundle | ≤ 350 KB gzipped JS baseline; route-level code splitting |
| Chart load (10 y daily) | < 300 ms render |
| Table render | 50 rows default, no virtualization needed below ~500 rows |

### 33.2 Techniques

| Technique | Applied where |
|-----------|---------------|
| Lazy loading | Heavy chart modules + less-visited routes (Experiments detail, Backtest detail) loaded on demand |
| Limited API calls | One request per view; server returns the full series window; client-side range slicing (§24) |
| Caching | In-memory cache per endpoint+params with short TTL; browser HTTP cache for static assets; stale-while-revalidate for status cards |
| Efficient tables | Pagination over virtualization in MVP (§25) |
| No premature optimization | No micro-benchmarks, no WebSocket, no service workers in MVP |

---

## 34. Responsible Data Presentation

### 34.1 Never exaggerate model confidence

| Forbidden pattern | Why |
|-------------------|-----|
| Oversized "WIN RATE" banners | Implies reliability from one number |
| Deceptive green/red profit effects | Color-only success cues; gambling-like |
| Animated/gamified interactions | Undermines scientific reading |
| Fake certainty ("72% correct!") | Probabilities are model scores; calibration may be unvalidated |
| Unexplained confidence scores | Confidence must always carry its definition (P of predicted class) + calibration status |

### 34.2 The interface must look like a scientific product

- Numbers over slogans; tables over banners; labels over legends-only.
- Precision formatting consistent (metrics from backend, formatted, never rounded in ways that flip meaning).
- Equity curves normalized and labeled `Hypothetical $1.00` (EVAL §16.1).
- Historical performance is *always* marked historical/simulated.

---

## 35. Figma / Design Handoff

For every major page, the following handoff spec is provided (summarized here; full per-page rows in §36 and layout in §6–18):

| Handoff field | Spec source |
|---------------|-------------|
| Page purpose | §7–18 (one line each) |
| Layout | §6 shell + §7–18 anatomy diagrams |
| Hierarchy | §6/§7 (title → context → primary panel → secondary) |
| Components | §31 component list per page (§36) |
| Interactions | §24 + per-page flows (§37) |
| Data dependencies | §29/§30 + §36 data-source column |
| Responsive behavior | §22 per page |
| States | §26 per page (loading/empty/error/stale) |
| Tokens | §20/§21 (typography, spacing, color roles) |

A visual design tool (Figma) can reproduce the interface from §6–§36 without further product decisions; the spec fixes information architecture, tokens, components, and states so design work is visual polish, not rediscovery.

---

## 36. Page Inventory

| # | Page | Purpose | Primary user | Primary components | Data source | Key actions | Empty state | Error state |
|---|------|---------|--------------|--------------------|-------------|-------------|-------------|-------------|
| 1 | **Overview** | Status: model, latest prediction, performance, errors, changes | All | MetricCards ×7, status strip, mini equity chart, recent-activity table | /model/info, /predictions, /backtests, /experiments, /datasets, /health (+§29 additions) | Navigate to detail pages; refresh | "No model/dataset/backtest yet — see README quickstart" | Card-level error + System Health link |
| 2 | **Market Explorer** | Chart instrument price + prediction/signal context | Researcher, quant | PriceChart, overlay layers, prediction/signal markers, detail panel | /candles/{ticker}, /predictions (audit), decision log (+§29) | Select instrument/range/overlays; open prediction | "No data for this instrument" | "Instrument data unavailable — check ingestion" |
| 3 | **Prediction** | Full model vs decision breakdown for one (ticker, time) | Researcher | ProbabilityChart, RiskIndicator, ReasonCodeList, MetadataPanel | POST /predict response record / audit replay (+§29) | Open in market explorer; view audit JSON | "No prediction record for this selection" | "Prediction record unavailable/expired" |
| 4 | **Backtest** | Review backtest identity/performance/risk/benchmarks | Researcher, quant | EquityChart, DrawdownChart, ReturnsHistogram, MetricCards, DataTable (trades), Benchmark table | /backtests/{id} (+§29) → metrics JSON, curves CSV, ledger | Choose backtest; inspect trades; compare benchmark; export report link | "No backtests — run pipeline backtest first" | "Backtest outputs incomplete/corrupt" |
| 5 | **Experiments** | List, filter, compare experiments | Researcher | DataTable, ExperimentCard, ComparabilityNotice, two-column compare | /experiments, /experiments/{id} (+§29) | Compare A vs B; open model/dataset links | "No experiments yet" | "Experiment records unavailable" |
| 6 | **Models** | Model info + status facets | Researcher, developer, owner | Model detail, facet StatusBadges, DataTable, MetricsPanel (validation vs backtest) | /models, /model/info (+§29) | View version; view validation/backtest metrics | "No model registered" | "Registry unreadable — see System Health" |
| 7 | **Datasets** | Dataset identity + quality | Researcher | Dataset detail, quality score breakdown, lineage line | /datasets (+§29) | View version; open quality report | "No datasets built" | "Dataset metadata missing" |
| 8 | **System Health** | System/API/data/model status + events | Developer, owner | Status blocks, event table, AlertBanner | /health, /system/status (+§29) | Refresh; open failing component | "No events recorded" | "Health API unreachable" |

**MVP page count: 8.** Deliberately limited; every page maps to a backend record type (§5.1).

---

## 37. MVP User Flows

### FLOW A — Open Dashboard → inspect active model → inspect latest prediction
```
Overview
  → Active Model card: model version, type, validation acc, backtest Sharpe
  → [View] → Models page (detail)
  ← back to Overview
  → Latest Prediction card: AAPL · P(UP) 0.62 · NO_TRADE
  → [View] → Prediction View (probabilities + reasons)
```

### FLOW B — Select instrument → market chart → prediction → decision reasons
```
Market Explorer
  → pick AAPL · range 1Y · interval 1d
  → price + volume render; prediction markers appear
  → hover marker at 2026-09-04
  → Prediction View opens for that timestamp
  → DECISION OUTPUT panel: NO_TRADE + reason codes (CONFIDENCE_BELOW_THRESHOLD, EDGE_BELOW_COST)
  → "why?" tooltip shows code definition from backend code map
```

### FLOW C — Open Backtest → performance → risk → benchmark
```
Backtests page → select bt_20260904_153000
  → identity panel (model/dataset/feature/label/strategy versions, period, costs)
  → primary metrics (cumulative return, Sharpe, max DD)
  → equity curve vs Buy & Hold vs Zero-Trade
  → drawdown curve; risk section (max DD reference)
  → benchmark table (same period, labeled)
```

### FLOW D — Open Experiments → compare → inspect configuration
```
Experiments page → select exp_A and exp_B
  → comparability gate: compatible → side-by-side metrics
  → incompatible → ComparabilityNotice listing differing dimensions
  → expand config snapshot: model params, seed, dataset/feature/label versions
```

### FLOW E — Open System Health → identify issue
```
System Health → status blocks (API ok, model ok, DATA STALE)
  → STALE banner: last update timestamp vs expected freshness
  → events table filtered to WARNING/ERROR
  → affected component → link to Dataset/Ingestion context
```

---

## 38. UX Acceptance Criteria

The UI/UX specification is complete when:

| Criterion | Status |
|-----------|--------|
| Navigation is defined (8 flat items, justified) | ✅ §5 |
| Page inventory is defined (8 pages, full spec table) | ✅ §36 |
| Key user flows are defined (5 flows) | ✅ §37 |
| Prediction UI is defined (model vs decision separation) | ✅ §9 |
| Risk UI is defined (score + level + scale, non-color) | ✅ §11 |
| Backtest UI is defined (identity, metrics, curves, benchmarks) | ✅ §13–14 |
| Experiment comparison is defined (compatibility gate) | ✅ §15 |
| Model/dataset metadata is defined (status facets, lineage) | ✅ §16–17 |
| System health is defined (lightweight) | ✅ §18 |
| Error/empty/loading states are defined (per page) | ✅ §26, §36 |
| Accessibility is addressed (WCAG AA, non-color, keyboard) | ✅ §21, §23 |
| Responsive behavior is addressed (desktop-first subset) | ✅ §22 |
| Research/live separation is enforced (no trade UI) | ✅ §6, §28 |
| Responsible data presentation rules exist | ✅ §3, §34 |
| API → UI and Backtest → UI contracts defined | ✅ §29–30 |
| Design system + color tokens + component hierarchy defined | ✅ §20–21, §31 |
| Backend gaps documented, not silently invented | ✅ §29.3, §39 |

---

## 39. Consistency Check

Cross-checked against: PRD_MVP.md, SYSTEM_ARCHITECTURE.md, DATA_ARCHITECTURE.md, DATASET_BUILDER_BLUEPRINT.md, BASELINE_MODEL_BLUEPRINT.md, TRAINING_PIPELINE_BLUEPRINT.md, EVALUATION_BACKTESTING_BLUEPRINT.md, RISK_DECISION_ENGINE_BLUEPRINT.md, INFERENCE_API_BLUEPRINT.md.

### 39.1 Consistency Table

| Document | Check | Status |
|----------|-------|--------|
| PRD_MVP.md | FR-DB-01..06 (predictions + confidence, backtest metrics, equity curve, model info, dashboard reads API, simple) | ✅ All satisfied by pages 1/3/4/6; FR-DB-05 enforced in §29 |
| PRD_MVP.md | US-07 + Milestone 6 exit criteria | ✅ Covered by Overview/Backtest/Prediction pages |
| SYSTEM_ARCHITECTURE.md | §2.11 Dashboard module (reads API responses) | ✅ Architecture preserved; §32 refines the module into a static SPA — see finding F1 |
| DATA_ARCHITECTURE.md | model_predictions table (future) vs JSONL audit | ✅ UI reads audit trail via API; DB is future home (§29) |
| DATASET_BUILDER_BLUEPRINT.md | Dataset metadata + versioning | ✅ Dataset page mirrors fields (§17) |
| BASELINE_MODEL_BLUEPRINT.md | ModelVersion + registry statuses (active/deprecated/archived) | ✅ Model page shows registry facet (§16) |
| TRAINING_PIPELINE_BLUEPRINT.md | Experiment identity, 5-status lifecycle, gate outcomes, metric separation, no auto-deployment | ✅ Experiments/Models pages mirror exactly (§15–16, §19) |
| EVALUATION_BACKTESTING_BLUEPRINT.md | §15 metrics, §16 curves, §17 benchmarks, §27 outputs, §28 ledger | ✅ Backtest/Benchmark pages map 1:1 (§13–14, §30) |
| RISK_DECISION_ENGINE_BLUEPRINT.md | Reason codes, risk score, no-trade policy, research labeling, strategy versions | ✅ Prediction/risk UI mirrors (§9–12); research-safety copy (§3/§28) |
| INFERENCE_API_BLUEPRINT.md | 4 endpoints, response contract, modes, error model | ✅ Prediction View fully backed; modes shown in shell (§6) |

### 39.2 Findings

| # | Finding | Type | Resolution |
|---|---------|------|------------|
| **G1** | **Dashboard read endpoints do not exist.** INFERENCE_API_BLUEPRINT defines only /predict, /health, /model/info, /version. Market data, prediction history, backtests, experiments, models list, datasets, and system status are not servable to the UI without additions — yet PRD FR-DB-05 requires the dashboard to read from the API | **Missing API data** | §29.3 lists the required read-only additions to be specified during implementation (same FastAPI process). Do NOT build the dashboard on direct file/model access |
| **G2** | UI-spec-style statuses "Candidate/Validated/Rejected/Archived" do **not** exist in the backend. Real statuses: pipeline CREATED/RUNNING/COMPLETED/FAILED/INVALIDATED (TRAINING §12), registry active/deprecated/archived (BASELINE §7.3), gate PASS/REJECT/INCONCLUSIVE/NEEDS_MORE_DATA (TRAINING §20) | **Conflicting terminology** | UI uses facet badges of real backend statuses (§16.3, §19); invented taxonomy rejected |
| **G3** | "Confidence" in the /predict response is P(argmax class). The UI must not present it as general model accuracy or certainty; calibration may be unvalidated (EVAL §5.2; reason code CALIBRATION_UNVALIDATED) | Terminology / trust | §9.4, §10.2 explicit labeling |
| **G4** | SYSTEM_ARCHITECTURE §4.1 places the dashboard under `src/dashboard/` as a Python module; §32 recommends a Vite/React SPA served by the API | Architecture refinement | Documented in ADR-0022 (DECISIONS.md). FR-DB-05 preserved; no unrelated files modified |
| **G5** | No unnecessary MVP features added: no settings page, no live mode, no market index benchmark UI, no portfolio/order UI (all PRD out-of-scope) | Scope | Confirmed absent (§5.1, §28) |
| **G6** | Risk/signal copy must carry research labels and the risk-score definition (6-component, informational) | Terminology | §11.3, §12 |

### 39.3 No silent invention

Every data field the UI displays traces to a backend record or endpoint named in §29/§30 or to a documented required addition (§29.3). Nothing is fabricated.

---

## 40. Deliverables

| Deliverable | Status |
|-------------|--------|
| `docs/UI_UX_BLUEPRINT.md` | ✅ This document (contains component spec + IA per §2) |
| `docs/CURRENT_STATE.md` | ⏳ To update — add blueprint (19 docs), ADR-0022 |
| `docs/DECISIONS.md` | ⏳ To update — add ADR-0022 (Dashboard UI/UX + frontend stack) |

Do not modify unrelated files.

---

## 41. Stop Condition

**This document is UI/UX architecture and design specification only.**

**DO NOT:**
- Write React code
- Write CSS
- Install frontend dependencies
- Create dashboard implementation
- Connect APIs
- Create mock production functionality
- Implement charts

**STOP after the UI/UX architecture and design specification is complete.**

---

## Final Report

### A. Final MVP Navigation

Eight flat items: **Overview · Market Explorer · Predictions · Backtests · Experiments · Models · Datasets · System Health.** Each maps to one backend domain record; no nesting, no settings page.

### B. Final Page Inventory

8 pages (Overview, Market Explorer, Prediction, Backtest, Experiments, Models, Datasets, System Health) — full spec in §36 with purpose, components, data source, actions, empty/error states. Deliberately limited count.

### C. Primary User Flows

Five flows (§37): A overview→model→prediction; B instrument→chart→prediction→decision reasons; C backtest→performance→risk→benchmark; D experiments→comparison→config; E system health→issue identification.

### D. Design-System Recommendation

Light theme by default; token-driven semantic color roles; 4 px spacing scale; mono tabular-nums for all data; system font stack (offline-safe); text+glyph status badges; neutral probability bars with single accent; risk shown as number + Low/Moderate/High + segmented scale. Analytical readability over trend.

### E. Frontend Stack Recommendation

**Vite + React + TypeScript SPA**, served as static assets by FastAPI (same origin), typed fetch client, react-router-dom, CSS Modules + CSS custom-property design tokens. No state library, no UI kit, no Tailwind in MVP. Records a genuine refinement of SYSTEM_ARCHITECTURE's Python dashboard placeholder → **ADR-0022**.

### F. Charting Recommendation

**ECharts** (single library): equity/drawdown/returns-histogram/price charts, dataZoom and crosshair built in. TradingView lightweight-charts reserved for future price-chart specialization. Charts never color-only (§21.2) and always paired with numeric/table equivalents.

### G. Accessibility Strategy

WCAG 2.1 AA contrast; keyboard-complete with visible focus rings; every chart has a data table or numeric summary; non-color status indicators (glyphs + text) everywhere; screen-reader labels; `prefers-reduced-motion` support; mono tabular-nums ≥ 13 px.

### H. Research-Mode Safety Strategy

Persistent `RESEARCH MODE` / `PAPER SIMULATION` badge in the global shell; no order/trade/live UI of any kind; all backtest numbers labeled simulated/historical; footer disclaimer on every page; structurally no execution path exists in the product (backend has no live mode either).

### I. Backend/UI Contract Gaps

- **Primary gap (G1):** the inference API's 4 endpoints cannot feed 6 of the 8 pages. Required additions (read-only, same FastAPI process): `/candles/{ticker}`, `/predictions`, `/backtests[/{id}]`, `/experiments[/{id}]`, `/models`, `/datasets[/{version}]`, `/system/status`. Must be specified before dashboard implementation.
- **Terminology (G2/G3):** invented "Candidate/Validated/Rejected/Archived" taxonomy rejected in favor of real backend facets; confidence always labeled as P(predicted class) with calibration status.
- **Architecture (G4):** SPA recommendation refines SYSTEM_ARCHITECTURE §2.11/§4.1 — recorded as ADR-0022.
- No other conflicts; every UI field traces to a backend record (§39.3).

### J. Exact Next Recommended Task

1. Update `CURRENT_STATE.md` (19 docs, 22 ADRs) and add **ADR-0022** to `DECISIONS.md` (Dashboard UI/UX + frontend stack: Vite/React/TS SPA served by FastAPI; light theme; ECharts).
2. **Specify the dashboard read API** (extend INFERENCE_API_BLUEPRINT §6 with the §29.3 endpoint list) — the gating dependency for 6 of 8 pages.
3. Then continue the existing roadmap: finish Phase 2 implementation (Data Layer) per CURRENT_STATE — the dashboard (Milestone 6) is implemented last, after the data → features → labels → dataset → model → backtest → API layers exist.