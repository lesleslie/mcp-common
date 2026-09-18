"""Principal model — the authenticated identity attached to a request."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from mcp_common.auth.permissions import Permission


@dataclass(frozen=True)
class Principal:
    """An authenticated identity, attached to a request-scoped Context.

    Attributes:
        issuer: Token issuer identifier (e.g. "mahavishnu", "anthropic").
        subject: Unique identifier within the issuer.
        permissions: Set of granted permissions.
        expires_at: Token expiration timestamp (UTC).
        raw_claims: Full token payload for downstream consumers.
    """

    issuer: str
    subject: str
    permissions: frozenset[Permission]
    expires_at: datetime
    raw_claims: dict[str, Any]

    def has_permission(self, permission: Permission) -> bool:
        """Return True iff this Principal holds the given permission."""
        return permission in self.permissions

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict for FastMCP session state.

        Used by ``BearerTokenMiddleware`` to write the Principal into the
        FastMCP session-scoped state store (``serializable=True``). Without
        this conversion, ``set_state`` raises TypeError because ``frozenset``
        and ``datetime`` are not JSON-serializable. Mirror of
        ``AuthAuditEvent.to_dict`` (audit.py) — ``permission`` becomes its
        enum string value (e.g. ``"read"``), ``expires_at`` becomes its
        ISO-8601 string, ``permissions`` becomes a sorted list of values.

        Note: ``raw_claims`` is stored as-is. If a provider returns
        non-JSON-serializable values in ``raw_claims`` (e.g. bytes), the
        middleware must filter them before calling ``set_state``.
        """
        return {
            "issuer": self.issuer,
            "subject": self.subject,
            "permissions": sorted(p.value for p in self.permissions),
            "expires_at": self.expires_at.isoformat(),
            "raw_claims": dict(self.raw_claims),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Principal:
        """Reconstruct a Principal from its ``to_dict`` form.

        Used by ``@require_auth`` to read the Principal back out of
        FastMCP's session-scoped state store (``Context.get_state``) when
        the contextvar set by the middleware is not visible in the tool
        body's task (the FastMCP streamable-HTTP task-isolation gap).
        """
        return cls(
            issuer=data["issuer"],
            subject=data["subject"],
            permissions=frozenset(Permission(v) for v in data["permissions"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            raw_claims=dict(data.get("raw_claims") or {}),
        )
