"""Discovery module for cross-component agent + skill catalogs.

Per spec §4.11 — discovery is the read-side counterpart to the canonical
schemas. Consumers (e.g. ``mcp__mahavishnu__discover_tools``) call into
this module to enumerate agents/skills without depending on the source
component directly.

Refs:
- docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md §4.11
- docs/audits/2026-09-15-decomposition-final-review.md §2.1 W4
"""
from __future__ import annotations

from typing import Any


def discover_agents(*, source: str | None = None) -> list[dict[str, Any]]:
    """Return agent catalog entries.

    Currently a stub — Phase 4 wires this to the actual source catalogs
    (Crackerjack for agents/skills; Oneiric for adapters). Returns an
    empty list until the wiring lands.

    Args:
        source: optional component filter ('crackerjack', 'oneiric', etc.).
            None means all known sources.

    Returns:
        List of agent metadata dicts.
    """
    return []


def discover_skills(*, source: str | None = None) -> list[dict[str, Any]]:
    """Return skill catalog entries.

    Currently a stub — Phase 4 wires this to Crackerjack's skill
    registry. Returns an empty list until the wiring lands.

    Args:
        source: optional component filter ('crackerjack', 'oneiric', etc.).

    Returns:
        List of skill metadata dicts.
    """
    return []


__all__ = ["discover_agents", "discover_skills"]
