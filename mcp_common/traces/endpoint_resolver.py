"""Per-component DuckDB trace path resolver.

Per Phase 5 / spec §5 — each Bodai component writes its OTel traces
to a per-component DuckDB file. The default path convention is
``/Users/les/.local/share/<component>/traces.duckdb``. Operators can
override via env vars (``MAHAVISHNU_TRACES_PATH``, ``AKOSHA_TRACES_PATH``,
``CRACKERJACK_TRACES_PATH``, ``SESSION_BUDDY_TRACES_PATH``,
``DHARA_TRACES_PATH``).

Refs:
- docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md §5 Phase 5
- docs/audits/2026-09-15-decomposition-final-review.md §2.1 W4
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Default base directory per spec §5 Phase 5 task 3.
_DEFAULT_BASE = Path("/Users/les/.local/share")

# Map of component → env-var override name.
_COMPONENT_ENV: dict[str, str] = {
    "mahavishnu": "MAHAVISHNU_TRACES_PATH",
    "akosha": "AKOSHA_TRACES_PATH",
    "crackerjack": "CRACKERJACK_TRACES_PATH",
    "session_buddy": "SESSION_BUDDY_TRACES_PATH",
    "dhara": "DHARA_TRACES_PATH",
}


@dataclass(frozen=True)
class TraceEndpoint:
    """Resolved per-component DuckDB trace endpoint."""

    component: str
    path: Path
    exists: bool


class EndpointResolver:
    """Resolves per-component trace DuckDB paths from env vars + defaults."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base = base_dir or _DEFAULT_BASE

    def resolve(self, component: str) -> TraceEndpoint:
        """Return the trace endpoint for ``component``.

        Precedence: env var override → ``<base>/<component>/traces.duckdb`` default.
        """
        env_var = _COMPONENT_ENV.get(component)
        if env_var and (override := os.environ.get(env_var)):
            path = Path(override)
        else:
            path = self._base / component / "traces.duckdb"
        return TraceEndpoint(component=component, path=path, exists=path.exists())

    def resolve_all(self) -> list[TraceEndpoint]:
        """Return all known component endpoints."""
        return [self.resolve(c) for c in _COMPONENT_ENV]


__all__ = ["EndpointResolver", "TraceEndpoint"]
