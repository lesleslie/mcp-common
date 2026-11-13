"""Health check infrastructure for MCP servers.

Provides standardized health check responses with component-level detail,
supporting production deployments with Docker and Kubernetes orchestration.

Phase 10.1: Production Hardening - Health Check Endpoints

Extended 2026-02-27: Added HTTP dependency checking with Oneiric integration.
See docs/plans/2026-02-27-health-check-system-design.md for design rationale.

Phase 1 (2026-09-14, transport unification plan §5 tasks 4 + 5):
    Added the :mod:`mcp_common.health.feed` sub-module
    (``HealthFeedState``, ``StatusValue``, ``ReasonCode``, ``record_success`` /
    ``record_error`` / ``is_healthy``) and :mod:`mcp_common.health.aggregator`
    (``aggregate_feed_states``). The package layout moved from a flat
    ``health.py`` to ``mcp_common/health/``; all existing
    ``from mcp_common.health import X`` paths continue to work because the
    public API is re-exported from this ``__init__.py``.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import typing as t
import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from weakref import WeakSet

from mcp_common.auth.health import AuthHealth

# Phase 1 (2026-09-14): re-exports of the new feed-state + aggregator types.
from mcp_common.health.aggregator import aggregate_feed_states
from mcp_common.health.feed import (
    HealthFeedState,
    ReasonCode,
    StatusValue,
    is_healthy,
    record_error,
    record_success,
)
from mcp_common.health.metrics import update_health_metrics

logger = logging.getLogger(__name__)


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
        success: Whether all required dependencies became healthy
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
            from oneiric.actions.http import (  # type: ignore[import-untyped]
                HttpFetchAction,
            )

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
            response_json: dict[str, t.Any] = result.get("json", {}) or {}
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

        except TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name=service_name,
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                error="Timeout",
            )
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
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
        import httpx2 as httpx

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
            except (OSError, ValueError, TypeError) as e:
                logger.debug("HTTP fallback failed: %s", e)
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


@dataclass
class LivenessContext:
    """Process-level state required by the ``get_liveness`` tool.

    Attributes:
        start_time: Unix timestamp (from ``time.time()``) marking
            when the server started.
        service_name: Human-readable service identifier (e.g.
            ``"mahavishnu"``, ``"session-buddy"``).
        version: Service version string.

    A module-level singleton of this dataclass is mutated by
    ``seed_liveness_context`` and read by the ``get_liveness`` /
    ``get_readiness`` tools registered by :func:`register_health_tools`.
    The state lives here - in the module that owns the health tools -
    so there is exactly one implementation of the liveness envelope.
    """

    start_time: float = field(default_factory=time.time)
    service_name: str = "mcp-server"
    version: str = "0.0.0"

    def uptime_seconds(self) -> float:
        """Return seconds elapsed since ``start_time``."""
        return max(0.0, time.time() - self.start_time)


# Module-level singleton. Lock protects concurrent seeding from a
# lifespan hook plus a fallback ``register_health_tools`` call.
_LIVENESS_LOCK = threading.Lock()
_LIVENESS_CONTEXT = LivenessContext()

# Servers whose health tools are already registered. FastMCP replaces a
# duplicate registration (logging "Component already exists"), which
# leaves the first copy shadowed - the exact defect the Phase 2 collapse
# removes. Tracking the servers we wired keeps "one registration per
# name" true even when a consumer mounts the health tools twice
# (Session-Buddy mounts ``bootstrap_baseline_tools`` AND
# ``register_health_tools``).
_WIRED_SERVERS: WeakSet[t.Any] = WeakSet()


def _is_wired(mcp: t.Any) -> bool:
    """Return True when the health tools are already registered on ``mcp``."""
    try:
        return mcp in _WIRED_SERVERS
    except TypeError:
        # Not hashable - treat as never wired rather than failing the boot.
        return False


def _mark_wired(mcp: t.Any) -> None:
    """Record that the health tools are registered on ``mcp``."""
    try:
        _WIRED_SERVERS.add(mcp)
    except TypeError:
        # Not weak-referenceable - the guard simply cannot track it.
        pass


def get_liveness_context() -> LivenessContext:
    """Return the current module-level ``LivenessContext``.

    Returns:
        The singleton. May be the seeded-at-import default if
        ``seed_liveness_context`` has not been called.
    """
    with _LIVENESS_LOCK:
        return _LIVENESS_CONTEXT


def seed_liveness_context(
    *,
    service_name: str,
    version: str,
    start_time: float | None = None,
) -> LivenessContext:
    """Seed the module-level ``LivenessContext`` for ``get_liveness``.

    Intended to be called from a FastMCP lifespan hook at server boot.
    Subsequent calls overwrite the singleton - useful for tests that
    reset the start time between scenarios.

    Args:
        service_name: Service identifier written into the
            ``get_liveness`` envelope.
        version: Version string written into the ``get_liveness``
            envelope.
        start_time: Optional Unix timestamp. Defaults to ``time.time()``
            at call time.

    Returns:
        The seeded context, so lifespan hooks can capture and yield it
        if desired.
    """
    if start_time is None:
        start_time = time.time()

    with _LIVENESS_LOCK:
        global _LIVENESS_CONTEXT
        _LIVENESS_CONTEXT = LivenessContext(
            start_time=start_time,
            service_name=service_name,
            version=version,
        )
        seeded = _LIVENESS_CONTEXT

    logger.info(
        "Seeded LivenessContext service=%s version=%s start_time=%.3f",
        service_name,
        version,
        start_time,
    )
    return seeded


def register_health_tools(  # noqa: C901
    mcp: t.Any,
    server_name: str = "mcp-server",
    version: str = "0.0.0",
    start_time: float | None = None,
    dependencies: dict[str, DependencyConfig] | None = None,
    deprecated_tools: Mapping[str, str] | None = None,
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

    These six tools are the single implementation of the Bodai health
    surface. ``mcp_common.baseline_tools`` deliberately registers only
    ``discover_tools`` so a server that mounts both modules cannot
    double-register ``get_liveness`` / ``get_readiness`` /
    ``health_check_all``.

    The liveness state (``service_name`` / ``version`` / ``start_time``)
    is seeded into the module-level :class:`LivenessContext` singleton,
    which the ``get_liveness`` / ``get_readiness`` tools read at call
    time. A lifespan hook that calls :func:`seed_liveness_context`
    therefore still wins over the values passed here.

    Registering twice on the same server is a no-op: the first
    registration owns the tool names, so a server that mounts the
    health surface through two paths (for example Session-Buddy's
    ``bootstrap_baseline_tools`` plus ``register_health_tools``) still
    registers each name exactly once.

    Args:
        mcp: FastMCP server instance
        server_name: Name of *this* service, reported by the
            ``get_liveness`` / ``get_readiness`` envelopes. Deliberately
            not named ``service_name``: the ``health_check_service`` tool
            owns that parameter name, and shadowing it leaked
            ``service_name_arg`` into the published input schema.
        version: Service version string
        start_time: Server start time (time.time()), defaults to now
        dependencies: Configured dependencies to check
        deprecated_tools: Optional mapping of tool name -> replacement
            tool name. A tool whose name is a key emits a
            ``DeprecationWarning`` (and a WARNING log line) when it is
            called, pointing at its replacement. Tool names that are
            absent from the mapping never warn, so a server that
            deprecates nothing stays warning-free.

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
    if _is_wired(mcp):
        logger.debug(
            "Health tools are already registered on this server; skipping "
            "re-registration so each tool name is registered exactly once. "
            "The first registration's identity and dependencies apply."
        )
        return

    if start_time is None:
        start_time = time.time()

    if dependencies is None:
        dependencies = {}

    # The liveness state is owned by this module; seed it with the
    # identity this registration was given so ``get_liveness`` and
    # ``get_readiness`` report it.
    seed_liveness_context(
        service_name=server_name,
        version=version,
        start_time=start_time,
    )

    checker = HealthChecker()
    waiter = DependencyWaiter()

    deprecations: dict[str, str] = dict(deprecated_tools or {})

    def _warn_if_deprecated(tool_name: str) -> None:
        """Warn when ``tool_name`` is listed in ``deprecated_tools``.

        Only names present in the mapping warn - every other tool stays
        silent, so a server that deprecates nothing is warning-free.
        """
        replacement = deprecations.get(tool_name)
        if replacement is None:
            return
        message = f"{tool_name} is deprecated; use {replacement} instead."
        logger.warning(message)
        warnings.warn(message, DeprecationWarning, stacklevel=3)

    @mcp.tool()  # type: ignore[untyped-decorator]
    async def health_check_service(
        service_name: str,
        host: str = "localhost",
        port: int = 8080,
        timeout: int = 5,
        use_tls: bool = False,
        health_path: str = "/health",
    ) -> dict[str, t.Any]:
        """Check health of a specific service.

        Performs an HTTP GET request to the service's health endpoint.

        Args:
            service_name: Name of the service to check
            host: Hostname or IP address
            port: Port number
            timeout: Request timeout in seconds
            use_tls: Use HTTPS instead of HTTP
            health_path: Path to health endpoint (default: /health, MCP servers use /mcp)

        Returns:
            Health status dictionary with status, latency, and any errors
        """
        _warn_if_deprecated("health_check_service")
        config = DependencyConfig(
            host=host, port=port, use_tls=use_tls, health_path=health_path
        )
        result = await checker.check(
            config.to_url(),
            timeout=timeout,
            service_name=service_name,
        )
        return result.to_dict()

    @mcp.tool()  # type: ignore[untyped-decorator]
    async def health_check_all() -> dict[str, t.Any]:
        """Check health of all configured dependencies.

        Returns:
            Dictionary with health status of all services
        """
        _warn_if_deprecated("health_check_all")
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
                    results[name] = t.cast(HealthCheckResult, result).to_dict()

        all_ok = all(
            r.get("status") in (HealthStatus.HEALTHY.value, HealthStatus.DEGRADED.value)
            for r in results.values()
        )

        return {
            "status": HealthStatus.HEALTHY.value
            if all_ok
            else HealthStatus.UNHEALTHY.value,
            "services": results,
            "total_services": len(results),
            "healthy_services": sum(
                1
                for r in results.values()
                if r.get("status") == HealthStatus.HEALTHY.value
            ),
        }

    @mcp.tool()  # type: ignore[untyped-decorator]
    async def wait_for_dependency(
        dep_service_name: str,
        host: str = "localhost",
        port: int = 8080,
        timeout: int = 30,
        required: bool = True,
        use_tls: bool = False,
        health_path: str = "/health",
    ) -> dict[str, t.Any]:
        """Wait for a specific dependency to become healthy.

        Uses exponential backoff for retries.

        Args:
            dep_service_name: Name of the dependency to wait for
            host: Hostname or IP address
            port: Port number
            timeout: Maximum wait time in seconds
            required: Whether this dependency is required
            use_tls: Use HTTPS instead of HTTP
            health_path: Path to health endpoint (default: /health, MCP servers use /mcp)

        Returns:
            Result indicating success or timeout
        """
        _warn_if_deprecated("wait_for_dependency")
        config = DependencyConfig(
            host=host,
            port=port,
            required=required,
            timeout_seconds=timeout,
            use_tls=use_tls,
            health_path=health_path,
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

    @mcp.tool()  # type: ignore[untyped-decorator]
    async def wait_for_all_dependencies() -> dict[str, t.Any]:
        """Wait for all configured dependencies to become healthy.

        Returns:
            Result indicating overall success and per-dependency status
        """
        _warn_if_deprecated("wait_for_all_dependencies")
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

    @mcp.tool()  # type: ignore[untyped-decorator]
    async def get_liveness() -> dict[str, t.Any]:
        """Get liveness status for this service.

        Returns basic "is this process running" information.
        Called by platform health checks (Cloud Run, Kubernetes, etc.).

        Returns:
            Health response with status, service name, version, and uptime
        """
        _warn_if_deprecated("get_liveness")
        ctx = get_liveness_context()
        return {
            "status": "ok",
            "service": ctx.service_name,
            "version": ctx.version,
            "uptime_seconds": round(ctx.uptime_seconds(), 2),
        }

    @mcp.tool()  # type: ignore[untyped-decorator]
    async def get_readiness() -> dict[str, t.Any]:
        """Get readiness status for this service.

        Checks if this service is ready to accept work by verifying
        all dependencies are healthy.

        Returns:
            Readiness response with dependency status
        """
        _warn_if_deprecated("get_readiness")
        ctx = get_liveness_context()
        if not dependencies:
            return {
                "ready": True,
                "service": ctx.service_name,
                "checks": {"process": "ok"},
            }

        result = await waiter.wait_for_all(dependencies)

        checks: dict[str, str] = {"process": "ok"}
        checks.update(
            {
                name: dep_result.status.value
                for name, dep_result in result.dependencies.items()
            }
        )

        return {
            "ready": result.success,
            "service": ctx.service_name,
            "checks": checks,
            "failed_required": result.failed_required,
        }

    # The six tool names are now owned by this server. A second
    # registration on the same server is skipped (see the guard at the
    # top of this function) so each name stays registered exactly once.
    _mark_wired(mcp)


# =============================================================================
# HTTP /health Route Helper
# =============================================================================


def register_http_health_route(
    mcp: t.Any,
    *,
    service_name: str,
    version: str,
    extra_components: list[dict[str, t.Any]] | None = None,
    auth_health_provider: Callable[[], AuthHealth | None] | None = None,
) -> None:
    """Register an HTTP ``/health`` route on the FastMCP server.

    This is the HTTP counterpart to :func:`register_health_tools`. It is
    intended for launchd wrappers, orchestrators, and ad-hoc ``curl`` checks
    that need a plain HTTP ``GET`` to confirm server readiness. Use
    :func:`register_health_tools` for MCP-protocol health endpoints and
    :func:`register_http_health_route` for HTTP readiness probes - the two
    answer different audiences and intentionally coexist.

    The handler always returns HTTP 200 with body shape::

        {"status": "healthy" | "degraded", "service": <service_name>, "version": <version>, "components": [...]}

    The ``status`` field in the body reports the aggregated health using the
    canonical :class:`~mcp_common.health.feed.StatusValue` 4-value enum
    (``healthy`` / ``warming_up`` / ``degraded`` / ``failed``). HTTP status
    code is unconditionally 200 to preserve the launchd probe contract
    across 9 sibling servers. A degraded auth provider flips the body status
    to ``"degraded"`` without changing the response code; the 503 semantic
    is reserved for a future ``/readyz`` endpoint (now removed fleet-wide;
    retained here for historical context). This helper previously hardcoded
    the legacy ``"ok"`` string instead of ``StatusValue.HEALTHY.value``,
    which silently defeated the canonicalization contract across every
    consumer that called it; the fix landed in 0.30.0.

    Args:
        mcp: The FastMCP server instance to register the route on.
        service_name: Short identifier for the service (e.g. ``"css-mcp"``).
        version: Version string for the service (semver, commit sha, or
            ``"unknown"``).
        extra_components: Optional list of component health dicts to merge
            into the response. Each dict is passed through verbatim
            (e.g. ``[{"name": "db", "status": "healthy"}]``).
        auth_health_provider: Optional callable invoked on every request
            to fetch the current :class:`~mcp_common.auth.health.AuthHealth`
            snapshot. The callable is re-invoked per request (not captured
            at registration) so transient flips in provider state surface
            in the very next probe. When the callable returns ``None`` or
            is omitted, the auth component is omitted entirely.

    Example:
        >>> from fastmcp import FastMCP
        >>> from mcp_common.health import register_http_health_route
        >>> mcp = FastMCP(name="my-mcp")
        >>> register_http_health_route(mcp, service_name="my-mcp", version="1.0.0")
    """

    @mcp.custom_route("/health", methods=["GET"])  # type: ignore[untyped-decorator]
    async def http_health(request: t.Any) -> t.Any:
        from starlette.responses import JSONResponse

        # B3 fix: recompute auth health per request, not at registration.
        components = list(extra_components or [])
        auth_health = auth_health_provider() if auth_health_provider else None
        is_degraded = auth_health.is_degraded() if auth_health is not None else False
        if auth_health is not None:
            # as_components() defaults to include_diagnostics=False; the
            # anonymous /health response must not leak last_error strings.
            components.extend(auth_health.as_components())

        # I-7 fix: body status reports canonical StatusValue ("healthy"|"degraded").
        # HTTP code is always 200 to preserve the launchd probe contract
        # across 9 sibling servers. StatusValue is the 4-value enum from
        # ``mcp_common.health.feed`` (the canonical "healthy" / "warming_up" /
        # "degraded" / "failed" set used across all Bodai consumers).
        # Previous implementation emitted the legacy 3-value string ``"ok"``,
        # which silently defeated canonicalization on every consumer that
        # routed through this helper (see feedback-mcp-surface-health-illusion.md);
        # fixed in mcp-common 0.30.0.
        status = (
            StatusValue.DEGRADED.value if is_degraded else StatusValue.HEALTHY.value
        )
        return JSONResponse(
            {
                "status": status,
                "service": service_name,
                "version": version,
                "components": components,
            },
            status_code=200,
        )


__all__ = [
    # Pre-Phase-1 public API (preserved verbatim across the package migration)
    # ComponentHealth, DependencyConfig, DependencyWaiter, HealthCheckFunc,
    # HealthCheckResponse, HealthCheckResult, HealthChecker, HealthStatus,
    # WaitResult, register_health_tools, register_http_health_route
    # Phase 1 (2026-09-14): feed-state aggregator
    # HealthFeedState, ReasonCode, StatusValue, aggregate_feed_states,
    # is_healthy, record_error, record_success
    # Phase 4 (2026-09-15): Prometheus metrics emission
    # update_health_metrics
    # Phase 2 (2026-11-08): liveness state ownership moved here from
    # mcp_common.baseline_tools, which now only registers discover_tools.
    "ComponentHealth",
    "DependencyConfig",
    "DependencyWaiter",
    "HealthCheckFunc",
    "HealthCheckResponse",
    "HealthCheckResult",
    "HealthChecker",
    "HealthFeedState",
    "HealthStatus",
    "LivenessContext",
    "ReasonCode",
    "StatusValue",
    "WaitResult",
    "aggregate_feed_states",
    "get_liveness_context",
    "is_healthy",
    "record_error",
    "record_success",
    "register_health_tools",
    "register_http_health_route",
    "seed_liveness_context",
    "update_health_metrics",
]
