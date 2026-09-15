"""Cross-component trace endpoint resolution.

Per Phase 5 / spec §5 — each Bodai component's OTel traces live in a
per-component DuckDB file. ``EndpointResolver`` resolves those file
paths from environment variables (with optional settings overrides),
so the fitness analyzer (and other cross-component trace consumers)
don't hardcode paths.

Refs:
- docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md §5 Phase 5
- docs/audits/2026-09-15-decomposition-final-review.md §2.1 W4
"""

from __future__ import annotations

from .endpoint_resolver import EndpointResolver, TraceEndpoint

__all__ = ["EndpointResolver", "TraceEndpoint"]
