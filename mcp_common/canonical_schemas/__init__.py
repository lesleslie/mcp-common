"""Canonical schemas for cross-component agent + skill publication.

Per docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md
§4.11 — canonical schemas live with mcp-common so multiple components
(Mahavishnu, Crackerjack, Oneiric) consume them without cross-component
imports.

Phase 10 task 4 extended the canonical schemas with the full installer
field set and exposed shared validators/helpers so the four local
agent_schema.py / skill_schema.py files can become thin re-exports
(`from mcp_common.canonical_schemas.agent import AgentCanonicalSchema as AgentMetadata`).

Refs:
- docs/audits/2026-09-15-decomposition-final-review.md §2.1 W4
- docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md §4.11
"""

from __future__ import annotations

from ._validators import (
    NAME_OR_SERVER_RE,
    allowlisted_name,
    build_agent_id,
    coerce_tools_value,
    compute_content_hash,
)
from .agent import AgentCanonicalSchema
from .skill import SkillCanonicalSchema

__all__ = [
    "AgentCanonicalSchema",
    "SkillCanonicalSchema",
    "NAME_OR_SERVER_RE",
    "allowlisted_name",
    "build_agent_id",
    "compute_content_hash",
    "coerce_tools_value",
]
