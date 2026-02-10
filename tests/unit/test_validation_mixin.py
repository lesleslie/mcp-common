"""Tests for ValidationMixin configuration validation patterns."""

from __future__ import annotations

import importlib
from unittest.mock import Mock

import pytest
from pydantic import BaseModel, ValidationError

from mcp_common.config import ValidationMixin
from mcp_common.config.validation_mixin import ValidationMixin as VM
from mcp_common.exceptions import (
    CredentialValidationError,
    ServerConfigurationError,
)


@pytest.mark.unit
class TestValidationMixinRequiredField:
    """Tests for validate_required_field method."""

    def test_valid_field_passes(self) -> None:
        """Test validation passes with valid non-empty field."""
        VM.validate_required_field("username", "testuser")
        VM.validate_required_field("api_key", "sk-1234567890")

    def test_none_field_fails(self) -> None:
        """Test validation fails with None field."""
        with pytest.raises(ServerConfigurationError) as exc_info:
            VM.validate_required_field("username", None)

        assert "username is not set in configuration" in str(exc_info.value)
        assert exc_info.value.field == "username"

    def test_empty_string_fails(self) -> None:
        """Test validation fails with empty string."""
        with pytest.raises(ServerConfigurationError) as exc_info:
            VM.validate_required_field("password", "")

        assert "password is not set in configuration" in str(exc_info.value)

    def test_whitespace_only_fails(self) -> None:
        """Test validation fails with whitespace-only string."""
        with pytest.raises(ServerConfigurationError) as exc_info:
            VM.validate_required_field("api_key", "   ")

        assert "api_key is not set in configuration" in str(exc_info.value)

    def test_with_context(self) -> None:
        """Test validation includes context in error message."""
        with pytest.raises(ServerConfigurationError) as exc_info:
            VM.validate_required_field(
                "host", None, context="Database Controller"
            )

        assert "Database Controller host is not set" in str(exc_info.value)

    def test_fallback_to_valueerror_without_exceptions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test fallback to ValueError when exceptions unavailable."""
        # Force exceptions to be unavailable
        monkeypatch.setattr(
            "mcp_common.config.validation_mixin.EXCEPTIONS_AVAILABLE", False
        )

        with pytest.raises(ValueError) as exc_info:
            VM.validate_required_field("field", None)

        assert "field is not set in configuration" in str(exc_info.value)


@pytest.mark.unit
class TestValidationMixinMinLength:
    """Tests for validate_min_length method."""

    def test_valid_length_passes(self) -> None:
        """Test validation passes when length meets minimum."""
        VM.validate_min_length("password", "securepassword123", min_length=12)
        VM.validate_min_length("api_key", "sk-1234567890", min_length=10)

    def test_short_value_fails(self) -> None:
        """Test validation fails when value is too short."""
        with pytest.raises(ServerConfigurationError) as exc_info:
            VM.validate_min_length("password", "short", min_length=12)

        assert "password is too short" in str(exc_info.value)
        assert "Required: 12 characters, got: 5" in str(exc_info.value)
        assert exc_info.value.field == "password"

    def test_with_context(self) -> None:
        """Test validation includes context in error message."""
        with pytest.raises(ServerConfigurationError) as exc_info:
            VM.validate_min_length(
                "api_key", "short", min_length=20, context="API"
            )

        assert "API api_key is too short" in str(exc_info.value)

    def test_exactly_min_length_passes(self) -> None:
        """Test value exactly at minimum length passes."""
        VM.validate_min_length("field", "abc", min_length=3)


@pytest.mark.unit
class TestValidationMixinCredentials:
    """Tests for validate_credentials method."""

    def test_valid_credentials_pass(self) -> None:
        """Test validation with valid username and password."""
        class TestModel(BaseModel, ValidationMixin):
            pass

        model = TestModel()
        model.validate_credentials(
            username="testuser",
            password="securepassword123",
        )

    def test_missing_username_fails(self) -> None:
        """Test validation fails when username is missing."""
        class TestModel(BaseModel, ValidationMixin):
            pass

        model = TestModel()

        with pytest.raises(CredentialValidationError) as exc_info:
            model.validate_credentials(username=None, password="password123")

        assert "username is not set" in str(exc_info.value)

    def test_missing_password_fails(self) -> None:
        """Test validation fails when password is missing."""
        class TestModel(BaseModel, ValidationMixin):
            pass

        model = TestModel()

        with pytest.raises(CredentialValidationError) as exc_info:
            model.validate_credentials(username="testuser", password=None)

        assert "password is not set" in str(exc_info.value)

    def test_short_password_fails(self) -> None:
        """Test validation fails when password is too short."""
        class TestModel(BaseModel, ValidationMixin):
            pass

        model = TestModel()

        with pytest.raises(CredentialValidationError) as exc_info:
            model.validate_credentials(
                username="testuser",
                password="short",
                min_password_length=12,
            )

        assert "password is too short" in str(exc_info.value)

    def test_custom_min_password_length(self) -> None:
        """Test validation with custom minimum password length."""
        class TestModel(BaseModel, ValidationMixin):
            pass

        model = TestModel()

        # Should pass with 8 chars
        model.validate_credentials(
            username="testuser",
            password="pass1234",
            min_password_length=8,
        )

        # Should fail with 7 chars
        with pytest.raises(CredentialValidationError):
            model.validate_credentials(
                username="testuser",
                password="pass123",
                min_password_length=8,
            )

    def test_with_context(self) -> None:
        """Test validation includes context in error message."""
        class TestModel(BaseModel, ValidationMixin):
            pass

        model = TestModel()

        with pytest.raises(CredentialValidationError) as exc_info:
            model.validate_credentials(
                username=None,
                password="password",
                context="Database",
            )

        assert "Database username is not set" in str(exc_info.value)


@pytest.mark.unit
class TestValidationMixinURLParts:
    """Tests for validate_url_parts method."""

    def test_valid_host_passes(self) -> None:
        """Test validation passes with valid host."""
        VM.validate_url_parts(host="localhost")
        VM.validate_url_parts(host="api.example.com")
        VM.validate_url_parts(host="192.168.1.1")

    def test_missing_host_fails(self) -> None:
        """Test validation fails when host is missing."""
        with pytest.raises(ServerConfigurationError) as exc_info:
            VM.validate_url_parts(host=None)

        assert "host is not set in configuration" in str(exc_info.value)
        assert exc_info.value.field == "host"

    def test_empty_host_fails(self) -> None:
        """Test validation fails when host is empty."""
        with pytest.raises(ServerConfigurationError):
            VM.validate_url_parts(host="   ")

    def test_valid_port_passes(self) -> None:
        """Test validation passes with valid port."""
        VM.validate_url_parts(host="localhost", port=8000)
        VM.validate_url_parts(host="localhost", port=1)
        VM.validate_url_parts(host="localhost", port=65535)

    def test_port_out_of_range_high(self) -> None:
        """Test validation fails when port > 65535."""
        with pytest.raises(ServerConfigurationError) as exc_info:
            VM.validate_url_parts(host="localhost", port=65536)

        assert "port must be between 1 and 65535" in str(exc_info.value)

    def test_port_out_of_range_low(self) -> None:
        """Test validation fails when port < 1."""
        with pytest.raises(ServerConfigurationError) as exc_info:
            VM.validate_url_parts(host="localhost", port=0)

        assert "port must be between 1 and 65535" in str(exc_info.value)

    def test_port_wrong_type(self) -> None:
        """Test validation fails with non-integer port."""
        with pytest.raises(ServerConfigurationError):
            VM.validate_url_parts(host="localhost", port="8080")  # type: ignore[arg-type]

    def test_none_port_passes(self) -> None:
        """Test validation passes with None port (optional)."""
        VM.validate_url_parts(host="localhost", port=None)

    def test_with_context(self) -> None:
        """Test validation includes context in error message."""
        with pytest.raises(ServerConfigurationError) as exc_info:
            VM.validate_url_parts(host=None, context="Redis")

        assert "Redis host is not set" in str(exc_info.value)


@pytest.mark.unit
class TestValidationMixinOneOfRequired:
    """Tests for validate_one_of_required method."""

    def test_one_value_set_passes(self) -> None:
        """Test validation passes when at least one field is set."""
        VM.validate_one_of_required(
            field_names=["host", "url"],
            values=["localhost", None],
        )

        VM.validate_one_of_required(
            field_names=["host", "url"],
            values=[None, "https://api.example.com"],
        )

    def test_all_values_set_passes(self) -> None:
        """Test validation passes when all fields are set."""
        VM.validate_one_of_required(
            field_names=["host", "url"],
            values=["localhost", "https://api.example.com"],
        )

    def test_no_values_set_fails(self) -> None:
        """Test validation fails when all fields are None/empty."""
        with pytest.raises(ServerConfigurationError) as exc_info:
            VM.validate_one_of_required(
                field_names=["host", "url"],
                values=[None, None],
            )

        assert "At least one of [host, url] is required" in str(exc_info.value)
        assert exc_info.value.field == "multiple_fields"

    def test_empty_strings_not_counted(self) -> None:
        """Test validation fails with only empty strings."""
        with pytest.raises(ServerConfigurationError):
            VM.validate_one_of_required(
                field_names=["field1", "field2"],
                values=["  ", "  "],
            )

    def test_with_context(self) -> None:
        """Test validation includes context in error message."""
        with pytest.raises(ServerConfigurationError) as exc_info:
            VM.validate_one_of_required(
                field_names=["option_a", "option_b"],
                values=[None, None],
                context="Configuration",
            )

        assert "Configuration: At least one of [option_a, option_b] is required" in str(
            exc_info.value
        )

    def test_mismatched_lengths_raise_valueerror(self) -> None:
        """Test ValueError when field_names and values lengths differ."""
        with pytest.raises(ValueError, match="field_names and values must have same length"):
            VM.validate_one_of_required(
                field_names=["field1", "field2"],
                values=["value1"],
            )


@pytest.mark.unit
class TestValidationMixinIntegration:
    """Integration tests for ValidationMixin with real models."""

    def test_model_with_validation_mixin(self) -> None:
        """Test ValidationMixin works with Pydantic models."""

        class ServerSettings(BaseModel, ValidationMixin):
            username: str
            password: str
            host: str
            port: int | None = None

        settings = ServerSettings(
            username="admin",
            password="securepassword123",
            host="localhost",
        )

        # Validate credentials
        settings.validate_credentials(
            username=settings.username,
            password=settings.password,
        )

        # Validate URL parts
        settings.validate_url_parts(
            host=settings.host,
            port=settings.port,
        )

    def test_model_validation_chain(self) -> None:
        """Test multiple validations in sequence."""

        class AppConfig(BaseModel, ValidationMixin):
            api_key: str
            api_secret: str
            endpoint: str

        config = AppConfig(
            api_key="key-1234567890",
            api_secret="secret-1234567890",
            endpoint="https://api.example.com",
        )

        # Chain validations
        config.validate_required_field("api_key", config.api_key)
        config.validate_required_field("api_secret", config.api_secret)
        config.validate_min_length("api_key", config.api_key, min_length=10)
        config.validate_url_parts(host=config.endpoint)
