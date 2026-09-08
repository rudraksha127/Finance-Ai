"""Registry tests — metadata completeness for all 52 MVP features."""

from __future__ import annotations

from src.features.registry import (
    CATEGORIES,
    FEATURE_COLUMNS,
    FEATURES,
    FEATURES_BY_ID,
    FEATURES_BY_NAME,
    feature_count,
    max_lookback,
    required_source_columns,
)

APPROVED_CATEGORIES = frozenset(
    {
        "price_return",
        "trend",
        "momentum",
        "volatility",
        "volume",
        "volume_price",
        "bollinger",
        "candle",
    }
)


def test_feature_count_is_52():
    assert feature_count() == 52
    assert len(FEATURES) == 52


def test_ids_and_names_unique():
    ids = [feature.feature_id for feature in FEATURES]
    names = [feature.name for feature in FEATURES]
    assert len(ids) == len(set(ids))
    assert len(names) == len(set(names))
    assert FEATURE_COLUMNS == tuple(names)


def test_ids_follow_approved_prefixes():
    prefixes = {"RET", "TRD", "MOM", "VOL", "VLM", "VP", "BB", "CS"}
    for feature in FEATURES:
        prefix = feature.feature_id.split("-")[0]
        assert prefix in prefixes, feature.feature_id


def test_lookup_tables_consistent():
    assert len(FEATURES_BY_ID) == 52
    assert len(FEATURES_BY_NAME) == 52
    for feature in FEATURES:
        assert FEATURES_BY_ID[feature.feature_id] is feature
        assert FEATURES_BY_NAME[feature.name] is feature


def test_metadata_fields_complete():
    for feature in FEATURES:
        assert feature.formula.strip(), feature.feature_id
        assert feature.inputs, feature.feature_id
        assert feature.lookback >= 0, feature.feature_id
        assert feature.output_type == "float64", feature.feature_id
        assert feature.normalization == "none", feature.feature_id
        assert feature.leakage == "none", feature.feature_id
        assert feature.expected_range, feature.feature_id
        assert feature.description.strip(), feature.feature_id
        assert feature.version, feature.feature_id


def test_categories_match_approved_taxonomy():
    declared = {feature.category for feature in FEATURES}
    assert declared == APPROVED_CATEGORIES
    assert tuple(CATEGORIES) == (
        "price_return",
        "trend",
        "momentum",
        "volatility",
        "volume",
        "volume_price",
        "bollinger",
        "candle",
    )


def test_category_counts_match_catalog():
    counts: dict[str, int] = {}
    for feature in FEATURES:
        counts[feature.category] = counts.get(feature.category, 0) + 1
    assert counts == {
        "price_return": 8,
        "trend": 8,
        "momentum": 6,
        "volatility": 8,
        "volume": 6,
        "volume_price": 4,
        "bollinger": 6,
        "candle": 6,
    }


def test_source_columns_within_ohlcv():
    assert required_source_columns() <= {"open", "high", "low", "close", "volume"}


def test_max_lookback():
    assert max_lookback() == 100  # bb_squeeze_20d (catalog lookback)


def test_lookbacks_match_catalog():
    lookbacks = {feature.name: feature.lookback for feature in FEATURES}
    assert lookbacks["returns_1d"] == 1
    assert lookbacks["returns_5d"] == 5
    assert lookbacks["sma_50"] == 50
    assert lookbacks["rsi_14"] == 14
    assert lookbacks["atr_14"] == 14
    assert lookbacks["bb_squeeze_20d"] == 100
    assert lookbacks["body_ratio"] == 0
    assert lookbacks["gap_pct"] == 1
    assert lookbacks["volume_zscore_20d"] == 20
    assert lookbacks["obv_slope_10d"] == 10


def test_catalog_formula_coverage():
    # Every catalog feature id is present and mapped to its canonical name.
    expected_names = {
        "returns_1d",
        "returns_3d",
        "returns_5d",
        "returns_10d",
        "returns_20d",
        "log_return_1d",
        "intraday_return",
        "overnight_return",
        "sma_5",
        "sma_10",
        "sma_20",
        "sma_50",
        "price_to_sma_20",
        "price_to_sma_50",
        "ema_12",
        "ema_26",
        "rsi_14",
        "rsi_7",
        "roc_5",
        "roc_10",
        "roc_20",
        "momentum_10",
        "volatility_5d",
        "volatility_10d",
        "volatility_20d",
        "volatility_50d",
        "atr_14",
        "true_range",
        "realized_vol_20d",
        "volatility_ratio",
        "volume_ratio_5d",
        "volume_ratio_20d",
        "volume_change_1d",
        "volume_trend_5d",
        "volume_zscore_20d",
        "obv_slope_10d",
        "vwap_deviation_5d",
        "vwap_deviation_20d",
        "volume_price_trend",
        "accumulation_distribution",
        "bb_upper_20d",
        "bb_lower_20d",
        "bb_position_20d",
        "bb_bandwidth_20d",
        "bb_squeeze_20d",
        "high_low_range_20d",
        "body_ratio",
        "upper_wick_ratio",
        "lower_wick_ratio",
        "close_position",
        "is_bullish",
        "gap_pct",
    }
    assert set(FEATURE_COLUMNS) == expected_names
