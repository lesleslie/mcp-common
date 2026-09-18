"""Canonical schemas for cross-component agent + skill publication.

Per docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md
§4.11 — canonical schemas live with mcp-common so multiple components
(Mahavishnu, Crackerjack, Oneiric) consume them without cross-component
imports.

Wire-shape contract
-------------------

The canonical ``AgentCanonicalSchema`` and ``SkillCanonicalSchema``
classes are the canonical **wire shape** for the bus-publication
envelope. Federation clients (Mahavishnu's tool picker, Akosha's
knowledge graph, Dhara's curator) consume this 6/8-field bus surface.

Per-repo schemas (akosha, mahavishnu, session-buddy, crackerjack) may
extend the canonical schema with installer / Pydantic fields (``id``,
``server_key``, ``system_prompt``, ``content_hash``, ``signature``,
etc.) and per-repo validators. The extension is intentional — each
repo's installer-layer invariants differ.

To bridge the two, use :func:`to_agent_envelope` and
:func:`to_skill_envelope` to extract the 6/8-field bus envelope from
any per-repo schema instance. These helpers tolerate arbitrary field
extensions: they read fields by attribute access, defaulting to
``""`` / ``None`` / empty list / empty dict when the attribute is
absent. Federation clients should use the envelope helpers — never
the per-repo subclasses — when comparing wire shapes across
components.

Refs:
- docs/audits/2026-09-15-decomposition-final-review.md §2.1 W4
- docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md §4.11
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ._validators import (
    NAME_OR_SERVER_RE,
    allowlisted_name,
    build_agent_id,
    coerce_tools_value,
    compute_content_hash,
)
from .agent import AgentCanonicalSchema
from .skill import SkillCanonicalSchema


def to_agent_envelope(model: BaseModel | Any) -> AgentCanonicalSchema:
    """Extract the 6-field bus envelope from any agent metadata model.

    Federation clients use this to normalize per-repo
    ``AgentMetadata`` variants (subclasses, pre-migration local
    classes, plain dicts) into the canonical bus surface for
    cross-component comparison.

    Reads attributes defensively: missing fields fall back to the
    canonical schema's documented defaults (``version="0.0.0"``,
    ``description=""``, ``capabilities=[]``, ``owner=None``,
    ``metadata={}``). Per-repo validators on the source model are
    not invoked — only attribute access — so this helper is safe to
    call on models that would otherwise reject empty descriptions or
    other strict contracts.

    The returned ``AgentCanonicalSchema`` is freshly constructed so
    the helper has no side effects on the input.
    """
    return AgentCanonicalSchema(
        name=getattr(model, "name", "") or "",
        version=getattr(model, "version", "0.0.0") or "0.0.0",
        description=getattr(model, "description", "") or "",
        capabilities=list(getattr(model, "capabilities", []) or []),
        owner=getattr(model, "owner", None),
        metadata=dict(getattr(model, "metadata", {}) or {}),
    )


def to_skill_envelope(model: BaseModel | Any) -> SkillCanonicalSchema:
    """Extract the 8-field bus envelope from any skill metadata model.

    Mirror of :func:`to_agent_envelope` for ``SkillMetadata``
    variants. Reads ``name``, ``version``, ``description``, ``tags``,
    ``owner``, ``prompt``, ``signature``, and ``metadata`` by
    attribute access; missing fields fall back to canonical defaults.
    """
    return SkillCanonicalSchema(
        name=getattr(model, "name", "") or "",
        version=getattr(model, "version", "") or "",
        description=getattr(model, "description", "") or "",
        tags=list(getattr(model, "tags", []) or []),
        owner=getattr(model, "owner", None),
        prompt=getattr(model, "prompt", None),
        signature=getattr(model, "signature", None),
        metadata=dict(getattr(model, "metadata", {}) or {}),
    )


__all__ = [
    "NAME_OR_SERVER_RE",
    "AgentCanonicalSchema",
    "SkillCanonicalSchema",
    "allowlisted_name",
    "build_agent_id",
    "coerce_tools_value",
    "compute_content_hash",
    "to_agent_envelope",
    "to_skill_envelope",
]
