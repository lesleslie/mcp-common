"""Health-check tools shared across Bodai MCP servers.

Per spec §4.8 + mcp-backend-wiring-discipline.md — every Bodai MCP
server's ``/health`` aggregates per-feed state. ``health_tools.py``
exposes helpers that tools call to register their feeds and to format
the aggregate health response.

Refs:
- docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md §4.8
- .claude/decisions/mcp-backend-wiring-discipline.md
- docs/audits/2026-09-15-decomposition-final-review.md §2.1 W4
"""
from __future__ import annotations

from typing import Any


def register_feed(server: Any, feed_name: str) -> Any:
    """Register a ComponentHealth feed on ``server``.

    Currently a stub — Phase 1 wires this to Oneiric's HealthMonitor
    / Mahavishnu's HealthMonitor. Returns ``None`` until wiring lands.
    """
    return None


def aggregate_health(server: Any) -> dict[str, Any]:
    """Aggregate per-feed health for the ``/health`` response.

    Currently a stub. Returns ``{"status": "UNKNOWN", "feeds": {}}``
    until wiring lands.
    """
    return {"status": "UNKNOWN", "feeds": {}}


__all__ = ["register_feed", "aggregate_health"]
