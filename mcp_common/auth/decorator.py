from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps
from typing import Any

from mcp_common.auth.audit import AuditLogger, AuthAuditEvent
from mcp_common.auth.config import AuthConfig
from mcp_common.auth.core import verify_token
from mcp_common.auth.exceptions import (
    AuthError,
    InsufficientPermissionError,
    TokenInvalidError,
)
from mcp_common.auth.permissions import Permission

logger = logging.getLogger(__name__)
_default_audit = AuditLogger()


def require_auth(
    permission: Permission = Permission.READ,
    *,
    config: AuthConfig | None = None,
    service_name: str | None = None,
    audit_logger: AuditLogger | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            cfg = config
            svc = service_name or (cfg.service_name if cfg else "unknown")
            along = audit_logger or _default_audit

            if cfg is None or not cfg.enabled:
                logger.debug("auth disabled for %s — allowing anonymous", func.__name__)
                return await func(*args, **kwargs)

            token_str = kwargs.pop("__auth_token__", None)
            if token_str is None:
                along.emit(
                    AuthAuditEvent(
                        timestamp=datetime.now(UTC),
                        service=svc,
                        caller_service="unknown",
                        caller_id="unknown",
                        action=func.__name__,
                        permission=permission,
                        result="denied",
                        reason="no __auth_token__ provided",
                        source_ip=None,
                        token_id=None,
                    )
                )
                raise TokenInvalidError("No __auth_token__ provided")

            try:
                payload = verify_token(
                    token_str, secret=cfg.secret, expected_audience=svc
                )
            except AuthError as exc:
                along.emit(
                    AuthAuditEvent(
                        timestamp=datetime.now(UTC),
                        service=svc,
                        caller_service="unknown",
                        caller_id="unknown",
                        action=func.__name__,
                        permission=permission,
                        result="denied",
                        reason=str(exc),
                        source_ip=None,
                        token_id=None,
                    )
                )
                raise

            if permission not in payload.permissions:
                along.emit(
                    AuthAuditEvent(
                        timestamp=datetime.now(UTC),
                        service=svc,
                        caller_service=payload.issuer,
                        caller_id=payload.subject,
                        action=func.__name__,
                        permission=permission,
                        result="denied",
                        reason=f"insufficient permission: needs {permission.value!r}",
                        source_ip=None,
                        token_id=payload.jti,
                    )
                )
                raise InsufficientPermissionError(
                    f"{func.__name__!r} requires {permission.value!r}; "
                    f"caller has {[p.value for p in payload.permissions]}"
                )

            along.emit(
                AuthAuditEvent(
                    timestamp=datetime.now(UTC),
                    service=svc,
                    caller_service=payload.issuer,
                    caller_id=payload.subject,
                    action=func.__name__,
                    permission=permission,
                    result="allowed",
                    reason=None,
                    source_ip=None,
                    token_id=payload.jti,
                )
            )
            kwargs["__auth_payload__"] = payload
            return await func(*args, **kwargs)

        return wrapper

    return decorator
