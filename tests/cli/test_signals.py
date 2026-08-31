import signal

import pytest

from mcp_common.cli.signals import SignalHandler


def test_register_sets_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, object]] = []

    def fake_signal(sig: int, handler: object) -> None:
        calls.append((sig, handler))

    monkeypatch.setattr(signal, "signal", fake_signal)

    handler = SignalHandler(on_shutdown=lambda: None)
    handler.register()

    assert [sig for sig, _ in calls] == [signal.SIGTERM, signal.SIGINT]
    assert calls[0][1].__name__ == "_handle_shutdown"


def test_register_sets_reload_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def fake_signal(sig: int, _handler: object) -> None:
        calls.append(sig)

    monkeypatch.setattr(signal, "signal", fake_signal)

    handler = SignalHandler(on_shutdown=lambda: None, on_reload=lambda: None)
    handler.register()

    assert calls == [signal.SIGTERM, signal.SIGINT, signal.SIGHUP]


def test_handle_shutdown_exits_after_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful shutdown callback triggers os._exit(0).

    Uses os._exit (C-level syscall) instead of sys.exit (which raises
    SystemExit) so that the signal handler does not interrupt the
    asyncio event loop during uvicorn / FastMCP lifespan teardown.
    """
    called: list[bool] = []
    exit_codes: list[int] = []

    def fake_exit(code: int) -> None:
        exit_codes.append(code)
        raise SystemExit(code)

    monkeypatch.setattr("mcp_common.cli.signals.os._exit", fake_exit)

    def shutdown() -> None:
        called.append(True)

    handler = SignalHandler(on_shutdown=shutdown)

    with pytest.raises(SystemExit) as excinfo:
        handler._handle_shutdown(signal.SIGTERM, None)

    assert excinfo.value.code == 0
    assert exit_codes == [0]
    assert called == [True]

    # Second call must NOT re-run the shutdown callback or call _exit again.
    handler._handle_shutdown(signal.SIGTERM, None)
    assert exit_codes == [0]
    assert called == [True]


def test_handle_shutdown_exits_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A shutdown-callback error triggers os._exit(1) without propagating."""
    exit_codes: list[int] = []

    def fake_exit(code: int) -> None:
        exit_codes.append(code)
        raise SystemExit(code)

    monkeypatch.setattr("mcp_common.cli.signals.os._exit", fake_exit)

    def shutdown() -> None:
        msg = "boom"
        raise RuntimeError(msg)

    handler = SignalHandler(on_shutdown=shutdown)

    with pytest.raises(SystemExit) as excinfo:
        handler._handle_shutdown(signal.SIGINT, None)

    assert excinfo.value.code == 1
    assert exit_codes == [1]


def test_handle_reload_suppresses_errors() -> None:
    called: list[bool] = []

    def reload() -> None:
        called.append(True)
        msg = "fail"
        raise RuntimeError(msg)

    handler = SignalHandler(on_shutdown=lambda: None, on_reload=reload)
    handler._handle_reload(signal.SIGHUP, None)

    assert called == [True]


def test_handle_reload_no_handler() -> None:
    handler = SignalHandler(on_shutdown=lambda: None, on_reload=None)
    handler._handle_reload(signal.SIGHUP, None)
