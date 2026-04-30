import json
import logging
from datetime import UTC, datetime

import pytest

from mcp_common.auth.audit import AuthAuditEvent, AuditLogger
from mcp_common.auth.permissions import Permission


def test_audit_event_serializes_to_dict():
    event = AuthAuditEvent(
        timestamp=datetime(2026, 4, 27, 8, 0, 0, tzinfo=UTC),
        service="session-buddy",
        caller_service="mahavishnu",
        caller_id="system",
        action="store_evidence",
        permission=Permission.WRITE,
        result="allowed",
        reason=None,
        source_ip="127.0.0.1",
        token_id="abc-123",
    )
    d = event.to_dict()
    assert d["service"] == "session-buddy"
    assert d["permission"] == "write"
    assert d["result"] == "allowed"
    assert "timestamp" in d


def test_audit_logger_emits_to_standard_logger(caplog):
    logger = AuditLogger()
    with caplog.at_level(logging.INFO, logger="mcp_common.auth.audit"):
        event = AuthAuditEvent(
            timestamp=datetime.now(UTC),
            service="akosha",
            caller_service="mahavishnu",
            caller_id="system",
            action="embed",
            permission=Permission.READ,
            result="allowed",
            reason=None,
            source_ip=None,
            token_id="jti-xyz",
        )
        logger.emit(event)
    assert any("auth_audit" in r.message for r in caplog.records)


def test_custom_sink_receives_event():
    received = []

    class MySink:
        def emit(self, event: AuthAuditEvent) -> None:
            received.append(event)

    logger = AuditLogger()
    logger.register_sink(MySink())

    event = AuthAuditEvent(
        timestamp=datetime.now(UTC),
        service="dhara",
        caller_service="crackerjack",
        caller_id="system",
        action="list",
        permission=Permission.READ,
        result="denied",
        reason="insufficient permission",
        source_ip=None,
        token_id=None,
    )
    logger.emit(event)
    assert len(received) == 1
    assert received[0].result == "denied"
