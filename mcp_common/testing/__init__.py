"""Test helpers for Bodai core consumers.

Re-exports the cross-server MCP surface helpers from
:meth:`mcp_common.testing.baseline_surface` so consumers can write::

    from mcp_common.testing import assert_baseline_surface
"""

from __future__ import annotations

from mcp_common.testing.baseline_surface import (
    BaselineSurfaceError,
    assert_baseline_surface,
)

__all__ = ["BaselineSurfaceError", "assert_baseline_surface"]
