from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from mcp_common.server.telemetry import FastMCPOpenTelemetryMiddleware


class _Span:
    def __init__(self) -> None:
        self.attributes: dict[str, object] = {}
        self.exceptions: list[BaseException] = []
        self.status: object | None = None

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def record_exception(self, exc: BaseException) -> None:
        self.exceptions.append(exc)

    def set_status(self, status: object) -> None:
        self.status = status


class _BareSpan:
    """Span stub without optional tracing methods."""

    pass


class _SpanContextManager:
    def __init__(self, span: object) -> None:
        self._span = span

    def __enter__(self) -> object:
        return self._span

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001,ANN201,ANN202
        return False


class _Tracer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.span: object = _Span()

    def start_as_current_span(
        self, name: str, attributes: dict[str, object] | None = None
    ) -> _SpanContextManager:
        self.calls.append((name, attributes or {}))
        if hasattr(self.span, "attributes"):
            self.span.attributes.update(attributes or {})
        return _SpanContextManager(self.span)


class _StatusCode:
    ERROR = "error"


class _Status:
    def __init__(self, code: object, description: str) -> None:
        self.code = code
        self.description = description


@pytest.mark.asyncio
async def test_fastmcp_middleware_emits_span(monkeypatch: pytest.MonkeyPatch) -> None:
    tracer = _Tracer()
    monkeypatch.setattr(
        "mcp_common.server.telemetry.trace.get_tracer",
        lambda _name: tracer,
    )

    middleware = FastMCPOpenTelemetryMiddleware(
        service_name="session-buddy",
        environment="production",
    )
    context = SimpleNamespace(
        method="tools/call",
        type="request",
        message=SimpleNamespace(name="track_session_start"),
    )

    result = await middleware.on_message(context, lambda _ctx: _success_result())

    assert result == {"status": "ok", "count": 1}
    assert tracer.calls[0][0] == "mcp.tools.call.track_session_start"
    assert tracer.calls[0][1]["service.name"] == "session-buddy"
    assert tracer.span.attributes["mcp.tool.name"] == "track_session_start"
    assert tracer.span.attributes["mcp.result.status"] == "ok"


@pytest.mark.asyncio
async def test_fastmcp_middleware_records_error(monkeypatch: pytest.MonkeyPatch) -> None:
    tracer = _Tracer()
    monkeypatch.setattr(
        "mcp_common.server.telemetry.trace.get_tracer",
        lambda _name: tracer,
    )

    middleware = FastMCPOpenTelemetryMiddleware(service_name="session-buddy")
    context = SimpleNamespace(
        method="tools/call",
        type="request",
        message=SimpleNamespace(name="broken"),
    )

    with pytest.raises(RuntimeError, match="boom"):
        await middleware.on_message(context, _raise_runtime_error)

    assert tracer.calls[0][0] == "mcp.tools.call.broken"
    assert tracer.span.exceptions


@pytest.mark.asyncio
async def test_fastmcp_middleware_bypasses_when_tracing_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("mcp_common.server.telemetry._OTEL_AVAILABLE", False)

    middleware = FastMCPOpenTelemetryMiddleware(service_name="session-buddy")
    context = SimpleNamespace(method=None, type="event", message=SimpleNamespace())

    called = False

    async def call_next(_ctx: object) -> dict[str, object]:
        nonlocal called
        called = True
        return {"status": "ok"}

    result = await middleware.on_message(context, call_next)

    assert called is True
    assert result == {"status": "ok"}


@pytest.mark.asyncio
async def test_fastmcp_middleware_resource_and_prompt_spans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracer = _Tracer()
    monkeypatch.setattr(
        "mcp_common.server.telemetry.trace.get_tracer",
        lambda _name: tracer,
    )

    middleware = FastMCPOpenTelemetryMiddleware(
        service_name="session-buddy",
        environment="staging",
    )

    resource_context = SimpleNamespace(
        method="resources/read",
        type="request",
        message=SimpleNamespace(uri="resource://docs/guide"),
    )

    prompt_context = SimpleNamespace(
        method="prompts/get",
        type="request",
        message=SimpleNamespace(name="welcome"),
    )

    resource_result = await middleware.on_message(
        resource_context, lambda _ctx: _resource_result()
    )
    prompt_result = await middleware.on_message(
        prompt_context, lambda _ctx: _prompt_result()
    )

    assert resource_result == {"status": "ok", "resource": True}
    assert prompt_result == {"status": "ok", "prompt": True}
    assert tracer.calls[0][0] == "mcp.resources.read.resource://docs/guide"
    assert tracer.span.attributes["mcp.resource.uri"] == "resource://docs/guide"
    assert tracer.span.attributes["mcp.prompt.name"] == "welcome"


@pytest.mark.asyncio
async def test_fastmcp_middleware_sets_error_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracer = _Tracer()
    monkeypatch.setattr(
        "mcp_common.server.telemetry.trace.get_tracer",
        lambda _name: tracer,
    )
    monkeypatch.setattr("mcp_common.server.telemetry.Status", _Status)
    monkeypatch.setattr("mcp_common.server.telemetry.StatusCode", _StatusCode)

    middleware = FastMCPOpenTelemetryMiddleware(service_name="session-buddy")
    context = SimpleNamespace(
        method="tools/call",
        type="request",
        message=SimpleNamespace(name="broken"),
    )

    with pytest.raises(ValueError, match="boom"):
        await middleware.on_message(context, _raise_value_error)

    assert tracer.span.status is not None
    assert tracer.span.status.code == _StatusCode.ERROR
    assert tracer.span.status.description == "boom"
    assert tracer.span.exceptions


@pytest.mark.asyncio
async def test_fastmcp_middleware_handles_span_without_optional_methods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracer = _Tracer()
    tracer.span = _BareSpan()
    monkeypatch.setattr(
        "mcp_common.server.telemetry.trace.get_tracer",
        lambda _name: tracer,
    )

    middleware = FastMCPOpenTelemetryMiddleware(
        service_name="session-buddy",
        environment="dev",
    )
    context = SimpleNamespace(
        method="resources/read",
        type="request",
        message=SimpleNamespace(),
    )

    async def call_next(_ctx: object) -> dict[str, object]:
        return {"error": "bad", "status": 123, "payload": True}

    result = await middleware.on_message(
        context,
        call_next,
    )

    assert result["payload"] is True
    assert tracer.calls[0][0] == "mcp.resources.read"
    assert tracer.calls[0][1]["service.environment"] == "dev"
    assert tracer.calls[0][1]["rpc.method"] == "resources/read"


@pytest.mark.asyncio
async def test_fastmcp_middleware_uses_uri_when_name_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracer = _Tracer()
    monkeypatch.setattr(
        "mcp_common.server.telemetry.trace.get_tracer",
        lambda _name: tracer,
    )

    middleware = FastMCPOpenTelemetryMiddleware(service_name="session-buddy")
    context = SimpleNamespace(
        method="prompts/get",
        type="request",
        message=SimpleNamespace(name="", uri="prompt://welcome"),
    )

    async def call_next(_ctx: object) -> dict[str, str]:
        return {"status": "ok"}

    result = await middleware.on_message(
        context,
        call_next,
    )

    assert result == {"status": "ok"}
    assert tracer.calls[0][0] == "mcp.prompts.get.prompt://welcome"
    assert tracer.span.attributes["mcp.component.name"] == "prompt://welcome"
    assert tracer.span.attributes["mcp.prompt.name"] == "prompt://welcome"


@pytest.mark.asyncio
async def test_fastmcp_middleware_tool_result_type_for_non_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracer = _Tracer()
    monkeypatch.setattr(
        "mcp_common.server.telemetry.trace.get_tracer",
        lambda _name: tracer,
    )

    middleware = FastMCPOpenTelemetryMiddleware(service_name="session-buddy")
    context = SimpleNamespace(
        method="tools/call",
        type="request",
        message=SimpleNamespace(name="count_items"),
    )

    async def call_next(_ctx: object) -> list[str]:
        return ["a", "b"]

    result = await middleware.on_message(context, call_next)

    assert result == ["a", "b"]
    assert tracer.span.attributes["mcp.result.type"] == "list"


def test_fastmcp_middleware_span_name_without_component() -> None:
    middleware = FastMCPOpenTelemetryMiddleware(service_name="session-buddy")
    context = SimpleNamespace(method=None, type="event", message=SimpleNamespace())

    assert middleware._span_name(context) == "mcp.message"
    assert middleware._component_name(context) is None


def test_fastmcp_middleware_span_attributes_without_resource_uri() -> None:
    middleware = FastMCPOpenTelemetryMiddleware(service_name="session-buddy")
    context = SimpleNamespace(
        method="resources/read",
        type="request",
        message=SimpleNamespace(),
    )

    attributes = middleware._span_attributes(context)

    assert "mcp.resource.uri" not in attributes
    assert "mcp.component.name" not in attributes


def test_fastmcp_middleware_annotate_result_variants() -> None:
    middleware = FastMCPOpenTelemetryMiddleware(service_name="session-buddy")
    context = SimpleNamespace(
        method="tools/call",
        type="request",
        message=SimpleNamespace(name="tool_name"),
    )

    bare_span = _BareSpan()
    middleware._annotate_result(bare_span, context, {"status": "ok"})

    span = _Span()
    middleware._annotate_result(
        span,
        context,
        {"status": 123, "error": "failed", "payload": True},
    )
    middleware._annotate_result(span, context, ["a", "b"])

    assert span.attributes["mcp.result.error"] == "failed"
    assert span.attributes["mcp.result.type"] == "list"


async def _success_result() -> dict[str, object]:
    return {"status": "ok", "count": 1}


async def _raise_runtime_error(_context: Any) -> None:
    raise RuntimeError("boom")


async def _resource_result() -> dict[str, object]:
    return {"status": "ok", "resource": True}


async def _prompt_result() -> dict[str, object]:
    return {"status": "ok", "prompt": True}


async def _raise_value_error(_context: Any) -> None:
    raise ValueError("boom")
