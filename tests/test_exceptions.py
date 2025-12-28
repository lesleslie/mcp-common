from mcp_common.exceptions import (
    APIKeyFormatError,
    APIKeyLengthError,
    APIKeyMissingError,
    DependencyMissingError,
    ServerConfigurationError,
    ServerInitializationError,
)


def test_server_configuration_error_fields() -> None:
    err = ServerConfigurationError("bad config", field="token", value="nope")

    assert err.field == "token"
    assert err.value == "nope"
    assert str(err) == "bad config"


def test_server_initialization_error_fields() -> None:
    err = ServerInitializationError("init failed", component="db", details="timeout")

    assert err.component == "db"
    assert err.details == "timeout"
    assert str(err) == "init failed"


def test_dependency_missing_error_fields() -> None:
    err = DependencyMissingError("missing", dependency="fastmcp", install_command="uv add fastmcp")

    assert err.dependency == "fastmcp"
    assert err.install_command == "uv add fastmcp"


def test_api_key_errors_attach_metadata() -> None:
    missing = APIKeyMissingError("no key", field="OPENAI_API_KEY", provider="openai")
    format_err = APIKeyFormatError(
        "bad format",
        field="OPENAI_API_KEY",
        provider="openai",
        expected_format="sk-...",
        example="sk-***",
    )
    length_err = APIKeyLengthError(
        "bad length",
        field="OPENAI_API_KEY",
        min_length=8,
        max_length=64,
        actual_length=4,
    )

    assert missing.provider == "openai"
    assert format_err.expected_format == "sk-..."
    assert format_err.example == "sk-***"
    assert length_err.min_length == 8
    assert length_err.max_length == 64
    assert length_err.actual_length == 4
