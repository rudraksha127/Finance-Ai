"""Tests for src/cleaning/validation.py — VAL-* rule engine with explicit reasons."""

from __future__ import annotations

from datetime import date, datetime

from src.cleaning.validation import (
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    ValidationOptions,
    validate_batch,
)


def _record(
    day: int = 2,
    *,
    close: float = 101.0,
    high: float | None = None,
    volume: float = 1_000_000,
    **overrides,
) -> dict:
    timestamp = datetime(2025, 1, day, 0, 0, 0)
    high = high if high is not None else max(close, 100.0) + 1.0
    record = {
        "ticker": "AAPL",
        "timestamp": timestamp,
        "open": 100.0,
        "high": high,
        "low": max(close, 100.0) - 1.0,
        "close": close,
        "adj_close": close,
        "volume": volume,
        "raw_line": day,  # 1-based CSV line
    }
    record.update(overrides)
    return record


def _batch(count: int = 3, *, start_day: int = 2, **overrides) -> list[dict]:
    return [
        _record(start_day + offset, close=100.0 + offset, **overrides if offset == 0 else {})
        for offset in range(count)
    ]


class TestSchemaRules:
    def test_min_rows_below_threshold_is_error(self):
        report = validate_batch([_record(2)], [], options=ValidationOptions(min_rows=2))
        assert report.schema_valid is False
        assert any(
            issue.rule_id == "VAL-S03" and issue.severity == SEVERITY_ERROR
            for issue in report.issues
        )

    def test_reader_schema_issue_sets_schema_invalid(self):
        report = validate_batch(
            [],
            [
                {
                    "rule_id": "VAL-S01",
                    "severity": "error",
                    "category": "schema",
                    "message": "bad cols",
                    "count": 1,
                }
            ],
        )
        assert report.schema_valid is False


class TestPriceVolumeRules:
    def test_non_positive_price_rejects_row(self):
        batch = _batch(3)
        batch[1]["close"] = -5.0
        report = validate_batch(batch, [])
        assert report.rejected_raw_lines == frozenset({batch[1]["raw_line"]})
        assert any(
            issue.rule_id == "VAL-P04" and issue.severity == SEVERITY_ERROR
            for issue in report.issues
        )

    def test_negative_volume_rejects_row(self):
        batch = _batch(3)
        batch[0]["volume"] = -1
        report = validate_batch(batch, [])
        assert batch[0]["raw_line"] in report.rejected_raw_lines
        assert any(issue.rule_id == "VAL-V01" for issue in report.issues)

    def test_ohlc_high_conflict_is_error_fixable(self):
        batch = _batch(2)
        batch[0]["high"] = 50.0  # < open/close
        report = validate_batch(batch, [])
        assert any(
            issue.rule_id == "VAL-P05" and issue.severity == SEVERITY_ERROR
            for issue in report.issues
        )

    def test_ohlc_low_conflict_is_error_fixable(self):
        batch = _batch(2)
        batch[1]["low"] = 200.0  # > open/close
        report = validate_batch(batch, [])
        assert any(issue.rule_id == "VAL-P06" for issue in report.issues)


class TestTimestampRules:
    def test_duplicate_timestamp_reports_val_t01(self):
        batch = _batch(2)
        dup = _record(2, close=200.0)
        report = validate_batch(batch + [dup], [])
        assert any(issue.rule_id == "VAL-T01" for issue in report.issues)
        assert issue_count(report, "VAL-T01") == 1  # only the later duplicate counts

    def test_future_timestamp_rejects_row(self):
        batch = _batch(2)
        batch[1]["timestamp"] = datetime(2030, 1, 2)
        report = validate_batch(batch, [], now=datetime(2025, 1, 31))
        assert batch[1]["raw_line"] in report.rejected_raw_lines
        assert any(issue.rule_id == "VAL-T03" for issue in report.issues)

    def test_weekend_rows_flagged_warning(self):
        # 2025-01-04 is a Saturday.
        batch = [_record(4), _record(6)]
        report = validate_batch(batch, [])
        assert any(
            issue.rule_id == "VAL-T04" and issue.severity == SEVERITY_WARNING
            for issue in report.issues
        )

    def test_holiday_rows_flagged_warning_when_configured(self):
        batch = [_record(2), _record(3)]
        options = ValidationOptions(holidays=frozenset({date(2025, 1, 3)}))
        report = validate_batch(batch, [], options=options)
        assert any(issue.rule_id == "VAL-T05" for issue in report.issues)

    def test_disordered_timestamps_warning(self):
        batch = [_record(6), _record(2), _record(4)]
        report = validate_batch(batch, [])
        assert any(
            issue.rule_id == "VAL-T02" and issue.severity == SEVERITY_WARNING
            for issue in report.issues
        )


class TestCompleteness:
    def test_high_missing_percentage_warns(self):
        batch = _batch(4)
        for record in batch:
            record["open"] = None  # 50% missing if 2 of 4? set 3 of 4
        batch[0]["open"] = 100.0
        report = validate_batch(batch, [], options=ValidationOptions(max_missing_pct=0.30))
        assert any(
            issue.rule_id == "VAL-C01" and issue.severity == SEVERITY_WARNING
            for issue in report.issues
        )

    def test_gap_over_five_days_warns(self):
        batch = [_record(2), _record(15)]  # 13-day gap
        report = validate_batch(batch, [])
        assert any(issue.rule_id == "VAL-C02" for issue in report.issues)


class TestReportShape:
    def test_every_failed_record_has_explicit_reason(self):
        batch = _batch(5)
        batch[0]["close"] = -1.0
        batch[2]["volume"] = -5
        batch[4]["high"] = 10.0  # < open/close → fixable
        report = validate_batch(batch, [])
        # Every rejected reason must be explicit.
        for line in report.rejected_raw_lines:
            assert any(
                line in issue.raw_lines
                for issue in report.issues
                if issue.severity == SEVERITY_ERROR
            )

    def test_validation_report_counts(self):
        report = validate_batch(_batch(3), [])
        assert report.rules_checked > 0
        assert report.summary["total"] == 3
        # Jan 4 is a Saturday → weekend warning flags line 4, but it is
        # not rejected.
        assert report.affected_raw_lines == frozenset({4})
        assert report.rejected_raw_lines == frozenset()


def issue_count(report, rule_id: str) -> int:
    return sum(issue.count for issue in report.issues if issue.rule_id == rule_id)
