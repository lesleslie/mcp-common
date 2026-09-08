"""IdentityProvider Protocol + ProviderHealth."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from mcp_common.auth.principal import Principal

ProviderState = Literal["healthy", "degraded", "dead"]


@dataclass(frozen=True)
class ProviderHealth:
    """Health snapshot of a single IdentityProvider."""

    name: str
    state: ProviderState = "healthy"
    last_check_at: datetime | None = None
    last_error: str | None = None


@runtime_checkable
class IdentityProvider(Protocol):
    """Protocol for token-issuing identity providers.

    Concrete implementations include JWTIdentityProvider (inter-service) and
    AnthropicIdentityProvider (human-facing, OAuth 2.0 + PKCE).
    """

    name: str

    async def verify_token(
        self,
        token: str,
        *,
        expected_audience: str | None = None,
    ) -> Principal:
        """Verify a token, return Principal on success.

        Raises AuthError subclass on failure.
        """
        ...

    async def health(self) -> ProviderHealth:
        """Return current health for /health aggregation."""
        ...
