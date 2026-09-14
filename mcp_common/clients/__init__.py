"""Common MCP client SDK for Bodai cross-component communication.

This package ships the canonical async MCP client used by Bodai
components to call tools on each other over streamable-HTTP at
``/mcp``. It is the renamed successor of
``akosha.akosha.mcp.client.BodaiComponentMCPClient`` (137 LOC) and is
the SDK documented in Phase 1 of
``docs/plans/2026-09-14-common-mcp-client-transport-unification.md``
(REQ-001).

Public surface:

* :class:`CommonMCPClient` — async MCP client with streamable-HTTP
  transport, SSRF guard, typed 5xx and timeout errors.
* :class:`MCPClientError` — base exception for client runtime errors.
* :class:`MCPClientHTTPError` — raised when the server returns 5xx.
* :class:`MCPClientTimeoutError` — raised when ``httpx.ReadTimeout``
  fires during a call.
"""

from __future__ import annotations

from mcp_common.clients.common_mcp_client import (
    CommonMCPClient,
    MCPClientError,
    MCPClientHTTPError,
    MCPClientTimeoutError,
)

__all__ = [
    "CommonMCPClient",
    "MCPClientError",
    "MCPClientHTTPError",
    "MCPClientTimeoutError",
]
