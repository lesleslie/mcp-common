"""MCP middleware utilities and configurations.

This module provides middleware components for MCP servers, including:
- Rate limiting configuration (profiles, constants, server configs)
"""

from .rate_limit_config import (
    PROFILES,
    SERVER_CONFIGS,
    RateLimitConfig,
    RateLimitProfile,
    create_custom_config,
    get_config_for_server,
    get_profile_config,
)

__all__ = [
    "RateLimitProfile",
    "RateLimitConfig",
    "PROFILES",
    "SERVER_CONFIGS",
    "get_config_for_server",
    "get_profile_config",
    "create_custom_config",
]
