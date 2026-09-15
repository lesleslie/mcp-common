"""Canonical schemas for cross-component agent + skill publication.

Per docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md
§4.11 — canonical schemas live with mcp-common so multiple components
(Mahavishnu, Crackerjack, Oneiric) consume them without cross-component
imports.

Refs:
- docs/audits/2026-09-15-decomposition-final-review.md §2.1 W4
- docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md §4.11
"""

from __future__ import annotations

from .agent import AgentCanonicalSchema
from .skill import SkillCanonicalSchema

__all__ = ["AgentCanonicalSchema", "SkillCanonicalSchema"]
