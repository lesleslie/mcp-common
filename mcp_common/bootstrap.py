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
- This helper does NOT seed ``LivenessContext``. Call
  ``mcp_common.baseline_tools.seed_liveness_context`` from your
  lifespan startup if you want ``get_liveness()`` to return a
  service-specific ``{service, version, uptime}`` envelope.
"""

from __future__ import annotations

from typing import Any

from mcp_common.baseline_tools import (
    BASELINE_TOOL_NAMES,
    register_baseline_tools,
)


def bootstrap_baseline_tools(server: Any) -> list[str]:
    """Register the 4 canonical Bodai baseline tools on ``server``.

    Args:
        server: A FastMCP server instance (or any object that
            ``register_baseline_tools`` accepts).

    Returns:
        The list of tool names registered, in the canonical order
        ``['discover_tools', 'get_liveness', 'get_readiness', 'health_check_all']``.
        Useful for tests that want to assert the baseline surface.
    """
    register_baseline_tools(server)
    return list(BASELINE_TOOL_NAMES)


__all__ = ["BASELINE_TOOL_NAMES", "bootstrap_baseline_tools"]
