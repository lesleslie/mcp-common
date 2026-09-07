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
    AuthenticationRequiredError,
    AuthError,
    InsufficientPermissionError,
    SecretNotConfiguredError,
    TokenExpiredError,
    TokenInvalidError,
    UnknownIssuerError,
)
from mcp_common.auth.identity import (
    IdentityProviderSpec,
    ServiceIdentity,
    validate_auth_config,
    verify_audience,
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
    "IdentityProviderSpec",
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
    "validate_auth_config",
    "verify_audience",
    "verify_token",
]
