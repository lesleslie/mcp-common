"""Health check infrastructure for MCP servers.

Provides standardized health check responses with component-level detail,
supporting production deployments with Docker and Kubernetes orchestration.

Phase 10.1: Production Hardening - Health Check Endpoints
"""

from __future__ import annotations

import time
import typing as t
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class HealthStatus(str, Enum):
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
        order = {HealthStatus.HEALTHY: 0, HealthStatus.DEGRADED: 1, HealthStatus.UNHEALTHY: 2}
        return order[self] < order[other]

    def __gt__(self, other: object) -> bool:
        """Support greater-than comparisons for max/min operations."""
        if not isinstance(other, HealthStatus):
            return NotImplemented
        order = {HealthStatus.HEALTHY: 0, HealthStatus.DEGRADED: 1, HealthStatus.UNHEALTHY: 2}
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


__all__ = [
    "ComponentHealth",
    "HealthCheckFunc",
    "HealthCheckResponse",
    "HealthStatus",
]
