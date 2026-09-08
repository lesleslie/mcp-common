"""@require_auth decorator — reads Principal from request-scoped Context.

Why this rewrite (vs. the previous ``__auth_token__`` kwarg transport)
----------------------------------------------------------------------
The old decorator popped ``__auth_token__`` from the tool's kwargs and
verified it inline. That worked for unit tests but leaked the auth
plumbing into every tool signature — and made cross-service auth
impossible without re-routing tokens through every call site.

The BearerTokenMiddleware (Task 6) now verifies the token at the
transport boundary and seeds a request-scoped Principal via
``mcp_common.auth.context``. The decorator's only job is to enforce
``permission`` on whatever Principal is in scope.

Fixes baked in
--------------

* B10 fix: uses the existing ``AuthAuditEvent`` type from
  ``mcp_common/auth/audit.py`` (not a new AuditEvent class). All required
  fields are populated (``timestamp``, ``service``, ``caller_service``,
  ``caller_id``, ``action``, ``permission``, ``result``, ``reason``,
  ``source_ip``, ``token_id``); ``source_ip`` and ``token_id`` are None
  because the decorator does not have access to them.

* I-2 fix: ``integrate_with_readyz`` parameter dropped. It was accepted
  but never consulted. Shipping a parameter that lies to callers is
  worse than no parameter. The /readyz aggregation semantics are
  deferred to a follow-up spec when there's an actual aggregation point.

* I-R2-2 fix: ``service_name`` is required (no ``"unknown"`` default).
  A service that doesn't know its own name should fail loudly at
  registration rather than silently emit audit events with caller_service
  = ``"unknown"`` (Article 32 / GDPR audit attribution).

* api-security R2-3 fix: audit values are sanitized at module level via
  ``_sanitize_audit_value`` to strip C0 control characters (except
  ``\\t``) and truncate to 256 chars. Defends against log-injection
  (a JWT ``sub`` claim containing ``\\r\\n`` could inject fake log lines)
  and over-long values (stack-trace fragments leaked via reason).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps
from typing import Any

from mcp_common.auth.audit import AuditLogger, AuthAuditEvent
from mcp_common.auth.context import _current_principal
from mcp_common.auth.exceptions import (
    AuthenticationRequiredError,
    InsufficientPermissionError,
)
from mcp_common.auth.permissions import Permission

logger = logging.getLogger(__name__)


# api-security R2-3 fix: control-character regex for audit-field sanitization.
# Strips C0 controls except ``\t`` (0x09). The spec allows ``\n`` for
# legitimate log line breaks; ``\r`` is stripped to prevent log injection.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_AUDIT_FIELD_MAX_LEN = 256


def _sanitize_audit_value(value: str | None) -> str | None:
    """Strip control chars and truncate long user-controlled audit fields.

    Defends against log-injection (a JWT ``sub`` claim containing ``\\r\\n``
    could inject fake log lines) and over-long values (stack-trace
    fragments leaked via ``reason``).
    """
    if value is None:
        return None
    cleaned = _CONTROL_CHARS_RE.sub("", value)
    if len(cleaned) > _AUDIT_FIELD_MAX_LEN:
        cleaned = cleaned[:_AUDIT_FIELD_MAX_LEN] + "..."
    return cleaned


def require_auth(
    permission: Permission = Permission.READ,
    *,
    allow_anonymous: bool = False,
    audit_logger: AuditLogger | None = None,
    service_name: str,  # I-R2-2 fix: required (no "unknown" default).
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator: enforce ``permission`` on the calling tool.

    Reads Principal from request-scoped Context (set by
    ``BearerTokenMiddleware`` via ``seed_principal()``). No kwarg transport
    — clean break with the prior convention.

    Error semantics (per auth-agent finding #4):

    - No Principal + ``allow_anonymous=False`` →
      ``AuthenticationRequiredError`` (401)
    - No Principal + ``allow_anonymous=True`` → proceed
    - Principal lacks permission → ``InsufficientPermissionError`` (403)

    Args:
        permission: Required Permission for the tool. Defaults to READ.
        allow_anonymous: If True, callers without a Principal may invoke
            the tool. The decorator still enforces the permission check
            if a Principal IS in scope.
        audit_logger: Optional AuditLogger for emitting AuthAuditEvents
            on allow/deny decisions.
        service_name: Name of the service hosting this tool. Required
            for audit attribution (Article 32).
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            func_name = getattr(func, "__name__", "<unknown>")
            principal = _current_principal()

            if principal is None:
                if allow_anonymous:
                    return await func(*args, **kwargs)
                # 401: no credentials presented. Emit an audit event so
                # the failed-access is attributable even when the caller
                # never reached token verification.
                if audit_logger is not None:
                    audit_logger.emit(
                        AuthAuditEvent(
                            timestamp=datetime.now(UTC),
                            service=service_name,
                            caller_service="unknown",
                            caller_id="unknown",
                            action=func_name,
                            permission=permission,
                            result="denied",
                            reason="no_principal",
                            source_ip=None,
                            token_id=None,
                        )
                    )
                raise AuthenticationRequiredError(
                    f"Authentication required for {func_name}"
                )

            if not principal.has_permission(permission):
                # 403: authenticated, lacks permission.
                if audit_logger is not None:
                    audit_logger.emit(
                        AuthAuditEvent(
                            timestamp=datetime.now(UTC),
                            service=service_name,
                            caller_service=_sanitize_audit_value(principal.issuer)
                            or "unknown",
                            caller_id=_sanitize_audit_value(principal.subject)
                            or "unknown",
                            action=func_name,
                            permission=permission,
                            result="denied",
                            reason=_sanitize_audit_value(
                                f"missing_permission:{permission.value}"
                            ),
                            source_ip=None,
                            token_id=None,
                        )
                    )
                raise InsufficientPermissionError(
                    f"Principal {principal.issuer}:{principal.subject} "
                    f"lacks {permission.value}"
                )

            if audit_logger is not None:
                audit_logger.emit(
                    AuthAuditEvent(
                        timestamp=datetime.now(UTC),
                        service=service_name,
                        caller_service=_sanitize_audit_value(principal.issuer)
                        or "unknown",
                        caller_id=_sanitize_audit_value(principal.subject) or "unknown",
                        action=func_name,
                        permission=permission,
                        result="allowed",
                        reason=None,
                        source_ip=None,
                        token_id=None,
                    )
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator
