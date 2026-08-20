"""Cross-server regression test for the Bodai baseline tool surface.

Phase 3 of ``docs/plans/2026-08-20-bodai-mcp-surface-standardization.md``
pins the 4-tool baseline (discover_tools, get_liveness, get_readiness,
health_check_all) so that any future commit removing a baseline tool
from any Bodai core MCP server fails CI.

Each parametrized case opens an MCP ``tools/list`` against one
of the 5 Bodai core servers and asserts the 4 canonical baseline tools
are present in the response. The test is marked ``requires_network``
so it auto-skips in offline CI when none of the servers are reachable.
"""

from __future__ import annotations

import pytest

from mcp_common.testing.baseline_surface import (
    BaselineSurfaceError,
    assert_baseline_surface,
)

# Canonical 5-server list per Phase 3 §3 task 2.
BODAI_CORE_SERVERS = (
    pytest.param("http://localhost:8680/mcp", id="mahavishnu"),
    pytest.param("http://localhost:8682/mcp", id="akosha"),
    pytest.param("http://localhost:8683/mcp", id="dhara"),
    pytest.param("http://localhost:8676/mcp", id="crackerjack"),
    pytest.param("http://localhost:8678/mcp", id="session-buddy"),
)


async def _baseline_or_skip(server_url: str) -> list[str]:
    """Run ``assert_baseline_surface`` and skip the test on connection failure.

    ``BaselineSurfaceError`` propagates (a server that's reachable but
    missing baseline tools is the regression we want to catch). Any
    other exception - connection refused, timeout, DNS failure -
    becomes ``pytest.skip`` so offline CI doesn't fail spuriously.
    """
    try:
        return await assert_baseline_surface(server_url)
    except BaselineSurfaceError:
        raise
    except Exception as exc:  # noqa: BLE001 - intentional broad skip
        pytest.skip(
            f"{server_url} unreachable; offline CI skip ({type(exc).__name__}: {exc})"
        )


@pytest.mark.parametrize("server_url", BODAI_CORE_SERVERS)
@pytest.mark.requires_network
@pytest.mark.asyncio
async def test_baseline_surface(server_url: str) -> None:
    """Every Bodai core MCP server exposes the 4 canonical baseline tools."""
    tool_names = await _baseline_or_skip(server_url)
    assert {
        "discover_tools",
        "get_liveness",
        "get_readiness",
        "health_check_all",
    }.issubset(set(tool_names)), (
        f"{server_url} missing baseline tools; got {sorted(tool_names)}"
    )


@pytest.mark.requires_network
@pytest.mark.asyncio
async def test_baseline_surface_missing_tools_raises() -> None:
    """A bogus server URL raises (and the helper does NOT silently pass)."""
    with pytest.raises(RuntimeError):
        await assert_baseline_surface(
            "http://localhost:1/never-listening",
            timeout=1.0,
        )
