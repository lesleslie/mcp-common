"""Reusable validation mixin for MCP server configuration classes.

This mixin provides common validation patterns extracted from multiple MCP servers,
reducing code duplication and ensuring consistent error handling across servers.

Phase 3.3 M5: Shared validation patterns with graceful degradation
"""

from __future__ import annotations

import typing as t

# Try to import specific exceptions (graceful degradation)
try:
    from mcp_common.exceptions import CredentialValidationError, ServerConfigurationError

    EXCEPTIONS_AVAILABLE = True
except ImportError:
    EXCEPTIONS_AVAILABLE = False


class ValidationMixin:
    """Reusable validation methods for MCP server settings.

    This mixin provides common validation patterns:
    - Required field validation (non-empty strings)
    - Credential validation (username/password pairs)
    - Minimum length validation
    - URL/host validation

    Usage:
        >>> from pydantic import BaseModel
        >>> from mcp_common.config import ValidationMixin
        >>>
        >>> class MySettings(BaseModel, ValidationMixin):
        ...     username: str
        ...     password: str
        ...
        ...     def validate_config(self) -> None:
        ...         self.validate_required_field("username", self.username)
        ...         self.validate_required_field("password", self.password)
        ...         self.validate_min_length("password", self.password, min_length=12)
    """

    def validate_required_field(
        self,
        field_name: str,
        value: str | None,
        context: str | None = None,
    ) -> None:
        """Validate that a required field is not None or empty.

        Args:
            field_name: Name of the field being validated
            value: Value to validate
            context: Optional context for error message (e.g., "Network Controller")

        Raises:
            ServerConfigurationError: If field is None or empty (when exceptions available)
            ValueError: Falls back to ValueError if exceptions unavailable
        """
        if not value or not value.strip():
            prefix = f"{context} " if context else ""
            msg = f"{prefix}{field_name} is not set in configuration"

            if EXCEPTIONS_AVAILABLE:
                raise ServerConfigurationError(
                    message=msg,
                    field=field_name,
                )
            else:
                raise ValueError(msg)

    def validate_min_length(
        self,
        field_name: str,
        value: str,
        min_length: int,
        context: str | None = None,
    ) -> None:
        """Validate that a string meets minimum length requirement.

        Args:
            field_name: Name of the field being validated
            value: Value to validate
            min_length: Minimum required length
            context: Optional context for error message

        Raises:
            ServerConfigurationError: If value is too short (when exceptions available)
            ValueError: Falls back to ValueError if exceptions unavailable
        """
        if len(value) < min_length:
            prefix = f"{context} " if context else ""
            msg = (
                f"{prefix}{field_name} is too short. "
                f"Required: {min_length} characters, got: {len(value)}"
            )

            if EXCEPTIONS_AVAILABLE:
                raise ServerConfigurationError(
                    message=msg,
                    field=field_name,
                    value=f"{len(value)} characters",
                )
            else:
                raise ValueError(msg)

    def validate_credentials(
        self,
        username: str | None,
        password: str | None,
        context: str | None = None,
        min_password_length: int = 12,
    ) -> None:
        """Validate username and password credentials.

        This is a convenience method that combines required field checks
        with password strength validation.

        Args:
            username: Username to validate
            password: Password to validate
            context: Optional context for error message (e.g., "API")
            min_password_length: Minimum password length (default: 12)

        Raises:
            CredentialValidationError: If credentials are invalid (when exceptions available)
            ValueError: Falls back to ValueError if exceptions unavailable
        """
        # Validate username
        if not username or not username.strip():
            prefix = f"{context} " if context else ""
            msg = f"{prefix}username is not set in configuration"

            if EXCEPTIONS_AVAILABLE:
                raise CredentialValidationError(
                    message=msg,
                    field="username",
                )
            else:
                raise ValueError(msg)

        # Validate password
        if not password or not password.strip():
            prefix = f"{context} " if context else ""
            msg = f"{prefix}password is not set in configuration"

            if EXCEPTIONS_AVAILABLE:
                raise CredentialValidationError(
                    message=msg,
                    field="password",
                )
            else:
                raise ValueError(msg)

        # Validate password strength
        if len(password) < min_password_length:
            prefix = f"{context} " if context else ""
            msg = (
                f"{prefix}password is too short. "
                f"Minimum: {min_password_length} characters, got: {len(password)}"
            )

            if EXCEPTIONS_AVAILABLE:
                raise CredentialValidationError(
                    message=msg,
                    field="password",
                )
            else:
                raise ValueError(msg)

    def validate_url_parts(
        self,
        host: str | None,
        port: int | None = None,
        context: str | None = None,
    ) -> None:
        """Validate host and optional port for URL construction.

        Args:
            host: Hostname or IP address
            port: Optional port number
            context: Optional context for error message

        Raises:
            ServerConfigurationError: If host is invalid (when exceptions available)
            ValueError: Falls back to ValueError if exceptions unavailable
        """
        # Validate host
        if not host or not host.strip():
            prefix = f"{context} " if context else ""
            msg = f"{prefix}host is not set in configuration"

            if EXCEPTIONS_AVAILABLE:
                raise ServerConfigurationError(
                    message=msg,
                    field="host",
                )
            else:
                raise ValueError(msg)

        # Validate port if provided
        if port is not None:
            if not isinstance(port, int) or port < 1 or port > 65535:
                prefix = f"{context} " if context else ""
                msg = f"{prefix}port must be between 1 and 65535, got: {port}"

                if EXCEPTIONS_AVAILABLE:
                    raise ServerConfigurationError(
                        message=msg,
                        field="port",
                        value=str(port),
                    )
                else:
                    raise ValueError(msg)

    def validate_one_of_required(
        self,
        field_names: list[str],
        values: list[t.Any],
        context: str | None = None,
    ) -> None:
        """Validate that at least one of multiple fields is set.

        Useful for scenarios like "at least one controller type must be configured".

        Args:
            field_names: List of field names being validated
            values: Corresponding list of values to check
            context: Optional context for error message

        Raises:
            ServerConfigurationError: If all fields are None/empty (when exceptions available)
            ValueError: Falls back to ValueError if exceptions unavailable
        """
        if len(field_names) != len(values):
            msg = "field_names and values must have same length"
            raise ValueError(msg)

        # Check if any value is not None/empty
        has_value = any(v is not None and str(v).strip() for v in values)

        if not has_value:
            prefix = f"{context}: " if context else ""
            field_list = ", ".join(field_names)
            msg = f"{prefix}At least one of [{field_list}] is required"

            if EXCEPTIONS_AVAILABLE:
                raise ServerConfigurationError(
                    message=msg,
                    field="multiple_fields",
                )
            else:
                raise ValueError(msg)


__all__ = ["ValidationMixin"]
