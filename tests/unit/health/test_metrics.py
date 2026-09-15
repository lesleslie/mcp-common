"""Unit tests for ``mcp_common.health.metrics.update_health_metrics``.

Plan §4 Observability + §11.4 PromQL alerts: this helper wires the
aggregator's ``HealthSnapshot`` into the consumer's existing
``prometheus_client.CollectorRegistry`` so the alerts in
``config/prometheus/health_aggregator_alerts.yml`` fire live.

Tests pin:
- Each metric is registered lazily on first call (no duplicate
  registration errors on repeated calls).
- The four required metrics emit with the correct labels and values.
- A status flip (healthy → degraded) clears the prior ``status=healthy``
  series to 0 so stale series don't keep firing alerts forever.
- Per-repo isolation: ``repo="akosha"`` and ``repo="session-buddy"``
  produce separate metric series.
"""

from __future__ import annotations

import time

import pytest

from mcp_common.health.aggregator import aggregate_feed_states
from mcp_common.health.feed import HealthFeedState
from mcp_common.health.metrics import _metric_cache, update_health_metrics


@pytest.fixture(autouse=True)
def _reset_metric_cache() -> None:
    """Clear the module-level ``_metric_cache`` between tests.

    Without this, tests that drop their ``CollectorRegistry`` instance
    see the cache return stale ``_RegistryMetrics`` for the next test's
    registry (CPython can reuse the same ``id()`` for the new
    registry once the previous one is garbage-collected, so the
    ``id()``-keyed cache returns the wrong metric instances).
    """
    _metric_cache.clear()
    yield
    _metric_cache.clear()


@pytest.fixture
def registry() -> "prometheus_client.CollectorRegistry":
    """Fresh ``CollectorRegistry`` per test — no global state leaks."""
    from prometheus_client import CollectorRegistry

    return CollectorRegistry()


def _sample_snapshot(feed_states: dict[str, HealthFeedState]) -> dict[str, object]:
    return aggregate_feed_states(feed_states)


def _read_metric_value(
    registry: "prometheus_client.CollectorRegistry",
    metric_name: str,
    labels: dict[str, str],
) -> float:
    """Read a gauge value from the registry. Returns 0 if not present."""
    from prometheus_client import generate_latest

    # ``generate_latest`` returns ``bytes`` in Prometheus text-exposition
    # format. Parse for the matching label set; return 0 if not found.
    text = generate_latest(registry).decode()
    target = (
        f'{metric_name}{{'
        + ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        + "}"
    )
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        if line.startswith(target):
            return float(line.split()[-1])
    return 0.0


def test_metrics_register_lazily_on_first_call(registry: object) -> None:
    """First call registers the four metrics; no duplicate registration errors."""
    snap = _sample_snapshot(
        {"local_traces": HealthFeedState(entities_count=10, cycles_total=5)}
    )

    # Must not raise on first or second call (lazy registration must
    # reuse the cached instances, not re-register).
    update_health_metrics(
        registry=registry,  # type: ignore[arg-type]
        snap=snap,  # type: ignore[arg-type]
        repo="akosha",
        halflife_seconds=300,
        duration_ms=1.5,
    )
    update_health_metrics(
        registry=registry,  # type: ignore[arg-type]
        snap=snap,  # type: ignore[arg-type]
        repo="akosha",
        halflife_seconds=300,
        duration_ms=1.5,
    )


def test_feed_status_gauge_reflects_aggregator_verdict(registry: object) -> None:
    """``health_feed_status{repo, feed, status}`` = 1 for current status."""
    snap = _sample_snapshot(
        {
            "local_traces": HealthFeedState(entities_count=10, cycles_total=5),
            "code_graphs": HealthFeedState(entities_count=10, cycles_total=5),
        }
    )
    update_health_metrics(
        registry=registry,  # type: ignore[arg-type]
        snap=snap,  # type: ignore[arg-type]
        repo="akosha",
        halflife_seconds=300,
        duration_ms=1.0,
    )

    # Both feeds are HEALTHY (entities > 0, no errors).
    for feed in ("local_traces", "code_graphs"):
        assert (
            _read_metric_value(
                registry,  # type: ignore[arg-type]
                "health_feed_status",
                {"repo": "akosha", "feed": feed, "status": "healthy"},
            )
            == 1.0
        )
        # The non-current statuses must be 0, not absent.
        for status_value in ("warming_up", "degraded", "failed"):
            assert (
                _read_metric_value(
                    registry,  # type: ignore[arg-type]
                    "health_feed_status",
                    {"repo": "akosha", "feed": feed, "status": status_value},
                )
                == 0.0
            )


def test_status_flip_clears_prior_status_series(registry: object) -> None:
    """healthy → degraded transition must zero the healthy series."""
    # First call: both feeds healthy.
    healthy_snap = _sample_snapshot(
        {
            "local_traces": HealthFeedState(entities_count=10, cycles_total=5),
        }
    )
    update_health_metrics(
        registry=registry,  # type: ignore[arg-type]
        snap=healthy_snap,  # type: ignore[arg-type]
        repo="akosha",
        halflife_seconds=300,
        duration_ms=1.0,
    )
    assert (
        _read_metric_value(
            registry,  # type: ignore[arg-type]
            "health_feed_status",
            {"repo": "akosha", "feed": "local_traces", "status": "healthy"},
        )
        == 1.0
    )

    # Second call: degraded (error within halflife).
    degraded_snap = _sample_snapshot(
        {
            "local_traces": HealthFeedState(
                entities_count=10,
                cycles_total=5,
                errors_total=1,
                last_error_at=time.time(),  # within halflife
            ),
        }
    )
    update_health_metrics(
        registry=registry,  # type: ignore[arg-type]
        snap=degraded_snap,  # type: ignore[arg-type]
        repo="akosha",
        halflife_seconds=300,
        duration_ms=1.0,
    )
    # New current status = degraded.
    assert (
        _read_metric_value(
            registry,  # type: ignore[arg-type]
            "health_feed_status",
            {"repo": "akosha", "feed": "local_traces", "status": "degraded"},
        )
        == 1.0
    )
    # Prior status = healthy must drop to 0 (otherwise Prometheus
    # alerts would keep firing the stale series forever).
    assert (
        _read_metric_value(
            registry,  # type: ignore[arg-type]
            "health_feed_status",
            {"repo": "akosha", "feed": "local_traces", "status": "healthy"},
        )
        == 0.0
    )


def test_halflife_seconds_gauge_carries_current_value(registry: object) -> None:
    """``mcp_common_health_halflife_seconds{repo}`` = current halflife."""
    snap = _sample_snapshot(
        {"local_traces": HealthFeedState(entities_count=10, cycles_total=5)}
    )

    update_health_metrics(
        registry=registry,  # type: ignore[arg-type]
        snap=snap,  # type: ignore[arg-type]
        repo="akosha",
        halflife_seconds=300,
        duration_ms=1.0,
    )
    assert (
        _read_metric_value(
            registry,  # type: ignore[arg-type]
            "mcp_common_health_halflife_seconds",
            {"repo": "akosha"},
        )
        == 300.0
    )

    # ``--health-disable-decay`` sets halflife to 0; the gauge
    # must reflect that so the BodaiHealthDecayDisabled alert fires.
    update_health_metrics(
        registry=registry,  # type: ignore[arg-type]
        snap=snap,  # type: ignore[arg-type]
        repo="akosha",
        halflife_seconds=0,
        duration_ms=1.0,
    )
    assert (
        _read_metric_value(
            registry,  # type: ignore[arg-type]
            "mcp_common_health_halflife_seconds",
            {"repo": "akosha"},
        )
        == 0.0
    )


def test_per_repo_isolation(registry: object) -> None:
    """``repo="akosha"`` and ``repo="session-buddy"`` produce separate series."""
    snap = _sample_snapshot(
        {"local_traces": HealthFeedState(entities_count=10, cycles_total=5)}
    )
    update_health_metrics(
        registry=registry,  # type: ignore[arg-type]
        snap=snap,  # type: ignore[arg-type]
        repo="akosha",
        halflife_seconds=300,
        duration_ms=1.0,
    )
    update_health_metrics(
        registry=registry,  # type: ignore[arg-type]
        snap=snap,  # type: ignore[arg-type]
        repo="session-buddy",
        halflife_seconds=300,
        duration_ms=1.0,
    )

    assert (
        _read_metric_value(
            registry,  # type: ignore[arg-type]
            "health_feed_status",
            {"repo": "akosha", "feed": "local_traces", "status": "healthy"},
        )
        == 1.0
    )
    assert (
        _read_metric_value(
            registry,  # type: ignore[arg-type]
            "health_feed_status",
            {"repo": "session-buddy", "feed": "local_traces", "status": "healthy"},
        )
        == 1.0
    )
    # And each repo's halflife gauge is independent.
    assert (
        _read_metric_value(
            registry,  # type: ignore[arg-type]
            "mcp_common_health_halflife_seconds",
            {"repo": "akosha"},
        )
        == 300.0
    )
    assert (
        _read_metric_value(
            registry,  # type: ignore[arg-type]
            "mcp_common_health_halflife_seconds",
            {"repo": "session-buddy"},
        )
        == 300.0
    )


def test_aggregate_duration_histogram_observes_values(registry: object) -> None:
    """Histogram observes the ``duration_ms`` argument per call."""
    snap = _sample_snapshot(
        {"local_traces": HealthFeedState(entities_count=10, cycles_total=5)}
    )
    update_health_metrics(
        registry=registry,  # type: ignore[arg-type]
        snap=snap,  # type: ignore[arg-type]
        repo="akosha",
        halflife_seconds=300,
        duration_ms=1.5,
    )
    update_health_metrics(
        registry=registry,  # type: ignore[arg-type]
        snap=snap,  # type: ignore[arg-type]
        repo="akosha",
        halflife_seconds=300,
        duration_ms=2.5,
    )

    # Read the histogram's sample count from the text exposition —
    # it increments on each ``.observe()`` call.
    from prometheus_client import generate_latest

    text = generate_latest(registry).decode()
    histogram_lines = [
        line
        for line in text.splitlines()
        if line.startswith("mcp_common_health_aggregate_duration_ms_count")
        and 'repo="akosha"' in line
    ]
    assert histogram_lines, "expected histogram _count series for akosha"
    # Two observations should produce a count of 2.
    assert float(histogram_lines[0].split()[-1]) == 2.0
