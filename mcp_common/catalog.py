"""Catalog module for cross-component capability descriptors.

Per spec §4.11 — the catalog is the searchable index of capabilities
exposed by all Bodai components. Used by ``mcp__mahavishnu__discover_tools``
and similar tools to surface capability descriptors to Claude.

Refs:
- docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md §4.11
- docs/audits/2026-09-15-decomposition-final-review.md §2.1 W4
"""

from __future__ import annotations

from typing import Any


def catalog(
    query: str, *, component: str | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    """Search the cross-component capability catalog.

    Currently a stub — Phase 4 wires this to Oneiric's adapter catalog
    and Crackerjack's agent/skill catalog. Returns an empty list until
    the wiring lands.

    Args:
        query: free-text search query.
        component: optional component filter.
        limit: maximum number of results.

    Returns:
        List of capability descriptor dicts (name, description, source).
    """
    return []


def list_capabilities(*, component: str | None = None) -> list[str]:
    """List capability names known to the catalog.

    Currently a stub. Returns an empty list until wiring lands.
    """
    return []


__all__ = ["catalog", "list_capabilities"]
