"""B-R2-3 fix: tests patch fastmcp.server.dependencies.get_http_headers to inject
test headers instead of using a scope-based MockContext. The middleware reads
headers via get_http_headers() (B1 fix); there is no request context in unit
tests, so we patch the dependency."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from mcp_common.auth.config import AuthConfig
from mcp_common.auth.context import _clear_principal, _current_principal
from mcp_common.auth.exceptions import TokenInvalidError
from mcp_common.auth.middleware import BearerTokenMiddleware
from mcp_common.auth.permissions import Permission
from mcp_common.auth.principal import Principal
from mcp_common.auth.provider import ProviderHealth


class MockContext:
    """Minimal MiddlewareContext stand-in. B-R2-3 fix: NO scope attribute;
    headers are injected via monkeypatch on get_http_headers() instead.
    """

    def __init__(self, method: str = "tools/call", message=None) -> None:
        self.method = method
        self.message = message
        self.fastmcp_context = None  # contextvars is the source of truth in tests


class MockProvider:
    def __init__(
        self,
        *,
        principal: Principal | None = None,
        raises: Exception | None = None,
        name: str = "mock",
    ) -> None:
        self._principal = principal
        self._raises = raises
        self._name = name
        self.verify_calls: list[str] = []

    @property
    def name(self) -> str:
        return self._name

    async def verify_token(self, token: str, *, expected_audience: str | None = None):
        self.verify_calls.append(token)
        if self._raises is not None:
            raise self._raises
        return self._principal

    async def health(self):
        return ProviderHealth(name=self.name, state="healthy")


@pytest.fixture(autouse=True)
def _reset_context():
    _clear_principal()
    yield
    _clear_principal()


@pytest.fixture
def patch_headers(monkeypatch):
    """Return a setter that monkey-patches get_http_headers for the test."""

    def _set(headers: dict[str, str]) -> None:
        from fastmcp.server import dependencies

        monkeypatch.setattr(dependencies, "get_http_headers", lambda: headers)

    return _set


@pytest.mark.asyncio
async def test_middleware_passes_through_when_no_authorization_header(patch_headers):
    config = AuthConfig(enabled=True, service_name="test-service")
    principal = Principal(
        issuer="test",
        subject="u",
        permissions=frozenset({Permission.READ}),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        raw_claims={},
    )
    provider = MockProvider(principal=principal)
    mw = BearerTokenMiddleware(auth_config=config, providers={"mock": provider})

    called_with: list[Any] = []

    async def call_next(ctx):
        called_with.append(ctx)
        return "ok"

    patch_headers({})  # No Authorization header
    result = await mw.on_request(MockContext(), call_next)
    assert result == "ok"
    assert len(called_with) == 1
    # No token → provider.verify_token NOT called
    assert provider.verify_calls == []


@pytest.mark.asyncio
async def test_middleware_extracts_bearer_token_and_verifies(patch_headers):
    config = AuthConfig(enabled=True, service_name="test-service")
    principal = Principal(
        issuer="test",
        subject="u",
        permissions=frozenset({Permission.READ}),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        raw_claims={},
    )
    provider = MockProvider(principal=principal)
    mw = BearerTokenMiddleware(auth_config=config, providers={"mock": provider})

    async def call_next(ctx):
        # Principal should be set during call_next
        assert _current_principal() is principal
        return "ok"

    patch_headers({"authorization": "Bearer abc.def.ghi"})
    result = await mw.on_request(MockContext(), call_next)
    assert result == "ok"
    assert provider.verify_calls == ["abc.def.ghi"]


@pytest.mark.asyncio
async def test_middleware_clears_principal_after_call_next(patch_headers):
    config = AuthConfig(enabled=True, service_name="test-service")
    principal = Principal(
        issuer="test",
        subject="u",
        permissions=frozenset({Permission.READ}),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        raw_claims={},
    )
    provider = MockProvider(principal=principal)
    mw = BearerTokenMiddleware(auth_config=config, providers={"mock": provider})

    async def call_next(ctx):
        return "ok"

    patch_headers({"authorization": "Bearer token123"})
    await mw.on_request(MockContext(), call_next)
    assert _current_principal() is None


@pytest.mark.asyncio
async def test_middleware_raises_auth_error_on_invalid_token(patch_headers):
    """B-R2-4 fix: assert TokenInvalidError specifically — not Exception.
    The OLD plan used pytest.raises((HTTPException, ToolError, Exception))
    which matches anything and would not have verified the B2 fix
    (AuthError, not HTTPException)."""
    config = AuthConfig(enabled=True, service_name="test-service")
    provider = MockProvider(raises=TokenInvalidError("bad token"))
    mw = BearerTokenMiddleware(auth_config=config, providers={"mock": provider})

    async def call_next(ctx):
        return "ok"

    patch_headers({"authorization": "Bearer token123"})
    with pytest.raises(TokenInvalidError):
        await mw.on_request(MockContext(), call_next)


@pytest.mark.asyncio
async def test_middleware_bypasses_initialize_handshake(patch_headers):
    """I-1 fix: 'initialize' method must bypass auth (MCP handshake)."""
    config = AuthConfig(enabled=True, service_name="test-service")
    provider = MockProvider(raises=TokenInvalidError("would fail if not bypassed"))
    mw = BearerTokenMiddleware(auth_config=config, providers={"mock": provider})

    async def call_next(ctx):
        return "ok"

    patch_headers({"authorization": "Bearer token123"})
    # Even with a token, initialize should pass through without verify
    result = await mw.on_request(MockContext(method="initialize"), call_next)
    assert result == "ok"
    assert provider.verify_calls == []


@pytest.mark.asyncio
async def test_middleware_bypasses_ping_keepalive(patch_headers):
    """I-1 fix: 'ping' method must bypass auth (spec allows keepalive without auth)."""
    config = AuthConfig(enabled=True, service_name="test-service")
    provider = MockProvider(raises=TokenInvalidError("would fail if not bypassed"))
    mw = BearerTokenMiddleware(auth_config=config, providers={"mock": provider})

    async def call_next(ctx):
        return "ok"

    patch_headers({"authorization": "Bearer token123"})
    result = await mw.on_request(MockContext(method="ping"), call_next)
    assert result == "ok"
    assert provider.verify_calls == []


@pytest.mark.asyncio
async def test_middleware_increments_verifications_counter_on_success(patch_headers):
    """B3 fix prep: verifications_total must increment on successful verify."""
    config = AuthConfig(enabled=True, service_name="test-service")
    principal = Principal(
        issuer="test",
        subject="u",
        permissions=frozenset({Permission.READ}),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        raw_claims={},
    )
    provider = MockProvider(principal=principal)
    mw = BearerTokenMiddleware(auth_config=config, providers={"mock": provider})

    async def call_next(ctx):
        return "ok"

    assert mw.verifications_total == 0
    patch_headers({"authorization": "Bearer token1"})
    await mw.on_request(MockContext(), call_next)
    assert mw.verifications_total == 1

    patch_headers({"authorization": "Bearer token2"})
    await mw.on_request(MockContext(), call_next)
    assert mw.verifications_total == 2
    assert mw.errors_total == 0


@pytest.mark.asyncio
async def test_middleware_increments_errors_counter_on_auth_error(patch_headers):
    """B3 fix prep: errors_total must increment on AuthError."""
    config = AuthConfig(enabled=True, service_name="test-service")
    provider = MockProvider(raises=TokenInvalidError("bad token"))
    mw = BearerTokenMiddleware(auth_config=config, providers={"mock": provider})

    async def call_next(ctx):
        return "ok"

    assert mw.errors_total == 0
    patch_headers({"authorization": "Bearer token1"})
    with pytest.raises(TokenInvalidError):
        await mw.on_request(MockContext(), call_next)
    assert mw.errors_total == 1
    assert mw.verifications_total == 0


@pytest.mark.asyncio
async def test_middleware_does_not_call_provider_when_principal_already_set(
    patch_headers,
):
    """Idempotency: if a Principal is already in context (test injection /
    internal hop), skip verify."""
    config = AuthConfig(enabled=True, service_name="test-service")
    provider = MockProvider(raises=TokenInvalidError("would fail if called"))
    mw = BearerTokenMiddleware(auth_config=config, providers={"mock": provider})

    existing = Principal(
        issuer="upstream",
        subject="u",
        permissions=frozenset({Permission.READ}),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        raw_claims={},
    )

    async def call_next(ctx):
        return "ok"

    # Seed principal before the request
    from mcp_common.auth.context import seed_principal

    seed_principal(existing)
    try:
        result = await mw.on_request(MockContext(), call_next)
        assert result == "ok"
        assert provider.verify_calls == []
    finally:
        _clear_principal()


@pytest.mark.asyncio
async def test_middleware_skips_verify_when_get_http_headers_raises_runtimeerror(
    monkeypatch,
):
    """M-R2-1 fix: bare RuntimeError around get_http_headers is non-fatal
    (stdio / non-HTTP transport passes through)."""
    from fastmcp.server import dependencies

    config = AuthConfig(enabled=True, service_name="test-service")
    provider = MockProvider(raises=TokenInvalidError("would fail if called"))
    mw = BearerTokenMiddleware(auth_config=config, providers={"mock": provider})

    def _raise():
        raise RuntimeError("no active request")

    monkeypatch.setattr(dependencies, "get_http_headers", _raise)

    async def call_next(ctx):
        return "ok"

    # Should pass through without raising and without calling the provider.
    result = await mw.on_request(MockContext(), call_next)
    assert result == "ok"
    assert provider.verify_calls == []


@pytest.mark.asyncio
async def test_middleware_rejects_oversized_token(patch_headers):
    """Defense in depth: reject Authorization header values over 8192 bytes."""
    config = AuthConfig(enabled=True, service_name="test-service")
    provider = MockProvider(raises=TokenInvalidError("would fail if called"))
    mw = BearerTokenMiddleware(auth_config=config, providers={"mock": provider})

    async def call_next(ctx):
        return "ok"

    oversized = "x" * 8193
    patch_headers({"authorization": f"Bearer {oversized}"})
    result = await mw.on_request(MockContext(), call_next)
    assert result == "ok"
    assert provider.verify_calls == []


@pytest.mark.asyncio
async def test_middleware_ignores_non_bearer_scheme(patch_headers):
    """Only Authorization: Bearer is honored; Basic / Digest / custom schemes
    pass through anonymously."""
    config = AuthConfig(enabled=True, service_name="test-service")
    provider = MockProvider(raises=TokenInvalidError("would fail if called"))
    mw = BearerTokenMiddleware(auth_config=config, providers={"mock": provider})

    async def call_next(ctx):
        return "ok"

    patch_headers({"authorization": "Basic dXNlcjpwYXNz"})
    result = await mw.on_request(MockContext(), call_next)
    assert result == "ok"
    assert provider.verify_calls == []


@pytest.mark.asyncio
async def test_middleware_skips_empty_bearer_token(patch_headers):
    """`Authorization: Bearer ` (no token after the scheme) is treated as
    anonymous — pass through without verify."""
    config = AuthConfig(enabled=True, service_name="test-service")
    provider = MockProvider(raises=TokenInvalidError("would fail if called"))
    mw = BearerTokenMiddleware(auth_config=config, providers={"mock": provider})

    async def call_next(ctx):
        return "ok"

    patch_headers({"authorization": "Bearer "})
    result = await mw.on_request(MockContext(), call_next)
    assert result == "ok"
    assert provider.verify_calls == []


class _RecordingAuditLogger:
    """Audit logger stub with log_success/log_failure methods (the middleware
    checks ``hasattr`` for these names; the canonical AuditLogger does NOT
    expose them, so the middleware falls back silently when wired with the
    canonical logger)."""

    def __init__(self) -> None:
        self.success_calls: list[dict] = []
        self.failure_calls: list[dict] = []

    def log_success(self, **kwargs) -> None:
        self.success_calls.append(kwargs)

    def log_failure(self, **kwargs) -> None:
        self.failure_calls.append(kwargs)


@pytest.mark.asyncio
async def test_middleware_calls_audit_logger_log_success_on_valid_token(patch_headers):
    """When wired with an audit logger that exposes log_success, the
    middleware invokes it with issuer / subject."""
    config = AuthConfig(enabled=True, service_name="test-service")
    principal = Principal(
        issuer="test-issuer",
        subject="test-subject",
        permissions=frozenset({Permission.READ}),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        raw_claims={},
    )
    provider = MockProvider(principal=principal)
    audit = _RecordingAuditLogger()
    mw = BearerTokenMiddleware(
        auth_config=config,
        providers={"mock": provider},
        audit_logger=audit,
    )

    async def call_next(ctx):
        return "ok"

    patch_headers({"authorization": "Bearer good.token"})
    await mw.on_request(MockContext(), call_next)

    assert len(audit.success_calls) == 1
    call = audit.success_calls[0]
    assert call["source"] == "middleware"
    assert call["principal_issuer"] == "test-issuer"
    assert call["principal_subject"] == "test-subject"


@pytest.mark.asyncio
async def test_middleware_calls_audit_logger_log_failure_on_auth_error(patch_headers):
    """When wired with an audit logger that exposes log_failure, the
    middleware invokes it on AuthError."""
    config = AuthConfig(enabled=True, service_name="test-service")
    provider = MockProvider(raises=TokenInvalidError("bad token"))
    audit = _RecordingAuditLogger()
    mw = BearerTokenMiddleware(
        auth_config=config,
        providers={"mock": provider},
        audit_logger=audit,
    )

    async def call_next(ctx):
        return "ok"

    patch_headers({"authorization": "Bearer bad.token"})
    with pytest.raises(TokenInvalidError):
        await mw.on_request(MockContext(), call_next)

    assert len(audit.failure_calls) == 1
    call = audit.failure_calls[0]
    assert call["source"] == "middleware"
    assert call["reason"] == "TokenInvalidError"
    assert call["token_present"] is True


class _MockFastMCPContext:
    """FastMCP-shaped Context stub supporting set_state / get_state / delete_state."""

    def __init__(self) -> None:
        self.state: dict[str, Any] = {}
        self.set_calls: list[tuple[str, Any]] = []
        self.get_calls: list[str] = []
        self.delete_calls: list[str] = []
        self.raise_on_set: Exception | None = None

    def get_state(self, key: str) -> Any:
        self.get_calls.append(key)
        return self.state.get(key)

    def set_state(self, key: str, value: Any, *, serializable: bool = True) -> None:
        self.set_calls.append((key, value))
        if self.raise_on_set is not None:
            raise self.raise_on_set
        self.state[key] = value

    def delete_state(self, key: str) -> None:
        self.delete_calls.append(key)
        self.state.pop(key, None)


@pytest.mark.asyncio
async def test_middleware_seeds_principal_into_fmcp_context(patch_headers):
    """When the MiddlewareContext carries a fastmcp_context, the middleware
    also stashes Principal there for FastMCP-native consumers."""
    config = AuthConfig(enabled=True, service_name="test-service")
    principal = Principal(
        issuer="test",
        subject="u",
        permissions=frozenset({Permission.READ}),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        raw_claims={},
    )
    provider = MockProvider(principal=principal)
    fmcp = _MockFastMCPContext()
    mw = BearerTokenMiddleware(auth_config=config, providers={"mock": provider})

    ctx = MockContext()
    ctx.fastmcp_context = fmcp

    captured: dict[str, Any] = {}

    async def call_next(ctx_arg):
        captured["state"] = fmcp.state.copy()
        return "ok"

    patch_headers({"authorization": "Bearer good.token"})
    result = await mw.on_request(ctx, call_next)
    assert result == "ok"
    # Principal was set during call_next
    assert captured["state"].get("principal") is principal
    # After call_next, the prior state (None, absent) is restored — so the
    # key is removed via delete_state.
    assert "principal" not in fmcp.state
    assert fmcp.delete_calls == ["principal"]


@pytest.mark.asyncio
async def test_middleware_restores_prior_fmcp_state(patch_headers):
    """When fmcp_context has a prior principal, the middleware restores it."""
    config = AuthConfig(enabled=True, service_name="test-service")
    incoming_principal = Principal(
        issuer="incoming",
        subject="in",
        permissions=frozenset({Permission.READ}),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        raw_claims={},
    )
    prior_principal = Principal(
        issuer="prior",
        subject="pr",
        permissions=frozenset({Permission.READ}),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        raw_claims={},
    )
    provider = MockProvider(principal=incoming_principal)
    fmcp = _MockFastMCPContext()
    # Seed prior state
    fmcp.state["principal"] = prior_principal
    mw = BearerTokenMiddleware(auth_config=config, providers={"mock": provider})

    ctx = MockContext()
    ctx.fastmcp_context = fmcp

    async def call_next(ctx_arg):
        assert fmcp.state["principal"] is incoming_principal
        return "ok"

    patch_headers({"authorization": "Bearer good.token"})
    await mw.on_request(ctx, call_next)
    # After call_next, the prior principal is restored.
    assert fmcp.state["principal"] is prior_principal


@pytest.mark.asyncio
async def test_middleware_continues_when_fmcp_set_state_fails(patch_headers):
    """If fmcp_context.set_state raises, the middleware logs and continues
    via contextvars (the source of truth)."""
    config = AuthConfig(enabled=True, service_name="test-service")
    principal = Principal(
        issuer="test",
        subject="u",
        permissions=frozenset({Permission.READ}),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        raw_claims={},
    )
    provider = MockProvider(principal=principal)
    fmcp = _MockFastMCPContext()
    fmcp.raise_on_set = TypeError("not serializable")
    mw = BearerTokenMiddleware(auth_config=config, providers={"mock": provider})

    ctx = MockContext()
    ctx.fastmcp_context = fmcp

    async def call_next(ctx_arg):
        # contextvars still has the principal even when set_state fails
        assert _current_principal() is principal
        return "ok"

    patch_headers({"authorization": "Bearer good.token"})
    result = await mw.on_request(ctx, call_next)
    assert result == "ok"


def test_select_provider_uses_default_provider_hint():
    """When AuthConfig.default_provider matches a registered provider, it is
    selected without ambiguity even if multiple providers are present."""
    config = AuthConfig(
        enabled=True,
        service_name="test",
        default_provider="primary",
    )
    a = MockProvider(name="primary")
    b = MockProvider(name="secondary")
    mw = BearerTokenMiddleware(
        auth_config=config, providers={"primary": a, "secondary": b}
    )
    assert mw._select_provider("anything") is a


def test_select_provider_falls_back_to_single_provider():
    """When only one provider is configured (no default_provider), it is used."""
    config = AuthConfig(enabled=True, service_name="test")
    provider = MockProvider()
    mw = BearerTokenMiddleware(
        auth_config=config, providers={"only": provider}
    )
    assert mw._select_provider("anything") is provider


def test_select_provider_raises_when_multiple_and_no_default():
    """When multiple providers are configured but default_provider is unset,
    _select_provider raises RuntimeError at request time."""
    config = AuthConfig(enabled=True, service_name="test")
    a = MockProvider()
    b = MockProvider()
    mw = BearerTokenMiddleware(
        auth_config=config, providers={"a": a, "b": b}
    )
    with pytest.raises(RuntimeError, match="Multiple providers"):
        mw._select_provider("anything")
