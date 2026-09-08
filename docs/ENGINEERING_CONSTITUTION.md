# ENGINEERING CONSTITUTION — Finance AI

> Non-negotiable engineering standards for the Finance AI project.
> Every contribution must comply with these rules.

---

## 1. Coding Standards

### General
- Python 3.10+ only
- Type hints on all public functions and classes
- Docstrings on all public modules, classes, and functions (Google style)
- Maximum line length: 100 characters
- No wildcard imports (`from x import *`)
- No global mutable state

### Formatting
- Use `black` for code formatting
- Use `ruff` for linting
- Use `isort` for import sorting

### Naming
- `snake_case` for functions, methods, variables, modules
- `PascalCase` for classes
- `UPPER_SNAKE_CASE` for constants
- `kebab-case` for configuration keys
- Descriptive names — no abbreviations unless industry-standard (OHLCV, VWAP)

### Module Boundaries
- Each module has a single responsibility
- Modules communicate through well-defined interfaces
- No circular imports
- Internal APIs use leading underscore convention

## 2. Dependency Policy

### Rules
- Pin all dependencies with version ranges in `requirements.txt`
- Document reason for every new dependency
- No duplicate functionality across dependencies
- Prefer standard library over third-party when feasible

### Forbidden (MVP)
- Cloud SDKs (AWS, GCP, Azure)
- Trading SDKs (ccxt, alpaca-trade-api)
- GPU frameworks (CUDA, cuDNN)
- Deep learning frameworks (PyTorch, TensorFlow, JAX)
- Vector databases
- LLM frameworks
- Heavy orchestration tools (Airflow, Prefect)

### Allowed (MVP)
- `pandas` — data manipulation
- `numpy` — numerical computation
- `scikit-learn` — ML models and utilities
- `pytest` — testing
- `pyyaml` — configuration
- `structlog` — logging
- `requests` — HTTP (if fetching data)

## 3. Error Handling Policy

- Never use bare `except:` — always catch specific exceptions
- Log errors with context before re-raising
- Use custom exception classes for domain-specific errors
- Pipeline stages must fail loudly — no silent error swallowing
- Validate inputs at module boundaries

## 4. Logging Policy

- Use `structlog` for structured, machine-readable logs
- Log levels: DEBUG (development), INFO (pipeline progress), WARNING (data issues), ERROR (failures)
- Every pipeline stage logs: start, parameters, duration, outcome
- No `print()` statements in production code

## 5. Configuration Policy

- All configuration in YAML files under `config/`
- Environment-specific config via `config/{environment}.yaml`
- Secrets via environment variables — never in config files
- Config schema validation at startup
- Default values must be documented

## 6. Testing Policy

- Minimum 80% line coverage for `src/`
- Unit tests for all utility functions
- Integration tests for pipeline stages
- No tests that depend on external services (MVP)
- Test data fixtures in `tests/fixtures/`
- Run full test suite before any merge

## 7. Documentation Policy

- Every module has a module-level docstring
- Every public function has a docstring with Args/Returns/Raises
- Complex algorithms have inline comments explaining the "why"
- Architecture decisions go in DECISIONS.md
- Current project state stays in CURRENT_STATE.md

## 8. Git / Change Management Rules

- Branch naming: `feat/`, `fix/`, `docs/`, `refactor/`, `test/`
- Commit messages: imperative mood, < 72 chars
- No force pushes to `main`
- Squash merge for feature branches
- All changes require PR review
- Never commit: data files, model binaries, secrets, IDE configs

## 9. Security Baseline

- No API keys in source code
- No credentials in config files
- `.env` files in `.gitignore` always
- `.env.example` tracks required environment variables
- No `eval()` or `exec()` on untrusted input
- Sanitize any user-provided parameters

## 10. Reproducibility Rules

- Random seeds set explicitly for all stochastic operations
- Package versions pinned in requirements
- Data transformations are pure functions where possible
- Experiment parameters logged before execution
- Results logged with full configuration snapshot

## 11. Data Integrity Rules

- Raw data is read-only — never modified in place
- Every transformation is logged: input shape → output shape
- Timestamps are validated at ingestion
- Missing data counts are logged at every stage
- Data quality checks are mandatory before feature engineering

## 12. ML Experiment Rules

- No future information in training features (ZERO tolerance)
- Chronological train/val/test splits always
- Walk-forward validation for time-series
- Metrics logged: accuracy, precision, recall, F1, Sharpe ratio, max drawdown
- Model artifacts logged with full training config
- No profitability claims without out-of-sample validation
- Baseline models must be established before complex models
