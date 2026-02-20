"""JWT authentication utilities for WebSocket connections.

This module provides JWT-based authentication for WebSocket servers and clients
in the MCP ecosystem. It supports token generation, verification, and permission
checking for secure real-time connections.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

try:
    import jwt
    from jwt import ExpiredSignatureError, InvalidTokenError
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

logger = logging.getLogger(__name__)


class WebSocketAuthenticator:
    """Handles WebSocket connection authentication using JWT.

    Provides methods for creating signed JWT tokens, verifying tokens, and
    authenticating WebSocket connections with optional permission checking.

    Example:
        >>> auth = WebSocketAuthenticator(secret="your-secret-key")
        >>> token = auth.create_token({"user_id": "user123"})
        >>> payload = auth.verify_token(token)
    """

    def __init__(
        self,
        secret: str,
        algorithm: str = "HS256",
        token_expiry: int = 3600,
    ):
        """Initialize authenticator.

        Args:
            secret: JWT secret key for signing tokens
            algorithm: JWT algorithm (default: HS256)
            token_expiry: Token expiry time in seconds (default: 1 hour)

        Raises:
            ImportError: If PyJWT is not installed
        """
        if not JWT_AVAILABLE:
            raise ImportError(
                "PyJWT is required for JWT authentication. "
                "Install it with: pip install PyJWT"
            )

        self.secret = secret
        self.algorithm = algorithm
        self.token_expiry = token_expiry

    def create_token(self, payload: dict[str, Any]) -> str:
        """Create JWT token for WebSocket authentication.

        Adds standard JWT claims (exp, iat) to the provided payload.

        Args:
            payload: Token payload data (user_id, permissions, etc.)

        Returns:
            Encoded JWT token as a string

        Example:
            >>> token = auth.create_token({
            ...     "user_id": "user123",
            ...     "permissions": ["read", "write"]
            ... })
        """
        # Create a copy to avoid modifying the original
        token_payload = payload.copy()

        # Add standard claims
        token_payload["exp"] = datetime.now(UTC) + timedelta(seconds=self.token_expiry)
        token_payload["iat"] = datetime.now(UTC)

        # Encode token
        token = jwt.encode(token_payload, self.secret, algorithm=self.algorithm)
        return token

    def verify_token(self, token: str) -> dict[str, Any] | None:
        """Verify JWT token and return payload.

        Args:
            token: JWT token to verify

        Returns:
            Decoded payload dictionary if valid, None if invalid

        Example:
            >>> payload = auth.verify_token(token)
            >>> if payload:
            ...     print(f"User: {payload['user_id']}")
        """
        if not JWT_AVAILABLE:
            logger.error("PyJWT not available for token verification")
            return None

        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm]
            )
            return payload
        except ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

    def authenticate_connection(
        self,
        token: str,
        required_permissions: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Authenticate WebSocket connection with optional permission check.

        Verifies the token and optionally checks if the user has all required
        permissions.

        Args:
            token: JWT token from connection handshake
            required_permissions: Optional list of required permissions

        Returns:
            User payload if authenticated and authorized, None otherwise

        Example:
            >>> # Require admin permission
            >>> user = auth.authenticate_connection(
            ...     token,
            ...     required_permissions=["admin"]
            ... )
            >>> if user:
            ...     print(f"Authenticated: {user['user_id']}")
        """
        payload = self.verify_token(token)

        if payload is None:
            return None

        # Check permissions if required
        if required_permissions:
            user_permissions = payload.get("permissions", [])
            if not all(perm in user_permissions for perm in required_permissions):
                logger.warning(
                    f"Insufficient permissions: required {required_permissions}, "
                    f"has {user_permissions}"
                )
                return None

        return payload


def generate_test_token(
    user_id: str,
    permissions: list[str] | None = None,
    secret: str = "test-secret",
) -> str:
    """Generate a test JWT token for development/testing.

    Args:
        user_id: User identifier
        permissions: List of permissions (default: ["read"])
        secret: JWT secret (default: "test-secret")

    Returns:
        JWT token string

    Example:
        >>> token = generate_test_token("user123", ["read", "write"])
    """
    auth = WebSocketAuthenticator(secret=secret)
    return auth.create_token({
        "user_id": user_id,
        "permissions": permissions or ["read"],
    })
