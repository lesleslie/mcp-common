"""AnthropicIdentityProvider — Task 5a: JWKS verification only.

B11 fix: This module verifies Anthropic-issued access tokens. The OAuth
authorization-code flow, PKCE code_verifier generation, and refresh-token
rotation are deferred to Task 5b (follow-up spec) and live in a separate
module (mcp_common/auth/providers/anthropic_oauth.py).

Implementation note: we use a httpx-based JWKS fetcher (not
``jwt.PyJWKClient``) because PyJWKClient uses urllib3 internally, which
makes it incompatible with the project's standard httpx mocking
(respx). This keeps the provider testable through the same httpx boundary
the rest of mcp-common uses.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import httpx
import jwt

from mcp_common.auth.exceptions import (
    ProviderUnavailableError,
    TokenInvalidError,
    UnknownIssuerError,
)
from mcp_common.auth.permissions import Permission
from mcp_common.auth.principal import Principal
from mcp_common.auth.provider import (
    IdentityProvider,
    ProviderHealth,
    ProviderState,
)


class _JwksCache:
    """Tiny async JWKS fetcher backed by httpx with a TTL cache.

    Mirrors the responsibilities of ``jwt.PyJWKClient`` (fetch by URL,
    match by ``kid``, cache with a lifespan) but uses ``httpx.AsyncClient``
    so the rest of the project's HTTP mocking surface (``respx``) applies.

    Distinguishes two failure modes:
    - ``PyJWKClientError`` for transport / HTTP / parse errors (caller maps
      to ``ProviderUnavailableError``).
    - ``jwt.InvalidTokenError`` when the token header is malformed or no
      matching key exists in a successfully-fetched JWKS (caller maps to
      ``TokenInvalidError``).
    """

    def __init__(
        self,
        jwks_url: str,
        *,
        lifespan: int = 3600,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._jwks_url = jwks_url
        self._lifespan = lifespan
        self._timeout = timeout_seconds
        self._client = httpx.AsyncClient(timeout=timeout_seconds)
        self._fetched_at: float = 0.0
        self._keys: dict[str, dict[str, Any]] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_signing_key(self, token: str) -> Any:
        """Return a key object usable by ``jwt.decode`` for ``token``."""
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            raise jwt.InvalidTokenError(f"Invalid token header: {exc}") from exc

        kid = header.get("kid")
        if not kid:
            raise jwt.InvalidTokenError("Token header missing 'kid'")

        keys = await self._get_keys()
        jwk = keys.get(kid)
        if jwk is None:
            raise jwt.InvalidTokenError(f"No JWK for kid={kid!r}")
        return jwt.algorithms.RSAAlgorithm.from_jwk(jwk)

    async def _get_keys(self) -> dict[str, dict[str, Any]]:
        now = time.monotonic()
        # Cache is valid when a fetch has happened (``_fetched_at > 0``) AND
        # the elapsed time is within ``self._lifespan``. Checking only
        # ``self._keys`` would re-fetch every call when the JWKS returns an
        # empty ``keys`` list — defeating ``jwks_cache_seconds`` for the
        # common case where the upstream JWKS rotates and the new set
        # excludes our cached ``kid``.
        if self._fetched_at > 0 and (now - self._fetched_at) < self._lifespan:
            return self._keys

        try:
            response = await self._client.get(self._jwks_url)
        except httpx.HTTPError as exc:
            raise jwt.PyJWKClientError(
                f"JWKS fetch failed: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise jwt.PyJWKClientError(
                f"JWKS fetch failed: HTTP {response.status_code}"
            )

        try:
            payload = response.json()
        except (ValueError, TypeError) as exc:
            raise jwt.PyJWKClientError(f"JWKS response not JSON: {exc}") from exc

        raw_keys = payload.get("keys", [])
        self._keys = {k["kid"]: k for k in raw_keys if "kid" in k}
        self._fetched_at = now
        return self._keys

    def reset_cache(self) -> None:
        """Force the next ``get_signing_key`` call to refetch from the JWKS URL.

        Public API for the upstream provider's ``force_refresh()`` and for
        tests that need to simulate cache-TTL expiry without reaching into
        private state. Mirrors the LOW-6 fix originally designed for
        ``PyJWKClient.__init__`` reinit.
        """
        self._fetched_at = 0.0
        self._keys = {}


class AnthropicIdentityProvider:
    """IdentityProvider for Anthropic-issued JWTs (5a: JWKS verify only).

    B7 fix: default-deny in _extract_permissions — empty scope/permissions
    returns []. B6 fix: trusted_issuers enforced (default-deny on empty).
    """

    def __init__(
        self,
        *,
        name: str = "anthropic",
        client_id: str,
        client_secret: str,
        oauth_token_url: str,
        jwks_url: str,
        audience: str,
        trusted_issuers: list[str] | None = None,
        jwks_cache_seconds: int = 3600,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.name = name
        self._client_id = client_id
        self._client_secret = client_secret
        self._oauth_token_url = oauth_token_url
        self._jwks_url = jwks_url
        self._audience = audience
        self._timeout = timeout_seconds
        self._trusted_issuers: list[str] = trusted_issuers or []
        self._jwks_client = _JwksCache(
            jwks_url,
            lifespan=jwks_cache_seconds,
            timeout_seconds=timeout_seconds,
        )
        self._last_error: str | None = None
        # LOW-5 fix (Task 5): import ProviderState directly instead of
        # reaching into ProviderHealth.__annotations__["state"] at runtime.
        # Mirrors the Task 12 fix so both providers use the same type for
        # the _last_state field.
        self._last_state: ProviderState = "healthy"

    async def aclose(self) -> None:
        await self._jwks_client.aclose()

    async def __aenter__(self) -> AnthropicIdentityProvider:
        return self

    def force_refresh(self) -> None:
        """Reset the cached JWKS so the next ``verify_token`` refetches.

        LOW-6 fix: this is the public API used by callers and tests that
        need to simulate JWKS cache-TTL expiry without reaching into the
        underlying cache's private state.
        """
        self._jwks_client.reset_cache()

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def verify_token(
        self,
        token: str,
        *,
        expected_audience: str | None = None,
    ) -> Principal:
        audience = expected_audience or self._audience
        try:
            signing_key = await self._jwks_client.get_signing_key(token)
        except jwt.PyJWKClientError as exc:
            # Transport / HTTP / parse failure — JWKS server unavailable.
            self._last_error = f"JWKS fetch failed: {exc}"
            self._last_state = "degraded"
            raise ProviderUnavailableError(
                f"JWKS fetch failed: {exc}", provider=self.name
            ) from exc
        except jwt.InvalidTokenError as exc:
            # Token header malformed or kid not in fetched JWKS —
            # the token is the problem, not the provider.
            raise TokenInvalidError(f"Invalid token: {exc}") from exc

        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=audience,
                options={"require": ["exp", "iat", "iss", "aud"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenInvalidError("Token expired") from exc
        except jwt.InvalidAudienceError as exc:
            raise TokenInvalidError(f"Audience mismatch: {exc}") from exc
        except jwt.InvalidTokenError as exc:
            raise TokenInvalidError(f"Invalid token: {exc}") from exc

        # B6 fix: trusted-issuers allow-list (default-deny — empty list
        # rejects all issuers, see Task 7 startup check).
        if payload.get("iss") not in self._trusted_issuers:
            raise UnknownIssuerError(
                f"Issuer '{payload.get('iss')}' not in trusted_issuers: "
                f"{self._trusted_issuers}"
            )

        self._last_state = "healthy"
        self._last_error = None

        return Principal(
            issuer=payload["iss"],
            subject=payload.get("sub", "unknown"),
            permissions=frozenset(self._extract_permissions(payload)),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
            raw_claims=payload,
        )

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            name=self.name,
            state=self._last_state,
            last_check_at=datetime.now(UTC),
            last_error=self._last_error,
        )

    def _extract_permissions(self, payload: dict[str, Any]) -> list[Permission]:
        """B7 fix: default-deny — empty scope/permissions returns [].

        Anthropic OAuth uses a 'scope' claim (space-separated) plus a custom
        'permissions' array. We use exact-match scope checking (no substring
        'in' which is exploitable — e.g., "read" in "read:admin").
        """
        scope_value = payload.get("scope", "")
        scopes = set(scope_value.split()) if isinstance(scope_value, str) else set()
        permissions: list[Permission] = []
        # Exact match against known scope tokens (no substring matching)
        if "read" in scopes or "read:mcp" in scopes:
            permissions.append(Permission.READ)
        if "write" in scopes or "write:mcp" in scopes:
            permissions.append(Permission.WRITE)
        if "admin" in scopes or "admin:mcp" in scopes:
            permissions.append(Permission.ADMIN)
        for p in payload.get("permissions", []):
            try:
                permissions.append(Permission(p))
            except ValueError:
                # Unknown permission value — fail closed. (B7 fix: do NOT
                # silently coerce to READ; let an empty result deny.)
                pass
        return permissions  # Default-deny: returns [] on empty scope
