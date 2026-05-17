from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

import pytest

import mcp_common.websocket.metrics as metrics_module
from mcp_common.websocket.metrics import WebSocketMetrics, get_metrics_summary


class _MetricHandle:
    def __init__(self) -> None:
        self.label_calls: list[dict[str, object]] = []
        self.inc_calls: list[float] = []
        self.dec_calls: int = 0
        self.set_calls: list[float] = []
        self.observe_calls: list[float] = []

    def labels(self, **kwargs: object) -> _MetricHandle:
        self.label_calls.append(kwargs)
        return self

    def inc(self, amount: float = 1) -> None:
        self.inc_calls.append(amount)

    def dec(self) -> None:
        self.dec_calls += 1

    def set(self, value: float) -> None:
        self.set_calls.append(value)

    def observe(self, amount: float) -> None:
        self.observe_calls.append(amount)


@pytest.mark.unit
class TestWebSocketMetrics:
    """Tests for websocket metrics collection."""

    def _install_metric_stubs(self, monkeypatch: pytest.MonkeyPatch) -> dict[str, _MetricHandle]:
        handles = {
            "connections_total": _MetricHandle(),
            "connections_active": _MetricHandle(),
            "messages_total": _MetricHandle(),
            "broadcast_total": _MetricHandle(),
            "broadcast_duration": _MetricHandle(),
            "connection_errors_total": _MetricHandle(),
            "message_errors_total": _MetricHandle(),
            "latency_seconds": _MetricHandle(),
        }

        monkeypatch.setattr(
            metrics_module,
            "websocket_connections_total",
            handles["connections_total"],
        )
        monkeypatch.setattr(
            metrics_module,
            "websocket_connections_active",
            handles["connections_active"],
        )
        monkeypatch.setattr(
            metrics_module,
            "websocket_messages_total",
            handles["messages_total"],
        )
        monkeypatch.setattr(
            metrics_module,
            "websocket_broadcast_total",
            handles["broadcast_total"],
        )
        monkeypatch.setattr(
            metrics_module,
            "websocket_broadcast_duration_seconds",
            handles["broadcast_duration"],
        )
        monkeypatch.setattr(
            metrics_module,
            "websocket_connection_errors_total",
            handles["connection_errors_total"],
        )
        monkeypatch.setattr(
            metrics_module,
            "websocket_message_errors_total",
            handles["message_errors_total"],
        )
        monkeypatch.setattr(
            metrics_module,
            "websocket_latency_seconds",
            handles["latency_seconds"],
        )
        return handles

    def test_disabled_metrics_short_circuit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        handles = self._install_metric_stubs(monkeypatch)
        metrics = WebSocketMetrics("session-buddy", enabled=False)

        metrics.on_connect("conn-1")
        metrics.on_disconnect("conn-1")
        metrics.on_message_sent("event")
        metrics.on_message_received("request")
        metrics.on_broadcast("room", 0.25)
        metrics.on_connection_error("timeout")
        metrics.on_message_error("decode_error")
        metrics.observe_latency("event", 0.1)
        metrics.set_active_connections(3)

        for handle in handles.values():
            assert handle.label_calls == []
            assert handle.inc_calls == []
            assert handle.dec_calls == 0
            assert handle.set_calls == []
            assert handle.observe_calls == []

        assert metrics._connection_start_times == {}

    def test_enabled_metrics_record_activity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        handles = self._install_metric_stubs(monkeypatch)
        monkeypatch.setattr(metrics_module, "PROMETHEUS_AVAILABLE", True)
        monkeypatch.setattr(metrics_module.time, "time", lambda: 123.45)

        metrics = WebSocketMetrics("session-buddy", tls_enabled=True, enabled=True)
        metrics.on_connect("conn-1")
        metrics.on_message_sent("event")
        metrics.on_message_received("request")
        metrics.on_broadcast("room", 0.25)
        metrics.on_connection_error("timeout")
        metrics.on_message_error("decode_error")
        metrics.observe_latency("event", 0.1)
        metrics.set_active_connections(7)
        metrics.on_disconnect("conn-1")

        assert handles["connections_total"].label_calls[0] == {
            "server": "session-buddy",
            "tls_mode": "wss",
        }
        assert handles["connections_total"].inc_calls == [1]
        assert handles["connections_active"].inc_calls == [1]
        assert handles["connections_active"].dec_calls == 1
        assert handles["messages_total"].label_calls[0] == {
            "server": "session-buddy",
            "message_type": "event",
            "direction": "sent",
        }
        assert handles["messages_total"].label_calls[1] == {
            "server": "session-buddy",
            "message_type": "request",
            "direction": "received",
        }
        assert handles["broadcast_total"].label_calls[0] == {
            "server": "session-buddy",
            "channel": "room",
        }
        assert handles["broadcast_total"].inc_calls == [1]
        assert handles["broadcast_duration"].observe_calls == [0.25]
        assert handles["connection_errors_total"].label_calls[0] == {
            "server": "session-buddy",
            "error_type": "timeout",
        }
        assert handles["message_errors_total"].label_calls[0] == {
            "server": "session-buddy",
            "error_type": "decode_error",
        }
        assert handles["latency_seconds"].observe_calls == [0.1]
        assert handles["connections_active"].set_calls == [7]
        assert "conn-1" not in metrics._connection_start_times

    def test_start_metrics_server_success_and_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(metrics_module, "PROMETHEUS_AVAILABLE", True)
        metrics = WebSocketMetrics("session-buddy", enabled=True)

        called: list[int] = []

        def fake_start_http_server(port: int) -> None:
            called.append(port)

        monkeypatch.setattr(metrics_module, "start_http_server", fake_start_http_server)

        assert metrics.start_metrics_server(9091) is True
        assert called == [9091]

        def failing_start_http_server(_port: int) -> None:
            raise RuntimeError("boom")

        monkeypatch.setattr(metrics_module, "start_http_server", failing_start_http_server)
        assert metrics.start_metrics_server(9092) is False

    def test_start_metrics_server_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        metrics = WebSocketMetrics("session-buddy", enabled=False)
        monkeypatch.setattr(metrics_module, "PROMETHEUS_AVAILABLE", True)

        assert metrics.start_metrics_server(9090) is False

    def test_summary_when_prometheus_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(metrics_module, "PROMETHEUS_AVAILABLE", False)
        assert get_metrics_summary("session-buddy") == {"available": False}

    def test_summary_available_and_error_paths(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(metrics_module, "PROMETHEUS_AVAILABLE", True)

        registry = type(
            "Registry",
            (),
            {"getCollectorNames": lambda self: {"a", "b", "c"}},
        )()
        fake_module = ModuleType("prometheus_client")
        fake_module.REGISTRY = registry
        monkeypatch.setitem(sys.modules, "prometheus_client", fake_module)

        summary = get_metrics_summary("session-buddy")
        assert summary["available"] is True
        assert summary["server"] == "session-buddy"
        assert summary["metrics_count"] == 3

        class BrokenRegistry:
            def getCollectorNames(self) -> set[str]:
                raise RuntimeError("boom")

        fake_module.REGISTRY = BrokenRegistry()
        summary = get_metrics_summary("session-buddy")
        assert summary["available"] is True
        assert summary["error"] == "boom"
