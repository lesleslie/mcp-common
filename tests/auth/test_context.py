"""Tests for request-scoped Principal context helpers."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mcp_common.auth.context import (
    _clear_principal,
    _current_principal,
    seed_principal,
)
from mcp_common.auth.permissions import Permission
from mcp_common.auth.principal import Principal


def _make_principal() -> Principal:
    return Principal(
        issuer="test",
        subject="user-1",
        permissions=frozenset({Permission.READ}),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        raw_claims={},
    )


def test_current_principal_returns_none_when_unset():
    _clear_principal()
    assert _current_principal() is None


def test_seed_principal_sets_current():
    p = _make_principal()
    token = seed_principal(p)
    try:
        assert _current_principal() is p
    finally:
        token.var.reset(token)


def test_clear_principal_resets():
    p = _make_principal()
    seed_principal(p)
    _clear_principal()
    assert _current_principal() is None
