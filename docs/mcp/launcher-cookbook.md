---
title: MCP Launcher Cookbook
status: active
role: reference
kind: migration-guide
date: 2026-09-26
last_reviewed: 2026-09-26
superseded_by: null
topic: mcp-launcher-migration
---

# MCP Launcher Cookbook

> **Migration patterns for `mcp_common.server.launcher.launch()`** (mcp-common 0.28.0+).
>
> Companion to `docs/plans/2026-09-26-mcp-launcher-standardization.md` in mahavishnu.
> Source: `mcp_common/server/launcher.py`; tests: `tests/server/test_launcher.py`.

## Why

Five Bespoke startup shapes (each repo reinventing secrets loading, transport selection, uvicorn grace timeout, and the `settings`-feed warm-up) collapse into one canonical `launch()` helper. Each repo contributes a 5–25 LOC `scripts/launch_mcp*.py` wrapper that supplies a `build_server` closure; the launcher handles the rest. After this lands, adding a new Bodai-managed MCP server means writing one closure — not re-implementing the launch sequence and discovering each wart (stdio-vs-http, 2-second uvicorn grace, feed warming that lies about data flow) independently.

## What the launcher gives you for free

The launcher is fully generic — no oneiric coupling — but it gives every consumer the same six guarantees:

| # | Concern | Handled by | REQ |
|---|---|---|---|
| 1 | Load `~/.config/secrets.env` into `os.environ` (so launchd-managed processes that don't inherit shell init files still get API keys) | `launcher.load_secrets()` | REQ-002 |
| 2 | Run FastMCP with `transport="http"` (so `host`/`port` aren't rejected as unexpected kwargs against the stdio default) | `launcher.run_with_uvicorn_config()` | REQ-007 |
| 3 | Pass `uvicorn_config={"timeout_graceful_shutdown": 30}` (SIGTERM stops the server within the grace window) | `launcher.run_with_uvicorn_config()` | REQ-007, REQ-014 |
| 4 | Pre-warm **only** the `settings` health feed with `entities_count > 0` (so `/health=200` on first probe; `context`/`progress` start unhealthy and populate via tool calls) | `launcher.warm_settings_feed()` | REQ-004 |
| 5 | Variadic `build_server: Callable[..., Any]` signature (so oneiric's 6-kwarg `build_mcp_server` works without unpacking) | `launcher.launch()` | REQ-003 |
| 6 | Expose `"launcher": "mcp_common.server.launcher@<version>"` in the `/health` body (incident triage: grep tells you which launcher build served the request) | consumer's `/health` route | REQ-005 |

A consumer must only:

1. Define `build_server()` — a closure that constructs the FastMCP app with the component's own auth, processor, and feed wiring.
2. Register a `/health` route on the app that emits `"launcher": "mcp_common.server.launcher@<version>"` (read `mcp_common.__version__` at request time so editable-install version drift doesn't lie). REQ-005 is a consumer contract, not a launcher-side enforcement — the launcher doesn't write to `/health`. The trivial smoke app in `scripts/launch_smoke.py` shows the canonical pattern: `@app.custom_route("/health", methods=["GET"])` returning JSON with the `launcher` field.

If you find yourself writing `transport="http"` or `timeout_graceful_shutdown=30` outside of a `build_server` closure, the launcher abstraction has leaked — file a regression.

## The contract

The launcher's `launch()` is keyword-only — every argument other than `build_server` has a default and is opt-in.

```python
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
    ...
```

The variadic `build_server` contract (REQ-003) is load-bearing: a closure is allowed to capture as many pre-bound config objects as it likes (auth config, providers, processor, warmed feed dict) from its enclosing scope, then call `build_server()` with no arguments. Forward-compatible: a future launcher version adding a new pre-bind helper doesn't break existing closures.

`secrets_path=None` and `settings_path=None` are valid opt-outs — components with no secrets file (or no settings.yaml) just pass `None` and the launcher skips that step. See Example 4 (`cj` / crackerjack) for the no-auth, no-settings shape.

## Cookbook examples

Each example below is a worked migration with a diff between the existing bespoke launch script and the new launcher wrapper. Examples are runnable against the actual source paths cited; paths were verified via `ls -la` at plan-write time.

### Example 1: oneiric (closure + secrets + settings-feed warm + processor)

**Before** — `/Users/les/Projects/oneiric/scripts/launch_mcp.py` (≈160 LOC, manual `WorkflowTaskProcessor`, manual `health_feeds`, manual transport selection):

```python
# oneiric/scripts/launch_mcp.py — current bespoke shape
from types import SimpleNamespace
from oneiric.cli.mcp import _load_auth_from_settings
from oneiric.mcp.config import load_auth_config
from oneiric.mcp.server import build_mcp_server


def _build_processor():
    from oneiric.core.config import LayerSettings
    from oneiric.core.lifecycle import LifecycleManager
    from oneiric.core.resolution import Resolver
    from oneiric.domains.workflows import WorkflowBridge
    from oneiric.mcp.scheduler import WorkflowTaskProcessor

    layer_settings = LayerSettings()
    resolver = Resolver()
    lifecycle = LifecycleManager(resolver)
    workflow_bridge = WorkflowBridge(resolver=resolver, lifecycle=lifecycle, settings=layer_settings)
    return WorkflowTaskProcessor(workflow_bridge)


def _build_warm_feeds() -> dict:
    from oneiric.mcp.health import HealthFeedState
    feeds = {}
    for name in ("settings", "context", "progress"):
        feed = HealthFeedState(name=name)
        feed.record_success(entities_count=0)
        feeds[name] = feed
    return feeds


def main() -> int:
    # argparse, settings_path validation, mode iteration...
    auth_config = _load_auth_from_settings(settings_path)
    mcp_auth_config, providers = load_auth_config(auth_config, provider_factories={})
    processor = _build_processor()
    health_feeds = _build_warm_feeds()

    server = build_mcp_server(
        config=SimpleNamespace(name="oneiric"),
        auth_config=mcp_auth_config,
        providers=providers,
        processor=processor,
        health_feeds=health_feeds,
    )
    asyncio.run(server.run_async(transport="http", host=host, port=port))
```

**Diff** — collapse to a wrapper; the launcher handles transport + uvicorn grace + settings-feed warming (just for `settings`, not `context`/`progress`):

```diff
-# scripts/launch_mcp.py — 160 LOC bespoke launch
-from types import SimpleNamespace
-from oneiric.cli.mcp import _load_auth_from_settings
-from oneiric.mcp.config import load_auth_config
-from oneiric.mcp.server import build_mcp_server
-from oneiric.core.config import LayerSettings
-from oneiric.core.lifecycle import LifecycleManager
-from oneiric.core.resolution import Resolver
-from oneiric.domains.workflows import WorkflowBridge
-from oneiric.mcp.scheduler import WorkflowTaskProcessor
-from oneiric.mcp.health import HealthFeedState
-import argparse
-import asyncio
-import sys
+# scripts/launch_mcp.py — ~25 LOC wrapper around launch()
+from pathlib import Path
+from types import SimpleNamespace
+from mcp_common.server import launch
```

```python
#!/usr/bin/env python3
"""Launch wrapper for the Oneiric FastMCP server (mcp-common launcher edition)."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace


def _build_processor():
    from oneiric.core.config import LayerSettings
    from oneiric.core.lifecycle import LifecycleManager
    from oneiric.core.resolution import Resolver
    from oneiric.domains.workflows import WorkflowBridge
    from oneiric.mcp.scheduler import WorkflowTaskProcessor

    layer_settings = LayerSettings()
    resolver = Resolver()
    lifecycle = LifecycleManager(resolver)
    workflow_bridge = WorkflowBridge(resolver=resolver, lifecycle=lifecycle, settings=layer_settings)
    return WorkflowTaskProcessor(workflow_bridge)


def build_server():
    """Closure: pre-binds auth, processor, warmed feeds; build_server() takes no args."""
    from oneiric.cli.mcp import _load_auth_from_settings
    from oneiric.mcp.config import load_auth_config
    from oneiric.mcp.server import build_mcp_server

    settings_path = Path(args.settings)  # captured from enclosing main()
    auth_config = _load_auth_from_settings(settings_path)
    mcp_auth_config, providers = load_auth_config(auth_config, provider_factories={})
    processor = _build_processor()

    return build_mcp_server(
        config=SimpleNamespace(name="oneiric"),
        auth_config=mcp_auth_config,
        providers=providers,
        processor=processor,
        # health_feeds left unset — the launcher pre-warmed `settings` only;
        # `context` and `progress` start unhealthy and populate via tool calls.
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("settings", nargs="?",
                        default=str(Path.home() / ".oneiric" / "settings.yaml"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8681)
    args = parser.parse_args()

    settings_path = Path(args.settings)
    if not settings_path.exists():
        print(f"settings file not found: {settings_path}", file=sys.stderr)
        return 2

    asyncio.run(
        launch(
            build_server=build_server,
            component_name="oneiric",
            secrets_path=Path("~/.config/secrets.env"),
            settings_path=settings_path,
            host=args.host,
            port=args.port,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Demonstrable by** (per REQ-005, REQ-013):

```bash
launchctl unload ~/Library/LaunchAgents/com.mcp.oneiric.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.mcp.oneiric.plist
sleep 2
curl -fsS http://127.0.0.1:8681/health | python -m json.tool
# expect HTTP 200, body contains "launcher": "mcp_common.server.launcher@<version>"
```

The `_build_warm_feeds()` helper is deleted outright — its only legitimate consumer was the `settings` feed, which the launcher now warms via `warm_settings_feed()`. Pre-warming `context`/`progress` with `entities_count=0` was a workaround for the 503-on-empty-feed cycle that the launcher fix avoids (see [[feedback-oneiric-mcp-health-feed-warmup]]).

### Example 2: vishnu (mahavishnu) (secrets only — no settings warm)

**Before** — `/Users/les/Projects/mahavishnu/scripts/launch_mcp_with_secrets.py` (≈90 LOC, inline secrets regex parser, then `os.execvp` to `mahavishnu mcp start`):

```python
# mahavishnu/scripts/launch_mcp_with_secrets.py — bespoke launch
SECRETS_ENV = Path.home() / ".config" / "secrets.env"
_REPO_ROOT = Path(__file__).resolve().parent.parent
MCP_PROGRAM = str(_REPO_ROOT / ".venv" / "bin" / "python")
MCP_ARGS = ("-m", "mahavishnu", "mcp", "start")

_LINE_RE = re.compile(r"""^\s*(?:export\s+)?([A-Z0-9_]+)\s*=\s*(['"]?)(.*?)\2\s*$""")


def _strip_comment(value: str) -> str:
    idx = value.find(" #")
    return value if idx < 0 else value[:idx].rstrip()


def load_secrets() -> dict[str, str]:
    if not SECRETS_ENV.exists():
        return {}
    result: dict[str, str] = {}
    try:
        with SECRETS_ENV.open() as f:
            for raw in f:
                line = raw.rstrip("\n")
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                m = _LINE_RE.match(line)
                if not m:
                    continue
                key, _quote, value = m.group(1), m.group(2), m.group(3)
                result[key.upper()] = _strip_comment(value)
    except OSError:
        return {}
    return result


def main() -> int:
    secrets = load_secrets()
    for key, value in secrets.items():
        os.environ.setdefault(key, value)
    os.execvp(MCP_PROGRAM, (MCP_PROGRAM, *MCP_ARGS))
    return 1
```

**After** — ~10 LOC. The regex parser is no longer needed (it lives at `mcp_common.server.launcher.load_secrets` per Task 1.1). The `os.execvp` hop is gone — we keep the same Python process and call `launch()` directly:

```python
#!/usr/bin/env python3
"""Launch wrapper for the Mahavishnu MCP server (mcp-common launcher edition)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp_common.server import launch
from mahavishnu.mcp.server import build_mahavishnu_mcp_app  # planned per plan §5 Phase 4a


def build_server():
    """Closure: returns the configured Mahavishnu FastMCP app. build_server() takes no args."""
    return build_mahavishnu_mcp_app()


def main() -> int:
    asyncio.run(
        launch(
            build_server=build_server,
            component_name="mahavishnu",
            secrets_path=Path("~/.config/secrets.env"),
            host="127.0.0.1",
            port=8680,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

> **Inline secrets parser — DELETE:** the `_LINE_RE`, `_strip_comment`, and `load_secrets()` helpers in `launch_mcp_with_secrets.py` are now covered by `mcp_common.server.launcher.load_secrets()`. They are removed in the same commit that introduces this wrapper.

**Demonstrable by**:

```bash
launchctl unload ~/Library/LaunchAgents/com.mcp.mahavishnu.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.mcp.mahavishnu.plist
sleep 3
curl -fsS http://127.0.0.1:8680/health | python -m json.tool | grep launcher
# expect: "launcher": "mcp_common.server.launcher@<version>"
```

### Example 3: ak (akosha) (mode dispatch collapse)

**Before** — `/Users/les/Projects/akosha/akosha/cli.py:_start_server` lines 368-440 (mode dispatch + FastMCP `app.run(transport="streamable-http", uvicorn_config={...})`):

```python
# akosha/akosha/cli.py:_start_server — bespoke shape with mode dispatch
def _start_server(host, port, mode, config, verbose) -> None:
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    valid_modes = ["lite", "standard"]
    if mode not in valid_modes:
        typer.echo(f"Invalid mode: {mode}", err=True)
        raise typer.Exit(code=1)

    logger.info(f"Starting Akosha MCP server in {mode} mode on {host}:{port}")

    config_dict: dict[str, Any] = _load_config(config) if config else {}
    mode_instance = _init_mode(mode, config_dict)
    _configure_logging(verbose)

    from akosha.mcp import create_app

    app_instance = create_app(mode=mode_instance)

    logger.info(f"Akosha ready in {mode} mode")
    logger.info(f"   Mode: {mode_instance.mode_config.description}")

    # Override FastMCP's hardcoded 2s graceful-shutdown timeout
    app_instance.run(
        transport="streamable-http",
        host=host,
        port=port,
        path="/mcp",
        uvicorn_config={"timeout_graceful_shutdown": 30},
    )
```

**After** — mode selection happens **outside** the closure (in the wrapper script, bound by the Typer `--mode` flag) so the closure captures `mode_instance` from its enclosing scope. The launcher handles transport (`"http"`) and uvicorn grace:

```python
# Wrapper: akosha/scripts/launch_mcp.py (planned per Phase 4b / Task 4b.1 discovery)
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp_common.server import launch

# Mode dispatch happens here (before the closure is constructed) so the
# closure captures mode_instance from enclosing scope with no args.
def _init_mode(mode: str, config_dict: dict) -> object:
    # Same logic as _start_server's mode dispatch — moved verbatim.
    from akosha.mcp.modes import LiteMode, StandardMode
    if mode == "lite":
        return LiteMode(config_dict)
    if mode == "standard":
        return StandardMode(config_dict)
    raise ValueError(f"Invalid mode: {mode}")


def build_server(mode: str = "lite"):
    """Closure factory: bind mode at construction; the returned closure takes no args."""
    mode_instance = _init_mode(mode, {})

    def _build():
        from akosha.mcp import create_app
        return create_app(mode=mode_instance)

    return _build


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("lite", "standard") else "lite"
    asyncio.run(
        launch(
            build_server=build_server(mode),
            component_name="akosha",
            secrets_path=Path("~/.config/secrets.env"),
            host="127.0.0.1",
            port=8682,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

> **Closure capture note:** the inner `_build()` takes no arguments because `mode_instance` is closed over from the factory's enclosing scope (REQ-003 — variadic `build_server: Callable[..., Any]`). Two-stage capture is a common pattern: factory binds deps, inner closure returns the assembled server.

**Demonstrable by**:

```bash
launchctl unload ~/Library/LaunchAgents/com.mcp.akosha.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.mcp.akosha.plist
sleep 3
curl -fsS http://127.0.0.1:8682/health | python -m json.tool | grep launcher
# expect: HTTP 200, body contains "launcher": "mcp_common.server.launcher@<version>"
# Also:  curl /health | jq .checks.settings.healthy
# expect: true (was false with cycle_count=0 only)
```

### Example 4: cj (crackerjack) (no auth, no settings — closure passes `auth_config=None`)

**Before** — `/Users/les/Projects/crackerjack/crackerjack/mcp/server_core.py:_run_mcp_server` lines 480-509 (mode flag, `mcp_app.run_http_async(host=, port=, uvicorn_config={"timeout_graceful_shutdown": 30})`):

```python
# crackerjack/crackerjack/mcp/server_core.py:_run_mcp_server — bespoke shape
def _run_mcp_server(mcp_app, mcp_config, http_mode) -> None:
    console.print("[yellow]MCP app created, about to run...[/yellow]")

    try:
        if mcp_config.get("http_enabled", False) or http_mode:
            host = mcp_config.get("http_host", "127.0.0.1")
            port = mcp_config.get("http_port", 8676)

            # Override FastMCP's hardcoded 2s graceful-shutdown timeout
            asyncio.run(
                mcp_app.run_http_async(
                    host=host,
                    port=port,
                    uvicorn_config={"timeout_graceful_shutdown": 30},
                )
            )
        else:
            mcp_app.run()
    except Exception as e:
        console.print(f"[red]MCP run failed: {e}[/red]")
        import traceback; traceback.print_exc(); raise
```

**After** — crackerjack has no auth subsystem and no `settings.yaml` consumed by the launcher, so the closure's pre-bind is minimal. `secrets_path=None` and `settings_path=None` opt out cleanly:

```python
# crackerjack/scripts/launch_mcp.py (planned per Phase 4a Task 4a.2)
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp_common.server import launch
from crackerjack.mcp.server_core import create_mcp_server


def build_server():
    """Closure: cj has no auth and no settings.yaml; the launcher skips both."""
    mcp_config = {"http_enabled": True, "http_host": "127.0.0.1", "http_port": 8676}

    # create_mcp_server is async + accepts config; the launcher build_server()
    # is sync (variadic Callable[..., Any]). Bridge with a small helper.
    server = asyncio.get_event_loop().run_until_complete(create_mcp_server(mcp_config))
    return server


def main() -> int:
    asyncio.run(
        launch(
            build_server=build_server,
            component_name="crackerjack",
            # cj has no auth subsystem, so no secrets.env pre-bind:
            secrets_path=None,
            # cj has no settings.yaml; the launcher's settings-feed warm is a no-op:
            settings_path=None,
            host="127.0.0.1",
            port=8676,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

> **Important:** `auth_config=None` is the right value for cj — pass it explicitly to `create_mcp_server(mcp_config, auth_config=None)` if the API accepts it; otherwise the closure simply omits it (crackerjack's factory has no `auth_config` kwarg today).
>
> The launcher's `run_with_uvicorn_config()` threads `timeout_graceful_shutdown=30` into the underlying `mcp_app.run_http_async(...)` call (REQ-007). The launcher doesn't need to know whether the FastMCP variant is `.run_async()` or `.run_http_async()` — it duck-types on `run_async(transport="http", uvicorn_config=...)`. cj's `mcp_app` must expose an async `run_async` method (or be migrated to expose one).

**Demonstrable by**:

```bash
launchctl unload ~/Library/LaunchAgents/com.mcp.crackerjack.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.mcp.crackerjack.plist
sleep 3
curl -fsS http://127.0.0.1:8676/health | python -m json.tool | grep launcher
# expect: HTTP 200, body contains "launcher": "mcp_common.server.launcher@<version>"
```

## Migration checklist

For a maintainer migrating a repo's MCP launch script to `mcp_common.server.launcher.launch()`:

1. **Read the current launch script.** Identify what it does inline: secrets loading, transport selection, uvicorn grace, feed warming, mode dispatch, processor wiring. Each of these is something the launcher (or `build_server`'s closure) should now own.
2. **Find the `build_server` callable in the current code.** For most components it's a function like `create_app`, `build_mcp_server`, `build_mahavishnu_mcp_app`. For atypical paths, the callable is whatever the existing code calls right before `app.run_async(...)`.
3. **Write the new wrapper** — 5 to 25 LOC, structured as:
   - a closure factory (or a plain function) that pre-binds config/auth/processor and returns the FastMCP instance;
   - `main()` that calls `await launch(build_server=..., component_name=..., ...)`.
4. **Update the launchd plist `ProgramArguments`** if the entry script changed path or invocation shape. Keep `--foreground` semantics where the existing plist supervised the wrapper directly.
5. **Delete the inline secrets parser** if the old wrapper had one — `mcp_common.server.launcher.load_secrets()` covers it (Task 1.1).
6. **Delete the inline feed warm helper** if it pre-warmed `context`/`progress` with `entities_count=0` — only `settings` should be pre-warmed (REQ-004). See [[feedback-oneiric-mcp-health-feed-warmup]] for the rationale.
7. **Smoke-test the migration**:

    ```bash
    launchctl unload ~/Library/LaunchAgents/com.mcp.<component>.plist 2>/dev/null
    launchctl load ~/Library/LaunchAgents/com.mcp.<component>.plist
    sleep 2
    curl -fsS http://127.0.0.1:<port>/health | python -m json.tool | grep launcher
    # expect: HTTP 200, body contains "launcher": "mcp_common.server.launcher@<version>"
    ```

8. **Verify the Backward Compatibility Test Matrix row stays green** (per REQ-013): public CLI commands + launchd plist `ProgramArguments` + smoke test must all match the pre-migration matrix entry.
9. **Confirm `pyproject.toml` version is unchanged.** Per [[feedback-mcp-common-version-bump-is-user]], mcp-common version bumps are user-owned via `crackerjack run -p minor`. Do not bump in the migration commit.

## Failure modes / Rollback

| Symptom | Likely cause | What to check |
|---|---|---|
| `curl /health` returns **503** indefinitely | `settings` health feed not warmed (entities_count==0 AND cycles_total>=1 AND ingester_running) | Run `curl /health | jq .checks.settings`. If `healthy: false` AND `entities_count: 0`, your closure is rebuilding the feed rather than letting the launcher's `warm_settings_feed()` run. Pass `settings_path=...` to `launch()`. |
| `curl /health` returns **200 but no `"launcher"` field** | The component's `/health` route handler doesn't emit the field (REQ-005 is consumer-side, not launcher-side) | Add a `@app.custom_route("/health", methods=["GET"])` handler that reads `mcp_common.__version__` and includes `"launcher": f"mcp_common.server.launcher@{mcp_common.__version__}"`. See `scripts/launch_smoke.py` for a working reference. |
| `TypeError: TransportMixin.run_stdio_async() got an unexpected keyword argument 'host'` | The `build_server` closure returned a server that lacks `run_async(transport=...)`, or the launcher was bypassed | Verify the wrapper's `main()` calls `launch(...)`. If migrating in stages, ensure no legacy `app.run(...)` / `app.run_async(host=, port=)` site survives. |
| Server boot loops every KeepAlive cycle in launchd | Stale `os.execvp` chain (Example 2 old shape) replaced by direct `launch()` but launchd still restarts on non-zero exit | Confirm the wrapper returns 0 on cooperative shutdown; don't bypass the launcher's signal handling. |
| `RuntimeError: schedule_task requires a processor; none supplied.` on first boot | Component forgot to bind a processor / WorkflowBridge inside `build_server` (per [[feedback-oneiric-cli-mcp-loader-gap]]) | Check the closure: `_build_processor()` must be called and the processor must be passed to the FastMCP factory. |
| `/health=200` immediately, then **503** ~30s later after first tool call | Pre-warmed feed was overwritten by a tool that records `record_success(entities_count=0)`, returning `WARMING_UP_EMPTY_FEED` predicate | Tool writes should populate `entities_count > 0` on success. Bug is in the tool, not the launcher. |
| `curl /health` **200** but the `checks.context`/`progress` feeds are unhealthy | This is correct. `context` and `progress` populate via `tools/list` followed by the first tool call. | Wait a few seconds; run any tool via `tools/call`; re-curl `/health`. |
| Launcher import fails: `ModuleNotFoundError: mcp_common.server.launcher` | mcp-common is below 0.28.0, or installed in a different venv | `pip show mcp-common` in the active venv. Per [[feedback-mcp-common-version-bump-is-user]], coordinate the bump with the user. |
| SIGTERM takes >60s to exit (after the migration) | A caller is still setting its own `uvicorn_config` or the FastMCP instance has its own handler | The launcher is the only place that pins `timeout_graceful_shutdown=30` (REQ-007). Search the closure for stray `uvicorn_config=` overrides. |
| Vanilla FastMCP/uvicorn exits with `returncode=-15` on SIGTERM, NOT `0` (discovered 2026-09-26 during REQ-014 smoke) | uvicorn completes graceful shutdown ("Application shutdown complete") but the Python process inherits the OS-level SIGTERM default disposition (returncode 128 + 15) | Install an explicit handler in the wrapper so REQ-014 holds for real-FastMCP migrations, not just the stub: `signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))` BEFORE `launch(...)`. launchd `KeepAlive.SuccessfulExit=false` is the standard plist setting, so the -15 exit doesn't trigger a restart loop, but incident-response scripts key on returncode=0 to distinguish clean shutdowns from signals. |

### Rollback to the bespoke launcher

If a migration must be reverted:

1. Restore the old `scripts/launch_mcp*.py` from git (`git checkout HEAD~1 -- <path>`).
2. Restore the launchd plist `ProgramArguments` if it was edited.
3. `launchctl unload && launchctl load` the plist; smoke-test with `curl /health` matching the pre-migration matrix row.
4. The mcp-common launcher import (`from mcp_common.server import launch`) is purely additive to mcp-common 0.28.0 — it has no side effects on import, so leaving the new wrapper present in the codebase while you roll back the plist is safe.

## See also

- [[feedback-oneiric-cli-mcp-loader-gap]] — the bug oneiric's `mcp_start` originally had with missing `WorkflowTaskProcessor` wiring (dormant; fixed by REQ-009 in plan Phase 2.5c).
- [[feedback-oneiric-mcp-health-feed-warmup]] — the 503-on-`cycles_total==0`-after-warm pattern that drove REQ-004's "pre-warm `settings` only, with `entities_count > 0`" decision.
- [[feedback-mcp-common-version-bump-is-user]] — version bumps + PyPI publish are user-owned; this plan and cookbook document migration shape only.
- `docs/plans/2026-09-26-mcp-launcher-standardization.md` in mahavishnu — the parent plan; cross-references REQ-001..016 throughout this cookbook.
- `mcp_common/server/launcher.py` — the helper itself (~150 LOC after tests).
- `tests/server/test_launcher.py` — TDD test coverage for each helper (29 tests).
- `mahavishnu/docs/mcp/server-migration-tracker.md` — per-repo action item table for all 20 standalone Bodai-managed MCP servers (planned per REQ-012, REQ-015).
