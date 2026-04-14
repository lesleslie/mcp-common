"""Tool profile system for MCP servers.

Controls which register_*() functions are called at startup, reducing
the number of tools exposed to Claude and saving context tokens.

Profiles:
    MINIMAL:  ~10 tools — health, status, basic operations
    STANDARD: ~30 tools — core workflow tools for daily development
    FULL:     All tools — current behavior, no reduction

Configuration (precedence order):
    1. Environment variable: {SERVER_NAME}_TOOL_PROFILE=standard
    2. settings/local.yaml:  tool_profile: standard
    3. settings/{server}.yaml: tool_profile: full (default)

Security:
    MANDATORY_TOOLS are always registered regardless of profile.
    These include infrastructure-critical endpoints used by
    Kubernetes probes, load balancers, and health monitoring.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import ClassVar


class ToolProfile(str, Enum):
    """Tool registration profile level.

    Ordering: MINIMAL < STANDARD < FULL
    Servers can use comparison: `if profile >= ToolProfile.STANDARD:`
    """

    MINIMAL = "minimal"
    STANDARD = "standard"
    FULL = "full"

    def __ge__(self, other: object) -> bool:
        """Support comparison for profile gating."""
        if not isinstance(other, ToolProfile):
            return NotImplemented
        order = {ToolProfile.MINIMAL: 0, ToolProfile.STANDARD: 1, ToolProfile.FULL: 2}
        return order[self] >= order[other]

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, ToolProfile):
            return NotImplemented
        order = {ToolProfile.MINIMAL: 0, ToolProfile.STANDARD: 1, ToolProfile.FULL: 2}
        return order[self] > order[other]

    def __le__(self, other: object) -> bool:
        if not isinstance(other, ToolProfile):
            return NotImplemented
        return not self.__gt__(other)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ToolProfile):
            return NotImplemented
        return not self.__ge__(other)

    @classmethod
    def from_string(cls, value: str | None, default: ToolProfile | None = None) -> ToolProfile:
        """Parse profile from string with safe fallback.

        Args:
            value: Profile name string (case-insensitive).
            default: Fallback profile if value is invalid. Defaults to FULL.

        Returns:
            Matching ToolProfile or default.
        """
        if default is None:
            default = ToolProfile.FULL

        if not value:
            return default

        try:
            return cls(value.lower().strip())
        except ValueError:
            return default

    @classmethod
    def from_env(cls, env_var: str, default: ToolProfile | None = None) -> ToolProfile:
        """Read profile from environment variable with safe fallback.

        Args:
            env_var: Environment variable name (e.g., "MAHAVISHNU_TOOL_PROFILE").
            default: Fallback profile. Defaults to FULL.

        Returns:
            ToolProfile from env var, or default.
        """
        return cls.from_string(os.getenv(env_var), default)


# Tools that MUST be registered in every profile.
# These are required by infrastructure (K8s probes, load balancers, monitoring).
MANDATORY_TOOLS: ClassVar[set[str]] = {
    "get_liveness",
    "get_readiness",
    "health_check",
    "health_check_all",
}
