"""Tests for @require_auth — reads Principal from request-scoped Context.

These tests exercise the Context-based Principal lookup (Task 6). Tests
inject Principals via ``seed_principal()`` rather than passing tokens
through tool kwargs (the old transport).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from mcp_common.auth.context import _clear_principal, seed_principal
from mcp_common.auth.decorator import require_auth
from mcp_common.auth.exceptions import (
    AuthenticationRequiredError,
    InsufficientPermissionError,
)
from mcp_common.auth.permissions import Permission
from mcp_common.auth.principal import Principal


def _make_principal(*permissions: Permission, issuer: str = "test") -> Principal:
    return Principal(
        issuer=issuer,
        subject="test-user",
        permissions=frozenset(permissions),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        raw_claims={},
    )


@pytest.fixture(autouse=True)
def _reset_context():
    _clear_principal()
    yield
    _clear_principal()


@pytest.mark.asyncio
async def test_require_auth_allows_when_principal_has_permission():
    @require_auth(permission=Permission.READ, service_name="svc")
    async def my_tool():
        return "ok"

    seed_principal(_make_principal(Permission.READ))
    assert await my_tool() == "ok"


@pytest.mark.asyncio
async def test_require_auth_denies_when_principal_lacks_permission():
    @require_auth(permission=Permission.WRITE, service_name="svc")
    async def my_tool():
        return "ok"

    seed_principal(_make_principal(Permission.READ))
    with pytest.raises(InsufficientPermissionError):
        await my_tool()


@pytest.mark.asyncio
async def test_require_auth_default_permission_is_read():
    @require_auth(service_name="svc")
    async def my_tool():
        return "ok"

    seed_principal(_make_principal(Permission.READ))
    assert await my_tool() == "ok"


@pytest.mark.asyncio
async def test_require_auth_anonymous_path_allows_when_no_principal():
    @require_auth(permission=Permission.READ, allow_anonymous=True, service_name="svc")
    async def my_tool():
        return "ok"

    assert await my_tool() == "ok"


@pytest.mark.asyncio
async def test_require_auth_anonymous_path_still_enforces_when_principal_set():
    @require_auth(permission=Permission.READ, allow_anonymous=True, service_name="svc")
    async def my_tool():
        return "ok"

    seed_principal(_make_principal())  # no permissions
    with pytest.raises(InsufficientPermissionError):
        await my_tool()


@pytest.mark.asyncio
async def test_require_auth_raises_authentication_required_when_no_principal():
    """No Principal in context + allow_anonymous=False → AuthenticationRequiredError (401)."""
    @require_auth(permission=Permission.READ, service_name="svc")
    async def my_tool():
        return "ok"

    with pytest.raises(AuthenticationRequiredError):
        await my_tool()


@pytest.mark.asyncio
async def test_require_auth_emits_audit_event_on_allow():
    """Successful tool invocation emits an AuthAuditEvent with result='allowed'."""
    from mcp_common.auth.audit import AuditLogger

    received = []

    class CaptureSink:
        def emit(self, event):
            received.append(event)

    audit = AuditLogger()
    audit.register_sink(CaptureSink())

    @require_auth(
        permission=Permission.READ,
        service_name="test-service",
        audit_logger=audit,
    )
    async def my_tool():
        return "ok"

    seed_principal(_make_principal(Permission.READ))
    await my_tool()

    assert len(received) == 1
    assert received[0].result == "allowed"
    assert received[0].service == "test-service"
    assert received[0].caller_service == "test"
    assert received[0].caller_id == "test-user"


@pytest.mark.asyncio
async def test_require_auth_emits_audit_event_on_deny_insufficient_permission():
    """Permission denial emits an AuthAuditEvent with result='denied'."""
    from mcp_common.auth.audit import AuditLogger

    received = []

    class CaptureSink:
        def emit(self, event):
            received.append(event)

    audit = AuditLogger()
    audit.register_sink(CaptureSink())

    @require_auth(
        permission=Permission.WRITE,
        service_name="test-service",
        audit_logger=audit,
    )
    async def my_tool():
        return "ok"

    seed_principal(_make_principal(Permission.READ))
    with pytest.raises(InsufficientPermissionError):
        await my_tool()

    assert len(received) == 1
    assert received[0].result == "denied"
    assert received[0].service == "test-service"
    assert received[0].permission == Permission.WRITE


@pytest.mark.asyncio
async def test_require_auth_emits_audit_event_on_401_no_principal():
    """No-Principal + allow_anonymous=False emits an AuthAuditEvent with result='denied'."""
    from mcp_common.auth.audit import AuditLogger

    received = []

    class CaptureSink:
        def emit(self, event):
            received.append(event)

    audit = AuditLogger()
    audit.register_sink(CaptureSink())

    @require_auth(
        permission=Permission.READ,
        service_name="test-service",
        audit_logger=audit,
    )
    async def my_tool():
        return "ok"

    with pytest.raises(AuthenticationRequiredError):
        await my_tool()

    assert len(received) == 1
    assert received[0].result == "denied"
    assert received[0].reason == "no_principal"
