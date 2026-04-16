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


class _SpanContextManager:
    def __init__(self, span: _Span) -> None:
        self._span = span

    def __enter__(self) -> _Span:
        return self._span

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001,ANN201,ANN202
        return False


class _Tracer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.span = _Span()

    def start_as_current_span(
        self, name: str, attributes: dict[str, object] | None = None
    ) -> _SpanContextManager:
        self.calls.append((name, attributes or {}))
        self.span.attributes.update(attributes or {})
        return _SpanContextManager(self.span)


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


async def _success_result() -> dict[str, object]:
    return {"status": "ok", "count": 1}


async def _raise_runtime_error(_context: Any) -> None:
    raise RuntimeError("boom")
