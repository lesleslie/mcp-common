---
title: mcp-common Auth Design
date: 2026-09-07
status: implemented
audience: mcp-common contributors, sibling-server maintainers
related:
  - https://github.com/lesleslie/mahavishnu/blob/main/docs/superpowers/specs/2026-09-06-mcp-common-auth-primitives-design.md (canonical spec)
---

# mcp-common Auth Design

## What this package does

`mcp_common/auth/` provides authentication primitives for Bodai MCP servers. It
implements the design documented at
`mahavishnu/docs/superpowers/specs/2026-09-06-mcp-common-auth-primitives-design.md`.

The package is **internal** — consumers should import from `mcp_common.auth.*`
directly (deep imports). Public-API graduation (re-export from `mcp_common/__init__.py`)
is a future spec after the surface has been used in production by at least one
sibling server.

## Components

- **`Principal`** — frozen dataclass representing an authenticated identity.
- **`IdentityProvider` Protocol** — runtime-checkable Protocol with `verify_token`
  and `health` methods.
- **`JWTIdentityProvider`** — concrete provider using HS256 JWT (the existing
  inter-service auth path, extracted from the free-function `verify_token`).
- **`AnthropicIdentityProvider`** — concrete provider using OAuth 2.0 + PKCE + JWKS.
- **`BearerTokenMiddleware`** — FastMCP middleware that reads `Authorization: Bearer`
  from the ASGI scope and stashes a Principal on the request-scoped Context.
- **`@require_auth`** — decorator that reads Principal from Context and enforces
  the requested permission.
- **`AuthConfig`** — settings surface integrated into `MCPServerSettings.auth`.
- **`AuthHealth`** — wiring-discipline §3 four-signal feed observability surfaced
  via the `/health` envelope.

## Usage

### Wiring BearerTokenMiddleware in a server's lifespan

```python
from mcp_common.auth.config import AuthConfig
from mcp_common.auth.core import JWTIdentityProvider
from mcp_common.auth.exceptions import SecretNotConfiguredError
from mcp_common.auth.health import AuthHealth
from mcp_common.auth.identity import validate_auth_config  # B6 fix: startup check
from mcp_common.auth.middleware import BearerTokenMiddleware
from mcp_common.auth.providers.anthropic import AnthropicIdentityProvider


def build_middleware(auth_config: AuthConfig) -> BearerTokenMiddleware:
    # B6 fix: fail-loud at startup if auth config is inconsistent
    validate_auth_config(auth_config)

    # AuthConfig.secret is a property that raises SecretNotConfiguredError
    # when resolved_secret is None. Capture the resolved value once so the
    # providers below reuse it without re-triggering the property.
    try:
        secret = auth_config.secret
    except SecretNotConfiguredError:
        raise RuntimeError(
            "auth.secret is required when auth.enabled=True"
        )

    # identity_providers may be None; default-deny is enforced by the
    # providers themselves via auth_config.trusted_issuers.
    providers: dict[str, object] = {}
    identity_providers = auth_config.identity_providers or {}
    if "jwt" in identity_providers:
        providers["jwt"] = JWTIdentityProvider(
            name="jwt",
            secret=secret,
            trusted_issuers=auth_config.trusted_issuers,
        )
    if anthropic_cfg := identity_providers.get("anthropic"):
        if anthropic_cfg.client_secret is None:
            raise RuntimeError(
                "identity_providers['anthropic'].client_secret is required"
            )
        providers["anthropic"] = AnthropicIdentityProvider(
            client_id=anthropic_cfg.client_id,
            client_secret=anthropic_cfg.client_secret,
            oauth_token_url=anthropic_cfg.oauth_token_url,
            jwks_url=anthropic_cfg.jwks_url,
            audience=anthropic_cfg.audience or auth_config.service_name,
            trusted_issuers=auth_config.trusted_issuers,
        )
    return BearerTokenMiddleware(auth_config=auth_config, providers=providers)
```

### Decorating a tool

```python
from mcp_common.auth.decorator import require_auth
from mcp_common.auth.permissions import Permission


@require_auth(permission=Permission.WRITE)
async def my_tool(...):
    ...
```

### Testing with seed_principal

```python
from mcp_common.auth.context import seed_principal
from mcp_common.auth.principal import Principal
from mcp_common.auth.permissions import Permission


def test_my_tool():
    principal = Principal(
        issuer="test",
        subject="user-1",
        permissions=frozenset({Permission.WRITE}),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        raw_claims={},
    )
    token_handle = seed_principal(principal)
    try:
        result = await my_tool()
    finally:
        token_handle.var.reset(token_handle)
```

## What's NOT here

- Other OAuth/OIDC providers (Google, GitHub, etc.) — future IdPs add incrementally
  via the IdentityProvider Protocol.
- mTLS / cert-based auth — deferred to v2.
- Federated identity / SAML — out of scope.

## Migration notes (from prior convention)

Prior versions of `@require_auth` accepted a `__auth_token__` kwarg for token
injection. This convention is gone. New code uses `seed_principal(...)` for tests
and middleware for production traffic. There is no deprecation window — the
package had zero production consumers at the time of this change.
