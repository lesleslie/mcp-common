"""Oneiric-native CLI factory for MCP servers.

This package provides a production-ready CLI factory for building standardized
MCP server command-line interfaces with lifecycle management, health monitoring,
and graceful shutdown.

Key Components:
    - MCPServerCLIFactory: Main factory for creating Typer CLIs
    - MCPServerSettings: Pydantic settings with YAML + environment loading
    - RuntimeHealthSnapshot: Health snapshot dataclass matching Oneiric schema
    - SignalHandler: Graceful shutdown signal handling

Example:
    >>> from mcp_common.cli import MCPServerCLIFactory
    >>>
    >>> factory = MCPServerCLIFactory("my-server")
    >>> app = factory.create_app()
    >>>
    >>> @app.command()
    >>> def custom():
    ...     print("Custom command")
    >>>
    >>> if __name__ == "__main__":
    ...     app()
"""

from mcp_common.cli.factory import MCPServerCLIFactory
from mcp_common.cli.health import RuntimeHealthSnapshot, load_runtime_health, write_runtime_health
from mcp_common.cli.settings import MCPServerSettings
from mcp_common.cli.signals import SignalHandler

__all__ = [
    "MCPServerCLIFactory",
    "MCPServerSettings",
    "RuntimeHealthSnapshot",
    "SignalHandler",
    "load_runtime_health",
    "write_runtime_health",
]
