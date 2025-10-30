"""MCP Common - ACB-Native Foundation Library for MCP Servers.

This package provides battle-tested patterns extracted from production MCP servers,
including HTTP clients, rate limiting, configuration management, and Rich UI components.

ACB-Native Design:
    - Dependency injection via ACB's `depends` system
    - Structured logging via ACB Logger
    - YAML + environment variable configuration via ACB Settings
    - Lifecycle management via ACB adapters

Usage:
    >>> from acb.depends import depends
    >>> from mcp_common.adapters.http import HTTPClientAdapter
    >>>
    >>> # Get HTTP client adapter from DI container
    >>> http = depends(HTTPClientAdapter)
    >>> client = await http._create_client()
"""

from __future__ import annotations

from acb import register_pkg

from mcp_common.adapters import HTTPClientAdapter, HTTPClientSettings
from mcp_common.config import MCPBaseSettings, ValidationMixin
from mcp_common.exceptions import (
    APIKeyFormatError,
    APIKeyLengthError,
    APIKeyMissingError,
    CredentialValidationError,
    DependencyMissingError,
    MCPServerError,
    ServerConfigurationError,
    ServerInitializationError,
)
from mcp_common.health import ComponentHealth, HealthCheckResponse, HealthStatus
from mcp_common.http_health import check_http_client_health, check_http_connectivity
from mcp_common.ui import ServerPanels

# Register mcp-common package with ACB
# This enables:
# - Dependency injection for all components
# - Automatic lifecycle management
# - Structured logging with context
# - Settings resolution via ACB config system
register_pkg("mcp_common")

__version__ = "2.0.0"  # ACB-native v2.0.0

__all__: list[str] = [
    "HTTPClientAdapter",
    "HTTPClientSettings",
    "MCPBaseSettings",
    "ValidationMixin",
    "ServerPanels",
    # Health checks (Phase 10.1: Production Hardening)
    "HealthStatus",
    "ComponentHealth",
    "HealthCheckResponse",
    "check_http_client_health",
    "check_http_connectivity",
    # Exceptions (Phase 3.3 M3: Custom exception hierarchy)
    "MCPServerError",
    "ServerConfigurationError",
    "ServerInitializationError",
    "DependencyMissingError",
    "CredentialValidationError",
    # Specific validation exceptions (Phase 3.3 M4)
    "APIKeyMissingError",
    "APIKeyFormatError",
    "APIKeyLengthError",
    "__version__",
]
