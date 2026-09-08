"""
Foundation validation tests.

These tests verify that the project structure and configuration
are correctly established. They should always pass.
"""

from pathlib import Path


class TestProjectStructure:
    """Verify that required directories exist."""

    def test_src_directory_exists(self):
        assert Path("src").exists(), "src/ directory missing"

    def test_tests_directory_exists(self):
        assert Path("tests").exists(), "tests/ directory missing"

    def test_data_directories_exist(self):
        data_dirs = ["data/raw", "data/interim", "data/processed", "data/external"]
        for directory in data_dirs:
            assert Path(directory).exists(), f"{directory} directory missing"

    def test_docs_directory_exists(self):
        assert Path("docs").exists(), "docs/ directory missing"

    def test_config_directory_exists(self):
        assert Path("config").exists(), "config/ directory missing"


class TestDocumentation:
    """Verify that required documentation exists."""

    def test_readme_exists(self):
        assert Path("README.md").exists(), "README.md missing"

    def test_project_bible_exists(self):
        assert Path("docs/PROJECT_BIBLE.md").exists(), "docs/PROJECT_BIBLE.md missing"

    def test_engineering_constitution_exists(self):
        assert Path(
            "docs/ENGINEERING_CONSTITUTION.md"
        ).exists(), "docs/ENGINEERING_CONSTITUTION.md missing"

    def test_architecture_principles_exists(self):
        assert Path(
            "docs/ARCHITECTURE_PRINCIPLES.md"
        ).exists(), "docs/ARCHITECTURE_PRINCIPLES.md missing"

    def test_decisions_exists(self):
        assert Path("docs/DECISIONS.md").exists(), "docs/DECISIONS.md missing"

    def test_current_state_exists(self):
        assert Path("docs/CURRENT_STATE.md").exists(), "docs/CURRENT_STATE.md missing"


class TestConfiguration:
    """Verify that configuration files exist."""

    def test_gitignore_exists(self):
        assert Path(".gitignore").exists(), ".gitignore missing"

    def test_env_example_exists(self):
        assert Path(".env.example").exists(), ".env.example missing"

    def test_requirements_exists(self):
        assert Path("requirements.txt").exists(), "requirements.txt missing"

    def test_gitignore_excludes_env(self):
        content = Path(".gitignore").read_text()
        assert ".env" in content, ".gitignore does not exclude .env"

    def test_gitignore_excludes_models(self):
        content = Path(".gitignore").read_text()
        assert (
            "models/" in content or "models/*" in content
        ), ".gitignore does not exclude model artifacts"

    def test_no_secrets_in_env_example(self):
        content = Path(".env.example").read_text()
        assert (
            "your_api_key_here" in content or "YOUR_" in content
        ), ".env.example should contain placeholder values only"
