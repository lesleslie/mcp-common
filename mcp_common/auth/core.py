from __future__ import annotations

import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt as pyjwt
from jwt import ExpiredSignatureError, InvalidTokenError
from jwt.exceptions import InvalidAudienceError
from pydantic import SecretStr

from mcp_common.auth.exceptions import (
    AudienceMismatchError,
    TokenExpiredError,
    TokenInvalidError,
    UnknownIssuerError,
)
from mcp_common.auth.permissions import Permission
from mcp_common.auth.principal import Principal
from mcp_common.auth.provider import ProviderHealth

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
    raw_claims: dict[str, Any] = field(default_factory=dict)  # B9: was `raw`


def create_service_token(
    *,
    secret: str,
    issuer: str,
    audience: str,
    permissions: list[Permission],
    subject: str | None = None,
    ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject if subject is not None else issuer,
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
    expected_audience: str | None = None,
) -> TokenPayload:
    """Verify a JWT and return TokenPayload.

    B5 fix: ``algorithms`` pinned to ``[JWT_ALGORITHM]`` (HS256). The pre-check
    on the unverified header is belt-and-suspenders — PyJWT already enforces
    the pinned list, but if a future PyJWT regression loosened the check, the
    header pre-check still rejects ``alg=none`` and HS256/RSA confusion attacks.

    R2-7 fix: ``leeway=30`` tolerates typical NTP clock skew between issuer
    and verifier (default is 0s).
    """
    try:
        unverified_header = pyjwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        raise TokenInvalidError(f"Malformed token: {exc}") from exc

    if unverified_header.get("alg") != JWT_ALGORITHM:
        raise TokenInvalidError(
            f"Unexpected algorithm: {unverified_header.get('alg')!r}"
        )

    try:
        raw = pyjwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            audience=expected_audience,
            options={"require": ["exp", "iat", "iss", "aud"]},
            leeway=30,
        )
    except ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired") from exc
    except InvalidAudienceError as exc:
        raise AudienceMismatchError(str(exc)) from exc
    except InvalidTokenError as exc:
        raise TokenInvalidError(str(exc)) from exc

    # Task 7: the legacy ``verify_issuer()`` free function (which referenced
    # the now-deleted KNOWN_SERVICES frozenset) was removed. The per-request
    # trusted_issuers allow-list check now lives in JWTIdentityProvider.verify_token
    # (default-deny B6). The free ``verify_token`` returns the decoded payload
    # so callers that don't go through a provider can still introspect claims.
    issuer = raw.get("iss", "")

    scopes = raw.get("scopes", [])
    perms: frozenset[Permission] = frozenset()
    with suppress(ValueError):
        perms = frozenset(Permission(s) for s in scopes)

    return TokenPayload(
        issuer=issuer,
        audience=raw.get("aud", ""),
        subject=raw.get("sub", ""),
        jti=raw.get("jti", ""),
        permissions=perms,
        issued_at=datetime.fromtimestamp(raw["iat"], tz=UTC),
        expires_at=datetime.fromtimestamp(raw["exp"], tz=UTC),
        raw_claims=raw,  # B9: was `raw`
    )


class JWTIdentityProvider:
    """IdentityProvider implementation using PyJWT HS256.

    B5 fix: ``jwt.decode`` pins ``algorithms=[JWT_ALGORITHM]`` (HS256).
    B6 fix: per-server ``trusted_issuers`` allow-list (default-deny: empty
    list rejects every issuer — the middleware startup check in Task 7
    fails-fast when an operator forgets to configure the allow-list).
    R2-4 fix: an unknown permission value in the JWT raises
    ``TokenInvalidError`` instead of leaking ``ValueError`` to a 500.
    """

    def __init__(
        self,
        *,
        name: str = "jwt",
        secret: str | SecretStr,
        trusted_issuers: list[str] | None = None,
    ) -> None:
        self.name = name
        self._secret = (
            secret.get_secret_value() if isinstance(secret, SecretStr) else secret
        )
        # B6 fix: trusted_issuers is the per-server allow-list. Empty list
        # rejects every issuer (default-deny); the Task 7 startup check
        # fails-fast if an operator forgets to configure it.
        self._trusted_issuers: list[str] = list(trusted_issuers or [])

    def issue_token(
        self,
        *,
        issuer: str,
        audience: str,
        permissions: list[Permission],
        subject: str,
        ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
    ) -> str:
        """Issue a signed JWT. Wraps the free-function ``create_service_token``."""
        return create_service_token(
            secret=self._secret,
            issuer=issuer,
            audience=audience,
            permissions=permissions,
            subject=subject,
            ttl_seconds=ttl_seconds,
        )

    async def verify_token(
        self,
        token: str,
        *,
        expected_audience: str | None = None,
    ) -> Principal:
        """Verify a JWT and return a Principal.

        Delegates signature/audience/issuer/exp validation to the free-function
        ``verify_token`` (which pins algorithms). Then enforces the
        ``trusted_issuers`` allow-list (B6) and re-validates raw permission
        values from the JWT (R2-4).
        """
        payload = verify_token(
            token, secret=self._secret, expected_audience=expected_audience
        )

        if payload.issuer not in self._trusted_issuers:
            raise UnknownIssuerError(
                f"Issuer {payload.issuer!r} not in trusted_issuers: "
                f"{self._trusted_issuers}"
            )

        # R2-4 fix: re-validate raw permission strings from the JWT. The
        # free-function ``verify_token`` silently drops unknown scope values;
        # the strict enum conversion here surfaces unprocessable tokens as
        # TokenInvalidError (mapped to 401 by the middleware) instead of
        # leaking ValueError to a 500.
        raw_scopes: list[str] = list(payload.raw_claims.get("scopes", []))
        try:
            permissions = frozenset({Permission(s) for s in raw_scopes})
        except ValueError as exc:
            raise TokenInvalidError(
                f"Token carries unknown permission value: {exc}"
            ) from exc

        return Principal(
            issuer=payload.issuer,
            subject=payload.subject,
            permissions=permissions,
            expires_at=payload.expires_at,
            raw_claims=payload.raw_claims,  # B9: no hasattr guard
        )

    async def health(self) -> ProviderHealth:
        return ProviderHealth(name=self.name, state="healthy")
