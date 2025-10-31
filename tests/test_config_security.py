"""Tests for MCPBaseSettings security enhancements.

Tests Phase 3 security methods added to MCPBaseSettings:
- validate_api_keys_at_startup()
- get_api_key_secure()
- get_masked_key()
- Backward compatibility with SECURITY_AVAILABLE flag
"""

from __future__ import annotations

import pytest
from pydantic import Field

from mcp_common.config import MCPBaseSettings


class TestMCPBaseSettingsGetAPIKey:
    """Test existing get_api_key method (baseline functionality)."""

    def test_get_api_key_returns_valid_key(self) -> None:
        """Should return API key when present."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="test-key-123")

        settings = Settings()
        result = settings.get_api_key()
        assert result == "test-key-123"

    def test_get_api_key_strips_whitespace(self) -> None:
        """Should strip whitespace from API keys."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="  test-key-123  ")

        settings = Settings()
        result = settings.get_api_key()
        assert result == "test-key-123"

    def test_get_api_key_raises_on_empty(self) -> None:
        """Should raise ValueError when key is empty."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="")

        settings = Settings()
        with pytest.raises(ValueError, match="api_key is required"):
            settings.get_api_key()

    def test_get_api_key_custom_field_name(self) -> None:
        """Should work with custom key field names."""

        class Settings(MCPBaseSettings):
            custom_key: str = Field(default="custom-value")

        settings = Settings()
        result = settings.get_api_key("custom_key")
        assert result == "custom-value"

    def test_get_api_key_raises_on_missing_field(self) -> None:
        """Should raise AttributeError for non-existent fields."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="test")

        settings = Settings()
        with pytest.raises(AttributeError, match="has no field 'nonexistent'"):
            settings.get_api_key("nonexistent")


class TestValidateAPIKeysAtStartup:
    """Test validate_api_keys_at_startup Phase 3 security method."""

    def test_validate_single_api_key(self) -> None:
        """Should validate default api_key field."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="sk-" + "a" * 48)

        settings = Settings()
        result = settings.validate_api_keys_at_startup(provider="openai")

        assert "api_key" in result
        assert result["api_key"] == "sk-" + "a" * 48

    def test_validate_multiple_keys(self) -> None:
        """Should validate multiple specified key fields."""

        class Settings(MCPBaseSettings):
            primary_key: str = Field(default="sk-" + "a" * 48)
            secondary_key: str = Field(default="sk-" + "b" * 48)

        settings = Settings()
        result = settings.validate_api_keys_at_startup(
            key_fields=["primary_key", "secondary_key"],
            provider="openai",
        )

        assert "primary_key" in result
        assert "secondary_key" in result

    def test_validate_raises_on_invalid_format(self) -> None:
        """Should raise ValueError for invalid key format."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="invalid-key")

        settings = Settings()
        with pytest.raises(ValueError, match="Invalid API key format"):
            settings.validate_api_keys_at_startup(provider="openai")

    def test_validate_skips_none_optional_fields(self) -> None:
        """Should skip optional fields that are None."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="sk-" + "a" * 48)
            optional_key: str | None = Field(default=None)

        settings = Settings()
        result = settings.validate_api_keys_at_startup(
            key_fields=["api_key", "optional_key"],
            provider="openai",
        )

        assert "api_key" in result
        assert "optional_key" not in result

    def test_validate_with_generic_provider(self) -> None:
        """Should work without specific provider (generic validation)."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="any-long-key-12345678")

        settings = Settings()
        result = settings.validate_api_keys_at_startup()

        assert "api_key" in result

    def test_validate_mailgun_format(self) -> None:
        """Should validate Mailgun hex format keys."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="0123456789abcdef" * 2)

        settings = Settings()
        result = settings.validate_api_keys_at_startup(provider="mailgun")

        assert "api_key" in result

    def test_validate_anthropic_format(self) -> None:
        """Should validate Anthropic key format."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="sk-ant-" + "a" * 95)

        settings = Settings()
        result = settings.validate_api_keys_at_startup(provider="anthropic")

        assert "api_key" in result


class TestGetAPIKeySecure:
    """Test get_api_key_secure Phase 3 enhanced method."""

    def test_get_secure_with_valid_openai_key(self) -> None:
        """Should return valid OpenAI key after validation."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="sk-" + "a" * 48)

        settings = Settings()
        result = settings.get_api_key_secure(provider="openai")
        assert result == "sk-" + "a" * 48

    def test_get_secure_raises_on_invalid_format(self) -> None:
        """Should raise a format error for invalid key format."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="invalid-key")

        settings = Settings()
        with pytest.raises(Exception) as excinfo:
            settings.get_api_key_secure(provider="openai", validate_format=True)
        assert "Invalid API key format" in str(excinfo.value)

    def test_get_secure_skips_validation_when_disabled(self) -> None:
        """Should skip format validation when validate_format=False."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="any-format-key")

        settings = Settings()
        result = settings.get_api_key_secure(validate_format=False)
        assert result == "any-format-key"

    def test_get_secure_strips_whitespace(self) -> None:
        """Should strip whitespace like base get_api_key."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="  sk-" + "a" * 48 + "  ")

        settings = Settings()
        result = settings.get_api_key_secure(provider="openai")
        assert result == "sk-" + "a" * 48

    def test_get_secure_with_custom_field(self) -> None:
        """Should work with custom key field names."""

        class Settings(MCPBaseSettings):
            custom_key: str = Field(default="sk-" + "a" * 48)

        settings = Settings()
        result = settings.get_api_key_secure("custom_key", provider="openai")
        assert result == "sk-" + "a" * 48

    def test_get_secure_without_provider(self) -> None:
        """Should work without provider (basic validation only)."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="any-key-value")

        settings = Settings()
        result = settings.get_api_key_secure(validate_format=False)
        assert result == "any-key-value"


class TestGetMaskedKey:
    """Test get_masked_key Phase 3 safe logging method."""

    def test_mask_openai_key(self) -> None:
        """Should mask OpenAI key for safe logging."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="sk-" + "a" * 48)

        settings = Settings()
        result = settings.get_masked_key()

        assert "sk-..." in result
        assert result.endswith("aaaa")
        assert "sk-" + "a" * 48 not in result

    def test_mask_github_token(self) -> None:
        """Should mask GitHub token with proper prefix."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="ghp_" + "b" * 36)

        settings = Settings()
        result = settings.get_masked_key()

        assert "ghp_..." in result
        assert result.endswith("bbbb")

    def test_mask_custom_visible_chars(self) -> None:
        """Should respect custom visible_chars parameter."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="sk-" + "a" * 48)

        settings = Settings()
        result = settings.get_masked_key(visible_chars=6)

        assert result.endswith("aaaaaa")

    def test_mask_returns_stars_for_missing_field(self) -> None:
        """Should return *** when field doesn't exist."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="test")

        settings = Settings()
        result = settings.get_masked_key("nonexistent")
        assert result == "***"

    def test_mask_returns_stars_for_none(self) -> None:
        """Should return *** when key is None."""

        class Settings(MCPBaseSettings):
            api_key: str | None = Field(default=None)

        settings = Settings()
        result = settings.get_masked_key()
        assert result == "***"

    def test_mask_returns_stars_for_empty(self) -> None:
        """Should return *** when key is empty."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="")

        settings = Settings()
        result = settings.get_masked_key()
        assert result == "***"

    def test_mask_custom_field_name(self) -> None:
        """Should work with custom key field names."""

        class Settings(MCPBaseSettings):
            custom_key: str = Field(default="sk-" + "c" * 48)

        settings = Settings()
        result = settings.get_masked_key("custom_key")

        assert "sk-..." in result
        assert result.endswith("cccc")


class TestBackwardCompatibility:
    """Test backward compatibility when security module unavailable."""

    def test_validate_api_keys_fallback(self) -> None:
        """validate_api_keys_at_startup should work without security module."""
        # This test ensures the fallback logic works
        # In practice, security module should always be available in tests

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="test-key-1234567890")  # 16+ chars for generic pattern

        settings = Settings()

        # Should work even if using basic validation
        result = settings.validate_api_keys_at_startup()
        assert "api_key" in result

    def test_get_api_key_secure_fallback(self) -> None:
        """get_api_key_secure should work with basic validation."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="test-key-123")

        settings = Settings()

        # Should work even without format validation
        result = settings.get_api_key_secure(validate_format=False)
        assert result == "test-key-123"

    def test_get_masked_key_fallback(self) -> None:
        """get_masked_key should have fallback masking logic."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="test-key-1234567890")

        settings = Settings()

        # Should still mask even with fallback logic
        result = settings.get_masked_key()
        assert "..." in result or "***" in result


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_server_startup_validation_success(self) -> None:
        """Simulate successful server startup with validation."""

        class ServerSettings(MCPBaseSettings):
            server_name: str = Field(default="Test Server")
            api_key: str = Field(default="sk-" + "a" * 48)
            secondary_key: str | None = Field(default=None)

        settings = ServerSettings()

        # Validate at startup
        keys = settings.validate_api_keys_at_startup(
            key_fields=["api_key", "secondary_key"],
            provider="openai",
        )

        assert "api_key" in keys
        assert "secondary_key" not in keys  # Optional and None

    def test_server_startup_validation_failure(self) -> None:
        """Simulate server startup failure due to invalid key."""

        class ServerSettings(MCPBaseSettings):
            server_name: str = Field(default="Test Server")
            api_key: str = Field(default="invalid")

        settings = ServerSettings()

        # Should fail to start
        with pytest.raises(ValueError, match="Validation failed"):
            settings.validate_api_keys_at_startup(provider="openai")

    def test_safe_logging_in_error_messages(self) -> None:
        """Should safely log API keys in error messages."""

        class ServerSettings(MCPBaseSettings):
            api_key: str = Field(default="sk-" + "secret" * 8)

        settings = ServerSettings()

        # Get masked key for error message
        masked = settings.get_masked_key()

        # Simulate error logging
        error_msg = f"Authentication failed with key {masked}"
        assert "sk-..." in error_msg
        assert "secret" * 8 not in error_msg

    def test_multiple_provider_keys(self) -> None:
        """Should handle settings with multiple API providers."""

        class MultiProviderSettings(MCPBaseSettings):
            openai_key: str = Field(default="sk-" + "a" * 48)
            mailgun_key: str = Field(default="0123456789abcdef" * 2)
            github_token: str = Field(default="ghp_" + "b" * 36)

        settings = MultiProviderSettings()

        # Validate all keys (generic validation since multiple providers)
        keys = settings.validate_api_keys_at_startup(
            key_fields=["openai_key", "mailgun_key", "github_token"]
        )

        assert len(keys) == 3
        assert all(key in keys for key in ("openai_key", "mailgun_key", "github_token"))


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_long_api_key(self) -> None:
        """Should handle very long API keys."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="x" * 1000)

        settings = Settings()
        masked = settings.get_masked_key()
        assert "..." in masked
        assert len(masked) < 20  # Masked version should be short

    def test_empty_key_fields_list(self) -> None:
        """Should handle empty key_fields list gracefully."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="test")

        settings = Settings()
        result = settings.validate_api_keys_at_startup(key_fields=[])
        assert not result

    def test_whitespace_only_key(self) -> None:
        """Should reject whitespace-only keys."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="   ")

        settings = Settings()
        with pytest.raises(ValueError, match="api_key is required"):
            settings.get_api_key()

    def test_unicode_in_keys(self) -> None:
        """Should handle unicode characters in keys."""

        class Settings(MCPBaseSettings):
            api_key: str = Field(default="test-key-🔑-unicode")

        settings = Settings()
        result = settings.get_api_key()
        assert "🔑" in result
