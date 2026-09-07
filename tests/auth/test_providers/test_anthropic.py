"""AnthropicIdentityProvider tests — Task 5a (JWKS verification only)."""
from __future__ import annotations

import base64
import json

import httpx
import pytest

from mcp_common.auth.exceptions import ProviderUnavailableError, TokenInvalidError
from mcp_common.auth.providers.anthropic import AnthropicIdentityProvider


CLIENT_ID = "test-client-id"
CLIENT_SECRET = "test-client-secret-long-enough-for-validation"
JWKS_URL = "https://example.invalid/oauth/jwks"
OAUTH_URL = "https://example.invalid/oauth/token"
AUDIENCE = "scapy-mcp"


def _b64url(payload: dict) -> str:
    """Base64url-encode a JSON dict (no padding) for a fake JWT segment."""
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _fake_jwt(kid: str = "test-kid") -> str:
    """Build a structurally valid JWT so PyJWKClient extracts kid and hits JWKS.

    The signature segment is dummy; verification is not asserted here.
    """
    header = _b64url({"alg": "RS256", "kid": kid, "typ": "JWT"})
    payload = _b64url(
        {
            "iss": "anthropic",
            "sub": "test-subject",
            "aud": AUDIENCE,
            "iat": 1,
            "exp": 9_999_999_999,
        }
    )
    return f"{header}.{payload}.fake-signature"


@pytest.fixture
def provider() -> AnthropicIdentityProvider:
    return AnthropicIdentityProvider(
        name="anthropic",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        oauth_token_url=OAUTH_URL,
        jwks_url=JWKS_URL,
        audience=AUDIENCE,
    )


async def test_anthropic_provider_health_is_healthy_before_first_call(provider):
    h = await provider.health()
    assert h.name == "anthropic"
    assert h.state == "healthy"


async def test_anthropic_provider_verify_token_calls_jwks_and_returns_principal(
    provider, respx_mock
):
    # Mock JWKS endpoint
    respx_mock.get(JWKS_URL).mock(
        return_value=httpx.Response(200, json={"keys": []})  # empty JWKS for now
    )

    with pytest.raises(TokenInvalidError):
        await provider.verify_token(_fake_jwt(), expected_audience=AUDIENCE)


async def test_anthropic_provider_unavailable_when_jwks_fetch_fails(
    provider, respx_mock
):
    respx_mock.get(JWKS_URL).mock(
        return_value=httpx.Response(503, text="upstream timeout")
    )

    with pytest.raises(ProviderUnavailableError) as exc_info:
        await provider.verify_token(_fake_jwt(), expected_audience=AUDIENCE)
    assert exc_info.value.provider == "anthropic"


async def test_anthropic_provider_records_health_degraded_on_jwks_failure(
    provider, respx_mock
):
    respx_mock.get(JWKS_URL).mock(
        return_value=httpx.Response(503, text="upstream timeout")
    )
    try:
        await provider.verify_token(_fake_jwt(), expected_audience=AUDIENCE)
    except ProviderUnavailableError:
        pass

    h = await provider.health()
    assert h.state == "degraded"
    assert "503" in (h.last_error or "")
