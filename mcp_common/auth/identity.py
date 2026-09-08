"""Identity primitives — service identity dataclass + startup validator.

Task 7: the legacy ``KNOWN_SERVICES`` frozenset is gone. Trust is now
expressed per-server via :attr:`AuthConfig.trusted_issuers` (default-deny
in the providers and in the middleware) and configured at startup via
:func:`validate_auth_config`. The free-function ``verify_issuer`` that
referenced ``KNOWN_SERVICES`` was deleted; :meth:`JWTIdentityProvider.verify_token`
and :meth:`AnthropicIdentityProvider.verify_token` now enforce the
per-server allow-list directly, with a defense-in-depth check in
:meth:`BearerTokenMiddleware.on_request` against ``AuthConfig.trusted_issuers``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mcp_common.auth.exceptions import AudienceMismatchError


@dataclass(frozen=True)
class ServiceIdentity:
    """Static metadata for a Bodai service in the ecosystem.

    Task 7: this dataclass is retained for callers that wanted to enumerate
    well-known services for documentation/CLI purposes, but the runtime
    auth layer no longer reads from it. Use :attr:`AuthConfig.trusted_issuers`
    for the actual allow-list.
    """

    name: str
    port: int
    secret_env_var: str


@dataclass(frozen=True)
class IdentityProviderSpec:
    """Configuration shape for a single identity provider.

    Task 7: the broker keeps a dict of these on :class:`AuthConfig`
    (``identity_providers``). The :func:`validate_auth_config` startup
    helper enforces that OAuth providers carry the credentials they need
    and that the ``type`` field matches a known provider kind. A ``type``
    of ``"jwt"`` requires the parent :class:`AuthConfig` to have a
    ``secret``; a ``type`` of ``"oauth"`` requires every OAuth field on
    this dataclass to be set.
    """

    type: Literal["jwt", "oauth", "anthropic"] = "jwt"
    # OAuth / Anthropic-specific fields. All optional; validate_auth_config
    # fails at startup when an OAuth provider is missing any of these.
    client_id: str | None = None
    client_secret: str | None = None
    oauth_token_url: str | None = None
    jwks_url: str | None = None
    audience: str | None = None


def verify_audience(claimed: str, expected: str) -> None:
    """Raise ``AudienceMismatchError`` when ``claimed != expected``.

    Kept as a free function so the few direct callers (websocket auth,
    legacy scripts) can validate audience without instantiating a provider.
    """
    if claimed != expected:
        raise AudienceMismatchError(
            f"Token audience {claimed!r} does not match service {expected!r}"
        )


def validate_auth_config(auth_config: object) -> None:
    """Fail-loud at startup if auth config is inconsistent.

    B6 fix (Task 7): if ``enabled=True``, ``trusted_issuers`` MUST be
    non-empty. A misconfigured deployment with empty ``trusted_issuers``
    and the default-deny semantics would reject every token — we surface
    that at startup rather than at the first request.

    api-security R2-6 fix (Task 7): an OAuth-shaped provider must carry
    every OAuth credential; the runtime would otherwise fail-loud on
    every request (annoying) or succeed against a default-deny OAuth
    endpoint (worse).
    """
    enabled = getattr(auth_config, "enabled", False)
    if not enabled:
        return

    trusted = tuple(getattr(auth_config, "trusted_issuers", ()) or ())
    if not trusted:
        raise ValueError(
            "auth.enabled=True but trusted_issuers is empty. "
            "Default-deny rejects all issuers. Configure at least one "
            "trusted issuer in settings/<service>.yaml or disable auth."
        )

    identity_providers = getattr(auth_config, "identity_providers", None)
    if not identity_providers:
        # The sibling-server wiring (BearerTokenMiddleware) is constructed
        # from a dict, so this is the right gate. When the sibling server
        # didn't register any providers, fail at startup so the operator
        # doesn't end up with anonymous middleware.
        raise ValueError("auth.enabled=True but no identity_providers configured.")

    default_provider = getattr(auth_config, "default_provider", None)
    if default_provider and default_provider not in identity_providers:
        raise ValueError(
            f"auth.default_provider={default_provider!r} is not in "
            f"identity_providers keys: {sorted(identity_providers.keys())}"
        )

    auth_secret = getattr(auth_config, "resolved_secret", None)
    for name, spec in identity_providers.items():
        provider_type = getattr(spec, "type", "jwt")
        if provider_type == "jwt" and not auth_secret:
            raise ValueError(
                f"identity_providers[{name!r}] is type=jwt but auth.secret is not set"
            )
        # api-security R2-6: an OAuth provider needs every credential —
        # otherwise token-exchange fails on every request or, worse, a
        # default-deny OAuth endpoint accidentally accepts an empty token.
        if provider_type == "oauth":
            required_oauth_fields = (
                "client_id",
                "client_secret",
                "oauth_token_url",
                "jwks_url",
                "audience",
            )
            missing: list[str] = [
                field_name
                for field_name in required_oauth_fields
                if not getattr(spec, field_name, None)
            ]
            if missing:
                raise ValueError(
                    f"identity_providers[{name!r}] is type=oauth but is "
                    f"missing required fields: {', '.join(missing)}. Set "
                    f"them in settings/<service>.yaml or disable this "
                    f"provider."
                )


__all__ = [
    "IdentityProviderSpec",
    "ServiceIdentity",
    "validate_auth_config",
    "verify_audience",
]
