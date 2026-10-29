"""Producer-side OpenTelemetry wiring for the Bodai span substrate.

The receiver in akosha can only report on the producers it hears from.
Until this module existed, it heard from nobody: every Bodai MCP server
started through the shared launcher but none of them installed a tracer
provider, so the spans they created never left the process. The
receiver's substrate held nothing but the receiver's own canary rows,
and its heartbeat watcher -- which asks "did every service we expect to
be talking still talk?" -- correctly reported every rostered service as
absent, forever.

Three decisions shape this module.

**One implementation, not one per service.** Every Bodai MCP server
already starts through :func:`mcp_common.server.launcher.launch`, and the
``component_name`` it passes there is the same string the receiver's
heartbeat roster watches (``mahavishnu``, ``akosha``, ``session-buddy``,
``oneiric``, ``crackerjack``). So the launcher is the seam, and
``component_name`` is the service identity -- no per-service wiring, and
no second naming scheme to keep in step with the roster.

**Opt-in, never accidental.** Producer telemetry is installed only when
the process is pointed at a collector (``OTEL_EXPORTER_OTLP_ENDPOINT`` or
``OTEL_EXPORTER_OTLP_TRACES_ENDPOINT``). The launcher is shared with MCP
servers outside the Bodai core set; those keep the behaviour they had --
no provider, and no request-span middleware either, because the launcher
attaches that only when spans can actually be exported. The fleet's
launchd plists set the variable explicitly.

**Never override an existing provider.** The OTel SDK refuses to replace
an installed provider, and this module honours that: if something already
installed one, it is left alone and this module reports that spans are
exported without claiming ownership. Without the check the first
component to boot would win the race for the global provider and the
others would silently keep the default no-op tracer. The check runs
BEFORE the opt-in gate, because "can this process export spans" is the
real question: a component that installed its own provider exports
whether or not the endpoint is in the environment.

The liveness emitter exists because request-driven spans cannot serve as
a heartbeat. An MCP server emits a span when somebody calls a tool, so an
idle fleet produces nothing and a two-minute absence detector fires on a
perfectly healthy service. The emitter puts a marker span on the wire on
a fixed interval, so silence means the *telemetry pipeline* is broken --
which is the thing the watcher is actually for. It mirrors the receiver's
canary one layer up: the canary proves the write path, the liveness span
proves the export path.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from opentelemetry.sdk.trace import TracerProvider

__all__ = [
    "DEFAULT_LIVENESS_INTERVAL_SECONDS",
    "DEFAULT_SERVICE_NAMESPACE",
    "LIVENESS_SPAN_NAME",
    "ProducerTracingResult",
    "configure_producer_tracing",
    "producer_telemetry_enabled",
    "run_liveness_emitter",
]


#: Span name for the periodic producer liveness marker.
#:
#: The leading underscore matches the receiver's own canary convention
#: (``_receiver_canary`` / ``_canary_substrate_write``): a reader scanning
#: the substrate can tell synthetic markers from real traces by name, and
#: no filter can accidentally mistake one for traffic.
LIVENESS_SPAN_NAME = "_service_liveness"

#: How often the liveness emitter emits.
#:
#: The receiver's heartbeat watcher uses a 60s window, so a 30s interval
#: guarantees every window contains at least one sample even if a cycle
#: is missed. Halving the window again would only buy rows.
DEFAULT_LIVENESS_INTERVAL_SECONDS: float = 30.0

#: The namespace every producer reports under.
#:
#: The receiver's resource validator allows a fixed set of NAMESPACES
#: (``bodai``, ``cli-tools``). A per-service namespace would mean every
#: service needed its own carve-out -- the same sprawl the namespace
#: exists to prevent -- so every core service reports under ``bodai``.
DEFAULT_SERVICE_NAMESPACE: str = "bodai"

#: Environment variables that point a process at an OTLP collector.
_ENDPOINT_ENV: str = "OTEL_EXPORTER_OTLP_ENDPOINT"
_TRACES_ENDPOINT_ENV: str = "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"
_PROTOCOL_ENV: str = "OTEL_EXPORTER_OTLP_PROTOCOL"

#: The path the OTLP/HTTP exporter appends to a base endpoint. The
#: signal-specific environment variable is used verbatim by the SDK; the
#: generic one gets this path appended. A caller-supplied endpoint is
#: normalised to the same shape so the two paths cannot disagree.
_TRACES_PATH: str = "/v1/traces"

_DEFAULT_PROTOCOL: str = "http/protobuf"


@dataclass(frozen=True, slots=True)
class ProducerTracingResult:
    """What the tracing call did, and who owns the provider.

    Two questions, two answers, because they are not the same question.

    ``export_spans`` says whether this process will ship spans to the
    collector. That is true when a provider is installed, whoever
    installed it -- the launcher needs this to decide whether to attach
    the request-span middleware and start the liveness emitter.

    ``provider`` says whether the provider is OURS: the one this call
    installed. That is what decides who may shut it down. A caller that
    holds a provider it did not install must not close it -- closing
    someone else's exporter is how a process ends up flushing another
    component's spans into the void at exit.

    Collapsing the two into a single ``bool`` is what made ownership
    unknowable. ``True`` used to mean "we installed it" in one branch
    and "someone else installed it and we declined" in another, so a
    caller could not tell "I may close this" from "I must not".
    """

    provider: TracerProvider | None
    export_spans: bool


def producer_telemetry_enabled() -> bool:
    """Whether this process is pointed at an OTLP collector.

    Both the generic and the signal-specific endpoint variables count.
    The signal-specific one wins in the OTel SDK, so honouring either
    here keeps this gate consistent with what the exporter will do.
    """
    return bool(os.getenv(_TRACES_ENDPOINT_ENV) or os.getenv(_ENDPOINT_ENV))


def configure_producer_tracing(
    service_name: str,
    *,
    service_namespace: str = DEFAULT_SERVICE_NAMESPACE,
    environment: str = "production",
    endpoint: str | None = None,
    protocol: str | None = None,
    resource_attributes: Mapping[str, str] | None = None,
) -> ProducerTracingResult:
    """Install a tracer provider that exports spans to the substrate.

    Args:
        service_name: The service's identity, as the receiver's roster
            spells it. This is written to the provider's ``Resource``, so
            it is the value the receiver reads as ``service_name``.
        service_namespace: The namespace every core service reports
            under. It is load-bearing, not decoration: the receiver
            quarantines a span whose namespace is not on its allowlist.
        environment: The deployment environment, recorded as
            ``deployment.environment``.
        endpoint: Override for the collector endpoint. ``None`` (the
            default) lets the OTel SDK resolve the endpoint from the
            environment, which is what keeps an operator's plist the one
            place the destination is configured.
        protocol: Override for the export protocol. ``None`` resolves
            ``OTEL_EXPORTER_OTLP_PROTOCOL``, then falls back to
            ``http/protobuf``.
        resource_attributes: Extra resource attributes for the provider's
            ``Resource`` -- the ``telemetry.source`` family, for example.
            They are applied FIRST, so the canonical identity below
            always wins: a caller cannot accidentally report a span under
            a different service name or namespace than the ones it
            passed to this function.

    Returns:
        A :class:`ProducerTracingResult`. Its ``provider`` is the
        provider THIS call installed, or ``None`` when it did not install
        one -- either because nothing was configured, or because a
        provider was already installed and this call declined to replace
        it. Its ``export_spans`` says whether spans will reach the
        collector at all, which is true whenever a provider exists,
        whoever installed it.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.trace import ProxyTracerProvider
    except ImportError:  # pragma: no cover - optional runtime dependency
        logger.debug(
            "mcp.producer_telemetry.opentelemetry_missing service=%s — the "
            "OpenTelemetry API is not installed, so no spans can be exported",
            service_name,
        )
        return ProducerTracingResult(None, False)

    existing = trace.get_tracer_provider()
    if not isinstance(existing, ProxyTracerProvider):
        # Something already installed a real provider. The SDK refuses to
        # replace it, and so does this function: whichever component got
        # there first owns the export path, and two components fighting
        # over the global provider would leave one of them exporting to
        # the wrong place.
        #
        # This is checked BEFORE the opt-in gate below, because "can this
        # process export spans" is the real question. A component that
        # installed its own provider exports whether or not the endpoint
        # is in the environment.
        #
        # The provider is NOT returned: it belongs to whoever installed
        # it, and this caller must not close it.
        logger.info(
            "mcp.producer_telemetry.provider_already_installed service=%s — "
            "leaving the existing tracer provider in place",
            service_name,
        )
        return ProducerTracingResult(None, True)

    if endpoint is None and not producer_telemetry_enabled():
        logger.debug(
            "mcp.producer_telemetry.not_configured service=%s — no OTLP endpoint "
            "in the environment, so no provider is installed",
            service_name,
        )
        return ProducerTracingResult(None, False)

    try:
        provider = _build_provider(
            service_name=service_name,
            service_namespace=service_namespace,
            environment=environment,
            endpoint=endpoint,
            protocol=protocol,
            resource_attributes=resource_attributes,
        )
    except Exception as exc:  # noqa: BLE001 — telemetry must never take the server down
        # A missing exporter package or a malformed endpoint must not take
        # the server down with it. Telemetry is not worth a boot failure.
        logger.warning(
            "mcp.producer_telemetry.configure_failed service=%s error=%s",
            service_name,
            exc,
        )
        return ProducerTracingResult(None, False)

    trace.set_tracer_provider(provider)
    logger.info(
        "mcp.producer_telemetry.configured service=%s namespace=%s endpoint=%s",
        service_name,
        service_namespace,
        _describe_endpoint(endpoint),
    )
    return ProducerTracingResult(provider, True)


def _build_provider(
    *,
    service_name: str,
    service_namespace: str,
    environment: str,
    endpoint: str | None,
    protocol: str | None,
    resource_attributes: Mapping[str, str] | None = None,
) -> Any:
    """Build the ``TracerProvider`` this module installs."""
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resolved_protocol = (
        protocol or os.getenv(_PROTOCOL_ENV) or _DEFAULT_PROTOCOL
    ).lower()

    # The caller's extra attributes go in FIRST so the canonical identity
    # always wins. The receiver reads ``service.namespace`` from the
    # resource and quarantines a span whose namespace is not on its
    # allowlist, so an extra attribute that shadowed the namespace would
    # silently quarantine every span the service produced.
    attributes: dict[str, str] = dict(resource_attributes or {})
    attributes.update(
        {
            "service.name": service_name,
            "service.namespace": service_namespace,
            "deployment.environment": environment,
        }
    )
    resource = Resource.create(attributes)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(_build_exporter(resolved_protocol, endpoint))
    )
    return provider


def _build_exporter(protocol: str, endpoint: str | None) -> Any:
    """Build the OTLP span exporter for ``protocol``.

    The exporter is handed ``endpoint=None`` whenever the caller did not
    supply one, so the OTel SDK resolves it from the environment. That
    resolution is not quite the SDK's default behaviour for an explicit
    endpoint: the signal-specific variable is used verbatim, while the
    generic one has the signal path appended. Letting the SDK do it means
    this module cannot disagree with the exporter about which URL the
    spans are going to.
    """
    if protocol.startswith("grpc"):
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        return OTLPSpanExporter(endpoint=endpoint) if endpoint else OTLPSpanExporter()

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    if endpoint is None:
        return OTLPSpanExporter()
    return OTLPSpanExporter(endpoint=_normalize_http_endpoint(endpoint))


def _normalize_http_endpoint(endpoint: str) -> str:
    """Give an explicit OTLP/HTTP endpoint its signal path.

    The exporter treats an explicit endpoint as the complete URL, so a
    base URL like ``http://127.0.0.1:4318`` would be posted to as-is and
    the receiver would answer 404. Appending the path when it is missing
    makes an explicit endpoint mean the same thing as the environment
    variable it mirrors.
    """
    if endpoint.rstrip("/").endswith(_TRACES_PATH):
        return endpoint
    return f"{endpoint.rstrip('/')}{_TRACES_PATH}"


def _describe_endpoint(endpoint: str | None) -> str:
    """A log-safe description of where spans are going."""
    if endpoint is not None:
        return endpoint
    return os.getenv(_TRACES_ENDPOINT_ENV) or os.getenv(_ENDPOINT_ENV) or "(unset)"


async def run_liveness_emitter(
    service_name: str,
    stop_event: asyncio.Event,
    *,
    interval_seconds: float = DEFAULT_LIVENESS_INTERVAL_SECONDS,
    emit: Callable[[], None] | None = None,
) -> None:
    """Emit a liveness span on every interval until ``stop_event`` is set.

    The first span is emitted immediately rather than after one interval.
    A liveness signal that starts one interval late looks identical to a
    producer that came up late, which is exactly the ambiguity the
    emitter exists to remove.

    Args:
        service_name: The service's identity, used in the span's
            attributes as well as on the provider's resource.
        stop_event: The event that ends the loop. The wait is a
            cancellable ``wait_for``, so a cancelled task unwinds the
            same way the rest of the lifespan's tasks do.
        interval_seconds: Seconds between emissions.
        emit: Test seam. When given, it replaces the span emission and
            the loop's only job becomes calling it on the interval.
    """
    from opentelemetry import trace

    tracer = trace.get_tracer(f"{__name__}.{service_name}")

    def _emit_once() -> None:
        if emit is not None:
            emit()
            return
        with tracer.start_as_current_span(
            LIVENESS_SPAN_NAME,
            attributes={
                "service.name": service_name,
                "service.namespace": DEFAULT_SERVICE_NAMESPACE,
                "telemetry.source.type": "producer_liveness",
            },
        ):
            pass

    while not stop_event.is_set():
        try:
            _emit_once()
        except Exception:
            # A liveness emitter that dies stops reporting the very thing
            # it exists to report, and a stopped emitter looks exactly
            # like a stopped producer. Keep going.
            logger.exception(
                "mcp.producer_telemetry.emit_failed service=%s", service_name
            )

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            return
        except TimeoutError:
            continue
