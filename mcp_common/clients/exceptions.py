"""Typed client-side exceptions for :class:`mcp_common.clients.CommonMCPClient`.

The exception classes (:class:`MCPClientError`, :class:`MCPClientHTTPError`,
:class:`MCPClientTimeoutError`) are defined inline in
:mod:`mcp_common.clients.common_mcp_client` and re-exported here so
callers can import them from a dedicated, stable import path.

A future revision may move the class bodies here directly; for now this
module is a thin aggregation surface that keeps the public exception
hierarchy discoverable via :mod:`mcp_common.clients.exceptions`.

Implements: REQ-001 exception semantics (umbrella
``docs/plans/2026-09-14-common-mcp-client-transport-unification.md``
Phase 1 task 2).
"""

from __future__ import annotations

from mcp_common.clients.common_mcp_client import (
    MCPClientError,
    MCPClientHTTPError,
    MCPClientTimeoutError,
)

__all__ = [
    "MCPClientError",
    "MCPClientHTTPError",
    "MCPClientTimeoutError",
]
