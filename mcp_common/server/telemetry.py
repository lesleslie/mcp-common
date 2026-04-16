"""OpenTelemetry helpers for FastMCP-based MCP servers.

FastMCP exposes middleware hooks but does not ship a native OTEL exporter.
This module provides a reusable middleware implementation that emits spans for
MCP requests so servers can share one tracing pattern across repositories.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    trace = None  # type: ignore[assignment]
    Status = None  # type: ignore[assignment]
    StatusCode = None  # type: ignore[assignment]
    _OTEL_AVAILABLE = False

logger = logging.getLogger(__name__)

type CallNext = Callable[[MiddlewareContext[Any]], Awaitable[Any]]


class FastMCPOpenTelemetryMiddleware(Middleware):
    """Emit OpenTelemetry spans for MCP messages handled by FastMCP."""

    def __init__(
        self,
        service_name: str,
        *,
        environment: str = "production",
        service_namespace: str = "mcp-ecosystem",
    ) -> None:
        self.service_name = service_name
        self.environment = environment
        self.service_namespace = service_namespace
        self._tracer = (
            trace.get_tracer(f"{__name__}.{service_name}") if _OTEL_AVAILABLE else None
        )

    async def on_message(
        self, context: MiddlewareContext[Any], call_next: CallNext
    ) -> Any:
        """Wrap every FastMCP request in a span."""
        if self._tracer is None:
            return await call_next(context)

        span_name = self._span_name(context)
        attributes = self._span_attributes(context)

        with self._tracer.start_as_current_span(
            span_name, attributes=attributes
        ) as span:
            try:
                result = await call_next(context)
                self._annotate_result(span, context, result)
                return result
            except Exception as exc:
                if hasattr(span, "record_exception"):
                    span.record_exception(exc)
                if (
                    Status is not None
                    and StatusCode is not None
                    and hasattr(span, "set_status")
                ):
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise

    def _span_name(self, context: MiddlewareContext[Any]) -> str:
        method = context.method or "message"
        component_name = self._component_name(context)
        normalized_method = method.replace("/", ".")

        if component_name:
            return f"mcp.{normalized_method}.{component_name}"
        return f"mcp.{normalized_method}"

    def _span_attributes(self, context: MiddlewareContext[Any]) -> dict[str, Any]:
        attributes: dict[str, Any] = {
            "rpc.system": "mcp",
            "rpc.method": context.method or "unknown",
            "service.name": self.service_name,
            "service.namespace": self.service_namespace,
            "service.environment": self.environment,
            "mcp.message.type": context.type,
        }

        component_name = self._component_name(context)
        if component_name:
            attributes["mcp.component.name"] = component_name

        if context.method == "tools/call":
            attributes["mcp.tool.name"] = component_name or "unknown"
        elif context.method == "resources/read":
            resource_uri = getattr(context.message, "uri", None)
            if resource_uri is not None:
                attributes["mcp.resource.uri"] = str(resource_uri)
        elif context.method == "prompts/get":
            attributes["mcp.prompt.name"] = component_name or "unknown"

        return attributes

    def _annotate_result(
        self, span: Any, context: MiddlewareContext[Any], result: Any
    ) -> None:
        if not hasattr(span, "set_attribute"):
            return

        if isinstance(result, dict):
            status = result.get("status")
            if isinstance(status, str):
                span.set_attribute("mcp.result.status", status)

            error = result.get("error")
            if error is not None:
                span.set_attribute("mcp.result.error", str(error))

        if context.method == "tools/call" and not isinstance(result, dict):
            span.set_attribute("mcp.result.type", type(result).__name__)

    def _component_name(self, context: MiddlewareContext[Any]) -> str | None:
        message = context.message
        name = getattr(message, "name", None)
        if isinstance(name, str) and name:
            return name

        uri = getattr(message, "uri", None)
        if isinstance(uri, str) and uri:
            return uri

        return None


__all__ = ["FastMCPOpenTelemetryMiddleware"]
