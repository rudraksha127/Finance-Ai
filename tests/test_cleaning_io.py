"""Tests for src/cleaning/io.py — raw reader edge cases, hashing, writer, holidays."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from src.cleaning.io import (
    interval_label,
    load_holidays,
    read_raw_csv,
    sha256_of,
    write_interim_csv,
)
from src.core.errors import StorageError


def _raw_csv(rows, columns=None):
    columns = columns or [
        "ticker",
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
    ]
    lines = [",".join(columns)]
    for row in rows:
        lines.append(",".join(str(cell) for cell in row))
    return "\n".join(lines) + "\n"


class TestReadRawCsv:
    def test_valid_rows_parse_with_raw_line(self, tmp_path):
        path = tmp_path / "AAPL_daily.csv"
        path.write_text(
            _raw_csv(
                [
                    (
                        "AAPL",
                        "2025-01-02T00:00:00",
                        "100.0",
                        "101.5",
                        "99.5",
                        "101.0",
                        "101.0",
                        "1000000",
                    ),
                    (
                        "AAPL",
                        "2025-01-03T00:00:00",
                        "101.0",
                        "102.5",
                        "100.5",
                        "102.0",
                        "102.0",
                        "1100000",
                    ),
                ]
            ),
            encoding="utf-8",
        )
        records, issues = read_raw_csv(path)
        assert len(records) == 2
        assert records[0]["raw_line"] == 2
        assert records[0]["timestamp"] == datetime(2025, 1, 2)
        assert records[0]["adj_close"] == 101.0
        assert issues == []

    def test_unparseable_row_reports_issue(self, tmp_path):
        path = tmp_path / "AAPL_daily.csv"
        path.write_text(
            _raw_csv(
                [
                    (
                        "AAPL",
                        "2025-01-02T00:00:00",
                        "100.0",
                        "101.5",
                        "99.5",
                        "101.0",
                        "101.0",
                        "1000000",
                    ),
                    ("AAPL", "not-a-date", "100.0", "x", "99.5", "101.0", "101.0", "1000000"),
                ]
            ),
            encoding="utf-8",
        )
        records, issues = read_raw_csv(path)
        assert len(records) == 1
        assert any(issue["rule_id"] == "VAL-S04" for issue in issues)
        assert issues[0]["raw_line"] == 3

    def test_unexpected_columns_reports_schema_issue(self, tmp_path):
        path = tmp_path / "AAPL_daily.csv"
        path.write_text(
            _raw_csv(
                [
                    (
                        "AAPL",
                        "2025-01-02T00:00:00",
                        "100.0",
                        "101.5",
                        "99.5",
                        "101.0",
                        "101.0",
                        "1000000",
                    )
                ],
                columns=["symbol", "date", "o", "h", "l", "c", "v"],
            ),
            encoding="utf-8",
        )
        _, issues = read_raw_csv(path)
        assert any(issue["rule_id"] == "VAL-S01" for issue in issues)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(StorageError, match="not found"):
            read_raw_csv(tmp_path / "nope.csv")

    def test_blank_adj_close_is_none(self, tmp_path):
        path = tmp_path / "AAPL_daily.csv"
        path.write_text(
            _raw_csv(
                [("AAPL", "2025-01-02T00:00:00", "100.0", "101.5", "99.5", "101.0", "", "1000000")]
            ),
            encoding="utf-8",
        )
        records, _ = read_raw_csv(path)
        assert records[0]["adj_close"] is None


class TestHashingAndWriter:
    def test_sha256_stable(self, tmp_path):
        path = tmp_path / "f.csv"
        path.write_text("a,b\n1,2\n", encoding="utf-8")
        assert sha256_of(path) == sha256_of(path)
        assert len(sha256_of(path)) == 64

    def test_write_interim_csv_sorts_and_has_raw_line(self, tmp_path):
        interim = tmp_path / "interim"
        records = [
            {
                "ticker": "AAPL",
                "timestamp": datetime(2025, 1, 3),
                "open": 101.0,
                "high": 102.0,
                "low": 100.0,
                "close": 101.5,
                "adj_close": None,
                "volume": 1000,
                "raw_line": 3,
            },
            {
                "ticker": "AAPL",
                "timestamp": datetime(2025, 1, 2),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "adj_close": 100.5,
                "volume": 900,
                "raw_line": 2,
            },
        ]
        path = write_interim_csv(interim, records, "AAPL", "1d", run_date=date(2025, 1, 10))
        assert path.name == "cleaned_20250110_AAPL_daily.csv"
        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines[0].startswith("ticker,timestamp,open,high,low,close,adj_close,volume,raw_line")
        # Sorted ascending: Jan 2 first.
        assert lines[1].split(",")[1] == "2025-01-02T00:00:00"
        assert lines[1].split(",")[-1] == "2"
        assert lines[2].split(",")[6] == ""  # adj_close None serialized blank

    def test_interval_label_valid_and_invalid(self):
        assert interval_label("1d") == "daily"
        assert interval_label("1wk") == "weekly"
        assert interval_label("1mo") == "monthly"
        with pytest.raises(StorageError, match="unsupported interval"):
            interval_label("5m")


class TestHolidays:
    def test_load_holidays_from_json(self, tmp_path):
        external = tmp_path / "external"
        external.mkdir()
        path = external / "holidays.json"
        path.write_text('["2025-01-01", "2025-12-25"]', encoding="utf-8")
        holidays = load_holidays("holidays.json", external)
        assert holidays == frozenset({date(2025, 1, 1), date(2025, 12, 25)})

    def test_load_holidays_unset_returns_empty(self, tmp_path):
        assert load_holidays(None, tmp_path) == frozenset()

    def test_load_holidays_missing_file_raises(self, tmp_path):
        with pytest.raises(StorageError, match="cannot read holidays"):
            load_holidays("nope.json", tmp_path)

    def test_load_holidays_bad_payload_raises(self, tmp_path):
        external = tmp_path / "external"
        external.mkdir()
        (external / "holidays.json").write_text('{"not": "a list"}', encoding="utf-8")
        with pytest.raises(StorageError, match="must be a JSON list"):
            load_holidays("holidays.json", external)
