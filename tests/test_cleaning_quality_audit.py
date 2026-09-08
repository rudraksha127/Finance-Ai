"""Tests for src/cleaning/quality.py and src/cleaning/audit.py."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.cleaning.audit import AuditRecord, TransformationStep, new_audit_id, write_audit_record
from src.cleaning.quality import compute_quality, gate_for, rating_for
from src.cleaning.validation import validate_batch


def _record(day: int, *, close: float = 101.0) -> dict:
    return {
        "ticker": "AAPL",
        "timestamp": datetime(2025, 1, day, 0, 0, 0),
        "open": 100.0,
        "high": max(close, 100.0) + 1.0,
        "low": min(close, 100.0) - 1.0,
        "close": close,
        "adj_close": close,
        "volume": 1_000_000,
        "raw_line": day,
    }


def _clean_records(days=(2, 3, 4), **overrides) -> list[dict]:
    return [dict(_record(day, **overrides), **{k: v for k, v in overrides.items()}) for day in days]


class TestQualityScore:
    def test_perfect_dataset_scores_high(self):
        records = _clean_records((2, 3, 4, 5))
        validation = validate_batch(records, [])
        report = compute_quality(records, validation, ticker="AAPL", now=datetime(2025, 1, 10))
        # completeness/consistency/uniqueness = 100; validity 100; freshness
        # (6 days) = 88 → 0.3+0.3+0.2+0.1*0.88+0.1 = 0.988 → ~98.8
        assert report.overall_score >= 95
        assert report.rating == rating_for(report.overall_score)
        assert report.gate in {"PASS", "PASS_WITH_WARNINGS"}

    def test_missing_and_duplicates_lower_score(self):
        records = [
            dict(_record(2), close=None),
            dict(_record(2), close=101.0),
            dict(_record(3, close=102.0)),
        ]
        validation = validate_batch(records, [])
        report = compute_quality(records, validation, ticker="AAPL", now=datetime(2025, 1, 10))
        assert report.overall_score < 95
        # 2 unique timestamps of 3 → 66.67; one null close trims completeness.
        assert report.dimensions["uniqueness"] == pytest.approx(66.67, abs=0.1)
        assert report.dimensions["completeness"] == pytest.approx(93.33, abs=0.1)

    def test_freshness_decays(self):
        records = _clean_records((2,))
        report_old = compute_quality(
            records, validate_batch(records, []), ticker="AAPL", now=datetime(2025, 3, 1)
        )
        report_new = compute_quality(
            records, validate_batch(records, []), ticker="AAPL", now=datetime(2025, 1, 3)
        )
        assert report_old.dimensions["freshness"] < report_new.dimensions["freshness"]

    def test_ratings_and_gate_bands(self):
        assert rating_for(95) == "excellent"
        assert rating_for(85) == "good"
        assert rating_for(75) == "fair"
        assert rating_for(65) == "poor"
        assert rating_for(50) == "failing"
        assert gate_for(95) == "PASS"
        assert gate_for(80) == "PASS_WITH_WARNINGS"
        assert gate_for(65) == "REVIEW_REQUIRED"
        assert gate_for(50) == "FAIL"

    def test_empty_batch_scores_zero(self):
        report = compute_quality([], validate_batch([], []), ticker="AAPL")
        assert report.overall_score == 0.0
        assert report.rating == "failing"


class TestAudit:
    def _record(self, audit_id="audit-abc") -> AuditRecord:
        return AuditRecord(
            audit_id=audit_id,
            ticker="AAPL",
            interval="1d",
            raw_file_path="data/raw/AAPL_daily.csv",
            raw_file_hash="a" * 64,
            raw_row_count=3,
            transformations=(
                TransformationStep(
                    step=1,
                    name="schema",
                    rule_id="VAL-S01",
                    input_rows=3,
                    output_rows=3,
                    rows_affected=0,
                ),
            ),
            output_file_path="data/interim/AAPL_cleaned.csv",
            output_file_hash="b" * 64,
            output_row_count=3,
            quality_score=98.5,
            quality_rating="excellent",
            validation_errors=0,
            validation_warnings=0,
            started_at="2025-01-05T00:00:00",
            completed_at="2025-01-05T00:00:01",
            duration_ms=12.0,
            pipeline_version="0.1.0",
        )

    def test_write_audit_record_creates_json_and_appends_log(self, tmp_path):
        audit_id = new_audit_id()
        record = self._record(audit_id)
        path = write_audit_record(tmp_path, record)
        assert path.exists()
        assert "audit_" in path.name
        log_path = tmp_path / "audit" / "audit_log.jsonl"
        assert log_path.exists()
        assert "audit-abc" in path.read_text(encoding="utf-8") or audit_id in path.read_text(
            encoding="utf-8"
        )

    def test_new_audit_id_unique_and_prefixed(self):
        ids = {new_audit_id() for _ in range(50)}
        assert len(ids) == 50
        for audit_id in ids:
            assert audit_id.startswith("audit-")

    def test_audit_record_serializes_to_json(self):
        payload = self._record().to_json()
        assert payload["ticker"] == "AAPL"
        assert payload["raw_file_hash"] == "a" * 64
        assert isinstance(payload["transformations"], list)
        assert payload["transformations"][0]["rule_id"] == "VAL-S01"
