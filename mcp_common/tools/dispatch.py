"""Apply ToolProfile gating to a FastMCP server at startup.

Verified against FastMCP 3.4.7 — uses public API only:
- await server.list_tools()  (NOT _tool_manager.list_tools())
- Tool.from_function(...) for registering the discover_tools meta-tool
- server._local_provider.remove_tool() for idempotent removal
- Tool.parameters for inputSchema dict

Supports 4 dispatch modes (see spec §Components §1):
- callable-only (typical Tier-A)
- decorator-mode (Tier-A edge — repos using @mcp.tool decorators)
- method-mode (mahavishnu's `_register_<group>()` pattern)
- single-group (Tier-B simple case)

Public API:
- apply_tool_profile(server, ...) - main entrypoint
- ALL_TOOLS - typed sentinel for ToolProfile.FULL = "register everything"
- InvalidProfileError - raised on SET-BUT-INVALID env var (NOT on unset)
"""

from __future__ import annotations

import asyncio
import inspect
import os
from collections.abc import Awaitable, Callable

from fastmcp import FastMCP
from fastmcp.tools import Tool
from oneiric.core.logging import get_logger

from mcp_common.tools.profiles import MANDATORY_GROUPS, MANDATORY_TOOLS, ToolProfile

logger = get_logger(__name__)


class ALL_TOOLS:
    """Typed sentinel marking `ToolProfile.FULL` to register every group.

    Using a class (not a string) prevents accidental collision with a
    legit group named "all_tools".
    """


class InvalidProfileError(Exception):
    """Raised when {SERVER}_TOOL_PROFILE is SET-BUT-INVALID (empty/whitespace/unknown).

    Per spec: UNSET env var falls through to FULL (matches existing from_env behavior).
    """


def _resolve_profile(
    profile_env_var: str, yaml_loader: Callable[[], dict | None] | None
) -> ToolProfile:
    """Resolve profile from env var (UNSET → yaml_loader → FULL fallback).

    Raises InvalidProfileError ONLY on SET-BUT-INVALID values.
    """
    raw = os.getenv(profile_env_var)
    if raw is None:
        # Env var unset — try YAML fallback
        if yaml_loader is not None:
            try:
                loaded = yaml_loader() or {}
                raw = str(loaded.get("tool_profile", "") or "")
            except Exception:  # noqa: BLE001
                raw = ""
        if raw is None or not raw:
            # No env, no yaml, no usable value — DEFAULT to FULL (per spec + existing from_env)
            return ToolProfile.FULL
    # Env var IS set (or yaml provided one) — validate it
    candidate = raw.strip().lower()
    if not candidate:
        raise InvalidProfileError(
            f"{profile_env_var}={raw!r} is empty or whitespace; expected one of "
            f"{[p.value for p in ToolProfile]}"
        )
    try:
        return ToolProfile(candidate)
    except ValueError as e:
        raise InvalidProfileError(
            f"{profile_env_var}={raw!r} is not a valid profile; "
            f"expected one of {[p.value for p in ToolProfile]}"
        ) from e


async def _maybe_await(result: Awaitable[None] | None) -> None:
    """Await if coroutine, else ignore."""
    if inspect.iscoroutine(result):
        await result


async def _default_discovery(server: FastMCP, filter_query: str | None) -> list[dict]:
    """Default introspection via the FastMCP PUBLIC `list_tools()` method.

    Verified FastMCP 3.4.7: Tool.model_fields contains 'parameters' (not 'inputSchema').
    inputSchema only exists after Tool.to_mcp_tool() conversion.
    """
    tools = await server.list_tools()
    result: list[dict[str, object]] = [
        {
            "name": t.name,
            "description": t.description or "",
            "inputSchema": t.parameters,  # parameters is the underlying dict
            "group": None,
        }
        for t in tools
    ]
    if filter_query:
        q = filter_query.lower()
        result = [
            t
            for t in result
            if q in str(t["name"]).lower() or q in str(t["description"]).lower()
        ]
    return result


async def _select_profile_groups(
    server: FastMCP,
    profile: ToolProfile,
    registrations: dict[ToolProfile, list[str | Callable] | type[ALL_TOOLS]],
    register_all_fn: Callable[[FastMCP], Awaitable[None] | None] | None,
) -> list[str | Callable]:
    """Resolve the list of (callable | group-name) registrations for the active profile.

    FULL + ALL_TOOLS short-circuits to ``register_all_fn``; FULL with a list
    returns that list; missing/empty registrations fall back to an empty list.
    """
    if profile is ToolProfile.MINIMAL:
        return registrations.get(ToolProfile.MINIMAL, [])
    if profile is ToolProfile.STANDARD:
        return registrations.get(ToolProfile.STANDARD, [])
    # ToolProfile.FULL
    full_value = registrations.get(ToolProfile.FULL)
    if full_value is ALL_TOOLS:
        if register_all_fn is None:
            raise ValueError(
                "register_all_fn must be provided when registrations[FULL] is ALL_TOOLS"
            )
        await _maybe_await(register_all_fn(server))
        return []
    if isinstance(full_value, list):
        return full_value
    return []


async def _apply_tool_profile_async(
    server: FastMCP,
    *,
    profile: ToolProfile,
    registrations: dict[ToolProfile, list[str | Callable] | type[ALL_TOOLS]],
    registration_map: dict[str, Callable[[FastMCP], Awaitable[None] | None]],
    register_all_fn: Callable[[FastMCP], Awaitable[None] | None] | None,
    mandatory_groups: set[str],
    essential_tool_names: set[str],
    discovery_fn: Callable[[FastMCP, str | None], Awaitable[list[dict]]] | None,
    profile_env_var: str,
) -> None:
    """Async implementation of apply_tool_profile.

    Sync validation happens in apply_tool_profile() before this is called.

    `mandatory_groups` is a set of registration_map keys; the helper runs each
    group's registration fn post-pass (so always-on groups are guaranteed at
    every profile). `essential_tool_names` is a subset check — it asserts that
    these tool names are present after dispatch, but does NOT drive registration.
    Set `essential_tool_names=set()` to opt out of the subset check.
    """
    # Step 1: Per-profile registration
    groups: list[str | Callable] = await _select_profile_groups(
        server, profile, registrations, register_all_fn
    )

    for item in groups:  # ty: ignore[not-iterable]
        if callable(item):
            await _maybe_await(item(server))  # ty: ignore[call-top-callable, invalid-argument-type]
        elif isinstance(item, str):
            fn = registration_map.get(item)
            if fn is None:
                raise ValueError(
                    f"Group {item!r} in registrations but not in registration_map. "
                    f"Add it via registration_map[{item!r}] = <register function>."
                )
            await _maybe_await(fn(server))
        else:
            raise TypeError(
                f"registrations values must be str, Callable, or ALL_TOOLS; got {type(item)}"
            )

    # Step 2a: MANDATORY groups (registration_map keys registered at every profile).
    # Walked AFTER per-profile registration so always-on groups are guaranteed
    # even if MINIMAL/STANDARD drops them. Per-group idempotency: refresh
    # registered_names after each call so re-registration is safe.
    registered_names = {t.name for t in await server.list_tools()}
    for group_name in mandatory_groups:
        fn = registration_map.get(group_name)
        if fn is None:
            raise ValueError(
                f"MANDATORY group {group_name!r} not in registration_map. "
                f"Add it or pass mandatory_groups=set() to skip."
            )
        await _maybe_await(fn(server))
        registered_names = {t.name for t in await server.list_tools()}

    # Step 2b: ESSENTIAL tool names (subset check — NOT a dispatch driver).
    # Asserts these tool names are present after Steps 1+2a. Repos opt-out
    # via essential_tool_names=set(). Failures here mean a registration_map
    # key was missing from the profile's registrations OR mandatory_groups.
    if essential_tool_names:
        registered_names = {t.name for t in await server.list_tools()}
        missing = essential_tool_names - registered_names
        if missing:
            raise ValueError(
                f"ESSENTIAL tool names {sorted(missing)!r} not registered after "
                f"profile application. Verify the appropriate groups are in "
                f"registrations or mandatory_groups."
            )

    # Step 3: discover_tools() (idempotent via _local_provider.remove_tool)
    disc = discovery_fn or _default_discovery
    await disc(server, None)

    # Remove existing discover_tools if present (use _local_provider, the FastMCP 3.4+ public attr)
    try:
        server._local_provider.remove_tool("discover_tools")  # type: ignore[attr-defined]
    except (KeyError, AttributeError, ValueError) as e:
        logger.debug("No existing discover_tools to remove (%s); registering fresh", e)

    # Register discover_tools via Tool.from_function (the only correct way in FastMCP 3.4+)
    async def discover_tools_handler(query: str | None = None) -> list[dict]:
        """List tools registered in this server, optionally filtered by query."""
        return await disc(server, query)

    discover_tool = Tool.from_function(
        fn=discover_tools_handler,
        name="discover_tools",
        description="List all tools registered in this server (with profile metadata).",
    )
    server.add_tool(discover_tool)

    n = len(await server.list_tools())
    logger.info(
        "Applied %s=%s → %d tools registered",
        profile_env_var,
        profile.value,
        n,
    )


def apply_tool_profile(
    server: FastMCP,
    *,
    profile_env_var: str,
    registrations: dict[ToolProfile, list[str | Callable] | type[ALL_TOOLS]],
    registration_map: dict[str, Callable[[FastMCP], Awaitable[None] | None]],
    register_all_fn: Callable[[FastMCP], Awaitable[None] | None] | None = None,
    mandatory_groups: set[str] = MANDATORY_GROUPS,
    essential_tool_names: set[str] = MANDATORY_TOOLS,
    mandatory_tools: set[str] | None = None,
    discovery_fn: Callable[[FastMCP, str | None], Awaitable[list[dict]]] | None = None,
    yaml_loader: Callable[[], dict | None] | None = None,
) -> None:
    """Apply the tool profile to the server at startup. See module docstring.

    Sync entrypoint: runs the async implementation via ``asyncio.run()``.
    Works from synchronous contexts (module import, CLI startup, unit tests).
    For async contexts (e.g. inside another ``async def``), use the
    ``_apply_tool_profile_async`` helper directly.

    Sync validation (InvalidProfileError, ValueError) raise immediately.
    Passing ``server=None`` skips the async registration phase; this is the
    convention used by unit tests that only exercise the resolver/validation.

    `mandatory_tools` is a deprecated alias for `mandatory_groups` (the
    pre-W0.5 code conflated the two concepts). Existing callers can pass
    `mandatory_tools=...` and it will be treated as a set of registration_map
    keys; new code should use `mandatory_groups` (dispatch driver) and
    `essential_tool_names` (subset check) separately.
    """
    # Deprecated alias handling
    if mandatory_tools is not None:
        import warnings

        warnings.warn(
            "mandatory_tools is deprecated; use mandatory_groups (for "
            "registration_map keys) and essential_tool_names (for subset "
            "checks) separately.",
            DeprecationWarning,
            stacklevel=2,
        )
        mandatory_groups = mandatory_tools

    # Sync validation phase
    profile = _resolve_profile(profile_env_var, yaml_loader)
    full_value = registrations.get(ToolProfile.FULL)
    if full_value is ALL_TOOLS and register_all_fn is None:
        raise ValueError(
            "ToolProfile.FULL == ALL_TOOLS requires register_all_fn; "
            "either pass it or set registrations[FULL] to a list of group names."
        )

    # If no server is provided, validation has already passed.
    # This is the convention used by unit tests that only exercise the
    # resolver/validation phase. Integration tests always pass a real server.
    if server is None:
        return

    # From a sync context, asyncio.run() spins a fresh loop and runs the
    # coroutine to completion. From an async context, raise so callers
    # can switch to the async helper.
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(
            _apply_tool_profile_async(
                server,
                profile=profile,
                registrations=registrations,
                registration_map=registration_map,
                register_all_fn=register_all_fn,
                mandatory_groups=mandatory_groups,
                essential_tool_names=essential_tool_names,
                discovery_fn=discovery_fn,
                profile_env_var=profile_env_var,
            )
        )
    else:
        raise RuntimeError(
            "apply_tool_profile() was called from within a running event loop. "
            "Use 'await _apply_tool_profile_async(...)' instead."
        )


async def _apply_tool_profile(
    server: FastMCP,
    *,
    profile_env_var: str,
    registrations: dict[ToolProfile, list[str | Callable] | type[ALL_TOOLS]],
    registration_map: dict[str, Callable[[FastMCP], Awaitable[None] | None]],
    register_all_fn: Callable[[FastMCP], Awaitable[None] | None] | None = None,
    mandatory_groups: set[str] = MANDATORY_GROUPS,
    essential_tool_names: set[str] = MANDATORY_TOOLS,
    mandatory_tools: set[str] | None = None,
    discovery_fn: Callable[[FastMCP, str | None], Awaitable[list[dict]]] | None = None,
    yaml_loader: Callable[[], dict | None] | None = None,
) -> None:
    """Async entrypoint for apply_tool_profile.

    Use this when calling from inside an existing event loop (e.g. async
    integration tests). The sync ``apply_tool_profile()`` wrapper raises
    in that case.

    `mandatory_tools` is a deprecated alias for `mandatory_groups`. See
    the sync `apply_tool_profile()` docstring for migration guidance.
    """
    if mandatory_tools is not None:
        import warnings

        warnings.warn(
            "mandatory_tools is deprecated; use mandatory_groups (for "
            "registration_map keys) and essential_tool_names (for subset "
            "checks) separately.",
            DeprecationWarning,
            stacklevel=2,
        )
        mandatory_groups = mandatory_tools

    profile = _resolve_profile(profile_env_var, yaml_loader)
    full_value = registrations.get(ToolProfile.FULL)
    if full_value is ALL_TOOLS and register_all_fn is None:
        raise ValueError(
            "ToolProfile.FULL == ALL_TOOLS requires register_all_fn; "
            "either pass it or set registrations[FULL] to a list of group names."
        )
    if server is None:
        return
    await _apply_tool_profile_async(
        server,
        profile=profile,
        registrations=registrations,
        registration_map=registration_map,
        register_all_fn=register_all_fn,
        mandatory_groups=mandatory_groups,
        essential_tool_names=essential_tool_names,
        discovery_fn=discovery_fn,
        profile_env_var=profile_env_var,
    )
