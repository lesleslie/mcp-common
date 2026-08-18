"""Integration test: apply_tool_profile against a real FastMCP 3.4.7 server."""
from __future__ import annotations

import pytest
from fastmcp import FastMCP
from fastmcp.tools import Tool

from mcp_common.tools import ToolProfile
from mcp_common.tools.dispatch import ALL_TOOLS, _apply_tool_profile, _apply_tool_profile_async


def make_server_with_groups(monkeypatch_session):
    """Build a FastMCP server with 3 groups (group_a, group_b, group_health)."""
    server = FastMCP("test-server")

    def register_group_a(s):
        s.add_tool(Tool.from_function(fn=lambda: "a1", name="tool_a1", description="A1"))
        s.add_tool(Tool.from_function(fn=lambda: "a2", name="tool_a2", description="A2"))

    def register_group_b(s):
        s.add_tool(Tool.from_function(fn=lambda: "b1", name="tool_b1", description="B1"))

    def register_group_health(s):
        s.add_tool(Tool.from_function(fn=lambda: "ok", name="get_liveness", description="Liveness"))
        s.add_tool(Tool.from_function(fn=lambda: "ok", name="get_readiness", description="Readiness"))
        s.add_tool(Tool.from_function(fn=lambda: "ok", name="health_check", description="Health"))
        s.add_tool(Tool.from_function(fn=lambda: "ok", name="health_check_all", description="Health All"))

    def register_all(s):
        register_group_a(s)
        register_group_b(s)
        register_group_health(s)

    registration_map = {
        "group_a": register_group_a,
        "group_b": register_group_b,
        "group_health": register_group_health,
    }

    registrations = {
        ToolProfile.MINIMAL: ["group_health"],
        ToolProfile.STANDARD: ["group_a", "group_health"],
        ToolProfile.FULL: ALL_TOOLS,
    }

    return server, registrations, registration_map, register_all


@pytest.mark.asyncio
async def test_minimal_registers_mandatory_and_discover(monkeypatch):
    server, registrations, reg_map, register_all = make_server_with_groups(monkeypatch)
    monkeypatch.setenv("TEST_PROFILE", "minimal")
    await _apply_tool_profile(
        server,
        profile_env_var="TEST_PROFILE",
        registrations=registrations,
        registration_map=reg_map,
        register_all_fn=register_all,
    )
    names = {t.name for t in await server.list_tools()}
    assert {"get_liveness", "get_readiness", "discover_tools"}.issubset(names)
    assert "tool_a1" not in names
    assert "tool_a2" not in names
    assert "tool_b1" not in names


@pytest.mark.asyncio
async def test_standard_registers_expected_groups(monkeypatch):
    server, registrations, reg_map, register_all = make_server_with_groups(monkeypatch)
    monkeypatch.setenv("TEST_PROFILE", "standard")
    await _apply_tool_profile(
        server,
        profile_env_var="TEST_PROFILE",
        registrations=registrations,
        registration_map=reg_map,
        register_all_fn=register_all,
    )
    names = {t.name for t in await server.list_tools()}
    assert {"tool_a1", "tool_a2", "get_liveness", "get_readiness", "discover_tools"}.issubset(names)
    assert "tool_b1" not in names


@pytest.mark.asyncio
async def test_full_registers_everything(monkeypatch):
    server, registrations, reg_map, register_all = make_server_with_groups(monkeypatch)
    monkeypatch.setenv("TEST_PROFILE", "full")
    await _apply_tool_profile(
        server,
        profile_env_var="TEST_PROFILE",
        registrations=registrations,
        registration_map=reg_map,
        register_all_fn=register_all,
    )
    names = {t.name for t in await server.list_tools()}
    assert {"tool_a1", "tool_a2", "tool_b1", "get_liveness", "get_readiness", "discover_tools"}.issubset(names)


@pytest.mark.asyncio
async def test_mandatory_subsetting(monkeypatch):
    """Repos without all 4 health tools can opt-out via mandatory_tools=set()."""
    server, registrations, reg_map, register_all = make_server_with_groups(monkeypatch)
    monkeypatch.setenv("TEST_PROFILE", "minimal")
    await _apply_tool_profile(
        server,
        profile_env_var="TEST_PROFILE",
        registrations={ToolProfile.MINIMAL: [], ToolProfile.STANDARD: [], ToolProfile.FULL: ALL_TOOLS},
        registration_map=reg_map,
        register_all_fn=register_all,
        mandatory_tools=set(),
    )
    names = {t.name for t in await server.list_tools()}
    assert "get_liveness" not in names
    assert "discover_tools" in names


@pytest.mark.asyncio
async def test_discover_tools_idempotent(monkeypatch):
    """Calling apply_tool_profile twice leaves exactly one discover_tools and identical tool set."""
    server, registrations, reg_map, register_all = make_server_with_groups(monkeypatch)
    monkeypatch.setenv("TEST_PROFILE", "full")
    await _apply_tool_profile(
        server,
        profile_env_var="TEST_PROFILE",
        registrations=registrations,
        registration_map=reg_map,
        register_all_fn=register_all,
    )
    first_names = {t.name for t in await server.list_tools()}
    # Second call
    await _apply_tool_profile(
        server,
        profile_env_var="TEST_PROFILE",
        registrations=registrations,
        registration_map=reg_map,
        register_all_fn=register_all,
    )
    second_names = {t.name for t in await server.list_tools()}
    assert "discover_tools" in second_names
    assert first_names == second_names, "Second call must produce identical tool set"


@pytest.mark.asyncio
async def test_unset_env_defaults_to_full(monkeypatch):
    """Unset env var falls through to FULL (matches existing from_env)."""
    monkeypatch.delenv("TEST_PROFILE", raising=False)
    server, registrations, reg_map, register_all = make_server_with_groups(monkeypatch)
    await _apply_tool_profile(
        server,
        profile_env_var="TEST_PROFILE",
        registrations=registrations,
        registration_map=reg_map,
        register_all_fn=register_all,
    )
    names = {t.name for t in await server.list_tools()}
    # FULL registers everything
    assert {"tool_a1", "tool_a2", "tool_b1", "discover_tools"}.issubset(names)


@pytest.mark.asyncio
async def test_callable_items_in_minimal(monkeypatch):
    """Items in registrations can be callables (not just strings)."""
    from fastmcp import FastMCP
    from fastmcp.tools import Tool
    from mcp_common.tools.dispatch import _apply_tool_profile

    server = FastMCP("callable-test-server")

    def direct_register(s):
        s.add_tool(
            Tool.from_function(fn=lambda: "x", name="direct_tool", description="Direct")
        )

    monkeypatch.setenv("TEST_PROFILE", "minimal")
    await _apply_tool_profile(
        server,
        profile_env_var="TEST_PROFILE",
        registrations={
            ToolProfile.MINIMAL: [direct_register],
            ToolProfile.STANDARD: [],
            ToolProfile.FULL: ALL_TOOLS,
        },
        registration_map={},
        register_all_fn=lambda s: None,
        mandatory_tools=set(),
    )
    names = {t.name for t in await server.list_tools()}
    assert "direct_tool" in names
    assert "discover_tools" in names


@pytest.mark.asyncio
async def test_string_group_not_in_map_raises(monkeypatch):
    """String group name in registrations but missing from registration_map raises ValueError."""
    from mcp_common.tools.dispatch import _apply_tool_profile

    server = FastMCP("missing-map-test")
    monkeypatch.setenv("TEST_PROFILE", "minimal")
    with pytest.raises(ValueError, match="not in registration_map"):
        await _apply_tool_profile(
            server,
            profile_env_var="TEST_PROFILE",
            registrations={
                ToolProfile.MINIMAL: ["nonexistent_group"],
                ToolProfile.STANDARD: [],
                ToolProfile.FULL: ALL_TOOLS,
            },
            registration_map={},
            register_all_fn=lambda s: None,
        )


@pytest.mark.asyncio
async def test_full_with_explicit_group_list(monkeypatch):
    """FULL profile can use an explicit list of group names instead of ALL_TOOLS."""
    from mcp_common.tools.dispatch import _apply_tool_profile

    server = FastMCP("full-list-test")

    def register_group_z(s):
        s.add_tool(
            Tool.from_function(
                fn=lambda: "z", name="zebra_tool", description="Zebra group"
            )
        )

    monkeypatch.setenv("TEST_PROFILE", "full")
    await _apply_tool_profile(
        server,
        profile_env_var="TEST_PROFILE",
        registrations={
            ToolProfile.MINIMAL: [],
            ToolProfile.STANDARD: [],
            ToolProfile.FULL: ["group_z"],
        },
        registration_map={"group_z": register_group_z},
        register_all_fn=None,
        mandatory_tools=set(),
    )
    names = {t.name for t in await server.list_tools()}
    assert "zebra_tool" in names


@pytest.mark.asyncio
async def test_async_register_all_fn_via_async_helper(monkeypatch):
    """When _apply_tool_profile is called with sync register_all_fn in async context."""
    from mcp_common.tools.dispatch import _apply_tool_profile

    server = FastMCP("sync-register-async-test")

    def sync_register_all(s):
        s.add_tool(
            Tool.from_function(
                fn=lambda: "x", name="sync_added_tool", description="Sync"
            )
        )

    monkeypatch.setenv("TEST_PROFILE", "full")
    await _apply_tool_profile(
        server,
        profile_env_var="TEST_PROFILE",
        registrations={
            ToolProfile.MINIMAL: [],
            ToolProfile.STANDARD: [],
            ToolProfile.FULL: ALL_TOOLS,
        },
        registration_map={},
        register_all_fn=sync_register_all,
        mandatory_tools=set(),
    )
    names = {t.name for t in await server.list_tools()}
    assert "sync_added_tool" in names


@pytest.mark.asyncio
async def test_mandatory_tool_not_in_map_raises(monkeypatch):
    """A mandatory tool missing from registration_map raises ValueError."""
    from mcp_common.tools.dispatch import _apply_tool_profile

    server = FastMCP("missing-mandatory-test")
    monkeypatch.setenv("TEST_PROFILE", "minimal")
    with pytest.raises(ValueError, match="MANDATORY tool"):
        await _apply_tool_profile(
            server,
            profile_env_var="TEST_PROFILE",
            registrations={
                ToolProfile.MINIMAL: [],
                ToolProfile.STANDARD: [],
                ToolProfile.FULL: ALL_TOOLS,
            },
            registration_map={"get_liveness": lambda s: None},  # only 1 of 4
            register_all_fn=lambda s: None,
        )


@pytest.mark.asyncio
async def test_default_discovery_filter(monkeypatch):
    """_default_discovery filters tools by query when filter_query is given."""
    from mcp_common.tools.dispatch import _default_discovery

    server = FastMCP("discovery-test")
    server.add_tool(
        Tool.from_function(
            fn=lambda: "x", name="alpha_tool", description="Alpha description"
        )
    )
    server.add_tool(
        Tool.from_function(
            fn=lambda: "y", name="beta_tool", description="Beta description"
        )
    )

    # Filter by name
    results = await _default_discovery(server, "alpha")
    names = [r["name"] for r in results]
    assert "alpha_tool" in names
    assert "beta_tool" not in names

    # Filter by description
    results = await _default_discovery(server, "Beta")
    names = [r["name"] for r in results]
    assert "beta_tool" in names
    assert "alpha_tool" not in names


@pytest.mark.asyncio
async def test_register_all_fn_with_async(monkeypatch):
    """register_all_fn can be async; _maybe_await handles the coroutine."""
    from mcp_common.tools.dispatch import _apply_tool_profile

    server = FastMCP("async-register-all-test")

    async def async_register_all(s):
        s.add_tool(
            Tool.from_function(
                fn=lambda: "x", name="async_added_tool", description="Async"
            )
        )

    monkeypatch.setenv("TEST_PROFILE", "full")
    await _apply_tool_profile(
        server,
        profile_env_var="TEST_PROFILE",
        registrations={
            ToolProfile.MINIMAL: [],
            ToolProfile.STANDARD: [],
            ToolProfile.FULL: ALL_TOOLS,
        },
        registration_map={},
        register_all_fn=async_register_all,
        mandatory_tools=set(),
    )
    names = {t.name for t in await server.list_tools()}
    assert "async_added_tool" in names


@pytest.mark.asyncio
async def test_custom_discovery_fn(monkeypatch):
    """Custom discovery_fn is used to register discover_tools."""
    from mcp_common.tools.dispatch import _apply_tool_profile

    server = FastMCP("custom-discovery-test")

    async def custom_disc(s, q):
        return [{"name": "custom", "description": "custom", "inputSchema": {}, "group": None}]

    monkeypatch.setenv("TEST_PROFILE", "minimal")
    await _apply_tool_profile(
        server,
        profile_env_var="TEST_PROFILE",
        registrations={
            ToolProfile.MINIMAL: [],
            ToolProfile.STANDARD: [],
            ToolProfile.FULL: ALL_TOOLS,
        },
        registration_map={},
        register_all_fn=lambda s: None,
        discovery_fn=custom_disc,
        # Skip the default MANDATORY_TOOLS lookup
        mandatory_tools=set(),
    )
    # Custom discover_tools registered (we don't call it here; the goal
    # is to exercise the custom discovery_fn code path in `_apply_tool_profile_async`).
    names = {t.name for t in await server.list_tools()}
    assert "discover_tools" in names


@pytest.mark.asyncio
async def test_apply_tool_profile_sync_from_async_raises(monkeypatch):
    """Calling apply_tool_profile() from within a running event loop raises RuntimeError."""
    from mcp_common.tools.dispatch import apply_tool_profile

    server = FastMCP("sync-in-async-test")
    monkeypatch.setenv("TEST_PROFILE", "minimal")
    with pytest.raises(RuntimeError, match="running event loop"):
        apply_tool_profile(
            server,
            profile_env_var="TEST_PROFILE",
            registrations={
                ToolProfile.MINIMAL: [],
                ToolProfile.STANDARD: [],
                ToolProfile.FULL: ALL_TOOLS,
            },
            registration_map={},
            register_all_fn=lambda s: None,
        )


def test_apply_tool_profile_sync_no_server(monkeypatch):
    """apply_tool_profile() with server=None runs sync validation only."""
    from mcp_common.tools.dispatch import apply_tool_profile

    monkeypatch.setenv("TEST_PROFILE", "minimal")
    # Sync call, no server — should not raise
    apply_tool_profile(
        server=None,  # type: ignore
        profile_env_var="TEST_PROFILE",
        registrations={
            ToolProfile.MINIMAL: [],
            ToolProfile.STANDARD: [],
            ToolProfile.FULL: ALL_TOOLS,
        },
        registration_map={},
        register_all_fn=lambda s: None,
    )


@pytest.mark.asyncio
async def test_async_helper_with_server_none(monkeypatch):
    """_apply_tool_profile with server=None is a no-op async."""
    from mcp_common.tools.dispatch import _apply_tool_profile

    monkeypatch.setenv("TEST_PROFILE", "minimal")
    # No server, no error
    await _apply_tool_profile(
        server=None,  # type: ignore
        profile_env_var="TEST_PROFILE",
        registrations={
            ToolProfile.MINIMAL: [],
            ToolProfile.STANDARD: [],
            ToolProfile.FULL: ALL_TOOLS,
        },
        registration_map={},
        register_all_fn=lambda s: None,
    )
