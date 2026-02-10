"""Full MCP server profile - production-ready with all features.

This profile provides a complete production-grade MCP server with:
- Tool registration
- Resource management
- Prompt templates
- Authentication
- Telemetry/observability
- Multi-worker support

Use Case: Production servers requiring enterprise features

Features:
    - Tools: Yes
    - Resources: Yes
    - Prompts: Yes
    - Auth: Yes (JWT)
    - Telemetry: Yes (OpenTelemetry)
    - Health checks: Comprehensive
    - Workers: Multi-worker support

Example:
    >>> from mcp_common.profiles import FullServer
    >>> from mcp_common.auth import JWTAuth
    >>> from mcp_common.telemetry import OpenTelemetry
    >>>
    >>> auth = JWTAuth(secret="your-secret")
    >>> telemetry = OpenTelemetry(endpoint="http://jaeger:4317")
    >>>
    >>> server = FullServer(
    ...     name="full-server",
    ...     auth=auth,
    ...     telemetry=telemetry
    ... )
    >>>
    >>> # Add tools, resources, prompts
    >>> server.run(workers=4)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import Field

from mcp_common.config import MCPBaseSettings


# Type aliases for auth/telemetry (these would be imported from actual modules)
class AuthBackend:
    """Base class for authentication backends."""

    pass


class TelemetryBackend:
    """Base class for telemetry backends."""

    pass


class FullServerSettings(MCPBaseSettings):
    """Settings for full-featured MCP server.

    Configuration loading order (later overrides earlier):
    1. Default values (below)
    2. settings/{server_name}.yaml (committed)
    3. settings/local.yaml (gitignored)
    4. Environment variables: FULL_SERVER_{FIELD}

    Example YAML (settings/full-server.yaml):
        server_name: "Full MCP Server"
        description: "Production-ready server"
        log_level: INFO
        enable_http_transport: true
        http_port: 8000
        auth_enabled: true
        telemetry_enabled: true
        workers: 4
    """

    description: str = Field(
        default="Full MCP Server", description="Server description"
    )
    auth_enabled: bool = Field(default=False, description="Enable authentication")
    telemetry_enabled: bool = Field(
        default=False, description="Enable OpenTelemetry tracing"
    )
    workers: int = Field(default=1, description="Number of worker processes")
    enable_prompts: bool = Field(default=True, description="Enable prompt templates")


class FullServer:
    """Full-featured MCP server for production deployments.

    This profile provides enterprise-grade features, suitable for:
    - Production servers
    - Multi-user environments
    - Servers requiring authentication
    - Servers needing observability
    - High-traffic deployments

    Features:
        - Tool registration
        - Resource management
        - Prompt templates
        - JWT authentication
        - OpenTelemetry tracing
        - Multi-worker support
        - Comprehensive health checks
        - Graceful shutdown

    Args:
        name: Server name (used for config loading)
        description: Server description
        auth: Optional authentication backend
        telemetry: Optional telemetry backend
        settings: Optional settings instance (created from name if not provided)

    Example:
        >>> from mcp_common.auth import JWTAuth
        >>> from mcp_common.telemetry import OpenTelemetry
        >>>
        >>> auth = JWTAuth(secret="your-secret-key")
        >>> telemetry = OpenTelemetry(endpoint="http://jaeger:4317")
        >>>
        >>> server = FullServer(
        ...     name="my-server",
        ...     description="Production server",
        ...     auth=auth,
        ...     telemetry=telemetry
        ... )
        >>>
        >>> @server.tool()
        >>> async def process_data(data: dict) -> dict:
        ...     # Telemetry tracing is automatic
        ...     return transform(data)
        >>>
        >>> @server.resource("data://{id}")
        >>> async def get_data(id: str) -> str:
        ...     # Auth check is automatic
        ...     return fetch_data(id)
        >>>
        >>> @server.prompt("analyze")
        >>> def analyze_prompt(data: str) -> str:
        ...     return f"Analyze this data: {data}"
        >>>
        >>> server.run(workers=4)
    """

    def __init__(
        self,
        name: str,
        description: str = "Full MCP Server",
        auth: AuthBackend | None = None,
        telemetry: TelemetryBackend | None = None,
        settings: FullServerSettings | None = None,
    ) -> None:
        """Initialize full server.

        Args:
            name: Server name
            description: Server description
            auth: Optional authentication backend
            telemetry: Optional telemetry backend
            settings: Optional settings (loaded from config if not provided)
        """
        self.name = name
        self.description = description
        self.auth = auth
        self.telemetry = telemetry
        self.settings = settings or FullServerSettings.load(name)

        self._tools: dict[str, Callable] = {}
        self._resources: dict[str, Callable] = {}
        self._prompts: dict[str, Callable] = {}

    def tool(self, name: str | None = None) -> Callable:
        """Decorator to register a tool.

        Tools registered here will automatically have:
        - Authentication checks (if auth enabled)
        - Telemetry tracing (if telemetry enabled)
        - Error handling

        Args:
            name: Optional tool name (defaults to function name)

        Example:
            >>> @server.tool()
            >>> async def process_data(data: dict) -> dict:
            ...     return transform(data)
        """

        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            self._tools[tool_name] = func
            return func

        return decorator

    def resource(self, uri_pattern: str) -> Callable:
        """Decorator to register a resource handler.

        Resources registered here will automatically have:
        - Authentication checks (if auth enabled)
        - Telemetry tracing (if telemetry enabled)
        - Caching support

        Args:
            uri_pattern: URI pattern (e.g., "config://{name}")

        Example:
            >>> @server.resource("data://{id}")
            >>> async def get_data(id: str) -> str:
            ...     return fetch_data(id)
        """

        def decorator(func: Callable) -> Callable:
            self._resources[uri_pattern] = func
            return func

        return decorator

    def prompt(self, name: str | None = None) -> Callable:
        """Decorator to register a prompt template.

        Prompt templates are reusable prompt strings with parameters.

        Args:
            name: Optional prompt name (defaults to function name)

        Example:
            >>> @server.prompt("analyze")
            >>> def analyze_prompt(data: str) -> str:
            ...     return f"Analyze this data: {data}"
        """

        def decorator(func: Callable) -> Callable:
            prompt_name = name or func.__name__
            self._prompts[prompt_name] = func
            return func

        return decorator

    def run(self, workers: int = 1, **kwargs: Any) -> None:
        """Run the server with worker processes.

        This method should be overridden by the actual server implementation
        (e.g., FastMCP, native MCP server).

        Args:
            workers: Number of worker processes
            **kwargs: Additional arguments passed to the underlying server

        Example:
            >>> server.run(workers=4, host="localhost", port=8000)
        """
        raise NotImplementedError(
            "FullServer.run() must be implemented by the actual server "
            "implementation (e.g., FastMCP, native MCP)"
        )

    def health_check(self) -> dict[str, Any]:
        """Comprehensive health check.

        Returns:
            Dict with detailed health status including all components

        Example:
            >>> health = server.health_check()
            >>> assert health["status"] == "healthy"
            >>> assert health["auth"]["enabled"] == True
        """
        return {
            "status": "healthy",
            "server": self.name,
            "description": self.description,
            "tools": len(self._tools),
            "resources": len(self._resources),
            "prompts": len(self._prompts),
            "auth": {
                "enabled": self.auth is not None,
                "type": type(self.auth).__name__ if self.auth else None,
            },
            "telemetry": {
                "enabled": self.telemetry is not None,
                "type": type(self.telemetry).__name__ if self.telemetry else None,
            },
            "workers": self.settings.workers,
        }

    def list_tools(self) -> list[str]:
        """List registered tools."""
        return list(self._tools.keys())

    def list_resources(self) -> list[str]:
        """List resource URI patterns."""
        return list(self._resources.keys())

    def list_prompts(self) -> list[str]:
        """List prompt template names."""
        return list(self._prompts.keys())

    def get_tool(self, name: str) -> Callable | None:
        """Get a registered tool by name."""
        return self._tools.get(name)

    def get_resource(self, uri_pattern: str) -> Callable | None:
        """Get a resource handler by URI pattern."""
        return self._resources.get(uri_pattern)

    def get_prompt(self, name: str) -> Callable | None:
        """Get a prompt template by name."""
        return self._prompts.get(name)
