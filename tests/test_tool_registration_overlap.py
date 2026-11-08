"""Phase 2 proofs for the mcp-common tool-disambiguation collapse.

``mcp_common.baseline_tools`` and ``mcp_common.health`` used to BOTH
register ``get_liveness``, ``get_readiness`` and ``health_check_all``.
Session-Buddy mounts both modules, so those three names were
registered twice on every boot (the health copy silently shadowed the
baseline copy).

These tests pin the properties Phase 2 establishes:

1. One registration per name - mounting both modules registers each
   health tool exactly once.
2. The published ``health_check_service`` input schema exposes
   ``service_name`` (the tool's own parameter), not ``service_name_arg``
   (the leaked outer ``register_health_tools`` parameter).
3. The deprecation shim is driven by the ``deprecated_tools`` mapping -
   mapped names warn, unmapped names stay silent.
4. The liveness state API (``LivenessContext`` /
   ``get_liveness_context`` / ``seed_liveness_context``) stays public
   and importable from every path consumers use, with the state owned
   by ``mcp_common.health``.
5. ``bootstrap_baseline_tools`` still mounts the full 4-name baseline
   surface, so a consumer that calls it keeps what it had.

Refs: ``mahavishnu/docs/plans/2026-11-07-mcp-tool-disambiguation.md``
Phase 2.
"""

from __future__ import annotations

import logging
import time
import warnings

import pytest
from fastmcp import FastMCP

from mcp_common.baseline_tools import register_baseline_tools
from mcp_common.bootstrap import bootstrap_baseline_tools
from mcp_common.health import register_health_tools, seed_liveness_context

# FastMCP logs this when a tool name is registered twice on one server.
# The old double registration showed up here and nowhere else.
DUPLICATE_REGISTRATION_MESSAGE = "Component already exists"


async def _tool_names(server: FastMCP) -> list[str]:
    """Return the tool names the server serves."""
    return [tool.name for tool in await server.list_tools()]


async def _tool(server: FastMCP, name: str):  # type: ignore[no-untyped-def]
    """Return the registered tool named ``name``."""
    for tool in await server.list_tools():
        if tool.name == name:
            return tool
    raise AssertionError(f"tool {name!r} is not registered")


class TestNoDuplicateRegistration:
    """Mounting both modules must not register any name twice."""

    @pytest.mark.asyncio
    async def test_health_trio_registered_exactly_once(self, caplog) -> None:
        caplog.set_level(logging.WARNING)

        server = FastMCP(name="overlap")
        register_baseline_tools(server)
        register_health_tools(server, server_name="overlap", version="1.0.0")

        duplicates = [
            record.getMessage()
            for record in caplog.records
            if DUPLICATE_REGISTRATION_MESSAGE in record.getMessage()
        ]
        assert duplicates == [], f"tool names registered twice: {duplicates}"

        names = await _tool_names(server)
        for name in ("get_liveness", "get_readiness", "health_check_all"):
            assert names.count(name) == 1, f"{name} served {names.count(name)} times"
        assert "discover_tools" in names

    @pytest.mark.asyncio
    async def test_registration_order_does_not_matter(self, caplog) -> None:
        """Health-first ordering must be just as collision-free."""
        caplog.set_level(logging.WARNING)

        server = FastMCP(name="overlap-reversed")
        register_health_tools(server, server_name="overlap", version="1.0.0")
        register_baseline_tools(server)

        duplicates = [
            record.getMessage()
            for record in caplog.records
            if DUPLICATE_REGISTRATION_MESSAGE in record.getMessage()
        ]
        assert duplicates == [], f"tool names registered twice: {duplicates}"

        names = await _tool_names(server)
        for name in ("get_liveness", "get_readiness", "health_check_all"):
            assert names.count(name) == 1
        assert "discover_tools" in names

    @pytest.mark.asyncio
    async def test_baseline_alone_registers_no_health_tool(self) -> None:
        """The baseline module owns ``discover_tools`` and nothing else."""
        server = FastMCP(name="baseline-only")
        register_baseline_tools(server)

        names = await _tool_names(server)
        assert names == ["discover_tools"]


class TestHealthCheckServiceSchema:
    """The outer ``service_name`` leak must not reach the public schema."""

    @pytest.mark.asyncio
    async def test_schema_exposes_service_name(self) -> None:
        server = FastMCP(name="schema")
        register_health_tools(server, server_name="schema", version="1.0.0")

        tool = await _tool(server, "health_check_service")
        properties = tool.parameters["properties"]

        assert "service_name" in properties
        assert "service_name_arg" not in properties
        assert tool.parameters["required"] == ["service_name"]

    @pytest.mark.asyncio
    async def test_server_name_is_the_outer_parameter(self) -> None:
        """``server_name`` configures THIS server; the tool owns ``service_name``."""
        server = FastMCP(name="identity")
        register_health_tools(server, server_name="my-service", version="1.0.0")

        liveness = await _tool(server, "get_liveness")
        envelope = await liveness.fn()
        assert envelope["service"] == "my-service"

        service = await _tool(server, "health_check_service")
        assert "service_name" in service.parameters["properties"]


class TestDeprecatedTools:
    """The deprecation shim is driven by the ``deprecated_tools`` mapping."""

    @pytest.mark.asyncio
    async def test_mapped_tool_warns(self) -> None:
        server = FastMCP(name="deprecated")
        register_health_tools(
            server,
            server_name="deprecated",
            version="1.0.0",
            deprecated_tools={"health_check_all": "ecosystem_status"},
        )

        tool = await _tool(server, "health_check_all")
        with pytest.warns(DeprecationWarning, match="health_check_all is deprecated"):
            await tool.fn()

    @pytest.mark.asyncio
    async def test_unmapped_tool_does_not_warn(self) -> None:
        """Without a mapping, no tool warns."""
        server = FastMCP(name="not-deprecated")
        register_health_tools(server, server_name="not-deprecated", version="1.0.0")

        tool = await _tool(server, "health_check_all")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            await tool.fn()

        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert deprecations == []

    @pytest.mark.asyncio
    async def test_only_mapped_names_warn(self) -> None:
        """A mapping for one tool leaves the other five silent."""
        server = FastMCP(name="partial-deprecation")
        register_health_tools(
            server,
            server_name="partial-deprecation",
            version="1.0.0",
            deprecated_tools={"health_check_all": "ecosystem_status"},
        )

        unmapped = await _tool(server, "get_liveness")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            await unmapped.fn()

        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert deprecations == []

    @pytest.mark.asyncio
    async def test_deprecation_names_the_replacement(self) -> None:
        server = FastMCP(name="replacement")
        register_health_tools(
            server,
            server_name="replacement",
            version="1.0.0",
            deprecated_tools={"health_check_all": "ecosystem_status"},
        )

        tool = await _tool(server, "health_check_all")
        with pytest.warns(DeprecationWarning) as record:
            await tool.fn()

        messages = [str(w.message) for w in record]
        assert any(
            "health_check_all is deprecated" in m and "ecosystem_status" in m
            for m in messages
        ), messages


class TestLivenessState:
    """The liveness state API stays public; the state lives in health."""

    def test_public_import_paths_are_preserved(self) -> None:
        """Consumers import the liveness API from two paths - both work."""
        import mcp_common
        from mcp_common.baseline_tools import (
            LivenessContext as BaselineLivenessContext,
        )
        from mcp_common.baseline_tools import (
            get_liveness_context as baseline_get_liveness_context,
        )
        from mcp_common.baseline_tools import (
            seed_liveness_context as baseline_seed_liveness_context,
        )
        from mcp_common.health import LivenessContext as HealthLivenessContext
        from mcp_common.health import (
            get_liveness_context as health_get_liveness_context,
        )
        from mcp_common.health import (
            seed_liveness_context as health_seed_liveness_context,
        )

        # One implementation, re-exported - not a second copy.
        assert BaselineLivenessContext is HealthLivenessContext
        assert mcp_common.LivenessContext is HealthLivenessContext
        assert baseline_seed_liveness_context is health_seed_liveness_context
        assert mcp_common.seed_liveness_context is health_seed_liveness_context
        assert baseline_get_liveness_context is health_get_liveness_context
        assert mcp_common.get_liveness_context is health_get_liveness_context

    @pytest.mark.asyncio
    async def test_bootstrap_preserves_the_seeded_identity(self) -> None:
        """The consumer pattern (seed, then bootstrap) keeps the identity."""
        server = FastMCP(name="seeded")
        seed_liveness_context(
            service_name="seeded-service",
            version="9.9.9",
            start_time=time.time() - 5.0,
        )
        bootstrap_baseline_tools(server)

        tool = await _tool(server, "get_liveness")
        envelope = await tool.fn()

        assert envelope["service"] == "seeded-service"
        assert envelope["version"] == "9.9.9"
        assert envelope["uptime_seconds"] >= 5.0

    @pytest.mark.asyncio
    async def test_seed_after_registration_wins(self) -> None:
        """A lifespan-hook seed (after registration) is what is served."""
        server = FastMCP(name="late-seed")
        register_health_tools(server, server_name="registered-name", version="1.0.0")
        seed_liveness_context(service_name="late-seed", version="2.0.0")

        tool = await _tool(server, "get_liveness")
        envelope = await tool.fn()

        assert envelope["service"] == "late-seed"
        assert envelope["version"] == "2.0.0"

    @pytest.mark.asyncio
    async def test_registration_identity_is_served(self) -> None:
        """Without an explicit seed, the registration's identity is served."""
        server = FastMCP(name="registered")
        register_health_tools(server, server_name="registered-name", version="1.0.0")

        tool = await _tool(server, "get_liveness")
        envelope = await tool.fn()

        assert envelope["service"] == "registered-name"
        assert envelope["version"] == "1.0.0"


class TestBootstrapBaselineTools:
    """``bootstrap_baseline_tools`` still mounts the 4-name surface."""

    @pytest.mark.asyncio
    async def test_mounts_the_full_baseline_surface(self) -> None:
        from mcp_common.baseline_tools import BASELINE_TOOL_NAMES

        server = FastMCP(name="bootstrap")
        registered = bootstrap_baseline_tools(server)

        served = await _tool_names(server)
        for name in BASELINE_TOOL_NAMES:
            assert name in served, f"{name} missing from the bootstrap surface"
        assert registered == sorted(BASELINE_TOOL_NAMES)

    @pytest.mark.asyncio
    async def test_bootstrap_then_health_registers_each_name_once(self, caplog) -> None:
        """Session-Buddy's shape: bootstrap AND register_health_tools."""
        caplog.set_level(logging.WARNING)

        server = FastMCP(name="double-mount")
        bootstrap_baseline_tools(server)
        register_health_tools(server, server_name="double-mount", version="1.0.0")

        duplicates = [
            record.getMessage()
            for record in caplog.records
            if DUPLICATE_REGISTRATION_MESSAGE in record.getMessage()
        ]
        assert duplicates == [], f"tool names registered twice: {duplicates}"

        served = await _tool_names(server)
        for name in ("get_liveness", "get_readiness", "health_check_all"):
            assert served.count(name) == 1
