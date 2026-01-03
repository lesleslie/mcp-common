"""Optional dependency availability check helpers.

Provides centralized utilities for detecting optional dependencies like
ServerPanels, security utilities, and rate limiting middleware. These
checks are cached to avoid repeated import attempts.

Usage:
    >>> from mcp_common.server import check_serverpanels_available
    >>>
    >>> if check_serverpanels_available():
    ...     from mcp_common.ui import ServerPanels
    ...     ServerPanels.startup_success(...)
"""

from __future__ import annotations

import importlib.util
from functools import lru_cache

# Module paths for optional dependencies
_SERVERPANELS_MODULE = "mcp_common.ui"
_SECURITY_MODULE = "mcp_common.security"
_RATE_LIMITING_MODULE = "fastmcp.server.middleware.rate_limiting"


@lru_cache(maxsize=1)
def check_serverpanels_available() -> bool:
    """Check if ServerPanels (Rich UI) is available.

    Returns:
        True if mcp_common.ui can be imported, False otherwise.

    Example:
        >>> from mcp_common.server import check_serverpanels_available
        >>>
        >>> if check_serverpanels_available():
        ...     from mcp_common.ui import ServerPanels
        ...     ServerPanels.startup_success("my-server", ["Feature 1", "Feature 2"])
    """
    return importlib.util.find_spec(_SERVERPANELS_MODULE) is not None


@lru_cache(maxsize=1)
def check_security_available() -> bool:
    """Check if mcp_common.security utilities are available.

    Returns:
        True if mcp_common.security can be imported, False otherwise.

    Example:
        >>> from mcp_common.server import check_security_available
        >>>
        >>> if check_security_available():
        ...     from mcp_common.security import sanitize_user_input
        ...     clean_input = sanitize_user_input(user_data)
    """
    return importlib.util.find_spec(_SECURITY_MODULE) is not None


@lru_cache(maxsize=1)
def check_rate_limiting_available() -> bool:
    """Check if FastMCP rate limiting middleware is available.

    Returns:
        True if fastmcp.server.middleware.rate_limiting can be imported,
        False otherwise.

    Example:
        >>> from mcp_common.server import check_rate_limiting_available
        >>>
        >>> if check_rate_limiting_available():
        ...     from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
        ...     rate_limiter = RateLimitingMiddleware(max_requests_per_second=10.0)
    """
    return importlib.util.find_spec(_RATE_LIMITING_MODULE) is not None


@lru_cache(maxsize=1)
def get_availability_status() -> dict[str, bool]:
    """Get status of all optional dependencies.

    Returns:
        Dictionary mapping dependency names to availability status.

        Keys:
            - "serverpanels": ServerPanels availability
            - "security": Security utilities availability
            - "rate_limiting": Rate limiting middleware availability

    Example:
        >>> from mcp_common.server import get_availability_status
        >>>
        >>> status = get_availability_status()
        >>> if status["serverpanels"]:
        ...     print("Rich UI panels available")
    """
    return {
        "serverpanels": check_serverpanels_available(),
        "security": check_security_available(),
        "rate_limiting": check_rate_limiting_available(),
    }
