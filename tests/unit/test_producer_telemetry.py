"""Tests for ``mcp_common.server.producer_telemetry``.

The module exists because the receiver's heartbeat roster had no
producers behind it: every rostered service started through the shared
launcher but none of them installed a tracer provider, so the spans they
created never left the process and the watcher reported every rostered
service as absent, forever.

The tests below pin the four properties that make the fix correct:

* **Opt-in.** No collector in the environment means no provider, so MCP
  servers outside the Bodai core set are unaffected.
* **Correct identity.** The installed provider's resource carries the
  service name the roster watches and a namespace the receiver allows.
* **No takeover.** An already-installed provider is left alone.
* **A liveness signal.** The emitter fires immediately, keeps firing, and
  stops when told to.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from mcp_common.server.producer_telemetry import (
    DEFAULT_SERVICE_NAMESPACE,
    LIVENESS_SPAN_NAME,
    _normalize_http_endpoint,
    configure_producer_tracing,
    producer_telemetry_enabled,
    run_liveness_emitter,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ENDPOINT_ENV = "OTEL_EXPORTER_OTLP_ENDPOINT"
_TRACES_ENDPOINT_ENV = "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"
_PROTOCOL_ENV = "OTEL_EXPORTER_OTLP_PROTOCOL"


@pytest.fixture
def clean_otel_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every OTLP variable the module reads."""
    for name in (_ENDPOINT_ENV, _TRACES_ENDPOINT_ENV, _PROTOCOL_ENV):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def reset_tracer_provider() -> Any:
    """Restore the global tracer provider after the test.

    The OTel SDK installs a global provider exactly once per process and
    refuses to replace it, so a test that installs one would leak it into
    every test after it. The module's own globals are reset here for the
    same reason.
    """
    from opentelemetry import trace
    from opentelemetry.util._once import Once

    original_provider = trace._TRACER_PROVIDER
    original_once = trace._TRACER_PROVIDER_SET_ONCE
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE = Once()
    try:
        yield
    finally:
        trace._TRACER_PROVIDER = original_provider
        trace._TRACER_PROVIDER_SET_ONCE = original_once


@pytest.fixture
def otel_sdk() -> None:
    """Skip when the OpenTelemetry SDK is not installed.

    mcp-common does not depend on the SDK: it ships the *API* surface and
    leaves the SDK to the consumer, the same way
    ``mcp_common/server/telemetry.py`` leaves ``opentelemetry-api`` to
    whoever installs the library. Every consumer that reports spans
    brings the SDK; a developer running the suite without it gets the
    SDK-dependent tests skipped rather than failed.
    """
    pytest.importorskip(
        "opentelemetry.sdk.trace",
        reason="the OpenTelemetry SDK is a consumer-provided dependency",
    )


# ---------------------------------------------------------------------------
# The opt-in gate
# ---------------------------------------------------------------------------


class TestProducerTelemetryEnabled:
    """The gate that keeps non-fleet MCP servers unchanged."""

    def test_off_without_any_endpoint(self, clean_otel_env: None) -> None:
        assert producer_telemetry_enabled() is False

    def test_on_with_the_generic_endpoint(
        self, clean_otel_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(_ENDPOINT_ENV, "http://127.0.0.1:4318")
        assert producer_telemetry_enabled() is True

    def test_on_with_the_signal_specific_endpoint(
        self, clean_otel_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(_TRACES_ENDPOINT_ENV, "http://127.0.0.1:4318/v1/traces")
        assert producer_telemetry_enabled() is True


# ---------------------------------------------------------------------------
# configure_producer_tracing()
# ---------------------------------------------------------------------------


class TestConfigureProducerTracing:
    """Provider installation."""

    def test_nothing_is_installed_without_a_collector(
        self, clean_otel_env: None, reset_tracer_provider: Any
    ) -> None:
        from opentelemetry import trace
        from opentelemetry.trace import ProxyTracerProvider

        assert configure_producer_tracing("mahavishnu") is False
        assert isinstance(trace.get_tracer_provider(), ProxyTracerProvider)

    def test_the_provider_carries_the_roster_identity(
        self,
        clean_otel_env: None,
        reset_tracer_provider: Any,
        otel_sdk: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from opentelemetry import trace

        monkeypatch.setenv(_ENDPOINT_ENV, "http://127.0.0.1:4318")

        assert configure_producer_tracing("mahavishnu") is True

        resource = trace.get_tracer_provider().resource
        assert resource.attributes["service.name"] == "mahavishnu"
        assert resource.attributes["service.namespace"] == DEFAULT_SERVICE_NAMESPACE

    def test_an_existing_provider_is_not_replaced(
        self,
        clean_otel_env: None,
        reset_tracer_provider: Any,
        otel_sdk: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider

        monkeypatch.setenv(_ENDPOINT_ENV, "http://127.0.0.1:4318")

        incumbent = TracerProvider()
        trace.set_tracer_provider(incumbent)

        assert configure_producer_tracing("oneiric") is True
        assert trace.get_tracer_provider() is incumbent

    def test_an_explicit_endpoint_overrides_the_environment(
        self,
        clean_otel_env: None,
        reset_tracer_provider: Any,
        otel_sdk: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from opentelemetry import trace

        monkeypatch.setenv(_ENDPOINT_ENV, "http://127.0.0.1:4318")

        assert (
            configure_producer_tracing("akosha", endpoint="http://127.0.0.1:9999")
            is True
        )
        assert (
            trace.get_tracer_provider().resource.attributes["service.name"] == "akosha"
        )


class TestEndpointNormalization:
    """An explicit OTLP/HTTP endpoint means the same thing as the env var."""

    @pytest.mark.parametrize(
        ("given", "expected"),
        [
            ("http://127.0.0.1:4318", "http://127.0.0.1:4318/v1/traces"),
            ("http://127.0.0.1:4318/", "http://127.0.0.1:4318/v1/traces"),
            (
                "http://127.0.0.1:4318/v1/traces",
                "http://127.0.0.1:4318/v1/traces",
            ),
        ],
    )
    def test_the_signal_path_is_present_exactly_once(
        self, given: str, expected: str
    ) -> None:
        assert _normalize_http_endpoint(given) == expected


# ---------------------------------------------------------------------------
# run_liveness_emitter()
# ---------------------------------------------------------------------------


class TestLivenessEmitter:
    """The signal that makes silence mean something."""

    async def test_the_first_span_is_emitted_immediately(self) -> None:
        stop_event = asyncio.Event()
        emitted: list[int] = []

        task = asyncio.create_task(
            run_liveness_emitter(
                "akosha",
                stop_event,
                interval_seconds=3600,
                emit=lambda: emitted.append(1),
            )
        )
        # The emitter fires before its first wait, so one poll is enough.
        for _ in range(50):
            if emitted:
                break
            await asyncio.sleep(0.01)

        stop_event.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        assert emitted, (
            "the liveness emitter must not wait an interval before its first span"
        )

    async def test_it_stops_when_the_stop_event_is_set(self) -> None:
        stop_event = asyncio.Event()
        emitted: list[int] = []

        task = asyncio.create_task(
            run_liveness_emitter(
                "oneiric",
                stop_event,
                interval_seconds=0.01,
                emit=lambda: emitted.append(1),
            )
        )
        await asyncio.sleep(0.05)
        stop_event.set()
        await asyncio.wait_for(task, timeout=2.0)

        assert emitted

    async def test_a_failing_emit_does_not_kill_the_loop(self) -> None:
        stop_event = asyncio.Event()
        attempts: list[int] = []

        def _explode() -> None:
            attempts.append(1)
            raise RuntimeError("exporter is down")

        task = asyncio.create_task(
            run_liveness_emitter(
                "crackerjack",
                stop_event,
                interval_seconds=0.01,
                emit=_explode,
            )
        )
        await asyncio.sleep(0.05)
        stop_event.set()
        await asyncio.wait_for(task, timeout=2.0)

        assert len(attempts) > 1, "the emitter must survive a failed emission"


# ---------------------------------------------------------------------------
# The launcher's wiring
# ---------------------------------------------------------------------------


class TestLauncherMiddlewareAttachment:
    """The launcher gives every component a request-span middleware."""

    def test_it_attaches_one_when_the_server_has_none(self) -> None:
        from mcp_common.server.launcher import _attach_request_span_middleware
        from mcp_common.server.telemetry import FastMCPOpenTelemetryMiddleware

        class _Server:
            def __init__(self) -> None:
                self.middleware: list[Any] = []

            def add_middleware(self, middleware: Any) -> None:
                self.middleware.append(middleware)

        server = _Server()
        assert _attach_request_span_middleware(server, "mahavishnu") is True
        assert len(server.middleware) == 1
        assert isinstance(server.middleware[0], FastMCPOpenTelemetryMiddleware)
        assert server.middleware[0].service_name == "mahavishnu"

    def test_it_does_not_attach_a_second_one(self) -> None:
        from mcp_common.server.launcher import _attach_request_span_middleware

        class _Server:
            def __init__(self) -> None:
                self.middleware: list[Any] = []

            def add_middleware(self, middleware: Any) -> None:
                self.middleware.append(middleware)

        server = _Server()
        _attach_request_span_middleware(server, "mahavishnu")
        assert _attach_request_span_middleware(server, "mahavishnu") is False
        assert len(server.middleware) == 1

    def test_a_server_without_add_middleware_is_skipped(self) -> None:
        from mcp_common.server.launcher import _attach_request_span_middleware

        assert _attach_request_span_middleware(object(), "akosha") is False


def test_the_liveness_span_name_is_distinguishable() -> None:
    """Synthetic markers carry an underscore prefix, like the canary.

    A reader scanning the substrate must be able to tell a liveness
    marker from a real trace without reading the attributes.
    """
    assert LIVENESS_SPAN_NAME.startswith("_")
