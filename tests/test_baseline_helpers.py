"""Unit tests for mcp_common.baseline_tools (Phase 1 of bodai-mcp-surface-standardization).

The 4 canonical baseline tools are:

    - discover_tools - introspect registered tool set
    - get_liveness - report {status, service, version, uptime}
    - get_readiness - report dependency readiness
    - health_check_all - report dependency health summary

These tests exercise the helpers directly without spinning up a full
FastMCP server, mirroring the MockMCP pattern used by
``tests/test_health_tools.py``.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_common.baseline_tools import (
    BASELINE_TOOL_NAMES,
    LivenessContext,
    _baseline_discover_tools,
    _baseline_get_liveness,
    _baseline_get_readiness,
    _baseline_health_check_all,
    get_liveness_context,
    register_baseline_tools,
    seed_liveness_context,
)
from mcp_common.health import (
    DependencyConfig,
    DependencyWaiter,
    HealthCheckResult,
    HealthChecker,
    HealthStatus,
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


@pytest.fixture(autouse=True)
def _reset_liveness_singleton():
    """Reset module-level LivenessContext before each test.

    ``seed_liveness_context`` mutates a singleton; without this fixture
    test ordering would matter.
    """
    seed_liveness_context(
        service_name="mcp-server",
        version="0.0.0",
        start_time=time.time(),
    )
    yield


# ---------------------------------------------------------------------------
# Module surface tests
# ---------------------------------------------------------------------------


class TestBaselineModule:
    """Sanity checks on the module surface itself."""

    def test_baseline_tool_names_is_frozen(self) -> None:
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

    def test_register_baseline_tools_rejects_non_fastmcp_servers(self) -> None:
        """A plain object without .tool() / .add_tool() should fail loudly."""
        with pytest.raises(TypeError, match="FastMCP-like server"):
            register_baseline_tools(object())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# LivenessContext singleton tests
# ---------------------------------------------------------------------------


class TestLivenessContextSingleton:
    """The singleton must be readable + writable from outside the module."""

    def test_default_context_has_sane_defaults(self) -> None:
        ctx = get_liveness_context()
        assert ctx.service_name == "mcp-server"
        assert ctx.version == "0.0.0"
        assert ctx.start_time <= time.time()

    def test_seed_overwrites_singleton(self) -> None:
        before = get_liveness_context()
        seed_liveness_context(
            service_name="session-buddy",
            version="0.7.0",
            start_time=1_000_000.0,
        )
        after = get_liveness_context()

        assert before is not after
        assert after.service_name == "session-buddy"
        assert after.version == "0.7.0"
        assert after.start_time == 1_000_000.0

    def test_seed_returns_seeded_context(self) -> None:
        seeded = seed_liveness_context(
            service_name="dhara",
            version="1.2.3",
            start_time=1_234_567.0,
        )
        assert isinstance(seeded, LivenessContext)
        assert seeded.service_name == "dhara"

    def test_uptime_seconds_is_non_negative(self) -> None:
        ctx = LivenessContext(start_time=time.time() - 5.0)
        assert ctx.uptime_seconds() >= 5.0
        assert ctx.uptime_seconds() < 6.0

    def test_uptime_seconds_clamps_future_drift(self) -> None:
        """If ``start_time`` is in the future (clock skew), return 0."""
        ctx = LivenessContext(start_time=time.time() + 100.0)
        assert ctx.uptime_seconds() == 0.0


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
# get_liveness tests
# ---------------------------------------------------------------------------


class TestBaselineGetLiveness:
    """get_liveness must read from the LivenessContext singleton."""

    @pytest.mark.asyncio
    async def test_returns_canonical_envelope(self) -> None:
        seed_liveness_context(
            service_name="session-buddy",
            version="0.7.1",
            start_time=time.time() - 12.5,
        )

        result = await _baseline_get_liveness()

        assert result["status"] == "ok"
        assert result["service"] == "session-buddy"
        assert result["version"] == "0.7.1"
        assert isinstance(result["uptime_seconds"], float)
        assert result["uptime_seconds"] >= 12.5
        assert result["uptime_seconds"] < 13.0

    @pytest.mark.asyncio
    async def test_uptime_rounds_to_two_decimals(self) -> None:
        seed_liveness_context(
            service_name="dhara",
            version="1.0.0",
            start_time=time.time() - 3.14159,
        )

        result = await _baseline_get_liveness()
        # Rounded to 2dp; allow ±0.01 for test latency.
        assert abs(result["uptime_seconds"] - 3.14) < 0.05


# ---------------------------------------------------------------------------
# get_readiness tests
# ---------------------------------------------------------------------------


class TestBaselineGetReadiness:
    """get_readiness reports ready when no deps are configured."""

    @pytest.mark.asyncio
    async def test_no_dependencies_is_immediately_ready(self) -> None:
        result = await _baseline_get_readiness(dependencies={}, waiter=None)
        assert result == {"ready": True, "checks": {"process": "ok"}}

    @pytest.mark.asyncio
    async def test_failed_required_deps_yield_unready(self) -> None:
        dep = DependencyConfig(host="localhost", port=9999, required=True)
        waiter = MagicMock(spec=DependencyWaiter)
        waiter.wait_for_all = AsyncMock(
            return_value=MagicMock(
                success=False,
                dependencies={"db": MagicMock(status=HealthStatus.UNHEALTHY)},
                failed_required=["db"],
            )
        )

        result = await _baseline_get_readiness(
            dependencies={"db": dep}, waiter=waiter
        )

        assert result["ready"] is False
        assert result["checks"]["process"] == "ok"
        assert result["checks"]["db"] == "unhealthy"
        assert result["failed_required"] == ["db"]


# ---------------------------------------------------------------------------
# health_check_all tests
# ---------------------------------------------------------------------------


class TestBaselineHealthCheckAll:
    """health_check_all aggregates per-dependency status."""

    @pytest.mark.asyncio
    async def test_no_dependencies_reports_healthy(self) -> None:
        result = await _baseline_health_check_all(dependencies={}, checker=None)
        assert result["status"] == "healthy"
        assert result["services"] == {}
        assert result["total_services"] == 0
        assert result["healthy_services"] == 0
        assert "No dependencies configured" in result["message"]
        # Timestamp is always emitted so consumers can cache-bust.
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_aggregates_healthy_and_degraded(self) -> None:
        dependencies = {
            "db": DependencyConfig(port=5432),
            "cache": DependencyConfig(port=6379),
        }
        checker = MagicMock(spec=HealthChecker)
        checker.check = AsyncMock(
            side_effect=[
                HealthCheckResult(
                    service_name="db", status=HealthStatus.HEALTHY
                ),
                HealthCheckResult(
                    service_name="cache", status=HealthStatus.DEGRADED
                ),
            ]
        )

        result = await _baseline_health_check_all(
            dependencies=dependencies, checker=checker
        )

        # Mixed healthy+degraded still counts as overall healthy.
        assert result["status"] == "healthy"
        assert result["total_services"] == 2
        assert result["healthy_services"] == 1
        assert "db" in result["services"]
        assert "cache" in result["services"]

    @pytest.mark.asyncio
    async def test_unhealthy_dependency_flips_overall_status(self) -> None:
        dependencies = {"db": DependencyConfig(port=5432)}
        checker = MagicMock(spec=HealthChecker)
        checker.check = AsyncMock(
            return_value=HealthCheckResult(
                service_name="db",
                status=HealthStatus.UNHEALTHY,
                error="timeout",
            )
        )

        result = await _baseline_health_check_all(
            dependencies=dependencies, checker=checker
        )

        assert result["status"] == "unhealthy"
        assert result["services"]["db"]["status"] == "unhealthy"
        assert result["services"]["db"]["error"] == "timeout"

    @pytest.mark.asyncio
    async def test_checker_exception_isolated_to_one_dep(self) -> None:
        dependencies = {
            "db": DependencyConfig(port=5432),
            "cache": DependencyConfig(port=6379),
        }
        checker = MagicMock(spec=HealthChecker)
        checker.check = AsyncMock(
            side_effect=[
                HealthCheckResult(service_name="db", status=HealthStatus.HEALTHY),
                RuntimeError("boom"),
            ]
        )

        result = await _baseline_health_check_all(
            dependencies=dependencies, checker=checker
        )

        assert result["status"] == "unhealthy"
        assert result["services"]["db"]["status"] == "healthy"
        assert result["services"]["cache"]["status"] == "unhealthy"
        assert result["services"]["cache"]["error"] == "boom"

    @pytest.mark.asyncio
    async def test_response_includes_iso_timestamp(self) -> None:
        result = await _baseline_health_check_all(dependencies={}, checker=None)
        assert "timestamp" in result
        # ISO 8601 with UTC marker
        assert "T" in result["timestamp"]
        assert result["timestamp"].endswith("+00:00") or result[
            "timestamp"
        ].endswith("Z")


# ---------------------------------------------------------------------------
# register_baseline_tools integration tests
# ---------------------------------------------------------------------------


class TestRegisterBaselineTools:
    """End-to-end: register on a mock server, exercise each tool."""

    def test_registers_all_four_baseline_tools(self) -> None:
        server = MockFastMCP()
        register_baseline_tools(server, service_name="demo", version="1.0.0")

        registered = set(server.tool_names())
        for name in BASELINE_TOOL_NAMES:
            assert name in registered, f"missing baseline tool: {name}"

    def test_no_extra_tools_registered(self) -> None:
        """Only the 4 baseline tools - nothing else."""
        server = MockFastMCP()
        register_baseline_tools(server, service_name="demo", version="1.0.0")

        assert set(server.tool_names()) == set(BASELINE_TOOL_NAMES)

    def test_seeds_liveness_context_when_kwargs_supplied(self) -> None:
        server = MockFastMCP()
        register_baseline_tools(
            server,
            service_name="mahavishnu",
            version="0.18.0",
            start_time=time.time() - 100.0,
        )

        ctx = get_liveness_context()
        assert ctx.service_name == "mahavishnu"
        assert ctx.version == "0.18.0"

    def test_explicit_liveness_context_wins_over_kwargs(self) -> None:
        server = MockFastMCP()
        ctx = LivenessContext(
            service_name="from-context",
            version="9.9.9",
            start_time=time.time() - 50.0,
        )

        register_baseline_tools(
            server,
            service_name="from-kwargs",
            version="0.0.1",
            liveness_context=ctx,
        )

        # Singleton now reflects the explicit context, not the kwargs.
        assert get_liveness_context().service_name == "from-context"
        assert get_liveness_context().version == "9.9.9"

    def test_health_check_all_uses_provided_dependencies(self) -> None:
        """When dependencies={} is passed, health_check_all short-circuits."""
        server = MockFastMCP()
        register_baseline_tools(
            server,
            service_name="demo",
            version="1.0.0",
            dependencies={},
        )

        # The tool is registered; sanity check by listing tools.
        assert "health_check_all" in server.tool_names()
        assert "get_readiness" in server.tool_names()

    @pytest.mark.asyncio
    async def test_registered_get_liveness_returns_seeded_envelope(self) -> None:
        server = MockFastMCP()
        register_baseline_tools(
            server,
            service_name="akosha",
            version="2.3.4",
            start_time=time.time() - 7.5,
        )

        # Pull the registered callable and invoke it.
        get_liveness = server._tools["get_liveness"]
        result = await get_liveness()

        assert result["status"] == "ok"
        assert result["service"] == "akosha"
        assert result["version"] == "2.3.4"
        assert result["uptime_seconds"] >= 7.5

    @pytest.mark.asyncio
    async def test_registered_get_readiness_with_no_deps(self) -> None:
        server = MockFastMCP()
        register_baseline_tools(
            server, service_name="demo", version="1.0.0", dependencies={}
        )

        get_readiness = server._tools["get_readiness"]
        result = await get_readiness()

        assert result == {"ready": True, "checks": {"process": "ok"}}

    @pytest.mark.asyncio
    async def test_registered_discover_tools_lists_baseline(self) -> None:
        server = MockFastMCP()
        register_baseline_tools(server, service_name="demo", version="1.0.0")

        # The FunctionTool returned by Tool.from_function has a .fn
        # attribute we can invoke; the wrapper itself is not callable.
        discover_tool = server._tools["discover_tools"]
        result = await discover_tool.fn()

        assert result["status"] == "success"
        for name in BASELINE_TOOL_NAMES:
            assert name in result["loaded_tools"]
        assert result["loaded_count"] == len(BASELINE_TOOL_NAMES)


# ---------------------------------------------------------------------------
# Async helpers (consumed by health_check_all / get_readiness)
# ---------------------------------------------------------------------------


def _gather(coro) -> object:  # type: ignore[no-untyped-def]
    """Drive a single coroutine for the test sync harness."""
    return asyncio.get_event_loop().run_until_complete(coro)