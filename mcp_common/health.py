"""Health check infrastructure for MCP servers.

Provides standardized health check responses with component-level detail,
supporting production deployments with Docker and Kubernetes orchestration.

Phase 10.1: Production Hardening - Health Check Endpoints

Extended 2026-02-27: Added HTTP dependency checking with Oneiric integration.
See docs/plans/2026-02-27-health-check-system-design.md for design rationale.
"""

from __future__ import annotations

import asyncio
import time
import typing as t
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class HealthStatus(StrEnum):
    """Health check status values.

    Attributes:
        HEALTHY: All components operating normally
        DEGRADED: Some components experiencing issues but service functional
        UNHEALTHY: Critical components failing, service unavailable
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

    def __str__(self) -> str:
        """Return string representation of status."""
        return str(self.value)

    def __lt__(self, other: object) -> bool:
        """Compare health status severity (healthy < degraded < unhealthy)."""
        if not isinstance(other, HealthStatus):
            return NotImplemented
        order = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DEGRADED: 1,
            HealthStatus.UNHEALTHY: 2,
        }
        return order[self] < order[other]

    def __gt__(self, other: object) -> bool:
        """Support greater-than comparisons for max/min operations."""
        if not isinstance(other, HealthStatus):
            return NotImplemented
        order = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DEGRADED: 1,
            HealthStatus.UNHEALTHY: 2,
        }
        return order[self] > order[other]


@dataclass
class ComponentHealth:
    """Health status for an individual component.

    Attributes:
        name: Component identifier (e.g., "database", "external_api")
        status: Current health status of the component
        message: Optional human-readable status message
        latency_ms: Optional latency measurement in milliseconds
        metadata: Additional component-specific health information

    Example:
        >>> component = ComponentHealth(
        ...     name="database",
        ...     status=HealthStatus.HEALTHY,
        ...     message="Connection established",
        ...     latency_ms=12.5
        ... )
    """

    name: str
    status: HealthStatus
    message: str | None = None
    latency_ms: float | None = None
    metadata: dict[str, t.Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, t.Any]:
        """Convert component health to dictionary representation."""
        result: dict[str, t.Any] = {
            "name": self.name,
            "status": self.status.value,
        }
        if self.message is not None:
            result["message"] = self.message
        if self.latency_ms is not None:
            result["latency_ms"] = round(self.latency_ms, 2)
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class HealthCheckResponse:
    """Comprehensive health check response.

    Attributes:
        status: Overall system health status (worst component status)
        timestamp: ISO 8601 timestamp of health check
        version: Server version string
        components: List of component health checks
        uptime_seconds: Server uptime in seconds
        metadata: Additional system-level health information

    Example:
        >>> response = HealthCheckResponse(
        ...     status=HealthStatus.HEALTHY,
        ...     timestamp="2025-10-28T12:00:00Z",
        ...     version="1.0.0",
        ...     components=[component],
        ...     uptime_seconds=3600.0
        ... )
    """

    status: HealthStatus
    timestamp: str
    version: str
    components: list[ComponentHealth]
    uptime_seconds: float
    metadata: dict[str, t.Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        components: list[ComponentHealth],
        version: str,
        start_time: float,
        metadata: dict[str, t.Any] | None = None,
    ) -> HealthCheckResponse:
        """Create health check response with automatic status aggregation.

        Args:
            components: List of component health checks
            version: Server version string
            start_time: Server start timestamp (time.time())
            metadata: Optional system-level metadata

        Returns:
            HealthCheckResponse with aggregated status

        Note:
            Overall status is determined by the worst component status:
            - All HEALTHY -> HEALTHY
            - Any DEGRADED -> DEGRADED
            - Any UNHEALTHY -> UNHEALTHY
        """
        # Aggregate overall status (worst component status)
        # Use the __lt__ comparison we defined (HEALTHY < DEGRADED < UNHEALTHY)
        overall_status = HealthStatus.HEALTHY
        if components:
            overall_status = max(c.status for c in components)

        return cls(
            status=overall_status,
            timestamp=datetime.now(UTC).isoformat(),
            version=version,
            components=components,
            uptime_seconds=time.time() - start_time,
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, t.Any]:
        """Convert health check response to dictionary representation.

        Returns:
            Dictionary suitable for JSON serialization
        """
        result: dict[str, t.Any] = {
            "status": self.status.value,
            "timestamp": self.timestamp,
            "version": self.version,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "components": [c.to_dict() for c in self.components],
        }
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    def is_healthy(self) -> bool:
        """Check if overall health is HEALTHY."""
        return self.status == HealthStatus.HEALTHY

    def is_ready(self) -> bool:
        """Check if system is ready to accept requests (not UNHEALTHY)."""
        return self.status != HealthStatus.UNHEALTHY


# Type alias for health check functions
HealthCheckFunc = t.Callable[[], t.Awaitable[ComponentHealth]]


# =============================================================================
# HTTP Dependency Checking (Oneiric Integration)
# =============================================================================


@dataclass
class DependencyConfig:
    """Configuration for an HTTP dependency health check.

    Attributes:
        host: Hostname or IP address
        port: Port number
        required: Whether this dependency is required for startup
        timeout_seconds: Maximum wait time during startup
        use_tls: Use HTTPS instead of HTTP
        health_path: Path to health endpoint (default: /health)
    """

    host: str = "localhost"
    port: int = 8080
    required: bool = True
    timeout_seconds: int = 30
    use_tls: bool = False
    health_path: str = "/health"

    def to_url(self) -> str:
        """Build the health check URL."""
        scheme = "https" if self.use_tls else "http"
        return f"{scheme}://{self.host}:{self.port}{self.health_path}"


@dataclass
class HealthCheckResult:
    """Result of a single health check operation.

    Attributes:
        service_name: Name of the checked service
        status: Health status (OK, DEGRADED, UNHEALTHY)
        latency_ms: Response latency in milliseconds
        error: Error message if check failed
        response_data: Response body if available
    """

    service_name: str
    status: HealthStatus
    latency_ms: float = 0.0
    error: str | None = None
    response_data: dict[str, t.Any] | None = None

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary."""
        result: dict[str, t.Any] = {
            "service_name": self.service_name,
            "status": self.status.value,
            "latency_ms": round(self.latency_ms, 2),
        }
        if self.error:
            result["error"] = self.error
        if self.response_data:
            result["response"] = self.response_data
        return result


@dataclass
class WaitResult:
    """Result of waiting for dependencies.

    Attributes:
        success: Whether all required dependencies are healthy
        dependencies: Per-dependency health check results
        total_wait_seconds: Total time spent waiting
        failed_required: List of failed required dependency names
        skipped_optional: List of skipped optional dependency names
    """

    success: bool
    dependencies: dict[str, HealthCheckResult]
    total_wait_seconds: float
    failed_required: list[str] = field(default_factory=list)
    skipped_optional: list[str] = field(default_factory=list)


class HealthChecker:
    """HTTP health checker using Oneiric's HttpFetchAction.

    Provides health checking for HTTP endpoints with configurable timeout
    and TLS support. Uses Oneiric's HTTP infrastructure for observability.

    Example:
        >>> checker = HealthChecker()
        >>> result = await checker.check("http://localhost:8678/health")
        >>> print(result.status)
        HealthStatus.HEALTHY
    """

    def __init__(self, timeout_seconds: int = 5) -> None:
        """Initialize health checker.

        Args:
            timeout_seconds: Default timeout for health check requests
        """
        self._timeout = timeout_seconds
        self._http_action = self._create_http_action()

    def _create_http_action(self) -> t.Any:
        """Create HTTP action, with fallback if Oneiric unavailable."""
        try:
            from oneiric.actions.http import HttpFetchAction

            return HttpFetchAction()
        except ImportError:
            # Fallback to httpx directly if Oneiric not available
            return _HttpxFallback()

    async def check(
        self,
        url: str,
        timeout: int | None = None,
        service_name: str = "unknown",
    ) -> HealthCheckResult:
        """Check health of an HTTP endpoint.

        Args:
            url: Health check URL
            timeout: Request timeout (uses default if not specified)
            service_name: Service name for result

        Returns:
            HealthCheckResult with status and latency
        """
        start_time = time.time()
        timeout = timeout or self._timeout

        try:
            result = await self._http_action.execute(
                {
                    "url": url,
                    "method": "GET",
                    "timeout": timeout,
                }
            )

            latency_ms = (time.time() - start_time) * 1000

            # Check for HTTP errors
            if not result.get("ok", False):
                status_code = result.get("status_code", "unknown")
                return HealthCheckResult(
                    service_name=service_name,
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=latency_ms,
                    error=f"HTTP {status_code}",
                )

            # Parse response
            response_json = result.get("json", {}) or {}
            response_status = response_json.get("status", "healthy")

            # Map status string to enum
            if response_status in ("healthy", "ok", "up"):
                status = HealthStatus.HEALTHY
            elif response_status in ("degraded", "warning"):
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY

            return HealthCheckResult(
                service_name=service_name,
                status=status,
                latency_ms=latency_ms,
                response_data=response_json,
            )

        except asyncio.TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name=service_name,
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                error="Timeout",
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name=service_name,
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                error=str(e),
            )


class _HttpxFallback:
    """Fallback HTTP client when Oneiric is unavailable."""

    async def execute(
        self,
        url: str,
        method: str = "GET",
        timeout: int = 5,
    ) -> dict[str, t.Any]:
        """Execute HTTP request using httpx."""
        import httpx

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.request(method, url)
                return {
                    "ok": response.is_success,
                    "status_code": response.status_code,
                    "json": response.json() if response.content else None,
                }
            except httpx.TimeoutException:
                return {"ok": False, "status_code": None, "json": None}
            except Exception:
                return {"ok": False, "status_code": None, "json": None}


class DependencyWaiter:
    """Wait for dependencies to become healthy using exponential backoff.

    Used during startup to wait for required services. Implements exponential
    backoff with configurable delays to avoid overwhelming dependencies.

    Example:
        >>> waiter = DependencyWaiter()
        >>> dependencies = {
        ...     "session_buddy": DependencyConfig(port=8678, required=True),
        ... }
        >>> result = await waiter.wait_for_all(dependencies)
        >>> if not result.success:
        ...     print(f"Failed: {result.failed_required}")
    """

    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 16.0,
    ) -> None:
        """Initialize dependency waiter.

        Args:
            base_delay: Initial delay between retries (seconds)
            max_delay: Maximum delay between retries (seconds)
        """
        self._checker = HealthChecker()
        self._base_delay = base_delay
        self._max_delay = max_delay

    async def wait_for_all(
        self,
        dependencies: dict[str, DependencyConfig],
    ) -> WaitResult:
        """Wait for all dependencies to become healthy.

        Args:
            dependencies: Dict of dependency name -> config

        Returns:
            WaitResult with overall status and per-dependency results
        """
        start_time = time.time()
        results: dict[str, HealthCheckResult] = {}
        failed_required: list[str] = []
        skipped_optional: list[str] = []

        for name, config in dependencies.items():
            result = await self._wait_for_single(name, config)
            results[name] = result

            if result.status == HealthStatus.UNHEALTHY:
                if config.required:
                    failed_required.append(name)
                else:
                    skipped_optional.append(name)

        return WaitResult(
            success=len(failed_required) == 0,
            dependencies=results,
            total_wait_seconds=time.time() - start_time,
            failed_required=failed_required,
            skipped_optional=skipped_optional,
        )

    async def _wait_for_single(
        self,
        name: str,
        config: DependencyConfig,
    ) -> HealthCheckResult:
        """Wait for a single dependency with exponential backoff."""
        url = config.to_url()
        deadline = time.time() + config.timeout_seconds
        delay = self._base_delay

        while time.time() < deadline:
            result = await self._checker.check(
                url,
                timeout=5,
                service_name=name,
            )

            if result.status != HealthStatus.UNHEALTHY:
                return result

            # Wait before retry
            await asyncio.sleep(delay)
            delay = min(delay * 2, self._max_delay)

        # Final attempt
        return await self._checker.check(
            url,
            timeout=5,
            service_name=name,
        )


# =============================================================================
# FastMCP Tool Registration
# =============================================================================


def register_health_tools(
    mcp: t.Any,
    service_name: str = "mcp-server",
    version: str = "0.0.0",
    start_time: float | None = None,
    dependencies: dict[str, DependencyConfig] | None = None,
) -> None:
    """Register health check MCP tools with FastMCP server.

    This function adds standard health check tools that can be used by
    orchestration platforms, load balancers, and other services.

    Tools registered:
        - health_check_service: Check health of a specific service
        - health_check_all: Check all configured dependencies
        - wait_for_dependency: Wait for a dependency to become healthy
        - wait_for_all_dependencies: Wait for all dependencies
        - get_liveness: Basic liveness probe (is process running)
        - get_readiness: Readiness probe (can accept work)

    Args:
        mcp: FastMCP server instance
        service_name: Name of this service
        version: Service version
        start_time: Server start time (time.time()), defaults to now
        dependencies: Configured dependencies to check

    Example:
        >>> from fastmcp import FastMCP
        >>> from mcp_common.health import register_health_tools, DependencyConfig
        >>>
        >>> mcp = FastMCP(name="my-server")
        >>> dependencies = {
        ...     "session_buddy": DependencyConfig(port=8678, required=True),
        ... }
        >>> register_health_tools(mcp, "my-server", "1.0.0", dependencies=dependencies)
    """
    if start_time is None:
        start_time = time.time()

    if dependencies is None:
        dependencies = {}

    checker = HealthChecker()
    waiter = DependencyWaiter()

    @mcp.tool()
    async def health_check_service(
        service_name_arg: str,
        host: str = "localhost",
        port: int = 8080,
        timeout: int = 5,
        use_tls: bool = False,
    ) -> dict[str, t.Any]:
        """Check health of a specific service.

        Performs an HTTP GET request to the service's /health endpoint.

        Args:
            service_name_arg: Name of the service to check
            host: Hostname or IP address
            port: Port number
            timeout: Request timeout in seconds
            use_tls: Use HTTPS instead of HTTP

        Returns:
            Health status dictionary with status, latency, and any errors
        """
        config = DependencyConfig(host=host, port=port, use_tls=use_tls)
        result = await checker.check(
            config.to_url(),
            timeout=timeout,
            service_name=service_name_arg,
        )
        return result.to_dict()

    @mcp.tool()
    async def health_check_all() -> dict[str, t.Any]:
        """Check health of all configured dependencies.

        Returns:
            Dictionary with health status of all services
        """
        if not dependencies:
            return {
                "status": "healthy",
                "services": {},
                "message": "No dependencies configured",
            }

        tasks = {
            name: checker.check(config.to_url(), service_name=name)
            for name, config in dependencies.items()
        }

        results = {}
        if tasks:
            gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for (name, _), result in zip(tasks.items(), gathered):
                if isinstance(result, Exception):
                    results[name] = {
                        "status": HealthStatus.UNHEALTHY.value,
                        "error": str(result),
                    }
                else:
                    results[name] = result.to_dict()

        all_ok = all(
            r.get("status") in (HealthStatus.HEALTHY.value, HealthStatus.DEGRADED.value)
            for r in results.values()
        )

        return {
            "status": HealthStatus.HEALTHY.value if all_ok else HealthStatus.UNHEALTHY.value,
            "services": results,
            "total_services": len(results),
            "healthy_services": sum(
                1 for r in results.values() if r.get("status") == HealthStatus.HEALTHY.value
            ),
        }

    @mcp.tool()
    async def wait_for_dependency(
        dep_service_name: str,
        host: str = "localhost",
        port: int = 8080,
        timeout: int = 30,
        required: bool = True,
        use_tls: bool = False,
    ) -> dict[str, t.Any]:
        """Wait for a specific dependency to become healthy.

        Uses exponential backoff for retries.

        Args:
            dep_service_name: Name of the service to wait for
            host: Hostname or IP address
            port: Port number
            timeout: Maximum wait time in seconds
            required: Whether this is a required dependency
            use_tls: Use HTTPS instead of HTTP

        Returns:
            Result indicating success or timeout
        """
        config = DependencyConfig(
            host=host,
            port=port,
            required=required,
            timeout_seconds=timeout,
            use_tls=use_tls,
        )

        start = time.time()
        result = await waiter.wait_for_all({dep_service_name: config})
        elapsed = time.time() - start

        dep_result = result.dependencies.get(dep_service_name)

        response: dict[str, t.Any] = {
            "service_name": dep_service_name,
            "success": result.success or (not required and dep_result is not None),
            "elapsed_seconds": elapsed,
            "timeout_seconds": timeout,
        }

        if dep_result:
            response["status"] = dep_result.status.value
            response["latency_ms"] = dep_result.latency_ms
            if dep_result.error:
                response["error"] = dep_result.error

        if not result.success and required:
            response["message"] = (
                f"Required dependency '{dep_service_name}' did not become healthy within {timeout}s"
            )

        return response

    @mcp.tool()
    async def wait_for_all_dependencies() -> dict[str, t.Any]:
        """Wait for all configured dependencies to become healthy.

        Returns:
            Result indicating overall success and per-dependency status
        """
        if not dependencies:
            return {
                "success": True,
                "message": "No dependencies configured",
                "dependencies": {},
                "total_wait_seconds": 0,
            }

        result = await waiter.wait_for_all(dependencies)

        response: dict[str, t.Any] = {
            "success": result.success,
            "total_wait_seconds": result.total_wait_seconds,
            "failed_required": result.failed_required,
            "skipped_optional": result.skipped_optional,
        }

        deps_status = {
            name: dep_result.to_dict()
            for name, dep_result in result.dependencies.items()
        }
        response["dependencies"] = deps_status

        if not result.success:
            response["message"] = (
                f"Failed to connect to required dependencies: {', '.join(result.failed_required)}"
            )

        return response

    @mcp.tool()
    async def get_liveness() -> dict[str, t.Any]:
        """Get liveness status for this service.

        Returns basic "is this process running" information.
        Called by platform health checks (Cloud Run, Kubernetes, etc.).

        Returns:
            Health response with status, service name, version, and uptime
        """
        return {
            "status": "ok",
            "service": service_name,
            "version": version,
            "uptime_seconds": round(time.time() - start_time, 2),
        }

    @mcp.tool()
    async def get_readiness() -> dict[str, t.Any]:
        """Get readiness status for this service.

        Checks if this service is ready to accept work by verifying
        all dependencies are healthy.

        Returns:
            Readiness response with dependency status
        """
        if not dependencies:
            return {
                "ready": True,
                "service": service_name,
                "checks": {"process": "ok"},
            }

        result = await waiter.wait_for_all(dependencies)

        checks: dict[str, str] = {"process": "ok"}
        checks.update({
            name: dep_result.status.value
            for name, dep_result in result.dependencies.items()
        })

        return {
            "ready": result.success,
            "service": service_name,
            "checks": checks,
            "failed_required": result.failed_required,
        }


__all__ = [
    # Core types
    "ComponentHealth",
    "HealthCheckFunc",
    "HealthCheckResponse",
    "HealthStatus",
    # HTTP dependency checking
    "DependencyConfig",
    "HealthCheckResult",
    "WaitResult",
    "HealthChecker",
    "DependencyWaiter",
    # FastMCP integration
    "register_health_tools",
]
