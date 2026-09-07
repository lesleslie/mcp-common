from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mcp_common.auth.permissions import Permission
from mcp_common.auth.principal import Principal


def test_principal_has_permission_returns_true_when_granted():
    expires = datetime.now(UTC) + timedelta(hours=1)
    p = Principal(
        issuer="anthropic",
        subject="user-123",
        permissions=frozenset({Permission.READ, Permission.WRITE}),
        expires_at=expires,
        raw_claims={},
    )
    assert p.has_permission(Permission.READ) is True
    assert p.has_permission(Permission.WRITE) is True


def test_principal_has_permission_returns_false_when_not_granted():
    expires = datetime.now(UTC) + timedelta(hours=1)
    p = Principal(
        issuer="anthropic",
        subject="user-123",
        permissions=frozenset({Permission.READ}),
        expires_at=expires,
        raw_claims={},
    )
    assert p.has_permission(Permission.ADMIN) is False


def test_principal_is_frozen():
    expires = datetime.now(UTC) + timedelta(hours=1)
    p = Principal(
        issuer="anthropic",
        subject="user-123",
        permissions=frozenset({Permission.READ}),
        expires_at=expires,
        raw_claims={},
    )
    try:
        p.subject = "other"  # type: ignore[misc]
    except Exception as exc:  # FrozenInstanceError or AttributeError
        assert isinstance(exc, (AttributeError,))
        return
    raise AssertionError("Principal should be frozen")
