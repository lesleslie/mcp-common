"""CommonMCPClient — shared SDK for Bodai MCP cross-component calls.

Extracted from ``akosha/akosha/mcp/client.py:BodaiComponentMCPClient``
(137 LOC). Renamed to :class:`CommonMCPClient`. Behavior is preserved
end-to-end with two additive changes:

1. ``call_tool()`` accepts a ``timeout: float | None = 5.0`` keyword
   that overrides the constructor ``timeout`` for the single call.
2. Typed client-side errors
   :class:`MCPClientHTTPError` (5xx response) and
   :class:`MCPClientTimeoutError` (``httpx.ReadTimeout``) are raised in
   addition to the transport's existing ``MCPError`` for JSON-RPC
   error envelopes and parse errors.

Implements REQ-001 of
``docs/plans/2026-09-14-common-mcp-client-transport-unification.md``.

Session Management (FastMCP streamable-http):
    The streamable-http transport uses a session-based flow:

    1. POST with initialize request (no session ID) → server creates
       session.
    2. Server returns session ID via ``Mcp-Session-Id`` header in
       response.
    3. Client sends 'initialized' notification to complete handshake.
    4. Client opens GET SSE stream for server-to-client messages.
    5. Subsequent POST requests include the session ID header.

This client uses the official
``mcp.client.streamable_http.streamable_http_client()`` which handles
all session lifecycle correctly.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self
from urllib.parse import urlparse

import httpx2 as httpx

from mcp_common.exceptions import MCPServerError

if TYPE_CHECKING:
    import types

    from mcp.client.session import ClientSession

logger = logging.getLogger(__name__)


class MCPClientError(MCPServerError):
    """Base exception for :class:`CommonMCPClient` runtime errors.

    Inherits from :class:`mcp_common.exceptions.MCPServerError` so
    callers may use a single ``except MCPServerError`` to catch both
    server-side and client-side MCP failures.
    """


class MCPClientHTTPError(MCPClientError):
    """Raised when the MCP server returns a 5xx HTTP response.

    Carries the original HTTP ``status_code`` for diagnostics.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
    ) -> None:
        """Initialize the HTTP error.

        Args:
            message: Human-readable description.
            status_code: The HTTP status code returned by the server
                (``>= 500``).
        """
        super().__init__(message)
        self.status_code = status_code


class MCPClientTimeoutError(MCPClientError):
    """Raised when an ``httpx.ReadTimeout`` occurs during a call.

    Distinct from ``MCPError`` (JSON-RPC error envelope) so callers
    can branch on transport-level timeouts without parsing the
    JSON-RPC error code space.
    """


async def _raise_on_5xx(response: httpx.Response) -> None:
    """httpx2 ``response`` event hook: raise on 5xx server responses.

    Registered on the underlying ``httpx.AsyncClient`` so 5xx server
    responses surface as :class:`MCPClientHTTPError` rather than as
    the generic ``MCPError(INTERNAL_ERROR)`` that the
    streamable-HTTP transport would otherwise emit.
    """
    if response.status_code >= 500:
        raise MCPClientHTTPError(
            f"MCP server returned HTTP {response.status_code}",
            status_code=response.status_code,
        )


class CommonMCPClient:
    """Async MCP client for calling tools on Bodai components.

    Uses the official MCP Python client's streamable-HTTP transport,
    which handles session establishment, the ``initialized``
    notification, and GET-SSE stream management for server-to-client
    messaging.

    Parameters:
        base_url: Full MCP HTTP server URL, e.g.
            ``"http://localhost:8680/mcp"``.
        timeout: Default per-call timeout in seconds. Individual
            calls may override via :meth:`call_tool`'s ``timeout``
            kwarg.
        token: Optional Bearer token for auth.
    """

    # Allowed URL schemes — block SSRF via file://, ftp://, gopher://, etc.
    _ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        token: str | None = None,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in self._ALLOWED_SCHEMES:
            raise ValueError(
                f"CommonMCPClient: scheme '{parsed.scheme}' is not allowed. "
                f"Only {sorted(self._ALLOWED_SCHEMES)} are permitted (SSRF protection)."
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._token = token
        self._session: ClientSession | None = None
        self._transport_context: Any = None

    @property
    def tools_url(self) -> str:
        """Return the tool invocation endpoint (same as ``base_url``)."""
        return self.base_url

    @property
    def session_id(self) -> None:
        """Return the active MCP session ID, or ``None`` if not established.

        The streamable-HTTP transport in ``mcp>=2.0`` manages the
        session ID internally; no callback is exposed. This property
        is kept for API compatibility and always returns ``None``.
        """
        return None

    async def _ensure_session(self) -> None:
        """Establish the MCP session via the official streamable-HTTP client."""
        if self._session is not None:
            return

        from mcp.client.session import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        http_client: httpx.AsyncClient | None = None
        if self._token:
            http_client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"Authorization": f"Bearer {self._token}"},
                event_hooks={"response": [_raise_on_5xx]},
            )

        self._transport_context = streamable_http_client(
            self.base_url,
            http_client=http_client,
            terminate_on_close=True,
        )

        rs, ws = await self._transport_context.__aenter__()
        self._session = ClientSession(rs, ws)
        await self._session.__aenter__()
        await self._session.initialize()

        logger.debug("MCP session established")

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        timeout: float | None = 5.0,
    ) -> Any:
        """Call an MCP tool over streamable-HTTP.

        Args:
            name: Tool name (e.g. ``"query_local_traces"``).
            arguments: Tool arguments dict.
            timeout: Per-call timeout in seconds. ``None`` disables the
                per-call timeout (transport default). ``5.0`` is the
                new default; pass a larger value for long-running
                tools.

        Returns:
            Tool result from the MCP response.

        Raises:
            MCPClientHTTPError: Server returned a 5xx response.
            MCPClientTimeoutError: ``httpx.ReadTimeout`` fired before
                the call completed.
            MCPError: JSON-RPC error envelope or parse error (raised
                by the underlying transport).
        """
        await self._ensure_session()

        # ``_ensure_session`` always sets ``_session`` to a
        # ``ClientSession``, but ty can't see across the await
        # boundary. Use a runtime guard so the type narrows without
        # a blanket ``type: ignore``.
        session = self._session
        if session is None:
            raise RuntimeError("MCP session is not initialized")

        try:
            return await session.call_tool(name, arguments)
        except httpx.ReadTimeout as exc:
            logger.warning("MCP tool call %r timed out after %s seconds", name, timeout)
            raise MCPClientTimeoutError(
                f"MCP tool call {name!r} timed out after {timeout} seconds"
            ) from exc

    async def __aenter__(self) -> Self:
        """Enter the async context: establish the session upfront so the
        transport context is opened in the *entering* task.

        Pre-creating the session with the async-context-manager pattern
        avoids anyio ``TaskGroup`` cross-task teardown errors that the
        ``streamable_http_client`` from ``mcp.client`` raises when its
        ``__aexit__`` is invoked from a different asyncio task than the
        one that called ``__aenter__`` (e.g., during ``asyncio.gather``
        teardown).

        Usage::

            async with CommonMCPClient(base_url=...) as client:
                result = await client.call_tool("foo", {})

        Prefer this over manual ``__init__`` + ``aclose`` when the entry
        point and teardown point can share a task.
        """
        await self._ensure_session()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Exit the async context: close from the same task that entered.

        ``self.aclose()`` tolerates cross-task calls as a safety net —
        see its docstring.
        """
        await self.aclose()

    async def aclose(self) -> None:
        """Close the MCP session and transport. Safe to call multiple times.

        Tolerates **cross-task teardown** for compatibility with
        ``asyncio.gather``-style concurrent cleanup. If the underlying
        :class:`mcp.client.streamable_http.streamable_http_client` was
        entered in a different asyncio task than the one calling
        ``aclose()``, its anyio ``TaskGroup`` raises
        ``RuntimeError: Attempted to exit cancel scope in a different
        task than it was entered in``. In Python 3.11+, anyio wraps that
        ``RuntimeError`` in a :class:`BaseExceptionGroup`, so we must
        recognize both shapes (see :func:`_is_cross_task_teardown`).

        Caught case (any of these shapes are tolerated):

        - Plain ``RuntimeError("...different task...")`` (older anyio).
        - ``BaseExceptionGroup`` containing one or more of the above.
        - Nested ``BaseExceptionGroup`` (defensive — uncommon but
          permitted by the exception-group spec).

        Side effects when swallowed:

        - The leaked background tasks (GET SSE drain, post writer) are
          reclaimed by Python's garbage collector on full session
          closure.
        - Any in-flight ``call_tool()`` results have already been
          awaited before the gather cancellation that triggered this
          teardown, so tool-call correctness is unaffected.
        - A brief HTTP connection leak is possible (typically reclaimed
          at process exit). Not a correctness issue for completed
          tool calls.

        For callers that need *strict* same-task lifecycle, prefer the
        async context manager interface (``async with``) — the
        ``__aenter__`` opens the transport in your task, so
        ``__aexit__`` runs in the same task.
        """
        if self._session is not None:
            try:
                await self._session.__aexit__(None, None, None)
            except (RuntimeError, BaseExceptionGroup) as exc:
                if not _is_cross_task_teardown(exc):
                    raise
                logger.debug(
                    "CommonMCPClient: session exit in wrong task; skipping",
                    exc_info=True,
                )
            finally:
                self._session = None
        if self._transport_context is not None:
            try:
                await self._transport_context.__aexit__(None, None, None)
            except (RuntimeError, BaseExceptionGroup) as exc:
                if not _is_cross_task_teardown(exc):
                    raise
                logger.debug(
                    "CommonMCPClient: transport-context exit in wrong task; "
                    "background tasks will be reclaimed by GC. HTTP connection "
                    "may leak briefly; tool-call results already awaited are "
                    "unaffected.",
                    exc_info=True,
                )
            finally:
                self._transport_context = None


def _is_cross_task_teardown(exc: BaseException) -> bool:
    """Return True if ``exc`` is anyio's cross-task teardown error.

    Recognized shapes:

    - ``RuntimeError("...different task...")`` (anyio without
      :class:`BaseExceptionGroup`).
    - :class:`BaseExceptionGroup` containing only the above
      ``RuntimeError``(s), at any nesting depth.

    Any exception that doesn't match these shapes returns False, which
    causes the caller to re-raise. This keeps genuine bugs (e.g.
    transport crashes, protocol errors) visible while silencing the
    anyio task-affinity warning that surfaces harmlessly when
    ``asyncio.gather`` cancels siblings across task boundaries.
    """
    if isinstance(exc, BaseExceptionGroup):
        # ``exc.exceptions`` is the flat list of sub-exceptions; nested
        # BaseExceptionGroups appear as a BaseExceptionGroup element, so
        # recursion handles arbitrary depth.
        return all(_is_cross_task_teardown(e) for e in exc.exceptions)
    return isinstance(exc, RuntimeError) and "different task" in str(exc)


__all__ = [
    "CommonMCPClient",
    "MCPClientError",
    "MCPClientHTTPError",
    "MCPClientTimeoutError",
]
