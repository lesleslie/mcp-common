"""Benchmarks for configuration loading performance."""

import pytest
from pathlib import Path
from mcp_common.config import MCPBaseSettings


class TestConfigBenchmarks:
    """Benchmark configuration loading operations."""

    @pytest.mark.benchmark(group="config", min_rounds=10)
    def test_yaml_loading_default(self, benchmark):
        """Benchmark YAML loading with default values only."""

        def load():
            class TestSettings(MCPBaseSettings):
                test_field: str = "default"

            return TestSettings.load("benchmark-test")

        result = benchmark(load)
        assert result.test_field == "default"

    @pytest.mark.benchmark(group="config", min_rounds=10)
    def test_yaml_loading_with_file(self, benchmark, tmp_path):
        """Benchmark YAML loading from file."""
        import yaml

        # Create settings directory in temp path
        settings_dir = tmp_path / "settings"
        settings_dir.mkdir(parents=True, exist_ok=True)

        yaml_file = settings_dir / "benchmark-test.yaml"
        yaml_file.write_text("test_field: from_file\n")

        def load():
            class TestSettings(MCPBaseSettings):
                test_field: str = "default"

            # Load from the temp path
            import os
            old_cwd = os.getcwd()
            try:
                os.chdir(str(tmp_path))
                return TestSettings.load("benchmark-test")
            finally:
                os.chdir(old_cwd)

        result = benchmark(load)
        assert result.test_field == "from_file"

    @pytest.mark.benchmark(group="config", min_rounds=10)
    def test_env_var_override(self, benchmark, monkeypatch):
        """Benchmark environment variable override."""
        monkeypatch.setenv("BENCHMARK_TEST_TEST_FIELD", "from_env")

        def load():
            class TestSettings(MCPBaseSettings):
                test_field: str = "default"

            return TestSettings.load("benchmark-test")

        result = benchmark(load)
        assert result.test_field == "from_env"

    @pytest.mark.benchmark(group="config", min_rounds=10)
    def test_settings_validation(self, benchmark):
        """Benchmark settings validation with Pydantic."""

        def load():
            class TestSettings(MCPBaseSettings):
                pass  # No custom fields to test base validation

            return TestSettings.load("benchmark-test")

        result = benchmark(load)
        # Just verify it loads without error
        assert result is not None
