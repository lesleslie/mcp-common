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

from oneiric.adapters.http import HTTPClientAdapter, HTTPClientSettings

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
from mcp_common.interfaces import DualUseTool, ensure_dual_use
from mcp_common.profiles import FullServer, MinimalServer, StandardServer
from mcp_common.schemas import ToolInput, ToolResponse
from mcp_common.ui import ServerPanels
from mcp_common.validation import validate_input, validate_output

__version__ = "0.5.0"  # Usage profiles

__all__: list[str] = [
    "APIKeyFormatError",
    "APIKeyLengthError",
    "APIKeyMissingError",
    "CredentialValidationError",
    "DependencyMissingError",
    "DualUseTool",
    "HTTPClientAdapter",
    "HTTPClientSettings",
    "MCPBaseSettings",
    "MCPServerCLIFactory",
    "MCPServerError",
    "MCPServerSettings",
    "RuntimeHealthSnapshot",
    "ServerConfigurationError",
    "ServerInitializationError",
    "ServerPanels",
    "ToolInput",
    "ToolResponse",
    "ValidationMixin",
    "FullServer",
    "MinimalServer",
    "StandardServer",
    "__version__",
    "ensure_dual_use",
    "validate_input",
    "validate_output",
]
