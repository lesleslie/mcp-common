#!/usr/bin/env python3
"""Manual smoke script for the Bodai baseline tools (Phase 1).

Seeds the liveness identity and calls ``bootstrap_baseline_tools`` on a
fresh FastMCP instance, then exercises each of the 4 canonical tools,
printing the structured JSON envelope. Run from the repo root::

    PYTHONPATH=. python scripts/smoke_baseline.py

Each tool prints exactly one JSON envelope so a downstream parser can
diff against the canonical shape from
``docs/plans/2026-08-20-bodai-mcp-surface-standardization.md``.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any

from fastmcp import FastMCP

# Make ``mcp_common`` importable when this script is run from the
# repo root without an editable install (matches the test-suite path).
sys.path.insert(0, ".")

from mcp_common.baseline_tools import seed_liveness_context
from mcp_common.bootstrap import bootstrap_baseline_tools


def _print_envelope(label: str, payload: dict[str, Any]) -> None:
    """Print one JSON envelope per line so downstream tools can grep."""
    print(f"=== {label} ===")
    print(json.dumps(payload, indent=2, default=str))
    print()


async def _invoke(server: FastMCP, name: str, **kwargs: Any) -> dict[str, Any]:
    """Call a registered tool by name and unwrap its structured content.

    FastMCP's public ``call_tool`` returns a ``ToolResult`` envelope;
    the dict the underlying function returned lives at
    ``.structured_content`` (when the function declares a dict return).
    """
    result = await server.call_tool(name, kwargs or None)
    payload: dict[str, Any]
    if hasattr(result, "structured_content") and result.structured_content:
        payload = dict(result.structured_content)
    else:
        # Fallback: parse the TextContent JSON.
        text_blocks = [
            c.text for c in result.content if getattr(c, "type", None) == "text"
        ]
        joined = "\n".join(text_blocks)
        try:
            loaded = json.loads(joined)
            payload = loaded if isinstance(loaded, dict) else {"raw": loaded}
        except json.JSONDecodeError:
            payload = {"raw": joined}
    return payload


async def _main() -> int:
    """Build a fresh FastMCP server, register the baseline, run each tool."""
    server = FastMCP(name="smoke-baseline", version="0.0.0+smoke")

    # Seed the liveness identity BEFORE the bootstrap so get_liveness
    # reports meaningful numbers. The bootstrap forwards the seeded
    # identity to the health registration.
    seed_liveness_context(
        service_name="smoke-baseline",
        version="0.0.0+smoke",
        # Pretend we started 1.25s ago.
        start_time=time.time() - 1.25,
    )

    # ``discover_tools`` comes from mcp_common.baseline_tools; the
    # health trio comes from mcp_common.health (Phase 2 collapse - one
    # registration per name, one implementation behind it).
    bootstrap_baseline_tools(server)

    # discover_tools: list the registered set with a query filter.
    discover_payload = await _invoke(server, "discover_tools", query="health")
    _print_envelope("discover_tools(query='health')", discover_payload)

    # get_liveness: canonical {status, service, version, uptime}.
    liveness_payload = await _invoke(server, "get_liveness")
    _print_envelope("get_liveness()", liveness_payload)

    # get_readiness: no deps -> immediate ready.
    readiness_payload = await _invoke(server, "get_readiness")
    _print_envelope("get_readiness()", readiness_payload)

    # health_check_all: no deps -> immediate healthy.
    health_payload = await _invoke(server, "health_check_all")
    _print_envelope("health_check_all()", health_payload)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
