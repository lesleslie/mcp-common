"""Tests for HTTP client health check utilities.

Tests comprehensive health checks for HTTPClientAdapter including:
- Client initialization health
- Connection pool health
- Connectivity tests with various scenarios
- Latency monitoring
- Error handling

Phase 10.1: Production Hardening - HTTP Health Check Tests
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mcp_common.health import HealthStatus
from mcp_common.http_health import check_http_client_health, check_http_connectivity


class TestHTTPClientHealth:
    """Test HTTP client health check."""

    @pytest.mark.asyncio
    async def test_client_healthy_no_connectivity_test(self) -> None:
        """Should return HEALTHY when client initializes without connectivity test."""
        # Create mock HTTP client adapter
        mock_adapter = MagicMock()
        mock_adapter.settings = MagicMock()
        mock_adapter.settings.max_connections = 100
        mock_adapter.settings.max_keepalive_connections = 20
        mock_adapter.settings.timeout = 30

        # Mock the client creation
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_adapter._create_client = AsyncMock(return_value=mock_client)

        result = await check_http_client_health(http_client=mock_adapter)

        assert result.name == "http_client"
        assert result.status == HealthStatus.HEALTHY
        assert "initialized and ready" in result.message.lower()
        assert result.latency_ms is not None
        assert result.latency_ms < 100  # Should be fast
        assert result.metadata["max_connections"] == 100
        assert result.metadata["max_keepalive"] == 20

    @pytest.mark.asyncio
    async def test_client_healthy_with_successful_connectivity(self) -> None:
        """Should return HEALTHY with successful connectivity test."""
        # Create mock HTTP client adapter
        mock_adapter = MagicMock()
        mock_adapter.settings = MagicMock()
        mock_adapter.settings.max_connections = 100
        mock_adapter.settings.max_keepalive_connections = 20
        mock_adapter.settings.timeout = 30

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_adapter._create_client = AsyncMock(return_value=mock_client)

        result = await check_http_client_health(
            http_client=mock_adapter,
            test_url="https://httpbin.org/status/200",
        )

        assert result.name == "http_client"
        assert result.status == HealthStatus.HEALTHY
        assert "successful connectivity test" in result.message.lower()
        assert result.latency_ms is not None
        assert result.metadata["status_code"] == 200
        assert result.metadata["test_url"] == "https://httpbin.org/status/200"

    @pytest.mark.asyncio
    async def test_client_degraded_http_error(self) -> None:
        """Should return DEGRADED when connectivity test returns HTTP error."""
        mock_adapter = MagicMock()
        mock_adapter.settings = MagicMock()
        mock_adapter.settings.max_connections = 100
        mock_adapter.settings.max_keepalive_connections = 20
        mock_adapter.settings.timeout = 30

        # Mock HTTP 500 error response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_adapter._create_client = AsyncMock(return_value=mock_client)

        result = await check_http_client_health(
            http_client=mock_adapter,
            test_url="https://httpbin.org/status/500",
        )

        assert result.name == "http_client"
        assert result.status == HealthStatus.DEGRADED
        assert "connectivity test failed" in result.message.lower()
        assert result.metadata["status_code"] == 500

    @pytest.mark.asyncio
    async def test_client_degraded_timeout(self) -> None:
        """Should return DEGRADED when connectivity test times out."""
        mock_adapter = MagicMock()
        mock_adapter.settings = MagicMock()
        mock_adapter.settings.max_connections = 100
        mock_adapter.settings.max_keepalive_connections = 20
        mock_adapter.settings.timeout = 30

        # Mock timeout exception
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
        mock_adapter._create_client = AsyncMock(return_value=mock_client)

        result = await check_http_client_health(
            http_client=mock_adapter,
            test_url="https://slow.example.com",
        )

        assert result.name == "http_client"
        assert result.status == HealthStatus.DEGRADED
        assert "timeout" in result.message.lower()
        assert result.metadata["error"] == "timeout"

    @pytest.mark.asyncio
    async def test_client_degraded_high_latency(self) -> None:
        """Should return DEGRADED when response latency exceeds threshold."""
        mock_adapter = MagicMock()
        mock_adapter.settings = MagicMock()
        mock_adapter.settings.max_connections = 100
        mock_adapter.settings.max_keepalive_connections = 20
        mock_adapter.settings.timeout = 30

        # Mock slow response
        import asyncio

        async def slow_get(*args, **kwargs):
            await asyncio.sleep(0.01)  # 10ms delay
            response = MagicMock()
            response.status_code = 200
            return response

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = slow_get
        mock_adapter._create_client = AsyncMock(return_value=mock_client)

        result = await check_http_client_health(
            http_client=mock_adapter,
            test_url="https://example.com",
            timeout_ms=5,  # Very low threshold
        )

        assert result.name == "http_client"
        assert result.status == HealthStatus.DEGRADED
        assert "high latency" in result.message.lower()
        assert result.latency_ms is not None
        assert result.latency_ms > 5

    @pytest.mark.asyncio
    async def test_client_unhealthy_initialization_failure(self) -> None:
        """Should return UNHEALTHY when client initialization fails."""
        mock_adapter = MagicMock()
        mock_adapter._create_client = AsyncMock(
            side_effect=RuntimeError("Failed to create client")
        )

        result = await check_http_client_health(http_client=mock_adapter)

        assert result.name == "http_client"
        assert result.status == HealthStatus.UNHEALTHY
        assert "health check failed" in result.message.lower()
        assert "Failed to create client" in result.message

    @pytest.mark.asyncio
    async def test_client_unhealthy_returns_none(self) -> None:
        """Should return UNHEALTHY when client creation returns None."""
        mock_adapter = MagicMock()
        mock_adapter.settings = MagicMock()
        mock_adapter._create_client = AsyncMock(return_value=None)

        result = await check_http_client_health(http_client=mock_adapter)

        assert result.name == "http_client"
        assert result.status == HealthStatus.UNHEALTHY
        assert "returned none" in result.message.lower()

    @pytest.mark.asyncio
    async def test_client_uses_di_when_not_provided(self) -> None:
        """Should use DI to get client when none provided."""
        # Mock the DI container
        mock_adapter = MagicMock()
        mock_adapter.settings = MagicMock()
        mock_adapter.settings.max_connections = 100
        mock_adapter.settings.max_keepalive_connections = 20
        mock_adapter.settings.timeout = 30
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_adapter._create_client = AsyncMock(return_value=mock_client)

        with patch("acb.depends.depends") as mock_depends:
            mock_depends.get_sync.return_value = mock_adapter

            result = await check_http_client_health()

            assert result.status == HealthStatus.HEALTHY
            mock_depends.get_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_client_unhealthy_di_failure(self) -> None:
        """Should return UNHEALTHY when DI fails to provide client."""
        with patch("acb.depends.depends") as mock_depends:
            mock_depends.get_sync.side_effect = RuntimeError("DI container not initialized")

            result = await check_http_client_health()

            assert result.status == HealthStatus.UNHEALTHY
            assert "Failed to initialize HTTP client" in result.message


class TestHTTPConnectivityCheck:
    """Test HTTP connectivity check."""

    @pytest.mark.asyncio
    async def test_connectivity_healthy(self) -> None:
        """Should return HEALTHY with successful connectivity."""
        mock_adapter = MagicMock()
        mock_adapter.settings = MagicMock()
        mock_adapter.settings.timeout = 30

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_adapter._create_client = AsyncMock(return_value=mock_client)

        result = await check_http_connectivity(
            url="https://api.example.com/health",
            http_client=mock_adapter,
        )

        assert result.name == "http_connectivity"
        assert result.status == HealthStatus.HEALTHY
        assert "successful" in result.message.lower()
        assert result.metadata["status_code"] == 200
        assert result.metadata["url"] == "https://api.example.com/health"

    @pytest.mark.asyncio
    async def test_connectivity_degraded_wrong_status(self) -> None:
        """Should return DEGRADED when status code doesn't match expected."""
        mock_adapter = MagicMock()
        mock_adapter.settings = MagicMock()
        mock_adapter.settings.timeout = 30

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_adapter._create_client = AsyncMock(return_value=mock_client)

        result = await check_http_connectivity(
            url="https://api.example.com/health",
            expected_status=200,
            http_client=mock_adapter,
        )

        assert result.name == "http_connectivity"
        assert result.status == HealthStatus.DEGRADED
        assert "unexpected status code" in result.message.lower()
        assert result.metadata["status_code"] == 404
        assert result.metadata["expected_status"] == 200

    @pytest.mark.asyncio
    async def test_connectivity_degraded_high_latency(self) -> None:
        """Should return DEGRADED when latency exceeds threshold."""
        mock_adapter = MagicMock()
        mock_adapter.settings = MagicMock()
        mock_adapter.settings.timeout = 30

        import asyncio

        async def slow_get(*args, **kwargs):
            await asyncio.sleep(0.01)  # 10ms delay
            response = MagicMock()
            response.status_code = 200
            return response

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = slow_get
        mock_adapter._create_client = AsyncMock(return_value=mock_client)

        result = await check_http_connectivity(
            url="https://slow.example.com",
            timeout_ms=5,  # Very low threshold
            http_client=mock_adapter,
        )

        assert result.name == "http_connectivity"
        assert result.status == HealthStatus.DEGRADED
        assert "high latency" in result.message.lower()
        assert result.latency_ms is not None
        assert result.latency_ms > 5

    @pytest.mark.asyncio
    async def test_connectivity_unhealthy_timeout(self) -> None:
        """Should return UNHEALTHY when request times out."""
        mock_adapter = MagicMock()
        mock_adapter.settings = MagicMock()
        mock_adapter.settings.timeout = 30

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        mock_adapter._create_client = AsyncMock(return_value=mock_client)

        result = await check_http_connectivity(
            url="https://timeout.example.com",
            http_client=mock_adapter,
        )

        assert result.name == "http_connectivity"
        assert result.status == HealthStatus.UNHEALTHY
        assert "timeout" in result.message.lower()
        assert result.metadata["error"] == "timeout"

    @pytest.mark.asyncio
    async def test_connectivity_unhealthy_http_error(self) -> None:
        """Should return UNHEALTHY for HTTP errors."""
        mock_adapter = MagicMock()
        mock_adapter.settings = MagicMock()
        mock_adapter.settings.timeout = 30

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPError("Connection refused")
        )
        mock_adapter._create_client = AsyncMock(return_value=mock_client)

        result = await check_http_connectivity(
            url="https://unreachable.example.com",
            http_client=mock_adapter,
        )

        assert result.name == "http_connectivity"
        assert result.status == HealthStatus.UNHEALTHY
        assert "http error" in result.message.lower()
        assert "Connection refused" in result.message

    @pytest.mark.asyncio
    async def test_connectivity_unhealthy_di_failure(self) -> None:
        """Should return UNHEALTHY when DI fails."""
        with patch("acb.depends.depends") as mock_depends:
            mock_depends.get_sync.side_effect = RuntimeError("DI error")

            result = await check_http_connectivity(url="https://example.com")

            assert result.status == HealthStatus.UNHEALTHY
            assert "Failed to initialize HTTP client" in result.message
