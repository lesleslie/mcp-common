"""MCP Common - Oneiric-Native Foundation Library for MCP Servers.

This package provides battle-tested patterns extracted from production MCP servers,
including configuration management, Rich UI components, and CLI lifecycle management.

Oneiric Design Patterns:
    - YAML + environment variable configuration
    - Rich console UI for beautiful terminal output
    - Type-safe settings with Pydantic validation
    - CLI factory for standardized server lifecycle
    - Usage profiles for different server modes

Usage:
    >>> from mcp_common.ui import ServerPanels
    >>> from mcp_common.config import MCPBaseSettings
    >>> from mcp_common.cli import MCPServerCLIFactory
    >>> from mcp_common.profiles import MinimalServer, StandardServer, FullServer
    >>>
    >>> # Display startup panel
    >>> ServerPanels.startup_success(
    ...     server_name="My Server",
    ...     features=["Feature 1", "Feature 2"]
    ... )
    >>>
    >>> # Load configuration
    >>> settings = MCPBaseSettings.load("my-server")
    >>>
    >>> # Or use a pre-configured profile
    >>> server = StandardServer(name="my-server")
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from oneiric.adapters.http import HTTPClientAdapter, HTTPClientSettings

from mcp_common.baseline_tools import (
    BASELINE_TOOL_NAMES,
    LivenessContext,
    get_liveness_context,
    register_baseline_tools,
    seed_liveness_context,
)
from mcp_common.bootstrap import bootstrap_baseline_tools
from mcp_common.cli import MCPServerCLIFactory, MCPServerSettings, RuntimeHealthSnapshot
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
from mcp_common.interfaces import DualUseTool, ensure_dual_use
from mcp_common.profiles import FullServer, MinimalServer, StandardServer
from mcp_common.schemas import ToolInput, ToolResponse
from mcp_common.tools import MANDATORY_TOOLS, ToolProfile, trim_description
from mcp_common.ui import ServerPanels
from mcp_common.validation import validate_input, validate_output

# Read the version from package metadata so it stays in sync with releases.
# Falls back to a dev sentinel if the package is imported without being
# installed (e.g. running tests directly from a source checkout).
try:
    __version__ = _pkg_version("mcp-common")
except PackageNotFoundError:  # pragma: no cover - dev/source-checkout path
    __version__ = "0.0.0+unknown"

__all__: list[str] = [
    "BASELINE_TOOL_NAMES",
    "MANDATORY_TOOLS",
    "APIKeyFormatError",
    "APIKeyLengthError",
    "APIKeyMissingError",
    "ComponentHealth",
    "CredentialValidationError",
    "DependencyConfig",
    "DependencyMissingError",
    "DependencyWaiter",
    "DualUseTool",
    "FullServer",
    "HTTPClientAdapter",
    "HTTPClientSettings",
    "HealthCheckResponse",
    "HealthCheckResult",
    "HealthChecker",
    "HealthStatus",
    "LivenessContext",
    "MCPBaseSettings",
    "MCPServerCLIFactory",
    "MCPServerError",
    "MCPServerSettings",
    "MinimalServer",
    "RuntimeHealthSnapshot",
    "ServerConfigurationError",
    "ServerInitializationError",
    "ServerPanels",
    "StandardServer",
    "ToolInput",
    "ToolProfile",
    "ToolResponse",
    "ValidationMixin",
    "WaitResult",
    "__version__",
    "ensure_dual_use",
    "get_liveness_context",
    "register_baseline_tools",
    "register_health_tools",
    "seed_liveness_context",
    "trim_description",
    "validate_input",
    "validate_output",
]
