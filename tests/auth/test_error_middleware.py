"""Tests for AuthErrorTranslationMiddleware (Task 6b).

I-R2-3 fix: ships the JSON-RPC -32001 translation surface that the B2 fix
relied on. The middleware catches AuthError subclasses raised inside the
FastMCP pipeline and re-raises them as a JSON-RPC-shaped error with OAuth
error codes per RFC 6749 §5.2 in the data payload.
"""
from __future__ import annotations

import pytest

from mcp_common.auth.error_middleware import AuthErrorTranslationMiddleware
from mcp_common.auth.exceptions import (
    AuthenticationRequiredError,
    InsufficientPermissionError,
    TokenInvalidError,
)


@pytest.mark.asyncio
async def test_translates_authentication_required_to_jsonrpc_error():
    """401 semantic: maps AuthenticationRequiredError to JSON-RPC -32001 with
    WWW-Authenticate-style data payload."""
    mw = AuthErrorTranslationMiddleware()
    error = AuthenticationRequiredError("no token")
    payload = mw._translate(error)
    assert payload["code"] == -32001
    assert payload["data"]["error"] == "authentication_required"
    assert "WWW-Authenticate" in payload["data"]


@pytest.mark.asyncio
async def test_translates_insufficient_permission_to_jsonrpc_error():
    """403 semantic: maps InsufficientPermissionError to JSON-RPC -32001."""
    mw = AuthErrorTranslationMiddleware()
    error = InsufficientPermissionError("lacks read")
    payload = mw._translate(error)
    assert payload["code"] == -32001
    assert payload["data"]["error"] == "insufficient_permission"


@pytest.mark.asyncio
async def test_translates_token_invalid_to_jsonrpc_error():
    """401 semantic: maps TokenInvalidError to JSON-RPC -32001."""
    mw = AuthErrorTranslationMiddleware()
    error = TokenInvalidError("bad sig")
    payload = mw._translate(error)
    assert payload["code"] == -32001
    assert payload["data"]["error"] == "invalid_token"