"""MCP Common - ACB-Native Foundation Library for MCP Servers.

This package provides battle-tested patterns extracted from production MCP servers,
including HTTP clients, configuration management, and Rich UI components.

ACB-Native Design:
    - Dependency injection via ACB's `depends` system
    - Structured logging via ACB Logger
    - YAML + environment variable configuration via ACB Settings
    - Lifecycle management via ACB adapters

Usage:
    >>> from acb.depends import depends
    >>> from mcp_common.ui import ServerPanels
"""

from __future__ import annotations

from acb import register_pkg
from acb.monitoring.health import ComponentHealth, HealthCheckResponse, HealthStatus

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
    "APIKeyFormatError",
    "APIKeyLengthError",
    "APIKeyMissingError",
    "ComponentHealth",
    "CredentialValidationError",
    "DependencyMissingError",
    "HealthCheckResponse",
    "HealthStatus",
    "MCPBaseSettings",
    "MCPServerError",
    "ServerConfigurationError",
    "ServerInitializationError",
    "ServerPanels",
    "ValidationMixin",
    "__version__",
]
