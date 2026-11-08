"""Server bootstrap helpers for Bodai MCP servers.

This module centralizes the "one-liner" wiring each Bodai core repo
needs to expose the canonical baseline tool surface
(discover_tools, get_liveness, get_readiness, health_check_all).

Background
----------
Bodai core repos historically grew parallel server entry points:
the canonical ``mcp/server.py`` and a per-repo "optimized" or "modular"
variant that CLI dispatch actually invokes. Tool registrations made
in ``mcp/server.py``-adjacent files (e.g. profiles.py's REGISTRATION_MAP,
MANDATORY_GROUPS) silently had no runtime effect on the production
path. Auditing which entry point each repo's CLI dispatches to is the
real work; the helper below is the standardized landing spot once
the right file is identified.

Usage
-----
In the file that the CLI's ``run_server`` actually calls:

.. code-block:: python

    from mcp_common.bootstrap import bootstrap_baseline_tools

    mcp = FastMCP(...)
    bootstrap_baseline_tools(mcp)  # 4 canonical baseline tools registered

After this single call, ``tools/list`` will include ``discover_tools``,
``get_liveness``, ``get_readiness``, and ``health_check_all`` for
clients that probe the standard Bodai baseline surface.

Notes
-----
- ``register_baseline_tools`` is idempotent at the FastMCP level: calling
  it twice on the same server is safe.
- Since the Phase 2 collapse, ``mcp_common.baseline_tools`` registers
  ``discover_tools`` ONLY, and this helper mounts the health trio
  through :func:`mcp_common.health.register_health_tools` - the single
  owner of those three names. A server that mounts the health surface
  through two paths (Session-Buddy mounts this helper AND
  ``register_health_tools``) still registers each name exactly once:
  the health registration is a no-op on an already-wired server.
- The liveness identity is forwarded from the current
  :class:`~mcp_common.health.LivenessContext`, so a lifespan hook that
  called ``seed_liveness_context`` before the bootstrap keeps its
  service name and version.
"""

from __future__ import annotations

from typing import Any

from mcp_common.baseline_tools import (
    BASELINE_REGISTERED_TOOL_NAMES,
    BASELINE_TOOL_NAMES,
    register_baseline_tools,
)
from mcp_common.health import get_liveness_context, register_health_tools


def bootstrap_baseline_tools(server: Any) -> list[str]:
    """Register the 4 canonical Bodai baseline tools on ``server``.

    ``discover_tools`` comes from
    :func:`mcp_common.baseline_tools.register_baseline_tools`; the health
    trio comes from :func:`mcp_common.health.register_health_tools`,
    which owns the single implementation of those three names.

    Args:
        server: A FastMCP server instance (or any object that
            ``register_baseline_tools`` accepts).

    Returns:
        The list of tool names registered, in the canonical order
        ``['discover_tools', 'get_liveness', 'get_readiness', 'health_check_all']``.
        Useful for tests that want to assert the baseline surface.
    """
    register_baseline_tools(server)

    # Forward the current liveness identity so a prior
    # ``seed_liveness_context`` call keeps winning over the defaults.
    ctx = get_liveness_context()
    register_health_tools(
        server,
        server_name=ctx.service_name,
        version=ctx.version,
        start_time=ctx.start_time,
    )

    return sorted(BASELINE_TOOL_NAMES)


__all__ = [
    "BASELINE_REGISTERED_TOOL_NAMES",
    "BASELINE_TOOL_NAMES",
    "bootstrap_baseline_tools",
]
