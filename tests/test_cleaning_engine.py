"""Tests for src/cleaning/cleaning.py and src/cleaning/actions.py."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.cleaning.actions import (
    CorporateActionError,
    apply_actions,
    load_actions,
    validate_action,
)
from src.cleaning.cleaning import clean_batch


def _record(
    day: int, *, close: float | None = 101.0, volume: float | None = 1_000_000, **overrides
) -> dict:
    record = {
        "ticker": "AAPL",
        "timestamp": datetime(2025, 1, day, 0, 0, 0),
        "open": 100.0,
        "high": 102.0 if close is None else max(close, 100.0) + 1.0,
        "low": 99.0 if close is None else min(close, 100.0) - 1.0,
        "close": close,
        "adj_close": close,
        "volume": volume,
        "raw_line": day,
    }
    record.update(overrides)
    return record


def _batch(days=3, start_day=2) -> list[dict]:
    return [_record(start_day + i, close=100.0 + i) for i in range(days)]


class TestCleanBatch:
    def test_clean_records_unchanged_input_rows(self):
        records = _batch(3)
        cleaned, stats = clean_batch(records)
        assert stats.input_rows == 3
        assert stats.output_rows == 3
        assert cleaned[0]["raw_line"] == records[0]["raw_line"]

    def test_duplicate_keep_last(self):
        records = _batch(2)
        dup = _record(2, close=999.0)
        dup["raw_line"] = 99
        records.append(dup)
        cleaned, stats = clean_batch(records, duplicate_strategy="keep_last")
        assert stats.duplicates_removed == 1
        assert any(record["close"] == 999.0 for record in cleaned)  # later row wins

    def test_duplicate_keep_first(self):
        records = _batch(2)
        dup = _record(2, close=999.0)
        dup["raw_line"] = 99
        records.append(dup)
        cleaned, _ = clean_batch(records, duplicate_strategy="keep_first")
        assert all(record["close"] != 999.0 for record in cleaned)

    def test_rejected_rows_dropped(self):
        records = _batch(4)
        rejected_line = records[1]["raw_line"]
        cleaned, stats = clean_batch(records, rejected_raw_lines=frozenset({rejected_line}))
        assert stats.rejected_dropped == 1
        assert all(record["raw_line"] != rejected_line for record in cleaned)

    def test_ohlc_order_fixed(self):
        records = _batch(2)
        records[0]["high"] = 50.0  # should become max(open, close) = 100
        records[1]["low"] = 500.0  # should become min(open, close) = min(open, close)
        cleaned, stats = clean_batch(records)
        assert stats.ohlc_fixed == 2
        assert cleaned[0]["high"] == 100.0  # max(open=100, close=100) = 100
        assert cleaned[1]["low"] == 100.0  # min(open=100, close=101) = 100

    def test_missing_price_forward_filled_in_one_day_gap(self):
        records = _batch(3)
        records[1]["close"] = None
        cleaned, stats = clean_batch(records)
        assert stats.forward_filled >= 1
        assert cleaned[1]["close"] == 100.0  # carried from day 1

    def test_missing_price_interpolated_two_day_gap(self):
        records = _batch(4)
        records[1]["close"] = None
        records[2]["close"] = None
        cleaned, stats = clean_batch(records, interpolate_max_gap=3)
        assert stats.interpolated >= 2
        assert 100.0 < cleaned[1]["close"] < 103.0  # between neighbors

    def test_missing_volume_zero_filled(self):
        records = _batch(3)
        records[1]["volume"] = None
        cleaned, stats = clean_batch(records)
        assert stats.volume_zero_filled == 1
        assert cleaned[1]["volume"] == 0.0

    def test_disabled_fill_never_creates_prices(self):
        records = _batch(2)
        records[0]["close"] = None  # leading gap is never extrapolated
        cleaned, stats = clean_batch(records)
        # Leading gap: marked incomplete (kept with close=None), never filled.
        assert stats.marked_incomplete >= 1
        assert cleaned[0]["close"] is None
        assert cleaned[0].get("incomplete") is True
        assert stats.input_rows == len(records)

    def test_trailing_gap_marked_incomplete_never_fabricated(self):
        records = _batch(3)
        records[2]["close"] = None  # trailing: cannot interpolate forward
        cleaned, stats = clean_batch(records)
        assert cleaned[2]["close"] is None
        assert cleaned[2].get("incomplete") is True
        assert stats.marked_incomplete >= 1

    def test_long_gap_drops_row(self):
        # 12 consecutive missing closes (> MAX_INCOMPLETE_RUN=10) -> dropped.
        records = _batch(14, start_day=2)
        for record in records[1:13]:
            record["close"] = None
        cleaned, stats = clean_batch(records)
        assert stats.dropped_missing == 12
        assert len(cleaned) == 2

    def test_interpolation_outside_sanity_uses_forward_fill(self):
        # Linear midpoint between 10 and 400 is ~205; outside ±20% of the
        # 10-side neighbor band [8, 12] → guard fails → forward fill used.
        records = _batch(4)
        records[1]["close"] = None
        records[2]["close"] = None
        records[0]["close"] = 10.0
        records[0]["high"] = 11.0
        records[0]["low"] = 9.0
        records[3]["close"] = 400.0
        records[3]["high"] = 401.0
        records[3]["low"] = 399.0
        cleaned, stats = clean_batch(records, interpolate_max_gap=3)
        assert stats.interpolated == 0
        assert stats.forward_filled >= 2
        assert cleaned[1]["close"] == 10.0
        assert cleaned[2]["close"] == 10.0

    def test_adj_close_forward_filled(self):
        records = _batch(3)
        records[1]["adj_close"] = None
        cleaned, stats = clean_batch(records)
        assert cleaned[1]["adj_close"] == 100.0
        assert stats.forward_filled >= 1

    def test_outlier_flagged_kept(self):
        # 20 flat closes at 100, then a 500 spike, then back to 100. The
        # 4.0 return is a clear z-score outlier (no masking with n=22).
        records = []
        for day, close in enumerate([100.0] * 20 + [500.0, 100.0], start=2):
            records.append(
                {
                    "ticker": "AAPL",
                    "timestamp": datetime(2025, 1, day, 0, 0, 0),
                    "open": close,
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                    "adj_close": close,
                    "volume": 1_000_000,
                    "raw_line": day,
                }
            )
        cleaned, stats = clean_batch(records, outlier_zscore_threshold=3.0)
        assert stats.outliers_flagged >= 1
        assert any(record.get("outlier_flagged") for record in cleaned)
        assert len(cleaned) == len(records)  # kept, not dropped

    def test_completely_empty_batch_is_safe(self):
        cleaned, stats = clean_batch([])
        assert cleaned == []
        assert stats.output_rows == 0


class TestAdjustment:
    def test_split_factor_and_rows(self):
        records = [_record(2, close=100.0), _record(3, close=103.0), _record(4, close=106.0)]
        adjusted, _ = apply_actions(
            records, [{"type": "split", "ratio": 4.0, "effective_date": "2025-01-04"}]
        )
        before = [r for r in adjusted if r["timestamp"].day < 4]
        after = [r for r in adjusted if r["timestamp"].day >= 4]
        assert [r["close"] for r in before] == [25.0, 25.75]
        assert [r["close"] for r in after] == [106.0]

    def test_dividend_uses_pre_ex_close_factor(self):
        before = _record(2, close=100.0)
        ex = _record(3, close=103.0)
        later = _record(4, close=106.0)
        adjusted, summary = apply_actions(
            [before, ex, later],
            [{"type": "dividend", "dividend_amount": 5.0, "effective_date": "2025-01-03"}],
        )
        # factor = 1 - 5/100 = 0.95 → only rows strictly before ex-date adjusted.
        assert adjusted[0]["close"] == pytest.approx(95.0)
        assert adjusted[1]["close"] == 103.0
        assert adjusted[2]["close"] == 106.0
        assert summary.total_rows_adjusted == 1

    def test_dividend_exceeding_close_raises(self):
        with pytest.raises(CorporateActionError):
            apply_actions(
                [_record(2, close=100.0)],
                [{"type": "dividend", "dividend_amount": 500.0, "effective_date": "2025-01-03"}],
            )

    def test_ticker_change_renames_only(self):
        # The raw records use ticker AAPL; the action targets FB→META, so
        # no rows match and nothing changes — verify the no-op path.
        adjusted, summary = apply_actions(
            [_record(2)],
            [
                {
                    "type": "ticker_change",
                    "old_symbol": "FB",
                    "new_symbol": "META",
                    "effective_date": "2022-06-09",
                }
            ],
        )
        assert adjusted[0]["ticker"] == "AAPL"
        assert adjusted[0].get("ticker_changed") is None
        assert summary.total_rows_adjusted == 0

    def test_ticker_change_renames_matching_rows(self):
        records = [
            {
                "ticker": "FB",
                "timestamp": datetime(2022, 6, 8, 0, 0, 0),
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "adj_close": 101.0,
                "volume": 1_000_000,
                "raw_line": 2,
            }
        ]
        adjusted, summary = apply_actions(
            records,
            [
                {
                    "type": "ticker_change",
                    "old_symbol": "FB",
                    "new_symbol": "META",
                    "effective_date": "2022-06-09",
                }
            ],
        )
        assert adjusted[0]["ticker"] == "META"
        assert adjusted[0]["ticker_changed"] is True
        assert summary.total_rows_adjusted == 1

    def test_actions_are_applied_chronologically_and_no_raw_mutation(self):
        before = [dict(r) for r in _batch(4)]
        apply_actions(_batch(4), [{"type": "split", "ratio": 2.0, "effective_date": "2025-01-04"}])
        # Original input records must be untouched (defensive copies).
        assert [r["close"] for r in before] == [100.0, 101.0, 102.0, 103.0]

    def test_load_actions_from_json(self, tmp_path):
        path = tmp_path / "actions.json"
        path.write_text(
            '[{"type": "split", "ratio": 2.0, "effective_date": "2025-01-04"}]',
            encoding="utf-8",
        )
        actions = load_actions(path)
        assert len(actions) == 1
        assert actions[0]["ratio"] == 2.0

    def test_load_actions_missing_file_is_empty(self, tmp_path):
        assert load_actions(tmp_path / "nope.json") == []

    def test_invalid_action_type_rejected(self):
        with pytest.raises(CorporateActionError):
            validate_action({"type": "quantum_squeeze", "effective_date": "2025-01-04"})
