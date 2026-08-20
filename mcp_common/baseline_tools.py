"""Canonical baseline MCP tools for Bodai core servers.

Phase 1 of the Bodai MCP surface standardization plan (see
``docs/plans/2026-08-20-bodai-mcp-surface-standardization.md``)
establishes the 4-tool baseline that every Bodai core MCP server
exposes::

    - discover_tools(query | None) -> dict
    - get_liveness() -> {status, service, version, uptime}
    - get_readiness() -> dict
    - health_check_all() -> dict

This module provides a single registration function
``register_baseline_tools(server, ...)`` that wires all four tools onto
a FastMCP instance using the canonical envelope shapes. The shapes
mirror mahavishnu's reference implementation (see
``mahavishnu/mcp/server_core.py:discover_tools``) so drift across the
5 Bodai core servers is impossible - consumers and cross-server
regression tests can assert against a single source of truth.

The ``get_liveness`` tool reads its ``{start_time, service_name,
version}`` from a ``LivenessContext``. The context can be passed in
explicitly via the ``liveness_context`` parameter or seeded via
``seed_liveness_context(...)`` so lifespan hooks can populate it at
server boot.

Usage (typical)::

    from contextlib import asynccontextmanager
    from fastmcp import FastMCP
    from mcp_common.baseline_tools import register_baseline_tools

    @asynccontextmanager
    async def lifespan(server):
        from mcp_common.baseline_tools import seed_liveness_context
        seed_liveness_context(
            service_name="my-server",
            version="1.0.0",
            start_time=time.time(),
        )
        yield

    server = FastMCP(name="my-server", version="1.0.0", lifespan=lifespan)
    register_baseline_tools(server)

Or skip the lifespan wiring entirely - pass the context directly::

    from mcp_common.baseline_tools import (
        LivenessContext,
        register_baseline_tools,
    )
    register_baseline_tools(
        server,
        service_name="my-server",
        version="1.0.0",
        dependencies={"db": DependencyConfig(port=5432)},
    )

The ``ping`` tool is intentionally NOT registered here - that alias is
server-specific (see Phase 2 of the standardization plan: only
Session-Buddy needs the alias for its 3 confirmed callers).
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import typing as t
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastmcp import FastMCP
from fastmcp.tools import Tool

from mcp_common.health import (
    DependencyConfig,
    DependencyWaiter,
    HealthCheckResult,
    HealthChecker,
    HealthStatus,
)

logger = logging.getLogger(__name__)


# Canonical 4-tool baseline. Membership in this set is what
# `mcp_common.testing.assert_baseline_surface` (Phase 3) checks
# against. Do not rename a member without updating every Bodai core
# server that calls `register_baseline_tools`.
BASELINE_TOOL_NAMES: frozenset[str] = frozenset(
    {"discover_tools", "get_liveness", "get_readiness", "health_check_all"}
)


@dataclass
class LivenessContext:
    """Process-level state required by the ``get_liveness`` tool.

    Attributes:
        start_time: Unix timestamp (from ``time.time()``) marking
            when the server started.
        service_name: Human-readable service identifier (e.g.
            ``"mahavishnu"``, ``"session-buddy"``).
        version: Service version string.

    A module-level singleton of this dataclass is mutated by
    ``seed_liveness_context`` so that the FastMCP ``get_liveness`` tool
    closure always reads the freshest values without requiring a
    reference to the server object.
    """

    start_time: float = field(default_factory=time.time)
    service_name: str = "mcp-server"
    version: str = "0.0.0"

    def uptime_seconds(self) -> float:
        """Return seconds elapsed since ``start_time``."""
        return max(0.0, time.time() - self.start_time)


# Module-level singleton. Lock protects concurrent seeding from a
# lifespan hook plus a fallback ``register_baseline_tools`` call.
_LIVENESS_LOCK = threading.Lock()
_LIVENESS_CONTEXT = LivenessContext()


def get_liveness_context() -> LivenessContext:
    """Return the current module-level ``LivenessContext``.

    Returns:
        The singleton. May be the seeded-at-import default if
        ``seed_liveness_context`` has not been called.
    """
    with _LIVENESS_LOCK:
        return _LIVENESS_CONTEXT


def seed_liveness_context(
    *,
    service_name: str,
    version: str,
    start_time: float | None = None,
) -> LivenessContext:
    """Seed the module-level ``LivenessContext`` for ``get_liveness``.

    Intended to be called from a FastMCP lifespan hook at server boot.
    Subsequent calls overwrite the singleton - useful for tests that
    reset the start time between scenarios.

    Args:
        service_name: Service identifier written into the
            ``get_liveness`` envelope.
        version: Version string written into the ``get_liveness``
            envelope.
        start_time: Optional Unix timestamp. Defaults to ``time.time()``
            at call time.

    Returns:
        The seeded context, so lifespan hooks can capture and yield it
        if desired.
    """
    if start_time is None:
        start_time = time.time()

    with _LIVENESS_LOCK:
        global _LIVENESS_CONTEXT
        _LIVENESS_CONTEXT = LivenessContext(
            start_time=start_time,
            service_name=service_name,
            version=version,
        )
        seeded = _LIVENESS_CONTEXT

    logger.info(
        "Seeded LivenessContext service=%s version=%s start_time=%.3f",
        service_name,
        version,
        start_time,
    )
    return seeded


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
    Session-Buddy and Dhara use.

    Args:
        server: The FastMCP server instance to introspect.
        query: Optional substring filter applied to tool names.
        capability: Optional capability gate. When ``"ready"``,
            include the routable-worker snapshot from
            ``mcp_common.health.DependencyConfig`` if available. Most
            Bodai core servers ignore this for now.
        known_tool_names: Optional pre-known set. If ``None``, we use
            the currently registered tools as the "known" universe -
            this keeps lean servers (Dhara) honest without forcing
            them to maintain a static registry.

    Returns:
        Canonical envelope dict.
    """
    try:
        registered_names = {t.name for t in await server.list_tools()}
    except (RuntimeError, AttributeError, ValueError, TypeError) as e:
        logger.exception("discover_tools: server.list_tools failed")
        registered_names = set()

    all_known = set(known_tool_names) if known_tool_names else set(registered_names)

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
            "Set `capability=\"ready\"` to include the routable-worker "
            "snapshot (only meaningful when this server manages workers)."
        ),
    }

    return response


async def _baseline_get_liveness() -> dict[str, t.Any]:
    """Canonical ``get_liveness`` implementation.

    Reads the seeded ``LivenessContext`` so lifespan hooks are the
    single source of truth for service identity and start time.
    """
    ctx = get_liveness_context()
    return {
        "status": "ok",
        "service": ctx.service_name,
        "version": ctx.version,
        "uptime_seconds": round(ctx.uptime_seconds(), 2),
    }


async def _baseline_get_readiness(
    *,
    dependencies: dict[str, DependencyConfig],
    waiter: DependencyWaiter | None,
) -> dict[str, t.Any]:
    """Canonical ``get_readiness`` implementation.

    Mirrors ``mcp_common.health.register_health_tools.get_readiness``
    but is callable without an enclosing FastMCP server, so it can be
    unit-tested in isolation.

    Args:
        dependencies: Configured dependency map. Empty map yields
            ``ready=True``.
        waiter: Optional pre-built ``DependencyWaiter``. If ``None``,
            we construct one with defaults.
    """
    if not dependencies:
        return {
            "ready": True,
            "checks": {"process": "ok"},
        }

    actual_waiter = waiter or DependencyWaiter()
    result = await actual_waiter.wait_for_all(dependencies)

    checks: dict[str, str] = {"process": "ok"}
    checks.update(
        {
            name: dep_result.status.value
            for name, dep_result in result.dependencies.items()
        }
    )

    return {
        "ready": result.success,
        "checks": checks,
        "failed_required": result.failed_required,
    }


async def _baseline_health_check_all(
    *,
    dependencies: dict[str, DependencyConfig],
    checker: HealthChecker | None,
) -> dict[str, t.Any]:
    """Canonical ``health_check_all`` implementation.

    Mirrors ``mcp_common.health.register_health_tools.health_check_all``
    but is callable without an enclosing FastMCP server, so it can be
    unit-tested in isolation.
    """
    if not dependencies:
        return {
            "status": HealthStatus.HEALTHY.value,
            "services": {},
            "total_services": 0,
            "healthy_services": 0,
            "message": "No dependencies configured",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    actual_checker = checker or HealthChecker()

    tasks = {
        name: actual_checker.check(config.to_url(), service_name=name)
        for name, config in dependencies.items()
    }

    results: dict[str, dict[str, t.Any]] = {}
    if tasks:
        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for (name, _), result in zip(tasks.items(), gathered):
            if isinstance(result, BaseException):
                results[name] = {
                    "status": HealthStatus.UNHEALTHY.value,
                    "error": str(result),
                }
            else:
                results[name] = t.cast(HealthCheckResult, result).to_dict()

    all_ok = all(
        r.get("status")
        in (HealthStatus.HEALTHY.value, HealthStatus.DEGRADED.value)
        for r in results.values()
    )

    return {
        "status": HealthStatus.HEALTHY.value
        if all_ok
        else HealthStatus.UNHEALTHY.value,
        "services": results,
        "total_services": len(results),
        "healthy_services": sum(
            1
            for r in results.values()
            if r.get("status") == HealthStatus.HEALTHY.value
        ),
        "timestamp": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Public registration entrypoint.
# ---------------------------------------------------------------------------


def register_baseline_tools(  # noqa: C901 - intentional multi-tool wiring
    server: FastMCP,
    *,
    service_name: str | None = None,
    version: str | None = None,
    start_time: float | None = None,
    dependencies: dict[str, DependencyConfig] | None = None,
    liveness_context: LivenessContext | None = None,
    known_tool_names: set[str] | None = None,
) -> None:
    """Register the 4 canonical baseline tools on a FastMCP server.

    This is the single entrypoint every Bodai core server calls at
    boot. It wires::

        - discover_tools(query, capability) - canonical envelope
        - get_liveness() - reads LivenessContext (seeded or passed)
        - get_readiness() - delegates to DependencyWaiter
        - health_check_all() - delegates to HealthChecker

    Args:
        server: The FastMCP server to register on.
        service_name: Optional service name. If supplied (along with
            ``version``) and no ``liveness_context`` is passed,
            ``seed_liveness_context`` is called so ``get_liveness``
            returns the right values.
        version: Optional version string. See ``service_name``.
        start_time: Optional Unix timestamp. Defaults to ``time.time()``
            at call time. Ignored when ``liveness_context`` is passed.
        dependencies: Optional map of dependency name -> config. If
            ``None``, ``get_readiness`` and ``health_check_all`` report
            ready/healthy unconditionally. Pass ``{}`` explicitly to
            register the tools but skip dependency checks.
        liveness_context: Optional pre-built ``LivenessContext``. Wins
            over the ``service_name``/``version``/``start_time``
            kwargs. Use this when lifespan hooks already seeded the
            singleton.
        known_tool_names: Optional pre-known tool universe for
            ``discover_tools``. Defaults to "currently registered
            tools" which is the lean shape used by Dhara.

    Raises:
        TypeError: If ``server`` does not expose ``tool()`` and
            ``add_tool()``. We validate up-front so callers see a
            clear error rather than a confusing FastMCP stack trace.

    Example::

        >>> from fastmcp import FastMCP
        >>> from mcp_common.baseline_tools import register_baseline_tools
        >>> server = FastMCP(name="demo", version="0.1.0")
        >>> register_baseline_tools(server, service_name="demo", version="0.1.0")
    """
    if not hasattr(server, "tool") or not hasattr(server, "add_tool"):
        raise TypeError(
            "register_baseline_tools requires a FastMCP-like server "
            "(with .tool() and .add_tool()). Got: "
            f"{type(server).__module__}.{type(server).__name__}"
        )

    deps = dependencies if dependencies is not None else {}
    checker = HealthChecker()
    waiter = DependencyWaiter()

    # Seed the singleton when the caller passed identity kwargs but
    # no explicit context. FastMCP server boot is the typical path -
    # the lifespan hook has already started, so we update here too.
    if liveness_context is not None:
        with _LIVENESS_LOCK:
            global _LIVENESS_CONTEXT
            _LIVENESS_CONTEXT = liveness_context
    elif service_name is not None or version is not None or start_time is not None:
        seed_liveness_context(
            service_name=service_name or "mcp-server",
            version=version or "0.0.0",
            start_time=start_time,
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

    # ----- get_liveness / get_readiness / health_check_all -----------
    # These three use mcp.tool() because they don't need the explicit
    # Tool.from_function wrapper - the closure captures the resolved
    # dependencies, checker, and waiter references, which is exactly
    # the same shape mcp_common.health.register_health_tools uses.

    @server.tool()  # type: ignore[untyped-decorator]
    async def get_liveness() -> dict[str, t.Any]:
        """Get liveness status for this service.

        Returns:
            Dict with ``status`` (``"ok"``), ``service`` (the seeded
            service name), ``version`` (the seeded version), and
            ``uptime_seconds`` (computed from the seeded start time).
        """
        return await _baseline_get_liveness()

    @server.tool()  # type: ignore[untyped-decorator]
    async def get_readiness() -> dict[str, t.Any]:
        """Get readiness status for this service.

        Returns:
            Dict with ``ready`` (bool), ``checks`` (per-dependency
            status map), and ``failed_required`` (list of dependency
            names that did not become healthy).
        """
        return await _baseline_get_readiness(dependencies=deps, waiter=waiter)

    @server.tool()  # type: ignore[untyped-decorator]
    async def health_check_all() -> dict[str, t.Any]:
        """Check health of all configured dependencies.

        Returns:
            Dict with ``status`` (``"healthy"`` | ``"unhealthy"``),
            ``services`` (per-dependency dict), ``total_services``,
            ``healthy_services``, and an ISO timestamp.
        """
        return await _baseline_health_check_all(dependencies=deps, checker=checker)


__all__ = [
    "BASELINE_TOOL_NAMES",
    "LivenessContext",
    "get_liveness_context",
    "register_baseline_tools",
    "seed_liveness_context",
]