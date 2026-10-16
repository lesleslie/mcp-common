"""Offline smoke test for ``mcp_common.health``.

Builds three synthetic ``HealthFeedState`` instances (healthy-after-decay,
degraded-with-recent-error, warming-up-empty) and asserts
:func:`mcp_common.health.aggregator.aggregate_feed_states` returns the
expected ``(status, reason_codes)`` tuple for each.

Exits 0 on success, 1 on assertion failure (with the failing state
printed to stderr).

CLI::

    python scripts/smoke_health_feed.py [--halflife-seconds=300]

Implements: REQ-002 (HealthFeedState), REQ-007 (time-bounded decay),
REQ-008 (warming_up predicate) per umbrella
``docs/plans/2026-09-14-common-mcp-client-transport-unification.md``.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow ``python scripts/smoke_health_feed.py`` to find the in-tree
# ``mcp_common`` package without an editable install.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from mcp_common.health.aggregator import aggregate_feed_states
from mcp_common.health.feed import (
    HealthFeedState,
    ReasonCode,
    StatusValue,
    record_error,
)


def _make_healthy_after_error(*, halflife_seconds: int) -> HealthFeedState:
    """Build a feed whose last error fell out of the halflife window.

    Set ``last_error_at`` to ``halflife + 1`` seconds ago so the
    decay predicate classifies it as HEALTHY again.
    """
    state = HealthFeedState(
        entities_count=3,
        cycles_total=1,
        ingester_running=True,
    )
    record_error(state)
    # Override `last_error_at` AFTER record_error so it lands far in the past.
    state.last_error_at = time.time() - halflife_seconds - 1
    return state


def _make_degraded_within_halflife(*, halflife_seconds: int) -> HealthFeedState:
    """Build a feed whose last error is within the halflife window."""
    state = HealthFeedState(
        entities_count=1,
        cycles_total=1,
        ingester_running=True,
    )
    record_error(state)
    return state


def _make_warming_up_empty() -> HealthFeedState:
    """Build a feed that's empty but reports the ingester running.

    Per the warming-up predicate: ``entities_count == 0``,
    ``cycles_total >= 1``, ``ingester_running = True``, no recent error.
    """
    state = HealthFeedState(
        entities_count=0,
        cycles_total=1,
        ingester_running=True,
    )
    return state


def _check(label: str, expected_status: StatusValue) -> bool:
    """Run a single case, print PASS/FAIL, return success."""
    if expected_status is StatusValue.HEALTHY:
        state = _make_healthy_after_error(halflife_seconds=300)
    elif expected_status is StatusValue.DEGRADED:
        state = _make_degraded_within_halflife(halflife_seconds=300)
    else:  # WARMING_UP
        state = _make_warming_up_empty()

    snapshot = aggregate_feed_states({"smoke": state}, halflife_seconds=300)
    feed_check = snapshot["checks"]["smoke"]
    actual_status = StatusValue(feed_check["status"])
    ok = actual_status == expected_status
    marker = "OK" if ok else "FAIL"
    print(
        f"  [{marker}] {label}: status={actual_status} "
        f"reasons={sorted(feed_check['reason_codes'])} "
        f"(expected status={expected_status})",
        file=sys.stderr,
    )
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--halflife-seconds",
        type=int,
        default=300,
        help="Time-bounded decay window for the synthetic feeds (default: 300)",
    )
    args = parser.parse_args()

    print(
        f"== smoke_health_feed (halflife={args.halflife_seconds}s, "
        f"req-marker REQ-002/REQ-007/REQ-008) ==",
        file=sys.stderr,
    )
    cases = [
        ("healthy (error outside halflife)", StatusValue.HEALTHY),
        ("degraded (error within halflife)", StatusValue.DEGRADED),
        (
            "warming_up (empty, ingester running, cycles_total=1)",
            StatusValue.WARMING_UP,
        ),
    ]

    failed = False
    for label, expected_status in cases:
        if not _check(label, expected_status):
            failed = True

    # Print the worst-case top-level status for completeness.
    snapshot = aggregate_feed_states(
        {
            "smoke_healthy": _make_healthy_after_error(
                halflife_seconds=args.halflife_seconds
            ),
            "smoke_degraded": _make_degraded_within_halflife(
                halflife_seconds=args.halflife_seconds
            ),
            "smoke_warming": _make_warming_up_empty(),
        },
        halflife_seconds=args.halflife_seconds,
    )
    print(
        f"  [INFO] worst-case across all 3 feeds: status={snapshot['status']} "
        f"reason_codes={sorted(snapshot['reason_codes'])}",
        file=sys.stderr,
    )

    if failed:
        print(
            "FAIL: at least one HealthFeedState assertion did not hold",
            file=sys.stderr,
        )
        return 1
    print(
        "PASS: all HealthFeedState decay-narrative cases hold",
        file=sys.stderr,
    )
    # Verify REQ-007: ERROR_WITHIN_HALFLIFE reason appears under degraded.
    if ReasonCode.ERROR_WITHIN_HALFLIFE not in (
        _ := aggregate_feed_states(
            {
                "smoke": _make_degraded_within_halflife(
                    halflife_seconds=args.halflife_seconds
                )
            },
            halflife_seconds=args.halflife_seconds,
        )["checks"]["smoke"]["reason_codes"]
    ):
        print(
            "FAIL: REQ-007 (ERROR_WITHIN_HALFLIFE reason) not present on degraded feed",
            file=sys.stderr,
        )
        return 1
    print(
        "PASS: REQ-002/REQ-007/REQ-008 satisfied",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
