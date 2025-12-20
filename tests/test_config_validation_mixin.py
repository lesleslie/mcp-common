"""Tests for ValidationMixin.

Tests comprehensive validation patterns for MCP server configuration,
ensuring consistent error handling and graceful degradation.

Phase 3.3 M5: Shared validation mixin tests
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from mcp_common.config import ValidationMixin
from mcp_common.exceptions import CredentialValidationError, ServerConfigurationError


class SampleSettings(BaseModel, ValidationMixin):
    """Test settings class using ValidationMixin."""

    username: str | None = None
    password: str | None = None
    host: str | None = None
    port: int | None = None


class TestValidateRequiredField:
    """Test validate_required_field method."""

    def test_validates_non_empty_string(self) -> None:
        """Should pass for non-empty strings."""
        settings = SampleSettings()
        # Should not raise
        settings.validate_required_field("test_field", "valid_value")

    def test_rejects_none_value(self) -> None:
        """Should raise ServerConfigurationError for None."""
        settings = SampleSettings()

        with pytest.raises(ServerConfigurationError, match="test_field is not set") as exc_info:
            settings.validate_required_field("test_field", None)

        assert exc_info.value.field == "test_field"

    def test_rejects_empty_string(self) -> None:
        """Should raise ServerConfigurationError for empty string."""
        settings = SampleSettings()

        with pytest.raises(ServerConfigurationError, match="test_field is not set"):
            settings.validate_required_field("test_field", "")

    def test_rejects_whitespace_only(self) -> None:
        """Should raise ServerConfigurationError for whitespace-only string."""
        settings = SampleSettings()

        with pytest.raises(ServerConfigurationError, match="test_field is not set"):
            settings.validate_required_field("test_field", "   ")

    def test_includes_context_in_error(self) -> None:
        """Should include context in error message when provided."""
        settings = SampleSettings()

        with pytest.raises(ServerConfigurationError, match="API Controller test_field is not set"):
            settings.validate_required_field("test_field", None, context="API Controller")


class TestValidateMinLength:
    """Test validate_min_length method."""

    def test_validates_sufficient_length(self) -> None:
        """Should pass for strings meeting minimum length."""
        settings = SampleSettings()
        # Should not raise
        settings.validate_min_length("password", "long_enough_value", min_length=10)

    def test_rejects_too_short_string(self) -> None:
        """Should raise ServerConfigurationError for too-short strings."""
        settings = SampleSettings()

        with pytest.raises(
            ServerConfigurationError,
            match=r"password is too short\. Required: 12 characters, got: 5",
        ) as exc_info:
            settings.validate_min_length("password", "short", min_length=12)

        assert exc_info.value.field == "password"
        assert exc_info.value.value == "5 characters"

    def test_includes_context_in_error(self) -> None:
        """Should include context in error message when provided."""
        settings = SampleSettings()

        with pytest.raises(ServerConfigurationError, match="Database password is too short"):
            settings.validate_min_length("password", "short", min_length=12, context="Database")


class TestValidateCredentials:
    """Test validate_credentials method."""

    def test_validates_valid_credentials(self) -> None:
        """Should pass for valid username and password."""
        settings = SampleSettings()
        # Should not raise
        settings.validate_credentials(
            username="admin",
            password="secure_password_12345",
            min_password_length=12,
        )

    def test_rejects_none_username(self) -> None:
        """Should raise CredentialValidationError for None username."""
        settings = SampleSettings()

        with pytest.raises(CredentialValidationError, match="username is not set") as exc_info:
            settings.validate_credentials(username=None, password="password123456")

        assert exc_info.value.field == "username"

    def test_rejects_empty_username(self) -> None:
        """Should raise CredentialValidationError for empty username."""
        settings = SampleSettings()

        with pytest.raises(CredentialValidationError, match="username is not set"):
            settings.validate_credentials(username="", password="password123456")

    def test_rejects_none_password(self) -> None:
        """Should raise CredentialValidationError for None password."""
        settings = SampleSettings()

        with pytest.raises(CredentialValidationError, match="password is not set") as exc_info:
            settings.validate_credentials(username="admin", password=None)

        assert exc_info.value.field == "password"

    def test_rejects_empty_password(self) -> None:
        """Should raise CredentialValidationError for empty password."""
        settings = SampleSettings()

        with pytest.raises(CredentialValidationError, match="password is not set"):
            settings.validate_credentials(username="admin", password="")

    def test_rejects_weak_password(self) -> None:
        """Should raise CredentialValidationError for too-short password."""
        settings = SampleSettings()

        with pytest.raises(
            CredentialValidationError,
            match=r"password is too short\. Minimum: 12 characters, got: 5",
        ) as exc_info:
            settings.validate_credentials(
                username="admin", password="short", min_password_length=12
            )

        assert exc_info.value.field == "password"

    def test_custom_min_password_length(self) -> None:
        """Should respect custom minimum password length."""
        settings = SampleSettings()

        # Should pass with custom minimum
        settings.validate_credentials(username="admin", password="pass8", min_password_length=5)

        # Should fail with default minimum (12)
        with pytest.raises(CredentialValidationError):
            settings.validate_credentials(username="admin", password="pass8")

    def test_includes_context_in_error(self) -> None:
        """Should include context in error messages."""
        settings = SampleSettings()

        with pytest.raises(CredentialValidationError, match="API username is not set"):
            settings.validate_credentials(username=None, password="password", context="API")


class TestValidateURLParts:
    """Test validate_url_parts method."""

    def test_validates_valid_host(self) -> None:
        """Should pass for valid host."""
        settings = SampleSettings()
        # Should not raise
        settings.validate_url_parts(host="example.com")

    def test_validates_valid_host_and_port(self) -> None:
        """Should pass for valid host and port."""
        settings = SampleSettings()
        # Should not raise
        settings.validate_url_parts(host="example.com", port=8080)

    def test_rejects_none_host(self) -> None:
        """Should raise ServerConfigurationError for None host."""
        settings = SampleSettings()

        with pytest.raises(ServerConfigurationError, match="host is not set") as exc_info:
            settings.validate_url_parts(host=None)

        assert exc_info.value.field == "host"

    def test_rejects_empty_host(self) -> None:
        """Should raise ServerConfigurationError for empty host."""
        settings = SampleSettings()

        with pytest.raises(ServerConfigurationError, match="host is not set"):
            settings.validate_url_parts(host="")

    def test_rejects_invalid_port_too_low(self) -> None:
        """Should raise ServerConfigurationError for port < 1."""
        settings = SampleSettings()

        with pytest.raises(
            ServerConfigurationError,
            match="port must be between 1 and 65535, got: 0",
        ) as exc_info:
            settings.validate_url_parts(host="example.com", port=0)

        assert exc_info.value.field == "port"
        assert exc_info.value.value == "0"

    def test_rejects_invalid_port_too_high(self) -> None:
        """Should raise ServerConfigurationError for port > 65535."""
        settings = SampleSettings()

        with pytest.raises(
            ServerConfigurationError,
            match="port must be between 1 and 65535, got: 99999",
        ):
            settings.validate_url_parts(host="example.com", port=99999)

    def test_accepts_valid_port_range(self) -> None:
        """Should accept ports 1-65535."""
        settings = SampleSettings()

        # Boundary tests
        settings.validate_url_parts(host="example.com", port=1)
        settings.validate_url_parts(host="example.com", port=65535)

        # Common ports
        settings.validate_url_parts(host="example.com", port=80)
        settings.validate_url_parts(host="example.com", port=443)
        settings.validate_url_parts(host="example.com", port=8080)

    def test_includes_context_in_error(self) -> None:
        """Should include context in error messages."""
        settings = SampleSettings()

        with pytest.raises(ServerConfigurationError, match="Database host is not set"):
            settings.validate_url_parts(host=None, context="Database")


class TestValidateOneOfRequired:
    """Test validate_one_of_required method."""

    def test_validates_when_first_field_set(self) -> None:
        """Should pass when first field has value."""
        settings = SampleSettings()
        # Should not raise
        settings.validate_one_of_required(
            field_names=["field1", "field2"],
            values=["value1", None],
        )

    def test_validates_when_second_field_set(self) -> None:
        """Should pass when second field has value."""
        settings = SampleSettings()
        # Should not raise
        settings.validate_one_of_required(
            field_names=["field1", "field2"],
            values=[None, "value2"],
        )

    def test_validates_when_all_fields_set(self) -> None:
        """Should pass when all fields have values."""
        settings = SampleSettings()
        # Should not raise
        settings.validate_one_of_required(
            field_names=["field1", "field2", "field3"],
            values=["value1", "value2", "value3"],
        )

    def test_rejects_when_all_fields_none(self) -> None:
        """Should raise ServerConfigurationError when all fields are None."""
        settings = SampleSettings()

        with pytest.raises(
            ServerConfigurationError,
            match="At least one of \\[field1, field2\\] is required",
        ) as exc_info:
            settings.validate_one_of_required(
                field_names=["field1", "field2"],
                values=[None, None],
            )

        assert exc_info.value.field == "multiple_fields"

    def test_rejects_when_all_fields_empty(self) -> None:
        """Should raise ServerConfigurationError when all fields are empty strings."""
        settings = SampleSettings()

        with pytest.raises(ServerConfigurationError, match="At least one of"):
            settings.validate_one_of_required(
                field_names=["field1", "field2"],
                values=["", "   "],
            )

    def test_includes_context_in_error(self) -> None:
        """Should include context in error message."""
        settings = SampleSettings()

        with pytest.raises(
            ServerConfigurationError,
            match="Controllers: At least one of \\[network, access\\] is required",
        ):
            settings.validate_one_of_required(
                field_names=["network", "access"],
                values=[None, None],
                context="Controllers",
            )

    def test_raises_on_mismatched_lengths(self) -> None:
        """Should raise ValueError when field_names and values have different lengths."""
        settings = SampleSettings()

        with pytest.raises(ValueError, match="field_names and values must have same length"):
            settings.validate_one_of_required(
                field_names=["field1", "field2"],
                values=["value1"],  # Only one value
            )


class TestMixinIntegration:
    """Test ValidationMixin integration with Pydantic models."""

    def test_mixin_works_with_pydantic_model(self) -> None:
        """ValidationMixin should work seamlessly with Pydantic models."""

        class MySettings(BaseModel, ValidationMixin):
            username: str = "admin"
            password: str = "secure_password_123"

        settings = MySettings()

        # Should not raise
        settings.validate_credentials(settings.username, settings.password)

    def test_mixin_multiple_validation_calls(self) -> None:
        """Should support multiple validation method calls."""
        settings = SampleSettings(
            username="admin",
            password="secure_password_123",
            host="example.com",
            port=443,
        )

        # Multiple validations should all pass
        settings.validate_required_field("username", settings.username)
        settings.validate_required_field("password", settings.password)
        assert settings.password is not None  # validate_required_field ensures this
        settings.validate_min_length("password", settings.password, min_length=12)
        settings.validate_url_parts(settings.host, settings.port)
        settings.validate_credentials(settings.username, settings.password)
