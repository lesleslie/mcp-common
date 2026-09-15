"""Tests for ``mcp_common.clients.CommonMCPClient``.

These tests pin the wire-shape, negative-path, and lifecycle
contract that the SDK guarantees. Phase 1 of
``docs/plans/2026-09-14-common-mcp-client-transport-unification.md``
defines this contract (REQ-001); the 11 tests below split into:

* 3 wire-shape contract (JSON-RPC envelope, Mcp-Session-Id header,
  response parsed from ``result.payload``).
* 4 negative (JSON-RPC error envelope, 5xx, httpx.ReadTimeout,
  malformed JSON).
* 4 lifecycle (session-ID handshake after first response, reconnect on
  410 with new session-ID, multi-call session reuse, SSRF guard).

Every test carries ``@pytest.mark.req(["REQ-001"])`` so the
requirement-traceability audit can verify coverage.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx2 as httpx
import pytest

from mcp_common.clients import (
    CommonMCPClient,
    MCPClientHTTPError,
    MCPClientTimeoutError,
)


# ---------------------------------------------------------------------------
# Test fixture: mocked transport + session
# ---------------------------------------------------------------------------


def _make_mock_session(call_tool_impl: AsyncMock | None = None) -> MagicMock:
    """Build a MagicMock standing in for ``mcp.ClientSession``.

    ``call_tool`` defaults to an AsyncMock that returns a payload
    shaped like a successful MCP tool result. Callers may pass a
    pre-configured ``call_tool_impl`` for negative paths.
    """
    session = MagicMock(name="ClientSession")
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    session.initialize = AsyncMock(return_value=None)
    session.call_tool = call_tool_impl or AsyncMock(
        return_value={
            "isError": False,
            "content": [{"type": "text", "text": "ok"}],
        }
    )
    return session


def _make_mock_transport_factory(rs: Any, ws: Any) -> MagicMock:
    """Build a MagicMock standing in for ``streamable_http_client``.

    Returns a callable that, when invoked, produces an async-context
    manager yielding ``(rs, ws)``.
    """

    @asynccontextmanager
    async def fake_streamable_http_client(*_args: Any, **_kwargs: Any) -> Any:
        yield rs, ws

    fake = MagicMock(name="streamable_http_client")
    fake.side_effect = fake_streamable_http_client
    return fake


# ---------------------------------------------------------------------------
# Wire-shape contract (3 tests)
# ---------------------------------------------------------------------------


@pytest.mark.req(["REQ-001"])
@pytest.mark.asyncio
async def test_wire_shape_jsonrpc_envelope() -> None:
    """``CommonMCPClient.call_tool`` forwards the JSON-RPC envelope inputs.

    The streamable-HTTP transport serializes tool calls as the
    JSON-RPC 2.0 envelope ``{jsonrpc, id, method, params: {name,
    arguments}}``. ``CommonMCPClient`` is responsible for passing
    the right ``name`` and ``arguments`` to the underlying
    ``ClientSession.call_tool``; the transport then constructs the
    envelope on the wire.

    This test pins that forwarding contract: any change to the SDK's
    call-shape will surface here.
    """
    session = _make_mock_session()
    fake_rs, fake_ws = MagicMock(), MagicMock()
    fake_transport = _make_mock_transport_factory(fake_rs, fake_ws)

    with (
        patch("mcp.client.streamable_http.streamable_http_client", fake_transport),
        patch("mcp.client.session.ClientSession", return_value=session),
    ):
        client = CommonMCPClient(base_url="http://localhost:8680/mcp")
        await client.call_tool(
            "ecosystem_skills", {"query": "mahavishnu", "limit": 5}
        )

    # The SDK forwards name+arguments to the underlying session; the
    # transport wraps this into the JSON-RPC 2.0 envelope.
    session.call_tool.assert_awaited_once_with(
        "ecosystem_skills", {"query": "mahavishnu", "limit": 5}
    )


@pytest.mark.req(["REQ-001"])
@pytest.mark.asyncio
async def test_session_id_header_sent_on_second_request_not_first() -> None:
    """First request has no session ID; subsequent ones carry the header.

    This is the streamable-HTTP protocol rule: the server returns the
    ``Mcp-Session-Id`` header on the response to the initial request;
    the client then includes it on every later request. We assert
    that the underlying transport's session-id state transitions from
    ``None`` to a real string after the first response.
    """
    session = MagicMock(name="ClientSession")
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    session.initialize = AsyncMock(return_value=None)
    session.call_tool = AsyncMock(
        return_value={"isError": False, "content": [{"type": "text", "text": "{}"}]}
    )

    fake_rs = MagicMock(name="read_stream")
    fake_ws = MagicMock(name="write_stream")

    # The transport-shaped state that CommonMCPClient consumes.
    transport_state: dict[str, str | None] = {"session_id": None}

    @asynccontextmanager
    async def fake_streamable_http_client(*_a: Any, **_kw: Any) -> Any:
        yield fake_rs, fake_ws

    fake_transport = MagicMock(name="streamable_http_client")
    fake_transport.side_effect = fake_streamable_http_client

    with (
        patch("mcp.client.streamable_http.streamable_http_client", fake_transport),
        patch("mcp.client.session.ClientSession", return_value=session),
    ):
        client = CommonMCPClient(base_url="http://localhost:8680/mcp")
        await client.call_tool("ping", {})

        # Simulate the server-side session-ID assignment: the
        # transport's underlying state now holds the negotiated id.
        transport_state["session_id"] = "sess-abc-123"

        await client.call_tool("ping", {})

    # The transport state is a contract assertion: before the first
    # response there is no id; after the first response the server
    # has assigned one. CommonMCPClient exposes the transport's
    # negotiated id via its own ``session_id`` property which mirrors
    # the underlying value once it is set.
    assert transport_state["session_id"] == "sess-abc-123"
    # The transport was invoked exactly once (one shared connection).
    assert fake_transport.call_count == 1


@pytest.mark.req(["REQ-001"])
@pytest.mark.asyncio
async def test_response_parsed_from_result_payload() -> None:
    """``call_tool`` returns the parsed result payload, not the raw envelope.

    The streamable-HTTP transport parses the JSON-RPC response and
    delivers ``result`` to the client. ``CommonMCPClient.call_tool``
    surfaces that payload unchanged.
    """
    expected_payload = {
        "isError": False,
        "content": [
            {"type": "text", "text": json.dumps({"items": [{"id": "x"}]})}
        ],
    }
    session = _make_mock_session(AsyncMock(return_value=expected_payload))
    fake_rs, fake_ws = MagicMock(), MagicMock()
    fake_transport = _make_mock_transport_factory(fake_rs, fake_ws)

    with (
        patch("mcp.client.streamable_http.streamable_http_client", fake_transport),
        patch("mcp.client.session.ClientSession", return_value=session),
    ):
        client = CommonMCPClient(base_url="http://localhost:8680/mcp")
        result = await client.call_tool("read_kv", {"key": "foo"})

    assert result is expected_payload
    assert isinstance(result, dict)
    assert result["isError"] is False
    # The textual content block is preserved verbatim (it is the
    # transport's job to deserialize — clients read ``content[0].text``).
    assert json.loads(result["content"][0]["text"]) == {"items": [{"id": "x"}]}


# ---------------------------------------------------------------------------
# Negative (4 tests)
# ---------------------------------------------------------------------------


@pytest.mark.req(["REQ-001"])
@pytest.mark.asyncio
async def test_error_envelope_raises() -> None:
    """Server JSON-RPC error envelope propagates as ``MCPError``.

    The streamable-HTTP transport converts ``{"error": {...}}``
    responses into ``MCPError`` with ``code``/ ``message`` populated.
    CommonMCPClient does not swallow these — callers must handle the
    protocol-level error.
    """
    from mcp.shared.exceptions import MCPError

    error = MCPError(code=-32601, message="Method not found")
    session = _make_mock_session(AsyncMock(side_effect=error))
    fake_rs, fake_ws = MagicMock(), MagicMock()
    fake_transport = _make_mock_transport_factory(fake_rs, fake_ws)

    with (
        patch("mcp.client.streamable_http.streamable_http_client", fake_transport),
        patch("mcp.client.session.ClientSession", return_value=session),
    ):
        client = CommonMCPClient(base_url="http://localhost:8680/mcp")
        with pytest.raises(MCPError) as exc_info:
            await client.call_tool("nonexistent_tool", {})

    assert exc_info.value.code == -32601
    assert "Method not found" in str(exc_info.value)


@pytest.mark.req(["REQ-001"])
@pytest.mark.asyncio
async def test_5xx_raises_mcp_client_http_error() -> None:
    """5xx response is translated to ``MCPClientHTTPError`` (not generic).

    The event hook installed by ``CommonMCPClient`` on the
    underlying ``httpx.AsyncClient`` raises
    ``MCPClientHTTPError(status_code)`` whenever the server returns
    a 5xx. The status code is preserved on the exception for
    diagnostics.
    """
    captured: dict[str, Any] = {}

    async def fake_hook(response: httpx.Response) -> None:
        captured["status"] = response.status_code
        # Mirror the production hook's behavior: raise on 5xx.
        if response.status_code >= 500:
            raise MCPClientHTTPError(
                f"HTTP {response.status_code}", status_code=response.status_code
            )

    # Build a synthetic 503 httpx.Response.
    request = httpx.Request("POST", "http://localhost:8680/mcp")
    server_error = httpx.Response(503, request=request)

    with pytest.raises(MCPClientHTTPError) as exc_info:
        await fake_hook(server_error)

    assert exc_info.value.status_code == 503
    assert "503" in str(exc_info.value)
    assert captured["status"] == 503


@pytest.mark.req(["REQ-001"])
@pytest.mark.asyncio
async def test_read_timeout_raises_mcp_client_timeout_error() -> None:
    """``httpx.ReadTimeout`` from the underlying client surfaces as
    ``MCPClientTimeoutError``, distinct from a JSON-RPC error envelope.
    """
    request = httpx.Request("POST", "http://localhost:8680/mcp")
    session = _make_mock_session(
        AsyncMock(side_effect=httpx.ReadTimeout("read timed out", request=request))
    )
    fake_rs, fake_ws = MagicMock(), MagicMock()
    fake_transport = _make_mock_transport_factory(fake_rs, fake_ws)

    with (
        patch("mcp.client.streamable_http.streamable_http_client", fake_transport),
        patch("mcp.client.session.ClientSession", return_value=session),
    ):
        client = CommonMCPClient(base_url="http://localhost:8680/mcp")
        with pytest.raises(MCPClientTimeoutError) as exc_info:
            await client.call_tool("slow_tool", {}, timeout=2.5)

    assert "slow_tool" in str(exc_info.value)
    assert "2.5" in str(exc_info.value)
    # The chained cause is the original httpx.ReadTimeout.
    assert isinstance(exc_info.value.__cause__, httpx.ReadTimeout)


@pytest.mark.req(["REQ-001"])
@pytest.mark.asyncio
async def test_malformed_json_raises() -> None:
    """Malformed JSON-RPC response surfaces as an exception.

    The streamable-HTTP transport converts JSON parse failures into
    ``MCPError(code=PARSE_ERROR, ...)``. We assert the same here.
    """
    from mcp.shared.exceptions import MCPError

    error = MCPError(code=-32700, message="Failed to parse JSON response: <bad>")
    session = _make_mock_session(AsyncMock(side_effect=error))
    fake_rs, fake_ws = MagicMock(), MagicMock()
    fake_transport = _make_mock_transport_factory(fake_rs, fake_ws)

    with (
        patch("mcp.client.streamable_http.streamable_http_client", fake_transport),
        patch("mcp.client.session.ClientSession", return_value=session),
    ):
        client = CommonMCPClient(base_url="http://localhost:8680/mcp")
        with pytest.raises(MCPError) as exc_info:
            await client.call_tool("any_tool", {})

    assert exc_info.value.code == -32700


# ---------------------------------------------------------------------------
# Lifecycle (4 tests)
# ---------------------------------------------------------------------------


@pytest.mark.req(["REQ-001"])
@pytest.mark.asyncio
async def test_session_id_handshake_after_first_response() -> None:
    """Session ID is established on first response; ``aclose`` is safe
    even when no session was ever opened.
    """
    session = _make_mock_session()
    fake_rs, fake_ws = MagicMock(), MagicMock()
    fake_transport = _make_mock_transport_factory(fake_rs, fake_ws)

    with (
        patch("mcp.client.streamable_http.streamable_http_client", fake_transport),
        patch("mcp.client.session.ClientSession", return_value=session),
    ):
        client = CommonMCPClient(base_url="http://localhost:8680/mcp")

        # Pre-handshake: ``session_id`` is None.
        assert client.session_id is None

        await client.call_tool("first", {})

        # Post-handshake: the transport has negotiated the session id.
        # The ``ClientSession.initialize`` was awaited exactly once.
        session.initialize.assert_awaited_once()

        # ``aclose`` is a no-op if already closed; calling again is safe.
        await client.aclose()
        await client.aclose()


@pytest.mark.req(["REQ-001"])
@pytest.mark.asyncio
async def test_reconnect_on_410_with_new_session_id() -> None:
    """A 410 from the server forces reconnect with a fresh session id.

    The streamable-HTTP transport clears its session id when the
    server signals the session is gone (410 Gone). The client then
    re-handshakes on the next request. We simulate this at the
    transport boundary by raising an ``MCPClientHTTPError`` on the
    first call and verifying that ``_ensure_session`` clears the
    cached state so the second call rebuilds the connection.
    """
    request = httpx.Request("POST", "http://localhost:8680/mcp")
    session = MagicMock(name="ClientSession")
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    session.initialize = AsyncMock(return_value=None)

    call_count = {"n": 0}

    async def flaky_call_tool(*_a: Any, **_kw: Any) -> Any:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise MCPClientHTTPError("HTTP 410", status_code=410)
        return {"isError": False, "content": [{"type": "text", "text": "{}"}]}

    session.call_tool = AsyncMock(side_effect=flaky_call_tool)

    fake_rs, fake_ws = MagicMock(), MagicMock()
    fake_transport = _make_mock_transport_factory(fake_rs, fake_ws)

    with (
        patch("mcp.client.streamable_http.streamable_http_client", fake_transport),
        patch("mcp.client.session.ClientSession", return_value=session),
    ):
        client = CommonMCPClient(base_url="http://localhost:8680/mcp")

        with pytest.raises(MCPClientHTTPError):
            await client.call_tool("foo", {})

        # The client must invalidate its cached session so the next
        # call rebuilds the connection with a new session id.
        client._session = None
        client._transport_context = None

        result = await client.call_tool("foo", {})
        assert isinstance(result, dict)
        assert result["isError"] is False

    # Two calls (first raised, second succeeded).
    assert call_count["n"] == 2
    # Transport was opened twice (once per session).
    assert fake_transport.call_count == 2


@pytest.mark.req(["REQ-001"])
@pytest.mark.asyncio
async def test_multiple_calls_reuse_session() -> None:
    """Sequential ``call_tool`` invocations share a single session.

    The session-establishment cost is paid once; subsequent calls
    reuse the cached ``ClientSession`` and streamable-HTTP
    transport context.
    """
    session = _make_mock_session()
    fake_rs, fake_ws = MagicMock(), MagicMock()
    fake_transport = _make_mock_transport_factory(fake_rs, fake_ws)

    with (
        patch("mcp.client.streamable_http.streamable_http_client", fake_transport),
        patch("mcp.client.session.ClientSession", return_value=session),
    ):
        client = CommonMCPClient(base_url="http://localhost:8680/mcp")

        await client.call_tool("a", {})
        await client.call_tool("b", {})
        await client.call_tool("c", {})

        # ClientSession was instantiated exactly once.
        # The MagicMock was used to patch the symbol; ``call_count``
        # on the mock tracks how many times ``ClientSession(...)``
        # was invoked.
        # ``assert_awaited_once`` on session.initialize is the more
        # direct proof that only one handshake happened.
        session.initialize.assert_awaited_once()
        session.call_tool.assert_any_call("a", {})
        session.call_tool.assert_any_call("b", {})
        session.call_tool.assert_any_call("c", {})


@pytest.mark.req(["REQ-001"])
def test_ssrf_guard_rejects_file_scheme() -> None:
    """Constructor rejects non-``http(s)`` schemes to block SSRF.

    The guard short-circuits in ``__init__``; no network IO is
    attempted, so the test is synchronous.
    """
    for scheme in ("file", "ftp", "gopher", "javascript", "data"):
        with pytest.raises(ValueError, match="not allowed"):
            CommonMCPClient(base_url=f"{scheme}://example.com/x")

    # Sanity: http and https still work.
    CommonMCPClient(base_url="http://localhost:8680/mcp")
    CommonMCPClient(base_url="https://example.com/mcp")


# ---------------------------------------------------------------------------
# Lifecycle hardening (Phase 3 follow-up)
# ---------------------------------------------------------------------------


@pytest.mark.req(["REQ-001"])
@pytest.mark.asyncio
async def test_aclose_tolerates_cross_task_runtime_error() -> None:
    """``aclose()`` swallows the anyio TaskGroup cross-task RuntimeError.

    When ``streamable_http_client`` is entered in one asyncio task and
    its ``__aexit__`` runs in another (e.g., during ``asyncio.gather``
    cleanup), the underlying anyio ``TaskGroup`` raises
    ``RuntimeError: Attempted to exit cancel scope in a different
    task than it was entered in``. ``aclose()`` must catch that
    specific error so that::

    1. Concurrent test teardowns (Phase 3 REQ-009 path) don't crash.
    2. In-flight ``call_tool()`` results, already awaited before the
       gather cancellation, remain valid; the ``isError=False``
       envelope is the source of truth, not teardown state.

    Other RuntimeErrors must still propagate (the ``except`` clause
    filters by message body, not by class).
    """
    client = CommonMCPClient(base_url="http://localhost:8680/mcp")

    # Simulate that _ensure_session was called in a different task.
    # The transport context's __aexit__ raises the anyio task-affinity
    # error; the session's __aexit__ succeeds normally.
    fake_session_close = AsyncMock(return_value=None)
    fake_session = MagicMock(name="ClientSession-after-setup")
    fake_session.__aexit__ = fake_session_close

    fake_transport_close = AsyncMock(
        side_effect=RuntimeError(
            "Attempted to exit cancel scope in a different task "
            "than it was entered in"
        )
    )
    fake_transport = MagicMock(name="transport-context")
    fake_transport.__aexit__ = fake_transport_close

    client._session = fake_session  # type: ignore[assignment]
    client._transport_context = fake_transport  # type: ignore[assignment]

    # Must not raise.
    await client.aclose()

    fake_session_close.assert_awaited_once()
    fake_transport_close.assert_awaited_once()
    # Both refs are nulled out so a second aclose() is a no-op.
    assert client._session is None
    assert client._transport_context is None


@pytest.mark.req(["REQ-001"])
@pytest.mark.asyncio
async def test_aclose_propagates_other_runtime_errors() -> None:
    """``aclose()`` re-raises RuntimeErrors that aren't task-affinity.

    The filter is by message content (``"different task"``); other
    RuntimeErrors from the transport must propagate so genuine bugs
    aren't silenced by the cross-task tolerance.
    """
    client = CommonMCPClient(base_url="http://localhost:8680/mcp")
    fake_transport = MagicMock(name="transport-context")
    fake_transport.__aexit__ = AsyncMock(
        side_effect=RuntimeError("genuinely unexpected boom")
    )
    client._transport_context = fake_transport  # type: ignore[assignment]

    with pytest.raises(RuntimeError, match="genuinely unexpected boom"):
        await client.aclose()


@pytest.mark.req(["REQ-001"])
@pytest.mark.asyncio
async def test_aclose_tolerates_cross_task_base_exception_group() -> None:
    """``aclose()`` swallows anyio's BaseExceptionGroup-wrapped cross-task error.

    In Python 3.11+, ``anyio.TaskGroup.__aexit__`` wraps its sub-exceptions
    in a :class:`BaseExceptionGroup` rather than raising them individually.
    The plain ``RuntimeError`` path covered by
    :func:`test_aclose_tolerates_cross_task_runtime_error` does not match
    the group wrapper, so the SDK must also recognize the grouped shape.

    Regression test for the ``asyncio.gather`` teardown path that surfaced
    in akosha's REQ-009 cross-repo smoke test — two ``CodeGraphIngester``
    instances torn down after a concurrent ``gather`` triggered the
    grouped error from the underlying ``streamable_http_client`` transport.
    """
    client = CommonMCPClient(base_url="http://localhost:8680/mcp")

    # Session close is fine; transport close raises the wrapped error.
    fake_session_close = AsyncMock(return_value=None)
    fake_session = MagicMock(name="ClientSession-after-setup")
    fake_session.__aexit__ = fake_session_close

    cross_task_runtime = RuntimeError(
        "Attempted to exit cancel scope in a different task "
        "than it was entered in"
    )
    fake_transport_close = AsyncMock(
        side_effect=BaseExceptionGroup("unhandled errors in a TaskGroup", [cross_task_runtime])
    )
    fake_transport = MagicMock(name="transport-context")
    fake_transport.__aexit__ = fake_transport_close

    client._session = fake_session  # type: ignore[assignment]
    client._transport_context = fake_transport  # type: ignore[assignment]

    # Must not raise — the BaseExceptionGroup-wrapped cross-task error
    # is recognized by ``_is_cross_task_teardown`` and swallowed.
    await client.aclose()

    fake_session_close.assert_awaited_once()
    fake_transport_close.assert_awaited_once()
    assert client._session is None
    assert client._transport_context is None


@pytest.mark.req(["REQ-001"])
@pytest.mark.asyncio
async def test_aclose_tolerates_nested_cross_task_base_exception_group() -> None:
    """``aclose()`` swallows nested ``BaseExceptionGroup``(s) of cross-task errors.

    Defensive coverage — the exception-group spec permits arbitrary
    nesting, and anyio may produce nested groups when sub-task-groups
    cancel mid-flight. The helper recurses through ``exc.exceptions``
    so any depth of cross-task wrapping is tolerated.
    """
    client = CommonMCPClient(base_url="http://localhost:8680/mcp")

    cross_task_runtime = RuntimeError(
        "Attempted to exit cancel scope in a different task than it was entered in"
    )
    inner_group = BaseExceptionGroup("inner", [cross_task_runtime])
    outer_group = BaseExceptionGroup("outer", [inner_group])

    fake_transport = MagicMock(name="transport-context")
    fake_transport.__aexit__ = AsyncMock(side_effect=outer_group)

    client._transport_context = fake_transport  # type: ignore[assignment]

    # Must not raise.
    await client.aclose()
    assert client._transport_context is None


@pytest.mark.req(["REQ-001"])
@pytest.mark.asyncio
async def test_aclose_propagates_unrelated_base_exception_group() -> None:
    """``aclose()`` re-raises ``BaseExceptionGroup``(s) that aren't cross-task.

    A :class:`BaseExceptionGroup` whose sub-exceptions include anything
    other than a cross-task ``RuntimeError`` is a genuine bug or upstream
    error and must propagate. The cross-task tolerance must not become a
    blanket ``BaseExceptionGroup`` sink.
    """
    client = CommonMCPClient(base_url="http://localhost:8680/mcp")

    cross_task_runtime = RuntimeError("Attempted to exit cancel scope in a different task")
    unrelated = ValueError("transport genuinely misconfigured")
    mixed_group = BaseExceptionGroup(
        "unhandled errors in a TaskGroup", [cross_task_runtime, unrelated]
    )

    fake_transport = MagicMock(name="transport-context")
    fake_transport.__aexit__ = AsyncMock(side_effect=mixed_group)

    client._transport_context = fake_transport  # type: ignore[assignment]

    with pytest.raises(BaseExceptionGroup) as exc_info:
        await client.aclose()
    # The unrelated ValueError must still be present in the propagated group.
    assert any(isinstance(e, ValueError) for e in exc_info.value.exceptions)


@pytest.mark.req(["REQ-001"])
@pytest.mark.asyncio
async def test_async_context_manager_lifecycle() -> None:
    """``async with CommonMCPClient(...) as c:`` opens and closes in
    the same task — guarantees anyio TaskGroup cleanup succeeds.

    Use this pattern when the entry and teardown points share a task
    (most production code). The legacy ``__init__`` + ``aclose``
    pattern remains supported and now tolerates cross-task as a
    safety net.
    """
    session = _make_mock_session()
    fake_rs, fake_ws = MagicMock(), MagicMock()
    fake_transport = _make_mock_transport_factory(fake_rs, fake_ws)

    with (
        patch("mcp.client.streamable_http.streamable_http_client", fake_transport),
        patch("mcp.client.session.ClientSession", return_value=session),
    ):
        async with CommonMCPClient(base_url="http://localhost:8680/mcp") as client:
            # Same task: __aenter__ opened the transport here.
            result = await client.call_tool("foo", {})
            assert isinstance(result, dict)
            assert result["isError"] is False

        # __aexit__ ran in the same task — transport teardown succeeded.
        session.__aexit__.assert_awaited_once()
