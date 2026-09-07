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
