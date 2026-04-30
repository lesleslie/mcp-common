from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from mcp_common.auth.permissions import Permission

logger = logging.getLogger(__name__)


class AuditSink(Protocol):
    def emit(self, event: AuthAuditEvent) -> None: ...


@dataclass
class AuthAuditEvent:
    timestamp: datetime
    service: str
    caller_service: str
    caller_id: str
    action: str
    permission: Permission
    result: str
    reason: str | None
    source_ip: str | None
    token_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": "auth_audit",
            "timestamp": self.timestamp.isoformat(),
            "service": self.service,
            "caller_service": self.caller_service,
            "caller_id": self.caller_id,
            "action": self.action,
            "permission": self.permission.value,
            "result": self.result,
            "reason": self.reason,
            "source_ip": self.source_ip,
            "token_id": self.token_id,
        }


class AuditLogger:
    def __init__(self) -> None:
        self._sinks: list[AuditSink] = []

    def register_sink(self, sink: AuditSink) -> None:
        self._sinks.append(sink)

    def emit(self, event: AuthAuditEvent) -> None:
        logger.info(json.dumps(event.to_dict()))
        for sink in self._sinks:
            try:
                sink.emit(event)
            except Exception:
                logger.exception("AuditSink %r raised during emit", sink)
