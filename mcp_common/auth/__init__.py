from __future__ import annotations

from mcp_common.auth.config import AuthConfig
from mcp_common.auth.core import (
    JWT_ALGORITHM,
    TokenPayload,
    create_service_token,
    verify_token,
)
from mcp_common.auth.exceptions import (
    AudienceMismatchError,
    AuthError,
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
from mcp_common.auth.permissions import (
    Permission,
    Role,
    ROLE_PERMISSIONS,
)

__all__ = [
    "AudienceMismatchError",
    "AuthConfig",
    "AuthError",
    "InsufficientPermissionError",
    "JWT_ALGORITHM",
    "KNOWN_SERVICES",
    "Permission",
    "Role",
    "ROLE_PERMISSIONS",
    "SecretNotConfiguredError",
    "ServiceIdentity",
    "TokenExpiredError",
    "TokenInvalidError",
    "TokenPayload",
    "UnknownIssuerError",
    "create_service_token",
    "verify_audience",
    "verify_issuer",
    "verify_token",
]
