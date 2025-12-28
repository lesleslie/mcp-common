"""Comprehensive tests for MCPServerSettings."""

import os
from pathlib import Path

import pytest
import yaml

from mcp_common.cli.settings import MCPServerSettings


class TestMCPServerSettingsBasic:
    """Test basic MCPServerSettings functionality."""

    def test_default_values(self):
        """Test default values for all fields."""
        settings = MCPServerSettings(server_name="test")

        assert settings.server_name == "test"
        assert settings.cache_root == Path(".oneiric_cache")
        assert settings.health_ttl_seconds == 60.0
        assert settings.log_level == "INFO"
        assert settings.log_file is None

    def test_custom_values(self, tmp_path: Path):
        """Test custom values override defaults."""
        settings = MCPServerSettings(
            server_name="custom",
            cache_root=tmp_path,
            health_ttl_seconds=30.0,
            log_level="DEBUG",
            log_file=tmp_path / "test.log",
        )

        assert settings.server_name == "custom"
        assert settings.cache_root == tmp_path
        assert settings.health_ttl_seconds == 30.0
        assert settings.log_level == "DEBUG"
        assert settings.log_file == tmp_path / "test.log"

    def test_health_ttl_validation(self):
        """Test health_ttl_seconds must be >= 1.0."""
        # Valid values
        MCPServerSettings(server_name="test", health_ttl_seconds=1.0)
        MCPServerSettings(server_name="test", health_ttl_seconds=100.0)

        # Invalid value should raise
        with pytest.raises(Exception):  # Pydantic ValidationError
            MCPServerSettings(server_name="test", health_ttl_seconds=0.5)


class TestMCPServerSettingsPathHelpers:
    """Test path helper methods."""

    def test_pid_path(self, tmp_path: Path):
        """Test PID file path generation."""
        settings = MCPServerSettings(server_name="test", cache_root=tmp_path)

        pid_path = settings.pid_path()

        assert pid_path == tmp_path / "mcp_server.pid"
        assert pid_path.parent == tmp_path

    def test_health_snapshot_path(self, tmp_path: Path):
        """Test health snapshot path generation."""
        settings = MCPServerSettings(server_name="test", cache_root=tmp_path)

        health_path = settings.health_snapshot_path()

        assert health_path == tmp_path / "runtime_health.json"
        assert health_path.parent == tmp_path

    def test_telemetry_snapshot_path(self, tmp_path: Path):
        """Test telemetry snapshot path generation."""
        settings = MCPServerSettings(server_name="test", cache_root=tmp_path)

        telemetry_path = settings.telemetry_snapshot_path()

        assert telemetry_path == tmp_path / "runtime_telemetry.json"
        assert telemetry_path.parent == tmp_path


class TestMCPServerSettingsLoad:
    """Test layered configuration loading."""

    def test_load_no_files(self, tmp_path: Path):
        """Test load when no YAML files exist."""
        # Change to temp dir to avoid finding project settings/
        os.chdir(tmp_path)

        settings = MCPServerSettings.load("test-server")

        # Should use defaults
        assert settings.server_name == "test-server"
        assert settings.cache_root == Path(".oneiric_cache")
        assert settings.health_ttl_seconds == 60.0

    def test_load_server_yaml(self, tmp_path: Path):
        """Test loading from settings/{server_name}.yaml."""
        os.chdir(tmp_path)
        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()

        # Create server-specific YAML
        server_yaml = settings_dir / "test-server.yaml"
        server_yaml.write_text(
            yaml.safe_dump(
                {
                    "cache_root": "/custom/cache",
                    "health_ttl_seconds": 120.0,
                    "log_level": "DEBUG",
                }
            )
        )

        settings = MCPServerSettings.load("test-server")

        # Should load from YAML
        assert settings.server_name == "test-server"
        assert settings.cache_root == Path("/custom/cache")
        assert settings.health_ttl_seconds == 120.0
        assert settings.log_level == "DEBUG"

    def test_load_local_yaml_overrides_server_yaml(self, tmp_path: Path):
        """Test local.yaml overrides server.yaml."""
        os.chdir(tmp_path)
        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()

        # Create server YAML
        (settings_dir / "test-server.yaml").write_text(
            yaml.safe_dump({"log_level": "INFO", "health_ttl_seconds": 60.0})
        )

        # Create local YAML (higher priority)
        (settings_dir / "local.yaml").write_text(yaml.safe_dump({"log_level": "DEBUG"}))

        settings = MCPServerSettings.load("test-server")

        # local.yaml should override server.yaml
        assert settings.log_level == "DEBUG"
        # But server.yaml values not overridden should remain
        assert settings.health_ttl_seconds == 60.0

    def test_load_env_vars_override_yaml(self, tmp_path: Path):
        """Test environment variables override YAML files."""
        os.chdir(tmp_path)
        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()

        # Create YAML with log_level
        (settings_dir / "test-server.yaml").write_text(
            yaml.safe_dump({"log_level": "INFO", "health_ttl_seconds": 60.0})
        )

        # Set env var (highest priority)
        os.environ["MCP_SERVER_LOG_LEVEL"] = "ERROR"
        os.environ["MCP_SERVER_HEALTH_TTL_SECONDS"] = "90.0"

        try:
            settings = MCPServerSettings.load("test-server")

            # Env vars should win
            assert settings.log_level == "ERROR"
            assert settings.health_ttl_seconds == 90.0
        finally:
            # Cleanup
            os.environ.pop("MCP_SERVER_LOG_LEVEL", None)
            os.environ.pop("MCP_SERVER_HEALTH_TTL_SECONDS", None)

    def test_load_explicit_config_path(self, tmp_path: Path):
        """Test explicit config_path has highest priority."""
        os.chdir(tmp_path)
        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()

        # Create multiple YAML files
        (settings_dir / "test-server.yaml").write_text(yaml.safe_dump({"log_level": "INFO"}))
        (settings_dir / "local.yaml").write_text(yaml.safe_dump({"log_level": "DEBUG"}))

        # Create explicit config
        custom_config = tmp_path / "custom.yaml"
        custom_config.write_text(yaml.safe_dump({"log_level": "WARNING"}))

        # Set env var too
        os.environ["MCP_SERVER_LOG_LEVEL"] = "ERROR"

        try:
            settings = MCPServerSettings.load("test-server", config_path=custom_config)

            # Explicit config should win (even over env vars)
            assert settings.log_level == "WARNING"
        finally:
            os.environ.pop("MCP_SERVER_LOG_LEVEL", None)

    def test_load_custom_env_prefix(self, tmp_path: Path):
        """Test custom environment variable prefix."""
        os.chdir(tmp_path)

        os.environ["CUSTOM_LOG_LEVEL"] = "DEBUG"

        try:
            settings = MCPServerSettings.load("test-server", env_prefix="CUSTOM")

            assert settings.log_level == "DEBUG"
        finally:
            os.environ.pop("CUSTOM_LOG_LEVEL", None)

    def test_load_path_expansion(self, tmp_path: Path):
        """Test Path type coercion from env vars."""
        os.chdir(tmp_path)

        os.environ["MCP_SERVER_CACHE_ROOT"] = str(tmp_path / "cache")

        try:
            settings = MCPServerSettings.load("test-server")

            assert settings.cache_root == tmp_path / "cache"
            assert isinstance(settings.cache_root, Path)
        finally:
            os.environ.pop("MCP_SERVER_CACHE_ROOT", None)

    def test_load_none_string_for_optional_path(self, tmp_path: Path):
        """Test empty string env var becomes None for optional Path."""
        os.chdir(tmp_path)

        os.environ["MCP_SERVER_LOG_FILE"] = ""

        try:
            settings = MCPServerSettings.load("test-server")

            assert settings.log_file is None
        finally:
            os.environ.pop("MCP_SERVER_LOG_FILE", None)

    def test_load_empty_yaml_files(self, tmp_path: Path):
        """Test loading when YAML files are empty."""
        os.chdir(tmp_path)
        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()

        # Create empty YAML files
        (settings_dir / "test-server.yaml").write_text("")
        (settings_dir / "local.yaml").write_text("")

        settings = MCPServerSettings.load("test-server")

        # Should still work with defaults
        assert settings.server_name == "test-server"
        assert settings.cache_root == Path(".oneiric_cache")

    def test_load_malformed_yaml_graceful_handling(self, tmp_path: Path):
        """Test malformed YAML is handled gracefully."""
        os.chdir(tmp_path)
        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()

        # Create malformed YAML
        (settings_dir / "test-server.yaml").write_text("{invalid yaml content")

        # Should raise YAML parsing error
        with pytest.raises(yaml.YAMLError):
            MCPServerSettings.load("test-server")


class TestMCPServerSettingsLayeredConfig:
    """Test complete layered configuration priority."""

    def test_full_config_hierarchy(self, tmp_path: Path):
        """Test complete configuration hierarchy (5 layers)."""
        os.chdir(tmp_path)
        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()

        # Layer 1: Server defaults (settings/test-server.yaml)
        (settings_dir / "test-server.yaml").write_text(
            yaml.safe_dump(
                {
                    "log_level": "INFO",
                    "health_ttl_seconds": 60.0,
                    "cache_root": "/server/cache",
                }
            )
        )

        # Layer 2: Local overrides (settings/local.yaml)
        (settings_dir / "local.yaml").write_text(
            yaml.safe_dump({"log_level": "DEBUG", "health_ttl_seconds": 90.0})
        )

        # Layer 3: Environment variables
        os.environ["MCP_SERVER_LOG_LEVEL"] = "WARNING"

        # Layer 4: Explicit config
        custom_config = tmp_path / "custom.yaml"
        custom_config.write_text(yaml.safe_dump({"health_ttl_seconds": 120.0}))

        try:
            settings = MCPServerSettings.load("test-server", config_path=custom_config)

            # Verify priority (highest to lowest):
            # - explicit config wins for health_ttl_seconds (120.0)
            # - env var wins for log_level (WARNING)
            # - server yaml wins for cache_root (/server/cache)
            assert settings.health_ttl_seconds == 120.0
            assert settings.log_level == "WARNING"
            assert settings.cache_root == Path("/server/cache")
        finally:
            os.environ.pop("MCP_SERVER_LOG_LEVEL", None)
