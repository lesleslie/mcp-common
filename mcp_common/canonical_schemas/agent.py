"""Canonical schema for agent metadata publication.

Phase 4 / spec §4.11 — agents from Crackerjack's registry publish a
canonical schema for downstream consumers (Oneiric's MCP server,
Mahavishnu's tool picker). This module owns the schema so the contract
is enforced at the substrate boundary, not duplicated per consumer.

Refs:
- docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md §4.11
- docs/audits/2026-09-15-decomposition-final-review.md §2.1 W4
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentCanonicalSchema(BaseModel):
    """Canonical agent metadata published across Bodai components."""

    name: str = Field(..., description="Agent name (e.g. 'mahavishnu-orchestrator')")
    version: str = Field(..., description="Semantic version of the agent")
    description: str = Field(default="", description="One-line agent description")
    capabilities: list[str] = Field(
        default_factory=list,
        description="List of capabilities the agent advertises",
    )
    owner: str | None = Field(
        default=None, description="Owning component (mahavishnu, akosha, ...)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Free-form additional metadata"
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict for bus publication."""
        return self.model_dump(mode="json")


__all__ = ["AgentCanonicalSchema"]
