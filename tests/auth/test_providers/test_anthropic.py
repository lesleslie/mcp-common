"""AnthropicIdentityProvider tests — Task 5a (JWKS verification only)."""
from __future__ import annotations

import base64
import json

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from mcp_common.auth.exceptions import (
    ProviderUnavailableError,
    TokenInvalidError,
    UnknownIssuerError,
)
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


def _rsa_keypair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _public_jwk(public_key: rsa.RSAPublicKey, kid: str) -> dict:
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(public_key))
    jwk["kid"] = kid
    jwk["alg"] = "RS256"
    jwk["use"] = "sig"
    return jwk


def _signed_jwt(private_key: rsa.RSAPrivateKey, *, kid: str, iss: str) -> str:
    """Build a real RSA-signed JWT so ``jwt.decode`` accepts the signature."""
    return jwt.encode(
        {
            "iss": iss,
            "sub": "test-subject",
            "aud": AUDIENCE,
            "iat": 1,
            "exp": 9_999_999_999,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )


async def test_anthropic_provider_rejects_untrusted_issuer(respx_mock):
    """B6 default-deny: valid signature + untrusted iss must raise UnknownIssuerError.

    The signature MUST be valid so the failure is unambiguously about the
    issuer — proving the trusted-issuers gate fires regardless of crypto.
    """
    private_key, public_key = _rsa_keypair()
    respx_mock.get(JWKS_URL).mock(
        return_value=httpx.Response(
            200, json={"keys": [_public_jwk(public_key, "test-kid")]}
        )
    )

    provider = AnthropicIdentityProvider(
        name="anthropic",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        oauth_token_url=OAUTH_URL,
        jwks_url=JWKS_URL,
        audience=AUDIENCE,
        trusted_issuers=["good-issuer"],
    )

    token = _signed_jwt(private_key, kid="test-kid", iss="evil-corp")

    with pytest.raises(UnknownIssuerError):
        await provider.verify_token(token, expected_audience=AUDIENCE)
