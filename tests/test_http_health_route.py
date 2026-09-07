"""Tests for the register_http_health_route helper in mcp_common.health.

The helper registers a plain HTTP /health route on a FastMCP server, returning
a JSONResponse with shape:

    {"status": "ok", "service": <service_name>, "version": <version>, "components": [...]}

This is the HTTP counterpart to register_health_tools (which registers MCP
protocol tools). Repos use it from server bootstrap to satisfy the launchd
launch_with_healthcheck.sh wrapper and per-repo /health probes.
"""

from __future__ import annotations

import typing as t

import httpx2 as httpx
import pytest
from fastmcp import FastMCP

from mcp_common.health import register_http_health_route


async def _get_health(mcp: FastMCP, path: str = "/health") -> httpx.Response:
    """Issue a real ASGI request against the FastMCP server.

    Uses httpx.ASGITransport so no socket is opened - this is fast, hermetic,
    and matches the production HTTP layer (Starlette) used by FastMCP.
    """
    app = mcp.http_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        return await client.get(path)


class TestRegisterHttpHealthRoute:
    """Test the register_http_health_route helper."""

    @pytest.mark.asyncio
    async def test_route_registration_returns_200(self) -> None:
        """GET /health returns 200 on a FastMCP instance."""
        mcp = FastMCP(name="test-svc")
        register_http_health_route(mcp, service_name="test-svc", version="1.0.0")

        response = await _get_health(mcp)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_response_is_json_with_canonical_keys(self) -> None:
        """Response body parses as JSON with status, service, version, components."""
        mcp = FastMCP(name="test-svc")
        register_http_health_route(mcp, service_name="test-svc", version="1.0.0")

        response = await _get_health(mcp)

        # Must be parseable as JSON
        body = response.json()
        assert isinstance(body, dict)
        # Must have the canonical keys
        assert set(body.keys()) >= {"status", "service", "version", "components"}

    @pytest.mark.asyncio
    async def test_response_echoes_service_and_version(self) -> None:
        """status is 'ok'; service and version echo the inputs."""
        mcp = FastMCP(name="echo-svc")
        register_http_health_route(
            mcp, service_name="echo-svc", version="0.17.7"
        )

        response = await _get_health(mcp)
        body = response.json()

        assert body["status"] == "ok"
        assert body["service"] == "echo-svc"
        assert body["version"] == "0.17.7"

    @pytest.mark.asyncio
    async def test_components_default_to_empty_list(self) -> None:
        """components defaults to [] when extra_components is omitted."""
        mcp = FastMCP(name="no-components")
        register_http_health_route(
            mcp, service_name="no-components", version="0.0.1"
        )

        response = await _get_health(mcp)
        body = response.json()

        assert body["components"] == []

    @pytest.mark.asyncio
    async def test_components_round_trip_extra_components(self) -> None:
        """components round-trips extra_components when provided."""
        mcp = FastMCP(name="with-components")
        extra: list[dict[str, t.Any]] = [
            {"name": "db", "status": "ok"},
            {"name": "redis", "status": "ok"},
        ]
        register_http_health_route(
            mcp,
            service_name="with-components",
            version="2.0.0",
            extra_components=extra,
        )

        response = await _get_health(mcp)
        body = response.json()

        assert body["components"] == [
            {"name": "db", "status": "ok"},
            {"name": "redis", "status": "ok"},
        ]

    @pytest.mark.asyncio
    async def test_response_content_type_is_application_json(self) -> None:
        """Response content type is application/json."""
        mcp = FastMCP(name="ct-check")
        register_http_health_route(mcp, service_name="ct-check", version="1.2.3")

        response = await _get_health(mcp)

        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type


class TestRegisterHttpHealthRouteWithAuthHealth:
    """Test that the helper accepts auth_health_provider and includes AuthHealth.

    These tests cover Task 11 of the mcp-common auth-primitives plan:
    - I-7 fix: /health stays 200-only; status field reports "ok" or "degraded"
    - B3 fix:  is_degraded is recomputed per request via the callable
    - R2-1 fix: parameter is a Callable, not a captured value
    - R2-2 fix: include_diagnostics=False is the default (last_error redacted)
    """

    @pytest.mark.asyncio
    async def test_auth_components_appear_when_provider_configured(self) -> None:
        """AuthHealth component appears in components[] when callable provided."""
        from datetime import UTC, datetime

        from mcp_common.auth.health import AuthHealth
        from mcp_common.auth.provider import ProviderHealth

        mcp = FastMCP(name="auth-svc")
        auth_health = AuthHealth(
            providers={"jwt": ProviderHealth(name="jwt", state="healthy")},
            verifications_total=5,
            errors_total=0,
            last_successful_verification_at=datetime.now(UTC),
            last_updated_timestamp=datetime.now(UTC),
            cycles_total=1,
        )

        register_http_health_route(
            mcp,
            service_name="auth-svc",
            version="0.0.1",
            auth_health_provider=lambda: auth_health,
        )

        response = await _get_health(mcp)
        body = response.json()

        assert response.status_code == 200
        assert body["status"] == "ok"
        names = [c["name"] for c in body["components"]]
        assert "auth" in names

    @pytest.mark.asyncio
    async def test_degraded_provider_yields_status_degraded(self) -> None:
        """B3 fix: a degraded provider surfaces status='degraded' in body."""
        from datetime import UTC, datetime

        from mcp_common.auth.health import AuthHealth
        from mcp_common.auth.provider import ProviderHealth

        mcp = FastMCP(name="auth-degraded")
        auth_health = AuthHealth(
            providers={
                "jwt": ProviderHealth(name="jwt", state="degraded", last_error="boom"),
            },
            verifications_total=2,
            errors_total=1,
            last_successful_verification_at=None,
            last_updated_timestamp=datetime.now(UTC),
            cycles_total=1,
        )

        register_http_health_route(
            mcp,
            service_name="auth-degraded",
            version="0.0.1",
            auth_health_provider=lambda: auth_health,
        )

        response = await _get_health(mcp)
        body = response.json()

        # I-7 fix: still 200, but body says "degraded"
        assert response.status_code == 200
        assert body["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_provider_called_per_request_not_captured(self) -> None:
        """B3 fix: the callable is invoked on each request (state can flip)."""
        from datetime import UTC, datetime

        from mcp_common.auth.health import AuthHealth
        from mcp_common.auth.provider import ProviderHealth

        mcp = FastMCP(name="auth-flip")

        ts = datetime.now(UTC)
        healthy = AuthHealth(
            providers={"jwt": ProviderHealth(name="jwt", state="healthy")},
            verifications_total=1,
            errors_total=0,
            last_successful_verification_at=ts,
            last_updated_timestamp=ts,
            cycles_total=1,
        )
        degraded = AuthHealth(
            providers={"jwt": ProviderHealth(name="jwt", state="degraded")},
            verifications_total=1,
            errors_total=1,
            last_successful_verification_at=None,
            last_updated_timestamp=ts,
            cycles_total=1,
        )

        current = {"snapshot": healthy}

        def provider() -> AuthHealth:
            return current["snapshot"]

        register_http_health_route(
            mcp,
            service_name="auth-flip",
            version="0.0.1",
            auth_health_provider=provider,
        )

        # Request 1: healthy
        response = await _get_health(mcp)
        assert response.json()["status"] == "ok"

        # Mutate the live snapshot; request 2 must reflect the new state
        current["snapshot"] = degraded
        response = await _get_health(mcp)
        assert response.json()["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_last_error_redacted_by_default(self) -> None:
        """R2-2 fix: include_diagnostics=False default redacts last_error."""
        from datetime import UTC, datetime

        from mcp_common.auth.health import AuthHealth
        from mcp_common.auth.provider import ProviderHealth

        mcp = FastMCP(name="auth-redact")
        auth_health = AuthHealth(
            providers={
                "jwt": ProviderHealth(
                    name="jwt", state="degraded", last_error="internal-uri-leak"
                ),
            },
            verifications_total=1,
            errors_total=1,
            last_successful_verification_at=None,
            last_updated_timestamp=datetime.now(UTC),
            cycles_total=1,
        )

        register_http_health_route(
            mcp,
            service_name="auth-redact",
            version="0.0.1",
            auth_health_provider=lambda: auth_health,
        )

        response = await _get_health(mcp)
        body = response.json()

        # last_error must not leak into the anonymous /health response
        auth_component = next(c for c in body["components"] if c["name"] == "auth")
        jwt_provider = auth_component["providers"]["jwt"]
        assert "last_error" not in jwt_provider


class TestRegisterHttpHealthRouteCoexistence:
    """Test that the helper coexists with register_health_tools without conflict."""

    @pytest.mark.asyncio
    async def test_helper_registers_only_the_health_route(self) -> None:
        """The helper adds /health but does not add /healthz or other aliases."""
        mcp = FastMCP(name="coexist")
        register_http_health_route(mcp, service_name="coexist", version="1.0.0")

        # /health exists
        ok = await _get_health(mcp, "/health")
        assert ok.status_code == 200

        # /healthz is NOT registered by this helper (per the plan: the helper
        # standardizes on /health; excalidraw-mcp's /healthz alias is dropped
        # separately during Wave 2)
        not_found = await _get_health(mcp, "/healthz")
        assert not_found.status_code == 404
