# DECISIONS.md — Architecture Decision Records

> Every significant architectural decision is recorded here.
> Prevents silent architecture drift.

---

## Format

```markdown
### ADR-NNNN: Title

- **Date:** YYYY-MM-DD
- **Status:** Accepted | Superseded | Deprecated
- **Context:** What is the issue?
- **Decision:** What was decided?
- **Consequences:** What are the trade-offs?
- **Alternatives Considered:** What else was evaluated?
```

---

## ADR-0001: Project Initialization — Foundation Only

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** Starting a new Finance AI project. Need engineering foundation before features.
- **Decision:** Initialize with documentation, directory structure, and standards only. No implementation.
- **Consequences:**
  - ✅ Clear contract for future development
  - ✅ No premature architecture decisions
  - ⚠️ No working code yet (intentional)

## ADR-0002: Python as Primary Language

- **Date:** 2026-09-04
- **Status:** Accepted
- **Decision:** Python 3.10+ for all components.
- **Consequences:**
  - ✅ Best ML ecosystem (pandas, scikit-learn, numpy)
  - ✅ Largest talent pool
  - ⚠️ Runtime performance vs compiled languages (acceptable for MVP)

## ADR-0003: YAML-Based Configuration

- **Date:** 2026-09-04
- **Status:** Accepted
- **Decision:** YAML for all configuration files in `config/`.
- **Consequences:**
  - ✅ Human-readable, supports comments, Git-friendly
  - ⚠️ No built-in schema validation (mitigated by explicit validation)

## ADR-0004: Chronological Data Splits Only

- **Date:** 2026-09-04
- **Status:** Accepted
- **Decision:** All train/val/test splits MUST be chronological. No random splitting.
- **Consequences:**
  - ✅ Prevents look-ahead bias
  - ✅ Realistic evaluation
  - ⚠️ May show lower accuracy than random splits (this is correct)

## ADR-0005: File-Based Data Storage (MVP)

- **Date:** 2026-09-04
- **Status:** Accepted
- **Decision:** Local file system (CSV/Parquet) for data storage. No databases.
- **Consequences:**
  - ✅ Zero infrastructure, fully local, version-controllable
  - ⚠️ Not suitable for concurrent access (acceptable for MVP)

## ADR-0006: structlog for Logging

- **Date:** 2026-09-04
- **Status:** Accepted
- **Decision:** `structlog` for all logging. No `print()` in production code.
- **Consequences:**
  - ✅ Machine-parseable, consistent format, contextual logging

## ADR-0007: No Cloud/External Dependencies (MVP)

- **Date:** 2026-09-04
- **Status:** Accepted
- **Decision:** No cloud SDKs, no external APIs, no cloud storage in MVP.
- **Consequences:**
  - ✅ Fully reproducible locally, works offline
  - ⚠️ Data must be manually provided (acceptable for MVP)

## ADR-0008: MVP Product Requirements Document

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** The project has engineering standards but no formal product specification. Need a single source of truth for MVP scope, requirements, and acceptance criteria.
- **Decision:** Create `docs/PRD_MVP.md` as the authoritative MVP product requirements document covering all 12 required sections: vision, problem, users, functional/non-functional requirements, user stories, I/O contracts, success metrics, risks, out-of-scope, milestones, and acceptance criteria.
- **Consequences:**
  - ✅ Clear, unambiguous scope for all future implementation tasks
  - ✅ Every feature can be traced to a requirement ID
  - ✅ Acceptance criteria enable objective verification
  - ⚠️ PRD must be kept in sync with implementation (living document)

## ADR-0009: System Architecture Blueprint

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** The project needs a detailed technical architecture to guide implementation. ARCHITECTURE_PRINCIPLES.md defines layer boundaries; this blueprint defines the concrete module structure, data flow, API contracts, and testing strategy.
- **Decision:** Create `docs/SYSTEM_ARCHITECTURE.md` with: high-level architecture diagram, module breakdown (12 modules), detailed data flow, production folder structure, API boundaries, database boundaries, configuration architecture, logging architecture, testing architecture, and future extension points (News Engine, Options Engine, Risk Engine, Autonomous Retraining, LLM Agent).
- **Consequences:**
  - ✅ Clear module responsibilities and interfaces for implementation
  - ✅ Dependency graph enforces no circular dependencies
  - ✅ Extension points defined for future phases without rewrites
  - ✅ Testing architecture provides concrete coverage targets
  - ⚠️ Architecture must be updated if module responsibilities change

## ADR-0010: Data Architecture & Database Blueprint

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** The project needs a comprehensive data architecture defining PostgreSQL schema, time-series rules, validation rules, storage lifecycle, and feature/label storage strategy. MVP uses file-based storage; this defines the target database for Phase 2+.
- **Decision:** Create `docs/DATA_ARCHITECTURE.md` with: 8 core tables (instruments, market_candles, corporate_actions, trading_calendar, features, labels, dataset_versions, model_predictions), EAV feature storage with materialized view option, chronological partitioning strategy, 15 OHLCV validation rules, 5 feature validation rules, 4 label validation rules, 3-tier storage lifecycle (raw/interim/processed), and 5 future expansion placeholders (news, options, order book, macro, risk).
- **Consequences:**
  - ✅ Complete PostgreSQL schema ready for Phase 2 migration
  - ✅ Time-series rules enforce UTC timestamps and chronological integrity
  - ✅ Validation rules catch data quality issues at ingestion
  - ✅ Feature-label separation enforced at schema level
  - ✅ Future expansion tables defined as placeholders
  - ⚠️ MVP uses files; database schema is reference architecture

## ADR-0011: Data Ingestion Engine Blueprint

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** The project needs a detailed ingestion pipeline design covering data sources, fetch-validate-normalize-store flow, backfill/incremental strategies, error handling, and metadata tracking. Must be idempotent, traceable, and produce immutable raw data.
- **Decision:** Create `docs/DATA_INGESTION_BLUEPRINT.md` with: 4 MVP data sources (Yahoo Finance primary, NSE secondary, Trading Calendar, Corporate Actions), 6-stage pipeline (Source→Fetch→Validate→Normalize→Store→Log), 5 backfill modes (quick/recent/standard/full/custom), daily incremental update with trading calendar integration, 15 validation rules, normalization rules (timestamps/symbols/intervals/precision), exponential backoff retry with rate limiting, full metadata tracking with checksums, and 5 future extension placeholders (WebSocket, news, options, macro, sentiment).
- **Consequences:**
  - ✅ Clear ingestion pipeline design for implementation
  - ✅ Idempotent updates prevent duplicate data
  - ✅ Rate limiting prevents source API abuse
  - ✅ Metadata tracking enables full audit trail
  - ✅ Error handling ensures partial failures don't block pipeline
  - ⚠️ MVP uses Yahoo Finance only; NSE is secondary priority

## ADR-0012: Data Cleaning & Validation Engine Blueprint

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** The project needs a comprehensive data cleaning and validation engine design covering pipeline stages, validation rules, corporate action adjustments, missing data strategies, outlier detection, quality scoring, audit trail, and error categorization. Raw data must remain immutable and every transformation must be logged.
- **Decision:** Create `docs/DATA_CLEANING_VALIDATION.md` with: 7-stage cleaning pipeline (Load→Schema Validate→Data Validate→Clean→Normalize→Quality Score→Output), 23 validation rules across 5 categories (schema/price/volume/timestamp/completeness), corporate action adjustment strategy (backward adjustment for splits/dividends), 5 missing data strategies (forward fill, backward fill, interpolate, drop, mark) with gap-length-based selection, 3 outlier detection methods (z-score, IQR, rolling window) with multi-window consensus, 5-dimension quality scoring (completeness 30%, validity 30%, consistency 20%, freshness 10%, uniqueness 10%) on 0-100 scale, full audit trail with SHA-256 hash chain (raw→cleaned→features→dataset→model), and 5 error categories with 4 severity levels (critical/error/warning/info).
- **Consequences:**
  - ✅ Complete cleaning pipeline design for implementation
  - ✅ Raw data immutability enforced by design
  - ✅ Quality scoring enables automated data gates
  - ✅ Audit trail provides full traceability to raw data
  - ✅ Error categorization ensures consistent handling
  - ⚠️ Corporate action adjustments require accurate action data

## ADR-0013: Feature Engineering Engine Blueprint

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** The project needs a comprehensive feature engineering design covering feature taxonomy, mathematical definitions, lookback windows, normalization, leakage analysis, validation, versioning, storage, and future extensions. Must align with PRD requirements (FR-FE-01 to FR-FE-10) and system architecture (FeatureEngine module).
- **Decision:** Create `docs/FEATURE_ENGINEERING_BLUEPRINT.md` (28 sections) and `docs/FEATURE_CATALOG.md` (52-feature specification table). 52 MVP features across 8 categories: Price/Return (8), Trend (8), Momentum (6), Volatility (8), Volume (6), Volume-Price (4), Bollinger (6), Candle Structure (6). Precompute-and-persist strategy using Parquet files. No scaling for tree models, StandardScaler for logistic regression. Feature versioning via SHA-256 hash. 5 future extension placeholders (news, fundamentals, options, orderbook, macro).
- **Consequences:**
  - ✅ Complete feature engineering design for implementation
  - ✅ Every feature has mathematical definition and leakage assessment
  - ✅ 52 features — focused set, not 200+ indicators
  - ✅ Anti-overfitting rules prevent feature explosion
  - ✅ Future extensions clearly separated from MVP
  - ⚠️ Feature validation and selection are ongoing research tasks

## ADR-0014: Label Generation & Target Definition Blueprint

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** The project needs a comprehensive label generation design covering prediction problem definition, direction classification, prediction horizon, future return formulation, HOLD class design, timing contract, leakage prevention, label generation algorithm, edge cases, overlapping labels, class balance, transaction cost awareness, versioning, metadata, and research experiments. Must align with PRD requirements (FR-LG-01 to FR-LG-05) and system architecture (LabelEngine module).
- **Decision:** Create `docs/LABEL_GENERATION_BLUEPRINT.md` with 25 sections. Primary target: Direction Classification (UP/DOWN/HOLD). Horizon: 5 trading days. Thresholds: ±1%. Simple returns over log returns. Fixed thresholds (not adaptive). No cost-aware labels in MVP. No temporal purging for daily data. Architecture supports future multi-target extensions (regression, volatility, adverse movement).
- **Consequences:**
  - ✅ Complete label generation design for implementation
  - ✅ Every edge case documented with handling strategy
  - ✅ Leakage prevention rules are explicit and testable
  - ✅ Class balance monitoring strategy defined
  - ✅ Future extensions clearly separated from MVP
  - ✅ Consistent with all previous architecture documents
  - ⚠️ Threshold tuning is a research task (not automatic)
  - ⚠️ `config/default.yaml` has `label_type: regression` but all blueprints specify `classification`. Config must be updated before implementation begins.
- **Cross-reference conflicts:**
  - `config/default.yaml` line 45: `label_type: regression` vs. all blueprint documents specifying `label_type: classification` (PRD_MVP.md, LABEL_GENERATION_BLUEPRINT.md, DATASET_BUILDER_BLUEPRINT.md).

## ADR-0015: Dataset Builder & Versioning Blueprint

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** The project needs a comprehensive dataset builder design covering pipeline stages, schema definition, chronological train/val/test splits, walk-forward dataset strategy, purging/embargo, versioning, storage format, metadata, validation, and future incremental updates. Must align with PRD requirements (FR-DS-01 to FR-DS-05), label generation blueprint, and system architecture (DatasetBuilder module).
- **Decision:** Create `docs/DATASET_BUILDER_BLUEPRINT.md` with 10 sections: 7-stage pipeline (Raw→Clean→Features→Labels→Dataset→Version→Export), 4-column-group schema (metadata/raw/features/labels), chronological split with 60/20/20 ratio, rolling-window walk-forward strategy with configurable step size, purging + embargo window to prevent leakage, semantic versioning (vX.Y) with feature/label/source version tracking, Parquet as MVP storage format (compressed, columnar, typed), rich dataset metadata (rows/symbols/range/quality score), 6 validation checks, and daily incremental append strategy.
- **Consequences:**
  - ✅ Complete dataset builder design for implementation
  - ✅ Walk-forward strategy ensures realistic backtesting
  - ✅ Purging + embargo prevents temporal leakage
  - ✅ Versioning enables reproducible experiments
  - ✅ Parquet provides fast I/O with compression
  - ✅ Consistent with all previous architecture documents
  - ⚠️ Incremental updates require careful dedup logic

## ADR-0016: Baseline ML Model Selection

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** The project needs a baseline ML model design covering model selection (logistic regression vs random forest vs XGBoost vs LightGBM), input contract, training pipeline, hyperparameter strategy, class imbalance handling, experiment tracking, model versioning, checkpointing, reproducibility, failure handling, and future compatibility. Must align with PRD requirements (FR-TM-01 to FR-TM-08) and system architecture (TrainingEngine module).
- **Decision:** Create `docs/BASELINE_MODEL_BLUEPRINT.md` with 11 sections + 2 appendices. MVP baselines: Logistic Regression (P0, linear baseline) + Random Forest (P0, non-linear baseline). XGBoost and LightGBM deferred to future phases per PRD_MVP.md Section 10 (Out of Scope). Deep learning (LSTM, Transformer) explicitly out of scope. Model versioning: v{major}.{minor}.{patch}-{date}. Reproducibility: fixed random seed, config snapshot, environment metadata. Class imbalance: class_weight='balanced'. No automatic hyperparameter tuning in MVP.
- **Consequences:**
  - ✅ Clear baseline model design for implementation
  - ✅ Two models (LR + RF) test linear vs non-linear signal
  - ✅ Reproducibility guarantees (seed, config, env metadata)
  - ✅ Experiment tracking enables comparison across runs
  - ✅ Model registry enables version management
  - ✅ Future extensions (XGBoost, LSTM, ensemble) reserved without rewrite
  - ⚠️ Model configuration must be added to config/default.yaml
  - ⚠️ Random Forest requires n_jobs=1 for full determinism
- **Cross-reference consistency:**
  - PRD_MVP.md FR-TM-01, FR-TM-02: Logistic regression + random forest (matches)
  - SYSTEM_ARCHITECTURE.md Section 2.7: TrainingEngine module (matches)
  - FEATURE_ENGINEERING_BLUEPRINT.md Section 11: Scaling rules (matches — StandardScaler for LR, no scaling for RF)
  - LABEL_GENERATION_BLUEPRINT.md Section 20: Classification target (matches)
  - DATASET_BUILDER_BLUEPRINT.md Section 2.3: DatasetSplit output (matches)

## ADR-0017: Training Pipeline & Experiment Management

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** The project needs a comprehensive training pipeline and experiment management design covering training lifecycle (15 stages), experiment identity, configuration system (YAML), reproducibility strategy, preprocessing rules (fit on train only), hyperparameter management (3-level config), experiment types (6 categories), experiment tracking (parameters, metrics, artifacts), artifact structure, model artifact management, training status lifecycle (5 statuses), failure handling (13 categories), dataset/code/config compatibility checks, seed & randomness policy, compute profile, metric policy (ML vs financial separation), evaluation data separation (three-way split), experiment comparability rules, model selection gate (5 stages), research report format, future MLOps extensions, security & data integrity, testing strategy (7 categories), and research questions (open vs decided). Must align with all previous architecture documents.
- **Decision:** Create `docs/TRAINING_PIPELINE_BLUEPRINT.md` with 29 sections. Training pipeline: 15-stage lifecycle from dataset loading to report generation. Experiment identity: timestamp-based IDs with full version metadata. Configuration: YAML with three-level hierarchy (default → experiment override → environment override). Reproducibility: pin all versions + config hash + seed + environment + code version. Preprocessing: StandardScaler fit on train only (LR), no scaling (RF). Metric policy: strict separation of ML metrics (training) from financial metrics (backtesting). Evaluation data: three-way split with enforced usage rules. Model selection gate: 5-stage process with PASS/REJECT/INCONCLUSIVE/NEEDS_MORE_DATA outcomes. No automatic deployment — gate produces candidate, not deployment.
- **Consequences:**
  - ✅ Complete training pipeline design for implementation
  - ✅ Experiment tracking enables full reproducibility and comparison
  - ✅ Configuration-driven experiments — no hardcoded values
  - ✅ ML and financial metrics properly separated
  - ✅ Model selection gate is future-compatible but MVP-appropriate
  - ✅ Extension points reserved for MLflow, model registry, automated retraining
  - ⚠️ Experiment directory structure must be created during implementation
  - ⚠️ Research report template must be followed for all experiments
  - ⚠️ Test set protection must be enforced architecturally
- **Cross-reference consistency:**
  - PRD_MVP.md FR-TM-01 through FR-TM-08: All match
  - SYSTEM_ARCHITECTURE.md TrainingEngine module: Matches
  - BASELINE_MODEL_BLUEPRINT.md: Complements and extends (model-specific vs pipeline-wide)
  - DATASET_BUILDER_BLUEPRINT.md: Uses pre-computed splits, consistent versioning
  - LABEL_GENERATION_BLUEPRINT.md: Classification target, label versioning consistent
  - FEATURE_ENGINEERING_BLUEPRINT.md: Scaling rules, feature versioning consistent
  - All documents: No conflicts found

## ADR-0018: Evaluation & Walk-Forward Backtesting Framework

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** The project needs a rigorous evaluation and walk-forward backtesting framework covering evaluation layers (data quality, prediction quality, signal quality, strategy performance, robustness), data quality gate (15 checks), prediction metrics (classification + probability + regression), signal evaluation (threshold methodology, validation-only selection), walk-forward validation (expanding window MVP, defaults 252/21/21), temporal leakage controls (purge windows, embargo, 7 leakage types), execution timing (close-to-close MVP convention), transaction cost model (configurable, gross vs net separation), slippage model (fixed percentage MVP), position model (LONG/FLAT only), trading rules (entry/exit/no-trade, max holding period), 15+ financial metrics with formulas, equity curve specifications (5 curves), benchmarks (buy-and-hold, zero-trade), ablation testing, robustness testing (5 market regimes), cost/slippage/threshold sensitivity, model comparison rules, statistical significance framework, overfitting safeguards, final test protocol (8 freeze steps), 9 backtest outputs, trade ledger (16 fields), reproducibility requirements, backtest engine architecture (8 modules), failure conditions (13 scenarios), 14-section report structure, and future extensions.
- **Decision:** Create `docs/EVALUATION_BACKTESTING_BLUEPRINT.md` with 37 sections. Expanding window walk-forward as MVP default. Close-to-close execution convention (simplified, documented limitation). Fixed percentage slippage (5 bps per side). LONG/FLAT position model (no shorting in MVP). Strict separation of ML metrics from financial metrics. Final test protocol with 8 freeze steps — test set evaluated ONCE. No separate backtest logic — shared decision engine required.
- **Consequences:**
  - ✅ Complete backtesting framework for implementation
  - ✅ Walk-forward methodology ensures realistic out-of-sample evaluation
  - ✅ Cost-aware evaluation prevents misleading gross-return claims
  - ✅ Leakage controls align with feature/label architecture
  - ✅ Final test protocol protects test set from overfitting
  - ✅ Backtest engine architecture provides clear module boundaries
  - ⚠️ Execution convention (close-to-close) is simplification — future next-day open
  - ⚠️ Statistical significance limited by trade count and non-i.i.d. data
  - ⚠️ Shared decision engine required — no separate backtest logic
- **Cross-reference consistency:**
  - PRD_MVP.md FR-BT-01 through FR-BT-07: All match
  - SYSTEM_ARCHITECTURE.md BacktestingEngine module: Matches
  - DATASET_BUILDER_BLUEPRINT.md: Uses pre-computed splits, purging aligns
  - LABEL_GENERATION_BLUEPRINT.md: 5-day horizon, close-to-close timing matches
  - TRAINING_PIPELINE_BLUEPRINT.md: Metric separation, model selection gate aligns
  - BASELINE_MODEL_BLUEPRINT.md: Model versioning, experiment tracking aligns
  - All documents: No conflicts found

## ADR-0019: Risk Management & Decision Engine

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** The project needs a deterministic decision layer that converts model outputs into research signals while applying explicit risk controls. Must cover prediction/decision/execution separation, input/output contracts, signal generation (threshold-based, BUY/SELL/HOLD/NO_TRADE), cost-aware decision logic (expected net edge vs minimum), 8 risk filters (volatility, data quality, staleness, model uncertainty, etc.), market regime filter (optional MVP, default: no filter), confidence handling (3 zones, calibration requirement), position sizing (fixed quantity MVP), risk budget (max simultaneous positions = 1, daily loss limit, drawdown guard), stop-loss/take-profit evaluation (default: none in MVP), holding period (5 days, matches label horizon), signal expiry (validity window = horizon), position states (FLAT/LONG only for MVP), conflicting signals (deterministic state-aware resolution), model quality gate (version, status, feature compatibility), data quality gate (price validity, timestamps, features, alignment), risk score (6-component normalized score), decision explanation (22 reason codes), decision log (full DecisionLog structure), backtest integration (shared decision logic required), research safety (disclaimers, prohibited claims), threshold research (validation-only, versioned), sensitivity analysis (4 parameter types), and mandatory no-trade policy.
- **Decision:** Create `docs/RISK_DECISION_ENGINE_BLUEPRINT.md` with 32 sections. Strict separation: Prediction → Decision → Execution (execution OUT OF SCOPE for MVP). Signal generation uses probability thresholds (P(UP) >= 0.55 for BUY). Cost-aware filter: expected net edge must exceed 15 bps minimum. 8 mandatory risk filters — any failure → NO_TRADE. Fixed quantity position sizing (1 unit). Risk budget: max 1 simultaneous position, daily loss limit -2%, drawdown guard -10%. No explicit stop-loss/take-profit in MVP (max holding period provides natural exit). Regime filter NOT enabled in MVP (optional input, logged but not used). Decision Engine must be shared module used by both research and backtest — no separate logic. All outputs labeled as research only.
- **Consequences:**
  - ✅ Complete decision engine design for implementation
  - ✅ Prediction/decision/execution separation enables independent testing
  - ✅ Risk filters ensure no signal bypasses risk controls
  - ✅ Cost-aware decision prevents obviously unprofitable signals
  - ✅ No-trade policy is mandatory feature — system can abstain
  - ✅ Shared decision engine ensures backtest matches research
  - ✅ Research safety statements prevent misleading claims
  - ⚠️ Fixed quantity sizing is simple but not risk-adjusted
  - ⚠️ Calibration validation required before trusting probabilities
  - ⚠️ Regime filter deferred — future enhancement
- **Cross-reference consistency:**
  - PRD_MVP.md FR-PM-01, FR-PM-02, FR-BT-01, FR-BT-03, FR-BT-07: All match
  - SYSTEM_ARCHITECTURE.md Decision/Risk Engine placeholder: Matches
  - EVALUATION_BACKTESTING_BLUEPRINT.md: Position model (LONG/FLAT), trading rules, execution timing, cost model, backtest integration — all align
  - TRAINING_PIPELINE_BLUEPRINT.md: Experiment versioning, metric separation — align
  - LABEL_GENERATION_BLUEPRINT.md: 5-day horizon, threshold research methodology — align
  - BASELINE_MODEL_BLUEPRINT.md: Model versioning — align
  - DATASET_BUILDER_BLUEPRINT.md: Dataset versioning — align
  - FEATURE_ENGINEERING_BLUEPRINT.md: Regime features (future) — align
  - All documents: No conflicts found

## ADR-0020: Prediction / Decision / Execution Separation

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** The project architecture includes multiple blueprints that touch on prediction, decision, and execution concepts (LABEL_GENERATION_BLUEPRINT.md for prediction targets, RISK_DECISION_ENGINE_BLUEPRINT.md for decision logic, EVALUATION_BACKTESTING_BLUEPRINT.md for backtest execution simulation). Need to explicitly document the architectural boundary between these three layers to prevent future drift.
- **Decision:** Establish PREDICTION / DECISION / EXECUTION as a first-class architectural separation across all blueprints. Prediction = what the model says (probabilities, expected returns). Decision = what the system should do based on prediction + risk controls (BUY/SELL/HOLD/NO_TRADE). Execution = how the decision is carried out (order placement, timing, position management — OUT OF SCOPE for MVP). This separation is now an architectural principle applicable to all future blueprints.
- **Consequences:**
  - ✅ Clear architectural boundary prevents confusion between layers
  - ✅ Decision Engine can be tested independently of prediction model
  - ✅ Backtest Engine can be tested independently of live execution
  - ✅ Future execution module can be added without rewriting decision logic
  - ✅ Research safety: Decision Engine outputs are research signals, not trading orders
  - ⚠️ All future blueprints must respect this separation
  - ⚠️ Execution layer is explicitly OUT OF SCOPE for MVP — must not silently expand
- **Cross-reference consistency:**
  - LABEL_GENERATION_BLUEPRINT.md: Defines prediction targets (UP/DOWN/HOLD probabilities) — PREDICTION layer
  - RISK_DECISION_ENGINE_BLUEPRINT.md: Defines decision logic (BUY/SELL/HOLD/NO_TRADE) — DECISION layer
  - EVALUATION_BACKTESTING_BLUEPRINT.md: Defines backtest simulation — EXECUTION layer (research/paper only)
  - All documents: Consistent with this separation

## ADR-0021: Prediction & Inference API Blueprint

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** The project needs a prediction and inference API architecture covering service responsibilities, endpoint contracts, request/response schemas, model resolution, compatibility checks, feature sourcing, input validation, error model, health checks, observability, audit trail, idempotency, security, configuration, backtest compatibility, research/live mode separation, response explanation, contract versioning, testing strategy, and failure/degradation behavior. Must align with PRD API requirements (FR-API-01 to FR-API-08), SYSTEM_ARCHITECTURE.md §2.9/§5.2 (Prediction Service, REST contracts), BASELINE_MODEL_BLUEPRINT.md (registry/artifact structure), and RISK_DECISION_ENGINE_BLUEPRINT.md (shared decision logic, reason codes, strategy versioning).
- **Decision:** Create `docs/INFERENCE_API_BLUEPRINT.md` with 34 sections. Technology: **FastAPI** (locks PRD FR-API-08 choice; already the SYSTEM_ARCHITECTURE §2.9 dependency). Endpoints: POST /predict, GET /health, GET /model/info, GET /version — root paths kept exactly as SYSTEM_ARCHITECTURE.md §5.2 (no `/api/v1/` prefix in MVP; breaking changes must introduce versioned paths later). Feature sourcing: **Approach A — client supplies features** (feature_set_version must match model.feature_version; mismatch → 409). Model resolution: explicit model_version wins, else configured default (registry active_model); version locked per request, no silent switching. Response contract separates **model_output** from **decision_output** per ADR-0020. Shared Decision Engine module reused — backtest logic and API logic are identical. Modes: RESEARCH (default) + PAPER/SIMULATION (optional); LIVE structurally disabled (`mode: live` fails at startup). Audit trail: append-only JSONL under `predictions/audit/`. Contract versioning: five identifiers (API_VERSION, MODEL_VERSION, FEATURE_VERSION, LABEL_VERSION, STRATEGY_VERSION). Error model: 10 machine-readable codes, uniform shape, fail closed — never fabricate predictions.
- **Consequences:**
  - ✅ Complete inference API architecture ready for implementation
  - ✅ FastAPI choice locked, consistent with SYSTEM_ARCHITECTURE.md §2.9
  - ✅ Deterministic version resolution prevents silent model switching
  - ✅ Client-supplied features keep the API thin and reproducible (same feature engine as training)
  - ✅ Model output and decision output separation honors ADR-0020
  - ✅ Shared decision code path guarantees backtest matches API behavior
  - ✅ Research/paper modes only — accidental live operation is structurally impossible
  - ✅ Audit trail supports prediction-vs-actual comparison without online learning
  - ⚠️ `config/default.yaml` needs an `api:` section before implementation
  - ⚠️ Client-supplied features require callers to use the versioned feature pipeline
  - ⚠️ No authentication in MVP — localhost only; auth becomes mandatory if ever exposed
- **Cross-reference consistency:**
  - PRD_MVP.md FR-API-01..08, NFR-PF-01, NFR-SE-04, NFR-CF, NFR-LO: All match
  - SYSTEM_ARCHITECTURE.md §2.9 (Prediction Service), §5.2 (REST contracts), §4.1 (layout): Matches; /predict response extended additively with decision_output
  - BASELINE_MODEL_BLUEPRINT.md §7/§8.2/§8.3/§8.4: Model versioning, artifact structure, registry, loading — align
  - RISK_DECISION_ENGINE_BLUEPRINT.md §4/§21/§23/§25: Input contract, reason codes, shared decision module, strategy versioning — align
  - EVALUATION_BACKTESTING_BLUEPRINT.md: Shared decision logic requirement — align
  - FEATURE_ENGINEERING_BLUEPRINT.md: Feature versioning (SHA-256), precompute-and-persist — align
  - All documents: No conflicts found; two additive changes recorded (decision_output in /predict response; contract versioning policy)

## ADR-0022: Dashboard UI/UX & Frontend Stack

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** The project needs a complete UI/UX architecture for the research + model evaluation dashboard covering product UX principles, information architecture, page inventory, prediction/risk/signal visualization, backtest and experiment review, model/dataset metadata views, system health, status taxonomy, design system, accessibility, responsive behavior, API→UI and Backtest→UI contracts, and research/live separation. SYSTEM_ARCHITECTURE.md §2.11/§4.1 placeholder the dashboard as a Python module (src/dashboard) reading API responses; PRD FR-DB-01..06 define dashboard behavior (reads from API, not models).
- **Decision:** Create `docs/UI_UX_BLUEPRINT.md` with 41 sections. Navigation: 8 flat pages (Overview, Market Explorer, Predictions, Backtests, Experiments, Models, Datasets, System Health), each mapping to one backend domain record. **Frontend stack: Vite + React + TypeScript SPA** served as static assets by the FastAPI backend (same origin), react-router-dom, CSS Modules + CSS custom-property design tokens (light theme default), no state library, no UI kit. **Charting: ECharts** as the single chart library. **Genuine findings:** (1) the inference API's 4 endpoints cannot feed 6 of 8 dashboard pages — required read-only additions (candles, predictions audit, backtests, experiments, models list, datasets, system status) are documented as gaps in §29.3 and must be specified before dashboard implementation; (2) the UI deliberately rejects the invented model-status taxonomy "Candidate/Validated/Rejected/Archived" and instead shows the three real backend status facets (pipeline CREATED/RUNNING/COMPLETED/FAILED/INVALIDATED, registry active/deprecated/archived, gate PASS/REJECT/INCONCLUSIVE/NEEDS_MORE_DATA). Research-mode safety: persistent RESEARCH MODE indicator, no trade/order UI of any kind, all backtest numbers labeled simulated.
- **Consequences:**
  - ✅ Complete UI/UX specification for implementation (pages, flows, components, tokens, states)
  - ✅ Frontend stack decision made — minimal, coherent (no UI kits, no Tailwind, no state library)
  - ✅ FR-DB-05 preserved — dashboard reads only from the API
  - ✅ MODEL OUTPUT vs DECISION OUTPUT separation carried into the UI (ADR-0020)
  - ✅ Research/live separation enforced at the UI layer — no accidental execution path
  - ✅ Responsible data presentation rules prevent misleading certainty/profit claims
  - ⚠️ Introduces a Node toolchain (Vite/React) into a Python repo — refinement of SYSTEM_ARCHITECTURE §2.11/§4.1 dashboard placeholder
  - ⚠️ Dashboard implementation (Milestone 6) is blocked on the §29.3 read-API additions
  - ⚠️ Dashboard is implemented LAST, after data → features → labels → dataset → model → backtest → API layers
- **Cross-reference consistency:**
  - PRD_MVP.md FR-DB-01..06, US-07, Milestone 6: All match
  - SYSTEM_ARCHITECTURE.md §2.11 (Dashboard reads API): Preserved; module refined to static SPA (recorded above)
  - INFERENCE_API_BLUEPRINT.md: Prediction View fully backed by /predict contract; 4 endpoints confirmed; §29.3 gaps flagged (not silently invented)
  - EVALUATION_BACKTESTING_BLUEPRINT.md: Metrics/curves/benchmarks/outputs/ledger displayed 1:1 — never recomputed in the frontend
  - RISK_DECISION_ENGINE_BLUEPRINT.md: Reason codes, risk score, no-trade policy rendered as authoritative backend values
  - TRAINING_PIPELINE_BLUEPRINT.md: Status lifecycle, gate outcomes, metric separation, no auto-deployment — mirrored exactly
  - BASELINE_MODEL_BLUEPRINT.md: Registry statuses mirrored as a status facet
  - DATASET_BUILDER_BLUEPRINT.md: Dataset metadata mirrored
  - All documents: No contradictions; two findings recorded (read-API gap G1, status-terminology reconciliation G2)

## ADR-0023: Milestone 01 — Data Foundation (File-Based, ADR-0005 Confirmed)

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** First implementation milestone (Data Foundation). The milestone brief proposed a PostgreSQL foundation (connectivity, ORM models, Alembic migrations, DB constraint tests). The approved architecture explicitly states the opposite: ADR-0005 "File-Based Data Storage (MVP) — No databases", PRD §10 out-of-scope "Database storage — file-based storage for MVP", DATA_ARCHITECTURE.md is labeled "Phase 2+ reference", and ENGINEERING_CONSTITUTION's allowed-dependency list contains no database driver/ORM. The environment also lacks a PostgreSQL server, psql, and Docker, so DB tests could not be truthfully executed. User decision (recorded): implement the **file-based foundation**; keep PostgreSQL as Phase-2 reference.
- **Decision:** Milestone 01 implements: typed environment-aware configuration (`src/config/`, dataclass-based — no pydantic, per the allowed-dependency policy); structlog logging foundation (`src/logging/`); a dependency-free `src/core/` foundation package (errors, enums, validation primitives, Instrument/Candle domain models, raw/interim/processed storage layout); environment overlay files (`config/development|testing|production.yaml`); `.env.example` documenting `ENVIRONMENT`/`LOG_LEVEL`/`LOG_FORMAT`; `pyproject.toml` tooling config (pytest+coverage, black, isort, ruff at 100 cols); and 105 tests (122 total with the 17 foundation tests) at 97% coverage. No new runtime dependencies added. Validation primitives and the `candle_observation_key` UNIQUE-key mirror the DATA_ARCHITECTURE constraints at the file layer; the ticker/timestamp/price/volume rules come verbatim from DATA_ARCHITECTURE §3/§4/§6.
- **Consequences:**
  - ✅ Milestone fully testable locally with no external services (constitution §6 "no tests that depend on external services")
  - ✅ No dependency additions, no secret exposure, README/CURRENT_STATE accurate
  - ✅ PostgreSQL schema + SQLAlchemy/Alembic choice remains open for the Phase-2 milestone (revisit ADR-0005 then)
  - ⚠️ No DB constraint enforcement exists yet — the file layer enforces constraints at validation time instead
  - ⚠️ `src/core/` was added as a foundation package not named in SYSTEM_ARCHITECTURE §4.1 (which predates implementation); documented here as a layout clarification
- **Alternatives Considered:** (1) Pulling PostgreSQL forward (new deps, ADR-0005 supersession, untestable without a server) — rejected by user; (2) hybrid (untested SQL artifacts scaffolded) — rejected; (3) pydantic-based config models — rejected (not in allowed deps; dataclasses suffice).
- **Cross-reference consistency:**
  - ADR-0005 / PRD §10 / DATA_ARCHITECTURE: File-based MVP confirmed; DB deferred to Phase 2
  - SYSTEM_ARCHITECTURE §4.1: `src/config/` + `src/logging/` match the approved layout; `src/core/` added as documented clarification
  - ENGINEERING_CONSTITUTION: allowed dependencies unchanged; error/logging/config/testing policies followed
  - DATA_ARCHITECTURE §3/§4/§6/§7: validation rules, naive-UTC policy, uniqueness keys, and tier layout mirrored at the file layer

## ADR-0024: Milestone 02 — Yahoo Finance Adapter over Requests (ADR-0011 Deviation)

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** DATA_INGESTION_BLUEPRINT §1.2 names `yfinance` as the first-priority historical source. The Engineering Constitution's exhaustive allowed-dependency list permits `requests` for HTTP data fetching but does not list `yfinance`. Pulling in an unapproved SDK would violate ADR-0011's dependency discipline. The same underlying provider (the Yahoo Finance chart API) is reachable over plain HTTPS.
- **Decision:** Milestone 02 implements the historical ingestion layer using a **Yahoo Finance adapter over the approved `requests` HTTP stack** (`src/data/sources/yahoo.py`), isolated behind the source-adapter contract (`src/data/sources/base.py`) so swapping in `yfinance` or a second source later touches no pipeline code. No new runtime dependencies were added beyond `requests` (already in `requirements.txt` for the constitution). The adapter implements epoch→UTC-date conversion, typed error taxonomy (HTTP 429 Retry-After, 5xx retryable, 4xx/non-retryable, malformed JSON → SOURCE_RESPONSE_ERROR), and the first-priority MVP source per the blueprint.
- **Consequences:**
  - ✅ Same approved source (Yahoo Finance) via an allowed dependency; no new SDK
  - ✅ Provider specifics fully isolated behind the `HistoricalDataSource` contract
  - ✅ File-based MVP unchanged (ADR-0005); no database persistence — raw-tier CSV store with `(ticker, timestamp, interval)` UNIQUE-key dedup, conflict detection (never silently overwrite), checksum, and JSONL ingestion journal
  - ✅ Offline deterministic tests for parsing/HTTP/normalization/store/engine; 187 tests passing, 94% coverage; one controlled live Yahoo fetch (AAPL, 2025-01-02..2025-01-10) verified idempotent on re-run
  - ⚠️ Yahoo Finance is an unofficial endpoint; availability/format may change (documented in README limitations)
  - ⚠️ Only `1d`/`1wk`/`1mo` intervals; intraday and other sources deferred to later milestones
  - 🔧 Idempotency refinement (post-verification): Yahoo serves `adj_close` with slightly different float precision (≈1e-7 relative) between otherwise identical responses. Row equality for dedup/conflict classification therefore uses a relative tolerance of `1e-6` (`src/data/store.py` `_rows_equal`): provider float noise is a duplicate (safe re-run), real data corrections (≫1e-6, e.g. a 5% adjustment) remain conflicts and are never silently overwritten. Verified live: a re-run that previously produced `DUPLICATE_DATA` FAILED now completes with `persisted=0, skipped=10, conflicts=0` and an unchanged SHA-256 checksum
- **Alternatives Considered:** (1) `yfinance` SDK (blueprint-listed) — rejected, not in allowed deps; (2) a second source now — rejected (implement only the first-priority MVP source, per blueprint); (3) PostgreSQL persistence — rejected (ADR-0005, file-based MVP).
- **Cross-reference consistency:**
  - ADR-0011 / DATA_INGESTION_BLUEPRINT: same source, same 6-stage pipeline; deviation is implementation library only
  - ADR-0005: file-based persistence retained (ingestion metadata/journal + raw CSV)
  - ENGINEERING_CONSTITUTION: `requests` already allowed; no dependency additions
  - DATA_ARCHITECTURE §3/§4/§6/§7: naive-UTC timestamps, UNIQUE observation key, raw-tier layout, checksums

## ADR-0025: Milestone 03 — Cleaned Data Goes to the Interim Tier (DATA_ARCHITECTURE Clarification)

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** The Milestone 03 brief says to "persist cleaned data into the processed layer/database". DATA_ARCHITECTURE §7.1 defines the tiers precisely: the **interim** tier holds "validated data, cleaned data" and is regenerated each run; the **processed** tier is versioned and holds "features, labels, train/val/test splits" (built by later milestones). No PostgreSQL exists in the MVP (ADR-0005).
- **Decision:** The cleaning engine writes cleaned output to `data/interim/cleaned_{YYYYMMDD}_{TICKER}_{interval}.csv` (raw/interim/processed separation preserved; raw byte-immutable). Interim output is CSV for now because the approved dependency list has no `parquet`/`pyarrow`; the naming follows DATA_ARCHITECTURE §7.3. The processed tier (Parquet features/labels/datasets) is the home of Milestones 04+.
- **Consequences:**
  - ✅ Architecture §7.1 honored: cleaned data is an intermediate result, not a final processed artifact
  - ✅ Audits + hashes + per-record raw_line traceability attached at the interim tier
  - ⚠️ A future Parquet migration changes only the storage format, not the architecture
- **Cross-reference:** DATA_ARCHITECTURE §7.1/§7.3, DATA_CLEANING_VALIDATION §1.2 stage 7, ADR-0005, ADR-0023.

## ADR-0026: Milestone 04 — pyarrow Added for Parquet Feature/Label Storage (DEPENDENCY ADDITION)

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** FEATURE_ENGINEERING_BLUEPRINT §18 makes a firm decision: "Precompute and persist features in **Parquet** files" (columnar, versioned, immutable). LABEL_GENERATION_BLUEPRINT §19 persists labels through the same processed-tier storage. The Engineering Constitution's allowed-dependency list (ADR-0011) includes `pandas`, `numpy`, `scikit-learn`, `pytest`, `pyyaml`, `structlog`, `requests` — but no Parquet engine. pandas cannot write Parquet without `pyarrow` (or `fastparquet`); neither is on the allowed list, so there is no allowed substitute that satisfies the blueprint's storage mandate (unlike ADR-0024, where an allowed dependency — `requests` — could replace the unapproved SDK).
- **Decision:** Add **`pyarrow>=15.0,<19.0`** to `requirements.txt` as the Parquet engine for feature/label persistence (Milestones 04/05), with the dependency documented in `requirements.txt` and this ADR. pyarrow is a small, well-understood, non-forbidden component (not a cloud SDK, trading SDK, GPU/DL framework, vector DB, LLM framework, or orchestration tool — the constitution's forbidden list). All other dependency rules are unchanged.
- **Consequences:**
  - ✅ Blueprint §18 Parquet storage honored: `data/processed/features/features_{v}_{TICKER}.parquet` and `data/processed/labels/labels_{v}_{TICKER}.parquet`, written atomically (tmp + rename), conflict-protected (identical re-generation is a byte-stable no-op; different content for the same version refuses to overwrite)
  - ✅ Both engines write timestamp-indexed Parquet via `engine="pyarrow"`; CSV remains a configurable fallback (`features.output_format`), not the MVP format
  - ✅ Milestone-04 feature engine: 52-feature registry + compute + FVAL validation; Milestone-05 label engine: direction labels (5-day horizon, ±1%); all mandatory leakage tests green
  - ⚠️ New runtime dependency requires `pip install -r requirements.txt` (documented in README setup)
- **Alternatives Considered:** (1) CSV persistence with a documented deviation — rejected: the blueprint's §18 Parquet decision is explicit and columnar storage is the point of the processed tier; ADR-0025 already reserved Parquet for Milestones 04+; (2) `fastparquet` — rejected: same dependency-class problem, less active maintenance; pyarrow is the pandas default engine
- **Cross-reference:** FEATURE_ENGINEERING_BLUEPRINT §18, LABEL_GENERATION_BLUEPRINT §17-19, ENGINEERING_CONSTITUTION §2 (dependency policy), ADR-0011, ADR-0025, DATA_ARCHITECTURE §7 (processed tier = versioned features/labels).

## ADR-0027: Milestone 06 — Chronological Splits Computed Per Instrument (Multi-Ticker Clarification)

- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** DATASET_BUILDER_BLUEPRINT §3.3 describes the static chronological split as row-based: "Sort data by timestamp ascending, compute total rows N, train = rows[0:floor(N×0.70)]…". That algorithm is specified for one price series (single ticker). Milestone 06's dataset may contain several instruments that all span the same date range (e.g. AAPL and MSFT over the same window). If a row-based cut is applied to the *concatenated* multi-ticker frame, identical timestamps from different instruments land in different splits — the validation period then shares observation dates with the training period and DVAL-06 (chronological splits, no overlap) fails.
- **Decision:** For frames with a `ticker` column, compute the chronological split **per instrument** at the same ratio row boundaries (blueprint §3.3 unchanged for a single series) and concatenate the per-instrument splits. Every instrument therefore contributes its own contiguous chronological segment; split sizes stay exactly proportional per ticker; temporal isolation between TRAIN/VAL/TEST holds globally; single-ticker frames behave identically to the blueprint algorithm.
- **Consequences:** + Multi-ticker datasets are chronologically isolated by construction (verified by DVAL-06 and the mandatory Test B). + Each instrument is represented in every split proportionally. − The 70/15/15 split is per-instrument rather than a single global row cut, which is the correct reading of "chronological" for a panel of co-existing series. Purge/embargo (blueprint §5.1/§5.3) remain implemented and config-gated for the walk-forward/backtest engine where label windows can straddle split boundaries.
- **Alternatives Considered:** (1) Time-boundary splits from global unique timestamps — rejected: with two instruments of equal span the 70/15/15 boundary cannot be represented on a shared timeline, and a purely calendar-based test window would starve later observations of the future data labels need; (2) splitting the concatenated frame by rows — rejected: creates the cross-instrument overlap described above.
- **Cross-reference:** DATASET_BUILDER_BLUEPRINT §3.1/§3.3/§5, ADR-0004 (chronological splits only), DATA_ARCHITECTURE §4.2 (naive-UTC storage), DVAL-06, `src/dataset/split.py`.

## ADR-0028: Milestone 08 — Evaluation & Walk-Forward Backtesting Engine

- **Date:** 2026-09-05
- **Status:** Accepted
- **Context:** EVALUATION_BACKTESTING_BLUEPRINT.md defines the evaluation/backtesting framework but Milestone 08 was the first implementation of it. Several wording ambiguities needed deterministic pinning (all within the blueprint's own options, no architecture change): exit semantics for NO_TRADE/HOLD, profit-factor basis, open positions at period end, benchmark cost treatment.
- **Decision:** Implement `src/backtest/` (data, prediction, signals, execution, metrics, benchmarks, report, engine, walkforward) + `scripts/run_backtest.py`. Frozen MVP strategy: long-only (LONG/FLAT), fixed quantity 1, BUY when P(UP) ≥ 0.55 (ADR-0019 default), exit on SELL or max holding of 5 trading rows (matches the label horizon), close-to-close execution, 10 bps/side cost (5 brokerage + 5 spread/slippage bucket; cost_v0.1), purge of overlapping-label training rows in walk-forward folds, embargo 0 for daily data. Clarifications: (1) NO_TRADE holds the position until SELL or max holding (§13.3 detailed table wins over §14.2's looser wording); (2) profit factor computed on net P&L, consistent with net-based win/loss (§15.2); (3) positions still open at period end are force-closed at the final close (`end_of_backtest`) so the ledger fully accounts; (4) buy-and-hold pays one round trip of the same per-side cost so benchmarks share cost assumptions (§17.3). Expanding-window walk-forward (252/21/21 defaults) trains a fresh baseline per fold and never uses future rows.
- **Consequences:** + Five-layer evaluation (data quality, prediction, signal, strategy, robustness) implemented and separated. + Trade ledger and equity curves reproduce the blueprint §27/§28 field sets. + ML metrics (training) stay separate from financial metrics (backtest). + Deterministic, fail-loud (no silent corrections — §31). − Close-to-close execution and long-only/no-stop assumptions remain documented MVP simplifications. − Real-data evaluation still requires a longer market-data backfill (current local data is too short for a usable dataset).
- **Alternatives Considered:** Rolling-window walk-forward (deferred — data-inefficient for MVP, §8.3); next-day-open execution (deferred — requires price-column model change, §10.3); stop-loss/take-profit (rejected for MVP — overfitting vector, §14.3).
- **Cross-reference:** EVALUATION_BACKTESTING_BLUEPRINT §§7–17, 27–32; RISK_DECISION_ENGINE_BLUEPRINT §6 (0.55 thresholds); BASELINE_MODEL_BLUEPRINT (M07 artifacts consumed by the prediction adapter); TRAINING_PIPELINE_BLUEPRINT (metric separation); ADR-0019; `config/default.yaml` → `backtest:`, `docs/EVALUATION_BACKTESTING_IMPLEMENTATION.md`.

## ADR-0029: Milestone 09 — Prediction & Inference API (FastAPI, Root Paths)

- **Date:** 2026-09-07
- **Status:** Accepted
- **Context:** INFERENCE_API_BLUEPRINT.md specifies a research-only prediction service. The milestone prompt suggested `/api/v1/` paths while the blueprint itself explicitly defers the prefix (§26.2) and commits to root paths via SYSTEM_ARCHITECTURE §5.2. Dependencies beyond the approved list (ENGINEERING_CONSTITUTION §2) were required for the first time.
- **Decision:** Implement `src/api/` (errors, schemas, resolver, decision, audit, orchestrator, app) + `scripts/run_api.py`. FastAPI + pydantic v2 per blueprint §5.2; uvicorn as the local ASGI server; httpx as the FastAPI TestClient transport (test-only). Four endpoints at root paths (`/predict`, `/health`, `/ready` added per milestone §23, `/model/info`, `/version`) with `API_VERSION: v1` reported by `/version` and in audit records — the `/api/v1` prefix is deferred exactly as the blueprint specifies. Decision logic is the shared M08 `src/backtest/signals.py` module (blueprint §23.1 one-code-path rule) wrapped with the RISK §20 risk score (3 of 6 components; liquidity/regime/drawdown unavailable to a stateless request) and §21 reason codes. Audit trail is append-only JSONL per blueprint §19.2 under `predictions/audit/`; audit failure marks the response `audit_written: false` rather than mutating decision output. New `api:` config section validated at load; `mode: live` refuses to boot (§24.2).
- **Consequences:** + Full contract validation with deterministic error codes (§16). + Version resolution explicit > configured default > newest artifact, never random (§9). + Compatibility checks before inference; no hidden conversion (§10). + 50-request local benchmark: median 7.4 ms, p95 8.7 ms (PRD budget 100 ms). − No authentication (localhost research baseline, §21.1). − Replay cache not implemented (determinism is; §20.2 convenience only). − New dependencies deviate from ADR-0007's minimal-deps posture and are recorded here.
- **Alternatives Considered:** `/api/v1/` prefix now (rejected — contradicts blueprint §26.2 and SYSTEM_ARCHITECTURE §5.2); server-side feature computation (rejected — blueprint §12.2 recommends Approach A client-supplied features); separate API decision module (rejected — §23.1 forbids divergent logic).
- **Cross-reference:** INFERENCE_API_BLUEPRINT §§5–13, 16–26; RISK_DECISION_ENGINE_BLUEPRINT §§6, 20–21; `src/backtest/signals.py` (shared logic); `config/default.yaml` → `api:`; `docs/INFERENCE_API_IMPLEMENTATION.md`.

## ADR-0030: Milestone 10 — Research Dashboard (React + Vite SPA) and Read-Only Dashboard Endpoints

- **Context:** UI_UX_BLUEPRINT.md approves React + Vite + TypeScript with CSS Modules and ECharts. The blueprint (§29.3) flags the dashboard's read endpoints as the #1 backend gap and requires them to be specified at implementation time inside the same FastAPI process, read-only, file-backed. The dashboard also needs candles and the prediction audit trail exposed as JSON.
- **Decision:** Implement `dashboard/` as a React 19 + TypeScript (strict) + Vite 7 SPA with react-router v7, CSS Modules on a design-token base (`src/styles/tokens.css`), and tree-shaken ECharts 6 (`echarts/core`). Add ten read-only endpoints in `src/api/reads.py` over the existing artifact stores (datasets, models, experiments, backtests, candles, predictions, system/status) — no computation, no mutation, same error envelope. All backend access goes through one typed client (`dashboard/src/api/client.ts`) with request-id propagation and `ApiError` conversion; base URL is same-origin `/api` via the Vite proxy or `VITE_API_BASE`. Dev dependencies (vitest, @testing-library, jsdom) are dev-only.
- **Consequences:** + All eight blueprint pages implemented with loading/error/empty/stale states and non-color status communication. + 35 frontend tests, strict `tsc --noEmit` clean, production build verified against the live API through the preview proxy. − Chart internals are not jsdom-testable beyond accessible summaries. − No visual-regression system (per blueprint §40 for MVP). − New frontend toolchain recorded here as a deliberate deviation from the Python-only dependency baseline.
- **Alternatives Considered:** Server-side rendering / Next.js (rejected — blueprint prescribes SPA React+Vite); a separate BFF service (rejected — blueprint requires same FastAPI process); fetching from components (rejected — §29 requires a centralized client).
- **Cross-reference:** UI_UX_BLUEPRINT §§5–14, 22–30, 39–40; INFERENCE_API_BLUEPRINT §29.3; `src/api/reads.py`; `docs/DASHBOARD_IMPLEMENTATION.md`.
