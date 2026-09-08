"""Typed, environment-aware configuration loading.

Layout and rules (ENGINEERING_CONSTITUTION.md section 5,
PRD NFR-CF-01..05):

1. ``config/default.yaml`` is always loaded and is required.
2. ``config/{environment}.yaml`` overlays it when present
   (environment from the ``ENVIRONMENT`` variable, default
   ``development``).
3. A small set of environment variables overrides individual keys
   (never secrets in YAML; secrets are environment-only).
4. Values are validated against typed dataclass models and every
   violation raises :class:`ConfigError` with the offending key path.

Sections typed and validated so far: ``project``, ``data``,
``logging``, and ``ingestion`` (data-ingestion milestone). Unknown
sections are tolerated so later milestones extend the schema without
breaking earlier environments; they are simply not exposed yet.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.core.enums import AppEnvironment, MarketInterval, values_of
from src.core.errors import ConfigError

# config/ lives at repo root, one level above this package (src/config).
DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"

DEFAULT_CONFIG_FILE = "default.yaml"
ENVIRONMENT_VAR = "ENVIRONMENT"

# Environment variables that override individual configuration keys.
ENV_VAR_OVERRIDES: dict[str, tuple[str, ...]] = {
    "LOG_LEVEL": ("logging", "level"),
    "LOG_FORMAT": ("logging", "format"),
}

LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
LOG_FORMATS = frozenset({"json", "console"})
DATA_FORMATS = frozenset({"csv", "parquet"})
ENVIRONMENTS = values_of(AppEnvironment)
MARKET_INTERVALS = values_of(MarketInterval)

# Implemented historical sources (DATA_INGESTION_BLUEPRINT section 1).
INGESTION_SOURCES = frozenset({"yahoo_finance"})


# ---------------------------------------------------------------------------
# Typed configuration models (foundation scope only)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ProjectConfig:
    """``project`` section."""

    name: str
    version: str
    description: str | None = None


@dataclass(frozen=True)
class DataConfig:
    """``data`` section — three-tier storage layout plus external data."""

    raw_dir: Path
    interim_dir: Path
    processed_dir: Path
    external_dir: Path
    default_format: str = "csv"


@dataclass(frozen=True)
class LoggingConfig:
    """``logging`` section."""

    level: str = "INFO"
    format: str = "json"


@dataclass(frozen=True)
class IngestionRetryConfig:
    """Bounded retry policy for transient source failures."""

    max_retries: int = 3
    base_delay_s: float = 1.0
    max_delay_s: float = 60.0
    retry_429_delay_s: float = 60.0  # used when no Retry-After header is given


@dataclass(frozen=True)
class IngestionConfig:
    """``ingestion`` section — historical market-data ingestion."""

    source: str = "yahoo_finance"
    interval: str = "1d"
    request_timeout_s: float = 30.0
    delay_between_requests_ms: int = 500
    continue_on_failure: bool = True
    raw_format: str = "csv"
    retry: IngestionRetryConfig = IngestionRetryConfig()


@dataclass(frozen=True)
class CleaningValidationConfig:
    """``cleaning.validation`` — data validation thresholds."""

    max_missing_pct: float = 0.30
    max_price_change_pct: float = 0.50


@dataclass(frozen=True)
class CleaningOptionsConfig:
    """``cleaning.cleaning`` — cleaning strategies and corporate-action switch."""

    duplicate_strategy: str = "keep_last"
    missing_fill_limit: int = 3
    interpolate_max_gap: int = 3
    outlier_zscore_threshold: float = 3.0
    apply_corporate_actions: bool = True


@dataclass(frozen=True)
class CleaningQualityConfig:
    """``cleaning.quality`` — quality-score weights and gate."""

    enabled: bool = True
    min_score: float = 70.0
    weights: tuple[tuple[str, float], ...] = (
        ("completeness", 0.30),
        ("validity", 0.30),
        ("consistency", 0.20),
        ("freshness", 0.10),
        ("uniqueness", 0.10),
    )
    freshness_max_days: int = 50


@dataclass(frozen=True)
class CleaningAuditConfig:
    """``cleaning.audit`` — audit trail toggles."""

    enabled: bool = True


@dataclass(frozen=True)
class CleaningConfig:
    """``cleaning`` section — data cleaning & quality pipeline (Milestone 03).

    Mirrors Appendix A of DATA_CLEANING_VALIDATION.md. Missing section →
    documented defaults; every value is validated on load.
    """

    pipeline_version: str = "0.1.0"
    min_rows: int = 2
    holidays_file: str | None = None  # relative to data.external_dir; JSON list of ISO dates
    validation: CleaningValidationConfig = CleaningValidationConfig()
    cleaning: CleaningOptionsConfig = CleaningOptionsConfig()
    quality: CleaningQualityConfig = CleaningQualityConfig()
    audit: CleaningAuditConfig = CleaningAuditConfig()


@dataclass(frozen=True)
class FeatureValidationConfig:
    """``features.validation`` — feature-quality thresholds (FVAL-* checks)."""

    max_nan_ratio: float = 0.30
    max_infinite: int = 0
    check_bounded_ranges: bool = True
    outlier_zscore_threshold: float = 5.0


@dataclass(frozen=True)
class FeatureConfig:
    """``features`` section — feature engineering (Milestone 04)."""

    version: str = "v0.1"
    output_format: str = "parquet"
    validation: FeatureValidationConfig = FeatureValidationConfig()


@dataclass(frozen=True)
class LabelConfig:
    """``dataset`` section — label generation (Milestone 05)."""

    label_type: str = "classification"
    label_window: int = 5
    threshold_up: float = 0.01
    threshold_down: float = 0.01
    label_version: str = "v0.1"
    price_column: str = "adj_close"
    split_ratios: tuple[tuple[str, float], ...] = (
        ("train", 0.7),
        ("val", 0.15),
        ("test", 0.15),
    )


@dataclass(frozen=True)
class DatasetPurgingConfig:
    """``dataset_builder.purging`` — drop earlier-split rows whose label
    window overlaps the following split (walk-forward engine concern)."""

    enabled: bool = False


@dataclass(frozen=True)
class DatasetEmbargoConfig:
    """``dataset_builder.embargo`` — gap rows excluded after a split boundary."""

    enabled: bool = False
    rows: int = 0


@dataclass(frozen=True)
class DatasetBuilderConfig:
    """``dataset_builder`` section — dataset assembly (Milestone 06).

    Split ratios are shared from ``dataset.split_ratios`` (chronological
    TRAIN/VAL/TEST, blueprint section 3). Output (dataset) version defaults
    to ``v0.1`` and must be bumped on any material change (blueprint 6.1).
    """

    dataset_version: str = "v0.1"
    min_quality_score: float = 70.0
    min_split_rows: tuple[tuple[str, int], ...] = (
        ("train", 100),
        ("val", 20),
        ("test", 20),
    )
    purging: DatasetPurgingConfig = DatasetPurgingConfig()
    embargo: DatasetEmbargoConfig = DatasetEmbargoConfig()


@dataclass(frozen=True)
class ModelSpec:
    """One approved baseline model and its hyperparameters."""

    name: str
    type: str
    params: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True)
class ModelConfig:
    """``model`` section for reproducible baseline training."""

    random_seed: int = 42
    artifact_dir: Path = Path("data/processed/models")
    n_jobs: int = 1
    config_version: str = "model-config-v0.1"
    models: tuple[ModelSpec, ...] = (
        ModelSpec(
            name="logistic_regression",
            type="linear",
            params=(
                ("C", 1.0),
                ("penalty", "l2"),
                ("solver", "lbfgs"),
                ("max_iter", 1000),
                ("class_weight", "balanced"),
            ),
        ),
        ModelSpec(
            name="random_forest",
            type="ensemble",
            params=(
                ("n_estimators", 100),
                ("max_depth", 10),
                ("min_samples_split", 5),
                ("min_samples_leaf", 2),
                ("class_weight", "balanced"),
                ("random_state", 42),
            ),
        ),
        ModelSpec(
            name="lightgbm",
            type="ensemble",
            params=(
                ("n_estimators", 500),
                ("max_depth", 6),
                ("learning_rate", 0.05),
                ("num_leaves", 31),
                ("subsample", 0.8),
                ("colsample_bytree", 0.8),
                ("class_weight", "balanced"),
                ("random_state", 42),
            ),
        ),
        ModelSpec(
            name="xgboost",
            type="ensemble",
            params=(
                ("n_estimators", 500),
                ("max_depth", 6),
                ("learning_rate", 0.05),
                ("subsample", 0.8),
                ("colsample_bytree", 0.8),
                ("eval_metric", "mlogloss"),
                ("random_state", 42),
            ),
        ),
    )


@dataclass(frozen=True)
class BacktestSignalConfig:
    """``backtest.signal`` — probability thresholds (ADR-0019 defaults)."""

    buy_threshold: float = 0.55
    sell_threshold: float = 0.55


@dataclass(frozen=True)
class BacktestPositionConfig:
    """``backtest.position`` — fixed-quantity long-only position model."""

    quantity: float = 1.0
    max_holding_period: int = 5  # trading rows, matches label horizon


@dataclass(frozen=True)
class BacktestCostConfig:
    """``backtest.costs`` — per-side cost components in basis points.

    Default 10 bps per side (5 brokerage + 5 spread/slippage bucket),
    20 bps round-trip (PRD FR-BT-03, blueprint sections 11-12).
    """

    brokerage_bps: float = 5.0
    spread_bps: float = 5.0
    slippage_bps: float = 0.0

    @property
    def per_side_bps(self) -> float:
        """Total cost on one side in basis points."""
        return self.brokerage_bps + self.spread_bps + self.slippage_bps

    @property
    def round_trip_bps(self) -> float:
        """Total cost for a full round trip in basis points."""
        return 2 * self.per_side_bps


@dataclass(frozen=True)
class BacktestWalkForwardConfig:
    """``backtest.walkforward`` — expanding-window walk-forward defaults."""

    enabled: bool = False
    train_window: int = 252
    test_window: int = 21
    step: int = 21
    purge: bool = True
    embargo_rows: int = 0  # 0 for MVP daily data (blueprint section 9.3)


@dataclass(frozen=True)
class BacktestConfig:
    """``backtest`` section — evaluation & walk-forward backtesting (M08)."""

    backtest_version: str = "v0.1"
    strategy_version: str = "stg_v0.1"
    cost_model_version: str = "cost_v0.1"
    execution_convention: str = "close_to_close"
    initial_capital: float = 1.0
    signal: BacktestSignalConfig = BacktestSignalConfig()
    position: BacktestPositionConfig = BacktestPositionConfig()
    costs: BacktestCostConfig = BacktestCostConfig()
    annualization: int = 252
    risk_free_rate: float = 0.0
    output_dir: Path = Path("backtests")
    walkforward: BacktestWalkForwardConfig = BacktestWalkForwardConfig()


@dataclass(frozen=True)
class ApiConfig:
    """``api`` section — prediction & inference API (M09).

    INFERENCE_API_BLUEPRINT.md section 22: local research service only.
    ``mode: live`` is rejected at startup (blueprint section 24.2).
    """

    host: str = "127.0.0.1"
    port: int = 8000
    mode: str = "research"
    default_model: str = ""
    inference_timeout_ms: int = 1000
    max_request_size_kb: int = 256
    rate_limit_per_minute: int = 0
    audit_dir: Path = Path("predictions/audit")
    model_cache_size: int = 2
    stale_data_max_age_seconds: int = 300


@dataclass(frozen=True)
class PipelineConfig:
    """Autonomous data pipeline configuration (P01)."""

    config_version: str = "pipeline-config-v0.1"
    lookback_days: int = 30          # default initial range when no watermark
    overlap_days: int = 1            # ingestion safety overlap (deduped downstream)
    retry_count: int = 2             # bounded transient retries per stage
    retry_delay_s: int = 5
    min_quality_score: float = 70.0  # quality gate minimum (dataset + cleaning)
    max_gap_ratio: float = 0.05      # tolerated gap ratio before failure
    instruments: tuple[str, ...] = ()


@dataclass(frozen=True)
class TemporalConfig:
    """``temporal`` section — temporal LSTM model (Post-MVP Milestone 06)."""

    model_version: str = "temporal_lstm_v0.1"
    sequence_length: int = 10
    hidden_size: int = 32
    num_layers: int = 1
    dropout: float = 0.0
    batch_size: int = 32
    max_epochs: int = 100
    patience: int = 10
    learning_rate: float = 0.001
    weight_decay: float = 0.0


@dataclass(frozen=True)
class RetrainingTriggerConfig:
    """Which autonomous retraining triggers are enabled (P03)."""

    dataset_growth: bool = True
    drift_critical: bool = True
    performance_critical: bool = True


@dataclass(frozen=True)
class RetrainingConfig:
    """Controlled autonomous retraining configuration (P03)."""

    config_version: str = "retraining-config-v0.1"
    cooldown_days: int = 7           # minimum days between retraining runs
    min_train_rows: int = 100        # eligibility: minimum TRAIN rows
    min_quality_score: float = 70.0  # eligibility: dataset quality gate
    # Promotion gates (risk-aware, documented baselines — never tuned on TEST)
    min_f1_margin: float = 0.02        # G4: candidate F1 >= current - margin
    max_sharpe_regression: float = 0.10  # G5: candidate Sharpe >= current - margin
    max_drawdown_regression: float = 0.02  # G5: drawdown not worse by more than this
    model_name: str = "logistic_regression"  # approved baseline family
    trigger: RetrainingTriggerConfig = RetrainingTriggerConfig()


@dataclass(frozen=True)
class AppConfig:
    """Validated application configuration."""

    environment: AppEnvironment
    project: ProjectConfig
    data: DataConfig
    logging: LoggingConfig
    ingestion: IngestionConfig = IngestionConfig()
    cleaning: CleaningConfig = CleaningConfig()
    features: FeatureConfig = FeatureConfig()
    dataset: LabelConfig = LabelConfig()
    dataset_builder: DatasetBuilderConfig = DatasetBuilderConfig()
    model: ModelConfig = ModelConfig()
    backtest: BacktestConfig = BacktestConfig()
    api: ApiConfig = ApiConfig()
    pipeline: PipelineConfig = PipelineConfig()
    retraining: RetrainingConfig = RetrainingConfig()
    temporal: TemporalConfig = TemporalConfig()


# ---------------------------------------------------------------------------
# Environment resolution
# ---------------------------------------------------------------------------
def environment_from_env(environ: Mapping[str, str]) -> AppEnvironment:
    """Resolve the environment from ``ENVIRONMENT`` (default development)."""
    raw = environ.get(ENVIRONMENT_VAR, AppEnvironment.DEVELOPMENT.value)
    try:
        return AppEnvironment(raw)
    except ValueError:
        raise ConfigError(
            f"invalid environment {raw!r}: expected one of {sorted(ENVIRONMENTS)}",
            context={"variable": ENVIRONMENT_VAR, "value": raw},
        ) from None


# ---------------------------------------------------------------------------
# YAML reading and merging
# ---------------------------------------------------------------------------
def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"configuration file not found: {path}") from None
    except yaml.YAMLError as error:
        raise ConfigError(
            f"invalid YAML in {path}: {error}", context={"path": str(path)}
        ) from error
    if content is None:
        return {}
    if not isinstance(content, dict):
        raise ConfigError(
            f"configuration root must be a mapping in {path}", context={"path": str(path)}
        )
    return content


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` on top of ``base`` (no shared state)."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _apply_env_overrides(raw: dict[str, Any], environ: Mapping[str, str]) -> dict[str, Any]:
    """Overlay documented environment variables onto the raw config."""
    for variable, key_path in ENV_VAR_OVERRIDES.items():
        if variable in environ:
            section: dict[str, Any] = raw
            for part in key_path[:-1]:
                section = section.setdefault(part, {})
            section[key_path[-1]] = environ[variable]
    return raw


# ---------------------------------------------------------------------------
# Typed section builders (raise ConfigError with key paths)
# ---------------------------------------------------------------------------
def _require_mapping(raw: dict[str, Any], section: str) -> dict[str, Any]:
    value = raw.get(section, {})
    if not isinstance(value, dict):
        raise ConfigError(
            f"config section {section!r} must be a mapping", context={"section": section}
        )
    return value


def _require_str(section: dict[str, Any], key: str, path: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(
            f"missing or invalid string config at {path}.{key}",
            context={"key": f"{path}.{key}", "value": value},
        )
    return value


def _build_retraining(section: dict[str, Any]) -> RetrainingConfig:
    """Build the autonomous retraining config (P03)."""

    def _num(key: str, default: float) -> float:
        value = section.get(key, default)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ConfigError(
                f"invalid retraining.{key}: expected a number", context={"value": value}
            )
        return float(value)

    trigger_raw = section.get("trigger") or {}
    if not isinstance(trigger_raw, dict):
        raise ConfigError(
            "retraining.trigger must be a mapping", context={"value": trigger_raw}
        )

    def _flag(key: str, default: bool) -> bool:
        value = trigger_raw.get(key, default)
        if not isinstance(value, bool):
            raise ConfigError(
                f"invalid retraining.trigger.{key}: expected a boolean",
                context={"value": value},
            )
        return value

    return RetrainingConfig(
        config_version=section.get("config_version") or "retraining-config-v0.1",
        cooldown_days=int(_num("cooldown_days", 7)),
        min_train_rows=int(_num("min_train_rows", 100)),
        min_quality_score=_num("min_quality_score", 70.0),
        min_f1_margin=_num("min_f1_margin", 0.02),
        max_sharpe_regression=_num("max_sharpe_regression", 0.10),
        max_drawdown_regression=_num("max_drawdown_regression", 0.02),
        model_name=section.get("model_name") or "logistic_regression",
        trigger=RetrainingTriggerConfig(
            dataset_growth=_flag("dataset_growth", True),
            drift_critical=_flag("drift_critical", True),
            performance_critical=_flag("performance_critical", True),
        ),
    )


def _build_pipeline(section: dict[str, Any]) -> PipelineConfig:
    """Build the autonomous pipeline config (P01)."""
    def _num(key: str, default: float) -> float:
        value = section.get(key, default)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ConfigError(
                f"invalid pipeline.{key}: expected a number", context={"value": value}
            )
        return float(value)

    instruments_raw = section.get("instruments", ())
    if instruments_raw is None:
        instruments_raw = ()
    if not isinstance(instruments_raw, (list, tuple)):
        raise ConfigError(
            "pipeline.instruments must be a list of tickers", context={"value": instruments_raw}
        )
    return PipelineConfig(
        config_version=section.get("config_version") or "pipeline-config-v0.1",
        lookback_days=int(_num("lookback_days", 30)),
        overlap_days=int(_num("overlap_days", 1)),
        retry_count=int(_num("retry_count", 2)),
        retry_delay_s=int(_num("retry_delay_s", 5)),
        min_quality_score=_num("min_quality_score", 70.0),
        max_gap_ratio=_num("max_gap_ratio", 0.05),
        instruments=tuple(str(item).upper() for item in instruments_raw),
    )


def _build_temporal(section: dict[str, Any]) -> TemporalConfig:
    """Build the temporal-model config (P06)."""
    def _num(key: str, default: float) -> float:
        value = section.get(key, default)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ConfigError(
                f"invalid temporal.{key}: expected a number", context={"value": value}
            )
        return float(value)

    sequence_length = int(_num("sequence_length", 10))
    if sequence_length < 1:
        raise ConfigError("config temporal.sequence_length must be >= 1")
    hidden_size = int(_num("hidden_size", 32))
    if hidden_size < 1:
        raise ConfigError("config temporal.hidden_size must be >= 1")
    num_layers = int(_num("num_layers", 1))
    if num_layers < 1:
        raise ConfigError("config temporal.num_layers must be >= 1")
    dropout = _num("dropout", 0.0)
    if not 0.0 <= dropout < 1.0:
        raise ConfigError("config temporal.dropout must be within [0, 1)")
    batch_size = int(_num("batch_size", 32))
    if batch_size < 1:
        raise ConfigError("config temporal.batch_size must be >= 1")
    max_epochs = int(_num("max_epochs", 100))
    if max_epochs < 1:
        raise ConfigError("config temporal.max_epochs must be >= 1")
    patience = int(_num("patience", 10))
    if patience < 1:
        raise ConfigError("config temporal.patience must be >= 1")
    learning_rate = _num("learning_rate", 0.001)
    if learning_rate <= 0:
        raise ConfigError("config temporal.learning_rate must be > 0")
    weight_decay = _num("weight_decay", 0.0)
    if weight_decay < 0:
        raise ConfigError("config temporal.weight_decay must be >= 0")
    model_version = section.get("model_version") or "temporal_lstm_v0.1"
    if not isinstance(model_version, str) or not model_version.strip():
        raise ConfigError("config temporal.model_version must be a non-empty string")
    return TemporalConfig(
        model_version=model_version,
        sequence_length=sequence_length,
        hidden_size=hidden_size,
        num_layers=num_layers,
        dropout=dropout,
        batch_size=batch_size,
        max_epochs=max_epochs,
        patience=patience,
        learning_rate=learning_rate,
        weight_decay=weight_decay,
    )


def _build_project(section: dict[str, Any]) -> ProjectConfig:
    path = "project"
    name = _require_str(section, "name", path)
    version = _require_str(section, "version", path)
    description = section.get("description")
    if description is not None and not isinstance(description, str):
        raise ConfigError(
            "config project.description must be a string", context={"key": "project.description"}
        )
    return ProjectConfig(name=name, version=version, description=description)


def _resolve_path(base: Path, raw_value: object, key: str) -> Path:
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ConfigError(
            f"missing or invalid path config at data.{key}",
            context={"key": f"data.{key}", "value": raw_value},
        )
    path = Path(raw_value)
    return path if path.is_absolute() else base / path


def _build_data(section: dict[str, Any], base: Path) -> DataConfig:
    default_format = section.get("default_format", "csv")
    if default_format not in DATA_FORMATS:
        raise ConfigError(
            f"config data.default_format must be one of {sorted(DATA_FORMATS)}",
            context={"key": "data.default_format", "value": default_format},
        )
    return DataConfig(
        raw_dir=_resolve_path(base, section.get("raw_dir"), "raw_dir"),
        interim_dir=_resolve_path(base, section.get("interim_dir"), "interim_dir"),
        processed_dir=_resolve_path(base, section.get("processed_dir"), "processed_dir"),
        external_dir=_resolve_path(base, section.get("external_dir"), "external_dir"),
        default_format=default_format,
    )


def _build_retry(section: dict[str, Any]) -> IngestionRetryConfig:
    path = "ingestion.retry"
    max_retries = int(section.get("max_retries", 3))
    if max_retries < 0:
        raise ConfigError(
            f"config {path}.max_retries must be >= 0",
            context={"key": f"{path}.max_retries", "value": max_retries},
        )
    base_delay_s = float(section.get("base_delay_s", 1.0))
    max_delay_s = float(section.get("max_delay_s", 60.0))
    retry_429_delay_s = float(section.get("retry_429_delay_s", 60.0))
    for key, value in (
        ("base_delay_s", base_delay_s),
        ("max_delay_s", max_delay_s),
        ("retry_429_delay_s", retry_429_delay_s),
    ):
        if value < 0:
            raise ConfigError(
                f"config {path}.{key} must be >= 0",
                context={"key": f"{path}.{key}", "value": value},
            )
    return IngestionRetryConfig(
        max_retries=max_retries,
        base_delay_s=base_delay_s,
        max_delay_s=max_delay_s,
        retry_429_delay_s=retry_429_delay_s,
    )


def _build_ingestion(section: dict[str, Any]) -> IngestionConfig:
    """Build ingestion config; a missing/partial section falls back to defaults."""
    if not section:
        return IngestionConfig()

    source = section.get("source", "yahoo_finance")
    if source not in INGESTION_SOURCES:
        raise ConfigError(
            f"config ingestion.source must be one of {sorted(INGESTION_SOURCES)}",
            context={"key": "ingestion.source", "value": source},
        )
    interval = section.get("interval", "1d")
    if interval not in MARKET_INTERVALS:
        raise ConfigError(
            f"config ingestion.interval must be one of {sorted(MARKET_INTERVALS)}",
            context={"key": "ingestion.interval", "value": interval},
        )
    raw_format = section.get("raw_format", "csv")
    if raw_format not in {"csv"}:
        raise ConfigError(
            "config ingestion.raw_format supports only 'csv' in this milestone",
            context={"key": "ingestion.raw_format", "value": raw_format},
        )
    return IngestionConfig(
        source=source,
        interval=interval,
        request_timeout_s=float(section.get("request_timeout_s", 30.0)),
        delay_between_requests_ms=int(section.get("delay_between_requests_ms", 500)),
        continue_on_failure=bool(section.get("continue_on_failure", True)),
        raw_format=raw_format,
        retry=_build_retry(dict(section.get("retry", {}) or {})),
    )


def _build_cleaning(section: dict[str, Any]) -> CleaningConfig:
    """Build cleaning config; a missing section falls back to documented defaults."""
    if not section:
        return CleaningConfig()

    pipeline_version = section.get("pipeline_version", "0.1.0")
    if not isinstance(pipeline_version, str) or not pipeline_version.strip():
        raise ConfigError(
            "config cleaning.pipeline_version must be a non-empty string",
            context={"key": "cleaning.pipeline_version", "value": pipeline_version},
        )
    min_rows = int(section.get("min_rows", 2))
    if min_rows < 2:
        raise ConfigError(
            "config cleaning.min_rows must be >= 2",
            context={"key": "cleaning.min_rows", "value": min_rows},
        )
    holidays_file = section.get("holidays_file")
    if holidays_file is not None and (
        not isinstance(holidays_file, str) or not holidays_file.strip()
    ):
        raise ConfigError(
            "config cleaning.holidays_file must be a non-empty path or null",
            context={"key": "cleaning.holidays_file", "value": holidays_file},
        )

    validation = dict(section.get("validation", {}) or {})
    max_missing_pct = float(validation.get("max_missing_pct", 0.30))
    max_price_change_pct = float(validation.get("max_price_change_pct", 0.50))
    if not 0.0 <= max_missing_pct <= 1.0:
        raise ConfigError("config cleaning.validation.max_missing_pct must be within [0, 1]")
    if max_price_change_pct <= 0:
        raise ConfigError("config cleaning.validation.max_price_change_pct must be > 0")

    cleaning = dict(section.get("cleaning", {}) or {})
    duplicate_strategy = cleaning.get("duplicate_strategy", "keep_last")
    if duplicate_strategy not in {"keep_last", "keep_first"}:
        raise ConfigError(
            "config cleaning.cleaning.duplicate_strategy must be 'keep_last' or 'keep_first'"
        )
    missing_fill_limit = int(cleaning.get("missing_fill_limit", 3))
    interpolate_max_gap = int(cleaning.get("interpolate_max_gap", 3))
    outlier_zscore_threshold = float(cleaning.get("outlier_zscore_threshold", 3.0))
    apply_corporate_actions = bool(cleaning.get("apply_corporate_actions", True))
    if missing_fill_limit < 0 or interpolate_max_gap < 0 or outlier_zscore_threshold <= 0:
        raise ConfigError("config cleaning.cleaning limits/thresholds must be non-negative")

    quality = dict(section.get("quality", {}) or {})
    quality_enabled = bool(quality.get("enabled", True))
    min_score = float(quality.get("min_score", 70.0))
    freshness_max_days = int(quality.get("freshness_max_days", 50))
    raw_weights = dict(quality.get("weights", {}) or {})
    expected_dims = ("completeness", "validity", "consistency", "freshness", "uniqueness")
    default_weights = (0.30, 0.30, 0.20, 0.10, 0.10)
    weights: list[tuple[str, float]] = []
    for dim, default in zip(expected_dims, default_weights):
        weight = float(raw_weights.get(dim, default))
        if weight < 0:
            raise ConfigError(f"config cleaning.quality.weights.{dim} must be >= 0")
        weights.append((dim, weight))
    total = sum(weight for _, weight in weights)
    if not 0.999 <= total <= 1.001:
        raise ConfigError(
            f"config cleaning.quality.weights must sum to 1.0 (got {total})",
            context={"key": "cleaning.quality.weights", "value": weights},
        )
    if not 0 <= min_score <= 100:
        raise ConfigError("config cleaning.quality.min_score must be within [0, 100]")
    if freshness_max_days <= 0:
        raise ConfigError("config cleaning.quality.freshness_max_days must be > 0")

    audit = dict(section.get("audit", {}) or {})
    audit_enabled = bool(audit.get("enabled", True))

    return CleaningConfig(
        pipeline_version=pipeline_version,
        min_rows=min_rows,
        holidays_file=holidays_file,
        validation=CleaningValidationConfig(
            max_missing_pct=max_missing_pct, max_price_change_pct=max_price_change_pct
        ),
        cleaning=CleaningOptionsConfig(
            duplicate_strategy=duplicate_strategy,
            missing_fill_limit=missing_fill_limit,
            interpolate_max_gap=interpolate_max_gap,
            outlier_zscore_threshold=outlier_zscore_threshold,
            apply_corporate_actions=apply_corporate_actions,
        ),
        quality=CleaningQualityConfig(
            enabled=quality_enabled,
            min_score=min_score,
            weights=tuple(weights),
            freshness_max_days=freshness_max_days,
        ),
        audit=CleaningAuditConfig(enabled=audit_enabled),
    )


def _build_features(section: dict[str, Any]) -> FeatureConfig:
    """Build feature config; a missing section falls back to documented defaults."""
    if not section:
        return FeatureConfig()

    version = section.get("version", "v0.1")
    if not isinstance(version, str) or not version.strip():
        raise ConfigError(
            "config features.version must be a non-empty string",
            context={"key": "features.version", "value": version},
        )
    output_format = section.get("output_format", "parquet")
    if output_format not in {"parquet", "csv"}:
        raise ConfigError(
            "config features.output_format must be 'parquet' or 'csv'",
            context={"key": "features.output_format", "value": output_format},
        )

    validation = dict(section.get("validation", {}) or {})
    max_nan_ratio = float(validation.get("max_nan_ratio", 0.30))
    max_infinite = int(validation.get("max_infinite", 0))
    check_bounded_ranges = bool(validation.get("check_bounded_ranges", True))
    outlier_zscore_threshold = float(validation.get("outlier_zscore_threshold", 5.0))
    if not 0.0 <= max_nan_ratio <= 1.0:
        raise ConfigError("config features.validation.max_nan_ratio must be within [0, 1]")
    if max_infinite < 0:
        raise ConfigError("config features.validation.max_infinite must be >= 0")
    if outlier_zscore_threshold <= 0:
        raise ConfigError("config features.validation.outlier_zscore_threshold must be > 0")

    return FeatureConfig(
        version=version,
        output_format=output_format,
        validation=FeatureValidationConfig(
            max_nan_ratio=max_nan_ratio,
            max_infinite=max_infinite,
            check_bounded_ranges=check_bounded_ranges,
            outlier_zscore_threshold=outlier_zscore_threshold,
        ),
    )


def _build_dataset(section: dict[str, Any]) -> LabelConfig:
    """Build label config; a missing section falls back to documented defaults."""
    if not section:
        return LabelConfig()

    label_type = section.get("label_type", "classification")
    if label_type != "classification":
        raise ConfigError(
            "config dataset.label_type supports only 'classification' in this milestone",
            context={"key": "dataset.label_type", "value": label_type},
        )
    label_window = int(section.get("label_window", 5))
    if label_window <= 0:
        raise ConfigError(
            "config dataset.label_window must be > 0",
            context={"key": "dataset.label_window", "value": label_window},
        )
    thresholds = dict(section.get("thresholds", {}) or {})
    threshold_up = float(thresholds.get("up", 0.01))
    threshold_down = float(thresholds.get("down", 0.01))
    if threshold_up <= 0 or threshold_down <= 0:
        raise ConfigError(
            "config dataset.thresholds must be positive",
            context={"key": "dataset.thresholds", "value": thresholds},
        )
    label_version = section.get("label_version", "v0.1")
    if not isinstance(label_version, str) or not label_version.strip():
        raise ConfigError(
            "config dataset.label_version must be a non-empty string",
            context={"key": "dataset.label_version", "value": label_version},
        )
    price_column = section.get("price_column", "adj_close")
    if not isinstance(price_column, str) or not price_column.strip():
        raise ConfigError(
            "config dataset.price_column must be a non-empty string",
            context={"key": "dataset.price_column", "value": price_column},
        )

    split_ratios_raw = dict(section.get("split_ratios", {}) or {})
    expected_splits = ("train", "val", "test")
    default_split_values = (0.7, 0.15, 0.15)
    split_ratios: list[tuple[str, float]] = []
    for name, default in zip(expected_splits, default_split_values):
        value = float(split_ratios_raw.get(name, default))
        if value < 0:
            raise ConfigError(f"config dataset.split_ratios.{name} must be >= 0")
        split_ratios.append((name, value))
    total = sum(value for _, value in split_ratios)
    if not 0.999 <= total <= 1.001:
        raise ConfigError(
            f"config dataset.split_ratios must sum to 1.0 (got {total})",
            context={"key": "dataset.split_ratios", "value": split_ratios},
        )

    return LabelConfig(
        label_type=label_type,
        label_window=label_window,
        threshold_up=threshold_up,
        threshold_down=threshold_down,
        label_version=label_version,
        price_column=price_column,
        split_ratios=tuple(split_ratios),
    )


def _build_dataset_builder(section: dict[str, Any]) -> DatasetBuilderConfig:
    """Build dataset-builder config; a missing section falls back to defaults."""
    if not section:
        return DatasetBuilderConfig()

    dataset_version = section.get("dataset_version", "v0.1")
    if not isinstance(dataset_version, str) or not dataset_version.strip():
        raise ConfigError(
            "config dataset_builder.dataset_version must be a non-empty string",
            context={"key": "dataset_builder.dataset_version", "value": dataset_version},
        )
    min_quality_score = float(section.get("min_quality_score", 70.0))
    if not 0 <= min_quality_score <= 100:
        raise ConfigError("config dataset_builder.min_quality_score must be within [0, 100]")

    min_split_raw = dict(section.get("min_split_rows", {}) or {})
    default_min = (("train", 100), ("val", 20), ("test", 20))
    min_split_rows: list[tuple[str, int]] = []
    for name, default in default_min:
        value = int(min_split_raw.get(name, default))
        if value < 0:
            raise ConfigError(f"config dataset_builder.min_split_rows.{name} must be >= 0")
        min_split_rows.append((name, value))

    purging = dict(section.get("purging", {}) or {})
    embargo = dict(section.get("embargo", {}) or {})
    embargo_rows = int(embargo.get("rows", 0))
    if embargo_rows < 0:
        raise ConfigError("config dataset_builder.embargo.rows must be >= 0")

    return DatasetBuilderConfig(
        dataset_version=dataset_version,
        min_quality_score=min_quality_score,
        min_split_rows=tuple(min_split_rows),
        purging=DatasetPurgingConfig(enabled=bool(purging.get("enabled", False))),
        embargo=DatasetEmbargoConfig(
            enabled=bool(embargo.get("enabled", False)), rows=embargo_rows
        ),
    )


def _build_model(section: dict[str, Any]) -> ModelConfig:
    """Build and validate the approved baseline model configuration."""
    if not section:
        return ModelConfig()
    random_seed = int(section.get("random_seed", 42))
    n_jobs = int(section.get("n_jobs", 1))
    if n_jobs != 1:
        raise ConfigError("config model.n_jobs must be 1 for deterministic MVP training")
    artifact_dir = Path(section.get("artifact_dir", "data/processed/models"))
    config_version = section.get("config_version", "model-config-v0.1")
    raw_models = section.get("models", [])
    if not isinstance(raw_models, list) or not raw_models:
        raise ConfigError("config model.models must be a non-empty list")
    specs: list[ModelSpec] = []
    for index, raw in enumerate(raw_models):
        if not isinstance(raw, dict):
            raise ConfigError(f"config model.models[{index}] must be a mapping")
        name = raw.get("name")
        model_type = raw.get("type")
        if name not in {"logistic_regression", "random_forest", "lightgbm", "xgboost"}:
            raise ConfigError(f"unsupported baseline model {name!r}")
        if model_type not in {"linear", "ensemble"}:
            raise ConfigError(f"unsupported model type {model_type!r}")
        params = raw.get("params", {}) or {}
        if not isinstance(params, dict):
            raise ConfigError(f"config model.models[{index}].params must be a mapping")
        specs.append(ModelSpec(name=name, type=model_type, params=tuple(params.items())))
    return ModelConfig(
        random_seed=random_seed,
        artifact_dir=artifact_dir,
        n_jobs=n_jobs,
        config_version=config_version,
        models=tuple(specs),
    )


def _build_backtest(section: dict[str, Any]) -> BacktestConfig:
    """Build and validate the backtest configuration (Milestone 08)."""
    if not section:
        return BacktestConfig()

    backtest_version = section.get("backtest_version", "v0.1")
    if not isinstance(backtest_version, str) or not backtest_version.strip():
        raise ConfigError(
            "config backtest.backtest_version must be a non-empty string",
            context={"key": "backtest.backtest_version", "value": backtest_version},
        )
    strategy_version = section.get("strategy_version", "stg_v0.1")
    if not isinstance(strategy_version, str) or not strategy_version.strip():
        raise ConfigError(
            "config backtest.strategy_version must be a non-empty string",
            context={"key": "backtest.strategy_version", "value": strategy_version},
        )
    cost_model_version = section.get("cost_model_version", "cost_v0.1")
    if not isinstance(cost_model_version, str) or not cost_model_version.strip():
        raise ConfigError(
            "config backtest.cost_model_version must be a non-empty string",
            context={"key": "backtest.cost_model_version", "value": cost_model_version},
        )
    convention = section.get("execution_convention", "close_to_close")
    if convention != "close_to_close":
        raise ConfigError(
            "config backtest.execution_convention supports only 'close_to_close' in MVP",
            context={"key": "backtest.execution_convention", "value": convention},
        )

    signal = dict(section.get("signal", {}) or {})
    buy_threshold = float(signal.get("buy_threshold", 0.55))
    sell_threshold = float(signal.get("sell_threshold", 0.55))
    if not 0.0 < buy_threshold < 1.0 or not 0.0 < sell_threshold < 1.0:
        raise ConfigError("config backtest.signal thresholds must be within (0, 1)")

    position = dict(section.get("position", {}) or {})
    quantity = float(position.get("quantity", 1.0))
    max_holding_period = int(position.get("max_holding_period", 5))
    if quantity <= 0:
        raise ConfigError("config backtest.position.quantity must be > 0")
    if max_holding_period <= 0:
        raise ConfigError("config backtest.position.max_holding_period must be > 0")

    costs = dict(section.get("costs", {}) or {})
    brokerage_bps = float(costs.get("brokerage_bps", 5.0))
    spread_bps = float(costs.get("spread_bps", 5.0))
    slippage_bps = float(costs.get("slippage_bps", 0.0))
    if brokerage_bps < 0 or spread_bps < 0 or slippage_bps < 0:
        raise ConfigError("config backtest.costs components must be >= 0")

    annualization = int(section.get("annualization", 252))
    if annualization <= 0:
        raise ConfigError("config backtest.annualization must be > 0")
    risk_free_rate = float(section.get("risk_free_rate", 0.0))
    if risk_free_rate < 0:
        raise ConfigError("config backtest.risk_free_rate must be >= 0")
    initial_capital = float(section.get("initial_capital", 1.0))
    if initial_capital <= 0:
        raise ConfigError("config backtest.initial_capital must be > 0")

    output_dir = Path(section.get("output_dir", "backtests"))

    walkforward = dict(section.get("walkforward", {}) or {})
    train_window = int(walkforward.get("train_window", 252))
    test_window = int(walkforward.get("test_window", 21))
    step = int(walkforward.get("step", 21))
    purge = bool(walkforward.get("purge", True))
    embargo_rows = int(walkforward.get("embargo_rows", 0))
    if train_window <= 0 or test_window <= 0 or step <= 0:
        raise ConfigError("config backtest.walkforward windows must be positive")
    if embargo_rows < 0:
        raise ConfigError("config backtest.walkforward.embargo_rows must be >= 0")

    return BacktestConfig(
        backtest_version=backtest_version,
        strategy_version=strategy_version,
        cost_model_version=cost_model_version,
        execution_convention=convention,
        initial_capital=initial_capital,
        signal=BacktestSignalConfig(buy_threshold=buy_threshold, sell_threshold=sell_threshold),
        position=BacktestPositionConfig(quantity=quantity, max_holding_period=max_holding_period),
        costs=BacktestCostConfig(
            brokerage_bps=brokerage_bps, spread_bps=spread_bps, slippage_bps=slippage_bps
        ),
        annualization=annualization,
        risk_free_rate=risk_free_rate,
        output_dir=output_dir,
        walkforward=BacktestWalkForwardConfig(
            enabled=bool(walkforward.get("enabled", False)),
            train_window=train_window,
            test_window=test_window,
            step=step,
            purge=purge,
            embargo_rows=embargo_rows,
        ),
    )


def _build_api(section: dict[str, Any]) -> ApiConfig:
    """Build and validate the inference-API configuration (Milestone 09)."""
    if not section:
        return ApiConfig()

    host = section.get("host", "127.0.0.1")
    if not isinstance(host, str) or not host.strip():
        raise ConfigError(
            "config api.host must be a non-empty string",
            context={"key": "api.host", "value": host},
        )
    port = int(section.get("port", 8000))
    if not 1 <= port <= 65535:
        raise ConfigError("config api.port must be within 1..65535")
    mode = section.get("mode", "research")
    if mode not in ("research", "paper"):
        raise ConfigError(
            "config api.mode must be 'research' or 'paper' (live is not implemented; "
            "the service refuses to boot in live mode)",
            context={"key": "api.mode", "value": mode},
        )
    default_model = section.get("default_model", "")
    if not isinstance(default_model, str):
        raise ConfigError("config api.default_model must be a string")
    inference_timeout_ms = int(section.get("inference_timeout_ms", 1000))
    if inference_timeout_ms <= 0:
        raise ConfigError("config api.inference_timeout_ms must be > 0")
    max_request_size_kb = int(section.get("max_request_size_kb", 256))
    if max_request_size_kb <= 0:
        raise ConfigError("config api.max_request_size_kb must be > 0")
    rate_limit_per_minute = int(section.get("rate_limit_per_minute", 0))
    if rate_limit_per_minute < 0:
        raise ConfigError("config api.rate_limit_per_minute must be >= 0")
    audit_dir = Path(section.get("audit_dir", "predictions/audit"))
    model_cache_size = int(section.get("model_cache_size", 2))
    if model_cache_size < 1:
        raise ConfigError("config api.model_cache_size must be >= 1")
    stale_data_max_age_seconds = int(section.get("stale_data_max_age_seconds", 300))
    if stale_data_max_age_seconds <= 0:
        raise ConfigError("config api.stale_data_max_age_seconds must be > 0")

    return ApiConfig(
        host=host,
        port=port,
        mode=mode,
        default_model=default_model,
        inference_timeout_ms=inference_timeout_ms,
        max_request_size_kb=max_request_size_kb,
        rate_limit_per_minute=rate_limit_per_minute,
        audit_dir=audit_dir,
        model_cache_size=model_cache_size,
        stale_data_max_age_seconds=stale_data_max_age_seconds,
    )


def _build_logging(section: dict[str, Any]) -> LoggingConfig:
    level = section.get("level", "INFO")
    if level not in LOG_LEVELS:
        raise ConfigError(
            f"config logging.level must be one of {sorted(LOG_LEVELS)}",
            context={"key": "logging.level", "value": level},
        )
    log_format = section.get("format", "json")
    if log_format not in LOG_FORMATS:
        raise ConfigError(
            f"config logging.format must be one of {sorted(LOG_FORMATS)}",
            context={"key": "logging.format", "value": log_format},
        )
    return LoggingConfig(level=level, format=log_format)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def load_config(
    environment: AppEnvironment | None = None,
    *,
    config_dir: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> AppConfig:
    """Load and validate configuration.

    Args:
        environment: Environment to load. When omitted, resolved from the
            ``ENVIRONMENT`` variable (default ``development``).
        config_dir: Directory containing ``default.yaml`` (defaults to the
            repository ``config/`` directory).
        environ: Environment-variable mapping (defaults to ``os.environ``).

    Raises:
        ConfigError: if the default configuration is missing/invalid or an
            environment value violates the schema.
    """
    env = environment or environment_from_env(environ or os.environ)
    config_dir = config_dir or DEFAULT_CONFIG_DIR

    default_path = config_dir / DEFAULT_CONFIG_FILE
    raw = _read_yaml(default_path)

    environment_path = config_dir / f"{env.value}.yaml"
    if environment_path.exists():
        raw = _deep_merge(raw, _read_yaml(environment_path))

    raw = _apply_env_overrides(
        raw, environ or os.environ
    )  # ``ingestion`` / ``cleaning`` are optional in this milestone: absent → typed defaults.
    ingestion_section = raw.get("ingestion")
    if ingestion_section is not None and not isinstance(ingestion_section, dict):
        raise ConfigError(
            "config section 'ingestion' must be a mapping", context={"section": "ingestion"}
        )
    cleaning_section = raw.get("cleaning")
    if cleaning_section is not None and not isinstance(cleaning_section, dict):
        raise ConfigError(
            "config section 'cleaning' must be a mapping", context={"section": "cleaning"}
        )
    features_section = raw.get("features")
    if features_section is not None and not isinstance(features_section, dict):
        raise ConfigError(
            "config section 'features' must be a mapping", context={"section": "features"}
        )
    dataset_builder_section = raw.get("dataset_builder")
    if dataset_builder_section is not None and not isinstance(dataset_builder_section, dict):
        raise ConfigError(
            "config section 'dataset_builder' must be a mapping",
            context={"section": "dataset_builder"},
        )
    dataset_section = raw.get("dataset")
    if dataset_section is not None and not isinstance(dataset_section, dict):
        raise ConfigError(
            "config section 'dataset' must be a mapping", context={"section": "dataset"}
        )
    model_section = raw.get("model")
    if model_section is not None and not isinstance(model_section, dict):
        raise ConfigError("config section 'model' must be a mapping", context={"section": "model"})
    backtest_section = raw.get("backtest")
    if backtest_section is not None and not isinstance(backtest_section, dict):
        raise ConfigError(
            "config section 'backtest' must be a mapping", context={"section": "backtest"}
        )
    api_section = raw.get("api")
    if api_section is not None and not isinstance(api_section, dict):
        raise ConfigError("config section 'api' must be a mapping", context={"section": "api"})
    pipeline_section = raw.get("pipeline")
    if pipeline_section is not None and not isinstance(pipeline_section, dict):
        raise ConfigError(
            "config section 'pipeline' must be a mapping", context={"section": "pipeline"}
        )
    retraining_section = raw.get("retraining")
    if retraining_section is not None and not isinstance(retraining_section, dict):
        raise ConfigError(
            "config section 'retraining' must be a mapping",
            context={"section": "retraining"},
        )
    temporal_section = raw.get("temporal")
    if temporal_section is not None and not isinstance(temporal_section, dict):
        raise ConfigError(
            "config section 'temporal' must be a mapping", context={"section": "temporal"}
        )

    return AppConfig(
        environment=env,
        project=_build_project(_require_mapping(raw, "project")),
        data=_build_data(_require_mapping(raw, "data"), config_dir.parent),
        logging=_build_logging(_require_mapping(raw, "logging")),
        ingestion=_build_ingestion(ingestion_section or {}),
        cleaning=_build_cleaning(cleaning_section or {}),
        features=_build_features(features_section or {}),
        dataset=_build_dataset(dataset_section or {}),
        dataset_builder=_build_dataset_builder(dataset_builder_section or {}),
        model=_build_model(model_section or {}),
        backtest=_build_backtest(backtest_section or {}),
        api=_build_api(api_section or {}),
        pipeline=_build_pipeline(pipeline_section or {}),
        retraining=_build_retraining(retraining_section or {}),
        temporal=_build_temporal(temporal_section or {}),
    )
