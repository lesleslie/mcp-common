"""Unit tests for ``mcp_common.health.aggregator``.

The plan's Phase 1 task 8 specifies exactly five tests here. Each carries
``@pytest.mark.req([...])`` so the requirement-traceability audit can
verify coverage: REQ-002 (time-bounded decay), REQ-003 (warming_up
predicate), REQ-007 (error_within_halflife causes degraded),
REQ-008 (warming_up when empty + ingester running + no errors).
"""

from __future__ import annotations

import time

import pytest

from mcp_common.health.aggregator import aggregate_feed_states
from mcp_common.health.feed import HealthFeedState, ReasonCode, StatusValue


# ---------------------------------------------------------------------------
# REQ-002 — time-bounded decay semantics
# ---------------------------------------------------------------------------


@pytest.mark.req(["REQ-002"])
def test_is_healthy_true_when_no_errors() -> None:
    """No errors → healthy True (and status HEALTHY).

    Anchor: REQ-002 — a clean running feed reports healthy. ``is_healthy``
    exposes the same predicate the aggregator uses for the per-feed
    ``status``, so exercising it via the aggregator pins both layers
    in one test.
    """
    states = {
        "local_traces": HealthFeedState(
            entities_count=128,
            cycles_total=4,
            ingester_running=True,
            last_updated_timestamp=time.time(),
        ),
    }

    snap = aggregate_feed_states(states)
    assert snap["status"] == StatusValue.HEALTHY
    assert snap["checks"]["local_traces"]["status"] == StatusValue.HEALTHY
    assert snap["checks"]["local_traces"]["healthy"] is True


@pytest.mark.req(["REQ-002", "REQ-007"])
def test_is_healthy_true_when_error_outside_halflife() -> None:
    """Error aged past ``halflife_seconds`` → still HEALTHY (decayed).

    Pins REQ-002 (time-bounded decay for transient errors) and REQ-007
    (the halflife threshold itself drives the healthy/degraded split).
    """
    halflife = 300.0
    states = {
        "local_traces": HealthFeedState(
            entities_count=128,
            cycles_total=10,
            ingester_running=True,
            errors_total=1,
            last_error_at=time.time() - (halflife + 1.0),
        ),
    }

    snap = aggregate_feed_states(states, halflife_seconds=halflife)

    assert snap["status"] == StatusValue.HEALTHY
    feed_check = snap["checks"]["local_traces"]
    assert feed_check["status"] == StatusValue.HEALTHY
    assert feed_check["healthy"] is True


@pytest.mark.req(["REQ-002", "REQ-007"])
def test_is_degraded_when_error_within_halflife() -> None:
    """Recent error (inside halflife) → DEGRADED, healthy=False, top status DEGRADED.

    REQ-007 demands that errors within the window escalate the aggregate;
    REQ-002 is the underlying time-bounded semantics.
    """
    halflife = 300.0
    states = {
        "local_traces": HealthFeedState(
            entities_count=128,
            cycles_total=10,
            ingester_running=True,
            errors_total=1,
            last_error_at=time.time() - 5.0,
        ),
    }

    snap = aggregate_feed_states(states, halflife_seconds=halflife)

    assert snap["status"] == StatusValue.DEGRADED
    feed_check = snap["checks"]["local_traces"]
    assert feed_check["status"] == StatusValue.DEGRADED
    assert feed_check["healthy"] is False


# ---------------------------------------------------------------------------
# REQ-003 + REQ-008 — warming_up predicate
# ---------------------------------------------------------------------------


@pytest.mark.req(["REQ-003", "REQ-008"])
def test_is_warming_up_when_empty_and_no_errors_and_ingester_running() -> None:
    """Empty feed + producer alive + no errors → WARMING_UP.

    REQ-008 = warming_up predicate shape (Phase 1 lenient form).
    REQ-003 = empty-but-running tolerated before first data lands.
    """
    states = {
        "local_traces": HealthFeedState(
            entities_count=0,
            cycles_total=1,
            ingester_running=True,
        ),
    }

    snap = aggregate_feed_states(states)

    assert snap["status"] == StatusValue.WARMING_UP
    feed_check = snap["checks"]["local_traces"]
    assert feed_check["status"] == StatusValue.WARMING_UP
    assert feed_check["healthy"] is False


# ---------------------------------------------------------------------------
# REQ-002 — worst-case roll-up
# ---------------------------------------------------------------------------


@pytest.mark.req(["REQ-002"])
def test_aggregate_picks_worst_status() -> None:
    """Across feeds, status is the maximum severity.

    Severity ordering: ``failed > degraded > warming_up > healthy``.
    Construct four feeds each landing in a distinct band; the aggregate
    must return ``failed`` and surface the corresponding per-feed
    statuses intact under ``checks``.
    """
    healthy = HealthFeedState(
        entities_count=100,
        cycles_total=5,
        ingester_running=True,
        last_updated_timestamp=time.time(),
    )
    warming_up = HealthFeedState(
        entities_count=0,
        cycles_total=1,
        ingester_running=True,
    )
    degraded = HealthFeedState(
        entities_count=100,
        cycles_total=5,
        ingester_running=True,
        last_error_at=time.time() - 5.0,
        errors_total=1,
    )
    failed = HealthFeedState(
        entities_count=0,
        ingester_running=False,
    )

    snap = aggregate_feed_states(
        {
            "healthy_feed": healthy,
            "warming_up_feed": warming_up,
            "degraded_feed": degraded,
            "failed_feed": failed,
        }
    )

    # Worst status is FAILED.
    assert snap["status"] == StatusValue.FAILED

    # Each per-feed ``status`` round-trips intact.
    assert snap["checks"]["healthy_feed"]["status"] == StatusValue.HEALTHY
    assert snap["checks"]["warming_up_feed"]["status"] == StatusValue.WARMING_UP
    assert snap["checks"]["degraded_feed"]["status"] == StatusValue.DEGRADED
    assert snap["checks"]["failed_feed"]["status"] == StatusValue.FAILED

    # Severity ordering: failed outranks all; healthy is the floor.
    assert (
        StatusValue.HEALTHY
        < StatusValue.WARMING_UP
        < StatusValue.DEGRADED
        < StatusValue.FAILED
    )
    assert StatusValue.FAILED > StatusValue.DEGRADED
    assert StatusValue.DEGRADED > StatusValue.WARMING_UP
    assert StatusValue.WARMING_UP > StatusValue.HEALTHY


# ---------------------------------------------------------------------------
# HNSW-on-DuckDB hardening (plan §5 task 6) — never-cycled aggregator path
# ---------------------------------------------------------------------------


@pytest.mark.req(["REQ-008"])
def test_aggregate_picks_degraded_for_never_cycled_feed() -> None:
    """A feed with ``cycles_total == 0`` + ``ingester_running=True`` propagates DEGRADED.

    Regression coverage for the HNSW-on-DuckDB bug — when the very first
    ingest attempt raises (e.g. HNSW index creation fails), the producer
    reports ``cycles_total=0`` because the cycle never completed. The
    aggregator must surface this as DEGRADED (not WARMING_UP) so operators
    see a broken producer, not a healthy-but-still-loading feed.

    Companion to
    :func:`test_feed.test_is_degraded_when_empty_and_never_cycled`; this
    test exercises the end-to-end path through ``aggregate_feed_states``
    so the worst-case roll-up inherits the new predicate.
    """
    states = {
        "local_traces": HealthFeedState(
            entities_count=0,
            cycles_total=0,
            ingester_running=True,
        ),
    }

    snap = aggregate_feed_states(states)

    # Top-level roll-up picks up DEGRADED.
    assert snap["status"] == StatusValue.DEGRADED
    # The per-feed check surfaces the broken-producer reason.
    feed_check = snap["checks"]["local_traces"]
    assert feed_check["status"] == StatusValue.DEGRADED
    assert feed_check["healthy"] is False
    assert ReasonCode.FEED_NEVER_POPULATED in feed_check["reason_codes"]
    # Top-level reason_codes inherits the worst feed's codes.
    assert ReasonCode.FEED_NEVER_POPULATED in snap["reason_codes"]


@pytest.mark.req(["REQ-002", "REQ-008"])
def test_aggregate_worst_case_failed_outranks_never_cycled_degraded() -> None:
    """FAILED outranks DEGRADED across feeds (worst-case roll-up preserved).

    Pins that the HNSW hardening did not disturb the existing severity
    ordering — a feed whose producer is dead (``FAILED``) still outranks
    a feed whose producer is alive but never cycled (``DEGRADED``).
    """
    failed_feed = HealthFeedState(
        entities_count=0,
        cycles_total=0,
        ingester_running=False,
    )
    never_cycled_feed = HealthFeedState(
        entities_count=0,
        cycles_total=0,
        ingester_running=True,
    )

    snap = aggregate_feed_states(
        {
            "failed_feed": failed_feed,
            "never_cycled_feed": never_cycled_feed,
        }
    )

    # Worst-case roll-up is FAILED (dead producer beats broken-but-alive).
    assert snap["status"] == StatusValue.FAILED
    # Both per-feed statuses round-trip intact.
    assert snap["checks"]["failed_feed"]["status"] == StatusValue.FAILED
    assert snap["checks"]["never_cycled_feed"]["status"] == StatusValue.DEGRADED


# ---------------------------------------------------------------------------
# Decay-disabled sentinel (plan §5 task 7 / ``--health-disable-decay``)
# ---------------------------------------------------------------------------


@pytest.mark.req(["REQ-002", "REQ-007"])
def test_aggregate_decay_disabled_never_escalates_to_degraded() -> None:
    """``halflife_seconds=0`` propagates through the aggregator.

    Plan §5 task 7 / ``--health-disable-decay``: when the CLI flag
    is set, ``HEALTH_FEED_HALFLIFE_SECONDS=0`` is exported before the
    lifespan runs. The probe bodies read it and pass ``0`` to the
    aggregator; the aggregator passes it to ``is_healthy`` which
    skips the time-bounded check. The feed stays HEALTHY even when
    there's a fresh error in the window.
    """
    state = HealthFeedState(
        entities_count=100,
        last_updated_timestamp=time.time(),
        cycles_total=10,
        ingester_running=True,
        errors_total=1,
        last_error_at=time.time() - 5.0,  # would normally be within halflife
    )

    snap = aggregate_feed_states({"local_traces": state}, halflife_seconds=0)

    # Aggregate + per-feed are HEALTHY despite the recent error.
    assert snap["status"] == StatusValue.HEALTHY
    assert snap["checks"]["local_traces"]["status"] == StatusValue.HEALTHY
    assert snap["checks"]["local_traces"]["healthy"] is True
    # No DEGRADED-elevated reason codes surface.
    assert ReasonCode.ERROR_WITHIN_HALFLIFE not in snap["checks"]["local_traces"]["reason_codes"]
