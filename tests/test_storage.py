"""Tests for src/core/storage.py — raw/interim/processed storage layout."""

from dataclasses import dataclass
from pathlib import Path

from src.core.enums import StorageTier
from src.core.storage import ensure_data_directories, tier_directory


@dataclass(frozen=True)
class _FixturePaths:
    """Structural stand-in for the config DataConfig (same attributes)."""

    raw_dir: Path
    interim_dir: Path
    processed_dir: Path


class TestTierDirectory:
    def test_tier_mapping(self, tmp_path):
        paths = _FixturePaths(
            raw_dir=tmp_path / "raw",
            interim_dir=tmp_path / "interim",
            processed_dir=tmp_path / "processed",
        )
        assert tier_directory(paths, StorageTier.RAW) == paths.raw_dir
        assert tier_directory(paths, StorageTier.INTERIM) == paths.interim_dir
        assert tier_directory(paths, StorageTier.PROCESSED) == paths.processed_dir


class TestEnsureDataDirectories:
    def test_directories_created_under_tmp(self, tmp_path):
        paths = _FixturePaths(
            raw_dir=tmp_path / "data" / "raw",
            interim_dir=tmp_path / "data" / "interim",
            processed_dir=tmp_path / "data" / "processed",
        )
        result = ensure_data_directories(paths)

        assert set(result) == {StorageTier.RAW, StorageTier.INTERIM, StorageTier.PROCESSED}
        for tier in StorageTier:
            assert result[tier] == tier_directory(paths, tier)
            assert result[tier].is_dir()

    def test_ensure_is_idempotent(self, tmp_path):
        paths = _FixturePaths(
            raw_dir=tmp_path / "raw",
            interim_dir=tmp_path / "interim",
            processed_dir=tmp_path / "processed",
        )
        ensure_data_directories(paths)
        ensure_data_directories(paths)  # second call must not fail

    def test_no_data_files_are_created(self, tmp_path):
        paths = _FixturePaths(
            raw_dir=tmp_path / "raw",
            interim_dir=tmp_path / "interim",
            processed_dir=tmp_path / "processed",
        )
        ensure_data_directories(paths)
        for tier in StorageTier:
            directory = tier_directory(paths, tier)
            assert (
                list(directory.iterdir()) == []
            ), f"storage layout must not create data files in {tier.value}"
