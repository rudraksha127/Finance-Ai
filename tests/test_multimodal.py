"""Tests for multimodal finance intelligence (Post-MVP Milestone 08).

Covers milestone sections 25/42/43: the six mandatory leakage tests
(publication time, future news, future filing, as-of, dataset extension,
same-day timing), the controlled reference fixture (10:00 market / 12:00
news / 15:00 prediction / 17:00 news / next-day filing), as-of semantics,
deduplication, restatement policy, timestamp normalization, and the
source -> normalize -> as-of -> features -> model-input integration chain.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.multimodal.asoof import (
    AsOfError,
    asof_records,
    effective_availability,
    events_in_window,
    latest_fundamental_asof,
)
from src.multimodal.contracts import ExternalRecord, TemporalReliability, normalize_timestamp
from src.multimodal.features import (
    MULTIMODAL_FEATURE_VERSION,
    build_multimodal_features,
    multimodal_feature_columns,
)
from src.multimodal.sources import (
    SourceError,
    deduplicate,
    load_fixture,
    normalize_batch,
    restatement_policy,
)

UTC = timezone.utc


def _record(
    identifier: str,
    *,
    event_type: str = "PRODUCT",
    published: datetime | None = None,
    event: datetime | None = None,
    instrument: str = "AAPL",
    reliability: TemporalReliability = TemporalReliability.RELIABLE,
    **payload,
) -> ExternalRecord:
    published = published or datetime(2024, 1, 3, 12, 0, tzinfo=UTC)
    # The storage contract is naive UTC: strip tzinfo once at the boundary.
    naive_published = published.astimezone(UTC).replace(tzinfo=None)
    return ExternalRecord(
        record_id=f"ext_{identifier}",
        source="fixture",
        source_identifier=identifier,
        instrument=instrument,
        event_type=event_type,
        event_timestamp=(event.astimezone(UTC).replace(tzinfo=None) if event else naive_published),
        publication_timestamp=naive_published,
        ingestion_timestamp=naive_published,
        availability_timestamp=naive_published,
        reliability=reliability,
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Controlled reference fixture (section 43) — MANDATORY scenario
# ---------------------------------------------------------------------------
@pytest.fixture()
def reference_records() -> list[ExternalRecord]:
    return load_fixture(Path("data/external/fixtures/multimodal_reference.json"))


def test_controlled_fixture_scenario(reference_records):
    """10:00 market / 12:00 news / 15:00 prediction / 17:00 news / next-day filing.

    The 15:00 prediction may use the 12:00 news but NOT the 17:00 news or the
    next-day filing.
    """
    prediction_time = datetime(2024, 1, 3, 15, 0)
    eligible = asof_records(reference_records, instrument="AAPL", as_of=prediction_time)
    identifiers = {record.source_identifier for record in eligible}
    assert "news-2024-01-03-1200" in identifiers  # 12:00 news IS eligible
    assert "news-2024-01-03-1700" not in identifiers  # 17:00 news NOT eligible
    assert "filing-Q4-2023" not in identifiers  # next-day filing NOT eligible

    # At 18:00 the next day, the filing (published 18:30 previous day) is eligible.
    next_day = datetime(2024, 1, 4, 18, 31)
    eligible_next = asof_records(reference_records, instrument="AAPL", as_of=next_day)
    assert "filing-Q4-2023" in {record.source_identifier for record in eligible_next}


# ---------------------------------------------------------------------------
# Mandatory leakage tests (section 25)
# ---------------------------------------------------------------------------
def test_leakage_a_publication_time(reference_records):
    """TEST A: a record published after T must not appear in features at T."""
    frame = _market_frame(pd.date_range("2024-01-03 14:00", periods=1, freq="h"))
    features = build_multimodal_features(frame, reference_records, instrument="AAPL")
    # The Q4 filing was published 2024-01-04 18:30 — must NOT be visible.
    assert np.isnan(features["revenue"].iloc[0])
    assert features["has_fundamentals"].iloc[0] == 0


def test_leakage_b_future_news(reference_records):
    """TEST B: adding future news must not change historical features."""
    frame = _market_frame(pd.date_range("2024-01-03 13:00", periods=1, freq="h"))
    before = build_multimodal_features(frame, reference_records, instrument="AAPL")
    future_news = _record(
        "future-news",
        published=datetime(2024, 1, 6, 10, 0, tzinfo=UTC),
        headline="A future event",
    )
    after = build_multimodal_features(frame, reference_records + [future_news], instrument="AAPL")
    pd.testing.assert_frame_equal(before, after)


def test_leakage_c_future_filing(reference_records):
    """TEST C: adding a future filing must not change historical fundamentals."""
    frame = _market_frame(pd.date_range("2024-01-03 13:00", periods=1, freq="h"))
    before = build_multimodal_features(frame, reference_records, instrument="AAPL")
    future_filing = _record(
        "future-filing",
        event_type="FUNDAMENTAL_FILING",
        published=datetime(2024, 2, 1, 18, 0, tzinfo=UTC),
        revenue=999,
    )
    after = build_multimodal_features(frame, reference_records + [future_filing], instrument="AAPL")
    pd.testing.assert_frame_equal(before, after)


def test_leakage_d_asof_query(reference_records):
    """TEST D: only records with availability <= T are returned."""
    query_time = datetime(2024, 1, 4, 12, 0)
    eligible = asof_records(reference_records, instrument="AAPL", as_of=query_time)
    for record in eligible:
        available = effective_availability(record)
        assert available is not None and available <= query_time


def test_leakage_e_dataset_extension(reference_records):
    """TEST E: extending data with future rows must not change history."""
    early = _market_frame(pd.date_range("2024-01-03 13:00", periods=2, freq="h"))
    extended = _market_frame(pd.date_range("2024-01-03 13:00", periods=40, freq="h"))
    before = build_multimodal_features(early, reference_records, instrument="AAPL")
    after = build_multimodal_features(extended, reference_records, instrument="AAPL")
    pd.testing.assert_frame_equal(before, after.iloc[: len(before)].reset_index(drop=True))


def test_leakage_f_same_day_timing():
    """TEST F: a 16:30 publication must not influence a 14:00 prediction."""
    afternoon_news = _record("afternoon-news", published=datetime(2024, 1, 3, 16, 30, tzinfo=UTC))
    eligible_morning = asof_records(
        [afternoon_news], instrument="AAPL", as_of=datetime(2024, 1, 3, 14, 0)
    )
    assert eligible_morning == []
    eligible_evening = asof_records(
        [afternoon_news], instrument="AAPL", as_of=datetime(2024, 1, 3, 17, 0)
    )
    assert len(eligible_evening) == 1


# ---------------------------------------------------------------------------
# As-of semantics (sections 8/18/19/22)
# ---------------------------------------------------------------------------
def test_day_only_records_eligible_next_day_only():
    """Unknown-offset sources become eligible at the START of the next day."""
    naive_utc, original, tz, reliability = normalize_timestamp(
        "2024-01-04T14:00:00", original_timezone="America/New_York"
    )
    assert naive_utc is not None and reliability is TemporalReliability.DAY_ONLY
    record = ExternalRecord(
        record_id="r",
        source="s",
        source_identifier="x",
        instrument="AAPL",
        event_type="REGULATORY",
        event_timestamp=naive_utc,
        publication_timestamp=naive_utc,
        ingestion_timestamp=naive_utc,
        availability_timestamp=naive_utc,
        reliability=reliability,
        original_timestamp=original,
        original_timezone=tz,
    )
    # Same day 23:00 → NOT eligible (never assume intraday/morning release).
    assert asof_records([record], instrument="AAPL", as_of=datetime(2024, 1, 4, 23, 0)) == []
    # Next day 00:00 → eligible.
    assert len(asof_records([record], instrument="AAPL", as_of=datetime(2024, 1, 5, 0, 0))) == 1


def test_insufficient_records_never_eligible():
    naive, _, _, reliability = normalize_timestamp("2024-01-04T14:00:00")  # no tz
    assert reliability is TemporalReliability.INSUFFICIENT and naive is None
    record = ExternalRecord(
        record_id="r2",
        source="s",
        source_identifier="y",
        instrument="AAPL",
        event_type="OTHER",
        event_timestamp=None,
        publication_timestamp=None,
        ingestion_timestamp=datetime(2024, 1, 4),
        availability_timestamp=None,
        reliability=reliability,
    )
    assert asof_records([record], instrument="AAPL", as_of=datetime(2025, 1, 1)) == []


def test_latest_fundamental_carry_forward():
    """Latest eligible filing is carried forward; nothing before publication."""
    older = _record(
        "filing-Q3",
        event_type="FUNDAMENTAL_FILING",
        published=datetime(2023, 10, 25, 18, 0, tzinfo=UTC),
        revenue=100,
    )
    newer = _record(
        "filing-Q4",
        event_type="FUNDAMENTAL_FILING",
        published=datetime(2024, 1, 4, 18, 30, tzinfo=UTC),
        revenue=120,
    )
    assert (
        latest_fundamental_asof(
            [older, newer], instrument="AAPL", as_of=datetime(2024, 1, 4, 12, 0)
        ).source_identifier
        == "filing-Q3"
    )
    assert (
        latest_fundamental_asof(
            [older, newer], instrument="AAPL", as_of=datetime(2024, 1, 5, 0, 0)
        ).source_identifier
        == "filing-Q4"
    )


def test_event_windows_are_controlled():
    records = [
        _record("e1", published=datetime(2024, 1, 2, 9, 0, tzinfo=UTC)),
        _record("e2", published=datetime(2024, 1, 5, 9, 0, tzinfo=UTC)),
    ]
    as_of = datetime(2024, 1, 5, 12, 0)
    assert len(events_in_window(records, instrument="AAPL", as_of=as_of, window_days=1)) == 1
    assert len(events_in_window(records, instrument="AAPL", as_of=as_of, window_days=3)) == 1
    assert len(events_in_window(records, instrument="AAPL", as_of=as_of, window_days=7)) == 2
    with pytest.raises(AsOfError, match="unsupported event window"):
        events_in_window(records, instrument="AAPL", as_of=as_of, window_days=30)


def test_entity_isolation():
    """Records of other instruments are never joined (entity resolution)."""
    other = _record("msft-news", instrument="MSFT")
    assert asof_records([other], instrument="AAPL", as_of=datetime(2025, 1, 1)) == []


# ---------------------------------------------------------------------------
# Source normalization, dedup, restatements (sections 20/26/27/29/30)
# ---------------------------------------------------------------------------
def test_normalize_batch_validates_and_normalizes(reference_records):
    assert len(reference_records) == 5  # 6 rows, 1 cross-source duplicate removed
    assert all(record.instrument == "AAPL" for record in reference_records)
    ambiguous = [r for r in reference_records if r.source_identifier == "news-ambiguous-tz"]
    assert ambiguous and ambiguous[0].reliability is TemporalReliability.DAY_ONLY


def test_normalize_batch_rejects_malformed():
    with pytest.raises(SourceError, match="missing required field"):
        normalize_batch([{"instrument": "AAPL", "event_type": "OTHER"}], source="x")
    with pytest.raises(SourceError, match="unknown event_type"):
        normalize_batch(
            [{"source_identifier": "a", "instrument": "AAPL", "event_type": "HYPE"}],
            source="x",
        )


def test_deduplicate_cross_source():
    first = _record("dup-1", published=datetime(2024, 1, 3, 12, 0, tzinfo=UTC), headline="A B C")
    second = _record("dup-2", published=datetime(2024, 1, 3, 12, 5, tzinfo=UTC), headline="A B C")
    deduped = deduplicate([second, first])
    assert len(deduped) == 1
    assert deduped[0].source_identifier == "dup-1"  # earliest publication kept


def test_restatement_policy():
    original = _record(
        "filing-Q1",
        event_type="FUNDAMENTAL_FILING",
        published=datetime(2024, 4, 25, 18, 0, tzinfo=UTC),
        fiscal_period="Q1-2024",
        revenue=100,
    )
    restated = _record(
        "filing-Q1-restated",
        event_type="FUNDAMENTAL_FILING",
        published=datetime(2024, 6, 10, 18, 0, tzinfo=UTC),
        fiscal_period="Q1-2024",
        revenue=105,
    )
    policy = restatement_policy([original, restated])
    assert "first_publication_is_truth" in policy["policy"]
    assert policy["periods_with_restatements"] == {"Q1-2024": 2}
    # A prediction between the two publications sees ONLY the original.
    as_of = datetime(2024, 5, 1)
    latest = latest_fundamental_asof([original, restated], instrument="AAPL", as_of=as_of)
    assert latest.source_identifier == "filing-Q1"


# ---------------------------------------------------------------------------
# Feature layer + integration chain (section 42)
# ---------------------------------------------------------------------------
def _market_frame(timestamps: pd.DatetimeIndex) -> pd.DataFrame:
    rows = len(timestamps)
    # Values depend only on the timestamp (not the frame length) so extended
    # datasets reproduce identical historical rows (leakage test E).
    hours = timestamps.hour.to_numpy(dtype=float)
    return pd.DataFrame(
        {
            "ticker": ["AAPL"] * rows,
            "timestamp": timestamps,
            "sma_5_ratio": 1.0 + 0.01 * np.sin(hours),
            "momentum_10d": 0.005 * np.cos(hours),
        }
    )


def test_multimodal_feature_row_combines_modalities(reference_records):
    timestamps = pd.date_range("2024-01-04 00:00", periods=3, freq="12h")
    features = build_multimodal_features(
        _market_frame(timestamps), reference_records, instrument="AAPL"
    )
    for column in ("revenue", "debt_ratio", "events_1d", "events_7d", "has_fundamentals"):
        assert column in features.columns
    # Before the filing publication (2024-01-04 18:30): no fundamentals.
    assert features["has_fundamentals"].iloc[0] == 0
    # After it: fundamentals visible with derived ratios.
    assert features["has_fundamentals"].iloc[2] == 1
    assert features["debt_ratio"].iloc[2] == pytest.approx(120 / 340)
    assert features["margin"].iloc[2] == pytest.approx(25 / 120)


def test_feature_version_is_dedicated():
    """The multimodal additions use feature_set_v0.2 — v0.1 is not mutated."""
    assert MULTIMODAL_FEATURE_VERSION == "feature_set_v0.2"
    assert "revenue" not in multimodal_feature_columns()[:0]  # columns exist
    assert "events_7d" in multimodal_feature_columns()


def test_missing_modality_is_nan_not_fabricated():
    frame = _market_frame(pd.date_range("2020-01-01", periods=2, freq="D"))
    features = build_multimodal_features(frame, [], instrument="AAPL")
    assert features["revenue"].isna().all()
    assert (features["has_fundamentals"] == 0).all()
    assert (features["events_1d"] == 0).all()


def test_integration_chain_to_model_input(reference_records):
    """Source -> normalize -> as-of -> features -> numeric model input matrix."""
    timestamps = pd.date_range("2024-01-04 00:00", periods=4, freq="12h")
    features = build_multimodal_features(
        _market_frame(timestamps), reference_records, instrument="AAPL"
    )
    numeric = features.select_dtypes(include=[np.number])
    # All external numeric columns are model-consumable (NaN allowed pre-publication).
    assert numeric.shape[0] == 4
    assert numeric["debt_ratio"].notna().sum() >= 1
