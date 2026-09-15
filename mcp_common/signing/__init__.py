"""Ed25519 signing utilities for skill publication.

Per spec §4.11 — skills published by Crackerjack are signed so consumers
(Oneiric's MCP server, downstream agents) can verify provenance. The
signer lives with mcp-common so the cryptographic contract is owned
centrally rather than duplicated per consumer.

Refs:
- docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md §4.11
- docs/audits/2026-09-15-decomposition-final-review.md §2.1 W4
"""

from __future__ import annotations

from .skills_signer import SkillsSigner

__all__ = ["SkillsSigner"]
