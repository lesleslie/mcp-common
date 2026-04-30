import time
import pytest
from mcp_common.auth.core import create_service_token, verify_token, TokenPayload
from mcp_common.auth.permissions import Permission
from mcp_common.auth.exceptions import TokenExpiredError, TokenInvalidError, UnknownIssuerError


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
    import jwt as pyjwt
    from datetime import UTC, datetime, timedelta
    bad_token = pyjwt.encode(
        {"sub": "x", "iss": "rogue-service", "aud": "dhara",
         "exp": datetime.now(UTC) + timedelta(seconds=60), "iat": datetime.now(UTC),
         "jti": "test-jti", "scopes": []},
        SECRET, algorithm="HS256",
    )
    with pytest.raises(UnknownIssuerError):
        verify_token(bad_token, secret=SECRET, expected_audience="dhara")


def test_verify_rejects_expired_token():
    import jwt as pyjwt
    from datetime import UTC, datetime, timedelta
    expired = pyjwt.encode(
        {"sub": "mahavishnu", "iss": "mahavishnu", "aud": "akosha",
         "exp": datetime.now(UTC) - timedelta(seconds=5), "iat": datetime.now(UTC),
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
