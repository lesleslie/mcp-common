"""Online smoke test for ``mcp_common.clients.CommonMCPClient``.

Instantiates :class:`CommonMCPClient`, calls one tool against a running
MCP server reachable at ``--target``, and reports success/failure.

CLI::

    python scripts/smoke_common_mcp_client.py --target URL --tool NAME \\
        [--args JSON_STRING] [--timeout-seconds=10]

Exits 0 on success, 1 on any exception (with the exception class + message
printed to stderr).

Implements: REQ-001 (live call_site behaviour) per umbrella
``docs/plans/2026-09-14-common-mcp-client-transport-unification.md``.

NOTE: This script is **online** — it requires a running MCP server at the
target URL. The ``smoke_health_feed.py`` companion script is the offline
alternative (no server needed).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Allow ``python scripts/smoke_common_mcp_client.py`` to find the in-tree
# ``mcp_common`` package without an editable install.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from mcp_common.clients import CommonMCPClient


async def _call(target: str, tool_name: str, arguments: dict, timeout: float) -> object:
    async with CommonMCPClient(base_url=target, timeout=timeout) as client:
        return await client.call_tool(tool_name, arguments, timeout=timeout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        required=True,
        help="Target MCP server URL (e.g. http://127.0.0.1:8680/mcp)",
    )
    parser.add_argument(
        "--tool",
        required=True,
        help="Tool name to invoke (e.g. query_local_traces)",
    )
    parser.add_argument(
        "--args",
        default="{}",
        help="JSON-encoded arguments dict (default: {})",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=10.0,
        help="Per-call timeout in seconds (default: 10)",
    )
    args = parser.parse_args()

    try:
        arguments = json.loads(args.args) if args.args.strip() else {}
    except json.JSONDecodeError as exc:
        print(f"FAIL: --args is not valid JSON: {exc}", file=sys.stderr)
        return 1

    if not isinstance(arguments, dict):
        print("FAIL: --args JSON must decode to an object/dict", file=sys.stderr)
        return 1

    try:
        result = asyncio.run(
            _call(args.target, args.tool, arguments, args.timeout_seconds)
        )
    except Exception as exc:
        print(
            f"FAIL: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    print(
        f"PASS: {args.tool}@target={args.target} -> {type(result).__name__}",
        file=sys.stderr,
    )
    try:
        json_repr = json.dumps(result, default=str, indent=2)
        print(json_repr)
    except TypeError, ValueError:
        print(repr(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
