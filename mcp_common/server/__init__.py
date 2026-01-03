"""Server integration utilities for MCP servers.

This module provides reusable components for building MCP servers with
Oneiric runtime integration, reducing boilerplate and duplication across
server implementations.

Core Components:
    - BaseOneiricServerMixin: Reusable server lifecycle methods
    - create_runtime_components(): Factory for runtime initialization
    - check_*_available(): Optional dependency detection helpers

Example:
    >>> from mcp_common.server import BaseOneiricServerMixin, create_runtime_components
    >>>
    >>> class MyMCPServer(BaseOneiricServerMixin):
    ...     def __init__(self, config):
    ...         self.config = config
    ...         self.runtime = create_runtime_components("my-server", ".oneiric_cache")
    >>>
    >>>     async def startup(self):
    ...         await self.runtime.initialize()
    ...         await self._create_startup_snapshot()
"""

from mcp_common.server.availability import (
    check_rate_limiting_available,
    check_security_available,
    check_serverpanels_available,
    get_availability_status,
)
from mcp_common.server.base import BaseOneiricServerMixin
from mcp_common.server.runtime import (
    RuntimeComponents,
    create_runtime_components,
)

__all__ = [
    "BaseOneiricServerMixin",
    "RuntimeComponents",
    "check_rate_limiting_available",
    "check_security_available",
    "check_serverpanels_available",
    "create_runtime_components",
    "get_availability_status",
]

__version__ = "0.4.0"
