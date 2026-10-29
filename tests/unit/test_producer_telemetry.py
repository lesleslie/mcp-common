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
    ProducerTracingResult,
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

    The SDK is a declared dependency of this package -- it was promoted
    out of the ``telemetry`` dependency group precisely so a consumer
    that calls the producer API gets a working exporter without having
    to know which packages that requires. The skip is still worth
    keeping: a developer running the suite in an environment where the
    SDK is absent should get the SDK-dependent tests skipped rather
    than failed.
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

        result = configure_producer_tracing("mahavishnu")
        assert result.export_spans is False
        assert result.provider is None
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

        result = configure_producer_tracing("mahavishnu")
        assert result.export_spans is True
        assert result.provider is trace.get_tracer_provider()

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

        result = configure_producer_tracing("oneiric")
        assert result.export_spans is True
        # The incumbent's provider, not ours: we declined to replace it,
        # so we do not get to close it either.
        assert result.provider is None
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

        result = configure_producer_tracing(
            "akosha", endpoint="http://127.0.0.1:9999"
        )
        assert result.export_spans is True
        assert (
            trace.get_tracer_provider().resource.attributes["service.name"] == "akosha"
        )

    def test_extra_resource_attributes_reach_the_resource(
        self,
        clean_otel_env: None,
        reset_tracer_provider: Any,
        otel_sdk: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from opentelemetry import trace

        monkeypatch.setenv(_ENDPOINT_ENV, "http://127.0.0.1:4318")

        result = configure_producer_tracing(
            "session-buddy",
            resource_attributes={"telemetry.source": "session-buddy"},
        )
        assert result.export_spans is True
        attributes = trace.get_tracer_provider().resource.attributes
        assert attributes["telemetry.source"] == "session-buddy"
        assert attributes["service.name"] == "session-buddy"

    def test_extra_attributes_cannot_shadow_the_identity(
        self,
        clean_otel_env: None,
        reset_tracer_provider: Any,
        otel_sdk: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The canonical identity wins over a caller's extra attributes.

        The receiver quarantines a span whose namespace is not on its
        allowlist, so an extra attribute that shadowed the namespace
        would silently quarantine every span the service produced.
        """
        from opentelemetry import trace

        monkeypatch.setenv(_ENDPOINT_ENV, "http://127.0.0.1:4318")

        configure_producer_tracing(
            "session-buddy",
            service_namespace=DEFAULT_SERVICE_NAMESPACE,
            resource_attributes={
                "service.namespace": "session-buddy",
                "service.name": "wrong-name",
            },
        )
        attributes = trace.get_tracer_provider().resource.attributes
        assert attributes["service.namespace"] == DEFAULT_SERVICE_NAMESPACE
        assert attributes["service.name"] == "session-buddy"


class TestProviderOwnership:
    """Who installed the provider decides who may close it.

    The result carries two facts because they answer two questions.
    ``export_spans`` says whether spans can go anywhere at all. ``provider``
    says whether the provider is OURS. Conflating them is what let a
    caller shut down an exporter it never installed -- reaching into
    another component's provider at process exit.
    """

    def test_the_provider_we_installed_is_ours(
        self,
        clean_otel_env: None,
        reset_tracer_provider: Any,
        otel_sdk: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from opentelemetry import trace

        monkeypatch.setenv(_ENDPOINT_ENV, "http://127.0.0.1:4318")

        result = configure_producer_tracing("session-buddy")

        assert result.provider is not None
        assert result.provider is trace.get_tracer_provider()

    def test_a_provider_we_declined_to_replace_is_not_ours(
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

        result = configure_producer_tracing("session-buddy")

        # Spans will export -- the incumbent's provider does that -- but
        # the incumbent owns it, so a caller must not close it.
        assert result.export_spans is True
        assert result.provider is None

    def test_an_unconfigured_process_owns_nothing(
        self,
        clean_otel_env: None,
        reset_tracer_provider: Any,
        otel_sdk: None,
    ) -> None:
        result = configure_producer_tracing("mahavishnu")

        assert result.provider is None
        assert result.export_spans is False


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


class TestTheMiddlewareIsGatedOnExport:
    """The request-span middleware is attached only when spans can go somewhere.

    The launcher is shared with MCP servers outside the Bodai core set.
    Attaching the middleware unconditionally would give every one of them
    a per-request span that is recorded and then discarded -- new work on
    a code path they never opted into.
    """

    async def test_a_process_that_cannot_export_gets_no_middleware(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from mcp_common.server import launcher

        attached: list[str] = []

        monkeypatch.setattr(
            launcher,
            "configure_producer_tracing",
            lambda *a, **k: ProducerTracingResult(None, False),
        )
        monkeypatch.setattr(
            launcher,
            "_attach_request_span_middleware",
            lambda server, name: attached.append(name) or True,
        )

        async def _fake_run(*_args: Any, **_kwargs: Any) -> None:
            return None

        monkeypatch.setattr(launcher, "run_with_uvicorn_config", _fake_run)

        await launcher.launch(
            build_server=lambda: object(),
            component_name="third-party",
        )

        assert attached == []

    async def test_a_process_that_can_export_gets_the_middleware(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from mcp_common.server import launcher

        attached: list[str] = []

        monkeypatch.setattr(
            launcher,
            "configure_producer_tracing",
            lambda *a, **k: ProducerTracingResult(None, True),
        )
        monkeypatch.setattr(
            launcher,
            "_attach_request_span_middleware",
            lambda server, name: attached.append(name) or True,
        )

        async def _fake_run(*_args: Any, **_kwargs: Any) -> None:
            return None

        monkeypatch.setattr(launcher, "run_with_uvicorn_config", _fake_run)

        await launcher.launch(
            build_server=lambda: object(),
            component_name="mahavishnu",
        )

        assert attached == ["mahavishnu"]


def test_the_liveness_span_name_is_distinguishable() -> None:
    """Synthetic markers carry an underscore prefix, like the canary.

    A reader scanning the substrate must be able to tell a liveness
    marker from a real trace without reading the attributes.
    """
    assert LIVENESS_SPAN_NAME.startswith("_")
