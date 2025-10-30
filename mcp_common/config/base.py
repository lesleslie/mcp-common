"""Base settings class for MCP servers.

Provides common configuration patterns with YAML + environment variable support.
"""

from __future__ import annotations

import typing as t
from pathlib import Path

from acb.config import Settings
from pydantic import Field, field_validator

# Import security utilities (with fallback for backward compatibility)
try:
    from mcp_common.security import APIKeyValidator, validate_api_key_startup

    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False


class MCPBaseSettings(Settings):
    """Base settings class for MCP servers using ACB configuration system.

    Extends ACB Settings to provide:
    - YAML file loading from settings/{name}.yaml
    - Environment variable overrides
    - Path expansion (~/ → home directory)
    - Type validation with Pydantic
    - Required API key validation

    Configuration loading order (later overrides earlier):
    1. Default values in field definitions
    2. settings/local.yaml (gitignored, for development)
    3. settings/{server_name}.yaml (committed, for production defaults)
    4. Environment variables {SERVER_NAME}_{FIELD}

    Example:
        >>> class MailgunSettings(MCPBaseSettings):
        ...     api_key: str = Field(description="Mailgun API key")
        ...     domain: str = Field(description="Mailgun domain")
        ...     timeout: int = Field(default=30, description="Request timeout")
        ...
        >>> # Loads from:
        >>> # - settings/local.yaml (if exists)
        >>> # - settings/mailgun.yaml (if exists)
        >>> # - Environment variables MAILGUN_API_KEY, MAILGUN_DOMAIN, MAILGUN_TIMEOUT
        >>> settings = MailgunSettings()

    Attributes:
        server_name: Display name for the MCP server (e.g., "Mailgun MCP")
        server_description: Brief description of server functionality
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_debug_mode: Enable debug features (verbose logging, etc.)
    """

    server_name: str = Field(
        default="MCP Server",
        description="Display name for the MCP server",
        min_length=1,
        max_length=100,
    )
    server_description: str = Field(
        default="Model Context Protocol Server",
        description="Brief description of server functionality",
        max_length=500,
    )
    log_level: t.Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level for the server",
    )
    enable_debug_mode: bool = Field(
        default=False,
        description="Enable debug features (verbose logging, additional validation)",
    )

    @field_validator("server_name", mode="after")
    @classmethod
    def validate_server_name(cls, v: str) -> str:
        """Validate server name is not empty after stripping whitespace.

        Args:
            v: Server name to validate

        Returns:
            Validated server name

        Raises:
            ValueError: If server name is empty after stripping
        """
        if not v.strip():
            msg = "server_name cannot be empty"
            raise ValueError(msg)
        return v.strip()

    def get_api_key(self, key_name: str = "api_key") -> str:
        """Get API key with validation.

        This is a convenience method for retrieving API keys with proper
        validation. Raises ValueError if key is missing or empty.

        Args:
            key_name: Name of the API key field (default: "api_key")

        Returns:
            Validated API key

        Raises:
            ValueError: If API key is missing or empty
            AttributeError: If field doesn't exist

        Example:
            >>> class MySettings(MCPBaseSettings):
            ...     api_key: str
            ...
            >>> settings = MySettings(api_key="sk-...")
            >>> key = settings.get_api_key()  # Validates and returns key
        """
        if not hasattr(self, key_name):
            msg = f"Settings class has no field '{key_name}'"
            raise AttributeError(msg)

        key = getattr(self, key_name)

        if not key or (isinstance(key, str) and not key.strip()):
            msg = f"{key_name} is required but not set. Set via environment variable or settings file."
            raise ValueError(msg)

        return key if not isinstance(key, str) else key.strip()

    def get_data_dir(self, dir_name: str = "data") -> Path:
        """Get data directory path with automatic creation.

        Retrieves a directory path field and ensures the directory exists.

        Args:
            dir_name: Name of the directory field (default: "data")

        Returns:
            Path object with directory created if necessary

        Raises:
            AttributeError: If field doesn't exist
            ValueError: If field is not a Path

        Example:
            >>> class MySettings(MCPBaseSettings):
            ...     data_dir: Path = Field(default=Path("~/.my-server/data"))
            ...
            >>> settings = MySettings()
            >>> data_dir = settings.get_data_dir("data_dir")
            >>> # Returns Path("/Users/you/.my-server/data"), creates if needed
        """
        if not hasattr(self, dir_name):
            msg = f"Settings class has no field '{dir_name}'"
            raise AttributeError(msg)

        path = getattr(self, dir_name)

        if not isinstance(path, Path):
            msg = f"Field '{dir_name}' must be a Path, got {type(path).__name__}"
            raise ValueError(msg)

        # Expand ~ and create directory
        expanded = path.expanduser()
        expanded.mkdir(parents=True, exist_ok=True)

        return expanded

    def validate_api_keys_at_startup(
        self,
        key_fields: list[str] | None = None,
        provider: str | None = None,
    ) -> dict[str, str]:
        """Validate API keys at server startup (Phase 3 Security Enhancement).

        Performs comprehensive validation of all API key fields to ensure
        they are present and match expected format patterns. This should be
        called during server initialization to fail fast with clear errors.

        Args:
            key_fields: List of API key field names to validate (default: ["api_key"])
            provider: Provider name for format validation (e.g., "openai", "mailgun")

        Returns:
            Dict mapping field names to validated keys

        Raises:
            ValueError: If any API key is invalid or missing

        Example:
            >>> class MySettings(MCPBaseSettings):
            ...     api_key: str
            ...     secondary_key: str | None = None
            ...
            >>> settings = MySettings(api_key="sk-abc123...")
            >>> # Validate at startup
            >>> keys = settings.validate_api_keys_at_startup(
            ...     key_fields=["api_key"],
            ...     provider="openai"
            ... )
            >>> # Server fails to start if validation fails
        """
        if not SECURITY_AVAILABLE:
            # Fallback to basic validation if security module not available
            if key_fields is None:
                key_fields = ["api_key"]

            validated = {}
            for field in key_fields:
                if hasattr(self, field):
                    key = getattr(self, field)
                    if key:
                        validated[field] = self.get_api_key(field)
            return validated

        # Use comprehensive validation from security module
        return validate_api_key_startup(
            settings=self,
            key_fields=key_fields,
            provider=provider,
        )

    def get_api_key_secure(
        self,
        key_name: str = "api_key",
        provider: str | None = None,
        validate_format: bool = True,
    ) -> str:
        """Get API key with enhanced security validation (Phase 3).

        Enhanced version of get_api_key() that validates API key format
        against known provider patterns for additional security.

        Args:
            key_name: Name of the API key field (default: "api_key")
            provider: Provider name for format validation (e.g., "openai", "mailgun")
            validate_format: If True, validate key format against provider pattern

        Returns:
            Validated and stripped API key

        Raises:
            ValueError: If key is invalid or doesn't match expected format
            AttributeError: If field doesn't exist

        Example:
            >>> settings = MySettings(api_key="sk-abc123...")
            >>> key = settings.get_api_key_secure(provider="openai")
            >>> # Raises ValueError if key doesn't match OpenAI format
        """
        # Use basic validation first
        key = self.get_api_key(key_name)

        # Enhanced format validation if available and requested
        if validate_format and SECURITY_AVAILABLE and provider:
            validator = APIKeyValidator(provider=provider)
            validator.validate(key, raise_on_invalid=True)

        return key

    def get_masked_key(self, key_name: str = "api_key", visible_chars: int = 4) -> str:
        """Get masked API key for safe logging (Phase 3 Security).

        Returns API key with most characters masked for safe display
        in logs and error messages.

        Args:
            key_name: Name of the API key field (default: "api_key")
            visible_chars: Number of characters to show at end

        Returns:
            Masked key string (e.g., "sk-...abc123")

        Example:
            >>> settings = MySettings(api_key="sk-abc123def456ghi789")
            >>> masked = settings.get_masked_key()
            >>> print(f"Using API key: {masked}")
            >>> # Prints: "Using API key: sk-...i789"
        """
        if not hasattr(self, key_name):
            return "***"

        key = getattr(self, key_name)
        if not key:
            return "***"

        if SECURITY_AVAILABLE:
            return APIKeyValidator.mask_key(key, visible_chars=visible_chars)

        # Fallback masking
        if len(key) <= visible_chars:
            return "***"
        return f"...{key[-visible_chars:]}"


class MCPServerSettings(MCPBaseSettings):
    """Extended settings with common MCP server configuration.

    Includes typical fields needed by most MCP servers beyond the base settings.

    Attributes:
        api_key: API key for external service (override this in subclasses)
        base_url: Base URL for API endpoint
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        enable_cache: Enable response caching
        cache_ttl_seconds: Cache TTL in seconds
    """

    api_key: str | None = Field(
        default=None,
        description="API key for external service (required for most servers)",
    )
    base_url: str = Field(
        default="https://api.example.com",
        description="Base URL for API endpoint",
    )
    timeout: int = Field(
        default=30,
        description="Request timeout in seconds",
        ge=1,
        le=300,
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts on failure",
        ge=0,
        le=10,
    )
    enable_cache: bool = Field(
        default=False,
        description="Enable response caching",
    )
    cache_ttl_seconds: int = Field(
        default=300,
        description="Cache TTL in seconds",
        ge=0,
        le=86400,  # Max 24 hours
    )

    @field_validator("base_url", mode="after")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Validate base URL format.

        Args:
            v: Base URL to validate

        Returns:
            Validated base URL

        Raises:
            ValueError: If URL is invalid
        """
        if not v.strip():
            msg = "base_url cannot be empty"
            raise ValueError(msg)

        # Ensure URL starts with http:// or https://
        if not (v.startswith("http://") or v.startswith("https://")):
            msg = "base_url must start with http:// or https://"
            raise ValueError(msg)

        # Remove trailing slash for consistency
        return v.rstrip("/")
