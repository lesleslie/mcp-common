"""
Shared messaging types for ecosystem-wide communication.

Used by:
- Session Buddy: Multi-project messaging
- Mahavishnu: Inter-repository messaging

Version: 0.4.0
"""

from enum import Enum

from pydantic import BaseModel

# =============================================================================
# Shared Enums (Condition 2: Messaging Types)
# =============================================================================


class Priority(str, Enum):
    """
    Message priority levels - SHARED ACROSS ECOSYSTEM

    Usage:
        from messaging.types import Priority

        message = RepositoryMessage(
            priority=Priority.HIGH,
            ...
        )
    """

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MessageType(str, Enum):
    """
    Message types - SHARED ACROSS ECOSYSTEM

    - request: Asking for something
    - response: Replying to a request
    - notification: Informing about something
    - update: Providing status update

    Usage:
        from messaging.types import MessageType

        message = ProjectMessage(
            content_type=MessageType.NOTIFICATION,
            ...
        )
    """

    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    UPDATE = "update"


class MessageStatus(str, Enum):
    """
    Message status - SHARED ACROSS ECOSYSTEM
    """

    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"


# =============================================================================
# Base Message Content Model
# =============================================================================


class MessageContent(BaseModel):
    """
    Message content structure - SHARED ACROSS ECOSYSTEM

    Attributes:
        type: Message type (request, response, notification, update)
        message: Main message body
        context: Additional metadata/context (optional)
        attachments: File attachments (optional)
    """

    type: MessageType
    message: str
    context: dict[str, object] | None = None
    attachments: list[dict[str, str]] | None = None


# =============================================================================
# Forwarded Message Structure
# =============================================================================


class ForwardedFrom(BaseModel):
    """
    Forwarded message metadata - SHARED ACROSS ECOSYSTEM

    When a message is forwarded, preserve original context.

    Attributes:
        original_message_id: ID of original message
        original_from: Original sender
        original_to: Original recipient
        original_timestamp: Original timestamp
        forwarded_by: Who forwarded the message
        forwarded_at: When forwarded
        forward_note: Optional note added when forwarding
    """

    original_message_id: str
    original_from: str
    original_to: str
    original_timestamp: str
    forwarded_by: str
    forwarded_at: str
    forward_note: str | None = None


# =============================================================================
# Session Buddy: Project-to-Project Message
# =============================================================================


class ProjectMessage(BaseModel):
    """
    Session Buddy: Multi-project message

    Used for communication between git worktrees/projects managed by
    a single Claude Code instance.

    Attributes:
        id: Unique message identifier
        from_project: Source project identifier
        to_project: Target project identifier
        timestamp: ISO 8601 timestamp
        subject: Message subject line
        priority: Message priority (low, normal, high, urgent)
        status: Message status (unread, read, archived)
        content_type: Type of message
        content_message: Message body
        content_context: Additional metadata (optional)
        content_attachments: File attachments (optional)
        in_reply_to: ID of message being replied to (optional)
        session_id: Session Buddy session ID (optional)
    """

    id: str
    from_project: str
    to_project: str
    timestamp: str
    subject: str
    priority: Priority
    status: MessageStatus
    content_type: MessageType
    content_message: str
    content_context: dict[str, object] | None = None
    content_attachments: list[dict[str, str]] | None = None
    in_reply_to: str | None = None
    session_id: str | None = None


# =============================================================================
# Mahavishnu: Repository-to-Repository Message
# =============================================================================


class RepositoryMessage(BaseModel):
    """
    Mahavishnu: Inter-repository message

    Used for communication between repositories in a multi-repo
    orchestration workflow.

    Attributes:
        id: Unique message identifier
        from_repository: Source repository identifier
        from_adapter: Source adapter (prefect, llamaindex, agno)
        to_repository: Target repository identifier
        timestamp: ISO 8601 timestamp
        subject: Message subject line
        priority: Message priority (low, normal, high, urgent)
        status: Message status (unread, read, archived)
        content_type: Type of message
        content_message: Message body
        content_context: Additional metadata (optional)
        content_attachments: File attachments (optional)
        in_reply_to: ID of message being replied to (optional)
        workflow_id: Associated workflow ID (optional)
        forwarded_from: Forwarded message metadata (optional)
    """

    id: str
    from_repository: str
    from_adapter: str | None  # 'prefect', 'llamaindex', 'agno'
    to_repository: str
    timestamp: str
    subject: str
    priority: Priority
    status: MessageStatus
    content_type: MessageType
    content_message: str
    content_context: dict[str, object] | None = None
    content_attachments: list[dict[str, str]] | None = None
    in_reply_to: str | None = None
    workflow_id: str | None = None
    forwarded_from: ForwardedFrom | None = None


# =============================================================================
# Example Usage
# =============================================================================

# Session Buddy Example
from messaging.types import MessageStatus, MessageType, Priority, ProjectMessage

project_message = ProjectMessage(
    id="msg-1234567890",
    from_project="session-buddy",
    to_project="crackerjack",
    timestamp="2025-01-24T10:30:00Z",
    subject="Quality metrics available",
    priority=Priority.NORMAL,
    status=MessageStatus.UNREAD,
    content_type=MessageType.NOTIFICATION,
    content_message="Session quality score: 87/100",
    content_context={"session_id": "session-buddy-main"},
)

# Mahavishnu Example
from messaging.types import MessageStatus, MessageType, Priority, RepositoryMessage

repository_message = RepositoryMessage(
    id="msg-1234567891",
    from_repository="myapp-backend-api",
    from_adapter="prefect",
    to_repository="myapp-frontend-dashboard",
    timestamp="2025-01-24T10:30:00Z",
    subject="User stats API ready",
    priority=Priority.HIGH,
    status=MessageStatus.UNREAD,
    content_type=MessageType.NOTIFICATION,
    content_message="GET /api/stats implemented and tested.",
    content_context={
        "endpoint": "/api/stats",
        "cache_ttl": 300,
        "rate_limit": "100/hour",
    },
    workflow_id="wf-stats-api-123",
)
