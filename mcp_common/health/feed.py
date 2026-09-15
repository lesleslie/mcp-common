"""Per-feed health state and reason codes.

This module owns the canonical ``HealthFeedState`` dataclass plus its three
mutator helpers (``record_success``, ``record_error``) and the per-feed
predicate ``is_healthy`` that maps a state snapshot to a time-bounded
``(healthy: bool, StatusValue, list[ReasonCode])`` triple.

The aggregator that rolls multiple feeds up to a single worst-case status
lives in :mod:`mcp_common.health.aggregator`.

Policy (from ``docs/plans/2026-09-14-common-mcp-client-transport-unification.md``
§5 Phase 1 task 4): no backward compatibility shims, no legacy support.
Phase 4 may extend ``ReasonCode`` (it's a ``str, Enum``); consumers should
treat unknown reasons as opaque strings.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum


class StatusValue(StrEnum):
    """Aggregate health status values, ordered by severity.

    Severity ordering (mildest → most severe)::

        HEALTHY < WARMING_UP < DEGRADED < FAILED

    Used by ``is_healthy`` per-feed and ``aggregate_feed_states`` cross-feed.
    ``__lt__`` / ``__gt__`` enable ``max()`` and ``min()`` semantics on
    heterogeneous feeds.
    """

    HEALTHY = "healthy"
    WARMING_UP = "warming_up"
    DEGRADED = "degraded"
    FAILED = "failed"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, StatusValue):
            return NotImplemented
        return _SEVERITY[self] < _SEVERITY[other]

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, StatusValue):
            return NotImplemented
        return _SEVERITY[self] > _SEVERITY[other]


_SEVERITY: dict[StatusValue, int] = {
    StatusValue.HEALTHY: 0,
    StatusValue.WARMING_UP: 1,
    StatusValue.DEGRADED: 2,
    StatusValue.FAILED: 3,
}


class ReasonCode(StrEnum):
    """Per-feed health reason codes.

    Initial set per plan §5 Phase 1 task 4. ``str`` Enum so additional codes
    added in Phase 4 (or later) remain forward-compatible: callers iterating
    the enum see new values, but JSON-encoded values stay as plain strings.
    """

    WARMING_UP_EMPTY_FEED = "warming_up_empty_feed"
    WARMING_UP_NEVER_CYCLED = "warming_up_never_cycled"
    INGESTER_NOT_RUNNING = "ingester_not_running"
    FEED_NEVER_POPULATED = "feed_never_populated"
    RECENT_ERROR_IN_WINDOW = "recent_error_in_window"
    ERROR_OUTSIDE_HALFLIFE = "error_outside_halflife"
    ERROR_WITHIN_HALFLIFE = "error_within_halflife"
    NO_PRODUCER_EVER_CYCLED = "no_producer_ever_cycled"
    PRODUCER_NOT_ALIVE = "producer_not_alive"


@dataclass
class HealthFeedState:
    """Time-bounded snapshot of a single feed's health.

    Producers (ingesters) mutate this through :func:`record_success` and
    :func:`record_error`; aggregators read it via :func:`is_healthy`.

    Attributes:
        entities_count: Current number of entities in the feed.
        last_updated_timestamp: ``time.time()`` value of the last successful
            mutation, or ``None`` if the feed has never produced.
        cycles_total: Total producer cycles completed (success + failure).
        errors_total: Cumulative error count (does not decay).
        last_error_at: ``time.time()`` value of the most recent error, or
            ``None`` if no error has been recorded.
        errors_within_window: Errors recorded since the last successful
            cycle. Reset to 0 by :func:`record_success`.
        first_unhealthy_at: ``time.time()`` value at which the feed first
            entered an unhealthy state in the current burn window.
            ``None`` while healthy. :func:`record_success` clears this so a
            subsequent unhealthy entry resets the burn-rate anchor.
        ingester_running: ``True`` when the producer task is alive.
    """

    entities_count: int = 0
    last_updated_timestamp: float | None = None
    cycles_total: int = 0
    errors_total: int = 0
    last_error_at: float | None = None
    errors_within_window: int = 0
    first_unhealthy_at: float | None = None
    ingester_running: bool = False


def record_success(state: HealthFeedState) -> None:
    """Record a successful cycle on the feed.

    Resets ``errors_within_window`` AND clears ``first_unhealthy_at``. The
    latter tracks the *entry* into an unhealthy state; clearing it on a
    successful cycle means the next unhealthy entry resets the burn-rate
    anchor rather than carrying an outdated anchor from a previous episode.
    """
    state.errors_within_window = 0
    state.first_unhealthy_at = None


def record_error(state: HealthFeedState) -> None:
    """Record an error on the feed.

    Updates ``last_error_at`` to the current time and sets
    ``first_unhealthy_at`` on the healthy→unhealthy transition
    (idempotent on subsequent errors — the first call in an unhealthy
    episode anchors the burn window).

    The caller is responsible for incrementing ``errors_total`` and
    ``cycles_total`` outside this helper; both are producer-specific policy
    choices (e.g. whether a retried-and-recovered attempt still counts).
    """
    now = time.time()
    state.last_error_at = now
    if state.first_unhealthy_at is None:
        state.first_unhealthy_at = now


def is_healthy(
    state: HealthFeedState,
    halflife_seconds: float = 300,
) -> tuple[bool, StatusValue, list[ReasonCode]]:
    """Evaluate one feed's health as ``(healthy, status, reason_codes)``.

    ``healthy`` is ``True`` iff ``status`` is exactly :attr:`StatusValue.HEALTHY`;
    warming_up, degraded and failed all imply ``healthy=False`` even though
    warming_up does not block ``/health=200`` in the wider contract.

    Time-bounded decay:
        - ``last_error_at`` within ``halflife_seconds`` of ``now`` → DEGRADED.
        - ``last_error_at`` outside ``halflife_seconds`` → HEALTHY (decayed).
        - No error ever recorded → pure entity-count check.

    HNSW-on-DuckDB hardening (plan §5 task 6):
        A feed where the producer reports ``ingester_running=True`` but
        ``cycles_total == 0`` has never completed a single cycle — it is
        *not* "warming up", it is broken-before-first-success. This branch
        surfaces as DEGRADED with ``FEED_NEVER_POPULATED`` so operators
        can distinguish a stuck producer (e.g. HNSW index creation
        failing on the very first attempt) from a healthy-but-empty feed.

    Order of evaluation:
        1. Recent error → DEGRADED (terminal: errors override everything else).
        2. Empty feed + ``cycles_total == 0`` + ingester running →
           DEGRADED (HNSW hardening; never-cycled producer).
        3. Empty feed + ingester not running → FAILED.
        4. Empty feed + ingester running + at least one cycle → WARMING_UP.
        5. Populated, error aged out → HEALTHY (with decayed-error reason).
        6. Populated, no errors → HEALTHY (no reason codes).
    """
    now = time.time()

    error_age: float | None = (
        now - state.last_error_at if state.last_error_at is not None else None
    )

    # 1. Recent error wins over everything.
    if error_age is not None and error_age <= halflife_seconds:
        return (
            False,
            StatusValue.DEGRADED,
            [ReasonCode.ERROR_WITHIN_HALFLIFE, ReasonCode.RECENT_ERROR_IN_WINDOW],
        )

    # 2. Empty-feed handling (no recent error).
    if state.entities_count == 0:
        # 2a. HNSW hardening: producer is alive but has never completed a
        # cycle. Distinguish from "warming up" (which implies the producer
        # has at least produced once and is mid-stride to filling the feed).
        if state.cycles_total == 0 and state.ingester_running:
            return (
                False,
                StatusValue.DEGRADED,
                [ReasonCode.FEED_NEVER_POPULATED],
            )
        # 2b. Producer dead and no data.
        if not state.ingester_running:
            return (
                False,
                StatusValue.FAILED,
                [ReasonCode.FEED_NEVER_POPULATED, ReasonCode.INGESTER_NOT_RUNNING],
            )
        # 2c. Producer alive and has cycled at least once but no entities yet.
        return (
            False,
            StatusValue.WARMING_UP,
            [ReasonCode.WARMING_UP_EMPTY_FEED],
        )

    # 3. Populated feed.
    if error_age is not None:
        return (
            True,
            StatusValue.HEALTHY,
            [ReasonCode.ERROR_OUTSIDE_HALFLIFE],
        )

    # 4. Populated, no errors.
    return (True, StatusValue.HEALTHY, [])


__all__ = [
    "HealthFeedState",
    "ReasonCode",
    "StatusValue",
    "is_healthy",
    "record_error",
    "record_success",
]
