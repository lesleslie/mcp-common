from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt as pyjwt
from jwt import ExpiredSignatureError, InvalidTokenError
from jwt.exceptions import InvalidAudienceError

from mcp_common.auth.exceptions import (
    AudienceMismatchError,
    TokenExpiredError,
    TokenInvalidError,
    UnknownIssuerError,
)
from mcp_common.auth.identity import verify_issuer
from mcp_common.auth.permissions import Permission

JWT_ALGORITHM = "HS256"
DEFAULT_TOKEN_TTL_SECONDS = 3600


@dataclass
class TokenPayload:
    issuer: str
    audience: str
    subject: str
    jti: str
    permissions: frozenset[Permission]
    issued_at: datetime
    expires_at: datetime
    raw: dict[str, Any] = field(default_factory=dict)


def create_service_token(
    *,
    secret: str,
    issuer: str,
    audience: str,
    permissions: list[Permission],
    ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": issuer,
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
        "jti": str(uuid.uuid4()),
        "scopes": [p.value for p in permissions],
    }
    return pyjwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def verify_token(
    token: str,
    *,
    secret: str,
    expected_audience: str,
) -> TokenPayload:
    try:
        raw = pyjwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            audience=expected_audience,
        )
    except ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired") from exc
    except InvalidAudienceError as exc:
        raise AudienceMismatchError(str(exc)) from exc
    except InvalidTokenError as exc:
        raise TokenInvalidError(str(exc)) from exc

    issuer = raw.get("iss", "")
    try:
        verify_issuer(issuer)
    except Exception as exc:
        raise UnknownIssuerError(str(exc)) from exc

    scopes = raw.get("scopes", [])
    perms: frozenset[Permission] = frozenset()
    try:
        perms = frozenset(Permission(s) for s in scopes)
    except ValueError:
        pass

    return TokenPayload(
        issuer=issuer,
        audience=raw.get("aud", ""),
        subject=raw.get("sub", ""),
        jti=raw.get("jti", ""),
        permissions=perms,
        issued_at=datetime.fromtimestamp(raw["iat"], tz=UTC),
        expires_at=datetime.fromtimestamp(raw["exp"], tz=UTC),
        raw=raw,
    )
