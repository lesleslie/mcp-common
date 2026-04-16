"""WebSocket abstraction layer for MCP servers.

This module provides a unified WebSocket interface for all ecosystem services,
enabling real-time bidirectional communication with consistent patterns.

Follows WebSocket Analysis implementation plan from docs/WEBSOCKET_ANALYSIS.md
"""

from . import metrics, tls
from .auth import WebSocketAuthenticator, generate_test_token
from .client import WebSocketClient
from .protocol import (
    EventTypes,
    MessageType,
    WebSocketMessage,
    WebSocketProtocol,
)
from .server import WebSocketServer

__all__ = [
    "WebSocketServer",
    "WebSocketClient",
    "WebSocketProtocol",
    "WebSocketMessage",
    "MessageType",
    "EventTypes",
    "WebSocketAuthenticator",
    "generate_test_token",
    "tls",
    "metrics",
]
