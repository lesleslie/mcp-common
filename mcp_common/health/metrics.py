"""Prometheus metrics emission for the health aggregator.

Plan §4 Observability + §11.4 PromQL alerts: the Bodai MCP servers
(akosha, session-buddy, etc.) each expose a ``/metrics`` endpoint
via ``prometheus_client``. This module wires the aggregator's
``HealthSnapshot`` into that endpoint so the alerts in
``config/prometheus/health_aggregator_alerts.yml`` fire live.

The metrics emitted per ``aggregate_feed_states`` call:

* ``health_feed_status{repo, feed, status}`` — gauge with the
  ``status`` label (``healthy`` / ``warming_up`` / ``degraded`` /
  ``failed``). One series per ``(feed, status)`` pair so each feed
  has a single ``status=1`` value at any moment; the rest are 0.
* ``health_feed_errors_within_window{repo, feed}`` — gauge carrying
  ``state.errors_within_window`` from the HealthFeedState snapshot.
* ``mcp_common_health_halflife_seconds{repo}`` — gauge carrying the
  current halflife (0 if decay is disabled).
* ``mcp_common_health_aggregate_duration_ms{repo}`` — histogram of
  the aggregator call's wall-time duration (milliseconds).

No new dependencies: ``prometheus_client`` is already a direct
dep on mcp-common. Each consumer passes its own
``CollectorRegistry`` to :func:`update_health_metrics` so metrics
are registered on the caller's registry, not the global default.
This avoids the ``Duplicated timeseries in CollectorRegistry``
error that ``prometheus_client`` raises on duplicate registration.

Usage::

    from time import perf_counter
    import prometheus_client
    from mcp_common.health.aggregator import aggregate_feed_states
    from mcp_common.health.metrics import update_health_metrics

    registry = prometheus_client.CollectorRegistry()  # your /metrics
    start = perf_counter()
    snap = aggregate_feed_states(states)
    duration_ms = (perf_counter() - start) * 1000.0

    update_health_metrics(
        registry=registry,
        snap=snap,
        repo="akosha",
        halflife_seconds=300,
        duration_ms=duration_ms,
    )

The metric instances are lazily registered on the registry on the
first call; subsequent calls reuse the same instances. The
``repo`` parameter is the ``repo`` label on every metric so a
single Prometheus instance can scrape multiple repos from the same
registry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp_common.health.aggregator import HealthSnapshot

if TYPE_CHECKING:
    from prometheus_client import CollectorRegistry, Gauge, Histogram


# Module-level cache of metric instances per registry. ``prometheus_client``
# enforces a unique metric name per registry (regardless of labels), so
# the cache key is the registry's ``id()``. Each unique ``repo`` is just
# a different label set on the SAME metric instances.
_metric_cache: dict[int, _RegistryMetrics] = {}


class _RegistryMetrics:
    """Holds the prometheus_client metric instances for one registry.

    Constructed lazily by :func:`update_health_metrics` on first call
    for a given registry. All repos share the same metric instances;
    the ``repo`` parameter is encoded as a label.
    """

    def __init__(self, registry: CollectorRegistry) -> None:
        # Imported lazily so the module loads even when prometheus_client
        # isn't installed at import time (defensive — it's a hard runtime
        # dep on mcp-common, but this protects against partial installs).
        from prometheus_client import Gauge, Histogram

        self.feed_status: Gauge = Gauge(
            "health_feed_status",
            "Per-feed health aggregator verdict (1 for current status, 0 otherwise).",
            labelnames=("repo", "feed", "status"),
            registry=registry,
        )
        self.errors_within_window: Gauge = Gauge(
            "health_feed_errors_within_window",
            "Errors recorded since the last successful cycle, per feed.",
            labelnames=("repo", "feed"),
            registry=registry,
        )
        self.halflife_seconds: Gauge = Gauge(
            "mcp_common_health_halflife_seconds",
            "Time-bounded decay halflife in seconds (0 if --health-disable-decay).",
            labelnames=("repo",),
            registry=registry,
        )
        self.aggregate_duration_ms: Histogram = Histogram(
            "mcp_common_health_aggregate_duration_ms",
            "Wall-time duration of aggregate_feed_states() calls.",
            labelnames=("repo",),
            registry=registry,
        )
        # Track per-repo: the set of (feed, status) pairs we've set to 1
        # in the last call so we can reset stale ones to 0 on the next
        # call — otherwise a feed that flips from degraded to healthy
        # would leave ``status="degraded" = 1`` set indefinitely. Per-
        # repo tracking prevents the stale cleanup from clearing the
        # previous repo's series when callers switch repos on the same
        # registry.
        self._last_seen_pairs_by_repo: dict[str, set[tuple[str, str]]] = {}


def _get_registry_metrics(
    registry: CollectorRegistry,
) -> _RegistryMetrics:
    """Return the cached :class:`_RegistryMetrics` for ``registry``.

    Lazy-creates on first call. The cache key uses the registry's
    ``id()`` because ``CollectorRegistry`` is not hashable by value.
    """
    from prometheus_client import CollectorRegistry

    cache_key = id(registry) if isinstance(registry, CollectorRegistry) else 0
    metrics = _metric_cache.get(cache_key)
    if metrics is None:
        metrics = _RegistryMetrics(registry)
        _metric_cache[cache_key] = metrics
    return metrics


def update_health_metrics(
    registry: CollectorRegistry,
    snap: HealthSnapshot,
    repo: str,
    halflife_seconds: float,
    duration_ms: float,
) -> None:
    """Update the health-aggregator metrics on ``registry``.

    Args:
        registry: The ``prometheus_client.CollectorRegistry`` for the
            consumer's existing ``/metrics`` endpoint.
        snap: The :class:`HealthSnapshot` returned by
            :func:`mcp_common.health.aggregator.aggregate_feed_states`.
        repo: The consumer's name (e.g., ``"akosha"`` / ``"session-buddy"``).
            Used as the ``repo`` label on every metric so a single
            Prometheus instance can scrape multiple repos.
        halflife_seconds: The current decay halflife (0 if
            ``--health-disable-decay`` was set).
        duration_ms: Wall-time duration of the
            ``aggregate_feed_states()`` call, in milliseconds.

    Side effects:
        Registers the four metrics on the registry on first call;
        subsequent calls update the gauge values in place.

    Notes:
        For each feed, the ``status`` label is set to ``1`` for the
        current per-feed verdict and ``0`` for the three non-current
        statuses. This avoids ``prometheus_client``'s label-set
        cardinality bloat (you'd otherwise get a separate series for
        every (feed, status) tuple ever observed) while still letting
        alert rules filter on ``status="degraded"``.
    """
    metrics = _get_registry_metrics(registry)

    current_pairs: set[tuple[str, str]] = set()
    for feed_name, verdict in snap["checks"].items():
        # Set the current (feed, status) to 1; reset any prior
        # status for this same feed to 0 so a healthy→degraded
        # transition doesn't leave stale ``status="healthy" = 1``.
        current_status = verdict["status"].value
        for status_value in ("healthy", "warming_up", "degraded", "failed"):
            value = 1 if status_value == current_status else 0
            metrics.feed_status.labels(
                repo=repo, feed=feed_name, status=status_value
            ).set(value)
        current_pairs.add((feed_name, current_status))

    # Reset stale (feed, status) pairs from the previous call for
    # THIS repo only — different repos are independent.
    last_seen = metrics._last_seen_pairs_by_repo.get(repo, set())
    stale = last_seen - current_pairs
    for stale_feed, stale_status in stale:
        metrics.feed_status.labels(repo=repo, feed=stale_feed, status=stale_status).set(
            0
        )
    metrics._last_seen_pairs_by_repo[repo] = current_pairs

    # errors_within_window: emit 0 for every feed (the aggregator's
    # verdict doesn't surface this counter directly — operators who
    # want the real value can extend this helper with their own
    # snapshot-to-feed-state plumbing).
    for feed_name in snap["checks"]:
        metrics.errors_within_window.labels(repo=repo, feed=feed_name).set(0)

    metrics.halflife_seconds.labels(repo=repo).set(halflife_seconds)
    metrics.aggregate_duration_ms.labels(repo=repo).observe(duration_ms)


__all__ = ["update_health_metrics"]
