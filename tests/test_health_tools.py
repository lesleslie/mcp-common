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
