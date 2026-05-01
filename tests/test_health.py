"""Tests for health check infrastructure.

Tests comprehensive health check patterns for MCP servers,
ensuring production-ready health monitoring and status reporting.

Phase 10.1: Production Hardening - Health Check Tests
Extended: HTTP dependency checking, DependencyWaiter, MCP tool registration.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, strategies as st

from mcp_common.health import (
    ComponentHealth,
    DependencyConfig,
    DependencyWaiter,
    HealthCheckResponse,
    HealthCheckResult,
    HealthChecker,
    HealthStatus,
    WaitResult,
    _HttpxFallback,
    register_health_tools,
)


# =============================================================================
# HealthStatus
# =============================================================================


class TestHealthStatus:
    """Test HealthStatus enum."""

    def test_enum_values(self) -> None:
        """Should have correct enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_string_representation(self) -> None:
        """Should convert to string correctly."""
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.DEGRADED == "degraded"
        assert HealthStatus.UNHEALTHY == "unhealthy"
        assert str(HealthStatus.HEALTHY) == "healthy"

    def test_comparison_with_non_status(self) -> None:
        """Should return NotImplemented for non-status comparisons."""
        assert HealthStatus.HEALTHY.__lt__("healthy") is NotImplemented
        assert HealthStatus.HEALTHY.__gt__("healthy") is NotImplemented
        assert HealthStatus.UNHEALTHY.__lt__(42) is NotImplemented
        assert HealthStatus.DEGRADED.__gt__(None) is NotImplemented

    def test_severity_comparison_lt(self) -> None:
        """Should compare by severity (healthy < degraded < unhealthy)."""
        assert HealthStatus.HEALTHY < HealthStatus.DEGRADED
        assert HealthStatus.DEGRADED < HealthStatus.UNHEALTHY
        assert HealthStatus.HEALTHY < HealthStatus.UNHEALTHY

        # Reverse comparisons must be false
        assert not (HealthStatus.DEGRADED < HealthStatus.HEALTHY)
        assert not (HealthStatus.UNHEALTHY < HealthStatus.DEGRADED)
        assert not (HealthStatus.UNHEALTHY < HealthStatus.HEALTHY)

        # Equality is not less-than
        assert not (HealthStatus.HEALTHY < HealthStatus.HEALTHY)
        assert not (HealthStatus.DEGRADED < HealthStatus.DEGRADED)

    def test_severity_comparison_gt(self) -> None:
        """Should support greater-than comparisons."""
        assert HealthStatus.UNHEALTHY > HealthStatus.DEGRADED
        assert HealthStatus.DEGRADED > HealthStatus.HEALTHY
        assert HealthStatus.UNHEALTHY > HealthStatus.HEALTHY

        assert not (HealthStatus.HEALTHY > HealthStatus.DEGRADED)
        assert not (HealthStatus.DEGRADED > HealthStatus.UNHEALTHY)
        assert not (HealthStatus.HEALTHY > HealthStatus.UNHEALTHY)

    def test_gt_with_non_status_returns_not_implemented(self) -> None:
        """Should return NotImplemented when compared with non-HealthStatus via gt."""
        result = HealthStatus.HEALTHY.__gt__("healthy")
        assert result is NotImplemented

        result = HealthStatus.UNHEALTHY.__gt__(123)
        assert result is NotImplemented


# =============================================================================
# ComponentHealth
# =============================================================================


class TestComponentHealth:
    """Test ComponentHealth dataclass."""

    def test_minimal_component(self) -> None:
        """Should create component with minimal fields."""
        component = ComponentHealth(
            name="database",
            status=HealthStatus.HEALTHY,
        )

        assert component.name == "database"
        assert component.status == HealthStatus.HEALTHY
        assert component.message is None
        assert component.latency_ms is None
        assert not component.metadata

    def test_full_component(self) -> None:
        """Should create component with all fields."""
        component = ComponentHealth(
            name="external_api",
            status=HealthStatus.DEGRADED,
            message="High latency detected",
            latency_ms=125.7,
            metadata={"endpoint": "/api/v1/users", "rate_limit_remaining": 50},
        )

        assert component.name == "external_api"
        assert component.status == HealthStatus.DEGRADED
        assert component.message == "High latency detected"
        assert component.latency_ms == 125.7
        assert component.metadata["endpoint"] == "/api/v1/users"
        assert component.metadata["rate_limit_remaining"] == 50

    def test_to_dict_minimal(self) -> None:
        """Should convert minimal component to dict."""
        component = ComponentHealth(
            name="database",
            status=HealthStatus.HEALTHY,
        )

        result = component.to_dict()

        assert result == {
            "name": "database",
            "status": "healthy",
        }
        assert "message" not in result
        assert "latency_ms" not in result
        assert "metadata" not in result

    def test_to_dict_full(self) -> None:
        """Should convert full component to dict with rounding."""
        component = ComponentHealth(
            name="external_api",
            status=HealthStatus.DEGRADED,
            message="High latency",
            latency_ms=125.789,
            metadata={"foo": "bar"},
        )

        result = component.to_dict()

        assert result == {
            "name": "external_api",
            "status": "degraded",
            "message": "High latency",
            "latency_ms": 125.79,  # Rounded to 2 decimals
            "metadata": {"foo": "bar"},
        }

    def test_to_dict_omits_empty_metadata(self) -> None:
        """Should omit metadata key when metadata dict is empty."""
        component = ComponentHealth(name="x", status=HealthStatus.HEALTHY, metadata={})
        result = component.to_dict()
        assert "metadata" not in result


# =============================================================================
# HealthCheckResponse
# =============================================================================


class TestHealthCheckResponse:
    """Test HealthCheckResponse dataclass."""

    def test_create_all_healthy(self) -> None:
        """Should aggregate status as HEALTHY when all components healthy."""
        components = [
            ComponentHealth(name="database", status=HealthStatus.HEALTHY),
            ComponentHealth(name="cache", status=HealthStatus.HEALTHY),
            ComponentHealth(name="api", status=HealthStatus.HEALTHY),
        ]

        start_time = time.time() - 100  # 100 seconds uptime
        response = HealthCheckResponse.create(
            components=components,
            version="1.0.0",
            start_time=start_time,
        )

        assert response.status == HealthStatus.HEALTHY
        assert response.version == "1.0.0"
        assert len(response.components) == 3
        assert 99 < response.uptime_seconds < 101  # ~100 seconds
        assert response.timestamp  # ISO 8601 timestamp present

    def test_create_with_degraded(self) -> None:
        """Should aggregate status as DEGRADED when any component degraded."""
        components = [
            ComponentHealth(name="database", status=HealthStatus.HEALTHY),
            ComponentHealth(name="cache", status=HealthStatus.DEGRADED),
            ComponentHealth(name="api", status=HealthStatus.HEALTHY),
        ]

        start_time = time.time()
        response = HealthCheckResponse.create(
            components=components,
            version="2.0.0",
            start_time=start_time,
        )

        assert response.status == HealthStatus.DEGRADED
        assert len(response.components) == 3

    def test_create_with_unhealthy(self) -> None:
        """Should aggregate status as UNHEALTHY when any component unhealthy."""
        components = [
            ComponentHealth(name="database", status=HealthStatus.HEALTHY),
            ComponentHealth(name="cache", status=HealthStatus.DEGRADED),
            ComponentHealth(name="api", status=HealthStatus.UNHEALTHY),
        ]

        start_time = time.time()
        response = HealthCheckResponse.create(
            components=components,
            version="1.5.0",
            start_time=start_time,
        )

        # Worst status wins
        assert response.status == HealthStatus.UNHEALTHY
        assert len(response.components) == 3

    def test_create_empty_components(self) -> None:
        """Should default to HEALTHY when no components."""
        start_time = time.time()
        response = HealthCheckResponse.create(
            components=[],
            version="1.0.0",
            start_time=start_time,
        )

        assert response.status == HealthStatus.HEALTHY
        assert not response.components

    def test_create_mixed_components_unhealthy_wins(self) -> None:
        """UNHEALTHY should win over DEGRADED when both present."""
        components = [
            ComponentHealth(name="a", status=HealthStatus.UNHEALTHY),
            ComponentHealth(name="b", status=HealthStatus.DEGRADED),
            ComponentHealth(name="c", status=HealthStatus.HEALTHY),
        ]
        start_time = time.time()
        response = HealthCheckResponse.create(components, "1.0.0", start_time)
        assert response.status == HealthStatus.UNHEALTHY

    def test_create_with_metadata(self) -> None:
        """Should include system-level metadata."""
        components = [ComponentHealth(name="db", status=HealthStatus.HEALTHY)]
        start_time = time.time()

        response = HealthCheckResponse.create(
            components=components,
            version="1.0.0",
            start_time=start_time,
            metadata={"environment": "production", "region": "us-west-2"},
        )

        assert response.metadata["environment"] == "production"
        assert response.metadata["region"] == "us-west-2"

    def test_create_default_metadata_is_empty(self) -> None:
        """Should default metadata to empty dict when not provided."""
        start_time = time.time()
        response = HealthCheckResponse.create(
            components=[],
            version="1.0.0",
            start_time=start_time,
        )
        assert response.metadata == {}

    def test_to_dict(self) -> None:
        """Should convert response to dict with proper structure."""
        components = [
            ComponentHealth(
                name="database",
                status=HealthStatus.HEALTHY,
                latency_ms=12.5,
            )
        ]

        start_time = time.time() - 3600  # 1 hour uptime
        response = HealthCheckResponse.create(
            components=components,
            version="2.0.0",
            start_time=start_time,
            metadata={"foo": "bar"},
        )

        result = response.to_dict()

        assert result["status"] == "healthy"
        assert result["version"] == "2.0.0"
        assert 3599 < result["uptime_seconds"] < 3601
        assert isinstance(result["timestamp"], str)
        assert len(result["components"]) == 1
        assert result["components"][0]["name"] == "database"
        assert result["metadata"] == {"foo": "bar"}

    def test_to_dict_without_metadata(self) -> None:
        """Should omit metadata when empty."""
        response = HealthCheckResponse(
            status=HealthStatus.HEALTHY,
            timestamp="2025-01-01T00:00:00+00:00",
            version="1.0.0",
            components=[],
            uptime_seconds=0.0,
            metadata={},
        )

        result = response.to_dict()

        assert "metadata" not in result

    def test_to_dict_with_metadata_direct(self) -> None:
        """Should include metadata when set directly."""
        response = HealthCheckResponse(
            status=HealthStatus.HEALTHY,
            timestamp="2025-01-01T00:00:00+00:00",
            version="1.0.0",
            components=[],
            uptime_seconds=0.0,
            metadata={"env": "test"},
        )

        result = response.to_dict()

        assert result["metadata"] == {"env": "test"}

    def test_is_healthy(self) -> None:
        """Should check if overall health is HEALTHY."""
        components_healthy = [ComponentHealth(name="db", status=HealthStatus.HEALTHY)]
        components_degraded = [ComponentHealth(name="db", status=HealthStatus.DEGRADED)]

        start_time = time.time()

        healthy_response = HealthCheckResponse.create(components_healthy, "1.0.0", start_time)
        degraded_response = HealthCheckResponse.create(components_degraded, "1.0.0", start_time)

        assert healthy_response.is_healthy()
        assert not degraded_response.is_healthy()

    def test_is_healthy_unhealthy(self) -> None:
        """Should return False for UNHEALTHY status."""
        start_time = time.time()
        response = HealthCheckResponse.create(
            [ComponentHealth(name="x", status=HealthStatus.UNHEALTHY)],
            "1.0.0",
            start_time,
        )
        assert not response.is_healthy()

    def test_is_ready(self) -> None:
        """Should check if system is ready (not UNHEALTHY)."""
        components_healthy = [ComponentHealth(name="db", status=HealthStatus.HEALTHY)]
        components_degraded = [ComponentHealth(name="db", status=HealthStatus.DEGRADED)]
        components_unhealthy = [ComponentHealth(name="db", status=HealthStatus.UNHEALTHY)]

        start_time = time.time()

        healthy_response = HealthCheckResponse.create(components_healthy, "1.0.0", start_time)
        degraded_response = HealthCheckResponse.create(components_degraded, "1.0.0", start_time)
        unhealthy_response = HealthCheckResponse.create(components_unhealthy, "1.0.0", start_time)

        # HEALTHY and DEGRADED are ready
        assert healthy_response.is_ready()
        assert degraded_response.is_ready()

        # UNHEALTHY is not ready
        assert not unhealthy_response.is_ready()


# =============================================================================
# DependencyConfig
# =============================================================================


class TestDependencyConfig:
    """Test DependencyConfig dataclass."""

    def test_defaults(self) -> None:
        """Should have sensible defaults."""
        config = DependencyConfig()
        assert config.host == "localhost"
        assert config.port == 8080
        assert config.required is True
        assert config.timeout_seconds == 30
        assert config.use_tls is False
        assert config.health_path == "/health"

    def test_custom_values(self) -> None:
        """Should accept custom values."""
        config = DependencyConfig(
            host="db.example.com",
            port=5432,
            required=False,
            timeout_seconds=60,
            use_tls=True,
            health_path="/ping",
        )
        assert config.host == "db.example.com"
        assert config.port == 5432
        assert config.required is False
        assert config.timeout_seconds == 60
        assert config.use_tls is True
        assert config.health_path == "/ping"

    def test_to_url_http(self) -> None:
        """Should build HTTP URL with defaults."""
        config = DependencyConfig()
        assert config.to_url() == "http://localhost:8080/health"

    def test_to_url_https(self) -> None:
        """Should build HTTPS URL when use_tls is True."""
        config = DependencyConfig(host="secure.example.com", port=443, use_tls=True)
        assert config.to_url() == "https://secure.example.com:443/health"

    def test_to_url_custom_health_path(self) -> None:
        """Should include custom health path in URL."""
        config = DependencyConfig(health_path="/mcp")
        assert config.to_url() == "http://localhost:8080/mcp"


# =============================================================================
# HealthCheckResult
# =============================================================================


class TestHealthCheckResult:
    """Test HealthCheckResult dataclass."""

    def test_defaults(self) -> None:
        """Should have sensible defaults."""
        result = HealthCheckResult(
            service_name="test",
            status=HealthStatus.HEALTHY,
        )
        assert result.service_name == "test"
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms == 0.0
        assert result.error is None
        assert result.response_data is None

    def test_to_dict_minimal(self) -> None:
        """Should convert to dict without error/response_data when None."""
        result = HealthCheckResult(
            service_name="svc",
            status=HealthStatus.HEALTHY,
            latency_ms=5.5,
        )
        d = result.to_dict()
        assert d == {
            "service_name": "svc",
            "status": "healthy",
            "latency_ms": 5.5,
        }
        assert "error" not in d
        assert "response" not in d

    def test_to_dict_with_error(self) -> None:
        """Should include error when set."""
        result = HealthCheckResult(
            service_name="svc",
            status=HealthStatus.UNHEALTHY,
            error="Connection refused",
        )
        d = result.to_dict()
        assert d["error"] == "Connection refused"

    def test_to_dict_with_response_data(self) -> None:
        """Should include response when set."""
        result = HealthCheckResult(
            service_name="svc",
            status=HealthStatus.HEALTHY,
            response_data={"status": "healthy", "version": "1.0"},
        )
        d = result.to_dict()
        assert d["response"] == {"status": "healthy", "version": "1.0"}

    def test_to_dict_latency_rounding(self) -> None:
        """Should round latency_ms to 2 decimal places."""
        result = HealthCheckResult(
            service_name="svc",
            status=HealthStatus.HEALTHY,
            latency_ms=12.345,
        )
        d = result.to_dict()
        assert d["latency_ms"] == 12.35


# =============================================================================
# WaitResult
# =============================================================================


class TestWaitResult:
    """Test WaitResult dataclass."""

    def test_defaults(self) -> None:
        """Should have sensible defaults for list fields."""
        result = WaitResult(
            success=True,
            dependencies={},
            total_wait_seconds=0.0,
        )
        assert result.success is True
        assert result.dependencies == {}
        assert result.total_wait_seconds == 0.0
        assert result.failed_required == []
        assert result.skipped_optional == []

    def test_with_failures(self) -> None:
        """Should hold failure information."""
        dep = HealthCheckResult(
            service_name="db",
            status=HealthStatus.UNHEALTHY,
            error="timeout",
        )
        result = WaitResult(
            success=False,
            dependencies={"db": dep},
            total_wait_seconds=30.0,
            failed_required=["db"],
            skipped_optional=["cache"],
        )
        assert result.success is False
        assert result.failed_required == ["db"]
        assert result.skipped_optional == ["cache"]
        assert result.dependencies["db"].error == "timeout"


# =============================================================================
# HealthChecker
# =============================================================================


class TestHealthChecker:
    """Test HealthChecker with mocked HTTP action."""

    def test_init_creates_http_action(self) -> None:
        """Should initialize and create an HTTP action."""
        checker = HealthChecker(timeout_seconds=10)
        assert checker._timeout == 10
        assert checker._http_action is not None

    @pytest.mark.asyncio
    async def test_check_healthy_response(self) -> None:
        """Should return HEALTHY for a successful health check response."""
        checker = HealthChecker(timeout_seconds=5)
        mock_action = AsyncMock()
        mock_action.execute = AsyncMock(return_value={
            "ok": True,
            "status_code": 200,
            "json": {"status": "healthy", "version": "1.0.0"},
        })
        checker._http_action = mock_action

        result = await checker.check("http://localhost:8080/health", service_name="test_svc")

        assert result.status == HealthStatus.HEALTHY
        assert result.service_name == "test_svc"
        assert result.error is None
        assert result.response_data is not None
        assert result.latency_ms > 0
        mock_action.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_ok_status_string(self) -> None:
        """Should map 'ok' status string to HEALTHY."""
        checker = HealthChecker(timeout_seconds=5)
        mock_action = AsyncMock()
        mock_action.execute = AsyncMock(return_value={
            "ok": True,
            "status_code": 200,
            "json": {"status": "ok"},
        })
        checker._http_action = mock_action

        result = await checker.check("http://localhost:8080/health")
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_up_status_string(self) -> None:
        """Should map 'up' status string to HEALTHY."""
        checker = HealthChecker(timeout_seconds=5)
        mock_action = AsyncMock()
        mock_action.execute = AsyncMock(return_value={
            "ok": True,
            "status_code": 200,
            "json": {"status": "up"},
        })
        checker._http_action = mock_action

        result = await checker.check("http://localhost:8080/health")
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_degraded_response(self) -> None:
        """Should return DEGRADED for a degraded health response."""
        checker = HealthChecker(timeout_seconds=5)
        mock_action = AsyncMock()
        mock_action.execute = AsyncMock(return_value={
            "ok": True,
            "status_code": 200,
            "json": {"status": "degraded"},
        })
        checker._http_action = mock_action

        result = await checker.check("http://localhost:8080/health")

        assert result.status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_check_warning_status_string(self) -> None:
        """Should map 'warning' status string to DEGRADED."""
        checker = HealthChecker(timeout_seconds=5)
        mock_action = AsyncMock()
        mock_action.execute = AsyncMock(return_value={
            "ok": True,
            "status_code": 200,
            "json": {"status": "warning"},
        })
        checker._http_action = mock_action

        result = await checker.check("http://localhost:8080/health")
        assert result.status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_check_unhealthy_response(self) -> None:
        """Should return UNHEALTHY for an unhealthy status string."""
        checker = HealthChecker(timeout_seconds=5)
        mock_action = AsyncMock()
        mock_action.execute = AsyncMock(return_value={
            "ok": True,
            "status_code": 200,
            "json": {"status": "unhealthy"},
        })
        checker._http_action = mock_action

        result = await checker.check("http://localhost:8080/health")
        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_check_http_error(self) -> None:
        """Should return UNHEALTHY when HTTP request fails (ok=False)."""
        checker = HealthChecker(timeout_seconds=5)
        mock_action = AsyncMock()
        mock_action.execute = AsyncMock(return_value={
            "ok": False,
            "status_code": 503,
            "json": None,
        })
        checker._http_action = mock_action

        result = await checker.check("http://localhost:8080/health", service_name="fail_svc")

        assert result.status == HealthStatus.UNHEALTHY
        assert "HTTP 503" in result.error

    @pytest.mark.asyncio
    async def test_check_timeout(self) -> None:
        """Should return UNHEALTHY with timeout error on TimeoutError."""
        checker = HealthChecker(timeout_seconds=5)
        mock_action = AsyncMock()
        mock_action.execute = AsyncMock(side_effect=TimeoutError("request timed out"))
        checker._http_action = mock_action

        result = await checker.check("http://localhost:8080/health", service_name="slow_svc")

        assert result.status == HealthStatus.UNHEALTHY
        assert result.error == "Timeout"
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_check_generic_exception(self) -> None:
        """Should return UNHEALTHY with error message on generic exception."""
        checker = HealthChecker(timeout_seconds=5)
        mock_action = AsyncMock()
        mock_action.execute = AsyncMock(side_effect=ConnectionError("Connection refused"))
        checker._http_action = mock_action

        result = await checker.check("http://localhost:8080/health", service_name="err_svc")

        assert result.status == HealthStatus.UNHEALTHY
        assert "Connection refused" in result.error
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_check_uses_provided_timeout(self) -> None:
        """Should pass provided timeout to HTTP action."""
        checker = HealthChecker(timeout_seconds=5)
        mock_action = AsyncMock()
        mock_action.execute = AsyncMock(return_value={
            "ok": True,
            "status_code": 200,
            "json": {"status": "healthy"},
        })
        checker._http_action = mock_action

        await checker.check("http://localhost:8080/health", timeout=10)
        call_args = mock_action.execute.call_args[0][0]
        assert call_args["timeout"] == 10

    @pytest.mark.asyncio
    async def test_check_uses_default_timeout(self) -> None:
        """Should use default timeout when none provided."""
        checker = HealthChecker(timeout_seconds=7)
        mock_action = AsyncMock()
        mock_action.execute = AsyncMock(return_value={
            "ok": True,
            "status_code": 200,
            "json": {"status": "healthy"},
        })
        checker._http_action = mock_action

        await checker.check("http://localhost:8080/health")
        call_args = mock_action.execute.call_args[0][0]
        assert call_args["timeout"] == 7

    @pytest.mark.asyncio
    async def test_check_handles_none_json_response(self) -> None:
        """Should handle None json in response gracefully."""
        checker = HealthChecker(timeout_seconds=5)
        mock_action = AsyncMock()
        mock_action.execute = AsyncMock(return_value={
            "ok": True,
            "status_code": 200,
            "json": None,
        })
        checker._http_action = mock_action

        result = await checker.check("http://localhost:8080/health")
        # None json defaults to empty dict, status defaults to "healthy"
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_default_service_name(self) -> None:
        """Should use 'unknown' as default service name."""
        checker = HealthChecker(timeout_seconds=5)
        mock_action = AsyncMock()
        mock_action.execute = AsyncMock(return_value={
            "ok": True,
            "status_code": 200,
            "json": {"status": "healthy"},
        })
        checker._http_action = mock_action

        result = await checker.check("http://localhost:8080/health")
        assert result.service_name == "unknown"


# =============================================================================
# _HttpxFallback
# =============================================================================


class TestHttpxFallback:
    """Test _HttpxFallback HTTP client.

    Since _HttpxFallback.execute does `import httpx` at call time, we
    temporarily swap sys.modules["httpx"] to inject our mock.  We do NOT
    reload the health module -- the import happens lazily inside execute().
    """

    @pytest.mark.asyncio
    async def test_successful_request(self) -> None:
        """Should return ok=True with status_code and json on success."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.content = b'{"status": "healthy"}'
        mock_response.json.return_value = {"status": "healthy"}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_httpx = MagicMock()
        mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
        mock_httpx.TimeoutException = type("TimeoutException", (Exception,), {})

        import sys
        original = sys.modules.get("httpx")
        # Remove cached import so that `import httpx` inside execute() picks up mock
        for key in list(sys.modules):
            if key == "httpx" or key.startswith("httpx."):
                del sys.modules[key]
        sys.modules["httpx"] = mock_httpx
        try:
            fallback = _HttpxFallback()
            result = await fallback.execute("http://localhost:8080/health", "GET", 5)
        finally:
            # Restore
            for key in list(sys.modules):
                if key == "httpx" or key.startswith("httpx."):
                    del sys.modules[key]
            if original is not None:
                sys.modules["httpx"] = original

        assert result["ok"] is True
        assert result["status_code"] == 200
        assert result["json"] == {"status": "healthy"}

    @pytest.mark.asyncio
    async def test_timeout_exception(self) -> None:
        """Should return ok=False on timeout."""
        timeout_exc = type("TimeoutException", (Exception,), {})

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=timeout_exc("timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_httpx = MagicMock()
        mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
        mock_httpx.TimeoutException = timeout_exc

        import sys
        original = sys.modules.get("httpx")
        for key in list(sys.modules):
            if key == "httpx" or key.startswith("httpx."):
                del sys.modules[key]
        sys.modules["httpx"] = mock_httpx
        try:
            fallback = _HttpxFallback()
            result = await fallback.execute("http://localhost:8080/health", "GET", 5)
        finally:
            for key in list(sys.modules):
                if key == "httpx" or key.startswith("httpx."):
                    del sys.modules[key]
            if original is not None:
                sys.modules["httpx"] = original

        assert result["ok"] is False
        assert result["status_code"] is None
        assert result["json"] is None

    @pytest.mark.asyncio
    async def test_generic_exception(self) -> None:
        """Should return ok=False on generic exception."""
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=ConnectionError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_httpx = MagicMock()
        mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
        mock_httpx.TimeoutException = type("TimeoutException", (Exception,), {})

        import sys
        original = sys.modules.get("httpx")
        for key in list(sys.modules):
            if key == "httpx" or key.startswith("httpx."):
                del sys.modules[key]
        sys.modules["httpx"] = mock_httpx
        try:
            fallback = _HttpxFallback()
            result = await fallback.execute("http://localhost:8080/health", "GET", 5)
        finally:
            for key in list(sys.modules):
                if key == "httpx" or key.startswith("httpx."):
                    del sys.modules[key]
            if original is not None:
                sys.modules["httpx"] = original

        assert result["ok"] is False
        assert result["status_code"] is None
        assert result["json"] is None

    @pytest.mark.asyncio
    async def test_empty_content_returns_none_json(self) -> None:
        """Should return None for json when response content is empty."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.content = b""
        mock_response.json.return_value = {}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_httpx = MagicMock()
        mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
        mock_httpx.TimeoutException = type("TimeoutException", (Exception,), {})

        import sys
        original = sys.modules.get("httpx")
        for key in list(sys.modules):
            if key == "httpx" or key.startswith("httpx."):
                del sys.modules[key]
        sys.modules["httpx"] = mock_httpx
        try:
            fallback = _HttpxFallback()
            result = await fallback.execute("http://localhost:8080/health", "GET", 5)
        finally:
            for key in list(sys.modules):
                if key == "httpx" or key.startswith("httpx."):
                    del sys.modules[key]
            if original is not None:
                sys.modules["httpx"] = original

        assert result["ok"] is True
        assert result["json"] is None

    @pytest.mark.asyncio
    async def test_passes_timeout_to_client(self) -> None:
        """Should pass timeout parameter to AsyncClient."""
        captured_kwargs = {}

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.content = b'{"status":"healthy"}'
        mock_response.json.return_value = {"status": "healthy"}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        def capture_client(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_client

        mock_httpx = MagicMock()
        mock_httpx.AsyncClient = MagicMock(side_effect=capture_client)
        mock_httpx.TimeoutException = type("TimeoutException", (Exception,), {})

        import sys
        original = sys.modules.get("httpx")
        for key in list(sys.modules):
            if key == "httpx" or key.startswith("httpx."):
                del sys.modules[key]
        sys.modules["httpx"] = mock_httpx
        try:
            fallback = _HttpxFallback()
            await fallback.execute("http://localhost:8080/health", "GET", 15)
        finally:
            for key in list(sys.modules):
                if key == "httpx" or key.startswith("httpx."):
                    del sys.modules[key]
            if original is not None:
                sys.modules["httpx"] = original

        assert captured_kwargs["timeout"] == 15


# =============================================================================
# DependencyWaiter
# =============================================================================


class TestDependencyWaiter:
    """Test DependencyWaiter with mocked HealthChecker."""

    def test_init_defaults(self) -> None:
        """Should initialize with default backoff parameters."""
        waiter = DependencyWaiter()
        assert waiter._base_delay == 1.0
        assert waiter._max_delay == 16.0

    def test_init_custom(self) -> None:
        """Should accept custom backoff parameters."""
        waiter = DependencyWaiter(base_delay=0.5, max_delay=8.0)
        assert waiter._base_delay == 0.5
        assert waiter._max_delay == 8.0

    @pytest.mark.asyncio
    async def test_wait_for_all_all_healthy(self) -> None:
        """Should succeed when all dependencies are healthy."""
        waiter = DependencyWaiter()
        waiter._checker = AsyncMock()
        waiter._checker.check = AsyncMock(return_value=HealthCheckResult(
            service_name="svc",
            status=HealthStatus.HEALTHY,
        ))

        deps = {
            "db": DependencyConfig(port=5432, required=True),
            "cache": DependencyConfig(port=6379, required=True),
        }

        result = await waiter.wait_for_all(deps)

        assert result.success is True
        assert result.failed_required == []
        assert result.skipped_optional == []
        assert "db" in result.dependencies
        assert "cache" in result.dependencies

    @pytest.mark.asyncio
    async def test_wait_for_all_required_fails(self) -> None:
        """Should fail when a required dependency is unhealthy."""
        waiter = DependencyWaiter(base_delay=0.01, max_delay=0.01)
        waiter._checker = AsyncMock()
        waiter._checker.check = AsyncMock(return_value=HealthCheckResult(
            service_name="db",
            status=HealthStatus.UNHEALTHY,
            error="Connection refused",
        ))

        deps = {
            "db": DependencyConfig(port=5432, required=True, timeout_seconds=1),
        }

        result = await waiter.wait_for_all(deps)

        assert result.success is False
        assert "db" in result.failed_required

    @pytest.mark.asyncio
    async def test_wait_for_all_optional_fails(self) -> None:
        """Should succeed but track skipped optional dependency."""
        waiter = DependencyWaiter(base_delay=0.01, max_delay=0.01)
        waiter._checker = AsyncMock()
        waiter._checker.check = AsyncMock(return_value=HealthCheckResult(
            service_name="cache",
            status=HealthStatus.UNHEALTHY,
        ))

        deps = {
            "cache": DependencyConfig(port=6379, required=False, timeout_seconds=1),
        }

        result = await waiter.wait_for_all(deps)

        assert result.success is True  # Optional, so still success
        assert "cache" in result.skipped_optional
        assert result.failed_required == []

    @pytest.mark.asyncio
    async def test_wait_for_all_mixed(self) -> None:
        """Should fail when required dep fails even if optional succeeds."""
        waiter = DependencyWaiter(base_delay=0.01, max_delay=0.01)

        async def mock_check(url: str, timeout: int = 5, service_name: str = "unknown") -> HealthCheckResult:
            if service_name == "db":
                return HealthCheckResult(service_name="db", status=HealthStatus.UNHEALTHY)
            return HealthCheckResult(service_name=service_name, status=HealthStatus.HEALTHY)

        waiter._checker = AsyncMock()
        waiter._checker.check = AsyncMock(side_effect=mock_check)

        deps = {
            "db": DependencyConfig(port=5432, required=True, timeout_seconds=1),
            "cache": DependencyConfig(port=6379, required=False, timeout_seconds=1),
        }

        result = await waiter.wait_for_all(deps)

        assert result.success is False
        assert "db" in result.failed_required
        assert "cache" not in result.skipped_optional  # cache was healthy

    @pytest.mark.asyncio
    async def test_wait_for_single_exponential_backoff(self) -> None:
        """Should use exponential backoff with capped delay."""
        call_count = 0

        async def mock_check(url: str, timeout: int = 5, service_name: str = "unknown") -> HealthCheckResult:
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                return HealthCheckResult(service_name=service_name, status=HealthStatus.HEALTHY)
            return HealthCheckResult(service_name=service_name, status=HealthStatus.UNHEALTHY)

        waiter = DependencyWaiter(base_delay=0.01, max_delay=0.05)
        waiter._checker = AsyncMock()
        waiter._checker.check = AsyncMock(side_effect=mock_check)

        config = DependencyConfig(port=8080, required=True, timeout_seconds=2)
        result = await waiter._wait_for_single("svc", config)

        assert result.status == HealthStatus.HEALTHY
        assert call_count == 3  # Two retries then success

    @pytest.mark.asyncio
    async def test_wait_for_single_timeout_exceeded(self) -> None:
        """Should return last result after deadline exceeded."""
        waiter = DependencyWaiter(base_delay=0.01, max_delay=0.01)
        waiter._checker = AsyncMock()
        waiter._checker.check = AsyncMock(return_value=HealthCheckResult(
            service_name="svc",
            status=HealthStatus.UNHEALTHY,
            error="Connection refused",
        ))

        config = DependencyConfig(port=8080, required=True, timeout_seconds=1)
        result = await waiter._wait_for_single("svc", config)

        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_wait_for_single_returns_immediately_on_healthy(self) -> None:
        """Should return immediately without retry when first check is healthy."""
        waiter = DependencyWaiter()
        waiter._checker = AsyncMock()
        waiter._checker.check = AsyncMock(return_value=HealthCheckResult(
            service_name="svc",
            status=HealthStatus.HEALTHY,
        ))

        config = DependencyConfig(port=8080, required=True)
        result = await waiter._wait_for_single("svc", config)

        assert result.status == HealthStatus.HEALTHY
        waiter._checker.check.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_for_single_degraded_is_success(self) -> None:
        """Should return immediately on DEGRADED (not UNHEALTHY)."""
        waiter = DependencyWaiter()
        waiter._checker = AsyncMock()
        waiter._checker.check = AsyncMock(return_value=HealthCheckResult(
            service_name="svc",
            status=HealthStatus.DEGRADED,
        ))

        config = DependencyConfig(port=8080, required=True)
        result = await waiter._wait_for_single("svc", config)

        assert result.status == HealthStatus.DEGRADED
        waiter._checker.check.assert_called_once()


# =============================================================================
# register_health_tools
# =============================================================================


class TestRegisterHealthTools:
    """Test register_health_tools MCP tool registration."""

    def test_registers_tools_on_mcp(self) -> None:
        """Should register 6 health tools on the MCP server."""
        mock_mcp = MagicMock()

        with patch("mcp_common.health.HealthChecker") as mock_checker_cls, \
             patch("mcp_common.health.DependencyWaiter") as mock_waiter_cls:
            register_health_tools(
                mock_mcp,
                service_name="test-service",
                version="1.2.3",
                dependencies={},
            )

        # @mcp.tool() decorator is called once per tool (6 tools)
        assert mock_mcp.tool.call_count == 6

    def test_registers_expected_tool_names(self) -> None:
        """Should register the 6 expected tool functions."""
        mock_mcp = MagicMock()
        tool_decorator_calls = []

        def capture_tool():
            def decorator(func):
                tool_decorator_calls.append(func.__name__)
                return func
            return decorator

        mock_mcp.tool = MagicMock(side_effect=capture_tool)

        with patch("mcp_common.health.HealthChecker"), \
             patch("mcp_common.health.DependencyWaiter"):
            register_health_tools(
                mock_mcp,
                service_name="test",
                version="1.0.0",
            )

        expected_tools = {
            "health_check_service",
            "health_check_all",
            "wait_for_dependency",
            "wait_for_all_dependencies",
            "get_liveness",
            "get_readiness",
        }
        assert set(tool_decorator_calls) == expected_tools

    def test_uses_default_start_time(self) -> None:
        """Should use time.time() when start_time is None."""
        mock_mcp = MagicMock()

        with patch("mcp_common.health.HealthChecker"), \
             patch("mcp_common.health.DependencyWaiter"), \
             patch("mcp_common.health.time.time") as mock_time:
            mock_time.return_value = 1000.0
            register_health_tools(mock_mcp)

            # start_time defaults to time.time() inside the function
            # Verify time.time was called
            assert mock_time.called

    def test_passes_dependencies_to_tools(self) -> None:
        """Should pass dependencies dict to the tool closures."""
        mock_mcp = MagicMock()

        deps = {
            "session_buddy": DependencyConfig(port=8678, required=True),
        }

        with patch("mcp_common.health.HealthChecker") as mock_checker_cls, \
             patch("mcp_common.health.DependencyWaiter") as mock_waiter_cls:
            register_health_tools(
                mock_mcp,
                dependencies=deps,
            )

        # The function should have been called (tools registered)
        assert mock_mcp.tool.call_count == 6


# =============================================================================
# Integration Tests
# =============================================================================


class TestHealthCheckIntegration:
    """Integration tests for health check scenarios."""

    def test_kubernetes_liveness_scenario(self) -> None:
        """Should support Kubernetes liveness probe pattern."""
        components = [
            ComponentHealth(name="db", status=HealthStatus.DEGRADED),
        ]

        start_time = time.time()
        response = HealthCheckResponse.create(components, "1.0.0", start_time)

        assert response.status != HealthStatus.UNHEALTHY

    def test_kubernetes_readiness_scenario(self) -> None:
        """Should support Kubernetes readiness probe pattern."""
        components_ready = [ComponentHealth(name="db", status=HealthStatus.HEALTHY)]
        components_not_ready = [ComponentHealth(name="db", status=HealthStatus.DEGRADED)]

        start_time = time.time()

        ready_response = HealthCheckResponse.create(components_ready, "1.0.0", start_time)
        not_ready_response = HealthCheckResponse.create(components_not_ready, "1.0.0", start_time)

        assert ready_response.is_healthy()
        assert not not_ready_response.is_healthy()

    def test_docker_health_check_scenario(self) -> None:
        """Should support Docker health check pattern."""
        components = [
            ComponentHealth(name="api", status=HealthStatus.HEALTHY),
            ComponentHealth(name="db", status=HealthStatus.DEGRADED),
        ]

        start_time = time.time()
        response = HealthCheckResponse.create(components, "1.0.0", start_time)

        assert response.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)

    def test_multi_component_failure_cascade(self) -> None:
        """Should handle cascading failures correctly."""
        components = [
            ComponentHealth(
                name="primary_db", status=HealthStatus.UNHEALTHY, message="Connection timeout"
            ),
            ComponentHealth(
                name="read_replica", status=HealthStatus.DEGRADED, message="High replication lag"
            ),
            ComponentHealth(name="cache", status=HealthStatus.HEALTHY),
            ComponentHealth(name="queue", status=HealthStatus.HEALTHY),
        ]

        start_time = time.time()
        response = HealthCheckResponse.create(components, "1.0.0", start_time)

        assert response.status == HealthStatus.UNHEALTHY
        assert len([c for c in response.components if c.status == HealthStatus.UNHEALTHY]) == 1
        assert len([c for c in response.components if c.status == HealthStatus.DEGRADED]) == 1
        assert len([c for c in response.components if c.status == HealthStatus.HEALTHY]) == 2


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestHealthPropertyBased:
    """Property-based tests for health checks.

    Uses Hypothesis to test health check properties across many random inputs.
    """

    @given(st.text(min_size=1, max_size=50), st.text(min_size=1, max_size=50))
    def test_component_health_creation(self, name: str, message: str) -> None:
        """Test ComponentHealth can be created with any strings.

        Property: ComponentHealth should accept any component name/message.
        """
        for status in HealthStatus:
            health = ComponentHealth(
                name=name,
                status=status,
                message=message,
            )
            assert health.name == name
            assert health.status == status
            assert health.message == message

    @given(
        st.text(min_size=1, max_size=30),
        st.sampled_from(["healthy", "degraded", "unhealthy"]),
    )
    def test_health_response_serialization(self, name: str, status_str: str) -> None:
        """Test health response can be serialized with random data.

        Property: HealthCheckResponse should be JSON serializable for all inputs.
        """
        status = HealthStatus(status_str)
        component = ComponentHealth(
            name=name,
            status=status,
            message="test",
        )

        component_dict = component.to_dict()
        assert isinstance(component_dict, dict)
        assert component_dict["name"] == name
        assert component_dict["status"] == status_str

        response = HealthCheckResponse(
            status=status,
            timestamp="2025-10-28T12:00:00Z",
            version="1.0.0",
            components=[component],
            uptime_seconds=3600.0,
        )

        assert response.status == status
        assert len(response.components) == 1

    @given(st.lists(
        st.tuples(
            st.text(min_size=1, max_size=30, alphabet="abc"),
            st.sampled_from(["healthy", "degraded", "unhealthy"]),
            st.text(min_size=0, max_size=100),
        ),
        min_size=0,
        max_size=10,
    ))
    def test_health_response_with_multiple_components(self, components_data: list) -> None:
        """Test health response with variable number of components.

        Property: Should handle any number of components.
        """
        components = []
        for name, status_str, message in components_data:
            components.append(ComponentHealth(
                name=name,
                status=HealthStatus(status_str),
                message=message,
            ))

        if components:
            if any(c.status == HealthStatus.UNHEALTHY for c in components):
                overall_status = HealthStatus.UNHEALTHY
            elif any(c.status == HealthStatus.DEGRADED for c in components):
                overall_status = HealthStatus.DEGRADED
            else:
                overall_status = HealthStatus.HEALTHY
        else:
            overall_status = HealthStatus.HEALTHY

        response = HealthCheckResponse(
            status=overall_status,
            timestamp="2025-10-28T12:00:00Z",
            version="1.0.0",
            components=components,
            uptime_seconds=3600.0,
        )

        assert response.status == overall_status
        assert len(response.components) == len(components_data)

    @given(
        st.text(min_size=1, max_size=50),
        st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1)),
    )
    def test_component_health_with_timestamp(self, name: str, timestamp: datetime) -> None:
        """Test ComponentHealth with various timestamps.

        Property: Should handle any valid datetime via metadata.
        """
        health = ComponentHealth(
            name=name,
            status=HealthStatus.HEALTHY,
            message="test",
            metadata={"checked_at": timestamp.isoformat()},
        )

        assert health.name == name
        assert "checked_at" in health.metadata

    @given(st.dictionaries(
        st.text(min_size=1, max_size=20, alphabet="abc"),
        st.sampled_from(["healthy", "degraded", "unhealthy"]),
        min_size=0,
        max_size=5,
    ))
    def test_health_response_empty_components(self, status_map: dict) -> None:
        """Test health response with empty or minimal components.

        Property: Should handle empty component list.
        """
        components = []
        for name, status_str in status_map.items():
            components.append(ComponentHealth(
                name=name,
                status=HealthStatus(status_str),
                message="test",
            ))

        if not components:
            overall_status = HealthStatus.HEALTHY
        elif any(c.status == HealthStatus.UNHEALTHY for c in components):
            overall_status = HealthStatus.UNHEALTHY
        elif any(c.status == HealthStatus.DEGRADED for c in components):
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        response = HealthCheckResponse(
            status=overall_status,
            timestamp="2025-10-28T12:00:00Z",
            version="1.0.0",
            components=components,
            uptime_seconds=3600.0,
        )

        assert response.status == overall_status
        assert len(response.components) == len(status_map)
