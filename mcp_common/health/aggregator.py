"""Aggregate per-feed health states into a single worst-case snapshot.

The aggregator is purely functional: it consumes ``HealthFeedState`` dicts
and emits a JSON-serialisable mapping. Aggregating is a pure read of
producer state; producers never read from the aggregator.

Worst-case roll-up severity: ``failed > degraded > warming_up > healthy``.
The aggregator's top-level ``status`` is the maximum severity across all
feeds; its ``reason_codes`` are inherited from the worst feed (with
union-on-tie so multiple feeds at the same severity contribute all codes).
"""

from __future__ import annotations

from mcp_common.health.feed import (
    HealthFeedState,
    ReasonCode,
    StatusValue,
    is_healthy,
)


def aggregate_feed_states(
    states: dict[str, HealthFeedState],
    halflife_seconds: float = 300,
) -> dict[str, object]:
    """Roll up per-feed health into a single snapshot.

    Returns::

        {
            "status": StatusValue,             # worst across all feeds
            "checks": {feed_name: {            # per-feed detail
                "status": StatusValue,
                "reason_codes": list[ReasonCode],
            }},
            "reason_codes": list[ReasonCode],   # codes from worst feed(s)
        }

    Args:
        states: Mapping from feed name (e.g. ``"local_traces"``) to its
            :class:`~mcp_common.health.feed.HealthFeedState` snapshot.
        halflife_seconds: Forwarded to
            :func:`~mcp_common.health.feed.is_healthy` for each feed.
            Default matches ``HEALTH_FEED_HALFLIFE_SECONDS`` in the
            Phase 4 wiring plan; Phase 4 may override per-environment.

    Returns:
        A JSON-serialisable dict. ``status`` is the worst severity seen;
        ``checks`` retains every input feed (sparse dict is OK — feeds with
        no data still appear because empty inputs signal broken producers);
        ``reason_codes`` carries the worst feed's reasons (or a deduped
        union when multiple feeds tie at the worst severity).
    """
    checks: dict[str, dict[str, object]] = {}
    worst_status: StatusValue = StatusValue.HEALTHY
    worst_reasons: list[ReasonCode] = []

    for feed_name, state in states.items():
        healthy, status, codes = is_healthy(state, halflife_seconds)
        checks[feed_name] = {
            "status": status,
            "healthy": healthy,
            "reason_codes": list(codes),
        }

        if status > worst_status:
            worst_status = status
            worst_reasons = list(codes)
        elif status == worst_status and codes:
            # Tie at worst: include each unique code once (preserve order).
            for code in codes:
                if code not in worst_reasons:
                    worst_reasons.append(code)

    return {
        "status": worst_status,
        "checks": checks,
        "reason_codes": worst_reasons,
    }


__all__ = ["aggregate_feed_states"]
