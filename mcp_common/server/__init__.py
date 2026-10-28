"""Server integration utilities for MCP servers.

This module provides reusable components for building MCP servers with
Oneiric runtime integration, reducing boilerplate and duplication across
server implementations.

Core Components:
    - BaseOneiricServerMixin: Reusable server lifecycle methods
    - create_runtime_components(): Factory for runtime initialization
    - check_*_available(): Optional dependency detection helpers

Example:
    >>> from mcp_common.server import BaseOneiricServerMixin, create_runtime_components
    >>>
    >>> class MyMCPServer(BaseOneiricServerMixin):
    ...     def __init__(self, config):
    ...         self.config = config
    ...         self.runtime = create_runtime_components("my-server", ".oneiric_cache")
    >>>
    >>>     async def startup(self):
    ...         await self.runtime.initialize()
    ...         await self._create_startup_snapshot()
"""

from mcp_common.server.availability import (
    check_rate_limiting_available,
    check_security_available,
    check_serverpanels_available,
    get_availability_status,
)
from mcp_common.server.base import BaseOneiricServerMixin
from mcp_common.server.launcher import launch
from mcp_common.server.producer_telemetry import (
    LIVENESS_SPAN_NAME,
    configure_producer_tracing,
    producer_telemetry_enabled,
    run_liveness_emitter,
)
from mcp_common.server.runtime import (
    RuntimeComponents,
    create_runtime_components,
)
from mcp_common.server.telemetry import FastMCPOpenTelemetryMiddleware

__all__ = [
    "LIVENESS_SPAN_NAME",
    "BaseOneiricServerMixin",
    "FastMCPOpenTelemetryMiddleware",
    "RuntimeComponents",
    "check_rate_limiting_available",
    "check_security_available",
    "check_serverpanels_available",
    "configure_producer_tracing",
    "create_runtime_components",
    "get_availability_status",
    "launch",
    "producer_telemetry_enabled",
    "run_liveness_emitter",
]

__version__ = "0.4.0"
