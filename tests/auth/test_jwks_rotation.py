"""Tests for JWKS rotation/TTL behavior on AnthropicIdentityProvider.

Task 12 plan-mandated requirements:
1. JWKS cache expiration logic (after ``jwks_cache_seconds``)
2. Public ``force_refresh()`` method (LOW-6 fix)
3. Test bypass uses the public API (no reaching into private state)
4. Existing tests still pass

These tests use ``respx`` to count network calls. The cache-hit test
resets the call count after a priming fetch and verifies that a
subsequent ``verify_token`` within the TTL does NOT re-fetch. The
cache-miss test uses the public ``provider.force_refresh()`` to
simulate TTL expiry, then verifies the next call does re-fetch.
"""
from __future__ import annotations

import base64
import json

import httpx
import pytest

from mcp_common.auth.exceptions import ProviderUnavailableError, TokenInvalidError
from mcp_common.auth.providers.anthropic import AnthropicIdentityProvider


CLIENT_ID = "rotation-test-client"
CLIENT_SECRET = "rotation-test-client-secret-long-enough"
JWKS_URL = "https://example.invalid/jwks"
OAUTH_URL = "https://example.invalid/oauth/token"
AUDIENCE = "rotation-test-audience"


def _b64url(payload: dict[str, str]) -> str:
    """Base64url-encode a JSON dict without padding (JWT-style)."""
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()


def _fake_jwt(kid: str = "test-kid") -> str:
    """Build a syntactically valid 3-segment JWT with the given kid in the header.

    The signature segment is meaningless — we only need ``jwt.get_unverified_header``
    to succeed so execution reaches ``_get_keys`` and the network call is exercised.
    All three segments must decode as valid base64url (length 4n / 4n+2 / 4n+3
    after padding) — PyJWT's ``_load`` validates each segment before returning the
    header, so an invalid segment prevents the JWKS lookup from ever running.
    """
    header = _b64url({"alg": "RS256", "typ": "JWT", "kid": kid})
    payload = _b64url({"iss": "test", "sub": "test", "aud": AUDIENCE})
    sig = _b64url({"sig": "fake"})
    return f"{header}.{payload}.{sig}"


@pytest.fixture
def provider() -> AnthropicIdentityProvider:
    return AnthropicIdentityProvider(
        name="anthropic",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        oauth_token_url=OAUTH_URL,
        jwks_url=JWKS_URL,
        audience=AUDIENCE,
        jwks_cache_seconds=60,
    )


@pytest.mark.asyncio
async def test_jwks_cache_hit_skips_network(provider, respx_mock):
    """First call hits network; second call within TTL uses cache."""
    respx_mock.get(JWKS_URL).mock(return_value=httpx.Response(200, json={"keys": []}))

    # First call: cache miss → network
    try:
        await provider.verify_token(_fake_jwt(), expected_audience=AUDIENCE)
    except (TokenInvalidError, ProviderUnavailableError):
        pass  # expected — we only care about network access

    # Reset call count to isolate the second-call behavior
    respx_mock.get(JWKS_URL).reset()

    # Second call within cache TTL: should not hit network
    try:
        await provider.verify_token(_fake_jwt(), expected_audience=AUDIENCE)
    except (TokenInvalidError, ProviderUnavailableError):
        pass

    assert respx_mock.get(JWKS_URL).call_count == 0, (
        "cache should prevent network hit within TTL"
    )


@pytest.mark.asyncio
async def test_jwks_cache_miss_after_force_refresh(provider, respx_mock):
    """After ``force_refresh()``, next call hits network again.

    Per plan requirement #3 the test bypass uses the PUBLIC
    ``force_refresh()`` API rather than mutating ``_jwks_cache_seconds``.
    """
    respx_mock.get(JWKS_URL).mock(return_value=httpx.Response(200, json={"keys": []}))

    # First call hits network
    try:
        await provider.verify_token(_fake_jwt(), expected_audience=AUDIENCE)
    except (TokenInvalidError, ProviderUnavailableError):
        pass

    # Public API: simulate cache-TTL expiry
    provider.force_refresh()

    # Second call after force_refresh → hits network again
    try:
        await provider.verify_token(_fake_jwt(), expected_audience=AUDIENCE)
    except (TokenInvalidError, ProviderUnavailableError):
        pass

    assert respx_mock.get(JWKS_URL).call_count == 2


@pytest.mark.asyncio
async def test_force_refresh_resets_cache_without_network(provider, respx_mock):
    """``force_refresh()`` itself does not perform network I/O.

    It only resets the cache state; the next ``verify_token`` is what
    refetches.
    """
    respx_mock.get(JWKS_URL).mock(return_value=httpx.Response(200, json={"keys": []}))

    # Prime the cache
    try:
        await provider.verify_token(_fake_jwt(), expected_audience=AUDIENCE)
    except (TokenInvalidError, ProviderUnavailableError):
        pass

    respx_mock.get(JWKS_URL).reset()

    # The reset itself must not hit the network
    provider.force_refresh()
    assert respx_mock.get(JWKS_URL).call_count == 0
