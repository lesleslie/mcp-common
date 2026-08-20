"""Assert that an MCP server exposes the Bodai baseline tool surface.

Phase 3 of ``docs/plans/2026-08-20-bodai-mcp-surface-standardization.md``
uses this helper to regression-test that every Bodai core MCP server
exposes the 4 canonical baseline tools::

    - discover_tools
    - get_liveness
    - get_readiness
    - health_check_all

``assert_baseline_surface(server_url)`` opens a streamable-HTTP MCP
connection to ``server_url``, calls ``tools/list``, asserts every
expected tool name is present, and returns the loaded tool name list.

Implementation note: the FastMCP 3.4+ ``Client`` class is the only
client SDK available in ``mcp_common``'s dep closure that handles the
streamable-HTTP session handshake (initialize -> mcp-session-id ->
tools/list). Hand-rolled ``urllib`` POSTs hit the same
``Bad Request: Missing session ID`` response on every Bodai core
server, so we delegate to ``fastmcp.Client`` here.

Typical usage in a Bodai core repo test suite::

    @pytest.mark.requires_network
    async def test_session_buddy_baseline_surface() -> None:
        tools = await assert_baseline_surface("http://localhost:8678/mcp")
        assert "ping" in set(tools)  # deprecated alias still present
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import Client

from mcp_common.baseline_tools import BASELINE_TOOL_NAMES

logger = logging.getLogger(__name__)

__all__ = ["BaselineSurfaceError", "assert_baseline_surface"]


class BaselineSurfaceError(AssertionError):
    """Raised when an MCP server fails the baseline surface check.

    Subclasses ``AssertionError`` so plain ``assert`` consumers can
    still surface the failure, but also exposes ``missing`` as a
    ``frozenset[str]`` so callers can render precise failure context.
    """

    def __init__(self, message: str, missing: frozenset[str]) -> None:
        super().__init__(message)
        self.missing = missing


async def assert_baseline_surface(
    server_url: str,
    expected_tool_names: frozenset[str] | None = None,
    *,
    timeout: float = 5.0,
) -> list[str]:
    """Assert that ``server_url`` exposes the Bodai baseline tools.

    Opens a FastMCP streamable-HTTP connection to ``server_url``,
    calls ``tools/list``, and asserts that every name in
    ``expected_tool_names`` is present in the loaded tool list. Returns
    the full loaded tool name list so the caller can perform additional
    assertions (e.g. asserting a deprecated alias is still present).

    Args:
        server_url: The MCP server endpoint, e.g.
            ``"http://localhost:8678/mcp"``.
        expected_tool_names: Override for the expected tool set.
            Defaults to ``BASELINE_TOOL_NAMES`` from
            ``mcp_common.baseline_tools``.
        timeout: HTTP request timeout in seconds. Defaults to ``5.0``.

    Returns:
        The full list of tool names reported by the server's
        ``tools/list`` call, in the order the server returned them.

    Raises:
        BaselineSurfaceError: At least one expected tool name is
            missing from the server's response. The exception message
            lists both the missing tools and the observed tools.
        Exception: Any connection / handshake error raised by the
            FastMCP client (e.g. ``ConnectionError``,
            ``httpx.ConnectError``). These propagate unchanged so
            ``pytest.mark.requires_network`` can naturally skip offline
            environments via ``pytest.skip(allow_module_level=...)`` or
            a fixture-level reachability probe.
    """
    if expected_tool_names is None:
        expected_tool_names = BASELINE_TOOL_NAMES

    client = Client(server_url, timeout=timeout)
    async with client:
        tools = await client.list_tools()

    tool_names: list[str] = [tool.name for tool in tools]
    missing = expected_tool_names - set(tool_names)

    if missing:
        logger.error(
            "baseline_surface: server=%s missing=%s observed=%s",
            server_url,
            sorted(missing),
            sorted(tool_names),
        )
        raise BaselineSurfaceError(
            f"{server_url} missing baseline tools {sorted(missing)}; "
            f"observed {sorted(tool_names)}",
            missing=frozenset(missing),
        )

    return tool_names


# Retained so callers can introspect the expected set directly without
# importing ``mcp_common.baseline_tools``. Not part of ``__all__`` to
# keep the public surface narrow - consumers that need the canonical
# set should import from ``mcp_common.baseline_tools``.
DEFAULT_EXPECTED_TOOL_NAMES: Any = BASELINE_TOOL_NAMES
