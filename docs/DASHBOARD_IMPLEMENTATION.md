# Research Dashboard Implementation (Milestone 10)

Status: **Implemented and verified** (2026-09-07). Read-heavy research UI per
`docs/UI_UX_BLUEPRINT.md`. Research-only — no execution controls exist anywhere
in the frontend.

## 1. Stack

| Layer      | Choice                                    | Rationale (UI_UX §29) |
| ---------- | ----------------------------------------- | --------------------- |
| Framework  | React 19 + TypeScript (strict)            | approved in blueprint |
| Build      | Vite 7                                    | approved in blueprint |
| Styling    | CSS Modules + design tokens (`tokens.css`) | approved, no UI framework |
| Routing    | react-router v7 (`createBrowserRouter`)    | approved |
| Charts     | Apache ECharts 6 (`echarts/core`, tree-shaken) | approved single chart lib |
| Tests      | Vitest + @testing-library/react + jsdom   | approved |

## 2. Backend additions (read-only endpoints)

UI_UX §29.3 requires dashboard read endpoints "specified at implementation
time (same FastAPI process; read-only; file-backed)". Implemented in
`src/api/reads.py`, mounted in `src/api/app.py`:

| Endpoint | Source |
| -------- | ------ |
| `GET /datasets` | `data/processed/datasets/*/manifest.json` |
| `GET /datasets/{version}` | manifest + quality report |
| `GET /models` | `data/processed/models/*/metadata.json` |
| `GET /experiments` | `experiments/*/metadata.json` |
| `GET /experiments/{id}` | full experiment metadata |
| `GET /backtests` | `backtests/*/metadata.json` |
| `GET /backtests/{id}` | metadata + metrics + equity/drawdown/trades/benchmarks |
| `GET /candles/{ticker}?limit=` | cleaned CSV (closes/volumes only) + `stale` flag |
| `GET /predictions?ticker=&limit=` | prediction audit JSONL (newest first) |
| `GET /system/status` | latest dataset/model/experiment/backtest + counts |

All endpoints are read-only (no mutation of any artifact), reuse the existing
`AppConfig` paths, and return the standardized error envelope on failure.
Tested in `tests/test_api_reads.py` (13 tests).

## 3. Routes / pages

| Route | Page | Notes |
| ----- | ---- | ----- |
| `/` | Overview | 7 summary cards (§7.3), quick links |
| `/market` | Market Explorer | price+volume chart, stale banner, ticker/range selectors |
| `/predictions` | Predictions | MODEL OUTPUT vs DECISION OUTPUT vs METADATA sections (§9.3), audit table, live replay button |
| `/backtests` | Backtests | identity panel, net-of-cost metrics, equity/drawdown charts, benchmark table, trade ledger |
| `/experiments` | Experiments | list + detail, metric comparison guardrails |
| `/models` | Models | registry table with validation metrics |
| `/datasets` | Datasets | lineage + quality badges |
| `/system` | System Health | /health, /ready checks, pipeline activity |

## 4. Component system

`AppShell` (sidebar + topbar with persistent **RESEARCH MODE** badge, §6),
`StatusBadge` (text tone tag — never color alone, §27), `MetricCard`
(definition tooltip), `DataTable` (paginated, captioned), `ProbabilityChart`
(exact values visible, §10.2), `EquityChart`/`DrawdownChart`/`PriceChart`
(ECharts wrappers with `role="img"` aria summaries), `LoadingState`,
`ErrorState` (code + request id, §24), `EmptyState` (guidance, §23),
`StaleDataBanner` (§25).

## 5. API integration

Single typed client `dashboard/src/api/client.ts` — all backend access goes
through it; components never fetch directly. Adds `X-Request-Id` to every
call, converts the backend error envelope into `ApiError` (code, message,
request id, status). Base URL: same-origin `/api` via the Vite dev proxy, or
`VITE_API_BASE` override. Data ownership: the backend is authoritative; the
UI only renders values (§30).

## 6. Local development

```bash
# Terminal 1 — API (development env aligns versions with live artifacts)
ENVIRONMENT=development .venv/Scripts/python.exe -m scripts.run_api --port 8000

# Terminal 2 — dashboard dev server (proxies /api → localhost:8000)
cd dashboard && npm install && npx vite --port 5173
# open http://localhost:5173

# Production bundle
cd dashboard && npm run build && npx vite preview --port 4173
```

Environment variables (public-safe only): `VITE_API_BASE` (optional API base
override). No secrets in the frontend; `.env.example` documents the variable.

## 7. Tests

`cd dashboard && npx vitest run` — 35 tests across:

- `src/api/client.test.ts` — success / validation error / server error /
  stale data / network failure conversion (§39 API integration)
- `src/components/components.test.tsx` — StatusBadge (non-color text tone),
  MetricCard, ProbabilityChart (values visible), DataTable, states (§39)
- `src/pages/pages.test.tsx` — Overview, Predictions (§9.3 separation, §14
  risk-as-text), Backtests (§23 empty state, §30.2 net-of-cost labeling),
  Models, Datasets, SystemHealth, error states (§39)
- `src/shell/AppShell.test.tsx` — RESEARCH MODE badge, nav, model indicator

Type safety: `npx tsc --noEmit` passes (strict). Production build: `npm run
build` succeeds.

## 8. Known limitations

- No visual-regression system (blueprint §40: do not introduce one for MVP);
  pages verified via component/page tests + manual inspection.
- Charts are jsdom-untestable below the accessible summary layer; the ECharts
  option objects are unit-checked indirectly through the wrappers.
- No WebSocket/live updates (§32: not required for MVP).
- The live-prediction replay button sends an empty feature payload and relies
  on server-side defaults only for demonstration; audited history remains the
  primary data source.
- Mobile layout is functional but not the primary target (§26).
