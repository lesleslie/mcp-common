"""Request-scoped Principal storage via contextvars.

Used by BearerTokenMiddleware to attach a Principal to a request, and by
@require_auth to read it. Tests use seed_principal to inject without
going through the middleware.
"""
from __future__ import annotations

from contextvars import ContextVar, Token

from mcp_common.auth.principal import Principal

_principal_var: ContextVar[Principal | None] = ContextVar(
    "mcp_common.auth.principal", default=None
)


def seed_principal(principal: Principal) -> Token[Principal | None]:
    """Set the current Principal in this request's context.

    Returns a Token so the caller can restore the previous value via
    ``token.var.reset(token)``. Typically used by BearerTokenMiddleware
    after verifying a token, and by tests to inject a Principal directly.
    """
    return _principal_var.set(principal)


def _current_principal() -> Principal | None:
    """Return the current Principal, or None if not set."""
    return _principal_var.get()


def _clear_principal() -> None:
    """Reset the current Principal to None."""
    _principal_var.set(None)