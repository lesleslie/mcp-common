"""Tests for API key validation utilities.

Tests comprehensive API key validation with provider-specific patterns,
startup validation, and secure key masking.
"""

from __future__ import annotations

import builtins
import importlib
import re

import pytest
from pydantic import BaseModel, Field

from mcp_common.exceptions import APIKeyFormatError, APIKeyMissingError
from mcp_common.security import api_keys as api_keys_module
from mcp_common.security.api_keys import (
    API_KEY_PATTERNS,
    APIKeyPattern,
    APIKeyValidator,
    create_api_key_validator,
    validate_api_key_format,
    validate_api_key_startup,
)


class TestAPIKeyPattern:
    """Test APIKeyPattern dataclass functionality."""

    def test_openai_pattern_matches_valid_key(self) -> None:
        """OpenAI pattern should match valid 'sk-' + 48 chars format."""
        pattern = API_KEY_PATTERNS["openai"]
        valid_key = "sk-" + "a" * 48
        assert pattern.matches(valid_key)

    def test_openai_pattern_rejects_invalid_key(self) -> None:
        """OpenAI pattern should reject keys with wrong format."""
        pattern = API_KEY_PATTERNS["openai"]
        assert not pattern.matches("sk-tooshort")
        assert not pattern.matches("wrong-prefix-" + "a" * 48)
        assert not pattern.matches("sk-" + "a" * 47)  # Too short

    def test_anthropic_pattern_matches_valid_key(self) -> None:
        """Anthropic pattern should match valid 'sk-ant-' + 95+ chars."""
        pattern = API_KEY_PATTERNS["anthropic"]
        valid_key = "sk-ant-" + "a" * 95
        assert pattern.matches(valid_key)
        assert pattern.matches("sk-ant-" + "a" * 100)  # Longer is ok

    def test_mailgun_pattern_matches_hex_string(self) -> None:
        """Mailgun pattern should match 32-character hex strings."""
        pattern = API_KEY_PATTERNS["mailgun"]
        valid_key = "a" * 32  # All lowercase hex
        assert pattern.matches(valid_key)
        assert pattern.matches("0123456789abcdef" * 2)

    def test_mailgun_pattern_rejects_non_hex(self) -> None:
        """Mailgun pattern should reject non-hex characters."""
        pattern = API_KEY_PATTERNS["mailgun"]
        assert not pattern.matches("g" * 32)  # 'g' is not hex
        assert not pattern.matches("sk-" + "a" * 30)

    def test_github_pattern_matches_valid_tokens(self) -> None:
        """GitHub pattern should match 'ghp_' and 'ghs_' tokens."""
        pattern = API_KEY_PATTERNS["github"]
        assert pattern.matches("ghp_" + "a" * 36)
        assert pattern.matches("ghs_" + "a" * 40)

    def test_gemini_pattern_matches_valid_keys(self) -> None:
        """Gemini pattern should match 'AIza' prefix with 35 chars."""
        pattern = API_KEY_PATTERNS["gemini"]
        assert pattern.matches("AIza" + "a" * 35)
        assert pattern.matches("AIzaSyD1234567890abcdefghijklmnopqrstuv")
        assert not pattern.matches("AIza" + "a" * 30)  # Too short
        assert not pattern.matches("Bza" + "a" * 35)  # Wrong prefix

    def test_generic_pattern_accepts_any_16plus_chars(self) -> None:
        """Generic pattern should accept any string ≥16 characters."""
        pattern = API_KEY_PATTERNS["generic"]
        assert pattern.matches("a" * 16)
        assert pattern.matches("any-format-here-1234567890")
        assert not pattern.matches("too-short")


class TestAPIKeyValidator:
    """Test APIKeyValidator class with various providers."""

    def test_validator_with_openai_provider(self) -> None:
        """Validator should use OpenAI pattern when provider='openai'."""
        validator = APIKeyValidator(provider="openai")
        valid_key = "sk-" + "a" * 48

        assert validator.validate(valid_key, raise_on_invalid=False)
        assert validator.validate(valid_key, raise_on_invalid=True)

    def test_validator_rejects_invalid_openai_key(self) -> None:
        """Validator should reject invalid OpenAI key format."""
        validator = APIKeyValidator(provider="openai")
        invalid_key = "sk-tooshort"

        assert not validator.validate(invalid_key, raise_on_invalid=False)

        with pytest.raises(
            APIKeyFormatError, match="Invalid API key format for OpenAI"
        ) as exc_info:
            validator.validate(invalid_key, raise_on_invalid=True)

        # Verify exception has rich context
        assert exc_info.value.provider == "openai"
        assert exc_info.value.expected_format is not None
        assert exc_info.value.example is not None

    def test_validator_with_anthropic_provider(self) -> None:
        """Validator should use Anthropic pattern when provider='anthropic'."""
        validator = APIKeyValidator(provider="anthropic")
        valid_key = "sk-ant-" + "a" * 95

        assert validator.validate(valid_key, raise_on_invalid=False)

    def test_validator_with_mailgun_provider(self) -> None:
        """Validator should use Mailgun hex pattern."""
        validator = APIKeyValidator(provider="mailgun")
        valid_key = "0123456789abcdef" * 2

        assert validator.validate(valid_key, raise_on_invalid=False)

    def test_validator_with_github_provider(self) -> None:
        """Validator should use GitHub token pattern."""
        validator = APIKeyValidator(provider="github")
        valid_key = "ghp_" + "a" * 36

        assert validator.validate(valid_key, raise_on_invalid=False)

    def test_validator_with_gemini_provider(self) -> None:
        """Validator should use Gemini API key pattern."""
        validator = APIKeyValidator(provider="gemini")
        valid_key = "AIza" + "a" * 35

        assert validator.validate(valid_key, raise_on_invalid=False)
        assert not validator.validate("invalid-gemini-key", raise_on_invalid=False)

    def test_validator_with_custom_min_length(self) -> None:
        """Validator should use custom min_length for generic validation."""
        validator = APIKeyValidator(min_length=20)

        assert validator.validate("a" * 20, raise_on_invalid=False)
        assert not validator.validate("a" * 19, raise_on_invalid=False)

    def test_validator_rejects_none_key(self) -> None:
        """Validator should reject None key."""
        validator = APIKeyValidator(provider="openai")

        assert not validator.validate(None, raise_on_invalid=False)

        with pytest.raises(APIKeyMissingError, match="API key is required but not set") as exc_info:
            validator.validate(None, raise_on_invalid=True)

        # Verify exception has provider context
        assert exc_info.value.provider == "openai"

    def test_validator_rejects_empty_string(self) -> None:
        """Validator should reject empty string."""
        validator = APIKeyValidator(provider="openai")

        assert not validator.validate("", raise_on_invalid=False)
        assert not validator.validate("   ", raise_on_invalid=False)

    def test_validator_missing_key_fallback_valueerror(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Validator should raise ValueError when specific exceptions are disabled."""
        monkeypatch.setattr(api_keys_module, "SPECIFIC_EXCEPTIONS_AVAILABLE", False)
        validator = APIKeyValidator(provider="openai")

        with pytest.raises(ValueError, match="API key is required but not set"):
            validator.validate(None, raise_on_invalid=True)

    def test_validator_invalid_format_fallback_valueerror(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Validator should raise ValueError when specific exceptions are disabled."""
        monkeypatch.setattr(api_keys_module, "SPECIFIC_EXCEPTIONS_AVAILABLE", False)
        validator = APIKeyValidator(provider="openai")

        with pytest.raises(ValueError, match="Invalid API key format"):
            validator.validate("invalid", raise_on_invalid=True)

    def test_validator_strips_whitespace(self) -> None:
        """Validator should strip whitespace before validation."""
        validator = APIKeyValidator(provider="openai")
        valid_key = "sk-" + "a" * 48

        assert validator.validate(f"  {valid_key}  ", raise_on_invalid=True)

    def test_mask_key_with_standard_prefix(self) -> None:
        """mask_key should preserve common prefixes and mask the rest."""
        assert APIKeyValidator.mask_key("sk-abc123def456", visible_chars=4) == "sk-...f456"
        assert APIKeyValidator.mask_key("ghp_abc123def456", visible_chars=4) == "ghp_...f456"
        assert APIKeyValidator.mask_key("ghs_abc123def456", visible_chars=4) == "ghs_...f456"

    def test_mask_key_without_prefix(self) -> None:
        """mask_key should mask keys without recognized prefix."""
        result = APIKeyValidator.mask_key("abc123def456", visible_chars=4)
        assert result == "...f456"

    def test_mask_key_too_short(self) -> None:
        """mask_key should return *** for very short keys."""
        assert APIKeyValidator.mask_key("abc", visible_chars=4) == "***"
        assert APIKeyValidator.mask_key("", visible_chars=4) == "***"

    def test_mask_key_custom_visible_chars(self) -> None:
        """mask_key should respect custom visible_chars parameter."""
        key = "sk-abc123def456xyz"
        assert APIKeyValidator.mask_key(key, visible_chars=6) == "sk-...456xyz"
        assert APIKeyValidator.mask_key(key, visible_chars=8) == "sk-...ef456xyz"


class TestValidateAPIKeyFormat:
    """Test validate_api_key_format convenience function."""

    def test_validate_with_openai_provider(self) -> None:
        """Function should validate and return OpenAI key."""
        valid_key = "sk-" + "a" * 48
        result = validate_api_key_format(valid_key, provider="openai")
        assert result == valid_key

    def test_validate_rejects_invalid_format(self) -> None:
        """Function should raise APIKeyFormatError for invalid format."""
        with pytest.raises(APIKeyFormatError, match="Invalid API key format") as exc_info:
            validate_api_key_format("invalid", provider="openai")

        # Verify exception has rich context
        assert exc_info.value.provider == "openai"
        assert exc_info.value.expected_format is not None

    def test_validate_strips_whitespace(self) -> None:
        """Function should strip whitespace from valid keys."""
        valid_key = "sk-" + "a" * 48
        result = validate_api_key_format(f"  {valid_key}  ", provider="openai")
        assert result == valid_key

    def test_validate_with_custom_pattern(self) -> None:
        """Function should accept custom APIKeyPattern."""
        custom_pattern = APIKeyPattern(
            name="Custom",
            pattern=r"^custom-[0-9]{10}$",
            description="Custom pattern",
            example="custom-1234567890",
        )

        valid_key = "custom-1234567890"
        result = validate_api_key_format(valid_key, pattern=custom_pattern)
        assert result == valid_key

    def test_validate_rejects_none(self) -> None:
        """Function should raise APIKeyMissingError for None."""
        with pytest.raises(APIKeyMissingError, match="API key is required") as exc_info:
            validate_api_key_format(None, provider="openai")

        # Verify exception has provider context
        assert exc_info.value.provider == "openai"


class TestValidateAPIKeyStartup:
    """Test validate_api_key_startup for comprehensive server initialization checks."""

    def test_validate_single_api_key_field(self) -> None:
        """Should validate single api_key field by default."""

        class Settings(BaseModel):
            api_key: str = Field(default="sk-" + "a" * 48)

        settings = Settings()
        result = validate_api_key_startup(settings, provider="openai")

        assert "api_key" in result
        assert result["api_key"] == settings.api_key

    def test_validate_multiple_key_fields(self) -> None:
        """Should validate multiple specified key fields."""

        class Settings(BaseModel):
            primary_key: str = Field(default="sk-" + "a" * 48)
            secondary_key: str = Field(default="sk-" + "b" * 48)

        settings = Settings()
        result = validate_api_key_startup(
            settings,
            key_fields=["primary_key", "secondary_key"],
            provider="openai",
        )

        assert "primary_key" in result
        assert "secondary_key" in result

    def test_validate_skips_missing_fields(self) -> None:
        """Should skip fields that don't exist on settings."""
        from pydantic import BaseModel, Field

        class Settings(BaseModel):
            api_key: str = Field(default="sk-" + "a" * 48)

        settings = Settings()
        result = validate_api_key_startup(
            settings,
            key_fields=["api_key", "nonexistent_key"],
            provider="openai",
        )

        assert "api_key" in result
        assert "nonexistent_key" not in result

    def test_validate_skips_none_optional_fields(self) -> None:
        """Should skip optional fields that are None."""
        from pydantic import BaseModel, Field

        class Settings(BaseModel):
            api_key: str = Field(default="sk-" + "a" * 48)
            optional_key: str | None = Field(default=None)

        settings = Settings()
        result = validate_api_key_startup(
            settings,
            key_fields=["api_key", "optional_key"],
            provider="openai",
        )

        assert "api_key" in result
        assert "optional_key" not in result

    def test_validate_raises_on_invalid_key(self) -> None:
        """Should raise ValueError with field name for invalid keys."""
        from pydantic import BaseModel, Field

        class Settings(BaseModel):
            api_key: str = Field(default="invalid-key")

        settings = Settings()

        # Note: validate_api_key_startup wraps exceptions in ValueError with field context
        with pytest.raises(ValueError, match="Validation failed for 'api_key'"):
            validate_api_key_startup(settings, provider="openai")

    def test_validate_default_fields_strips_key(self) -> None:
        """Should strip keys when using default field list."""

        class Settings(BaseModel):
            api_key: str = Field(default="  " + "a" * 16 + "  ")

        settings = Settings()
        result = validate_api_key_startup(settings, provider="generic")

        assert result["api_key"] == "a" * 16


class TestCreateAPIKeyValidator:
    """Test create_api_key_validator factory for Pydantic validators."""

    def test_create_validator_for_openai(self) -> None:
        """Should create validator function for OpenAI keys."""
        validator_func = create_api_key_validator(provider="openai")

        valid_key = "sk-" + "a" * 48
        result = validator_func(valid_key)
        assert result == valid_key

    def test_created_validator_raises_on_invalid(self) -> None:
        """Created validator should raise APIKeyFormatError for invalid keys."""
        validator_func = create_api_key_validator(provider="openai")

        with pytest.raises(APIKeyFormatError):
            validator_func("invalid")

    def test_created_validator_strips_whitespace(self) -> None:
        """Created validator should strip whitespace."""
        validator_func = create_api_key_validator(provider="openai")

        valid_key = "sk-" + "a" * 48
        result = validator_func(f"  {valid_key}  ")
        assert result == valid_key


def test_specific_exceptions_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reload module with missing exceptions to hit fallback import path."""
    original_import = builtins.__import__

    def fake_import(name: str, *args, **kwargs):
        if name == "mcp_common.exceptions":
            msg = "boom"
            raise ImportError(msg)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    reloaded = importlib.reload(api_keys_module)

    assert reloaded.SPECIFIC_EXCEPTIONS_AVAILABLE is False

    monkeypatch.setattr(builtins, "__import__", original_import)
    importlib.reload(reloaded)


class TestProviderPatternCoverage:
    """Ensure all common providers have pattern definitions."""

    def test_all_expected_providers_exist(self) -> None:
        """All common API providers should have patterns defined."""
        expected_providers = {
            "openai",
            "anthropic",
            "mailgun",
            "github",
            "generic",
        }

        assert expected_providers.issubset(set(API_KEY_PATTERNS.keys()))

    def test_all_patterns_have_required_fields(self) -> None:
        """All patterns should have name, pattern, description, example."""
        for provider, pattern in API_KEY_PATTERNS.items():
            assert pattern.name, f"{provider} missing name"
            assert pattern.pattern, f"{provider} missing pattern"
            assert pattern.description, f"{provider} missing description"
            assert pattern.example, f"{provider} missing example"

    def test_patterns_have_valid_regex(self) -> None:
        """All patterns should have valid regex that compiles."""

        for provider, pattern in API_KEY_PATTERNS.items():
            try:
                re.compile(pattern.pattern)
            except re.error as e:
                pytest.fail(f"{provider} pattern is invalid regex: {e}")
