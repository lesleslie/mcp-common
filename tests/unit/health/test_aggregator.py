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
from mcp_common.health.feed import HealthFeedState, StatusValue


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
