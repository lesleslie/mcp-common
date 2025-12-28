"""API key validation and security utilities.

Provides comprehensive API key validation for MCP servers:
- Format validation (pattern matching)
- Startup validation checks
- Secure key storage patterns
- Common API key format patterns

Phase 3.3 M4: Uses specific validation exceptions instead of generic ValueError
for fine-grained error handling and better error messages.
"""

from __future__ import annotations

import re
import typing as t
from dataclasses import dataclass

# Import specific validation exceptions (Phase 3.3 M4)
try:
    from mcp_common.exceptions import APIKeyFormatError, APIKeyMissingError

    SPECIFIC_EXCEPTIONS_AVAILABLE = True
except ImportError:
    SPECIFIC_EXCEPTIONS_AVAILABLE = False


@dataclass
class APIKeyPattern:
    """API key format pattern definition.

    Attributes:
        name: Human-readable name (e.g., "OpenAI", "Mailgun")
        pattern: Regex pattern for validation
        description: Description of the expected format
        example: Masked example (e.g., "sk-...abc123")
    """

    name: str
    pattern: str
    description: str
    example: str

    def matches(self, key: str) -> bool:
        """Check if key matches this pattern.

        Args:
            key: API key to validate

        Returns:
            True if key matches pattern
        """
        return bool(re.match(self.pattern, key))  # REGEX OK: API key pattern validation


# Common API key patterns for various services
API_KEY_PATTERNS: dict[str, APIKeyPattern] = {
    "openai": APIKeyPattern(
        name="OpenAI",
        pattern=r"^sk-[A-Za-z0-9]{48}$",
        description="OpenAI API keys start with 'sk-' followed by 48 alphanumeric characters",
        example="sk-...abc123",
    ),
    "anthropic": APIKeyPattern(
        name="Anthropic",
        pattern=r"^sk-ant-[A-Za-z0-9\-_]{95,}$",
        description="Anthropic API keys start with 'sk-ant-' followed by 95+ characters",
        example="sk-ant-...xyz789",
    ),
    "mailgun": APIKeyPattern(
        name="Mailgun",
        pattern=r"^[0-9a-f]{32}$",
        description="Mailgun API keys are 32-character hex strings",
        example="abc123...def456",
    ),
    "github": APIKeyPattern(
        name="GitHub",
        pattern=r"^gh[ps]_[A-Za-z0-9]{36,255}$",
        description="GitHub tokens start with 'ghp_' (personal) or 'ghs_' (server)",
        example="ghp_...abc123",
    ),
    "gemini": APIKeyPattern(
        name="Gemini",
        pattern=r"^AIza[0-9A-Za-z_-]{35}$",
        description="Google Gemini API keys start with 'AIza' followed by 35 characters",
        example="AIzaSyD1234567890abcdefghijklmnopqrstuv",
    ),
    "generic": APIKeyPattern(
        name="Generic",
        pattern=r"^.{16,}$",
        description="Generic API key with minimum 16 characters",
        example="any-format-16-chars-min",
    ),
}


class APIKeyValidator:
    """Comprehensive API key validator with pattern matching.

    Validates API keys against common patterns and provides
    detailed error messages for security issues.

    Example:
        >>> validator = APIKeyValidator(provider="openai")
        >>> validator.validate("sk-abc123...")  # Raises ValueError if invalid
        >>> validator.validate("sk-abc123...", raise_on_invalid=False)  # Returns bool
    """

    def __init__(
        self,
        provider: str | None = None,
        pattern: APIKeyPattern | None = None,
        min_length: int = 16,
    ) -> None:
        """Initialize API key validator.

        Args:
            provider: Known provider name (e.g., "openai", "mailgun")
            pattern: Custom APIKeyPattern to use instead of provider
            min_length: Minimum key length for generic validation
        """
        self.provider = provider
        self.min_length = min_length

        if pattern:
            self.pattern = pattern
        elif provider and provider in API_KEY_PATTERNS:
            self.pattern = API_KEY_PATTERNS[provider]
        else:
            # Use generic pattern with custom min_length
            self.pattern = APIKeyPattern(
                name="Generic",
                pattern=f"^.{{{min_length},}}$",
                description=f"Minimum {min_length} characters",
                example="x" * min_length,
            )

    def _validate_key_missing(self, key: str | None, raise_on_invalid: bool) -> bool | None:
        """Helper to validate if the key is missing."""
        if not key or not key.strip():
            if raise_on_invalid:
                msg = (
                    f"API key is required but not set. "
                    f"Expected format: {self.pattern.description}. "
                    f"Example: {self.pattern.example}"
                )
                if SPECIFIC_EXCEPTIONS_AVAILABLE:
                    raise APIKeyMissingError(
                        message=msg,
                        provider=self.provider,
                    )
                raise ValueError(msg)
            return False
        return None  # Key exists, continue with validation

    def _validate_pattern_match(self, key: str, raise_on_invalid: bool) -> bool:
        """Helper to validate if the key matches the pattern."""
        if not self.pattern.matches(key.strip()):
            if raise_on_invalid:
                msg = (
                    f"Invalid API key format for {self.pattern.name}. "
                    f"Expected: {self.pattern.description}. "
                    f"Example: {self.pattern.example}"
                )
                if SPECIFIC_EXCEPTIONS_AVAILABLE:
                    raise APIKeyFormatError(
                        message=msg,
                        provider=self.provider,
                        expected_format=self.pattern.description,
                        example=self.pattern.example,
                    )
                raise ValueError(msg)
            return False
        return True

    def validate(self, key: str | None, raise_on_invalid: bool = True) -> bool:
        """Validate API key format.

        Args:
            key: API key to validate
            raise_on_invalid: If True, raise specific validation exceptions

        Returns:
            True if valid, False if invalid (only when raise_on_invalid=False)

        Raises:
            APIKeyMissingError: If key is None or empty (when specific exceptions available)
            APIKeyFormatError: If key format is invalid (when specific exceptions available)
            ValueError: Falls back to ValueError if specific exceptions unavailable
        """
        # Check if key is None or empty
        result = self._validate_key_missing(key, raise_on_invalid)
        if result is not None:  # Key was either invalid or validation was raised
            return result

        # Check pattern match (key is non-None here; avoid assert for S101)
        key_str: str = t.cast("str", key)
        return self._validate_pattern_match(key_str, raise_on_invalid)

    @staticmethod
    def mask_key(key: str, visible_chars: int = 4) -> str:
        """Mask API key for safe logging.

        Args:
            key: API key to mask
            visible_chars: Number of characters to show at end

        Returns:
            Masked key string (e.g., "sk-...abc123")
        """
        if not key or len(key) <= visible_chars:
            return "***"

        # Show prefix if key has standard format
        prefix = ""
        if key.startswith("sk-"):
            prefix = "sk-"
        elif key.startswith("ghp_"):
            prefix = "ghp_"
        elif key.startswith("ghs_"):
            prefix = "ghs_"

        return f"{prefix}...{key[-visible_chars:]}"


def validate_api_key_format(
    key: str | None,
    provider: str | None = None,
    pattern: APIKeyPattern | None = None,
) -> str:
    """Validate API key format with provider-specific patterns.

    This is a convenience function for one-off validation.
    For repeated validation, use APIKeyValidator class.

    Args:
        key: API key to validate
        provider: Known provider name (e.g., "openai", "mailgun")
        pattern: Custom APIKeyPattern to use

    Returns:
        Validated and stripped key

    Raises:
        ValueError: If key is invalid

    Example:
        >>> key = validate_api_key_format(os.getenv("OPENAI_API_KEY"), provider="openai")
        >>> # Raises ValueError if key format is wrong
    """
    validator = APIKeyValidator(provider=provider, pattern=pattern)
    validator.validate(key, raise_on_invalid=True)
    return key.strip() if key else ""


def validate_api_key_startup(
    settings: t.Any,  # Can't import Settings without circular import
    key_fields: list[str] | None = None,
    provider: str | None = None,
) -> dict[str, str]:
    """Validate all API keys at server startup.

    Checks multiple API key fields in settings object and validates
    their formats. This should be called during server initialization
    to fail fast with clear error messages.

    Args:
        settings: Settings object with API key fields
        key_fields: List of field names to validate (default: ["api_key"])
        provider: Provider name for validation pattern

    Returns:
        Dict mapping field names to validated keys

    Raises:
        ValueError: If any key is invalid

    Example:
        >>> settings = MySettings()
        >>> keys = validate_api_key_startup(
        ...     settings,
        ...     key_fields=["openai_api_key", "anthropic_api_key"],
        ...     provider="openai"
        ... )
        >>> # Server will fail to start if keys are invalid
    """
    if key_fields is None:
        key_fields = ["api_key"]

    validated_keys: dict[str, str] = {}
    validator = APIKeyValidator(provider=provider)

    for field in key_fields:
        if not hasattr(settings, field):
            continue

        key = getattr(settings, field)
        if key is None:
            # Optional field, skip validation
            continue

        try:
            validator.validate(key, raise_on_invalid=True)
            validated_keys[field] = key.strip()
        except Exception as e:
            # Re-raise with field name for clarity
            # Catches both ValueError (fallback mode) and specific exceptions
            msg = f"Validation failed for '{field}': {e}"
            raise ValueError(msg) from e

    return validated_keys


def create_api_key_validator(
    provider: str | None = None,
) -> t.Callable[[str], str]:
    """Create a Pydantic field validator for API keys.

    This creates a validator that can be used with Pydantic's
    @field_validator decorator to automatically validate API keys
    during settings initialization.

    Args:
        provider: Provider name for validation pattern

    Returns:
        Validator function for use with @field_validator

    Example:
        >>> from pydantic import Field, field_validator
        >>> from mcp_common.config import MCPBaseSettings
        >>>
        >>> class MySettings(MCPBaseSettings):
        ...     api_key: str = Field(description="OpenAI API key")
        ...
        ...     _validate_api_key = field_validator("api_key")(
        ...         create_api_key_validator(provider="openai")
        ...     )
        >>>
        >>> settings = MySettings(api_key="invalid")  # Raises ValidationError
    """
    validator = APIKeyValidator(provider=provider)

    def validate_key(v: str) -> str:
        """Validate API key field."""
        validator.validate(v, raise_on_invalid=True)
        return v.strip()

    return validate_key
