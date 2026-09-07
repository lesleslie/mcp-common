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


class AuthenticationRequiredError(AuthError):
    """Raised when a tool requires authentication but no Principal is in Context.

    Maps to HTTP 401 (Unauthorized) in the error_handling middleware translation.
    Use this when @require_auth(allow_anonymous=False) is invoked without a
    Principal seeded by BearerTokenMiddleware (or by a test via seed_principal()).
    """
