"""Shared contract facade for MCP common primitives.

This module groups the canonical shared primitives that Bodai consumer repos
should import when they need common auth, health, telemetry, or WebSocket
building blocks.
"""

from __future__ import annotations

from mcp_common.auth.core import TokenPayload, create_service_token, verify_token
from mcp_common.health import (
    ComponentHealth,
    DependencyConfig,
    DependencyWaiter,
    HealthChecker,
    HealthCheckResponse,
    HealthCheckResult,
    HealthStatus,
    WaitResult,
    register_health_tools,
)
from mcp_common.server.telemetry import FastMCPOpenTelemetryMiddleware
from mcp_common.websocket.protocol import (
    EventTypes,
    MessageType,
    WebSocketMessage,
    WebSocketProtocol,
)
from mcp_common.websocket.server import WebSocketServer

__all__ = [
    "ComponentHealth",
    "DependencyConfig",
    "DependencyWaiter",
    "EventTypes",
    "FastMCPOpenTelemetryMiddleware",
    "HealthCheckResponse",
    "HealthCheckResult",
    "HealthChecker",
    "HealthStatus",
    "MessageType",
    "TokenPayload",
    "WaitResult",
    "WebSocketMessage",
    "WebSocketProtocol",
    "WebSocketServer",
    "create_service_token",
    "register_health_tools",
    "verify_token",
]
