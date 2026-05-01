from __future__ import annotations

from dataclasses import dataclass

from mcp_common.auth.exceptions import AudienceMismatchError, UnknownIssuerError

KNOWN_SERVICES: frozenset[str] = frozenset(
    {
        "mahavishnu",
        "session-buddy",
        "akosha",
        "dhara",
        "crackerjack",
    }
)


@dataclass(frozen=True)
class ServiceIdentity:
    name: str
    port: int
    secret_env_var: str


def verify_issuer(issuer: str) -> None:
    if issuer not in KNOWN_SERVICES:
        raise UnknownIssuerError(f"Unknown issuer: {issuer!r}")


def verify_audience(claimed: str, expected: str) -> None:
    if claimed != expected:
        raise AudienceMismatchError(
            f"Token audience {claimed!r} does not match service {expected!r}"
        )
