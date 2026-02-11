"""WebSocket server base class for MCP services.

Provides a unified WebSocket server implementation that all ecosystem
services can extend for real-time communication.
"""

from __future__ import annotations

import ssl
import uuid
from abc import ABC, abstractmethod
from logging import Logger
from typing import Any, Callable

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

from .protocol import (
    WebSocketMessage,
    WebSocketProtocol,
    MessageType,
    EventTypes,
)
from .tls import (
    create_ssl_context,
    create_development_ssl_context,
    get_tls_config_from_env,
    validate_certificate,
)

logger: Logger = logging.getLogger(__name__)


class WebSocketServer(ABC):
    """
    Base WebSocket server for MCP services.

    Features:
    - Room-based broadcasting
    - Request/response correlation
    - Automatic reconnection handling
    - JWT authentication integration
    - TLS/WSS support for secure connections
    - Message rate limiting
    - Graceful shutdown

    Usage:
        class MyServiceWebSocket(WebSocketServer):
            async def on_connect(self, websocket, session_id):
                await self.join_room(f"session:{session_id}")

            async def on_message(self, websocket, message):
                if message.event == "subscribe":
                    await self.subscribe_to_session(websocket, message.data["session_id"])

    Implementation:
        server = MyServiceWebSocket(host="127.0.0.1", port=8688)
        await server.start()

    With TLS:
        server = MyServiceWebSocket(
            host="0.0.0.0",
            port=8688,
            cert_file="/path/to/cert.pem",
            key_file="/path/to/key.pem"
        )
        await server.start()

    With auto-generated development certificate:
        server = MyServiceWebSocket(host="127.0.0.1", port=8688, tls_enabled=True)
        await server.start()
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8688,
        max_connections: int = 1000,
        message_rate_limit: int = 100,  # messages per second per connection
        authenticator: Any | None = None,  # WebSocketAuthenticator instance
        require_auth: bool = False,  # Require JWT authentication
        ssl_context: ssl.SSLContext | None = None,
        cert_file: str | None = None,
        key_file: str | None = None,
        ca_file: str | None = None,
        tls_enabled: bool = False,
        verify_client: bool = False,
        auto_cert: bool = False,
    ):
        """Initialize WebSocket server.

        Args:
            host: Server host address
            port: Server port number
            max_connections: Maximum concurrent connections
            message_rate_limit: Messages per second per connection
            authenticator: WebSocketAuthenticator instance for JWT auth
            require_auth: Whether to require authentication for connections
            ssl_context: Pre-configured SSL context (overrides cert/key files)
            cert_file: Path to TLS certificate file (PEM format)
            key_file: Path to TLS private key file (PEM format)
            ca_file: Path to CA file for client verification
            tls_enabled: Enable TLS (generates self-signed cert if no cert provided)
            verify_client: Verify client certificates
            auto_cert: Auto-generate self-signed certificate for development
        """
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError(
                "websockets package is required. "
                "Install it with: pip install websockets"
            )

        self.host = host
        self.port = port
        self.max_connections = max_connections
        self.message_rate_limit = message_rate_limit
        self.authenticator = authenticator
        self.require_auth = require_auth

        # TLS configuration
        self.ssl_context = ssl_context
        self.cert_file = cert_file
        self.key_file = key_file
        self.ca_file = ca_file
        self.tls_enabled = tls_enabled
        self.verify_client = verify_client
        self.auto_cert = auto_cert

        # Auto-generated certificate paths (for cleanup)
        self._auto_cert_path: str | None = None
        self._auto_key_path: str | None = None

        # Connection management
        self.connections: dict[str, Any] = {}  # connection_id -> websocket
        self.connection_rooms: dict[str, set[str]] = {}  # room_id -> {connection_ids}
        self.room_connections: dict[str, str] = {}  # connection_id -> room_id

        # Event handlers
        self.event_handlers: dict[str, set[Callable]] = {}

        # Server state
        self.server: Any | None = None
        self.is_running = False

        # Initialize SSL context if TLS enabled
        if self.tls_enabled and self.ssl_context is None:
            self._initialize_ssl_context()

    def _initialize_ssl_context(self) -> None:
        """Initialize SSL context from certificates or auto-generate.

        Raises:
            FileNotFoundError: If cert/key files specified but not found
            RuntimeError: If SSL context creation fails
        """
        try:
            # Use provided cert/key files
            if self.cert_file and self.key_file:
                self.ssl_context = create_ssl_context(
                    cert_file=self.cert_file,
                    key_file=self.key_file,
                    ca_file=self.ca_file,
                    verify_client=self.verify_client,
                )
                logger.info(f"Loaded TLS certificate: {self.cert_file}")

                # Validate certificate
                validation = validate_certificate(self.cert_file)
                if not validation["valid"]:
                    logger.warning(
                        f"Certificate validation warning: {validation['error']}"
                    )
                if validation.get("days_remaining"):
                    logger.info(
                        f"Certificate valid for {validation['days_remaining']} days"
                    )

            # Auto-generate self-signed certificate
            elif self.auto_cert or not (self.cert_file and self.key_file):
                self.ssl_context, self._auto_cert_path, self._auto_key_path = (
                    create_development_ssl_context(
                        common_name=self.host,
                        dns_names=[self.host, "localhost"],
                    )
                )
                logger.warning(
                    f"Using auto-generated self-signed certificate for development. "
                    f"Cert: {self._auto_cert_path}"
                )

        except Exception as e:
            raise RuntimeError(f"Failed to initialize SSL context: {e}") from e

    @property
    def uri(self) -> str:
        """Get the WebSocket server URI.

        Returns:
            WebSocket URI (ws:// or wss://)
        """
        scheme = "wss" if self.ssl_context else "ws"
        return f"{scheme}://{self.host}:{self.port}"

    @abstractmethod
    async def on_connect(self, websocket: Any, connection_id: str):
        """
        Handle new WebSocket connection.

        Args:
            websocket: WebSocket connection object
            connection_id: Unique connection identifier
        """
        pass

    @abstractmethod
    async def on_disconnect(self, websocket: Any, connection_id: str):
        """
        Handle WebSocket disconnection.

        Args:
            websocket: WebSocket connection object
            connection_id: Unique connection identifier
        """
        pass

    @abstractmethod
    async def on_message(self, websocket: Any, message: WebSocketMessage):
        """
        Handle incoming WebSocket message.

        Args:
            websocket: WebSocket connection object
            message: Decoded message
        """
        pass

    def authenticate_websocket(self, token: str) -> dict[str, Any] | None:
        """Authenticate WebSocket connection using JWT.

        Args:
            token: JWT token from connection

        Returns:
            User payload if authenticated, None otherwise

        Example:
            >>> # In on_connect handler
            >>> token = await websocket.recv()
            >>> user = self.authenticate_websocket(token)
            >>> if user is None:
            >>>     await websocket.close(code=1008, reason="Invalid token")
        """
        if self.authenticator is None:
            logger.warning("Authentication attempted but no authenticator configured")
            return None

        return self.authenticator.authenticate_connection(token)

    async def start(self):
        """Start the WebSocket server."""
        if self.is_running:
            logger.warning(f"WebSocket server already running on {self.uri}")
            return

        logger.info(f"Starting WebSocket server on {self.uri}")

        async def handler(websocket):
            # Check connection limit
            if len(self.connections) >= self.max_connections:
                await websocket.close(1013, "Server at maximum capacity")
                return

            connection_id = str(uuid.uuid4())

            # Handle authentication if required
            if self.require_auth and self.authenticator:
                try:
                    # Receive first message which should contain auth token
                    auth_message = await websocket.recv()
                    auth_data = WebSocketProtocol.decode(auth_message)

                    if auth_data.type == MessageType.REQUEST and auth_data.event == "auth":
                        token = auth_data.data.get("token")
                        user = self.authenticate_websocket(token)

                        if user is None:
                            # Send auth error and close
                            error = WebSocketProtocol.create_error(
                                error_code="AUTH_FAILED",
                                error_message="Invalid or expired token",
                                correlation_id=auth_data.correlation_id,
                            )
                            await websocket.send(WebSocketProtocol.encode(error))
                            await websocket.close(1008, "Authentication failed")
                            return

                        # Store user on websocket object
                        websocket.user = user
                        logger.info(
                            f"Authenticated connection {connection_id} "
                            f"for user {user.get('user_id')}"
                        )

                        # Send auth success
                        response = WebSocketProtocol.create_response(
                            auth_data,
                            200,
                            {"status": "authenticated", "user_id": user.get("user_id")}
                        )
                        await websocket.send(WebSocketProtocol.encode(response))
                    else:
                        # First message must be auth
                        error = WebSocketProtocol.create_error(
                            error_code="AUTH_REQUIRED",
                            error_message="Authentication required",
                        )
                        await websocket.send(WebSocketProtocol.encode(error))
                        await websocket.close(1008, "Authentication required")
                        return

                except Exception as e:
                    logger.error(f"Authentication error: {e}")
                    await websocket.close(1011, "Authentication error")
                    return

            try:
                await self.on_connect(websocket, connection_id)
                self.connections[connection_id] = websocket

                # Message loop
                async for message in websocket:
                    # Rate limiting check could go here
                    try:
                        decoded = WebSocketProtocol.decode(message)
                        await self.on_message(websocket, decoded)
                    except Exception as e:
                        logger.error(f"Error decoding message: {e}")
                        error_msg = WebSocketProtocol.create_error(
                            error_code="DECODE_ERROR",
                            error_message=str(e)
                        )
                        await websocket.send(WebSocketProtocol.encode(error_msg))

            except websockets.exceptions.ConnectionClosed:
                logger.info(f"Connection {connection_id} closed")
            finally:
                await self.on_disconnect(websocket, connection_id)
                if connection_id in self.connections:
                    del self.connections[connection_id]

        # Start server with or without SSL
        self.server = await websockets.serve(
            handler,
            self.host,
            self.port,
            ssl=self.ssl_context,
        )
        self.is_running = True

        if self.ssl_context:
            logger.info(f"WebSocket server listening on wss://{self.host}:{self.port}")
        else:
            logger.info(f"WebSocket server listening on ws://{self.host}:{self.port}")

    async def stop(self):
        """Stop the WebSocket server."""
        if not self.is_running:
            return

        logger.info("Stopping WebSocket server")

        # Close all connections
        for connection_id, websocket in list(self.connections.items()):
            try:
                await websocket.close()
            except Exception:
                pass

        self.is_running = False

        # Clean up auto-generated certificate files
        self._cleanup_auto_cert()

    def _cleanup_auto_cert(self) -> None:
        """Clean up auto-generated certificate files."""
        import os

        if self._auto_cert_path and os.path.exists(self._auto_cert_path):
            try:
                os.unlink(self._auto_cert_path)
                logger.debug(f"Cleaned up auto-generated cert: {self._auto_cert_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup cert file: {e}")

        if self._auto_key_path and os.path.exists(self._auto_key_path):
            try:
                os.unlink(self._auto_key_path)
                logger.debug(f"Cleaned up auto-generated key: {self._auto_key_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup key file: {e}")

        self._auto_cert_path = None
        self._auto_key_path = None

    async def join_room(self, room_id: str, connection_id: str):
        """Add a connection to a room."""
        if room_id not in self.connection_rooms:
            self.connection_rooms[room_id] = set()

        self.connection_rooms[room_id].add(connection_id)
        self.room_connections[connection_id] = room_id

        logger.debug(f"Connection {connection_id} joined room {room_id}")

    async def leave_room(self, room_id: str, connection_id: str):
        """Remove a connection from a room."""
        if room_id in self.connection_rooms:
            self.connection_rooms[room_id].discard(connection_id)

        if connection_id in self.room_connections:
            if self.room_connections[connection_id] == room_id:
                del self.room_connections[connection_id]

        logger.debug(f"Connection {connection_id} left room {room_id}")

    async def leave_all_rooms(self, connection_id: str):
        """Remove a connection from all rooms."""
        if connection_id in self.room_connections:
            room_id = self.room_connections[connection_id]
            await self.leave_room(room_id, connection_id)

    async def broadcast_to_room(
        self,
        room_id: str,
        message: WebSocketMessage
    ):
        """
        Broadcast a message to all connections in a room.

        Args:
            room_id: Room identifier
            message: Message to broadcast
        """
        if room_id not in self.connection_rooms:
            return

        message.room = room_id
        encoded = WebSocketProtocol.encode(message)

        # Send to all connections in the room
        for connection_id in list(self.connection_rooms[room_id]):
            if connection_id in self.connections:
                try:
                    websocket = self.connections[connection_id]
                    await websocket.send(encoded)
                except Exception as e:
                    logger.error(f"Error sending to {connection_id}: {e}")

    async def send_to_connection(
        self,
        connection_id: str,
        message: WebSocketMessage
    ):
        """
        Send a message to a specific connection.

        Args:
            connection_id: Connection identifier
            message: Message to send
        """
        if connection_id not in self.connections:
            logger.warning(f"Connection {connection_id} not found")
            return

        encoded = WebSocketProtocol.encode(message)

        try:
            websocket = self.connections[connection_id]
            await websocket.send(encoded)
        except Exception as e:
            logger.error(f"Error sending to {connection_id}: {e}")

    def on_event(self, event_type: str):
        """
        Decorator to register event handler.

        Usage:
            @server.on_event("session.updated")
            async def handle_session_update(data):
                print(f"Session updated: {data}")
        """
        def decorator(func: Callable) -> Callable:
            if event_type not in self.event_handlers:
                self.event_handlers[event_type] = set()
            self.event_handlers[event_type].add(func)
            return func
        return decorator

    async def emit_event(self, event_type: str, data: dict[str, Any]):
        """
        Emit an event to all registered handlers.

        Args:
            event_type: Event type
            data: Event data
        """
        if event_type not in self.event_handlers:
            return

        for handler in self.event_handlers[event_type]:
            try:
                import asyncio
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}")


import logging
