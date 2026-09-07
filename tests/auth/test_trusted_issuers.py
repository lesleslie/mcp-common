"""Task 7: trusted_issuers enforcement in JWTIdentityProvider (B6 default-deny).

The JWT provider now rejects any token whose ``iss`` claim is not in the
configured ``trusted_issuers`` allow-list. The middleware startup check
(see ``validate_auth_config``) ensures the operator configures a non-empty
allow-list when ``auth.enabled=True``; the per-request check is
defense-in-depth.
"""
from __future__ import annotations

import pytest

from mcp_common.auth.config import AuthConfig
from mcp_common.auth.core import JWTIdentityProvider
from mcp_common.auth.exceptions import UnknownIssuerError
from mcp_common.auth.permissions import Permission


SECRET = "trusted-issuers-test-secret-long-enough-abc"


@pytest.mark.asyncio
async def test_unknown_issuer_rejected():
    """An issuer not in trusted_issuers must raise UnknownIssuerError.

    The provider was constructed WITHOUT ``trusted_issuers`` — this is the
    default-deny (B6) case: any non-empty JWT must be rejected, because an
    empty allow-list allows nothing.
    """
    config = AuthConfig(
        enabled=True,
        secret_env_var="TRUSTED_ISSUERS_TEST_SECRET",
        service_name="test-service",
        trusted_issuers=["mahavishnu"],  # not "rogue-service"
    )
    # Provider has NO trusted_issuers set (default-deny semantics).
    provider = JWTIdentityProvider(name="jwt", secret=SECRET)
    token = provider.issue_token(
        issuer="rogue-service",
        audience="test-service",
        permissions=[Permission.READ],
        subject="attacker",
    )
    with pytest.raises(UnknownIssuerError):
        await provider.verify_token(token, expected_audience="test-service")


@pytest.mark.asyncio
async def test_trusted_issuer_accepted():
    """A trusted issuer must verify successfully and surface the issuer."""
    config = AuthConfig(
        enabled=True,
        secret_env_var="TRUSTED_ISSUERS_TEST_SECRET",
        service_name="test-service",
        trusted_issuers=["mahavishnu", "session-buddy"],
    )
    # Provider MUST see "session-buddy" in its allow-list for this to pass.
    provider = JWTIdentityProvider(
        name="jwt",
        secret=SECRET,
        trusted_issuers=list(config.trusted_issuers),
    )
    token = provider.issue_token(
        issuer="session-buddy",
        audience="test-service",
        permissions=[Permission.READ],
        subject="legit",
    )
    principal = await provider.verify_token(token, expected_audience="test-service")
    assert principal.issuer == "session-buddy"
