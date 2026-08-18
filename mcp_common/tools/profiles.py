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
from enum import StrEnum


class ToolProfile(StrEnum):
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
    def from_string(
        cls, value: str | None, default: ToolProfile | None = None
    ) -> ToolProfile:
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


# Registration_map keys guaranteed to be registered at every profile.
# Empty default — repos opt-in via `mandatory_groups={...}` when they have
# always-on groups (e.g. health/ecosystem). The helper's dispatch loop walks
# this set in `_apply_tool_profile_async` and calls `registration_map[name]`.
MANDATORY_GROUPS: set[str] = set()

# Tool names that MUST be present in the registered tool set after dispatch.
# Default is empty (repos opt-in via `essential_tool_names={...}`). Different
# repos use different naming conventions for health tools (e.g. mahavishnu
# uses `get_health`, not `health_check`), so the canonical default can't
# assume a universal name. The helper's `_apply_tool_profile_async` performs
# the subset check; pass a non-empty set to enable it.
#
# If you need a safety invariant on standard health tools, set:
#   essential_tool_names = {"get_liveness", "get_readiness", "get_health"}
# — but only IF your repo actually exposes those tool names.
MANDATORY_TOOLS: set[str] = set()
