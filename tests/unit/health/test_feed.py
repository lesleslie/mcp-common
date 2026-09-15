"""Unit tests for ``mcp_common.health.feed``.

Covers the per-feed helper trio: ``record_success``, ``record_error``,
``is_healthy``. Phase 1 of
``docs/plans/2026-09-14-common-mcp-client-transport-unification.md``
task 8 specifies ~5 helper tests; this file pins the contract for the
mutators plus the time-bounded ``is_healthy`` predicate.
"""

from __future__ import annotations

import time

import pytest

from mcp_common.health.feed import (
    HealthFeedState,
    ReasonCode,
    StatusValue,
    is_healthy,
    record_error,
    record_success,
)


# ---------------------------------------------------------------------------
# record_success / record_error
# ---------------------------------------------------------------------------


def test_record_success_resets_errors_within_window_and_clears_first_unhealthy_at() -> None:
    """``record_success`` clears both error-window counters in one shot.

    Anchor: plan task 4 — ``record_success(state)`` resets
    ``errors_within_window`` AND clears ``first_unhealthy_at``. Clearing
    the anchor lets the next unhealthy entry reset the burn-rate start.
    """
    state = HealthFeedState(
        errors_within_window=4,
        first_unhealthy_at=time.time() - 30.0,
        errors_total=4,
        last_error_at=time.time() - 30.0,
    )

    record_success(state)

    assert state.errors_within_window == 0
    assert state.first_unhealthy_at is None
    # Error bookkeeping that ``record_success`` deliberately doesn't touch:
    assert state.errors_total == 4
    assert state.last_error_at is not None


def test_record_error_sets_first_unhealthy_at_only_on_transition() -> None:
    """First error in a window anchors; subsequent errors are idempotent.

    Anchors: ``record_error(state)`` updates ``last_error_at`` and sets
    ``first_unhealthy_at`` on the healthy→unhealthy transition
    (idempotent on subsequent errors). Verifies both the first-call
    anchor and the idempotency guarantee.
    """
    state = HealthFeedState(entities_count=10, ingester_running=True)
    assert state.first_unhealthy_at is None

    before = time.time()
    record_error(state)
    after = time.time()

    assert state.first_unhealthy_at is not None
    first_anchor = state.first_unhealthy_at
    assert before <= first_anchor <= after
    assert state.last_error_at == first_anchor

    # Subsequent error: ``first_unhealthy_at`` must stay pinned to the
    # original anchor (NOT advance), and ``last_error_at`` must advance.
    time.sleep(0.01)
    record_error(state)
    assert state.first_unhealthy_at == first_anchor
    assert state.last_error_at is not None
    assert state.last_error_at >= first_anchor


# ---------------------------------------------------------------------------
# is_healthy — populated-feed branches
# ---------------------------------------------------------------------------


def test_is_healthy_returns_true_when_no_errors() -> None:
    """Populated, no-error feed → healthy True, status HEALTHY, no reasons."""
    state = HealthFeedState(
        entities_count=100,
        last_updated_timestamp=time.time(),
        cycles_total=5,
        ingester_running=True,
    )

    healthy, status, codes = is_healthy(state)

    assert healthy is True
    assert status == StatusValue.HEALTHY
    assert codes == []


def test_is_healthy_true_when_error_outside_halflife() -> None:
    """Error aged out beyond ``halflife_seconds`` → still HEALTHY (decayed).

    Pin the plan claim that ``is_healthy`` uses ``halflife_seconds`` so
    transient errors decay out and the feed recovers without manual
    intervention.
    """
    halflife = 300.0
    state = HealthFeedState(
        entities_count=100,
        last_updated_timestamp=time.time(),
        cycles_total=10,
        ingester_running=True,
        errors_total=1,
        last_error_at=time.time() - (halflife + 1.0),
    )

    healthy, status, codes = is_healthy(state, halflife_seconds=halflife)

    assert healthy is True
    assert status == StatusValue.HEALTHY
    assert ReasonCode.ERROR_OUTSIDE_HALFLIFE in codes


def test_is_degraded_when_error_within_halflife() -> None:
    """Recent error (within ``halflife_seconds``) → DEGRADED, healthy=False."""
    halflife = 300.0
    state = HealthFeedState(
        entities_count=100,
        last_updated_timestamp=time.time(),
        cycles_total=10,
        ingester_running=True,
        errors_total=1,
        last_error_at=time.time() - 5.0,  # well within halflife
    )

    healthy, status, codes = is_healthy(state, halflife_seconds=halflife)

    assert healthy is False
    assert status == StatusValue.DEGRADED
    assert ReasonCode.ERROR_WITHIN_HALFLIFE in codes


# ---------------------------------------------------------------------------
# is_healthy — decay-disabled sentinel (plan §5 task 7)
# ---------------------------------------------------------------------------


def test_is_healthy_decay_disabled_ignores_recent_error() -> None:
    """``halflife_seconds <= 0`` disables time-bounded decay entirely.

    With halflife disabled, even a freshly-recorded error does NOT
    escalate to DEGRADED — the populated-feed branch returns HEALTHY
    instead. Operators trigger this via the
    ``--health-disable-decay`` CLI flag (which sets
    ``HEALTH_FEED_HALFLIFE_SECONDS=0``) during incident triage when
    known upstream regressions are firing repeated errors that
    would otherwise mask real downstream faults.
    """
    state = HealthFeedState(
        entities_count=100,
        last_updated_timestamp=time.time(),
        cycles_total=10,
        ingester_running=True,
        errors_total=1,
        # 1 second ago — would be well within any normal halflife.
        last_error_at=time.time() - 1.0,
    )

    # halflife_seconds=0 is the canonical "disabled" sentinel.
    healthy, status, codes = is_healthy(state, halflife_seconds=0)

    assert healthy is True
    assert status == StatusValue.HEALTHY
    # The error is reported (so operators still see it) but not
    # escalated to DEGRADED.
    assert ReasonCode.ERROR_OUTSIDE_HALFLIFE in codes
    assert ReasonCode.ERROR_WITHIN_HALFLIFE not in codes


def test_is_healthy_decay_disabled_negative_halflife() -> None:
    """Negative ``halflife_seconds`` is also treated as disabled.

    Defensive coverage: a misconfigured operator who sets
    ``HEALTH_FEED_HALFLIFE_SECONDS=-1`` (e.g. from a wrapper script)
    should not get the opposite behaviour (everything DEGRADED).
    """
    state = HealthFeedState(
        entities_count=100,
        last_updated_timestamp=time.time(),
        cycles_total=10,
        ingester_running=True,
        errors_total=1,
        last_error_at=time.time() - 1.0,
    )

    healthy, status, _codes = is_healthy(state, halflife_seconds=-1.0)

    assert healthy is True
    assert status == StatusValue.HEALTHY


def test_is_warming_up_when_empty_and_no_errors_and_ingester_running() -> None:
    """Empty feed + ingester running + no errors → WARMING_UP.

    Implements REQ-003 + REQ-008 (warming_up predicate shape per
    Phase 4 task 6's lenient Phase-1 form).
    """
    state = HealthFeedState(
        entities_count=0,
        cycles_total=1,  # at least one cycle; still no data
        ingester_running=True,
    )

    healthy, status, codes = is_healthy(state)

    assert healthy is False
    assert status == StatusValue.WARMING_UP
    assert ReasonCode.WARMING_UP_EMPTY_FEED in codes


# ---------------------------------------------------------------------------
# is_healthy — HNSW-on-DuckDB hardening (plan §5 task 6)
# ---------------------------------------------------------------------------


def test_is_degraded_when_empty_and_never_cycled() -> None:
    """Empty feed + producer alive + zero cycles → DEGRADED, not WARMING_UP.

    Plan §5 task 6 HNSW hardening. A producer that reports
    ``ingester_running=True`` but has not yet completed a single cycle is
    *not* warming up — it is broken-before-first-success (e.g. an HNSW
    index creation failing on the very first attempt). Surface this as
    DEGRADED with ``FEED_NEVER_POPULATED`` so operators can distinguish
    a stuck producer from a healthy-but-empty feed.

    This is the regression test for the HNSW-on-DuckDB bug originally
    surfaced in :mod:`akosha.ingestion.code_graph_ingester` /
    :mod:`akosha.ingestion.otel_ingester` — when HNSW index creation
    failed on the first ingest attempt, the producers incorrectly
    reported as warming_up instead of degraded.
    """
    state = HealthFeedState(
        entities_count=0,
        cycles_total=0,  # ← never completed a single cycle
        ingester_running=True,
    )

    healthy, status, codes = is_healthy(state)

    assert healthy is False
    assert status == StatusValue.DEGRADED
    assert codes == [ReasonCode.FEED_NEVER_POPULATED]


def test_is_failed_when_empty_never_cycled_and_ingester_not_running() -> None:
    """Empty feed + zero cycles + producer dead → FAILED, not DEGRADED.

    Companion to :func:`test_is_degraded_when_empty_and_never_cycled`:
    when the producer has also exited (``ingester_running=False``), the
    feed is FAILED rather than DEGRADED. FAILED outranks DEGRADED in
    the aggregator's worst-case roll-up; operators reading the
    top-level ``status`` see the more severe condition first.
    """
    state = HealthFeedState(
        entities_count=0,
        cycles_total=0,
        ingester_running=False,
    )

    healthy, status, codes = is_healthy(state)

    assert healthy is False
    assert status == StatusValue.FAILED
    assert ReasonCode.FEED_NEVER_POPULATED in codes
    assert ReasonCode.INGESTER_NOT_RUNNING in codes


# ---------------------------------------------------------------------------
# is_healthy — empty-feed failed branch
# ---------------------------------------------------------------------------


def test_is_failed_when_empty_and_ingester_not_running() -> None:
    """Empty feed + producer dead → FAILED, healthy=False."""
    state = HealthFeedState(
        entities_count=0,
        ingester_running=False,
    )

    healthy, status, codes = is_healthy(state)

    assert healthy is False
    assert status == StatusValue.FAILED
    assert codes  # at least one reason surfaced


# ---------------------------------------------------------------------------
# record_success / record_error — interaction with is_healthy
# ---------------------------------------------------------------------------


def test_record_success_reverts_degraded_back_to_healthy() -> None:
    """Mutator cycle: error → degraded, success → healthy (within reason).

    End-to-end check that ``record_success`` clears the window counters
    sufficiently for ``is_healthy`` to flip back to HEALTHY. Without the
    clear, an old ``first_unhealthy_at`` would still gate the feed even
    after a successful cycle.
    """
    state = HealthFeedState(
        entities_count=100,
        cycles_total=5,
        ingester_running=True,
        last_error_at=time.time() - 5.0,  # recent → degraded initially
        errors_within_window=1,
        first_unhealthy_at=time.time() - 5.0,
    )
    record_success(state)

    # After success, last_error_at still points at the old error inside
    # halflife — but errors_within_window cleared and the burn anchor
    # cleared. Subsequent is_healthy runs from the snapshot, with the
    # error timestamp still present (record_success intentionally does
    # not rewrite last_error_at) — so the feed is still degraded by
    # last_error_at until enough wall-time passes.
    _, status, _ = is_healthy(state)
    assert status == StatusValue.DEGRADED  # old error still in window

    # Simulate time passing past the halflife: last_error_at now reads
    # outside the halflife. The clear of first_unhealthy_at has already
    # happened; error_within_halflife is no longer true.
    state.last_error_at = time.time() - 1000.0
    healthy, status, _ = is_healthy(state)
    assert healthy is True
    assert status == StatusValue.HEALTHY
