"""Minimal MCP server profile - tools only.

This profile provides the simplest possible MCP server with:
- Basic tool registration
- Simple configuration
- Fast startup
- Minimal dependencies

Use Case: Simple servers with stateless tools

Features:
    - Tools: Yes
    - Resources: No
    - Prompts: No
    - Auth: No
    - Telemetry: No
    - Health checks: Basic

Example:
    >>> from mcp_common.profiles import MinimalServer
    >>>
    >>> server = MinimalServer(name="minimal-server")
    >>>
    >>> @server.tool()
    >>> def hello(name: str) -> str:
    ...     return f"Hello {name}"
    >>>
    >>> server.run()
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mcp_common.config import MCPBaseSettings


class MinimalServerSettings(MCPBaseSettings):
    """Settings for minimal MCP server.

    Configuration loading order (later overrides earlier):
    1. Default values (below)
    2. settings/{server_name}.yaml (committed)
    3. settings/local.yaml (gitignored)
    4. Environment variables: MINIMAL_SERVER_{FIELD}

    Example YAML (settings/minimal-server.yaml):
        server_name: "Minimal MCP Server"
        log_level: INFO
    """

    # Minimal server has no additional settings beyond MCPBaseSettings
    pass


class MinimalServer:
    """Minimal MCP server with tools only.

    This is the simplest server profile, suitable for:
    - Quick prototypes
    - Simple utility servers
    - Stateless tools
    - Development environments

    Features:
        - Fast startup (no auth/telemetry overhead)
        - Simple configuration
        - Tool registration only
        - Basic health checks

    Args:
        name: Server name (used for config loading)
        settings: Optional settings instance (created from name if not provided)

    Example:
        >>> server = MinimalServer(name="my-server")
        >>>
        >>> @server.tool()
        >>> def add(a: int, b: int) -> int:
        ...     return a + b
        >>>
        >>> server.run()
    """

    def __init__(
        self,
        name: str,
        settings: MinimalServerSettings | None = None,
    ) -> None:
        """Initialize minimal server.

        Args:
            name: Server name
            settings: Optional settings (loaded from config if not provided)
        """
        self.name = name
        self.settings = settings or MinimalServerSettings.load(name)
        self._tools: dict[str, Callable] = {}

    def tool(self, name: str | None = None) -> Callable:
        """Decorator to register a tool.

        Args:
            name: Optional tool name (defaults to function name)

        Example:
            >>> @server.tool()
            >>> def my_tool(arg: str) -> str:
            ...     return arg
            >>>
            >>> @server.tool(name="custom-name")
            >>> def my_tool() -> str:
            ...     return "result"
        """

        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            self._tools[tool_name] = func
            return func

        return decorator

    def run(self, **kwargs: Any) -> None:
        """Run the server.

        This method should be overridden by the actual server implementation
        (e.g., FastMCP, native MCP server).

        Args:
            **kwargs: Additional arguments passed to the underlying server

        Example:
            >>> server.run(host="localhost", port=8000)
        """
        raise NotImplementedError(
            "MinimalServer.run() must be implemented by the actual server "
            "implementation (e.g., FastMCP, native MCP)"
        )

    def health_check(self) -> dict[str, Any]:
        """Basic health check.

        Returns:
            Dict with health status

        Example:
            >>> health = server.health_check()
            >>> assert health["status"] == "healthy"
        """
        return {
            "status": "healthy",
            "server": self.name,
            "tools": len(self._tools),
        }

    def list_tools(self) -> list[str]:
        """List registered tools.

        Returns:
            List of tool names

        Example:
            >>> tools = server.list_tools()
            >>> print(f"Available tools: {tools}")
        """
        return list(self._tools.keys())

    def get_tool(self, name: str) -> Callable | None:
        """Get a registered tool by name.

        Args:
            name: Tool name

        Returns:
            Tool function or None if not found

        Example:
            >>> tool = server.get_tool("my-tool")
            >>> if tool:
            ...     result = tool(arg="value")
        """
        return self._tools.get(name)
