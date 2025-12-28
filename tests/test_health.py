"""Tests for health check infrastructure.

Tests comprehensive health check patterns for MCP servers,
ensuring production-ready health monitoring and status reporting.

Phase 10.1: Production Hardening - Health Check Tests
"""

from __future__ import annotations

import time

from mcp_common.health import ComponentHealth, HealthCheckResponse, HealthStatus


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

    def test_severity_comparison(self) -> None:
        """Should compare by severity (healthy < degraded < unhealthy)."""
        assert HealthStatus.HEALTHY < HealthStatus.DEGRADED
        assert HealthStatus.DEGRADED < HealthStatus.UNHEALTHY
        assert HealthStatus.HEALTHY < HealthStatus.UNHEALTHY

        # Reverse comparisons
        assert not (HealthStatus.DEGRADED < HealthStatus.HEALTHY)
        assert not (HealthStatus.UNHEALTHY < HealthStatus.DEGRADED)
        assert not (HealthStatus.UNHEALTHY < HealthStatus.HEALTHY)


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

    def test_is_healthy(self) -> None:
        """Should check if overall health is HEALTHY."""
        components_healthy = [ComponentHealth(name="db", status=HealthStatus.HEALTHY)]
        components_degraded = [ComponentHealth(name="db", status=HealthStatus.DEGRADED)]

        start_time = time.time()

        healthy_response = HealthCheckResponse.create(components_healthy, "1.0.0", start_time)
        degraded_response = HealthCheckResponse.create(components_degraded, "1.0.0", start_time)

        assert healthy_response.is_healthy()
        assert not degraded_response.is_healthy()

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


class TestHealthCheckIntegration:
    """Integration tests for health check scenarios."""

    def test_kubernetes_liveness_scenario(self) -> None:
        """Should support Kubernetes liveness probe pattern."""
        # Simulate liveness check - only care about UNHEALTHY
        components = [
            ComponentHealth(name="db", status=HealthStatus.DEGRADED),  # Degraded OK for liveness
        ]

        start_time = time.time()
        response = HealthCheckResponse.create(components, "1.0.0", start_time)

        # Degraded service should still pass liveness (only unhealthy fails)
        assert response.status != HealthStatus.UNHEALTHY

    def test_kubernetes_readiness_scenario(self) -> None:
        """Should support Kubernetes readiness probe pattern."""
        # Simulate readiness check - DEGRADED or UNHEALTHY fails
        components_ready = [ComponentHealth(name="db", status=HealthStatus.HEALTHY)]
        components_not_ready = [ComponentHealth(name="db", status=HealthStatus.DEGRADED)]

        start_time = time.time()

        ready_response = HealthCheckResponse.create(components_ready, "1.0.0", start_time)
        not_ready_response = HealthCheckResponse.create(components_not_ready, "1.0.0", start_time)

        # Only HEALTHY should be ready for traffic
        assert ready_response.is_healthy()
        assert not not_ready_response.is_healthy()

    def test_docker_health_check_scenario(self) -> None:
        """Should support Docker health check pattern."""
        # Docker health checks are binary: healthy or unhealthy
        components = [
            ComponentHealth(name="api", status=HealthStatus.HEALTHY),
            ComponentHealth(name="db", status=HealthStatus.DEGRADED),
        ]

        start_time = time.time()
        response = HealthCheckResponse.create(components, "1.0.0", start_time)

        # For Docker, consider DEGRADED as still "working" (exit 0)
        # Only UNHEALTHY should fail (exit 1)
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

        # Single unhealthy component makes entire system unhealthy
        assert response.status == HealthStatus.UNHEALTHY
        assert len([c for c in response.components if c.status == HealthStatus.UNHEALTHY]) == 1
        assert len([c for c in response.components if c.status == HealthStatus.DEGRADED]) == 1
        assert len([c for c in response.components if c.status == HealthStatus.HEALTHY]) == 2
