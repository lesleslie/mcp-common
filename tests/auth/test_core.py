from datetime import UTC, datetime, timedelta
from inspect import iscoroutine

import jwt as pyjwt
import pytest

from mcp_common.auth.core import (
    JWTIdentityProvider,
    create_service_token,
    verify_token,
)
from mcp_common.auth.exceptions import (
    TokenExpiredError,
    TokenInvalidError,
    UnknownIssuerError,
)
from mcp_common.auth.permissions import Permission

SECRET = "a-test-secret-that-is-at-least-32-chars-long"


def test_create_and_verify_round_trip():
    token = create_service_token(
        secret=SECRET,
        issuer="mahavishnu",
        audience="session-buddy",
        permissions=[Permission.READ, Permission.WRITE],
    )
    payload = verify_token(token, secret=SECRET, expected_audience="session-buddy")
    assert payload.issuer == "mahavishnu"
    assert payload.audience == "session-buddy"
    assert Permission.READ in payload.permissions
    assert Permission.WRITE in payload.permissions


def test_verify_rejects_wrong_audience():
    token = create_service_token(
        secret=SECRET,
        issuer="mahavishnu",
        audience="session-buddy",
        permissions=[Permission.READ],
    )
    from mcp_common.auth.exceptions import AudienceMismatchError
    with pytest.raises(AudienceMismatchError):
        verify_token(token, secret=SECRET, expected_audience="akosha")


def test_verify_rejects_unknown_issuer():
    bad_token = pyjwt.encode(
        {"sub": "x", "iss": "rogue-service", "aud": "dhara",
         "exp": datetime.now(UTC) + timedelta(seconds=60), "iat": datetime.now(UTC),
         "jti": "test-jti", "scopes": []},
        SECRET, algorithm="HS256",
    )
    with pytest.raises(UnknownIssuerError):
        verify_token(bad_token, secret=SECRET, expected_audience="dhara")


def test_verify_rejects_expired_token():
    # Expired well outside the 30s clock-skew leeway (R2-7).
    expired = pyjwt.encode(
        {"sub": "mahavishnu", "iss": "mahavishnu", "aud": "akosha",
         "exp": datetime.now(UTC) - timedelta(seconds=120), "iat": datetime.now(UTC),
         "jti": "test-jti", "scopes": ["read"]},
        SECRET, algorithm="HS256",
    )
    with pytest.raises(TokenExpiredError):
        verify_token(expired, secret=SECRET, expected_audience="akosha")


def test_verify_rejects_bad_signature():
    token = create_service_token(
        secret=SECRET,
        issuer="mahavishnu",
        audience="session-buddy",
        permissions=[Permission.READ],
    )
    with pytest.raises(TokenInvalidError):
        verify_token(token, secret="wrong-secret-that-is-long-enough-123", expected_audience="session-buddy")


def test_token_payload_has_jti():
    token = create_service_token(
        secret=SECRET, issuer="crackerjack", audience="dhara",
        permissions=[Permission.READ],
    )
    payload = verify_token(token, secret=SECRET, expected_audience="dhara")
    assert payload.jti is not None
    assert len(payload.jti) > 0


def test_verify_ignores_unknown_scope_values(monkeypatch):
    import mcp_common.auth.core as auth_core

    now = datetime.now(UTC)
    raw_payload = {
        "sub": "mahavishnu",
        "iss": "mahavishnu",
        "aud": "session-buddy",
        "exp": int((now + timedelta(seconds=60)).timestamp()),
        "iat": int(now.timestamp()),
        "jti": "test-jti",
        "scopes": ["read", "not-a-real-scope"],
    }
    # B5 fix: verify_token now calls get_unverified_header() before decode()
    # for the algorithm pre-check, so monkeypatch both.
    monkeypatch.setattr(
        auth_core.pyjwt, "get_unverified_header", lambda *args, **kwargs: {"alg": "HS256"}
    )
    monkeypatch.setattr(auth_core.pyjwt, "decode", lambda *args, **kwargs: raw_payload)

    payload = auth_core.verify_token(
        "token",
        secret=SECRET,
        expected_audience="session-buddy",
    )

    assert payload.permissions == frozenset()


# --- JWTIdentityProvider tests (Task 4) ---


def _await_or_sync(value):
    """If ``value`` is awaitable, run it on a fresh loop and return the result.

    Tests use this so they can call ``verify_token`` / ``health`` whether the
    implementation is sync or async.
    """
    import asyncio

    if iscoroutine(value):
        return asyncio.new_event_loop().run_until_complete(value)
    return value


def test_jwt_identity_provider_roundtrip():
    provider = JWTIdentityProvider(
        name="jwt",
        secret=SECRET,
        trusted_issuers=["mahavishnu"],
    )
    token = provider.issue_token(
        issuer="mahavishnu",
        audience="test-service",
        permissions=[Permission.READ],
        subject="test-subject",
    )
    principal = _await_or_sync(
        provider.verify_token(token, expected_audience="test-service")
    )
    assert principal.issuer == "mahavishnu"
    assert principal.subject == "test-subject"
    assert Permission.READ in principal.permissions


def test_jwt_identity_provider_rejects_wrong_audience():
    provider = JWTIdentityProvider(
        name="jwt",
        secret=SECRET,
        trusted_issuers=["mahavishnu"],
    )
    token = provider.issue_token(
        issuer="mahavishnu",
        audience="service-a",
        permissions=[Permission.READ],
        subject="test",
    )
    with pytest.raises(Exception):  # AudienceMismatchError
        _await_or_sync(provider.verify_token(token, expected_audience="service-b"))


def test_jwt_identity_provider_health_is_healthy():
    provider = JWTIdentityProvider(name="jwt", secret=SECRET)
    h = _await_or_sync(provider.health())
    assert h.name == "jwt"
    assert h.state == "healthy"
