"""WebSocket protocol and message definitions."""

from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class MessageType(str, Enum):
    """WebSocket message types."""

    # Client → Server messages
    REQUEST = "request"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PING = "ping"

    # Server → Client messages
    RESPONSE = "response"
    EVENT = "event"
    ERROR = "error"
    PONG = "pong"

    # Bidirectional
    ACK = "ack"


class WebSocketMessage(BaseModel):
    """Standard WebSocket message format."""

    # Message identification
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None  # For request/response matching

    # Message content
    type: MessageType
    event: Optional[str] = None  # Event type (e.g., "session_update", "workflow_progress")
    data: Dict[str, Any] = Field(default_factory=dict)

    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    room: Optional[str] = None  # For room-based broadcasting

    # Error information (if type == ERROR)
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        use_enum_values = True


class WebSocketProtocol:
    """
    WebSocket protocol handler for encoding/decoding messages.

    Provides methods for:
    - Message serialization/deserialization
    - Request/response correlation
    - Room management
    - Error handling
    """

    @staticmethod
    def encode(message: WebSocketMessage) -> str:
        """Encode message to JSON string."""
        return message.model_dump_json()

    @staticmethod
    def decode(json_str: str) -> WebSocketMessage:
        """Decode JSON string to message."""
        return WebSocketMessage.model_validate_json(json_str)

    @staticmethod
    def create_request(
        event: str,
        data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> WebSocketMessage:
        """Create a request message."""
        return WebSocketMessage(
            type=MessageType.REQUEST,
            event=event,
            data=data,
            correlation_id=correlation_id or str(uuid.uuid4())
        )

    @staticmethod
    def create_response(
        request: WebSocketMessage,
        data: Dict[str, Any],
        error: Optional[str] = None
    ) -> WebSocketMessage:
        """Create a response message for a request."""
        message = WebSocketMessage(
            type=MessageType.RESPONSE if error is None else MessageType.ERROR,
            event=request.event,
            data=data,
            correlation_id=request.correlation_id,
            error_message=error
        )
        return message

    @staticmethod
    def create_event(
        event: str,
        data: Dict[str, Any],
        room: Optional[str] = None
    ) -> WebSocketMessage:
        """Create an event message for broadcasting."""
        return WebSocketMessage(
            type=MessageType.EVENT,
            event=event,
            data=data,
            room=room
        )

    @staticmethod
    def create_error(
        error_code: str,
        error_message: str,
        correlation_id: Optional[str] = None
    ) -> WebSocketMessage:
        """Create an error message."""
        return WebSocketMessage(
            type=MessageType.ERROR,
            error_code=error_code,
            error_message=error_message,
            correlation_id=correlation_id
        )


# Event type constants for type safety
class EventTypes:
    """Standard event types across all services."""

    # Session-buddy events
    SESSION_CREATED = "session.created"
    SESSION_UPDATED = "session.updated"
    SESSION_CHECKPOINT = "session.checkpoint"
    SESSION_CLOSED = "session.closed"
    KNOWLEDGE_CAPTURED = "knowledge.captured"
    KNOWLEDGE_SEARCH_RESULT = "knowledge.search_result"

    # Mahavishnu events
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_STAGE_COMPLETED = "workflow.stage_completed"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKER_STATUS_CHANGED = "worker.status_changed"
    POOL_STATUS_CHANGED = "pool.status_changed"

    # Akosha events
    PATTERN_DETECTED = "pattern.detected"
    ANOMALY_DETECTED = "anomaly.detected"
    INSIGHT_GENERATED = "insight.generated"
    AGGREGATION_COMPLETED = "aggregation.completed"

    # Crackerjack events
    TEST_STARTED = "test.started"
    TEST_COMPLETED = "test.completed"
    TEST_FAILED = "test.failed"
    QUALITY_GATE_CHECKED = "quality_gate.checked"
    COVERAGE_UPDATED = "coverage.updated"

    # Dhruva events
    ADAPTER_STORED = "adapter.stored"
    ADAPTER_UPDATED = "adapter.updated"
    ADAPTER_DISTRIBUTED = "adapter.distributed"
    STORAGE_EVENT = "storage.event"

    # Excalidraw events
    DIAGRAM_CREATED = "diagram.created"
    DIAGRAM_UPDATED = "diagram.updated"
    CURSOR_MOVED = "cursor.moved"
    USER_JOINED = "user.joined"
    USER_LEFT = "user.left"
