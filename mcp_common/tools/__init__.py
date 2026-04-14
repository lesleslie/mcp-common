"""Tool management utilities for MCP servers.

Provides description trimming and tool profile selection for reducing
MCP context consumption.

Usage:
    >>> from mcp_common.tools import ToolProfile, trim_description
    >>>
    >>> # Trim a verbose docstring for tool registration
    >>> short = trim_description(long_docstring, max_length=200)
    >>>
    >>> # Select a profile from environment/config
    >>> profile = ToolProfile.from_string("standard")
"""

from __future__ import annotations

from mcp_common.tools.descriptions import trim_description
from mcp_common.tools.profiles import MANDATORY_TOOLS, ToolProfile

__all__ = [
    "MANDATORY_TOOLS",
    "ToolProfile",
    "trim_description",
]
