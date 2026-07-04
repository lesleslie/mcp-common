"""Branch-focused tests for mcp_common.websocket.client."""

from __future__ import annotations

import asyncio
import ssl
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

_websockets_mock = MagicMock()
with pytest.MonkeyPatch.context() as monkeypatch:
    monkeypatch.setitem(sys.modules, "websockets", _websockets_mock)
    import mcp_common.websocket.client as client_mod
    from mcp_common.websocket.client import WebSocketClient
    from mcp_common.websocket.protocol import WebSocketProtocol


class _FakeSSLContext:
    def __init__(self) -> None:
        self.loaded_verify_locations: list[str] = []
        self.check_hostname: bool | None = None
        self.verify_mode: int | None = None

    def load_verify_locations(self, cafile: str) -> None:
        self.loaded_verify_locations.append(cafile)


class _FakeWebSocket:
    def __init__(self, recv_messages: list[str] | None = None, iter_messages: list[str] | None = None) -> None:
        self.recv_messages = list(recv_messages or [])
        self.iter_messages = list(iter_messages or [])
        self.sent_messages: list[str] = []
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent_messages.append(message)

    async def recv(self) -> str:
        return self.recv_messages.pop(0)

    async def close(self) -> None:
        self.closed = True

    def __aiter__(self) -> _FakeWebSocket:
        self._iter = iter(self.iter_messages)
        return self

    async def __anext__(self) -> str:
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _ErrorWebSocket(_FakeWebSocket):
    async def __anext__(self) -> str:
        raise RuntimeError("socket loop failed")


class _FakeTask:
    def __init__(self, result: object | None = None, cancel_raises: bool = False) -> None:
        self.result = result
        self.cancel_raises = cancel_raises
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def __await__(self):
        async def _inner():
            if self.cancel_raises:
                raise asyncio.CancelledError
            return self.result

        return _inner().__await__()


def _create_task(coro):
    coro.close()
    return _FakeTask()


@pytest.fixture(autouse=True)
def reset_websockets_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_mod, "websockets", _websockets_mock, raising=False)
    _websockets_mock.reset_mock()
    client_mod.WEBSOCKETS_AVAILABLE = True


class TestConstructorAndSsl:
    def test_raises_when_websockets_missing(self) -> None:
        client_mod.WEBSOCKETS_AVAILABLE = False
        with pytest.raises(ImportError, match="websockets package is required"):
            WebSocketClient("ws://example.com")

    def test_configures_ssl_for_wss(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _FakeSSLContext()
        default_context = MagicMock(return_value=ctx)
        monkeypatch.setattr(client_mod.ssl, "create_default_context", default_context)

        client = WebSocketClient("wss://example.com", ca_file="/tmp/ca.pem")

        assert client.ssl_context is ctx
        assert ctx.loaded_verify_locations == ["/tmp/ca.pem"]
        default_context.assert_called_once_with(ssl.Purpose.SERVER_AUTH)

    def test_configures_insecure_ssl_for_development(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _FakeSSLContext()
        default_context = MagicMock(return_value=ctx)
        monkeypatch.setattr(client_mod.ssl, "create_default_context", default_context)

        client = WebSocketClient("wss://example.com", verify_ssl=False)

        assert client.ssl_context is ctx
        assert ctx.check_hostname is False
        assert ctx.verify_mode == ssl.CERT_NONE
        default_context.assert_called_once_with()

    def test_is_secure_property(self) -> None:
        assert WebSocketClient("wss://example.com", ssl_context=_FakeSSLContext()  # ty: ignore[invalid-argument-type]
                          ).is_secure is True
        assert WebSocketClient("ws://example.com").is_secure is False


class TestConnectAndAuth:
    @pytest.mark.asyncio
    async def test_connect_already_connected(self) -> None:
        client = WebSocketClient("ws://example.com")
        client.is_connected = True
        await client.connect()

    @pytest.mark.asyncio
    async def test_connect_success_with_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        websocket = _FakeWebSocket(
            recv_messages=[
                WebSocketProtocol.encode(
                    WebSocketProtocol.create_response(
                        WebSocketProtocol.create_request("auth", {"token": "t"}),
                        {"user_id": "alice"},
                    )
                )
            ]
        )
        _websockets_mock.connect = AsyncMock(return_value=websocket)
        monkeypatch.setattr(client_mod.asyncio, "create_task", _create_task)

        client = WebSocketClient("ws://example.com", token="t")
        client._receive_loop = AsyncMock(return_value=None)  # type: ignore[method-assign]

        await client.connect()

        assert client.websocket is websocket
        assert client.is_connected is True
        assert client.is_authenticated is True
        assert client.connection_id is not None
        assert websocket.sent_messages
        _websockets_mock.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_success_without_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        websocket = _FakeWebSocket()
        _websockets_mock.connect = AsyncMock(return_value=websocket)
        monkeypatch.setattr(client_mod.asyncio, "create_task", _create_task)

        client = WebSocketClient("ws://example.com")
        client._receive_loop = AsyncMock(return_value=None)  # type: ignore[method-assign]

        await client.connect()

        assert client.websocket is websocket
        assert client.is_connected is True
        assert client.is_authenticated is False
        assert websocket.sent_messages == []

    @pytest.mark.asyncio
    async def test_connect_failure_no_reconnect(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _websockets_mock.connect = AsyncMock(side_effect=RuntimeError("boom"))
        client = WebSocketClient("ws://example.com", reconnect=False)

        with pytest.raises(RuntimeError, match="boom"):
            await client.connect()

    @pytest.mark.asyncio
    async def test_connect_failure_schedules_reconnect(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _websockets_mock.connect = AsyncMock(side_effect=RuntimeError("boom"))
        reconnect = AsyncMock()
        monkeypatch.setattr(client_mod.asyncio, "create_task", _create_task)
        client = WebSocketClient("ws://example.com", reconnect=True)
        client._reconnect_loop = reconnect  # type: ignore[method-assign]

        await client.connect()

        assert client.reconnect_task is not None

    @pytest.mark.asyncio
    async def test_authenticate_response_and_error(self) -> None:
        ok_ws = _FakeWebSocket(
            recv_messages=[
                WebSocketProtocol.encode(
                    WebSocketProtocol.create_response(
                        WebSocketProtocol.create_request("auth", {"token": "t"}),
                        {"user_id": "alice"},
                    )
                )
            ]
        )
        client = WebSocketClient("ws://example.com", token="t")
        client.websocket = ok_ws
        await client._authenticate()
        assert client.is_authenticated is True

        err_ws = _FakeWebSocket(
            recv_messages=[
                WebSocketProtocol.encode(
                    WebSocketProtocol.create_error("AUTH_FAILED", "bad token")
                )
            ]
        )
        client.websocket = err_ws
        with pytest.raises(ConnectionError, match="Authentication failed"):
            await client._authenticate()

        client.is_authenticated = False
        other_ws = _FakeWebSocket(
            recv_messages=[
                WebSocketProtocol.encode(
                    WebSocketProtocol.create_event("status", {"ok": True})
                )
            ]
        )
        client.websocket = other_ws
        await client._authenticate()
        assert client.is_authenticated is False

    @pytest.mark.asyncio
    async def test_authenticate_without_token_returns_none(self) -> None:
        client = WebSocketClient("ws://example.com")
        client.websocket = _FakeWebSocket()

        result = await client._authenticate()

        assert result is None


class TestDisconnectAndReceive:
    @pytest.mark.asyncio
    async def test_disconnect_cancels_tasks_and_closes_socket(self) -> None:
        websocket = _FakeWebSocket()
        client = WebSocketClient("ws://example.com")
        client.websocket = websocket
        client.is_connected = True
        client.is_authenticated = True
        client.receive_task = _FakeTask(cancel_raises=True)  # ty: ignore[invalid-assignment]
        client.reconnect_task = _FakeTask(cancel_raises=True)  # ty: ignore[invalid-assignment]

        await client.disconnect()

        assert websocket.closed is True
        assert client.is_connected is False
        assert client.is_authenticated is False
        assert client.websocket is None

    @pytest.mark.asyncio
    async def test_disconnect_without_tasks_or_socket(self) -> None:
        client = WebSocketClient("ws://example.com")

        await client.disconnect()

        assert client.websocket is None
        assert client.is_connected is False
        assert client.is_authenticated is False

    @pytest.mark.asyncio
    async def test_receive_loop_dispatches_and_reconnects(self, monkeypatch: pytest.MonkeyPatch) -> None:
        websocket = _FakeWebSocket(
            iter_messages=[
                WebSocketProtocol.encode(
                    WebSocketProtocol.create_event("event.one", {"value": 1})
                ),
                "not-json",
            ]
        )
        client = WebSocketClient("ws://example.com")
        client.websocket = websocket
        client._handle_message = AsyncMock()  # type: ignore[method-assign]
        monkeypatch.setattr(client_mod.asyncio, "create_task", _create_task)

        await client._receive_loop()

        client._handle_message.assert_awaited_once()
        assert client.is_connected is False
        assert client.is_authenticated is False
        assert client.reconnect_task is not None

    @pytest.mark.asyncio
    async def test_receive_loop_without_reconnect(self) -> None:
        websocket = _FakeWebSocket(iter_messages=[])
        client = WebSocketClient("ws://example.com", reconnect=False)
        client.websocket = websocket

        await client._receive_loop()

        assert client.is_connected is False
        assert client.is_authenticated is False
        assert client.reconnect_task is None

    @pytest.mark.asyncio
    async def test_receive_loop_handles_outer_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        websocket = _ErrorWebSocket()
        client = WebSocketClient("ws://example.com")
        client.websocket = websocket
        monkeypatch.setattr(client_mod.asyncio, "create_task", _create_task)
        client._handle_message = AsyncMock()  # type: ignore[method-assign]

        await client._receive_loop()

        assert client.is_connected is False
        assert client.is_authenticated is False


class TestReconnectAndMessages:
    @pytest.mark.asyncio
    async def test_reconnect_loop_success_and_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = WebSocketClient("wss://example.com", token="t", max_retries=2, initial_delay=0.0)
        client.rooms = {"room-1"}
        websocket = _FakeWebSocket(
            recv_messages=[
                WebSocketProtocol.encode(
                    WebSocketProtocol.create_response(
                        WebSocketProtocol.create_request("auth", {"token": "t"}),
                        {"user_id": "alice"},
                    )
                )
            ]
        )
        _websockets_mock.connect = AsyncMock(return_value=websocket)
        monkeypatch.setattr(client_mod.asyncio, "sleep", AsyncMock())
        monkeypatch.setattr(client_mod.asyncio, "create_task", _create_task)
        client._receive_loop = AsyncMock(return_value=None)  # type: ignore[method-assign]
        client.subscribe_to_room = AsyncMock(return_value=None)  # type: ignore[method-assign]

        await client._reconnect_loop()

        assert client.is_connected is True
        client.subscribe_to_room.assert_awaited_once_with("room-1")

        _websockets_mock.connect = AsyncMock(side_effect=RuntimeError("down"))
        client.max_retries = 1
        client.reconnect_task = None
        await client._reconnect_loop()

    @pytest.mark.asyncio
    async def test_reconnect_loop_without_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = WebSocketClient("ws://example.com", reconnect=True, max_retries=1, initial_delay=0.0)
        websocket = _FakeWebSocket()
        _websockets_mock.connect = AsyncMock(return_value=websocket)
        monkeypatch.setattr(client_mod.asyncio, "sleep", AsyncMock())
        monkeypatch.setattr(client_mod.asyncio, "create_task", _create_task)
        client._receive_loop = AsyncMock(return_value=None)  # type: ignore[method-assign]

        await client._reconnect_loop()

        assert client.is_connected is True
        assert client.is_authenticated is False

    @pytest.mark.asyncio
    async def test_handle_message_paths(self) -> None:
        client = WebSocketClient("ws://example.com")
        future = asyncio.Future()
        client.pending_requests["abc"] = future
        await client._handle_message(
            WebSocketProtocol.create_response(
                WebSocketProtocol.create_request("req", {"x": 1}, correlation_id="abc"),
                {"ok": True},
            )
        )
        assert future.done() is True

        client.event_handlers["evt"] = {AsyncMock()}
        await client._handle_message(WebSocketProtocol.create_event("evt", {"a": 1}))

    @pytest.mark.asyncio
    async def test_handle_message_done_future_and_non_event(self) -> None:
        client = WebSocketClient("ws://example.com")
        future = asyncio.Future()
        future.set_result("done")
        client.pending_requests["abc"] = future
        await client._handle_message(
            WebSocketProtocol.create_response(
                WebSocketProtocol.create_request("req", {"x": 1}, correlation_id="abc"),
                {"ok": True},
            )
        )
        assert future.done() is True

        await client._handle_message(
            WebSocketProtocol.create_response(WebSocketProtocol.create_request("req", {}), {"ok": True})
        )

    @pytest.mark.asyncio
    async def test_emit_event_sync_and_async(self) -> None:
        client = WebSocketClient("ws://example.com")
        hits: list[str] = []

        @client.on_event("evt")
        def sync_handler(data: dict[str, int]) -> None:
            hits.append("sync")

        @client.on_event("evt")
        async def async_handler(data: dict[str, int]) -> None:
            hits.append("async")

        await client._emit_event("evt", {"a": 1})
        assert set(hits) == {"sync", "async"}

    @pytest.mark.asyncio
    async def test_emit_event_missing_and_erroring_handler(self) -> None:
        client = WebSocketClient("ws://example.com")
        client.event_handlers["evt"] = {
            lambda data: (_ for _ in ()).throw(RuntimeError("boom"))
        }

        await client._emit_event("missing", {})
        await client._emit_event("evt", {})

    @pytest.mark.asyncio
    async def test_emit_event_event_without_handlers(self) -> None:
        client = WebSocketClient("ws://example.com")
        await client._emit_event("missing", {})

    @pytest.mark.asyncio
    async def test_send_request_and_send_helpers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        websocket = _FakeWebSocket()
        client = WebSocketClient("ws://example.com")
        client.websocket = websocket
        client.is_connected = True

        response = WebSocketProtocol.create_response(
            WebSocketProtocol.create_request("req", {"x": 1}),
            {"ok": True},
        )
        monkeypatch.setattr(client_mod.asyncio, "wait_for", AsyncMock(return_value=response))

        result = await client.send_request("req", {"x": 1})
        assert result is response
        assert websocket.sent_messages

        await client.send("evt", {"value": 2})
        assert len(websocket.sent_messages) >= 2

    @pytest.mark.asyncio
    async def test_send_raises_when_not_connected(self) -> None:
        client = WebSocketClient("ws://example.com")
        with pytest.raises(ConnectionError, match="Not connected"):
            await client.send("evt", {})

    @pytest.mark.asyncio
    async def test_send_request_raises_when_not_connected(self) -> None:
        client = WebSocketClient("ws://example.com")
        with pytest.raises(ConnectionError, match="Not connected"):
            await client.send_request("evt", {})

    @pytest.mark.asyncio
    async def test_send_request_timeout_cleans_pending(self, monkeypatch: pytest.MonkeyPatch) -> None:
        websocket = _FakeWebSocket()
        client = WebSocketClient("ws://example.com")
        client.websocket = websocket
        client.is_connected = True
        monkeypatch.setattr(client_mod.asyncio, "wait_for", AsyncMock(side_effect=TimeoutError))

        with pytest.raises(TimeoutError, match="timed out"):
            await client.send_request("evt", {}, timeout=0.01)

    @pytest.mark.asyncio
    async def test_subscribe_and_unsubscribe_and_events(self) -> None:
        websocket = _FakeWebSocket()
        client = WebSocketClient("ws://example.com")
        client.websocket = websocket
        client.is_connected = True

        await client.subscribe_to_room("room-1")
        await client.unsubscribe_from_room("room-1")
        assert "room-1" not in client.rooms

        client.send = AsyncMock(return_value=None)  # type: ignore[method-assign]
        client._emit_event = AsyncMock(return_value=None)  # type: ignore[method-assign]
        client.event_handlers["evt"] = {lambda data: None}
        await client._emit_event("missing", {})
