"""BearerTokenMiddleware — FastMCP middleware that verifies Authorization: Bearer tokens.

Why this middleware exists
--------------------------
BearerTokenMiddleware is the runtime binding layer between an authenticated
HTTP/stdio caller (via FastMCP) and a tool's @require_auth decorator. It
extracts the Bearer token, calls a registered IdentityProvider to verify it,
seeds a request-scoped Principal via contextvars (the source of truth for
@require_auth), and surfaces AuthError subclasses that the optional
AuthErrorTranslationMiddleware (Task 6b) translates into JSON-RPC -32001.

Fixes baked in (from the auth primitives plan review)

* B1 fix: headers are read via ``get_http_headers()`` from
  ``fastmcp.server.dependencies`` — NOT ``MiddlewareContext.scope``. The
  ``scope`` attribute does not exist on FastMCP's MiddlewareContext (verified
  against the FastMCP source). The earlier scope-based test harness was a
  hallucination.

* B2 fix: AuthError subclasses (not HTTPException) propagate out of the
  middleware. FastMCP surfaces these as JSON-RPC errors; the sibling
  ``AuthErrorTranslationMiddleware`` translates to JSON-RPC code ``-32001``
  with an OAuth-style ``data`` payload (RFC 6749 §5.2 codes).

* B3 fix prep: ``verifications_total`` and ``errors_total`` Counter
  properties are exposed so Task 14 sibling wiring can pass them to
  ``AuthHealth.from_providers(...)``. Both are incremented on each verify
  attempt (success / AuthError respectively).

* B4 fix: only ``AuthError`` subclasses are caught. Programming errors
  (``TypeError``, ``KeyError``, etc.) propagate so a bug in our code cannot
  silently become a 401 to the caller.

* M-R2-1 fix: ``get_http_headers()`` is guarded with a bare
  ``except RuntimeError`` even though the FastMCP docstring promises it
  "never raises" — a defensive net so a future API change cannot crash
  the middleware with a programming-error leak.

* M-R2-2 fix: the bypass set does NOT include ``notifications/progress``.
  Per the MCP spec, progress notifications are server→client and never
  reach middleware as an inbound message, so listing them here would be
  a misleading comment.

* M-R2-3 fix: Principal storage captures a snapshot of the prior FastMCP
  ``Context.set_state`` value, restores it in ``finally``. This preserves
  nesting for recursive / internal-hop call paths instead of clobbering
  the value with ``None``.

* M-R2-4 fix: docstring documents the dual storage strategy — ``contextvars``
  (via ``seed_principal``) is the source of truth for ``@require_auth``;
  FastMCP's ``Context.set_state`` is for FastMCP-native consumers.
"""
from __future__ import annotations

import logging
from typing import Any

from fastmcp.server import dependencies as _fmcp_dependencies
from fastmcp.server.middleware import Middleware, MiddlewareContext

from mcp_common.auth.audit import AuditLogger
from mcp_common.auth.config import AuthConfig
from mcp_common.auth.context import (
    _current_principal,
    seed_principal,
)
from mcp_common.auth.exceptions import AuthError
from mcp_common.auth.provider import IdentityProvider

# Module-attribute lookup at call time (not ``from X import Y`` at module
# load) so tests can ``monkeypatch.setattr(fastmcp.server.dependencies,
# "get_http_headers", ...)`` and have the patched callable take effect.
# This is the B-R2-3 fix from the Round 2 review: the test harness
# monkeypatches the module attribute, so the production code must look
# the symbol up at call time.

logger = logging.getLogger(__name__)

# MCP methods that bypass auth.
#
# - ``initialize``: the very first message in the MCP handshake; the client
#   has no Principal yet and a Bearer check would 401 the entire transport.
# - ``notifications/initialized``: client→server ack after the handshake;
#   same argument as ``initialize`` (no Principal yet).
# - ``notifications/cancelled``: client→server cancel notification; the
#   spec allows it on any in-flight request and it cannot itself carry a
#   useful Principal.
# - ``ping``: keepalive probe from the client; spec allows it without
#   auth so servers don't lose connectivity on token expiry.
#
# NOTE: ``notifications/progress`` is intentionally absent. Per the MCP
# spec, progress notifications are server→client and never reach
# middleware as inbound messages; listing them here would be misleading.
_AUTH_BYPASS_METHODS: frozenset[str] = frozenset({
    "initialize",
    "notifications/initialized",
    "notifications/cancelled",
    "ping",
})

# Defense-in-depth cap on the Authorization header. Anything beyond this is
# rejected before any cryptographic operation so a hostile client cannot
# exhaust memory with a multi-MB token.
_MAX_TOKEN_BYTES = 8192


class BearerTokenMiddleware(Middleware):
    """FastMCP middleware that verifies Bearer tokens on every request.

    Workflow (per inbound request):

    1. Bypass if ``context.method`` is in ``_AUTH_BYPASS_METHODS``
       (initialize handshake, ping keepalive, client→server notifications).
    2. Bypass if a Principal is already in the request context (test
       injection or internal hop).
    3. Read headers via ``get_http_headers()`` (FastMCP-native, never
       ``MiddlewareContext.scope``).
    4. Extract ``Authorization: Bearer <token>``; reject oversized tokens.
    5. Verify via the selected ``IdentityProvider``. Increment
       ``verifications_total`` on success, ``errors_total`` on AuthError.
    6. Seed Principal via contextvars (``seed_principal`` returns a Token;
       we restore in ``finally``). Also stash via FastMCP's
       ``Context.set_state`` (with the prior value captured) so
       FastMCP-native consumers can read it.
    7. Re-raise AuthError; let programming errors propagate.

    The middleware exposes two read-only counter properties
    (``verifications_total`` / ``errors_total``) for sibling servers to
    surface in /health. They are integer counters, not Prometheus metrics.
    """

    def __init__(
        self,
        *,
        auth_config: AuthConfig,
        providers: dict[str, IdentityProvider],
        audit_logger: AuditLogger | None = None,
    ) -> None:
        self._config = auth_config
        self._providers = providers
        # B3 fix prep: counter store. Middleware increments on every verify
        # attempt. Sibling servers wire this to the same AuthHealth surface.
        self._verifications_total: int = 0
        self._errors_total: int = 0
        self._audit_logger = audit_logger

    async def on_request(
        self,
        context: MiddlewareContext,
        call_next: Any,
    ) -> Any:
        # I-1 fix: skip auth on MCP handshake + notifications + ping.
        if context.method in _AUTH_BYPASS_METHODS:
            return await call_next(context)

        # Idempotency: skip if Principal already set (test injection or
        # internal hop that already authenticated upstream).
        if _current_principal() is not None:
            return await call_next(context)

        # M-R2-1 fix: bare except RuntimeError. get_http_headers() never
        # raises per its docstring, but we keep the guard so a future
        # FastMCP API change (or unusual embedding) cannot crash the
        # middleware with a programming-error leak.
        try:
            headers = _fmcp_dependencies.get_http_headers() or {}
        except RuntimeError:
            # stdio / non-HTTP transport — Bearer auth is meaningless;
            # pass through and let per-tool allow_anonymous decide.
            return await call_next(context)

        token = _extract_bearer_token(headers)
        if token is None:
            # Anonymous path; per-tool allow_anonymous decides whether to
            # allow or 401.
            return await call_next(context)

        provider = self._select_provider(token)
        try:
            principal = await provider.verify_token(
                token, expected_audience=self._config.service_name
            )
        except AuthError as exc:
            # B4 fix: only catch AuthError. Programming errors propagate.
            self._errors_total += 1
            if self._audit_logger is not None and hasattr(
                self._audit_logger, "log_failure"
            ):
                self._audit_logger.log_failure(
                    source="middleware",
                    reason=type(exc).__name__,
                    token_present=True,
                )
            raise
        else:
            self._verifications_total += 1
            if self._audit_logger is not None and hasattr(
                self._audit_logger, "log_success"
            ):
                self._audit_logger.log_success(
                    source="middleware",
                    principal_issuer=principal.issuer,
                    principal_subject=principal.subject,
                )

        # M-R2-4 fix: dual storage. contextvars is the source of truth for
        # @require_auth (it lives in the same execution context as the tool
        # function). FastMCP's Context.set_state is best-effort for
        # FastMCP-native consumers (middleware / tools that read state).
        token_handle = seed_principal(principal)

        # M-R2-3 fix: capture prior state so we can restore it in finally.
        # FastMCP's Context.set_state returns None (not a Token); we have
        # to snapshot the prior value ourselves via get_state() and restore
        # with delete_state() / set_state() in finally.
        fmcp_ctx = getattr(context, "fastmcp_context", None)
        state_key = "principal"
        prior_state: Any = _SENTINEL
        if fmcp_ctx is not None:
            try:
                prior_state = fmcp_ctx.get_state(state_key)
            except (AttributeError, TypeError):
                prior_state = _SENTINEL
            try:
                # Principal is a frozen dataclass with frozenset[Permission]
                # and datetime — not JSON-serializable. serializable=False
                # scopes the entry to the current request only.
                fmcp_ctx.set_state(state_key, principal, serializable=False)
            except (AttributeError, TypeError) as exc:
                # set_state is best-effort; contextvars is the source of truth.
                logger.debug("set_state failed in middleware (non-fatal): %s", exc)

        try:
            return await call_next(context)
        finally:
            # Restore prior Principal via token handle rather than
            # unconditionally clearing — preserves nesting for recursive
            # / internal-hop call paths.
            token_handle.var.reset(token_handle)
            if fmcp_ctx is not None and prior_state is not _SENTINEL:
                try:
                    if prior_state is None:
                        fmcp_ctx.delete_state(state_key)
                    else:
                        fmcp_ctx.set_state(
                            state_key, prior_state, serializable=False
                        )
                except (AttributeError, TypeError):
                    pass

    def _select_provider(self, token: str) -> IdentityProvider:
        """Pick provider by ``default_provider`` hint or single-provider fallback.

        For multi-provider deployments, prefer ``default_provider``. A future
        enhancement can decode the JWT header and pick by ``kid`` (Key ID).
        """
        if (
            self._config.default_provider
            and self._config.default_provider in self._providers
        ):
            return self._providers[self._config.default_provider]
        if len(self._providers) == 1:
            return next(iter(self._providers.values()))
        # Fail-loud at request time if misconfigured. Per api-security
        # IMPORTANT finding: don't per-request 500 for config errors;
        # surface at startup via validate_auth_config() (Task 7).
        raise RuntimeError(
            f"Multiple providers configured but no default_provider set; "
            f"cannot select one for token verification. Configured: "
            f"{list(self._providers.keys())}"
        )

    @property
    def verifications_total(self) -> int:
        """Count of successful token verifications since process start."""
        return self._verifications_total

    @property
    def errors_total(self) -> int:
        """Count of AuthError raises from verify_token since process start."""
        return self._errors_total


def _extract_bearer_token(headers: dict[str, str]) -> str | None:
    """Extract ``Authorization: Bearer <token>`` from a headers dict.

    B1 fix: takes a ``dict[str, str]`` (from ``get_http_headers``), not a
    ``MiddlewareContext``. Reject tokens longer than ``_MAX_TOKEN_BYTES``
    bytes (api-security: prevent memory exhaustion via a huge
    Authorization header).
    """
    auth = headers.get("authorization")
    if not auth:
        return None
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    if len(token) > _MAX_TOKEN_BYTES:
        # Reject oversized tokens before any cryptographic operation
        return None
    return token


# Internal sentinel for the "no prior state" case in M-R2-3 restore. We
# can't use ``None`` because ``None`` is a legitimate state value
# (Context.get_state returns None when the key is unset, but we also want
# to distinguish "key absent" from "key was None" if a previous call set
# it). A unique sentinel makes the restore unambiguous.
_SENTINEL = object()
