"""End-to-end test: Mahavishnu creates a token, Session-Buddy verifies it."""
from __future__ import annotations

import pytest

from mcp_common.auth.config import AuthConfig
from mcp_common.auth.core import create_service_token, verify_token
from mcp_common.auth.exceptions import AudienceMismatchError
from mcp_common.auth.permissions import Permission

SECRET = "integration-test-secret-at-least-32-chars-long"


@pytest.fixture
def config(monkeypatch):
    monkeypatch.setenv("BODAI_SHARED_SECRET", SECRET)
    return AuthConfig(service_name="session-buddy", secret_env_var="SESSION_BUDDY_SECRET")


def test_mahavishnu_to_session_buddy_happy_path(config):
    token = create_service_token(
        secret=SECRET,
        issuer="mahavishnu",
        audience="session-buddy",
        permissions=[Permission.READ, Permission.WRITE],
    )
    payload = verify_token(token, secret=SECRET, expected_audience="session-buddy")
    assert payload.issuer == "mahavishnu"
    assert Permission.WRITE in payload.permissions


def test_token_cannot_be_replayed_to_different_service(config):
    token = create_service_token(
        secret=SECRET,
        issuer="mahavishnu",
        audience="session-buddy",
        permissions=[Permission.READ],
    )
    with pytest.raises(AudienceMismatchError):
        verify_token(token, secret=SECRET, expected_audience="akosha")


def test_unique_jti_per_token():
    t1 = create_service_token(
        secret=SECRET, issuer="mahavishnu", audience="akosha", permissions=[Permission.READ]
    )
    t2 = create_service_token(
        secret=SECRET, issuer="mahavishnu", audience="akosha", permissions=[Permission.READ]
    )
    p1 = verify_token(t1, secret=SECRET, expected_audience="akosha")
    p2 = verify_token(t2, secret=SECRET, expected_audience="akosha")
    assert p1.jti != p2.jti
