"""Tests for MCP Server Exception Hierarchy."""

from __future__ import annotations

import pytest

from mcp_common.exceptions import (
    APIKeyFormatError,
    APIKeyLengthError,
    APIKeyMissingError,
    CredentialValidationError,
    DependencyMissingError,
    MCPServerError,
    ServerConfigurationError,
    ServerInitializationError,
)


@pytest.mark.unit
class TestMCPServerError:
    """Tests for base MCPServerError exception."""

    def test_mcp_server_error_is_base_exception(self) -> None:
        """Test MCPServerError is the base for all MCP exceptions."""
        error = MCPServerError("Base error")

        assert isinstance(error, Exception)
        assert str(error) == "Base error"

    def test_all_exceptions_inherit_from_base(self) -> None:
        """Test all custom exceptions inherit from MCPServerError."""
        exceptions = [
            ServerConfigurationError("test"),
            ServerInitializationError("test"),
            DependencyMissingError("test"),
            CredentialValidationError("test"),
            APIKeyMissingError("test"),
            APIKeyFormatError("test"),
            APIKeyLengthError("test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, MCPServerError)


@pytest.mark.unit
class TestServerConfigurationError:
    """Tests for ServerConfigurationError exception."""

    def test_basic_configuration_error(self) -> None:
        """Test basic configuration error."""
        error = ServerConfigurationError(message="Configuration is invalid")

        assert str(error) == "Configuration is invalid"
        assert error.field is None
        assert error.value is None

    def test_configuration_error_with_field(self) -> None:
        """Test configuration error with field context."""
        error = ServerConfigurationError(
            message="Port is invalid",
            field="port",
        )

        assert error.field == "port"
        assert "Port is invalid" in str(error)

    def test_configuration_error_with_value(self) -> None:
        """Test configuration error with value context."""
        error = ServerConfigurationError(
            message="Port out of range",
            field="port",
            value="70000",
        )

        assert error.field == "port"
        assert error.value == "70000"

    def test_configuration_error_all_attributes(self) -> None:
        """Test configuration error with all attributes."""
        error = ServerConfigurationError(
            message="Invalid timeout value",
            field="timeout",
            value="-5",
        )

        assert str(error) == "Invalid timeout value"
        assert error.field == "timeout"
        assert error.value == "-5"


@pytest.mark.unit
class TestServerInitializationError:
    """Tests for ServerInitializationError exception."""

    def test_basic_initialization_error(self) -> None:
        """Test basic initialization error."""
        error = ServerInitializationError(message="Failed to start server")

        assert str(error) == "Failed to start server"
        assert error.component is None
        assert error.details is None

    def test_initialization_error_with_component(self) -> None:
        """Test initialization error with component context."""
        error = ServerInitializationError(
            message="Component failed to initialize",
            component="database",
        )

        assert error.component == "database"
        assert "Component failed to initialize" in str(error)

    def test_initialization_error_with_details(self) -> None:
        """Test initialization error with technical details."""
        error = ServerInitializationError(
            message="Database connection failed",
            component="database",
            details="Connection timeout after 30s",
        )

        assert error.component == "database"
        assert error.details == "Connection timeout after 30s"

    def test_initialization_error_all_attributes(self) -> None:
        """Test initialization error with all attributes."""
        error = ServerInitializationError(
            message="Logger initialization failed",
            component="logger",
            details="Permission denied on /var/log/server.log",
        )

        assert "Logger initialization failed" in str(error)
        assert error.component == "logger"
        assert "Permission denied" in error.details


@pytest.mark.unit
class TestDependencyMissingError:
    """Tests for DependencyMissingError exception."""

    def test_basic_dependency_error(self) -> None:
        """Test basic dependency error."""
        error = DependencyMissingError(message="Required package not installed")

        assert str(error) == "Required package not installed"
        assert error.dependency is None
        assert error.install_command is None

    def test_dependency_error_with_name(self) -> None:
        """Test dependency error with dependency name."""
        error = DependencyMissingError(
            message="Package not found",
            dependency="fastmcp",
        )

        assert error.dependency == "fastmcp"

    def test_dependency_error_with_install_command(self) -> None:
        """Test dependency error with install command."""
        error = DependencyMissingError(
            message="fastmcp is required",
            dependency="fastmcp",
            install_command="uv add fastmcp",
        )

        assert error.dependency == "fastmcp"
        assert error.install_command == "uv add fastmcp"

    def test_dependency_error_all_attributes(self) -> None:
        """Test dependency error with all attributes."""
        error = DependencyMissingError(
            message="onnxruntime is required for inference",
            dependency="onnxruntime",
            install_command="pip install onnxruntime",
        )

        assert "inference" in str(error)
        assert error.dependency == "onnxruntime"
        assert error.install_command == "pip install onnxruntime"


@pytest.mark.unit
class TestCredentialValidationError:
    """Tests for CredentialValidationError exception."""

    def test_basic_credential_error(self) -> None:
        """Test basic credential validation error."""
        error = CredentialValidationError(message="Invalid credentials")

        assert isinstance(error, ServerConfigurationError)
        assert str(error) == "Invalid credentials"

    def test_credential_error_inherits_from_config_error(self) -> None:
        """Test CredentialValidationError inherits from ServerConfigurationError."""
        error = CredentialValidationError(message="Test")

        assert isinstance(error, ServerConfigurationError)
        assert isinstance(error, MCPServerError)


@pytest.mark.unit
class TestAPIKeyMissingError:
    """Tests for APIKeyMissingError exception."""

    def test_basic_api_key_missing(self) -> None:
        """Test basic API key missing error."""
        error = APIKeyMissingError(message="API key not provided")

        assert isinstance(error, CredentialValidationError)
        assert str(error) == "API key not provided"
        assert error.provider is None
        assert error.field is None

    def test_api_key_missing_with_field(self) -> None:
        """Test API key missing with field name."""
        error = APIKeyMissingError(
            message="API key is required",
            field="OPENAI_API_KEY",
        )

        assert error.field == "OPENAI_API_KEY"

    def test_api_key_missing_with_provider(self) -> None:
        """Test API key missing with provider context."""
        error = APIKeyMissingError(
            message="OpenAI API key not found",
            field="OPENAI_API_KEY",
            provider="openai",
        )

        assert error.provider == "openai"
        assert error.field == "OPENAI_API_KEY"

    def test_api_key_missing_inheritance(self) -> None:
        """Test APIKeyMissingError has correct inheritance chain."""
        error = APIKeyMissingError(message="Test")

        assert isinstance(error, APIKeyMissingError)
        assert isinstance(error, CredentialValidationError)
        assert isinstance(error, ServerConfigurationError)
        assert isinstance(error, MCPServerError)


@pytest.mark.unit
class TestAPIKeyFormatError:
    """Tests for APIKeyFormatError exception."""

    def test_basic_api_key_format_error(self) -> None:
        """Test basic API key format error."""
        error = APIKeyFormatError(message="Invalid API key format")

        assert isinstance(error, CredentialValidationError)
        assert str(error) == "Invalid API key format"
        assert error.provider is None
        assert error.expected_format is None
        assert error.example is None

    def test_api_key_format_with_provider(self) -> None:
        """Test API key format error with provider."""
        error = APIKeyFormatError(
            message="Invalid OpenAI API key format",
            field="api_key",
            provider="openai",
        )

        assert error.provider == "openai"
        assert error.field == "api_key"

    def test_api_key_format_with_details(self) -> None:
        """Test API key format error with format details."""
        error = APIKeyFormatError(
            message="API key doesn't match expected pattern",
            field="api_key",
            provider="openai",
            expected_format="sk-{ alphanumeric }",
            example="sk-...abc123",
        )

        assert error.provider == "openai"
        assert error.expected_format == "sk-{ alphanumeric }"
        assert error.example == "sk-...abc123"

    def test_api_key_format_all_attributes(self) -> None:
        """Test API key format error with all attributes."""
        error = APIKeyFormatError(
            message="Mailgun API key format invalid",
            field="MAILGUN_API_KEY",
            provider="mailgun",
            expected_format="key-{ alphanumeric }",
            example="key-1234567890abcdef",
        )

        assert "Mailgun" in str(error)
        assert error.provider == "mailgun"
        assert error.expected_format == "key-{ alphanumeric }"
        assert "1234567890" in error.example


@pytest.mark.unit
class TestAPIKeyLengthError:
    """Tests for APIKeyLengthError exception."""

    def test_basic_api_key_length_error(self) -> None:
        """Test basic API key length error."""
        error = APIKeyLengthError(message="API key is too short")

        assert isinstance(error, CredentialValidationError)
        assert str(error) == "API key is too short"
        assert error.field is None
        assert error.min_length is None
        assert error.max_length is None
        assert error.actual_length is None

    def test_api_key_length_too_short(self) -> None:
        """Test API key length error for too short key."""
        error = APIKeyLengthError(
            message="API key below minimum length",
            field="api_key",
            min_length=20,
            actual_length=10,
        )

        assert error.field == "api_key"
        assert error.min_length == 20
        assert error.actual_length == 10
        assert error.max_length is None

    def test_api_key_length_too_long(self) -> None:
        """Test API key length error for too long key."""
        error = APIKeyLengthError(
            message="API key exceeds maximum length",
            field="api_key",
            max_length=100,
            actual_length=150,
        )

        assert error.field == "api_key"
        assert error.max_length == 100
        assert error.actual_length == 150
        assert error.min_length is None

    def test_api_key_length_with_both_bounds(self) -> None:
        """Test API key length error with both min and max."""
        error = APIKeyLengthError(
            message="API key length out of range",
            field="api_key",
            min_length=20,
            max_length=100,
            actual_length=5,
        )

        assert error.min_length == 20
        assert error.max_length == 100
        assert error.actual_length == 5

    def test_api_key_length_all_attributes(self) -> None:
        """Test API key length error with all attributes."""
        error = APIKeyLengthError(
            message="Invalid API key length",
            field="OPENAI_API_KEY",
            min_length=20,
            max_length=100,
            actual_length=15,
        )

        assert "Invalid API key length" in str(error)
        assert error.field == "OPENAI_API_KEY"
        assert error.min_length == 20
        assert error.max_length == 100
        assert error.actual_length == 15


@pytest.mark.unit
class TestExceptionUsagePatterns:
    """Tests for realistic exception usage patterns."""

    def test_raise_configuration_error(self) -> None:
        """Test raising configuration error in real scenario."""
        with pytest.raises(ServerConfigurationError) as exc_info:
            raise ServerConfigurationError(
                message="Host is not set in configuration",
                field="host",
            )

        error = exc_info.value
        assert error.field == "host"
        assert "Host" in str(error)

    def test_raise_initialization_error(self) -> None:
        """Test raising initialization error in real scenario."""
        with pytest.raises(ServerInitializationError) as exc_info:
            raise ServerInitializationError(
                message="Database connection failed",
                component="database",
                details="Connection timeout after 30s",
            )

        error = exc_info.value
        assert error.component == "database"
        assert "timeout" in error.details

    def test_raise_api_key_missing_error(self) -> None:
        """Test raising API key missing error."""
        with pytest.raises(APIKeyMissingError) as exc_info:
            raise APIKeyMissingError(
                message="OpenAI API key not found",
                field="OPENAI_API_KEY",
                provider="openai",
            )

        error = exc_info.value
        assert error.provider == "openai"
        assert error.field == "OPENAI_API_KEY"

    def test_exception_catching_hierarchy(self) -> None:
        """Test catching exceptions using base classes."""

        def raise_config_error() -> None:
            raise APIKeyMissingError(
                message="API key missing",
                provider="test",
            )

        # Can catch as specific type
        with pytest.raises(APIKeyMissingError):
            raise_config_error()

        # Can catch as credential error
        with pytest.raises(CredentialValidationError):
            raise_config_error()

        # Can catch as config error
        with pytest.raises(ServerConfigurationError):
            raise_config_error()

        # Can catch as base MCP error
        with pytest.raises(MCPServerError):
            raise_config_error()


@pytest.mark.unit
class TestExceptionAttributes:
    """Tests for exception attribute access."""

    def test_configuration_error_attributes_accessible(self) -> None:
        """Test all configuration error attributes are accessible."""
        error = ServerConfigurationError(
            message="Test",
            field="test_field",
            value="test_value",
        )

        assert error.field == "test_field"
        assert error.value == "test_value"

    def test_initialization_error_attributes_accessible(self) -> None:
        """Test all initialization error attributes are accessible."""
        error = ServerInitializationError(
            message="Test",
            component="test_component",
            details="test_details",
        )

        assert error.component == "test_component"
        assert error.details == "test_details"

    def test_api_key_error_attributes_accessible(self) -> None:
        """Test all API key error attributes are accessible."""

        # Format error
        format_error = APIKeyFormatError(
            message="Test",
            provider="test_provider",
            expected_format="test_format",
            example="test_example",
        )
        assert format_error.provider == "test_provider"
        assert format_error.expected_format == "test_format"
        assert format_error.example == "test_example"

        # Length error
        length_error = APIKeyLengthError(
            message="Test",
            min_length=10,
            max_length=100,
            actual_length=5,
        )
        assert length_error.min_length == 10
        assert length_error.max_length == 100
        assert length_error.actual_length == 5
