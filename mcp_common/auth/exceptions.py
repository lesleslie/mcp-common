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


class ProviderUnavailableError(AuthError):
    """Raised when an IdentityProvider cannot be reached (network, 5xx, timeout).

    Attributes:
        provider: Name of the unavailable provider (e.g. "anthropic").
        message: Human-readable error description.
    """

    def __init__(self, message: str, *, provider: str | None = None) -> None:
        super().__init__(message)
        self.provider = provider
