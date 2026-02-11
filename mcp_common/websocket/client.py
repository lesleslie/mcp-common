"""WebSocket client for MCP services.

Provides automatic reconnection, message correlation, room management,
and TLS/WSS support for services connecting to ecosystem WebSocket servers.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
import uuid
from typing import Any, Callable

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

from .protocol import (
    WebSocketMessage,
    WebSocketProtocol,
    MessageType,
)
from .tls import create_ssl_context, get_tls_config_from_env

logger = logging.getLogger(__name__)


class WebSocketClient:
    """
    WebSocket client with automatic reconnection, JWT authentication, and TLS support.

    Features:
    - Automatic reconnection with exponential backoff
    - Request/response correlation
    - Room subscription management
    - Event handler registration
    - Connection state management
    - JWT authentication support
    - TLS/WSS support for secure connections

    Usage:
        client = WebSocketClient("wss://127.0.0.1:8688", token="your-jwt-token")

        @client.on_event("session.updated")
        async def handle_session_update(data):
            print(f"Session updated: {data}")

        await client.connect()
        await client.subscribe_to_room("session:abc123")

        # Send request
        response = await client.send_request("get_session", {"session_id": "abc123"})

    With custom SSL context:
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE  # For development

        client = WebSocketClient("wss://127.0.0.1:8688", ssl_context=ssl_context)
    """

    def __init__(
        self,
        uri: str,
        token: str | None = None,  # JWT token for authentication
        reconnect: bool = True,
        max_retries: int = 5,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        ssl_context: ssl.SSLContext | None = None,
        verify_ssl: bool = True,
        ca_file: str | None = None,
    ):
        """Initialize WebSocket client.

        Args:
            uri: WebSocket server URI (ws:// or wss://)
            token: JWT token for authentication
            reconnect: Enable automatic reconnection
            max_retries: Maximum reconnection attempts
            initial_delay: Initial reconnection delay in seconds
            max_delay: Maximum reconnection delay in seconds
            ssl_context: Custom SSL context for WSS connections
            verify_ssl: Verify SSL certificates (for WSS)
            ca_file: Path to CA file for SSL verification
        """
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError(
                "websockets package is required. "
                "Install it with: pip install websockets"
            )

        self.uri = uri
        self.token = token
        self.reconnect = reconnect
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay

        # TLS configuration
        self.ssl_context = ssl_context
        self.verify_ssl = verify_ssl
        self.ca_file = ca_file

        # Auto-configure SSL for WSS URIs
        if uri.startswith("wss://") and ssl_context is None:
            self._configure_ssl()

        # Connection state
        self.websocket: Any | None = None
        self.is_connected = False
        self.connection_id: str | None = None
        self.is_authenticated = False

        # Request/response tracking
        self.pending_requests: dict[str, asyncio.Future] = {}
        self.request_timeout: float = 30.0  # seconds

        # Event handlers
        self.event_handlers: dict[str, set[Callable]] = {}
        self.rooms: set[str] = set()

        # Background tasks
        self.receive_task: asyncio.Task | None = None
        self.reconnect_task: asyncio.Task | None = None

    def _configure_ssl(self) -> None:
        """Configure SSL context for WSS connections.

        Creates an SSL context based on verify_ssl and ca_file settings.
        For development with self-signed certificates, set verify_ssl=False.
        """
        if self.verify_ssl:
            # Production mode: verify certificates
            self.ssl_context = ssl.create_default_context(
                ssl.Purpose.SERVER_AUTH,
            )

            # Load custom CA if provided
            if self.ca_file:
                self.ssl_context.load_verify_locations(self.ca_file)
                logger.info(f"Loaded CA certificate: {self.ca_file}")
        else:
            # Development mode: don't verify (for self-signed certs)
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
            logger.warning(
                "SSL verification disabled - use only for development "
                "with self-signed certificates"
            )

    async def connect(self):
        """Connect to the WebSocket server."""
        if self.is_connected:
            logger.warning("Already connected")
            return

        logger.info(f"Connecting to {self.uri}")

        try:
            # Determine SSL parameter from URI scheme or explicit context
            ssl_param = self.ssl_context if self.uri.startswith("wss://") else None

            self.websocket = await websockets.connect(self.uri, ssl=ssl_param)

            # Send authentication if token provided
            if self.token:
                await self._authenticate()

            self.is_connected = True
            self.connection_id = str(uuid.uuid4())

            # Start message receiver
            self.receive_task = asyncio.create_task(self._receive_loop())

            logger.info(f"Connected to {self.uri}")

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            if self.reconnect:
                self.reconnect_task = asyncio.create_task(self._reconnect_loop())
            else:
                raise

    async def _authenticate(self):
        """Send JWT authentication to server."""
        if not self.token:
            return

        try:
            auth_request = WebSocketProtocol.create_request(
                "auth",
                {"token": self.token}
            )
            encoded = WebSocketProtocol.encode(auth_request)
            await self.websocket.send(encoded)

            # Wait for auth response
            response = await self.websocket.recv()
            response_data = WebSocketProtocol.decode(response)

            if response_data.type == MessageType.RESPONSE:
                self.is_authenticated = True
                logger.info(
                    f"Authenticated as {response_data.data.get('user_id')}"
                )
            elif response_data.type == MessageType.ERROR:
                logger.error(f"Authentication failed: {response_data.error_message}")
                raise ConnectionError("Authentication failed")

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise

    async def disconnect(self):
        """Disconnect from the WebSocket server."""
        logger.info("Disconnecting")

        # Cancel background tasks
        if self.receive_task:
            self.receive_task.cancel()
            try:
                await self.receive_task
            except asyncio.CancelledError:
                pass

        if self.reconnect_task:
            self.reconnect_task.cancel()
            try:
                await self.reconnect_task
            except asyncio.CancelledError:
                pass

        # Close connection
        if self.websocket:
            await self.websocket.close()

        self.is_connected = False
        self.is_authenticated = False
        self.websocket = None

    async def _receive_loop(self):
        """Background task to receive and handle messages."""
        try:
            async for message in self.websocket:
                try:
                    decoded = WebSocketProtocol.decode(message)
                    await self._handle_message(decoded)
                except Exception as e:
                    logger.error(f"Error decoding message: {e}")
        except Exception as e:
            logger.error(f"Receive loop error: {e}")
        finally:
            self.is_connected = False
            self.is_authenticated = False

            # Trigger reconnection if enabled
            if self.reconnect:
                self.reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self):
        """Background task to handle reconnection with exponential backoff."""
        delay = self.initial_delay

        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"Reconnection attempt {attempt + 1}/{self.max_retries}"
                )

                await asyncio.sleep(delay)

                # Determine SSL parameter
                ssl_param = self.ssl_context if self.uri.startswith("wss://") else None

                self.websocket = await websockets.connect(self.uri, ssl=ssl_param)

                # Re-authenticate if token provided
                if self.token:
                    await self._authenticate()

                self.is_connected = True
                self.connection_id = str(uuid.uuid4())

                # Restart receive loop
                self.receive_task = asyncio.create_task(self._receive_loop())

                # Re-subscribe to rooms
                for room in self.rooms:
                    await self.subscribe_to_room(room)

                logger.info(f"Reconnected to {self.uri}")
                return

            except Exception as e:
                logger.error(f"Reconnection attempt {attempt + 1} failed: {e}")

                # Exponential backoff
                delay = min(delay * 2, self.max_delay)

        logger.error("Max reconnection attempts reached")

    async def _handle_message(self, message: WebSocketMessage):
        """Handle incoming message.

        Args:
            message: Decoded WebSocket message
        """
        # Check if it's a response to a pending request
        if message.correlation_id and message.correlation_id in self.pending_requests:
            future = self.pending_requests.pop(message.correlation_id)
            if not future.done():
                future.set_result(message)

        # Check if it's an event
        elif message.type == MessageType.EVENT and message.event:
            await self._emit_event(message.event, message.data)

    async def _emit_event(self, event_type: str, data: dict[str, Any]):
        """Emit event to registered handlers.

        Args:
            event_type: Event type name
            data: Event data payload
        """
        if event_type not in self.event_handlers:
            return

        for handler in self.event_handlers[event_type]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}")

    async def send_request(
        self,
        event: str,
        data: dict[str, Any],
        timeout: float | None = None
    ) -> WebSocketMessage:
        """
        Send a request and wait for response.

        Args:
            event: Event/request name
            data: Request data
            timeout: Request timeout in seconds

        Returns:
            Response message

        Raises:
            ConnectionError: If not connected
            TimeoutError: If request times out
        """
        if not self.is_connected:
            raise ConnectionError("Not connected")

        request = WebSocketProtocol.create_request(event, data)
        encoded = WebSocketProtocol.encode(request)

        # Create future for response
        future = asyncio.Future()
        self.pending_requests[request.id] = future

        try:
            await self.websocket.send(encoded)

            # Wait for response with timeout
            timeout = timeout or self.request_timeout
            response = await asyncio.wait_for(future, timeout=timeout)

            return response

        except asyncio.TimeoutError:
            self.pending_requests.pop(request.id, None)
            raise TimeoutError(f"Request {event} timed out after {timeout}s")

        finally:
            self.pending_requests.pop(request.id, None)

    async def send(self, event: str, data: dict[str, Any]):
        """
        Send an event message (no response expected).

        Args:
            event: Event name
            data: Event data

        Raises:
            ConnectionError: If not connected
        """
        if not self.is_connected:
            raise ConnectionError("Not connected")

        message = WebSocketProtocol.create_event(event, data)
        encoded = WebSocketProtocol.encode(message)

        await self.websocket.send(encoded)

    async def subscribe_to_room(self, room_id: str):
        """
        Subscribe to a room to receive broadcasted events.

        Args:
            room_id: Room identifier

        Example:
            >>> await client.subscribe_to_room("session:abc123")
            >>> await client.subscribe_to_room("pool:pool_1")
        """
        await self.send("subscribe", {"room": room_id})
        self.rooms.add(room_id)
        logger.debug(f"Subscribed to room {room_id}")

    async def unsubscribe_from_room(self, room_id: str):
        """
        Unsubscribe from a room.

        Args:
            room_id: Room identifier
        """
        await self.send("unsubscribe", {"room": room_id})
        self.rooms.discard(room_id)
        logger.debug(f"Unsubscribed from room {room_id}")

    def on_event(self, event_type: str):
        """
        Decorator to register event handler.

        Usage:
            @client.on_event("session.updated")
            async def handle_session_update(data):
                print(f"Session updated: {data}")

        Args:
            event_type: Event type to handle

        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            if event_type not in self.event_handlers:
                self.event_handlers[event_type] = set()
            self.event_handlers[event_type].add(func)
            return func
        return decorator

    @property
    def is_secure(self) -> bool:
        """Check if connection is using WSS (secure)."""
        return self.uri.startswith("wss://")
