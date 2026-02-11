"""Prometheus metrics for WebSocket servers.

This module provides standardized metrics collection for WebSocket servers
across the ecosystem, enabling monitoring with Prometheus and Grafana.
"""

from __future__ import annotations

import logging
import time
from typing import Any

# Try to import prometheus_client, make it optional
try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Create stubs for when prometheus_client is not available
    class Counter:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any): pass
        def labels(self, **kwargs: Any): return self
        def inc(self, amount: float = 1) -> None: pass
    class Gauge:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any): pass
        def labels(self, **kwargs: Any): return self
        def set(self, value: float) -> None: pass
    class Histogram:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any): pass
        def labels(self, **kwargs: Any): return self
        def observe(self, amount: float) -> None: pass
    def start_http_server(port: int) -> None:  # type: ignore
        pass

logger = logging.getLogger(__name__)

# Define metrics at module level for Prometheus to scrape
websocket_connections_total = Counter(
    'websocket_connections_total',
    'Total number of WebSocket connections established',
    ['server', 'tls_mode']
)

websocket_connections_active = Gauge(
    'websocket_connections_active',
    'Current number of active WebSocket connections',
    ['server']
)

websocket_messages_total = Counter(
    'websocket_messages_total',
    'Total number of messages processed',
    ['server', 'message_type', 'direction']  # direction: sent, received
)

websocket_broadcast_total = Counter(
    'websocket_broadcast_total',
    'Total number of broadcast operations',
    ['server', 'channel']
)

websocket_broadcast_duration_seconds = Histogram(
    'websocket_broadcast_duration_seconds',
    'Time taken to broadcast messages to rooms',
    ['server', 'channel'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

websocket_connection_errors_total = Counter(
    'websocket_connection_errors_total',
    'Total number of WebSocket connection errors',
    ['server', 'error_type']
)

websocket_message_errors_total = Counter(
    'websocket_message_errors_total',
    'Total number of message processing errors',
    ['server', 'error_type']
)

websocket_latency_seconds = Histogram(
    'websocket_latency_seconds',
    'WebSocket message processing latency',
    ['server', 'message_type'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)


class WebSocketMetrics:
    """Metrics collector for WebSocket server.

    Tracks connections, messages, broadcasts, errors, and latency.
    Metrics are automatically exposed to Prometheus when enabled.

    Example:
        >>> metrics = WebSocketMetrics("mahavishnu", tls_enabled=True)
        >>> metrics.on_connect()
        >>> metrics.on_message("request")
        >>> metrics.on_disconnect()
    """

    def __init__(
        self,
        server_name: str,
        tls_enabled: bool = False,
        enabled: bool = True
    ):
        """Initialize metrics collector.

        Args:
            server_name: Name of the WebSocket server (e.g., "mahavishnu", "crackerjack")
            tls_enabled: Whether TLS/WSS is enabled
            enabled: Whether metrics collection is enabled
        """
        if not PROMETHEUS_AVAILABLE:
            logger.warning(
                "prometheus_client not available. "
                "Install it with: pip install prometheus-client"
            )
            self.enabled = False
        else:
            self.enabled = enabled

        self.server_name = server_name
        self.tls_mode = "wss" if tls_enabled else "ws"
        self._connection_start_times: dict[str, float] = {}

    def on_connect(self, connection_id: str) -> None:
        """Record new connection.

        Args:
            connection_id: Unique connection identifier
        """
        if not self.enabled:
            return

        websocket_connections_total.labels(
            server=self.server_name,
            tls_mode=self.tls_mode
        ).inc()
        websocket_connections_active.labels(server=self.server_name).inc()
        self._connection_start_times[connection_id] = time.time()

    def on_disconnect(self, connection_id: str) -> None:
        """Record disconnection.

        Args:
            connection_id: Unique connection identifier
        """
        if not self.enabled:
            return

        websocket_connections_active.labels(server=self.server_name).dec()

        # Record connection duration if we have start time
        if connection_id in self._connection_start_times:
            duration = time.time() - self._connection_start_times[connection_id]
            del self._connection_start_times[connection_id]

    def on_message_sent(self, message_type: str) -> None:
        """Record message sent to client.

        Args:
            message_type: Type of message (request, response, event, error)
        """
        if not self.enabled:
            return

        websocket_messages_total.labels(
            server=self.server_name,
            message_type=message_type,
            direction="sent"
        ).inc()

    def on_message_received(self, message_type: str) -> None:
        """Record message received from client.

        Args:
            message_type: Type of message (request, response, event, error)
        """
        if not self.enabled:
            return

        websocket_messages_total.labels(
            server=self.server_name,
            message_type=message_type,
            direction="received"
        ).inc()

    def on_broadcast(self, channel: str, duration: float) -> None:
        """Record broadcast operation.

        Args:
            channel: Channel/room name
            duration: Broadcast duration in seconds
        """
        if not self.enabled:
            return

        websocket_broadcast_total.labels(
            server=self.server_name,
            channel=channel
        ).inc()
        websocket_broadcast_duration_seconds.labels(
            server=self.server_name,
            channel=channel
        ).observe(duration)

    def on_connection_error(self, error_type: str) -> None:
        """Record connection error.

        Args:
            error_type: Type of error (e.g., "timeout", "handshake_failed")
        """
        if not self.enabled:
            return

        websocket_connection_errors_total.labels(
            server=self.server_name,
            error_type=error_type
        ).inc()

    def on_message_error(self, error_type: str) -> None:
        """Record message processing error.

        Args:
            error_type: Type of error (e.g., "decode_error", "validation_failed")
        """
        if not self.enabled:
            return

        websocket_message_errors_total.labels(
            server=self.server_name,
            error_type=error_type
        ).inc()

    def observe_latency(self, message_type: str, latency: float) -> None:
        """Record message processing latency.

        Args:
            message_type: Type of message
            latency: Processing time in seconds
        """
        if not self.enabled:
            return

        websocket_latency_seconds.labels(
            server=self.server_name,
            message_type=message_type
        ).observe(latency)

    def set_active_connections(self, count: int) -> None:
        """Set active connection count (for initialization).

        Args:
            count: Number of active connections
        """
        if not self.enabled:
            return

        websocket_connections_active.labels(server=self.server_name).set(count)

    def start_metrics_server(self, port: int = 9090) -> bool:
        """Start Prometheus metrics HTTP server.

        Args:
            port: Metrics server port (default: 9090)

        Returns:
            True if server started successfully, False otherwise
        """
        if not self.enabled or not PROMETHEUS_AVAILABLE:
            logger.warning("Metrics not enabled or prometheus_client not available")
            return False

        try:
            start_http_server(port)
            logger.info(f"Prometheus metrics server started on port {port}")
            logger.info(f"Metrics available at http://0.0.0.0:{port}/metrics")
            return True
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")
            return False


def get_metrics_summary(server_name: str) -> dict[str, Any]:
    """Get current metrics summary for a server.

    This is a convenience function for logging and debugging.
    Prometheus will scrape the actual metrics from the /metrics endpoint.

    Args:
        server_name: Name of the server

    Returns:
        Dictionary with metric information
    """
    if not PROMETHEUS_AVAILABLE:
        return {"available": False}

    try:
        from prometheus_client import REGISTRY

        summary = {
            "available": True,
            "server": server_name,
            "metrics_count": len(REGISTRY.getCollectorNames()),
        }
        return summary
    except Exception as e:
        return {"available": True, "error": str(e)}
