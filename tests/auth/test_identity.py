"""Tests for the mcp_common.auth.identity module (Task 7).

The legacy ``KNOWN_SERVICES`` frozenset and ``verify_issuer`` function were
removed; trust is now per-server via ``AuthConfig.trusted_issuers`` and
enforced inside ``JWTIdentityProvider.verify_token`` /
``AnthropicIdentityProvider.verify_token`` (default-deny). The startup
helper ``validate_auth_config`` is the operator-facing check.
"""
from __future__ import annotations

import pytest

from mcp_common.auth.exceptions import AudienceMismatchError
from mcp_common.auth.identity import (
    IdentityProviderSpec,
    ServiceIdentity,
    validate_auth_config,
    verify_audience,
)


def test_service_identity_is_a_frozen_dataclass():
    """ServiceIdentity is kept as a documentation/CLI helper, not as an
    enforcement primitive. Verify it's still constructible."""
    ident = ServiceIdentity(name="test", port=1234, secret_env_var="X")
    assert ident.name == "test"
    assert ident.port == 1234
    assert ident.secret_env_var == "X"


def test_identity_provider_spec_defaults_to_jwt():
    spec = IdentityProviderSpec()
    assert spec.type == "jwt"


def test_identity_provider_spec_oauth_carries_optional_fields():
    spec = IdentityProviderSpec(
        type="oauth",
        client_id="cid",
        client_secret="secret",
        oauth_token_url="https://example.com/token",
        jwks_url="https://example.com/jwks",
        audience="aud",
    )
    assert spec.type == "oauth"
    assert spec.client_id == "cid"
    assert spec.client_secret == "secret"


def test_verify_audience_passes_when_matches():
    verify_audience(claimed="session-buddy", expected="session-buddy")


def test_verify_audience_raises_when_mismatch():
    with pytest.raises(AudienceMismatchError):
        verify_audience(claimed="akosha", expected="session-buddy")


# --- validate_auth_config (Task 7) ---


class _FakeAuthConfig:
    """Minimal stand-in AuthConfig that ``validate_auth_config`` accepts.

    The real AuthConfig takes many constructor args (secret_env_var, default_provider,
    identity_providers, etc.). Tests of ``validate_auth_config`` only need the
    attributes the function reads.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        trusted_issuers=(),
        default_provider: str | None = None,
        identity_providers: dict | None = None,
        secret: str | None = None,
    ) -> None:
        self._enabled = enabled
        self._trusted_issuers = trusted_issuers
        self._default_provider = default_provider
        self._identity_providers = identity_providers or {}
        self._secret = secret

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def trusted_issuers(self):
        return tuple(self._trusted_issuers)

    @property
    def default_provider(self):
        return self._default_provider

    @property
    def identity_providers(self):
        return self._identity_providers


def test_validate_skips_when_disabled():
    cfg = _FakeAuthConfig(enabled=False, trusted_issuers=())
    validate_auth_config(cfg)  # no raise


def test_validate_rejects_empty_trusted_issuers_when_enabled():
    cfg = _FakeAuthConfig(
        enabled=True,
        trusted_issuers=(),
        identity_providers={"p": IdentityProviderSpec(type="jwt")},
        secret="a" * 32,
    )
    with pytest.raises(ValueError, match="trusted_issuers is empty"):
        validate_auth_config(cfg)


def test_validate_rejects_no_identity_providers_when_enabled():
    cfg = _FakeAuthConfig(
        enabled=True,
        trusted_issuers=("mahavishnu",),
        identity_providers={},
    )
    with pytest.raises(ValueError, match="no identity_providers"):
        validate_auth_config(cfg)


def test_validate_rejects_default_provider_not_in_dict():
    cfg = _FakeAuthConfig(
        enabled=True,
        trusted_issuers=("mahavishnu",),
        identity_providers={"p": IdentityProviderSpec(type="jwt")},
        default_provider="missing",
        secret="a" * 32,
    )
    with pytest.raises(ValueError, match="default_provider"):
        validate_auth_config(cfg)


def test_validate_rejects_jwt_provider_without_secret():
    cfg = _FakeAuthConfig(
        enabled=True,
        trusted_issuers=("mahavishnu",),
        identity_providers={"p": IdentityProviderSpec(type="jwt")},
        secret=None,
    )
    with pytest.raises(ValueError, match="type=jwt but auth.secret"):
        validate_auth_config(cfg)


def test_validate_rejects_oauth_provider_missing_fields():
    cfg = _FakeAuthConfig(
        enabled=True,
        trusted_issuers=("mahavishnu",),
        identity_providers={
            "anthropic": IdentityProviderSpec(
                type="oauth",
                client_id="cid",
                # client_secret deliberately missing
                oauth_token_url="https://example.com/token",
                jwks_url="https://example.com/jwks",
                audience="aud",
            )
        },
    )
    with pytest.raises(ValueError, match="client_secret"):
        validate_auth_config(cfg)


def test_validate_passes_for_correctly_configured_jwt():
    cfg = _FakeAuthConfig(
        enabled=True,
        trusted_issuers=("mahavishnu",),
        identity_providers={"p": IdentityProviderSpec(type="jwt")},
        default_provider="p",
        secret="a" * 32,
    )
    validate_auth_config(cfg)  # no raise


def test_validate_passes_for_correctly_configured_oauth():
    cfg = _FakeAuthConfig(
        enabled=True,
        trusted_issuers=("mahavishnu",),
        identity_providers={
            "anthropic": IdentityProviderSpec(
                type="oauth",
                client_id="cid",
                client_secret="secret",
                oauth_token_url="https://example.com/token",
                jwks_url="https://example.com/jwks",
                audience="aud",
            )
        },
        default_provider="anthropic",
    )
    validate_auth_config(cfg)  # no raise
