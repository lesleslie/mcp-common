"""Standard MCP server profile - tools + resources.

This profile provides a balanced feature set with:
- Tool registration
- Resource management
- Standard configuration
- Rich UI support

Use Case: Most MCP servers (the recommended default)

Features:
    - Tools: Yes
    - Resources: Yes
    - Prompts: No
    - Auth: No
    - Telemetry: No
    - Health checks: Enhanced

Example:
    >>> from mcp_common.profiles import StandardServer
    >>>
    >>> server = StandardServer(
    ...     name="standard-server",
    ...     description="Standard MCP server"
    ... )
    >>>
    >>> @server.tool()
    >>> def search(query: str) -> dict:
    ...     return {"results": []}
    >>>
    >>> @server.resource("config://{name}")
    >>> def get_config(name: str) -> dict:
    ...     return load_config(name)
    >>>
    >>> server.run()
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import Field

from mcp_common.config import MCPBaseSettings


class StandardServerSettings(MCPBaseSettings):
    """Settings for standard MCP server.

    Configuration loading order (later overrides earlier):
    1. Default values (below)
    2. settings/{server_name}.yaml (committed)
    3. settings/local.yaml (gitignored)
    4. Environment variables: STANDARD_SERVER_{FIELD}

    Example YAML (settings/standard-server.yaml):
        server_name: "Standard MCP Server"
        description: "My standard server"
        log_level: INFO
        enable_http_transport: true
        http_port: 8000
    """

    description: str = Field(
        default="Standard MCP Server", description="Server description"
    )
    enable_resources: bool = Field(default=True, description="Enable resource support")


class StandardServer:
    """Standard MCP server with tools and resources.

    This is the recommended profile for most MCP servers, suitable for:
    - Production servers
    - Servers with dynamic resources
    - Servers needing configuration management
    - Data access servers

    Features:
        - Tool registration
        - Resource management
        - Enhanced health checks
        - Rich UI support
        - HTTP transport support

    Args:
        name: Server name (used for config loading)
        description: Server description
        settings: Optional settings instance (created from name if not provided)

    Example:
        >>> server = StandardServer(
        ...     name="my-server",
        ...     description="My data server"
        ... )
        >>>
        >>> @server.tool()
        >>> def query_data(sql: str) -> list[dict]:
        ...     return execute_query(sql)
        >>>
        >>> @server.resource("data://{table}")
        >>> def get_table_data(table: str) -> str:
        ...     return json.dumps(fetch_table(table))
        >>>
        >>> server.run()
    """

    def __init__(
        self,
        name: str,
        description: str = "Standard MCP Server",
        settings: StandardServerSettings | None = None,
    ) -> None:
        """Initialize standard server.

        Args:
            name: Server name
            description: Server description
            settings: Optional settings (loaded from config if not provided)
        """
        self.name = name
        self.description = description
        self.settings = settings or StandardServerSettings.load(name)
        self._tools: dict[str, Callable] = {}
        self._resources: dict[str, Callable] = {}

    def tool(self, name: str | None = None) -> Callable:
        """Decorator to register a tool.

        Args:
            name: Optional tool name (defaults to function name)

        Example:
            >>> @server.tool()
            >>> def search(query: str) -> dict:
            ...     return {"results": []}
        """

        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            self._tools[tool_name] = func
            return func

        return decorator

    def resource(self, uri_pattern: str) -> Callable:
        """Decorator to register a resource handler.

        Args:
            uri_pattern: URI pattern (e.g., "config://{name}", "data://{table}")

        Example:
            >>> @server.resource("config://{name}")
            >>> def get_config(name: str) -> dict:
            ...     return load_config(name)
            >>>
            >>> @server.resource("data://{table}")
            >>> def get_table_data(table: str) -> str:
            ...     return json.dumps(fetch_table(table))
        """

        def decorator(func: Callable) -> Callable:
            self._resources[uri_pattern] = func
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
            "StandardServer.run() must be implemented by the actual server "
            "implementation (e.g., FastMCP, native MCP)"
        )

    def health_check(self) -> dict[str, Any]:
        """Enhanced health check.

        Returns:
            Dict with health status including tools and resources

        Example:
            >>> health = server.health_check()
            >>> assert health["status"] == "healthy"
            >>> assert health["tools"] > 0
        """
        return {
            "status": "healthy",
            "server": self.name,
            "description": self.description,
            "tools": len(self._tools),
            "resources": len(self._resources),
        }

    def list_tools(self) -> list[str]:
        """List registered tools.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def list_resources(self) -> list[str]:
        """List resource URI patterns.

        Returns:
            List of URI patterns
        """
        return list(self._resources.keys())

    def get_tool(self, name: str) -> Callable | None:
        """Get a registered tool by name."""
        return self._tools.get(name)

    def get_resource(self, uri_pattern: str) -> Callable | None:
        """Get a resource handler by URI pattern."""
        return self._resources.get(uri_pattern)
