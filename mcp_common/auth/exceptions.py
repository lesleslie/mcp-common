from __future__ import annotations


class AuthError(Exception):
    pass


class TokenExpiredError(AuthError):
    pass


class TokenInvalidError(AuthError):
    pass


class UnknownIssuerError(AuthError):
    pass


class AudienceMismatchError(AuthError):
    pass


class InsufficientPermissionError(AuthError):
    pass


class SecretNotConfiguredError(AuthError):
    pass
