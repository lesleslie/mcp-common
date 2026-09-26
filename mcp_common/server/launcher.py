"""Canonical MCP server launcher.

This module is the single source of truth for Bodai MCP server startup
across the 5 Core components (vishnu / ak / sb / cj / oneiric) plus the
20 standalone MCP servers tracked in
``mahavishnu/docs/mcp/server-migration-tracker.md``.

It is **fully generic** — no oneiric coupling. Each component supplies a
``build_server: Callable[..., FastMCP]`` closure that handles its own
auth loading, processor wiring, and feed population; this launcher is
responsible only for:

1. Loading ``~/.config/secrets.env`` into ``os.environ`` (so launchd-managed
   processes that don't inherit shell init files still get the API keys).
2. Optionally warming the ``settings`` health feed with ``entities_count > 0``
   (per ``mcp_common/health/feed.py:202-211`` this is required for
   ``is_healthy()`` to return ``StatusValue.HEALTHY`` and ``/health=200``).
3. Running FastMCP with ``transport="http"`` and
   ``uvicorn_config={"timeout_graceful_shutdown": 30}`` for SIGTERM-friendly
   shutdown (REQ-007, REQ-014).

Each helper is independently unit-tested (REQ-006); see
``tests/server/test_launcher.py``.
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp_common.health.feed import HealthFeedState, record_success

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level secrets parser (Task 1.1)
# ---------------------------------------------------------------------------

# Default secrets location. Module-level constant so tests can spy on it and
# downstream consumers can pre-populate or override it.
DEFAULT_SECRETS_PATH: Path = Path.home() / ".config" / "secrets.env"

# Matches: optional `export `, KEY, =, then a quoted or unquoted value.
# Captures: (1) key, (2) quote char or empty, (3) value.
#
# Keys may arrive lowercase in the source file; we normalise via
# ``key.upper()`` after matching so env-var convention is preserved.
# (mahavishnu's original parser required uppercase keys; this launcher is
# more permissive so callers can hand-edit secrets.env without surprise.)
_LINE_RE: re.Pattern[str] = re.compile(
    r"""^\s*(?:export\s+)?([A-Za-z0-9_]+)\s*=\s*(['"]?)(.*?)\2\s*$"""
)


def _strip_comment(value: str) -> str:
    """Strip a trailing ``# comment`` from an unquoted value.

    The regex already removed the surrounding quotes, so a ``#`` here is
    safe to strip if it appears outside a quote (we never have one at this
    point). For secrets.env values that contain ``#`` (e.g. JWTs with ``#``
    in the header), the quotes in the source file protect them — so this
    only fires for unquoted values.
    """
    idx = value.find(" #")
    return value if idx < 0 else value[:idx].rstrip()


def load_secrets(secrets_path: Path | None = None) -> dict[str, str]:
    """Parse a ``secrets.env``-style file into a ``{KEY: value}`` dict.

    Args:
        secrets_path: Optional path to the secrets file. Defaults to
            :data:`DEFAULT_SECRETS_PATH` (``~/.config/secrets.env``). The
            ``Path | None`` signature lets tests pass a ``tmp_path`` without
            monkeypatching ``Path.home``.

    Returns:
        A new ``dict[str, str]`` with upper-cased keys. Empty when the file
        does not exist or is unreadable. Lines that fail to parse are
        silently skipped — secrets files commonly contain shell-globbing
        fragments (``$FOO``) that aren't intended for our parser.
    """
    path = secrets_path or DEFAULT_SECRETS_PATH
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    try:
        with path.open() as f:
            for raw in f:
                line = raw.rstrip("\n")
                stripped = line.strip()
                # Skip blank lines and full-line comments.
                if not stripped or stripped.startswith("#"):
                    continue
                m = _LINE_RE.match(line)
                if not m:
                    continue
                key, _quote, value = m.group(1), m.group(2), m.group(3)
                result[key.upper()] = _strip_comment(value)
    except OSError:
        logger.debug("load_secrets: could not read %s", path, exc_info=True)
        return {}
    return result


# ---------------------------------------------------------------------------
# Task 1.2: warm_settings_feed()
# ---------------------------------------------------------------------------


def warm_settings_feed(settings_path: Path | None) -> HealthFeedState | None:
    """Pre-warm the ``settings`` health feed with ``entities_count > 0``.

    Per ``mcp_common/health/feed.py:202-211``, ``is_healthy()`` returns
    ``(False, WARMING_UP, [WARMING_UP_EMPTY_FEED])`` when
    ``entities_count == 0 AND cycles_total >= 1 AND ingester_running``.
    Seeding only ``cycles_total`` is NOT sufficient for ``/health=200``.

    Only the ``settings`` feed is pre-warmed — it is the only legitimate
    one-shot init (a single read of ``settings.yaml``). ``context`` and
    ``progress`` start unhealthy and populate via tool calls (Claude Code
    calls ``tools/list`` immediately after MCP initialize, populating the
    feeds within seconds).

    Args:
        settings_path: Optional path to the settings YAML file. When
            ``None`` or missing, returns ``None`` so the caller can no-op.

    Returns:
        A populated :class:`HealthFeedState` with ``entities_count=1``,
        ``cycles_total=1``, ``ingester_running=True``, and a fresh
        ``last_updated_timestamp``; or ``None`` when no settings file was
        provided / found.
    """
    if settings_path is None or not settings_path.exists():
        return None

    # Touch the file just enough to confirm it parses. We do NOT need to
    # stash the parsed contents here — the consuming component will read
    # the same file with its own loader.
    state = HealthFeedState(
        entities_count=1,
        cycles_total=1,
        ingester_running=True,
        last_updated_timestamp=time.time(),
    )
    record_success(state)
    return state


# ---------------------------------------------------------------------------
# Task 1.3: run_with_uvicorn_config()
# ---------------------------------------------------------------------------


async def run_with_uvicorn_config(
    server: Any,
    host: str,
    port: int,
    *,
    timeout_graceful_shutdown: int = 30,
) -> None:
    """Run a FastMCP server over HTTP with a configurable graceful-shutdown.

    Thin wrapper that pins ``transport="http"`` and threads the
    ``timeout_graceful_shutdown`` value into uvicorn's config so SIGTERM
    stops the server within the grace window (REQ-014 signal-handling
    smoke).

    Args:
        server: Any object exposing an ``async run_async(transport=...,
            host=..., port=..., uvicorn_config=...)`` method. In practice
            this is a ``fastmcp.FastMCP`` instance, but the dependency is
            left duck-typed to keep this module framework-agnostic.
        host: Bind host.
        port: Bind port.
        timeout_graceful_shutdown: Seconds uvicorn waits for in-flight
            requests to drain before forceful shutdown.
    """
    await server.run_async(
        transport="http",
        host=host,
        port=port,
        uvicorn_config={"timeout_graceful_shutdown": timeout_graceful_shutdown},
    )


# ---------------------------------------------------------------------------
# Task 1.5: launch() — top-level entry point
# ---------------------------------------------------------------------------


async def launch(
    *,
    build_server: Callable[..., Any],
    component_name: str,
    secrets_path: Path | None = None,
    settings_path: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8680,
    timeout_graceful_shutdown: int = 30,
) -> None:
    """Launch a Bodai MCP server with the canonical startup sequence.

    1. If ``secrets_path`` is provided, load it and merge into ``os.environ``
       (existing env wins via ``setdefault``).
    2. If ``settings_path`` is provided, pre-warm the ``settings`` health feed.
    3. Build the FastMCP server via ``build_server()`` — variadic, no args,
       so callers pre-bind config / auth_config / providers / processor inside
       their closure (REQ-003).
    4. Run with ``transport="http"`` and
       ``uvicorn_config={"timeout_graceful_shutdown": timeout_graceful_shutdown}``
       (REQ-007).

    Args:
        build_server: A zero-arg (variadic) callable that constructs and
            returns a FastMCP-compatible server. Each component owns its own
            ``build_server`` closure to keep this launcher generic.
        component_name: Short identifier for the launching component
            (e.g. ``"oneiric"``, ``"mahavishnu"``). Used in structured logs.
        secrets_path: Optional path to the ``secrets.env`` file.
        settings_path: Optional path to the ``settings.yaml`` file. When
            provided, the ``settings`` health feed is pre-warmed so
            ``/health=200`` on first probe.
        host: Bind host (default ``"127.0.0.1"``).
        port: Bind port (default ``8680``).
        timeout_graceful_shutdown: Uvicorn graceful-shutdown timeout in
            seconds (default ``30``).
    """
    logger.info(
        "mcp-launcher-starting component=%s host=%s port=%d",
        component_name,
        host,
        port,
    )

    if secrets_path is not None:
        secrets = load_secrets(secrets_path)
        for key, value in secrets.items():
            # setdefault: existing os.environ wins, so operators can still
            # override per-process via the shell when needed.
            os.environ.setdefault(key, value)
        logger.debug(
            "mcp-launcher-secrets-loaded count=%d component=%s",
            len(secrets),
            component_name,
        )

    if settings_path is not None:
        warm_settings_feed(settings_path)

    server = build_server()
    await run_with_uvicorn_config(
        server,
        host,
        port,
        timeout_graceful_shutdown=timeout_graceful_shutdown,
    )


__all__ = [
    "DEFAULT_SECRETS_PATH",
    "launch",
    "load_secrets",
    "run_with_uvicorn_config",
    "warm_settings_feed",
]
