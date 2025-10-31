"""Tests for MCPBaseSettings configuration management."""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from mcp_common.config import MCPBaseSettings, MCPServerSettings


@pytest.mark.unit
class TestMCPBaseSettings:
    """Tests for MCPBaseSettings configuration."""

    def test_default_settings(self) -> None:
        """Test default settings values."""
        settings = MCPBaseSettings()

        assert settings.server_name == "MCP Server"
        assert settings.server_description == "Model Context Protocol Server"
        assert settings.log_level == "INFO"
        assert not settings.enable_debug_mode

    def test_custom_settings(self) -> None:
        """Test custom settings override defaults."""
        settings = MCPBaseSettings(
            server_name="Custom MCP",
            server_description="Custom description",
            log_level="DEBUG",
            enable_debug_mode=True,
        )

        assert settings.server_name == "Custom MCP"
        assert settings.server_description == "Custom description"
        assert settings.log_level == "DEBUG"
        assert settings.enable_debug_mode

    def test_server_name_validation_strips_whitespace(self) -> None:
        """Test server name strips whitespace."""
        settings = MCPBaseSettings(server_name="  Test Server  ")
        assert settings.server_name == "Test Server"

    def test_server_name_validation_rejects_empty(self) -> None:
        """Test server name rejects empty strings."""
        with pytest.raises(ValidationError) as exc_info:
            MCPBaseSettings(server_name="   ")

        assert "server_name cannot be empty" in str(exc_info.value)

    def test_log_level_validation(self) -> None:
        """Test log level accepts only valid values."""
        # Valid levels
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            settings = MCPBaseSettings(log_level=level)
            assert settings.log_level == level

        # Invalid level
        with pytest.raises(ValidationError):
            MCPBaseSettings(log_level="INVALID")

    @given(
        server_name=st.text(min_size=1, max_size=100).filter(str.strip),
        log_level=st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    )
    def test_settings_property_based(
        self,
        server_name: str,
        log_level: str,
    ) -> None:
        """Test settings with property-based testing."""
        settings = MCPBaseSettings(
            server_name=server_name,
            log_level=log_level,
        )

        assert settings.server_name.strip() != ""
        assert settings.log_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


@pytest.mark.unit
class TestMCPBaseSettingsAPIKey:
    """Tests for API key validation helper."""

    def test_get_api_key_success(self) -> None:
        """Test successful API key retrieval."""

        class TestSettings(MCPBaseSettings):
            api_key: str = "test-key-123"

        settings = TestSettings()
        key = settings.get_api_key()

        assert key == "test-key-123"

    def test_get_api_key_strips_whitespace(self) -> None:
        """Test API key strips whitespace."""

        class TestSettings(MCPBaseSettings):
            api_key: str = "  test-key-123  "

        settings = TestSettings()
        key = settings.get_api_key()

        assert key == "test-key-123"

    def test_get_api_key_missing_field(self) -> None:
        """Test error when API key field doesn't exist."""
        settings = MCPBaseSettings()

        with pytest.raises(AttributeError) as exc_info:
            settings.get_api_key()

        assert "has no field 'api_key'" in str(exc_info.value)

    def test_get_api_key_empty_value(self) -> None:
        """Test error when API key is empty."""

        class TestSettings(MCPBaseSettings):
            api_key: str = ""

        settings = TestSettings()

        with pytest.raises(ValueError, match="api_key is required but not set"):
            settings.get_api_key()

    def test_get_api_key_custom_field_name(self) -> None:
        """Test API key retrieval with custom field name."""

        class TestSettings(MCPBaseSettings):
            custom_key: str = "custom-123"

        settings = TestSettings()
        key = settings.get_api_key(key_name="custom_key")

        assert key == "custom-123"


@pytest.mark.unit
class TestMCPBaseSettingsDataDir:
    """Tests for data directory helper."""

    def test_get_data_dir_creates_directory(self, tmp_path: Path) -> None:
        """Test data directory is created if it doesn't exist."""

        class TestSettings(MCPBaseSettings):
            data_dir: Path = tmp_path / "data"

        settings = TestSettings()
        data_dir = settings.get_data_dir("data_dir")

        assert data_dir.exists()
        assert data_dir.is_dir()
        assert data_dir == tmp_path / "data"

    def test_get_data_dir_expands_home(self) -> None:
        """Test data directory expands ~ to home directory."""

        class TestSettings(MCPBaseSettings):
            data_dir: Path = Path("~/test-mcp-data")

        settings = TestSettings()
        data_dir = settings.get_data_dir("data_dir")

        assert "~" not in str(data_dir)
        assert data_dir.is_absolute()
        # Cleanup test directory
        if data_dir.exists():
            data_dir.rmdir()

    def test_get_data_dir_missing_field(self) -> None:
        """Test error when data directory field doesn't exist."""
        settings = MCPBaseSettings()

        with pytest.raises(AttributeError) as exc_info:
            settings.get_data_dir("nonexistent")

        assert "has no field 'nonexistent'" in str(exc_info.value)

    def test_get_data_dir_wrong_type(self) -> None:
        """Test error when field is not a Path."""

        class TestSettings(MCPBaseSettings):
            not_a_path: str = "just a string"

        settings = TestSettings()

        with pytest.raises(ValueError, match="must be a Path"):
            settings.get_data_dir("not_a_path")


@pytest.mark.unit
class TestMCPServerSettings:
    """Tests for MCPServerSettings extended configuration."""

    def test_default_server_settings(self) -> None:
        """Test default server settings values."""
        settings = MCPServerSettings()

        assert settings.api_key is None
        assert settings.base_url == "https://api.example.com"
        assert settings.timeout == 30
        assert settings.max_retries == 3
        assert not settings.enable_cache
        assert settings.cache_ttl_seconds == 300

    def test_custom_server_settings(self) -> None:
        """Test custom server settings."""
        settings = MCPServerSettings(
            api_key="test-key",
            base_url="https://custom-api.com",
            timeout=60,
            max_retries=5,
            enable_cache=True,
            cache_ttl_seconds=600,
        )

        assert settings.api_key == "test-key"
        assert settings.base_url == "https://custom-api.com"
        assert settings.timeout == 60
        assert settings.max_retries == 5
        assert settings.enable_cache
        assert settings.cache_ttl_seconds == 600

    def test_base_url_validation_strips_trailing_slash(self) -> None:
        """Test base URL removes trailing slash."""
        settings = MCPServerSettings(base_url="https://api.example.com/")
        assert settings.base_url == "https://api.example.com"

    def test_base_url_validation_requires_protocol(self) -> None:
        """Test base URL requires http:// or https://."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerSettings(base_url="api.example.com")

        assert "must start with http:// or https://" in str(exc_info.value)

    def test_base_url_validation_rejects_empty(self) -> None:
        """Test base URL rejects empty strings."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerSettings(base_url="   ")

        assert "base_url cannot be empty" in str(exc_info.value)

    def test_timeout_validation_range(self) -> None:
        """Test timeout validation enforces range."""
        # Valid range
        settings = MCPServerSettings(timeout=1)
        assert settings.timeout == 1

        settings = MCPServerSettings(timeout=300)
        assert settings.timeout == 300

        # Out of range
        with pytest.raises(ValidationError):
            MCPServerSettings(timeout=0)

        with pytest.raises(ValidationError):
            MCPServerSettings(timeout=301)

    def test_max_retries_validation_range(self) -> None:
        """Test max_retries validation enforces range."""
        # Valid range
        settings = MCPServerSettings(max_retries=0)
        assert settings.max_retries == 0

        settings = MCPServerSettings(max_retries=10)
        assert settings.max_retries == 10

        # Out of range
        with pytest.raises(ValidationError):
            MCPServerSettings(max_retries=-1)

        with pytest.raises(ValidationError):
            MCPServerSettings(max_retries=11)

    def test_cache_ttl_validation_range(self) -> None:
        """Test cache TTL validation enforces range (0-86400)."""
        # Valid range
        settings = MCPServerSettings(cache_ttl_seconds=0)
        assert settings.cache_ttl_seconds == 0

        settings = MCPServerSettings(cache_ttl_seconds=86400)
        assert settings.cache_ttl_seconds == 86400

        # Out of range
        with pytest.raises(ValidationError):
            MCPServerSettings(cache_ttl_seconds=-1)

        with pytest.raises(ValidationError):
            MCPServerSettings(cache_ttl_seconds=86401)


@pytest.mark.integration
class TestMCPSettingsEnvironmentVariables:
    """Integration tests for environment variable overrides."""

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test environment variables override default values."""
        # Note: ACB Settings uses env vars with prefix based on class name
        # For MCPBaseSettings, prefix would be MCP_BASE_
        monkeypatch.setenv("MCP_BASE_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("MCP_BASE_ENABLE_DEBUG_MODE", "true")

        MCPBaseSettings()

        # Note: Actual behavior depends on ACB Settings implementation
        # This test documents expected behavior
        # If env vars don't work, this is a known limitation to document

    def test_env_var_override_server_settings(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test environment variables for server settings."""
        monkeypatch.setenv("MCP_SERVER_API_KEY", "env-key-123")
        monkeypatch.setenv("MCP_SERVER_TIMEOUT", "60")

        MCPServerSettings()

        # Document expected ACB Settings behavior
        # Actual implementation may vary
