from __future__ import annotations

from mcp_common.auth.audit import AuditLogger, AuditSink, AuthAuditEvent
from mcp_common.auth.config import AuthConfig
from mcp_common.auth.context import (
    seed_principal,
)
from mcp_common.auth.core import (
    JWT_ALGORITHM,
    TokenPayload,
    create_service_token,
    verify_token,
)
from mcp_common.auth.decorator import require_auth
from mcp_common.auth.exceptions import (
    AudienceMismatchError,
    AuthError,
    AuthenticationRequiredError,
    InsufficientPermissionError,
    SecretNotConfiguredError,
    TokenExpiredError,
    TokenInvalidError,
    UnknownIssuerError,
)
from mcp_common.auth.identity import (
    KNOWN_SERVICES,
    ServiceIdentity,
    verify_audience,
    verify_issuer,
)
from mcp_common.auth.middleware import BearerTokenMiddleware
from mcp_common.auth.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    Role,
)
from mcp_common.auth.principal import Principal
from mcp_common.auth.provider import IdentityProvider, ProviderHealth, ProviderState

__all__ = [
    "JWT_ALGORITHM",
    "KNOWN_SERVICES",
    "ROLE_PERMISSIONS",
    "AudienceMismatchError",
    "AuditLogger",
    "AuditSink",
    "AuthAuditEvent",
    "AuthConfig",
    "AuthError",
    "AuthenticationRequiredError",
    "BearerTokenMiddleware",
    "IdentityProvider",
    "InsufficientPermissionError",
    "Permission",
    "Principal",
    "ProviderHealth",
    "ProviderState",
    "Role",
    "SecretNotConfiguredError",
    "ServiceIdentity",
    "TokenExpiredError",
    "TokenInvalidError",
    "TokenPayload",
    "UnknownIssuerError",
    "create_service_token",
    "require_auth",
    "seed_principal",
    "verify_audience",
    "verify_issuer",
    "verify_token",
]
