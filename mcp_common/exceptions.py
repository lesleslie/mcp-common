"""Custom exceptions for MCP server lifecycle and configuration.

This module provides a hierarchy of exceptions for graceful error handling in
MCP servers, replacing sys.exit() calls in library code with proper exceptions.

Usage:
    from mcp_common.exceptions import ServerConfigurationError

    def validate_config(self) -> None:
        if not self.username:
            raise ServerConfigurationError(
                message="Username is not set in configuration",
                field="username",
            )
"""

from __future__ import annotations


class MCPServerError(Exception):
    """Base exception for all MCP server errors.

    All custom MCP server exceptions inherit from this base class, allowing
    calling code to catch all MCP-related errors with a single except clause.
    """


class ServerConfigurationError(MCPServerError):
    """Raised when server configuration is invalid or incomplete.

    This exception should be raised during configuration validation when:
    - Required configuration fields are missing
    - Configuration values are invalid or out of range
    - Configuration file is malformed or unreadable

    Attributes:
        field: The configuration field that failed validation (if applicable)
        value: The invalid value that caused the error (if applicable)
    """

    def __init__(self, message: str, field: str | None = None, value: str | None = None) -> None:
        """Initialize configuration error with optional field context.

        Args:
            message: Human-readable error description
            field: Name of the configuration field that failed
            value: The invalid value (optional, for debugging)
        """
        self.field = field
        self.value = value
        super().__init__(message)


class ServerInitializationError(MCPServerError):
    """Raised when server fails to initialize due to environment issues.

    This exception should be raised when the server cannot start due to:
    - Database connection failures
    - File system permissions issues
    - Network socket binding failures
    - Resource allocation failures

    Attributes:
        component: The server component that failed to initialize
        details: Additional error details for debugging
    """

    def __init__(
        self, message: str, component: str | None = None, details: str | None = None
    ) -> None:
        """Initialize initialization error with component context.

        Args:
            message: Human-readable error description
            component: Name of the component that failed (e.g., "database", "logger")
            details: Additional technical details about the failure
        """
        self.component = component
        self.details = details
        super().__init__(message)


class DependencyMissingError(MCPServerError):
    """Raised when a required dependency is not available.

    This exception should be raised when:
    - Required Python packages are not installed
    - System dependencies are missing
    - Optional features are accessed without their dependencies

    Attributes:
        dependency: Name of the missing dependency
        install_command: Command to install the dependency (for better UX)
    """

    def __init__(
        self,
        message: str,
        dependency: str | None = None,
        install_command: str | None = None,
    ) -> None:
        """Initialize dependency error with installation guidance.

        Args:
            message: Human-readable error description
            dependency: Name of the missing dependency (e.g., "fastmcp", "onnxruntime")
            install_command: Installation command (e.g., "uv add fastmcp")
        """
        self.dependency = dependency
        self.install_command = install_command
        super().__init__(message)


class CredentialValidationError(ServerConfigurationError):
    """Raised when credentials fail validation.

    This exception should be raised when:
    - Credentials are missing or empty
    - Credentials do not meet security requirements (length, complexity)
    - Credentials fail format validation (e.g., API key format)

    Inherits from ServerConfigurationError to allow catching all config errors.
    """


class APIKeyMissingError(CredentialValidationError):
    """Raised when a required API key is not provided.

    This exception should be raised when:
    - API key field is None or empty string
    - API key is required but missing from environment/config

    Attributes:
        provider: The API provider name (e.g., "openai", "gemini")
    """

    def __init__(
        self,
        message: str,
        field: str | None = None,
        provider: str | None = None,
    ) -> None:
        """Initialize API key missing error.

        Args:
            message: Human-readable error description
            field: Name of the API key field (e.g., "OPENAI_API_KEY")
            provider: Provider name (e.g., "openai", "anthropic")
        """
        self.provider = provider
        super().__init__(message=message, field=field)


class APIKeyFormatError(CredentialValidationError):
    """Raised when an API key has an invalid format.

    This exception should be raised when:
    - API key doesn't match expected pattern
    - API key has invalid characters
    - API key format is unrecognized

    Attributes:
        provider: The API provider name
        expected_format: Description of expected format
        example: Example of valid format
    """

    def __init__(
        self,
        message: str,
        field: str | None = None,
        provider: str | None = None,
        expected_format: str | None = None,
        example: str | None = None,
    ) -> None:
        """Initialize API key format error.

        Args:
            message: Human-readable error description
            field: Name of the API key field
            provider: Provider name
            expected_format: Description of expected format
            example: Example of valid format (masked)
        """
        self.provider = provider
        self.expected_format = expected_format
        self.example = example
        super().__init__(message=message, field=field)


class APIKeyLengthError(CredentialValidationError):
    """Raised when an API key is too short or too long.

    This exception should be raised when:
    - API key length is below minimum requirement
    - API key length exceeds maximum allowed

    Attributes:
        min_length: Minimum required length
        max_length: Maximum allowed length (optional)
        actual_length: Actual key length provided
    """

    def __init__(
        self,
        message: str,
        field: str | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        actual_length: int | None = None,
    ) -> None:
        """Initialize API key length error.

        Args:
            message: Human-readable error description
            field: Name of the API key field
            min_length: Minimum required length
            max_length: Maximum allowed length
            actual_length: Actual length of provided key
        """
        self.min_length = min_length
        self.max_length = max_length
        self.actual_length = actual_length
        super().__init__(message=message, field=field)


__all__ = [
    "APIKeyFormatError",
    "APIKeyLengthError",
    "APIKeyMissingError",
    "CredentialValidationError",
    "DependencyMissingError",
    "MCPServerError",
    "ServerConfigurationError",
    "ServerInitializationError",
]
