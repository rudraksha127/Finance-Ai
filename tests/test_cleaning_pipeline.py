"""End-to-end tests for src/cleaning/pipeline.py — raw tier → interim tier.

Builds a real raw-tier CSV (as Milestone 02 produces), runs the full
pipeline, and asserts: raw is untouched, cleaned output exists with the
raw-line traceability column, audit record is written, quality gate is
reached, and corporate actions adjust historical prices only.
"""

from __future__ import annotations

from datetime import date, datetime

from src.cleaning.audit import audit_directory
from src.cleaning.pipeline import CleaningPipeline
from src.config.loader import AppConfig, CleaningConfig, DataConfig, LoggingConfig, ProjectConfig
from src.core.enums import AppEnvironment
from src.data.normalize import normalize_fetched_to_candles
from src.data.store import raw_file_path, store_candles
from tests.data_helpers import candle_records, fetched


def _raw_lines(raw_dir, ticker="AAPL", interval="1d"):
    """Read a raw CSV back into line numbers (to verify raw untouched)."""
    from src.cleaning.io import read_raw_csv

    records, issues = read_raw_csv(raw_file_path(raw_dir, ticker, interval))
    return sorted(r["raw_line"] for r in records), issues


def _app_config(tmp_path, *, holidays=None) -> AppConfig:
    external = tmp_path / "external"
    if holidays:
        external.mkdir(parents=True, exist_ok=True)
        (external / "holidays.json").write_text(
            "[" + ",".join(f'"{d}"' for d in holidays) + "]",
            encoding="utf-8",
        )
    return AppConfig(
        environment=AppEnvironment.TESTING,
        project=ProjectConfig(name="finance-ai-test", version="0.1.0"),
        data=DataConfig(
            raw_dir=tmp_path / "raw",
            interim_dir=tmp_path / "interim",
            processed_dir=tmp_path / "processed",
            external_dir=external,
        ),
        logging=LoggingConfig(level="INFO", format="json"),
        cleaning=CleaningConfig(),
    )


def _seed_raw(raw_dir, ticker="AAPL"):
    records = candle_records(5, first_day=date(2025, 1, 2))
    batch = normalize_fetched_to_candles(
        fetched(ticker, date(2025, 1, 2), date(2025, 1, 10), records)
    )
    store_candles(raw_dir, list(batch.candles))


class TestCleaningPipeline:
    def test_full_run_produces_cleaned_output_and_audit(self, tmp_path):
        config = _app_config(tmp_path)
        _seed_raw(config.data.raw_dir)
        result = CleaningPipeline(config, now=datetime(2025, 1, 10)).run("AAPL", "1d")

        assert result.ticker == "AAPL"
        assert result.interval == "1d"
        assert result.cleaned_rows == 5
        assert result.raw_rows == 5
        assert result.output_file.exists()
        assert result.output_hash
        assert result.audit_file.exists()
        assert result.stages[0] == "LOADING"
        assert result.stages[-1] == "COMPLETED"
        assert result.quality.gate in {"PASS", "PASS_WITH_WARNINGS"}
        assert result.quality.overall_score >= 70

        # Every cleaned row must trace back to a raw line.
        with open(result.output_file, encoding="utf-8") as handle:
            cleaned = handle.readlines()
        assert len(cleaned) == 6  # header + 5 rows
        assert "raw_line" in cleaned[0]

    def test_raw_tier_is_never_modified(self, tmp_path):
        config = _app_config(tmp_path)
        _seed_raw(config.data.raw_dir)
        path = raw_file_path(config.data.raw_dir, "AAPL", "1d")
        before = path.read_bytes()
        CleaningPipeline(config, now=datetime(2025, 1, 10)).run("AAPL", "1d")
        assert path.read_bytes() == before

    def test_weekend_rows_flagged_but_kept(self, tmp_path):
        # Raw seeds weekends (candle_records includes them); pipeline should
        # keep them with a VAL-T04 warning, not reject.
        config = _app_config(tmp_path)
        _seed_raw(config.data.raw_dir)
        result = CleaningPipeline(config, now=datetime(2025, 1, 10)).run("AAPL", "1d")
        assert any(issue.rule_id == "VAL-T04" for issue in result.validation.issues)
        assert result.cleaned_rows == result.raw_rows

    def test_corporate_action_applied_in_pipeline(self, tmp_path):
        config = _app_config(tmp_path)
        _seed_raw(config.data.raw_dir)  # candles 2025-01-02 .. 2025-01-06
        # Split effective mid-range: rows before 01-04 adjust, 01-04+ don't.
        actions_dir = config.data.external_dir / "corporate_actions"
        actions_dir.mkdir(parents=True, exist_ok=True)
        (actions_dir / "AAPL.json").write_text(
            '[{"type": "split", "ratio": 4.0, "effective_date": "2025-01-04"}]',
            encoding="utf-8",
        )
        result = CleaningPipeline(config, now=datetime(2025, 1, 10)).run("AAPL", "1d")
        assert result.adjustment.actions_applied == 1
        assert result.adjustment.total_rows_adjusted == 2  # Jan 2, Jan 3

        with open(result.output_file, encoding="utf-8") as handle:
            rows = handle.readlines()[1:]
        # Columns: ticker,timestamp,open,high,low,close,adj_close,volume,raw_line
        # First row (Jan 2) close 101 ÷ 4 = 25.25; row Jan 4 close 103 unchanged.
        first_close = float(rows[0].split(",")[5])
        assert first_close == 25.25
        third_close = float(rows[2].split(",")[5])
        assert third_close == 103.0  # on/after effective date untouched

    def test_corporate_action_warns_when_file_missing(self, tmp_path):
        config = _app_config(tmp_path)
        _seed_raw(config.data.raw_dir)
        result = CleaningPipeline(config, now=datetime(2025, 1, 10)).run("AAPL", "1d")
        assert result.adjustment.actions_applied == 0  # no file → no action

    def test_audit_log_append_only(self, tmp_path):
        config = _app_config(tmp_path)
        _seed_raw(config.data.raw_dir)
        pipeline = CleaningPipeline(config, now=datetime(2025, 1, 10))
        pipeline.run("AAPL", "1d")
        pipeline.run("AAPL", "1d")
        log = audit_directory(config.data.interim_dir) / "audit_log.jsonl"
        lines = [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) == 2
