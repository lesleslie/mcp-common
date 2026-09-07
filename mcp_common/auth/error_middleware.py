"""AuthError → JSON-RPC translation middleware.

I-R2-3 fix: ships the translation surface that B2 fix relied on. Sibling
servers opt in via FastMCP(middleware=[AuthErrorTranslationMiddleware(), ...]).
"""
from __future__ import annotations

from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

from mcp_common.auth.exceptions import (
    AuthenticationRequiredError,
    InsufficientPermissionError,
    TokenInvalidError,
    UnknownIssuerError,
)


# JSON-RPC error code for auth/server-defined errors per the MCP spec.
_JSONRPC_AUTH_ERROR_CODE = -32001

# OAuth 2.0 error codes per RFC 6749 §5.2.
_ERROR_CODE_MAP: dict[type, str] = {
    AuthenticationRequiredError: "authentication_required",
    TokenInvalidError: "invalid_token",
    UnknownIssuerError: "unknown_issuer",
    InsufficientPermissionError: "insufficient_permission",
}


class AuthErrorTranslationMiddleware(Middleware):
    """Translate AuthError subclasses into JSON-RPC error code -32001 with
    OAuth-style data payload. Sibling servers must install this in their
    FastMCP constructor for the B2 contract to hold end-to-end.
    """

    async def on_request(
        self, context: MiddlewareContext, call_next: Any
    ) -> Any:
        try:
            return await call_next(context)
        except (
            AuthenticationRequiredError,
            TokenInvalidError,
            UnknownIssuerError,
            InsufficientPermissionError,
        ) as exc:
            payload = self._translate(exc)
            raise _AuthJSONRPCError(payload) from exc

    def _translate(self, exc: Exception) -> dict[str, Any]:
        return {
            "code": _JSONRPC_AUTH_ERROR_CODE,
            "message": "Authentication error",
            "data": {
                "error": _ERROR_CODE_MAP.get(type(exc), "authentication_error"),
                "error_description": str(exc),
                "WWW-Authenticate": 'Bearer realm="mcp"',
            },
        }


class _AuthJSONRPCError(Exception):
    """Internal carrier for the translated payload; raised into the FastMCP
    pipeline so it surfaces as a JSON-RPC error to the client."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        super().__init__(payload["message"])