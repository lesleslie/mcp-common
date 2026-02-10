"""Usage profiles for MCP servers.

This module provides pre-configured server profiles for different use cases:

- **MinimalServer**: Basic tools only (simplest, fastest)
- **StandardServer**: Tools + resources (most common)
- **FullServer**: All features including auth, telemetry (production-ready)

Usage:
    >>> from mcp_common.profiles import MinimalServer, StandardServer, FullServer
    >>>
    >>> # Minimal server
    >>> server = MinimalServer(name="minimal-server")
    >>>
    >>> # Standard server
    >>> server = StandardServer(name="standard-server")
    >>>
    >>> # Full server with auth and telemetry
    >>> server = FullServer(
    ...     name="full-server",
    ...     auth=JWTAuth(secret="secret"),
    ...     telemetry=OpenTelemetry(endpoint="http://jaeger:4317")
    ... )
"""

from __future__ import annotations

from mcp_common.profiles.full import FullServer
from mcp_common.profiles.minimal import MinimalServer
from mcp_common.profiles.standard import StandardServer

__all__ = [
    "MinimalServer",
    "StandardServer",
    "FullServer",
]
