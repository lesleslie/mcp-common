"""HTTP Client health check utilities for MCP servers.

Provides health checks for HTTPClientAdapter including:
- Client initialization status
- Connection pool health
- Basic connectivity tests
- Response latency monitoring

Phase 10.1: Production Hardening - HTTP Client Health Checks
"""

from __future__ import annotations

import time
import typing as t

import httpx

from mcp_common.health import ComponentHealth, HealthStatus

if t.TYPE_CHECKING:
    from mcp_common.adapters.http.client import HTTPClientAdapter


async def check_http_client_health(
    http_client: HTTPClientAdapter | None = None,
    test_url: str | None = None,
    timeout_ms: float = 5000,
) -> ComponentHealth:
    """Check HTTP client adapter health.

    Args:
        http_client: Optional HTTPClientAdapter instance (uses DI if None)
        test_url: Optional URL to test connectivity (no request if None)
        timeout_ms: Maximum acceptable response time in milliseconds

    Returns:
        ComponentHealth with HTTP client status

    Checks:
        - Client can be initialized
        - Connection pool is configured
        - Optional: Basic connectivity test
        - Optional: Response latency within bounds

    Example:
        >>> # Basic client health check
        >>> result = await check_http_client_health()
        >>>
        >>> # With connectivity test
        >>> result = await check_http_client_health(
        ...     test_url="https://httpbin.org/status/200"
        ... )
    """
    start_time = time.perf_counter()

    # Try to get HTTP client
    if http_client is None:
        try:
            from acb.depends import depends

            from mcp_common.adapters.http.client import HTTPClientAdapter

            http_client = depends.get_sync(HTTPClientAdapter)
        except Exception as e:
            return ComponentHealth(
                name="http_client",
                status=HealthStatus.UNHEALTHY,
                message=f"Failed to initialize HTTP client: {e}",
                metadata={"error": str(e), "error_type": type(e).__name__},
            )

    # Check if client can be created
    try:
        client = await http_client._create_client()

        # Verify client is configured
        if client is None:
            return ComponentHealth(
                name="http_client",
                status=HealthStatus.UNHEALTHY,
                message="HTTP client created but returned None",
            )

        # Get connection pool info
        metadata: dict[str, t.Any] = {
            "max_connections": http_client.settings.max_connections,
            "max_keepalive": http_client.settings.max_keepalive_connections,
            "timeout": http_client.settings.timeout,
        }

        # If test URL provided, perform connectivity test
        if test_url:
            try:
                response = await client.get(test_url, timeout=http_client.settings.timeout)
                latency_ms = (time.perf_counter() - start_time) * 1000

                # Check if response is successful
                if response.status_code >= 400:
                    return ComponentHealth(
                        name="http_client",
                        status=HealthStatus.DEGRADED,
                        message=f"Connectivity test failed: HTTP {response.status_code}",
                        latency_ms=latency_ms,
                        metadata={
                            **metadata,
                            "test_url": test_url,
                            "status_code": response.status_code,
                        },
                    )

                # Check latency
                if latency_ms > timeout_ms:
                    return ComponentHealth(
                        name="http_client",
                        status=HealthStatus.DEGRADED,
                        message=f"High latency detected: {latency_ms:.2f}ms (threshold: {timeout_ms}ms)",
                        latency_ms=latency_ms,
                        metadata={
                            **metadata,
                            "test_url": test_url,
                            "status_code": response.status_code,
                            "threshold_ms": timeout_ms,
                        },
                    )

                # All checks passed
                return ComponentHealth(
                    name="http_client",
                    status=HealthStatus.HEALTHY,
                    message="HTTP client operational with successful connectivity test",
                    latency_ms=latency_ms,
                    metadata={
                        **metadata,
                        "test_url": test_url,
                        "status_code": response.status_code,
                    },
                )

            except httpx.TimeoutException:
                latency_ms = (time.perf_counter() - start_time) * 1000
                return ComponentHealth(
                    name="http_client",
                    status=HealthStatus.DEGRADED,
                    message=f"Connectivity test timeout after {latency_ms:.2f}ms",
                    latency_ms=latency_ms,
                    metadata={
                        **metadata,
                        "test_url": test_url,
                        "error": "timeout",
                    },
                )

            except Exception as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                return ComponentHealth(
                    name="http_client",
                    status=HealthStatus.DEGRADED,
                    message=f"Connectivity test error: {e}",
                    latency_ms=latency_ms,
                    metadata={
                        **metadata,
                        "test_url": test_url,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )

        # No connectivity test, just verify initialization
        latency_ms = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            name="http_client",
            status=HealthStatus.HEALTHY,
            message="HTTP client initialized and ready",
            latency_ms=latency_ms,
            metadata=metadata,
        )

    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            name="http_client",
            status=HealthStatus.UNHEALTHY,
            message=f"HTTP client health check failed: {e}",
            latency_ms=latency_ms,
            metadata={"error": str(e), "error_type": type(e).__name__},
        )


async def check_http_connectivity(
    url: str,
    expected_status: int = 200,
    timeout_ms: float = 5000,
    http_client: HTTPClientAdapter | None = None,
) -> ComponentHealth:
    """Check connectivity to a specific HTTP endpoint.

    Args:
        url: Target URL to test
        expected_status: Expected HTTP status code (default: 200)
        timeout_ms: Maximum acceptable response time in milliseconds
        http_client: Optional HTTPClientAdapter instance

    Returns:
        ComponentHealth with connectivity status

    Example:
        >>> result = await check_http_connectivity(
        ...     url="https://api.example.com/health",
        ...     expected_status=200
        ... )
    """
    start_time = time.perf_counter()

    # Get HTTP client
    if http_client is None:
        try:
            from acb.depends import depends

            from mcp_common.adapters.http.client import HTTPClientAdapter

            http_client = depends.get_sync(HTTPClientAdapter)
        except Exception as e:
            return ComponentHealth(
                name="http_connectivity",
                status=HealthStatus.UNHEALTHY,
                message=f"Failed to initialize HTTP client: {e}",
                metadata={
                    "url": url,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

    try:
        client = await http_client._create_client()
        response = await client.get(url, timeout=http_client.settings.timeout)
        latency_ms = (time.perf_counter() - start_time) * 1000

        # Check status code
        if response.status_code != expected_status:
            return ComponentHealth(
                name="http_connectivity",
                status=HealthStatus.DEGRADED,
                message=f"Unexpected status code: {response.status_code} (expected: {expected_status})",
                latency_ms=latency_ms,
                metadata={
                    "url": url,
                    "status_code": response.status_code,
                    "expected_status": expected_status,
                },
            )

        # Check latency
        if latency_ms > timeout_ms:
            return ComponentHealth(
                name="http_connectivity",
                status=HealthStatus.DEGRADED,
                message=f"High latency: {latency_ms:.2f}ms (threshold: {timeout_ms}ms)",
                latency_ms=latency_ms,
                metadata={
                    "url": url,
                    "status_code": response.status_code,
                    "threshold_ms": timeout_ms,
                },
            )

        # Success
        return ComponentHealth(
            name="http_connectivity",
            status=HealthStatus.HEALTHY,
            message=f"Connectivity test successful: {url}",
            latency_ms=latency_ms,
            metadata={
                "url": url,
                "status_code": response.status_code,
            },
        )

    except httpx.TimeoutException:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            name="http_connectivity",
            status=HealthStatus.UNHEALTHY,
            message=f"Request timeout after {latency_ms:.2f}ms",
            latency_ms=latency_ms,
            metadata={"url": url, "error": "timeout"},
        )

    except httpx.HTTPError as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            name="http_connectivity",
            status=HealthStatus.UNHEALTHY,
            message=f"HTTP error: {e}",
            latency_ms=latency_ms,
            metadata={
                "url": url,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )

    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            name="http_connectivity",
            status=HealthStatus.UNHEALTHY,
            message=f"Connectivity check failed: {e}",
            latency_ms=latency_ms,
            metadata={
                "url": url,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )


__all__ = [
    "check_http_client_health",
    "check_http_connectivity",
]
