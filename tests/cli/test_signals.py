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


def test_handle_shutdown_exits_after_callback() -> None:
    called: list[bool] = []

    def shutdown() -> None:
        called.append(True)

    handler = SignalHandler(on_shutdown=shutdown)

    with pytest.raises(SystemExit) as excinfo:
        handler._handle_shutdown(signal.SIGTERM, None)

    assert excinfo.value.code == 0
    assert called == [True]

    handler._handle_shutdown(signal.SIGTERM, None)


def test_handle_shutdown_exits_on_error() -> None:
    def shutdown() -> None:
        msg = "boom"
        raise RuntimeError(msg)

    handler = SignalHandler(on_shutdown=shutdown)

    with pytest.raises(SystemExit) as excinfo:
        handler._handle_shutdown(signal.SIGINT, None)

    assert excinfo.value.code == 1


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
