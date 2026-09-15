"""Canonical schema for skill metadata publication.

Phase 4 / spec §4.11 — skills from Crackerjack's registry publish a
canonical schema for downstream consumers. Skill payloads are signed
by ``mcp_common.signing.SkillsSigner`` so consumers can verify provenance.

Refs:
- docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md §4.11
- docs/audits/2026-09-15-decomposition-final-review.md §2.1 W4
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SkillCanonicalSchema(BaseModel):
    """Canonical skill metadata published across Bodai components."""

    name: str = Field(..., description="Skill name (e.g. 'crackerjack-fast-hooks')")
    version: str = Field(..., description="Semantic version of the skill")
    description: str = Field(default="", description="One-line skill description")
    tags: list[str] = Field(default_factory=list, description="Search/discovery tags")
    owner: str | None = Field(default=None, description="Owning component")
    prompt: str | None = Field(default=None, description="Optional prompt body")
    signature: str | None = Field(
        default=None,
        description="ed25519 signature produced by mcp_common.signing.SkillsSigner",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Free-form additional metadata"
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict for bus publication."""
        return self.model_dump(mode="json")


__all__ = ["SkillCanonicalSchema"]
