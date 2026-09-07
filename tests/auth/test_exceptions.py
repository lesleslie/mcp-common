from mcp_common.auth.exceptions import (
    AuthError,
    ProviderUnavailableError,
    TokenExpiredError,
    TokenInvalidError,
    UnknownIssuerError,
    AudienceMismatchError,
    InsufficientPermissionError,
    SecretNotConfiguredError,
)


def test_auth_error_hierarchy():
    assert issubclass(TokenExpiredError, AuthError)
    assert issubclass(TokenInvalidError, AuthError)
    assert issubclass(UnknownIssuerError, AuthError)
    assert issubclass(AudienceMismatchError, AuthError)
    assert issubclass(InsufficientPermissionError, AuthError)
    assert issubclass(SecretNotConfiguredError, AuthError)


def test_auth_error_message():
    err = TokenExpiredError("token expired")
    assert str(err) == "token expired"


def test_provider_unavailable_error_inherits_from_auth_error():
    err = ProviderUnavailableError("Anthropic OAuth endpoint returned 503")
    assert isinstance(err, AuthError)
    assert "Anthropic OAuth endpoint returned 503" in str(err)


def test_provider_unavailable_error_includes_provider_name_attribute():
    err = ProviderUnavailableError("timeout", provider="anthropic")
    assert err.provider == "anthropic"  # type: ignore[attr-defined]
