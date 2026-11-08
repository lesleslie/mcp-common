"""Canonical baseline MCP tools for Bodai core servers.

Phase 1 of the Bodai MCP surface standardization plan (see
``docs/plans/2026-08-20-bodai-mcp-surface-standardization.md``)
establishes the 4-tool baseline that every Bodai core MCP server
exposes::

    - discover_tools(query | None) -> dict
    - get_liveness() -> {status, service, version, uptime}
    - get_readiness() -> dict
    - health_check_all() -> dict

Phase 2 of the MCP tool-disambiguation plan (see
``mahavishnu/docs/plans/2026-11-07-mcp-tool-disambiguation.md``)
collapses the overlap between this module and
:func:`mcp_common.health.register_health_tools`: both registered
``get_liveness``, ``get_readiness`` and ``health_check_all``, so any
server mounting both double-registered those three names (the health
copy silently shadowed the baseline copy on every boot).

:func:`mcp_common.health.register_health_tools` now owns the health
trio - it is the more comprehensive implementation (it also ships
``health_check_service``, ``wait_for_dependency`` and
``wait_for_all_dependencies``). This module registers
``discover_tools`` only, which is the piece that carries the per-tool
``group`` metadata the profile dispatch needs.

The 4-tool *surface* every Bodai core server exposes is unchanged:
``discover_tools`` comes from this module and the health trio comes
from :func:`mcp_common.health.register_health_tools`.
:func:`mcp_common.testing.assert_baseline_surface` still asserts all
four names against a live server.

Usage (typical)::

    from fastmcp import FastMCP
    from mcp_common.baseline_tools import register_baseline_tools

    server = FastMCP(name="my-server", version="1.0.0")
    register_baseline_tools(server)

A server that also wants the health probes mounts them explicitly::

    from mcp_common.health import register_health_tools

    register_health_tools(server, server_name="my-server", version="1.0.0")

The liveness state API (``LivenessContext``, ``get_liveness_context``,
``seed_liveness_context``) is re-exported here for import-path
compatibility, but its implementation and the state itself live in
:mod:`mcp_common.health` - the module that owns the health tools.

The ``ping`` tool is intentionally NOT registered here - that alias is
server-specific (see Phase 2 of the standardization plan: only
Session-Buddy needs the alias for its 3 confirmed callers).
"""

from __future__ import annotations

import logging
import typing as t

from fastmcp import FastMCP
from fastmcp.tools import Tool

from mcp_common.health import (
    LivenessContext,
    get_liveness_context,
    seed_liveness_context,
)

logger = logging.getLogger(__name__)


# Canonical 4-tool baseline SURFACE that every Bodai core MCP server
# exposes. Membership in this set is what
# `mcp_common.testing.assert_baseline_surface` (Phase 3) checks
# against a live server.
#
# The set is the union of two owners, NOT the set of tools this module
# registers:
#
#   - discover_tools            -> mcp_common.baseline_tools
#   - get_liveness              -> mcp_common.health
#   - get_readiness             -> mcp_common.health
#   - health_check_all          -> mcp_common.health
#
# Do not rename a member without updating every Bodai core server that
# calls `register_baseline_tools`.
BASELINE_TOOL_NAMES: frozenset[str] = frozenset(
    {"discover_tools", "get_liveness", "get_readiness", "health_check_all"}
)

# The tools `register_baseline_tools` actually registers on a server.
# The health trio is deliberately absent - `mcp_common.health` owns it.
BASELINE_REGISTERED_TOOL_NAMES: frozenset[str] = frozenset({"discover_tools"})


# ---------------------------------------------------------------------------
# Internal helpers - exposed for unit tests, NOT for direct tool registration.
# ---------------------------------------------------------------------------


async def _baseline_discover_tools(
    server: FastMCP,
    query: str | None = None,
    capability: str | None = None,
    known_tool_names: set[str] | None = None,
) -> dict[str, t.Any]:
    """Canonical ``discover_tools`` implementation.

    Mirrors mahavishnu's envelope shape so cross-server regression
    tests assert against one reference shape. ``known_tool_names`` is
    the set of tool names this server has registered at *some* point
    (typically via the FastMCP tool-version registry); defaults to
    "all currently registered tools" which is the leaner shape
    Session-Buddy and Oneiric use.

    Args:
        server: The FastMCP server instance to introspect.
        query: Optional substring filter applied to tool names.
        capability: Optional capability gate. When ``"ready"``,
            include the routable-worker snapshot from
            ``mcp_common.health.DependencyConfig`` if available. Most
            Bodai core servers ignore this for now.
        known_tool_names: Optional pre-known set. If ``None``, we use
            the currently registered tools as the "known" universe -
            this keeps lean servers (Oneiric) honest without forcing
            them to maintain a static registry.

    Returns:
        Canonical envelope dict.
    """
    try:
        registered_names = {t.name for t in await server.list_tools()}
    except RuntimeError, AttributeError, ValueError, TypeError:
        logger.exception("discover_tools: server.list_tools failed")
        registered_names = set()

    all_known = set(known_tool_names) if known_tool_names else registered_names.copy()

    if query:
        q = query.lower()
        all_known = {n for n in all_known if q in n.lower()}
        registered_names = {n for n in registered_names if q in n.lower()}

    not_loaded = sorted(all_known - registered_names)
    loaded = sorted(registered_names & all_known)

    response: dict[str, t.Any] = {
        "status": "success",
        "query": query,
        "capability": capability,
        "loaded_tools": loaded,
        "loaded_count": len(loaded),
        "not_loaded_tools": not_loaded,
        "not_loaded_count": len(not_loaded),
        "total_known": len(all_known),
        "hint": (
            "Pass a `query` substring to filter tool names. "
            'Set `capability="ready"` to include the routable-worker '
            "snapshot (only meaningful when this server manages workers)."
        ),
    }

    return response


# ---------------------------------------------------------------------------
# Public registration entrypoint.
# ---------------------------------------------------------------------------


def register_baseline_tools(
    server: FastMCP,
    *,
    known_tool_names: set[str] | None = None,
) -> None:
    """Register the canonical ``discover_tools`` meta-tool on a FastMCP server.

    This is the entrypoint every Bodai core server calls at boot. It
    wires::

        - discover_tools(query, capability) - canonical envelope

    The health trio (``get_liveness``, ``get_readiness``,
    ``health_check_all``) is NOT registered here - it belongs to
    :func:`mcp_common.health.register_health_tools`, which owns the one
    implementation of those names. Mount that module too if the server
    needs the health probes.

    Args:
        server: The FastMCP server to register on.
        known_tool_names: Optional pre-known tool universe for
            ``discover_tools``. Defaults to "currently registered
            tools" which is the lean shape used by Oneiric.

    Raises:
        TypeError: If ``server`` does not expose ``tool()`` and
            ``add_tool()``. We validate up-front so callers see a
            clear error rather than a confusing FastMCP stack trace.

    Example::
        >>> from fastmcp import FastMCP
        >>> from mcp_common.baseline_tools import register_baseline_tools
        >>> server = FastMCP(name="demo", version="0.1.0")
        >>> register_baseline_tools(server)
    """
    if not hasattr(server, "tool") or not hasattr(server, "add_tool"):
        raise TypeError(
            "register_baseline_tools requires a FastMCP-like server "
            "(with .tool() and .add_tool()). Got: "
            f"{type(server).__module__}.{type(server).__name__}"
        )

    # ----- discover_tools ---------------------------------------------
    # We use the same Tool.from_function() pattern that
    # mcp_common.tools.dispatch.apply_tool_profile uses. Tool.from_function
    # is the FastMCP 3.4+ public registration path; mcp.tool() would
    # create a redundant closure that wouldn't share state with the
    # server's tool manager.
    async def discover_tools_handler(
        query: str | None = None,
        capability: str | None = None,
    ) -> dict[str, t.Any]:
        """List registered MCP tools, optionally filtered by query.

        Args:
            query: Optional case-insensitive substring filter applied
                to tool names.
            capability: Optional capability gate. When ``"ready"``,
                include the routable-worker snapshot. Currently a
                no-op on lean servers; honored when the caller has
                registered workers via DependencyConfig.

        Returns:
            Canonical envelope with ``loaded_tools``,
            ``not_loaded_tools``, ``total_known``, and a ``hint``
            string.
        """
        return await _baseline_discover_tools(
            server,
            query=query,
            capability=capability,
            known_tool_names=known_tool_names,
        )

    discover_tool = Tool.from_function(
        fn=discover_tools_handler,
        name="discover_tools",
        description=(
            "List all tools registered on this MCP server. Pass a "
            "substring `query` to filter by name. Returns the canonical "
            "Bodai baseline envelope (status, loaded_tools, "
            "not_loaded_tools, total_known, hint)."
        ),
    )
    server.add_tool(discover_tool)


__all__ = [
    "BASELINE_REGISTERED_TOOL_NAMES",
    "BASELINE_TOOL_NAMES",
    "LivenessContext",
    "get_liveness_context",
    "register_baseline_tools",
    "seed_liveness_context",
]
