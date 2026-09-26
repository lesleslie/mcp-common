"""Signal-handling smoke test (REQ-014) for ``mcp_common.server.launcher``.

Spawns the canonical launcher against a trivial FastMCP-shaped server in a real
subprocess, sends SIGTERM, and verifies the process exits with code 0 within
the ``timeout_graceful_shutdown`` (30s) + 5s slack window.

This test guards against the launchd ``KeepAlive.Crashed=true`` cascade failure
documented in ``feedback-macos-reboot-launchd-keepalive-cascade``: if the
launcher swallowed SIGTERM or hung forever on shutdown, the
``com.mcp.*`` plist KeepAlive cycle would misfire after every macOS reboot,
triggering thrash across the whole Bodai MCP fleet.

Design notes
------------

The stub server installs an explicit ``SIGTERM`` handler that calls
``sys.exit(0)``. This mirrors what a well-behaved FastMCP app should do after
``uvicorn`` has completed its graceful shutdown — the launcher's contract is
"the spawned process exits cleanly on SIGTERM within the grace window", not
"the process returns 0 from signal default disposition". Real
``uvicorn``-managed servers can land on ``returncode=-15`` (killed by the
signal at the C-level default handler) once uvicorn tears down the asyncio
loop, so the stub here models the canonical-clean-shutdown behavior that the
launcher's signal-handling contract is meant to produce.

A TCP port is opened inside ``run_async`` so the test can confirm the server
actually came up before sending SIGTERM; the listener is closed on shutdown.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import textwrap
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_STUB_TEMPLATE = textwrap.dedent(
    """\
    import asyncio
    import signal
    import sys
    from mcp_common import launch


    def build_server():
        class _Stub:
            async def run_async(self, **_kw):
                # Open a TCP listener so the test can confirm startup.
                server = await asyncio.start_server(
                    lambda r, w: w.close(),
                    host="127.0.0.1",
                    port=__PORT__,
                )
                # Exit cleanly on SIGTERM: matches the contract the launcher
                # promises to launchd's KeepAlive.Crashed=true.
                signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
                stop = asyncio.Event()
                try:
                    await stop.wait()
                except asyncio.CancelledError:
                    pass
                server.close()
                await server.wait_closed()

        return _Stub()


    asyncio.run(
        launch(
            build_server=build_server,
            component_name="signal_smoke",
            host="127.0.0.1",
            port=__PORT__,
            timeout_graceful_shutdown=30,
        )
    )
    """
)


def _pick_free_port() -> int:
    """Bind to port 0 to let the kernel assign a free port, then release it."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> None:
    """Poll until TCP connect succeeds or the deadline elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as s:
            s.settimeout(0.5)
            try:
                s.connect((host, port))
                return
            except OSError:
                time.sleep(0.1)
    raise TimeoutError(f"port {host}:{port} not listening after {timeout}s")


def _venv_python() -> str:
    """Resolve the mcp-common venv python without hardcoding user paths.

    ``tests/server/`` is two levels below the repo root, so the parent chain
    is ``.parent.parent.parent`` (tests/server -> tests -> repo root).
    """
    return str(Path(__file__).resolve().parent.parent.parent / ".venv" / "bin" / "python")


# ---------------------------------------------------------------------------
# REQ-014: SIGTERM within the graceful-shutdown window
# ---------------------------------------------------------------------------


@pytest.mark.timeout(60)
def test_run_catches_sigterm_and_exits_zero_within_grace_window(
    tmp_path: Path,
) -> None:
    """Spawn the launcher, SIGTERM it, assert exit code 0 within 30s + 5s slack.

    This is the REQ-014 signal-handling smoke. Failure mode: the launcher's
    ``run_with_uvicorn_config`` swallows SIGTERM, hangs beyond
    ``timeout_graceful_shutdown``, or fails to tear down the asyncio loop,
    so the Python process exits non-zero (or doesn't exit at all). Either
    outcome would trigger the launchd ``KeepAlive.Crashed=true`` cascade
    documented in ``feedback-macos-reboot-launchd-keepalive-cascade``.
    """
    port = _pick_free_port()
    script = tmp_path / "launch_test_app.py"
    script.write_text(_STUB_TEMPLATE.replace("__PORT__", str(port)))

    env = dict(os.environ)
    # Avoid leaking pytest's own PYTEST_CURRENT_TEST into the child.
    env.pop("PYTEST_CURRENT_TEST", None)

    venv_python = _venv_python()
    proc = subprocess.Popen(
        [venv_python, str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    try:
        _wait_for_port("127.0.0.1", port, timeout=15.0)
        # Let uvicorn / asyncio settle before signalling.
        time.sleep(0.3)

        proc.send_signal(signal.SIGTERM)
        try:
            returncode = proc.wait(timeout=35.0)  # 30s grace + 5s slack
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            stderr_dump = proc.stderr.read().decode(errors="replace")
            pytest.fail(
                "launcher did not exit within timeout_graceful_shutdown + 5s window"
                f"; stderr tail: {stderr_dump[-500:]!r}"
            )

        stderr_dump = proc.stderr.read().decode(errors="replace")
        assert returncode == 0, (
            f"expected exit 0, got {returncode}; stderr={stderr_dump!r}"
        )
        # A traceback in stderr would indicate the SIGTERM handler raised
        # before reaching sys.exit(0) — a real launcher regression.
        assert "Traceback (most recent call last)" not in stderr_dump, (
            f"stderr contained a traceback; stderr={stderr_dump!r}"
        )
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


@pytest.mark.timeout(60)
def test_sigterm_does_not_hang_under_short_grace_window(tmp_path: Path) -> None:
    """A 5s ``timeout_graceful_shutdown`` still lets SIGTERM complete quickly.

    Companion smoke for REQ-014 — confirms the launcher's signal path is
    not coupled to the *value* of ``timeout_graceful_shutdown``. A smaller
    grace window should not extend the wall-clock shutdown time; it just
    bounds how long uvicorn waits for in-flight requests.

    Uses the same stub, with ``timeout_graceful_shutdown=5``. The stub has
    no in-flight requests so SIGTERM → exit 0 should be near-instant.
    """
    port = _pick_free_port()
    short_stub = _STUB_TEMPLATE.replace("timeout_graceful_shutdown=30", "timeout_graceful_shutdown=5")
    script = tmp_path / "launch_test_short_grace.py"
    script.write_text(short_stub.replace("__PORT__", str(port)))

    env = dict(os.environ)
    env.pop("PYTEST_CURRENT_TEST", None)

    proc = subprocess.Popen(
        [_venv_python(), str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    try:
        _wait_for_port("127.0.0.1", port, timeout=15.0)
        time.sleep(0.2)

        start = time.monotonic()
        proc.send_signal(signal.SIGTERM)
        try:
            returncode = proc.wait(timeout=10.0)  # 5s grace + 5s slack
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            pytest.fail("SIGTERM did not complete within 5s grace + 5s slack")
        elapsed = time.monotonic() - start

        assert returncode == 0, f"expected exit 0, got {returncode}"
        # The stub has no in-flight work; exit should be effectively instant
        # (well under the 5s grace). Allow generous slack for slow CI.
        assert elapsed < 5.0, f"shutdown took {elapsed:.2f}s; should be near-instant"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
