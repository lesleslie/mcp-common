# Security Implementation Guide

**Phase 3: Security Hardening Implementation**

This document provides comprehensive guidance for implementing the mcp-common security module across all MCP servers.

## Overview

The security module provides:

- **API Key Validation**: Provider-specific pattern matching for multiple services
- **Startup Validation**: Fail-fast validation during server initialization
- **Safe Logging**: Automatic masking of sensitive data in logs
- **Input/Output Sanitization**: Protection against common security vulnerabilities

## Quick Start

### Basic Implementation

```python
from mcp_common.config import MCPBaseSettings
from pydantic import Field


class MyServerSettings(MCPBaseSettings):
    """Server settings with API key validation."""

    server_name: str = Field(default="My MCP Server")
    api_key: str = Field(description="Service API key")

    # Validation happens automatically during initialization


# Server initialization
settings = MyServerSettings()

# Validate API keys at startup (recommended)
try:
    validated_keys = settings.validate_api_keys_at_startup(
        key_fields=["api_key"],
        provider="openai",  # or "anthropic", "mailgun", "github", etc.
    )
    print(f"✅ Server initialized with validated API key: {settings.get_masked_key()}")
except ValueError as e:
    print(f"❌ Server startup failed: {e}")
    exit(1)
```

## API Key Validation

### Supported Providers

The security module includes built-in patterns for:

- **OpenAI**: `sk-[A-Za-z0-9]{48}` - Standard OpenAI API keys
- **Anthropic**: `sk-ant-[A-Za-z0-9\-_]{95,}` - Claude API keys
- **Mailgun**: `[0-9a-f]{32}` - Mailgun hex format keys
- **GitHub**: `ghp_[A-Za-z0-9]{36,}` / `ghs_[A-Za-z0-9]{36,}` - GitHub tokens
- **Generic**: `[any]{16,}` - Generic validation with minimum length

### Startup Validation

**Recommended Pattern** - Validate all API keys during server initialization:

```python
class MultiKeySettings(MCPBaseSettings):
    """Settings with multiple API keys."""

    openai_key: str = Field(description="OpenAI API key")
    mailgun_key: str = Field(description="Mailgun API key")
    optional_key: str | None = Field(default=None, description="Optional key")


# In server initialization
settings = MultiKeySettings()

try:
    # Validate multiple keys with generic pattern
    validated = settings.validate_api_keys_at_startup(
        key_fields=["openai_key", "mailgun_key", "optional_key"]
    )

    print(f"✅ Validated {len(validated)} API keys")
    # Optional keys that are None are skipped automatically

except ValueError as e:
    print(f"❌ API key validation failed: {e}")
    exit(1)
```

### Provider-Specific Validation

When you know the provider, use provider-specific validation for better error messages:

```python
# Validate with specific provider pattern
try:
    validated = settings.validate_api_keys_at_startup(key_fields=["openai_key"], provider="openai")
except ValueError as e:
    # Error message includes provider-specific guidance:
    # "Invalid API key format for OpenAI. Expected: OpenAI API keys
    # start with 'sk-' followed by 48 alphanumeric characters"
    print(f"Configuration error: {e}")
```

### Runtime Key Access

```python
# Get API key with enhanced validation
try:
    key = settings.get_api_key_secure(key_name="api_key", provider="openai", validate_format=True)
    # Use key for API calls
except ValueError as e:
    print(f"Invalid API key: {e}")
```

## Safe Logging

### Masking API Keys

**Always mask API keys in logs and error messages:**

```python
# Get masked version for logging
masked = settings.get_masked_key("api_key")
print(f"Using API key: {masked}")
# Output: "Using API key: sk-...abc1"

# Custom visible characters
masked = settings.get_masked_key("api_key", visible_chars=6)
# Output: "Using API key: sk-...abc123"

# Error messages
try:
    api_call(settings.get_api_key())
except Exception as e:
    print(f"API call failed with key {settings.get_masked_key()}: {e}")
```

### Dictionary Sanitization

**Sanitize entire dictionaries before logging:**

```python
from mcp_common.security import sanitize_dict_for_logging

config = {
    "api_key": "sk-secret123",
    "user": "john",
    "password": "pass123",
    "timeout": 30,
}

# Sanitize for safe logging
safe_config = sanitize_dict_for_logging(config)
print(f"Server config: {safe_config}")
# Output: {"api_key": "***", "user": "john", "password": "***", "timeout": 30}
```

### Output Sanitization

**Sanitize output data to prevent key exposure:**

```python
from mcp_common.security import sanitize_output

response = {
    "status": "success",
    "message": "API call to sk-abc123def456... succeeded",
    "data": {"user": "john"},
}

# Mask any API keys in output
safe_response = sanitize_output(response)
# Keys are automatically detected and masked: [REDACTED-OPENAI]
```

## Input Sanitization

### Path Validation

**Prevent path traversal attacks:**

```python
from mcp_common.security.sanitization import sanitize_path
from pathlib import Path

# Safe path handling
try:
    # Reject paths with '..' components
    safe_path = sanitize_path("../../etc/passwd")
except ValueError as e:
    print(f"Path traversal detected: {e}")

# Confine paths to base directory
try:
    safe_path = sanitize_path("data/user_file.txt", base_dir="/app/data")
    # Returns Path object confined to /app/data
except ValueError as e:
    print(f"Path escape attempt: {e}")

# Allow absolute paths to specific directories
safe_path = sanitize_path("/tmp/cache/file.txt", allow_absolute=True)
# System directories (/etc, /sys, /proc) are always blocked
```

### User Input Validation

**Sanitize user-provided strings:**

```python
from mcp_common.security.sanitization import sanitize_input

# Basic sanitization
user_input = sanitize_input(
    "  user provided text  ", max_length=100
)  # Returns: "user provided text"

# HTML stripping
user_comment = sanitize_input(
    "<script>alert('xss')</script>Hello", strip_html=True
)  # Returns: "alert('xss')Hello" (tags removed)

# Character restrictions
username = sanitize_input("john_doe", allowed_chars="a-z_")  # Returns: "john_doe"

# Reject invalid input
try:
    sanitize_input("invalid!@#$", allowed_chars="a-z")
except ValueError as e:
    print(f"Invalid input: {e}")
```

## Custom API Key Patterns

**For services not included in built-in patterns:**

```python
from mcp_common.security.api_keys import APIKeyPattern, APIKeyValidator

# Define custom pattern
custom_pattern = APIKeyPattern(
    name="CustomService",
    pattern=r"^cs-[0-9]{10}-[a-z]{8}$",
    description="Custom service keys: 'cs-' + 10 digits + '-' + 8 lowercase letters",
    example="cs-1234567890-abcdefgh",
)

# Use in validation
validator = APIKeyValidator(pattern=custom_pattern)
try:
    validator.validate("cs-1234567890-abcdefgh", raise_on_invalid=True)
    print("✅ Custom key is valid")
except ValueError as e:
    print(f"❌ Invalid key: {e}")
```

## Pydantic Field Validators

**Integrate validation into Pydantic models:**

```python
from mcp_common.config import MCPBaseSettings
from mcp_common.security.api_keys import create_api_key_validator
from pydantic import Field, field_validator


class AutoValidatingSettings(MCPBaseSettings):
    """Settings with automatic field validation."""

    api_key: str = Field(description="OpenAI API key")

    # Automatic validation on field assignment
    _validate_api_key = field_validator("api_key")(create_api_key_validator(provider="openai"))


# Validation happens automatically during initialization
try:
    settings = AutoValidatingSettings(api_key="invalid")
except ValidationError as e:
    print(f"Invalid configuration: {e}")
```

## Migration Guide

### Step 1: Add Startup Validation

**Minimal change to add security:**

```python
# Before Phase 3
class MySettings(MCPBaseSettings):
    api_key: str


settings = MySettings()
# Server starts with any key, including invalid ones


# After Phase 3
class MySettings(MCPBaseSettings):
    api_key: str


settings = MySettings()

# Add this at server startup
try:
    settings.validate_api_keys_at_startup(provider="openai")
except ValueError as e:
    print(f"❌ Invalid API key: {e}")
    exit(1)
```

### Step 2: Update Logging

**Replace direct key logging:**

```python
# Before Phase 3
print(f"Using API key: {settings.api_key}")  # ❌ Exposes full key


# After Phase 3
print(f"Using API key: {settings.get_masked_key()}")  # ✅ Safe: "sk-...abc1"
```

### Step 3: Add Input Sanitization

**For servers that accept file paths or user input:**

```python
from mcp_common.security.sanitization import sanitize_path, sanitize_input

# Sanitize file paths
safe_path = sanitize_path(user_provided_path, base_dir="/app/data")

# Sanitize user input
safe_input = sanitize_input(user_text, max_length=1000, strip_html=True)
```

## Testing Recommendations

### Unit Tests

```python
import pytest
from mcp_common.config import MCPBaseSettings


def test_startup_validation_success():
    """Test successful API key validation."""

    class Settings(MCPBaseSettings):
        api_key: str = Field(default="sk-" + "a" * 48)

    settings = Settings()
    keys = settings.validate_api_keys_at_startup(provider="openai")

    assert "api_key" in keys


def test_startup_validation_failure():
    """Test that invalid keys cause startup failure."""

    class Settings(MCPBaseSettings):
        api_key: str = Field(default="invalid")

    settings = Settings()

    with pytest.raises(ValueError, match="Invalid API key format"):
        settings.validate_api_keys_at_startup(provider="openai")


def test_safe_logging():
    """Test that API keys are masked in logs."""

    class Settings(MCPBaseSettings):
        api_key: str = Field(default="sk-secret123abc456def789")

    settings = Settings()
    masked = settings.get_masked_key()

    assert "sk-..." in masked
    assert "secret123" not in masked
```

## Security Best Practices

1. **Always validate API keys at startup** - Fail fast with clear error messages
1. **Never log raw API keys** - Use `get_masked_key()` for all logging
1. **Sanitize all user input** - Use `sanitize_input()` and `sanitize_path()`
1. **Sanitize output data** - Use `sanitize_output()` before returning responses
1. **Use provider-specific validation** - Better error messages for debugging
1. **Handle optional keys gracefully** - `validate_api_keys_at_startup()` skips None values
1. **Test validation logic** - Ensure your server fails to start with invalid keys

## Common Patterns

### Multiple Providers

```python
class MultiProviderSettings(MCPBaseSettings):
    openai_key: str
    mailgun_key: str
    github_token: str | None = None


settings = MultiProviderSettings()

# Validate all keys (generic validation for mixed providers)
validated = settings.validate_api_keys_at_startup(
    key_fields=["openai_key", "mailgun_key", "github_token"]
)
```

### Environment-Specific Keys

```python
from pydantic import Field


class EnvironmentSettings(MCPBaseSettings):
    production_key: str = Field(description="Production API key")
    development_key: str | None = Field(default=None, description="Dev key")

    @property
    def active_key(self) -> str:
        """Get active key based on environment."""
        return (
            self.production_key
            if self.enable_debug_mode
            else self.development_key or self.production_key
        )


# Validate active key
settings = EnvironmentSettings()
active_key_name = "production_key" if not settings.enable_debug_mode else "development_key"

try:
    settings.validate_api_keys_at_startup(key_fields=[active_key_name], provider="openai")
except ValueError as e:
    print(f"Environment configuration error: {e}")
    exit(1)
```

### Graceful Fallback

```python
# Try secure validation first, fall back to basic if needed
try:
    key = settings.get_api_key_secure(provider="openai")
except ValueError:
    # Fall back to basic validation if security module unavailable
    key = settings.get_api_key()
    print("Warning: Using basic API key validation")
```

## Troubleshooting

### API Key Validation Errors

**Error**: "Invalid API key format for OpenAI"

**Solution**: Verify your key matches the expected format:

- OpenAI: `sk-` + 48 alphanumeric characters
- Check for whitespace (automatically stripped)
- Ensure the entire key is present

**Error**: "Validation failed for 'api_key'"

**Solution**: Check which field is failing:

```python
# Validate keys individually to identify the problem
for field in ["api_key", "secondary_key"]:
    try:
        settings.validate_api_keys_at_startup(key_fields=[field], provider="openai")
        print(f"✅ {field} is valid")
    except ValueError as e:
        print(f"❌ {field} validation failed: {e}")
```

### Backward Compatibility

If the security module is unavailable (shouldn't happen, but handled gracefully):

```python
# The SECURITY_AVAILABLE flag provides fallback behavior
# Methods like validate_api_keys_at_startup() fall back to basic validation
# This ensures servers continue working even without enhanced security

# To check if enhanced security is available:
from mcp_common.config.base import SECURITY_AVAILABLE

if SECURITY_AVAILABLE:
    print("✅ Enhanced security module active")
else:
    print("⚠️ Using fallback validation (security module unavailable)")
```

## References

- **Implementation Files**:

  - `mcp_common/security/api_keys.py` - API key validation
  - `mcp_common/security/sanitization.py` - Input/output sanitization
  - `mcp_common/config/base.py` - MCPBaseSettings security methods

- **Test Files**:

  - `tests/test_security_api_keys.py` - 36 API key validation tests
  - `tests/test_security_sanitization.py` - 55 sanitization tests
  - `tests/test_config_security.py` - 32 MCPBaseSettings integration tests

- **Documentation**:

  - `INTEGRATION_TRACKING.md` - Phase 3 implementation progress
  - `IMPLEMENTATION_PLAN.md` - Overall 10-week security roadmap

## Support

For questions or issues with the security module:

1. Review this guide and the test files for examples
1. Check `INTEGRATION_TRACKING.md` for known issues
1. Ensure you're using the latest version of mcp-common

**Phase 3 Status**: Security module complete with 123 passing tests ✅
