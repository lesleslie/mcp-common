from mcp_common.auth.exceptions import (
    AuthError,
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
