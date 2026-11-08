"""Unit tests for mcp_common.baseline_tools (Phase 1 of bodai-mcp-surface-standardization).

The canonical baseline SURFACE is 4 tools:

    - discover_tools - introspect registered tool set
    - get_liveness - report {status, service, version, uptime}
    - get_readiness - report dependency readiness
    - health_check_all - report dependency health summary

Phase 2 of the MCP tool-disambiguation plan collapsed the overlap
between ``mcp_common.baseline_tools`` and ``mcp_common.health``: the
health trio is owned by ``mcp_common.health.register_health_tools``
now, and this module registers ``discover_tools`` only.

These tests exercise the helpers directly without spinning up a full
FastMCP server, mirroring the MockMCP pattern used by
``tests/test_health_tools.py``.
"""

from __future__ import annotations

import pytest

from mcp_common.baseline_tools import (
    BASELINE_REGISTERED_TOOL_NAMES,
    BASELINE_TOOL_NAMES,
    _baseline_discover_tools,
    register_baseline_tools,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _NamedTool:
    """Simple stand-in for a fastmcp Tool with a real ``.name`` attribute."""

    def __init__(self, name: str) -> None:
        self.name = name


class MockFastMCP:
    """Minimal FastMCP stand-in for unit tests.

    Captures every tool that ``server.tool()`` decorates plus every
    tool that ``server.add_tool()`` adds. ``list_tools()`` returns the
    union so ``discover_tools`` can introspect.
    """

    def __init__(self) -> None:
        self._tools: dict[str, object] = {}

    def tool(self):  # type: ignore[no-untyped-def]
        """Mimic ``@server.tool()`` - register decorated function."""

        def decorator(func):  # type: ignore[no-untyped-def]
            self._tools[func.__name__] = func
            return func

        return decorator

    def add_tool(self, tool):  # type: ignore[no-untyped-def]
        """Mimic ``server.add_tool()`` - register a Tool instance."""
        # Tool.from_function returns a Tool; Tool has a .name attribute.
        self._tools[tool.name] = tool

    async def list_tools(self):  # type: ignore[no-untyped-def]
        """Mimic FastMCP.list_tools() - return Tool-like objects."""
        return [_NamedTool(n) for n in self._tools]

    def tool_names(self) -> list[str]:
        """Helper: sorted list of registered tool names."""
        return sorted(self._tools.keys())


# ---------------------------------------------------------------------------
# Module surface tests
# ---------------------------------------------------------------------------


class TestBaselineModule:
    """Sanity checks on the module surface itself."""

    def test_baseline_tool_names_is_frozen(self) -> None:
        """The baseline SURFACE is still the canonical 4-tool set."""
        assert isinstance(BASELINE_TOOL_NAMES, frozenset)
        assert BASELINE_TOOL_NAMES == frozenset(
            {
                "discover_tools",
                "get_liveness",
                "get_readiness",
                "health_check_all",
            }
        )

    def test_baseline_tool_names_are_immutable_strings(self) -> None:
        for name in BASELINE_TOOL_NAMES:
            assert isinstance(name, str)
            assert name == name.strip()
            assert name == name.lower()

    def test_registered_tool_names_are_discover_tools_only(self) -> None:
        """The health trio moved to mcp_common.health (Phase 2 collapse)."""
        assert isinstance(BASELINE_REGISTERED_TOOL_NAMES, frozenset)
        assert BASELINE_REGISTERED_TOOL_NAMES == frozenset({"discover_tools"})
        assert BASELINE_REGISTERED_TOOL_NAMES < BASELINE_TOOL_NAMES

    def test_register_baseline_tools_rejects_non_fastmcp_servers(self) -> None:
        """A plain object without .tool() / .add_tool() should fail loudly."""
        with pytest.raises(TypeError, match="FastMCP-like server"):
            register_baseline_tools(object())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# discover_tools tests
# ---------------------------------------------------------------------------


class TestBaselineDiscoverTools:
    """Exercise the canonical discover_tools envelope shape."""

    @pytest.mark.asyncio
    async def test_returns_canonical_envelope_with_no_query(self) -> None:
        server = MockFastMCP()
        server.add_tool(_NamedTool("foo"))
        server.add_tool(_NamedTool("bar"))

        result = await _baseline_discover_tools(server)

        assert result["status"] == "success"
        assert result["query"] is None
        assert result["capability"] is None
        assert result["loaded_tools"] == ["bar", "foo"]  # sorted
        assert result["loaded_count"] == 2
        assert result["not_loaded_tools"] == []
        assert result["not_loaded_count"] == 0
        assert result["total_known"] == 2
        assert isinstance(result["hint"], str)

    @pytest.mark.asyncio
    async def test_query_substring_filter_is_case_insensitive(self) -> None:
        server = MockFastMCP()
        server.add_tool(_NamedTool("discover_tools"))
        server.add_tool(_NamedTool("get_liveness"))
        server.add_tool(_NamedTool("dispatch_to_pool"))

        # Query "tools" (lowercase) should match "discover_tools" via
        # the case-insensitive substring filter but not
        # "get_liveness" or "dispatch_to_pool".
        result = await _baseline_discover_tools(server, query="tools")

        loaded_names = result["loaded_tools"]
        assert "discover_tools" in loaded_names
        assert "get_liveness" not in loaded_names
        assert "dispatch_to_pool" not in loaded_names

    @pytest.mark.asyncio
    async def test_known_tool_names_overrides_default_universe(self) -> None:
        """When ``known_tool_names`` is supplied, missing tools appear as not_loaded."""
        server = MockFastMCP()
        server.add_tool(_NamedTool("foo"))

        result = await _baseline_discover_tools(
            server,
            known_tool_names={"foo", "bar", "baz"},
        )

        assert result["loaded_tools"] == ["foo"]
        assert result["not_loaded_tools"] == ["bar", "baz"]
        assert result["total_known"] == 3

    @pytest.mark.asyncio
    async def test_list_tools_failure_returns_empty_envelope(self) -> None:
        """If ``server.list_tools()`` blows up, we still return a valid envelope."""

        class BrokenServer(MockFastMCP):
            async def list_tools(self):  # type: ignore[override]
                raise RuntimeError("tool registry unavailable")

        server = BrokenServer()
        server.add_tool(_NamedTool("foo"))

        result = await _baseline_discover_tools(server)

        # Envelope still has all canonical keys.
        for key in (
            "status",
            "query",
            "capability",
            "loaded_tools",
            "loaded_count",
            "not_loaded_tools",
            "not_loaded_count",
            "total_known",
            "hint",
        ):
            assert key in result
        assert result["loaded_count"] == 0


# ---------------------------------------------------------------------------
# register_baseline_tools integration tests
# ---------------------------------------------------------------------------


class TestRegisterBaselineTools:
    """End-to-end: register on a mock server, exercise the tool."""

    def test_registers_discover_tools(self) -> None:
        server = MockFastMCP()
        register_baseline_tools(server)

        assert "discover_tools" in server.tool_names()

    def test_does_not_register_the_health_trio(self) -> None:
        """The health trio belongs to mcp_common.health - never registered here.

        Registering it here is what made Session-Buddy double-register
        ``get_liveness`` / ``get_readiness`` / ``health_check_all``.
        """
        server = MockFastMCP()
        register_baseline_tools(server)

        registered = set(server.tool_names())
        for name in ("get_liveness", "get_readiness", "health_check_all"):
            assert name not in registered

    def test_no_extra_tools_registered(self) -> None:
        """Only ``discover_tools`` - nothing else."""
        server = MockFastMCP()
        register_baseline_tools(server)

        assert set(server.tool_names()) == set(BASELINE_REGISTERED_TOOL_NAMES)

    @pytest.mark.asyncio
    async def test_registered_discover_tools_lists_itself(self) -> None:
        server = MockFastMCP()
        register_baseline_tools(server)

        # The FunctionTool returned by Tool.from_function has a .fn
        # attribute we can invoke; the wrapper itself is not callable.
        discover_tool = server._tools["discover_tools"]
        result = await discover_tool.fn()

        assert result["status"] == "success"
        assert result["loaded_tools"] == ["discover_tools"]
        assert result["loaded_count"] == 1

    @pytest.mark.asyncio
    async def test_known_tool_names_reaches_the_envelope(self) -> None:
        """``known_tool_names`` still widens the discover_tools universe."""
        server = MockFastMCP()
        register_baseline_tools(server, known_tool_names={"discover_tools", "ghost"})

        discover_tool = server._tools["discover_tools"]
        result = await discover_tool.fn()

        assert result["loaded_tools"] == ["discover_tools"]
        assert result["not_loaded_tools"] == ["ghost"]
