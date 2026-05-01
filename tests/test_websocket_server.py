"""Tests for mcp_common.websocket.server.WebSocketServer."""

from __future__ import annotations

import asyncio
import ssl
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module-level mock: ensure websockets is never actually imported.
# This must happen BEFORE any import of the server module.
# ---------------------------------------------------------------------------
_websockets_mock = MagicMock()
with patch.dict("sys.modules", {"websockets": _websockets_mock}):
    from mcp_common.websocket.protocol import (
        MessageType,
        WebSocketMessage,
        WebSocketProtocol,
    )
    from mcp_common.websocket.server import WebSocketServer
    # Import the server module itself so we can patch attributes on it.
    import mcp_common.websocket.server as _server_mod


# ---------------------------------------------------------------------------
# Concrete subclass so we can instantiate the ABC
# ---------------------------------------------------------------------------

class ConcreteServer(WebSocketServer):
    """Minimal concrete implementation for testing."""

    async def on_connect(self, websocket: Any, connection_id: str) -> None:
        pass

    async def on_disconnect(self, websocket: Any, connection_id: str) -> None:
        pass

    async def on_message(self, websocket: Any, message: WebSocketMessage) -> None:
        pass


# ===================================================================
# 1. Constructor defaults and custom params
# ===================================================================

class TestConstructor:
    """Tests for __init__ parameter handling."""

    def test_default_values(self) -> None:
        srv = ConcreteServer()
        assert srv.host == "127.0.0.1"
        assert srv.port == 8688
        assert srv.max_connections == 1000
        assert srv.message_rate_limit == 100
        assert srv.authenticator is None
        assert srv.require_auth is False
        assert srv.ssl_context is None
        assert srv.cert_file is None
        assert srv.key_file is None
        assert srv.ca_file is None
        assert srv.tls_enabled is False
        assert srv.verify_client is False
        assert srv.auto_cert is False
        assert srv.server_name == "ConcreteServer"
        assert srv.enable_metrics is False
        assert srv.metrics_port == 9090

    def test_custom_values(self) -> None:
        mock_auth = MagicMock()
        fake_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        srv = ConcreteServer(
            host="0.0.0.0",
            port=9090,
            max_connections=500,
            message_rate_limit=50,
            authenticator=mock_auth,
            require_auth=True,
            ssl_context=fake_ctx,
            cert_file="/tmp/cert.pem",
            key_file="/tmp/key.pem",
            ca_file="/tmp/ca.pem",
            tls_enabled=True,
            verify_client=True,
            auto_cert=True,
            server_name="custom-name",
            enable_metrics=True,
            metrics_port=8080,
        )
        assert srv.host == "0.0.0.0"
        assert srv.port == 9090
        assert srv.max_connections == 500
        assert srv.message_rate_limit == 50
        assert srv.authenticator is mock_auth
        assert srv.require_auth is True
        assert srv.ssl_context is fake_ctx
        assert srv.cert_file == "/tmp/cert.pem"
        assert srv.key_file == "/tmp/key.pem"
        assert srv.ca_file == "/tmp/ca.pem"
        assert srv.tls_enabled is True
        assert srv.verify_client is True
        assert srv.auto_cert is True
        assert srv.server_name == "custom-name"
        assert srv.enable_metrics is True
        assert srv.metrics_port == 8080

    def test_initial_state(self) -> None:
        srv = ConcreteServer()
        assert srv.connections == {}
        assert srv.connection_rooms == {}
        assert srv.room_connections == {}
        assert srv.event_handlers == {}
        assert srv.server is None
        assert srv.is_running is False
        assert srv._auto_cert_path is None
        assert srv._auto_key_path is None


# ===================================================================
# 2. URI property
# ===================================================================

class TestUriProperty:
    """Tests for the uri property."""

    def test_ws_scheme_when_no_ssl(self) -> None:
        srv = ConcreteServer(host="127.0.0.1", port=8688)
        assert srv.uri == "ws://127.0.0.1:8688"

    def test_wss_scheme_with_ssl_context(self) -> None:
        fake_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        srv = ConcreteServer(host="0.0.0.0", port=443, ssl_context=fake_ctx)
        assert srv.uri == "wss://0.0.0.0:443"


# ===================================================================
# 3. ImportError when websockets not available
# ===================================================================

class TestImportError:
    """Tests for the ImportError guard."""

    def test_raises_import_error_without_websockets(self) -> None:
        """Ensure ImportError is raised when websockets is not importable."""
        # Patch the module-level flag directly on the already-loaded module.
        original = _server_mod.WEBSOCKETS_AVAILABLE
        _server_mod.WEBSOCKETS_AVAILABLE = False
        try:
            with pytest.raises(ImportError, match="websockets package is required"):
                ConcreteServer()
        finally:
            _server_mod.WEBSOCKETS_AVAILABLE = original


# ===================================================================
# 4. authenticate_websocket
# ===================================================================

class TestAuthenticateWebSocket:
    """Tests for the authenticate_websocket method."""

    def test_returns_none_when_no_authenticator(self) -> None:
        srv = ConcreteServer(authenticator=None)
        result = srv.authenticate_websocket("some-token")
        assert result is None

    def test_delegates_to_authenticator(self) -> None:
        mock_auth = MagicMock()
        mock_auth.authenticate_connection.return_value = {"user_id": "alice"}
        srv = ConcreteServer(authenticator=mock_auth)
        result = srv.authenticate_websocket("good-token")
        assert result == {"user_id": "alice"}
        mock_auth.authenticate_connection.assert_called_once_with("good-token")

    def test_returns_none_on_failed_auth(self) -> None:
        mock_auth = MagicMock()
        mock_auth.authenticate_connection.return_value = None
        srv = ConcreteServer(authenticator=mock_auth)
        result = srv.authenticate_websocket("bad-token")
        assert result is None


# ===================================================================
# 5. Room management
# ===================================================================

class TestRoomManagement:
    """Tests for join_room, leave_room, leave_all_rooms."""

    @pytest.mark.asyncio
    async def test_join_room_creates_room(self) -> None:
        srv = ConcreteServer()
        await srv.join_room("room1", "conn1")
        assert "room1" in srv.connection_rooms
        assert "conn1" in srv.connection_rooms["room1"]
        assert srv.room_connections["conn1"] == "room1"

    @pytest.mark.asyncio
    async def test_join_room_adds_to_existing_room(self) -> None:
        srv = ConcreteServer()
        await srv.join_room("room1", "conn1")
        await srv.join_room("room1", "conn2")
        assert srv.connection_rooms["room1"] == {"conn1", "conn2"}

    @pytest.mark.asyncio
    async def test_leave_room(self) -> None:
        srv = ConcreteServer()
        await srv.join_room("room1", "conn1")
        await srv.leave_room("room1", "conn1")
        assert "conn1" not in srv.connection_rooms["room1"]
        assert "conn1" not in srv.room_connections

    @pytest.mark.asyncio
    async def test_leave_room_nonexistent_room(self) -> None:
        """Leaving a room that doesn't exist should not raise."""
        srv = ConcreteServer()
        srv.room_connections["conn1"] = "room1"
        await srv.leave_room("nonexistent", "conn1")
        # room_connections should NOT be cleared because the room doesn't match
        assert srv.room_connections.get("conn1") == "room1"

    @pytest.mark.asyncio
    async def test_leave_room_different_room(self) -> None:
        """Leaving room X should not clear room_connections if conn is in room Y."""
        srv = ConcreteServer()
        srv.room_connections["conn1"] = "room2"
        await srv.leave_room("room1", "conn1")
        # conn1 is in room2, leaving room1 should not remove it
        assert srv.room_connections.get("conn1") == "room2"

    @pytest.mark.asyncio
    async def test_leave_all_rooms(self) -> None:
        srv = ConcreteServer()
        await srv.join_room("room1", "conn1")
        await srv.leave_all_rooms("conn1")
        assert "conn1" not in srv.connection_rooms.get("room1", set())
        assert "conn1" not in srv.room_connections

    @pytest.mark.asyncio
    async def test_leave_all_rooms_no_rooms(self) -> None:
        """leave_all_rooms on a connection with no rooms should not raise."""
        srv = ConcreteServer()
        await srv.leave_all_rooms("conn1")  # Should not raise


# ===================================================================
# 6. broadcast_to_room
# ===================================================================

class TestBroadcastToRoom:
    """Tests for broadcast_to_room."""

    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_room(self) -> None:
        """Broadcasting to a room that doesn't exist should silently return."""
        srv = ConcreteServer()
        msg = WebSocketProtocol.create_event("test.event", {"key": "val"})
        await srv.broadcast_to_room("no_room", msg)
        # No error raised

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_room(self) -> None:
        """Broadcasting to an empty room should succeed."""
        srv = ConcreteServer()
        srv.connection_rooms["room1"] = set()
        msg = WebSocketProtocol.create_event("test.event", {"key": "val"})
        await srv.broadcast_to_room("room1", msg)
        # No error raised

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_connections(self) -> None:
        srv = ConcreteServer()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        srv.connections = {"conn1": ws1, "conn2": ws2}
        srv.connection_rooms = {"room1": {"conn1", "conn2"}}

        msg = WebSocketProtocol.create_event("test.event", {"key": "val"})
        await srv.broadcast_to_room("room1", msg)

        ws1.send.assert_called_once()
        ws2.send.assert_called_once()
        # Verify the room field was set
        sent_data = ws1.send.call_args[0][0]
        decoded = WebSocketProtocol.decode(sent_data)
        assert decoded.room == "room1"

    @pytest.mark.asyncio
    async def test_broadcast_skips_disconnected(self) -> None:
        """Connections in room but not in self.connections are skipped."""
        srv = ConcreteServer()
        ws1 = AsyncMock()
        srv.connections = {"conn1": ws1}
        srv.connection_rooms = {"room1": {"conn1", "conn2"}}

        msg = WebSocketProtocol.create_event("test.event", {})
        await srv.broadcast_to_room("room1", msg)

        ws1.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_handles_send_error(self) -> None:
        """Send errors on individual connections should not stop the broadcast."""
        srv = ConcreteServer()
        ws1 = AsyncMock()
        ws1.send.side_effect = RuntimeError("send failed")
        ws2 = AsyncMock()
        srv.connections = {"conn1": ws1, "conn2": ws2}
        srv.connection_rooms = {"room1": {"conn1", "conn2"}}

        msg = WebSocketProtocol.create_event("test.event", {})
        await srv.broadcast_to_room("room1", msg)

        ws2.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_records_metrics(self) -> None:
        srv = ConcreteServer(enable_metrics=True)
        srv.metrics = MagicMock()
        ws1 = AsyncMock()
        srv.connections = {"conn1": ws1}
        srv.connection_rooms = {"room1": {"conn1"}}

        msg = WebSocketProtocol.create_event("test.event", {})
        await srv.broadcast_to_room("room1", msg)

        srv.metrics.on_broadcast.assert_called_once()
        call_args = srv.metrics.on_broadcast.call_args
        assert call_args[0][0] == "room1"
        assert isinstance(call_args[0][1], float)


# ===================================================================
# 7. send_to_connection
# ===================================================================

class TestSendToConnection:
    """Tests for send_to_connection."""

    @pytest.mark.asyncio
    async def test_send_to_unknown_connection(self) -> None:
        """Sending to a non-existent connection should silently return."""
        srv = ConcreteServer()
        msg = WebSocketProtocol.create_event("test.event", {})
        await srv.send_to_connection("nope", msg)

    @pytest.mark.asyncio
    async def test_send_success(self) -> None:
        srv = ConcreteServer()
        ws = AsyncMock()
        srv.connections = {"conn1": ws}

        msg = WebSocketProtocol.create_event("test.event", {"data": 1})
        await srv.send_to_connection("conn1", msg)

        ws.send.assert_called_once()
        sent_data = ws.send.call_args[0][0]
        decoded = WebSocketProtocol.decode(sent_data)
        assert decoded.event == "test.event"
        assert decoded.data == {"data": 1}

    @pytest.mark.asyncio
    async def test_send_error_handling(self) -> None:
        srv = ConcreteServer()
        ws = AsyncMock()
        ws.send.side_effect = RuntimeError("connection lost")
        srv.connections = {"conn1": ws}

        msg = WebSocketProtocol.create_event("test.event", {})
        await srv.send_to_connection("conn1", msg)  # Should not raise

    @pytest.mark.asyncio
    async def test_send_records_metrics(self) -> None:
        srv = ConcreteServer(enable_metrics=True)
        srv.metrics = MagicMock()
        ws = AsyncMock()
        srv.connections = {"conn1": ws}

        msg = WebSocketProtocol.create_event("test.event", {})
        await srv.send_to_connection("conn1", msg)

        srv.metrics.on_message_sent.assert_called_once_with(str(MessageType.EVENT))

    @pytest.mark.asyncio
    async def test_send_records_error_metric(self) -> None:
        srv = ConcreteServer(enable_metrics=True)
        srv.metrics = MagicMock()
        ws = AsyncMock()
        ws.send.side_effect = RuntimeError("fail")
        srv.connections = {"conn1": ws}

        msg = WebSocketProtocol.create_event("test.event", {})
        await srv.send_to_connection("conn1", msg)

        srv.metrics.on_message_error.assert_called_once_with("send_failed")


# ===================================================================
# 8. on_event decorator
# ===================================================================

class TestOnEventDecorator:
    """Tests for the on_event decorator."""

    def test_register_handler(self) -> None:
        srv = ConcreteServer()

        @srv.on_event("session.updated")
        def handler(data: Any) -> None:
            pass

        assert "session.updated" in srv.event_handlers
        assert handler in srv.event_handlers["session.updated"]

    def test_register_multiple_handlers_same_event(self) -> None:
        srv = ConcreteServer()

        @srv.on_event("session.updated")
        def handler1(data: Any) -> None:
            pass

        @srv.on_event("session.updated")
        def handler2(data: Any) -> None:
            pass

        assert len(srv.event_handlers["session.updated"]) == 2

    def test_register_different_events(self) -> None:
        srv = ConcreteServer()

        @srv.on_event("event.a")
        def handler_a(data: Any) -> None:
            pass

        @srv.on_event("event.b")
        def handler_b(data: Any) -> None:
            pass

        assert "event.a" in srv.event_handlers
        assert "event.b" in srv.event_handlers

    def test_decorator_returns_original_function(self) -> None:
        srv = ConcreteServer()

        def original(data: Any) -> None:
            pass

        decorated = srv.on_event("test")(original)
        assert decorated is original


# ===================================================================
# 9. emit_event
# ===================================================================

class TestEmitEvent:
    """Tests for emit_event with sync/async handlers."""

    @pytest.mark.asyncio
    async def test_emit_no_handlers(self) -> None:
        srv = ConcreteServer()
        await srv.emit_event("nonexistent", {"key": "val"})  # Should not raise

    @pytest.mark.asyncio
    async def test_emit_sync_handler(self) -> None:
        srv = ConcreteServer()
        results: list[dict[str, Any]] = []

        @srv.on_event("sync.event")
        def sync_handler(data: Any) -> None:
            results.append(data)

        await srv.emit_event("sync.event", {"value": 42})
        assert len(results) == 1
        assert results[0] == {"value": 42}

    @pytest.mark.asyncio
    async def test_emit_async_handler(self) -> None:
        srv = ConcreteServer()
        results: list[dict[str, Any]] = []

        @srv.on_event("async.event")
        async def async_handler(data: Any) -> None:
            results.append(data)

        await srv.emit_event("async.event", {"value": 99})
        assert len(results) == 1
        assert results[0] == {"value": 99}

    @pytest.mark.asyncio
    async def test_emit_calls_all_handlers(self) -> None:
        srv = ConcreteServer()
        call_order: list[str] = []

        @srv.on_event("multi.event")
        def handler1(data: Any) -> None:
            call_order.append("sync")

        @srv.on_event("multi.event")
        async def handler2(data: Any) -> None:
            call_order.append("async")

        await srv.emit_event("multi.event", {})
        assert call_order == ["sync", "async"]

    @pytest.mark.asyncio
    async def test_emit_handler_error_does_not_stop_others(self) -> None:
        srv = ConcreteServer()
        results: list[str] = []

        @srv.on_event("error.event")
        def failing_handler(data: Any) -> None:
            raise RuntimeError("handler error")

        @srv.on_event("error.event")
        def ok_handler(data: Any) -> None:
            results.append("ok")

        await srv.emit_event("error.event", {})
        assert results == ["ok"]

    @pytest.mark.asyncio
    async def test_emit_async_handler_error_does_not_stop_others(self) -> None:
        srv = ConcreteServer()
        results: list[str] = []

        @srv.on_event("async.error.event")
        async def failing_handler(data: Any) -> None:
            raise RuntimeError("async handler error")

        @srv.on_event("async.error.event")
        async def ok_handler(data: Any) -> None:
            results.append("ok")

        await srv.emit_event("async.error.event", {})
        assert results == ["ok"]


# ===================================================================
# 10. _cleanup_auto_cert
# ===================================================================

class TestCleanupAutoCert:
    """Tests for _cleanup_auto_cert with temporary files."""

    def test_cleanup_removes_cert_and_key_files(self, tmp_path: Any) -> None:
        cert_file = tmp_path / "auto_cert.pem"
        key_file = tmp_path / "auto_key.pem"
        cert_file.write_text("cert data")
        key_file.write_text("key data")

        srv = ConcreteServer()
        srv._auto_cert_path = str(cert_file)
        srv._auto_key_path = str(key_file)

        srv._cleanup_auto_cert()

        assert not cert_file.exists()
        assert not key_file.exists()
        assert srv._auto_cert_path is None
        assert srv._auto_key_path is None

    def test_cleanup_handles_missing_files(self, tmp_path: Any) -> None:
        """Missing files should not cause errors."""
        srv = ConcreteServer()
        srv._auto_cert_path = str(tmp_path / "nonexistent_cert.pem")
        srv._auto_key_path = str(tmp_path / "nonexistent_key.pem")

        srv._cleanup_auto_cert()  # Should not raise

        assert srv._auto_cert_path is None
        assert srv._auto_key_path is None

    def test_cleanup_handles_none_paths(self) -> None:
        srv = ConcreteServer()
        srv._auto_cert_path = None
        srv._auto_key_path = None
        srv._cleanup_auto_cert()  # Should not raise

    def test_cleanup_handles_readonly_file(self, tmp_path: Any) -> None:
        """Unlink failure should be caught and logged, not raised."""
        import os
        import stat

        cert_file = tmp_path / "readonly_cert.pem"
        cert_file.write_text("cert data")
        # Make file read-only
        os.chmod(str(cert_file), stat.S_IRUSR)

        srv = ConcreteServer()
        srv._auto_cert_path = str(cert_file)
        srv._auto_key_path = None

        # On macOS, unlink of a read-only file may still succeed if the
        # directory is writable.  The test verifies no exception propagates.
        srv._cleanup_auto_cert()  # Should not raise

        assert srv._auto_cert_path is None


# ===================================================================
# 11. SSL context initialization
# ===================================================================

class TestInitializeSslContext:
    """Tests for _initialize_ssl_context."""

    def test_with_cert_and_key_files(self) -> None:
        mock_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        mock_validation = {"valid": True, "days_remaining": 300}

        orig_create = _server_mod.create_ssl_context
        orig_validate = _server_mod.validate_certificate
        mock_create = MagicMock(return_value=mock_ctx)
        mock_validate = MagicMock(return_value=mock_validation)
        _server_mod.create_ssl_context = mock_create
        _server_mod.validate_certificate = mock_validate
        try:
            srv = ConcreteServer(
                cert_file="/path/cert.pem",
                key_file="/path/key.pem",
                tls_enabled=True,
            )
        finally:
            _server_mod.create_ssl_context = orig_create
            _server_mod.validate_certificate = orig_validate

        assert srv.ssl_context is mock_ctx
        mock_create.assert_called_with(
            cert_file="/path/cert.pem",
            key_file="/path/key.pem",
            ca_file=None,
            verify_client=False,
        )
        mock_validate.assert_called_with("/path/cert.pem")

    def test_auto_generate_cert(self) -> None:
        mock_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

        orig_dev = _server_mod.create_development_ssl_context
        mock_dev = MagicMock(
            return_value=(mock_ctx, "/tmp/cert.pem", "/tmp/key.pem")
        )
        _server_mod.create_development_ssl_context = mock_dev
        try:
            srv = ConcreteServer(tls_enabled=True, auto_cert=True)
        finally:
            _server_mod.create_development_ssl_context = orig_dev

        assert srv.ssl_context is mock_ctx
        assert srv._auto_cert_path == "/tmp/cert.pem"
        assert srv._auto_key_path == "/tmp/key.pem"
        mock_dev.assert_called_with(
            common_name="127.0.0.1",
            dns_names=["127.0.0.1", "localhost"],
        )

    def test_with_ca_file(self) -> None:
        mock_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        mock_validation = {"valid": True}

        orig_create = _server_mod.create_ssl_context
        orig_validate = _server_mod.validate_certificate
        _server_mod.create_ssl_context = MagicMock(return_value=mock_ctx)
        _server_mod.validate_certificate = MagicMock(return_value=mock_validation)
        try:
            srv = ConcreteServer(
                cert_file="/path/cert.pem",
                key_file="/path/key.pem",
                ca_file="/path/ca.pem",
                tls_enabled=True,
                verify_client=True,
            )
        finally:
            _server_mod.create_ssl_context = orig_create
            _server_mod.validate_certificate = orig_validate

        assert srv.ssl_context is mock_ctx

    def test_ssl_context_provided_skips_init(self) -> None:
        """If ssl_context is already set, _initialize_ssl_context should not run."""
        mock_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        orig_create = _server_mod.create_ssl_context
        mock_create = MagicMock()
        _server_mod.create_ssl_context = mock_create
        try:
            srv = ConcreteServer(
                ssl_context=mock_ctx,
                tls_enabled=True,
            )
        finally:
            _server_mod.create_ssl_context = orig_create

        # create_ssl_context should NOT be called since ssl_context was provided
        mock_create.assert_not_called()
        assert srv.ssl_context is mock_ctx

    def test_validation_warning(self) -> None:
        mock_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        mock_validation = {"valid": False, "error": "Certificate expires in 5 days"}

        orig_create = _server_mod.create_ssl_context
        orig_validate = _server_mod.validate_certificate
        _server_mod.create_ssl_context = MagicMock(return_value=mock_ctx)
        _server_mod.validate_certificate = MagicMock(return_value=mock_validation)
        try:
            srv = ConcreteServer(
                cert_file="/path/cert.pem",
                key_file="/path/key.pem",
                tls_enabled=True,
            )
        finally:
            _server_mod.create_ssl_context = orig_create
            _server_mod.validate_certificate = orig_validate

        assert srv.ssl_context is mock_ctx


# ===================================================================
# 12. _initialize_ssl_context error handling
# ===================================================================

class TestInitializeSslContextErrors:
    """Tests for error handling in _initialize_ssl_context."""

    def test_runtime_error_on_creation_failure(self) -> None:
        orig_dev = _server_mod.create_development_ssl_context
        _server_mod.create_development_ssl_context = MagicMock(
            side_effect=RuntimeError("cert generation failed")
        )
        try:
            with pytest.raises(RuntimeError, match="Failed to initialize SSL context"):
                ConcreteServer(tls_enabled=True, auto_cert=True)
        finally:
            _server_mod.create_development_ssl_context = orig_dev

    def test_runtime_error_on_cert_file_not_found(self) -> None:
        orig_create = _server_mod.create_ssl_context
        _server_mod.create_ssl_context = MagicMock(
            side_effect=FileNotFoundError("cert not found")
        )
        try:
            with pytest.raises(RuntimeError, match="Failed to initialize SSL context"):
                ConcreteServer(
                    cert_file="/missing/cert.pem",
                    key_file="/missing/key.pem",
                    tls_enabled=True,
                )
        finally:
            _server_mod.create_ssl_context = orig_create

    def test_runtime_error_wraps_original(self) -> None:
        original_error = FileNotFoundError("bad cert")
        orig_create = _server_mod.create_ssl_context
        _server_mod.create_ssl_context = MagicMock(side_effect=original_error)
        try:
            with pytest.raises(RuntimeError) as exc_info:
                ConcreteServer(
                    cert_file="/bad/cert.pem",
                    key_file="/bad/key.pem",
                    tls_enabled=True,
                )
            assert exc_info.value.__cause__ is original_error
        finally:
            _server_mod.create_ssl_context = orig_create


# ===================================================================
# 13. Connection management
# ===================================================================

class TestConnectionManagement:
    """Tests for connection tracking and max_connections."""

    def test_connections_dict(self) -> None:
        srv = ConcreteServer()
        assert isinstance(srv.connections, dict)
        assert len(srv.connections) == 0

    def test_max_connections_default(self) -> None:
        srv = ConcreteServer()
        assert srv.max_connections == 1000

    def test_max_connections_custom(self) -> None:
        srv = ConcreteServer(max_connections=42)
        assert srv.max_connections == 42

    def test_connection_room_tracking(self) -> None:
        srv = ConcreteServer()
        assert isinstance(srv.connection_rooms, dict)
        assert isinstance(srv.room_connections, dict)


# ===================================================================
# 14. Metrics initialization
# ===================================================================

class TestMetricsInitialization:
    """Tests for metrics initialization."""

    def test_metrics_disabled_by_default(self) -> None:
        srv = ConcreteServer()
        assert srv.enable_metrics is False
        assert srv.metrics is None

    def test_metrics_enabled_creates_instance(self) -> None:
        orig_cls = _server_mod.WebSocketMetrics
        mock_metrics_cls = MagicMock()
        mock_instance = MagicMock()
        mock_metrics_cls.return_value = mock_instance
        _server_mod.WebSocketMetrics = mock_metrics_cls
        try:
            srv = ConcreteServer(enable_metrics=True)
            mock_metrics_cls.assert_called_with(
                server_name="ConcreteServer",
                tls_enabled=False,
                enabled=True,
            )
            assert srv.metrics is mock_instance
        finally:
            _server_mod.WebSocketMetrics = orig_cls

    def test_metrics_with_tls(self) -> None:
        fake_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        orig_cls = _server_mod.WebSocketMetrics
        mock_metrics_cls = MagicMock()
        _server_mod.WebSocketMetrics = mock_metrics_cls
        try:
            ConcreteServer(enable_metrics=True, ssl_context=fake_ctx)
            mock_metrics_cls.assert_called_with(
                server_name="ConcreteServer",
                tls_enabled=True,
                enabled=True,
            )
        finally:
            _server_mod.WebSocketMetrics = orig_cls

    def test_metrics_custom_server_name(self) -> None:
        orig_cls = _server_mod.WebSocketMetrics
        mock_metrics_cls = MagicMock()
        _server_mod.WebSocketMetrics = mock_metrics_cls
        try:
            ConcreteServer(enable_metrics=True, server_name="MyServer")
            mock_metrics_cls.assert_called_with(
                server_name="MyServer",
                tls_enabled=False,
                enabled=True,
            )
        finally:
            _server_mod.WebSocketMetrics = orig_cls

    def test_server_name_defaults_to_class_name(self) -> None:
        srv = ConcreteServer()
        assert srv.server_name == "ConcreteServer"


# ===================================================================
# 15. stop method
# ===================================================================

class TestStop:
    """Tests for the stop method."""

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self) -> None:
        srv = ConcreteServer()
        srv.is_running = False
        await srv.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_stop_closes_connections(self) -> None:
        srv = ConcreteServer()
        srv.is_running = True
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        srv.connections = {"conn1": ws1, "conn2": ws2}

        await srv.stop()

        ws1.close.assert_called_once()
        ws2.close.assert_called_once()
        assert srv.is_running is False

    @pytest.mark.asyncio
    async def test_stop_handles_close_error(self) -> None:
        srv = ConcreteServer()
        srv.is_running = True
        ws = AsyncMock()
        ws.close.side_effect = RuntimeError("already closed")
        srv.connections = {"conn1": ws}

        await srv.stop()  # Should not raise
        assert srv.is_running is False

    @pytest.mark.asyncio
    async def test_stop_calls_cleanup_auto_cert(self) -> None:
        srv = ConcreteServer()
        srv.is_running = True
        srv._cleanup_auto_cert = MagicMock()  # type: ignore[method-assign]

        await srv.stop()

        srv._cleanup_auto_cert.assert_called_once()
        assert srv.is_running is False


# ===================================================================
# 16. start method (partial)
# ===================================================================

class TestStart:
    """Tests for the start method (non-network parts)."""

    @pytest.mark.asyncio
    async def test_start_already_running(self) -> None:
        srv = ConcreteServer()
        srv.is_running = True
        await srv.start()  # Should return early
        assert srv.is_running is True

    @pytest.mark.asyncio
    async def test_start_starts_metrics_server(self) -> None:
        srv = ConcreteServer(enable_metrics=True)
        srv.metrics = MagicMock()

        mock_serve = AsyncMock()
        mock_serve.return_value = MagicMock()
        _websockets_mock.serve = mock_serve

        await srv.start()

        srv.metrics.start_metrics_server.assert_called_once_with(srv.metrics_port)
        assert srv.is_running is True

    @pytest.mark.asyncio
    async def test_start_without_metrics(self) -> None:
        srv = ConcreteServer(enable_metrics=False)

        mock_serve = AsyncMock()
        mock_serve.return_value = MagicMock()
        _websockets_mock.serve = mock_serve

        await srv.start()

        assert srv.is_running is True
        mock_serve.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_passes_ssl_context(self) -> None:
        fake_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        srv = ConcreteServer(ssl_context=fake_ctx)

        mock_serve = AsyncMock()
        mock_serve.return_value = MagicMock()
        _websockets_mock.serve = mock_serve

        await srv.start()

        call_kwargs = mock_serve.call_args
        assert call_kwargs[1]["ssl"] is fake_ctx

    @pytest.mark.asyncio
    async def test_start_no_ssl(self) -> None:
        srv = ConcreteServer()

        mock_serve = AsyncMock()
        mock_serve.return_value = MagicMock()
        _websockets_mock.serve = mock_serve

        await srv.start()

        call_kwargs = mock_serve.call_args
        assert call_kwargs[1]["ssl"] is None

    @pytest.mark.asyncio
    async def test_start_sets_is_running(self) -> None:
        srv = ConcreteServer()

        mock_serve = AsyncMock()
        mock_serve.return_value = MagicMock()
        _websockets_mock.serve = mock_serve

        await srv.start()

        assert srv.is_running is True
        assert srv.server is not None
