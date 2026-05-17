"""Tests for health check tool registration in register_health_tools."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time

from mcp_common.health import (
    DependencyConfig,
    DependencyWaiter,
    HealthChecker,
    HealthCheckResult,
    HealthStatus,
    WaitResult,
    register_health_tools,
)


class MockMCP:
    """Mock MCP server for testing."""

    def __init__(self):
        self.tools = {}

    def tool(self):
        """Mock tool decorator."""

        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class TestRegisterHealthTools:
    """Test register_health_tools function."""

    def test_register_health_tools_initializes_dependencies(self) -> None:
        """Test that register_health_tools initializes with empty dependencies."""
        mcp = MockMCP()
        register_health_tools(mcp, "test-server", "1.0.0")

        # Verify tools are registered
        assert "health_check_service" in mcp.tools
        assert "health_check_all" in mcp.tools

    def test_register_health_tools_with_start_time(self) -> None:
        """Test register_health_tools with explicit start_time."""
        mcp = MockMCP()
        start_time = 1234567890.0

        register_health_tools(mcp, "test-server", "1.0.0", start_time=start_time)

        assert "health_check_service" in mcp.tools

    def test_register_health_tools_with_dependencies(self) -> None:
        """Test register_health_tools with configured dependencies."""
        mcp = MockMCP()
        dependencies = {
            "database": DependencyConfig(port=5432, required=True),
            "cache": DependencyConfig(port=6379, required=False),
        }

        register_health_tools(
            mcp, "test-server", "1.0.0", dependencies=dependencies
        )

        assert "health_check_service" in mcp.tools
        assert "health_check_all" in mcp.tools

    @pytest.mark.asyncio
    async def test_health_check_all_tool_no_dependencies(self) -> None:
        """Test health_check_all tool with no dependencies configured."""
        mcp = MockMCP()
        register_health_tools(mcp, "test-server", "1.0.0", dependencies={})

        health_check_all = mcp.tools["health_check_all"]

        # Call the tool - should return immediately with no deps message
        result = await health_check_all()

        assert result["status"] == "healthy"
        assert result["services"] == {}
        assert "No dependencies configured" in result.get("message", "")

    @pytest.mark.asyncio
    async def test_health_check_service_uses_custom_url(self) -> None:
        """Test health_check_service builds the expected URL and serializes result."""
        mcp = MockMCP()
        checker = MagicMock()
        checker.check = AsyncMock(
            return_value=HealthCheckResult(
                service_name="api",
                status=HealthStatus.DEGRADED,
                latency_ms=12.345,
                response_data={"status": "warning"},
            )
        )
        waiter = MagicMock()

        with patch("mcp_common.health.HealthChecker", return_value=checker), patch(
            "mcp_common.health.DependencyWaiter", return_value=waiter
        ):
            register_health_tools(mcp, "test-server", "1.0.0")

        result = await mcp.tools["health_check_service"](
            "api",
            host="example.com",
            port=8443,
            timeout=9,
            use_tls=True,
            health_path="/ready",
        )

        checker.check.assert_awaited_once_with(
            "https://example.com:8443/ready",
            timeout=9,
            service_name="api",
        )
        assert result["service_name"] == "api"
        assert result["status"] == "degraded"
        assert result["latency_ms"] == 12.35
        assert result["response"] == {"status": "warning"}

    @pytest.mark.asyncio
    async def test_health_check_all_handles_success_and_exception(self) -> None:
        """Test health_check_all for healthy, degraded, and exception results."""
        dependencies = {
            "db": DependencyConfig(port=5432, required=True),
            "cache": DependencyConfig(port=6379, required=False),
        }

        mcp = MockMCP()
        checker = MagicMock()
        checker.check = AsyncMock(
            side_effect=[
                HealthCheckResult(
                    service_name="db",
                    status=HealthStatus.HEALTHY,
                    response_data={"status": "healthy"},
                ),
                HealthCheckResult(
                    service_name="cache",
                    status=HealthStatus.DEGRADED,
                    response_data={"status": "warning"},
                ),
            ]
        )
        waiter = MagicMock()

        with patch("mcp_common.health.HealthChecker", return_value=checker), patch(
            "mcp_common.health.DependencyWaiter", return_value=waiter
        ):
            register_health_tools(
                mcp,
                "test-server",
                "1.0.0",
                dependencies=dependencies,
            )

        result = await mcp.tools["health_check_all"]()

        assert result["status"] == "healthy"
        assert result["total_services"] == 2
        assert result["healthy_services"] == 1
        assert result["services"]["db"]["status"] == "healthy"
        assert result["services"]["cache"]["status"] == "degraded"
        assert result["services"]["cache"]["response"] == {"status": "warning"}

        mcp_error = MockMCP()
        checker_error = MagicMock()
        checker_error.check = AsyncMock(
            side_effect=[
                HealthCheckResult(
                    service_name="db",
                    status=HealthStatus.HEALTHY,
                ),
                RuntimeError("boom"),
            ]
        )

        with patch(
            "mcp_common.health.HealthChecker", return_value=checker_error
        ), patch("mcp_common.health.DependencyWaiter", return_value=waiter):
            register_health_tools(
                mcp_error,
                "test-server",
                "1.0.0",
                dependencies=dependencies,
            )

        error_result = await mcp_error.tools["health_check_all"]()

        assert error_result["status"] == "unhealthy"
        assert error_result["services"]["db"]["status"] == "healthy"
        assert error_result["services"]["cache"]["status"] == "unhealthy"
        assert error_result["services"]["cache"]["error"] == "boom"

    @pytest.mark.asyncio
    async def test_wait_for_dependency_handles_required_and_optional(self) -> None:
        """Test wait_for_dependency response fields for required and optional deps."""
        mcp = MockMCP()
        waiter = MagicMock()
        waiter.wait_for_all = AsyncMock(
            side_effect=[
                WaitResult(
                    success=False,
                    dependencies={
                        "db": HealthCheckResult(
                            service_name="db",
                            status=HealthStatus.UNHEALTHY,
                            latency_ms=25.0,
                            error="timeout",
                        )
                    },
                    total_wait_seconds=3.5,
                    failed_required=["db"],
                ),
                WaitResult(
                    success=False,
                    dependencies={
                        "cache": HealthCheckResult(
                            service_name="cache",
                            status=HealthStatus.UNHEALTHY,
                            latency_ms=18.0,
                            error="timeout",
                        )
                    },
                    total_wait_seconds=2.0,
                    skipped_optional=["cache"],
                ),
            ]
        )
        checker = MagicMock()

        with patch("mcp_common.health.HealthChecker", return_value=checker), patch(
            "mcp_common.health.DependencyWaiter", return_value=waiter
        ):
            register_health_tools(mcp, "test-server", "1.0.0")

        required_result = await mcp.tools["wait_for_dependency"](
            "db",
            timeout=3,
            required=True,
        )
        optional_result = await mcp.tools["wait_for_dependency"](
            "cache",
            timeout=3,
            required=False,
        )

        assert required_result["success"] is False
        assert required_result["status"] == "unhealthy"
        assert required_result["error"] == "timeout"
        assert "Required dependency" in required_result["message"]

        assert optional_result["success"] is True
        assert optional_result["status"] == "unhealthy"
        assert optional_result["error"] == "timeout"
        assert "message" not in optional_result

    @pytest.mark.asyncio
    async def test_wait_for_all_dependencies_and_readiness_paths(self) -> None:
        """Test wait_for_all_dependencies, readiness, and liveness paths."""
        waiter = MagicMock()
        waiter.wait_for_all = AsyncMock(
            return_value=WaitResult(
                success=False,
                dependencies={
                    "db": HealthCheckResult(
                        service_name="db",
                        status=HealthStatus.DEGRADED,
                        latency_ms=11.0,
                    ),
                    "cache": HealthCheckResult(
                        service_name="cache",
                        status=HealthStatus.UNHEALTHY,
                        latency_ms=22.0,
                        error="down",
                    ),
                },
                total_wait_seconds=4.5,
                failed_required=["cache"],
                skipped_optional=["db"],
            )
        )
        checker = MagicMock()
        deps = {
            "db": DependencyConfig(port=5432, required=True),
            "cache": DependencyConfig(port=6379, required=False),
        }

        mcp = MockMCP()
        with patch("mcp_common.health.HealthChecker", return_value=checker), patch(
            "mcp_common.health.DependencyWaiter", return_value=waiter
        ):
            register_health_tools(
                mcp,
                "test-server",
                "1.0.0",
                start_time=1000.0,
                dependencies=deps,
            )

        all_result = await mcp.tools["wait_for_all_dependencies"]()

        assert all_result["success"] is False
        assert all_result["total_wait_seconds"] == 4.5
        assert all_result["failed_required"] == ["cache"]
        assert all_result["dependencies"]["db"]["status"] == "degraded"
        assert all_result["dependencies"]["cache"]["error"] == "down"
        assert "Failed to connect" in all_result["message"]

        readiness_result = await mcp.tools["get_readiness"]()
        assert readiness_result["ready"] is False
        assert readiness_result["service"] == "test-server"
        assert readiness_result["checks"]["process"] == "ok"
        assert readiness_result["checks"]["db"] == "degraded"
        assert readiness_result["checks"]["cache"] == "unhealthy"
        assert readiness_result["failed_required"] == ["cache"]

        with patch("mcp_common.health.time.time", return_value=1002.0):
            liveness_result = await mcp.tools["get_liveness"]()
        assert liveness_result == {
            "status": "ok",
            "service": "test-server",
            "version": "1.0.0",
            "uptime_seconds": 2.0,
        }

        empty_mcp = MockMCP()
        with patch("mcp_common.health.HealthChecker", return_value=checker), patch(
            "mcp_common.health.DependencyWaiter", return_value=waiter
        ):
            register_health_tools(
                empty_mcp,
                "test-server",
                "1.0.0",
                dependencies={},
            )

        assert await empty_mcp.tools["wait_for_all_dependencies"]() == {
            "success": True,
            "message": "No dependencies configured",
            "dependencies": {},
            "total_wait_seconds": 0,
        }
        assert await empty_mcp.tools["get_readiness"]() == {
            "ready": True,
            "service": "test-server",
            "checks": {"process": "ok"},
        }

    def test_register_health_tools_multiple_calls(self) -> None:
        """Test that register_health_tools can be called multiple times."""
        mcp1 = MockMCP()
        mcp2 = MockMCP()

        register_health_tools(mcp1, "server-1", "1.0.0")
        register_health_tools(mcp2, "server-2", "2.0.0")

        # Both should have the tools
        assert "health_check_service" in mcp1.tools
        assert "health_check_service" in mcp2.tools
        assert "health_check_all" in mcp1.tools
        assert "health_check_all" in mcp2.tools

    def test_dependency_config_conversion(self) -> None:
        """Test DependencyConfig URL conversion."""
        # HTTP config with default health path
        http_config = DependencyConfig(host="example.com", port=8080, use_tls=False)
        assert http_config.to_url() == "http://example.com:8080/health"

        # HTTPS config with default health path
        https_config = DependencyConfig(host="example.com", port=8443, use_tls=True)
        assert https_config.to_url() == "https://example.com:8443/health"

        # With custom health path
        config_with_path = DependencyConfig(
            host="example.com", port=8080, use_tls=False, health_path="/api/health"
        )
        assert config_with_path.to_url() == "http://example.com:8080/api/health"

        # With localhost (default)
        default_host = DependencyConfig(port=5432)
        assert default_host.to_url() == "http://localhost:5432/health"
