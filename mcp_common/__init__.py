"""MCP Common - Oneiric-Native Foundation Library for MCP Servers.

This package provides battle-tested patterns extracted from production MCP servers,
including configuration management, Rich UI components, and CLI lifecycle management.

Oneiric Design Patterns:
    - YAML + environment variable configuration
    - Rich console UI for beautiful terminal output
    - Type-safe settings with Pydantic validation
    - CLI factory for standardized server lifecycle

Usage:
    >>> from mcp_common.ui import ServerPanels
    >>> from mcp_common.config import MCPBaseSettings
    >>> from mcp_common.cli import MCPServerCLIFactory
    >>>
    >>> # Display startup panel
    >>> ServerPanels.startup_success(
    ...     server_name="My Server",
    ...     features=["Feature 1", "Feature 2"]
    ... )
    >>>
    >>> # Load configuration
    >>> settings = MCPBaseSettings.load("my-server")
"""

from __future__ import annotations

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
from mcp_common.schemas import ToolInput, ToolResponse
from mcp_common.ui import ServerPanels
from mcp_common.validation import validate_input, validate_output

__version__ = "0.4.4"  # Server module + enhanced CLI factory

__all__: list[str] = [
    "APIKeyFormatError",
    "APIKeyLengthError",
    "APIKeyMissingError",
    "CredentialValidationError",
    "DependencyMissingError",
    "DualUseTool",
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
    "__version__",
    "ensure_dual_use",
    "validate_input",
    "validate_output",
]
