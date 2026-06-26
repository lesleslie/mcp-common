"""Centralized FastMCP re-export surface for Bodai ecosystem consumers.

Plan 7 (FastMCP 3.x ecosystem upgrade) pins every repo to FastMCP 3.4.0 or
newer. To keep consumer imports stable across FastMCP patch and minor
releases, mcp-common re-exports the FastMCP symbols we rely on from one
module. Consumers should write::

    from mcp_common.fastmcp import FastMCP, Context, Middleware

instead of the upstream import path. If a future FastMCP release relocates
any of these symbols, we adjust the re-export here and downstream callers
do not need to change.

What is re-exported:

- ``FastMCP`` — the server class
- ``Context`` — the per-request context object
- ``Middleware`` — the base class for FastMCP middleware
- ``MiddlewareContext`` — the unified middleware context dataclass
- ``OneiricMCPConfig`` — the Oneiric-native MCP settings class that
  supersedes ``mcp_common.config.MCPBaseSettings``
- ``RateLimitingMiddleware`` — the built-in rate-limiting middleware from
  ``fastmcp.server.middleware.rate_limiting``
"""

from __future__ import annotations

from fastmcp import Context, FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from oneiric.core.config import OneiricMCPConfig

__all__ = [
    "Context",
    "FastMCP",
    "Middleware",
    "MiddlewareContext",
    "OneiricMCPConfig",
    "RateLimitingMiddleware",
]
