"""Rate limiting configuration profiles and constants.

This module provides standardized rate limiting configurations for MCP servers,
eliminating magic numbers and providing clear profiles for different use cases.

Phase 3.3 M1: Centralized rate limit configuration
"""

from dataclasses import dataclass
from enum import Enum


class RateLimitProfile(str, Enum):
    """Predefined rate limiting profiles for different server types.

    Use these profiles to ensure consistent rate limiting across the MCP ecosystem:
    - CONSERVATIVE: Email/external APIs with strict limits (5 req/sec)
    - MODERATE: Standard APIs and services (10-12 req/sec)
    - AGGRESSIVE: Core infrastructure and frameworks (15 req/sec)
    """

    CONSERVATIVE = "conservative"  # Email APIs, strict rate limits
    MODERATE = "moderate"  # Standard APIs, balanced throughput
    AGGRESSIVE = "aggressive"  # Framework operations, high throughput


@dataclass(frozen=True)
class RateLimitConfig:
    """Rate limiting configuration for MCP servers.

    Attributes:
        max_requests_per_second: Sustainable request rate (refill rate)
        burst_capacity: Maximum burst requests before rate limiting kicks in
        global_limit: Whether to apply limits globally (True) or per-client (False)
        description: Human-readable description of this configuration

    Example:
        >>> config = RateLimitConfig(
        ...     max_requests_per_second=10.0,
        ...     burst_capacity=20,
        ...     global_limit=True,
        ...     description="Standard API rate limiting"
        ... )
        >>> print(f"{config.max_requests_per_second} req/sec, burst {config.burst_capacity}")
        10.0 req/sec, burst 20
    """

    max_requests_per_second: float
    burst_capacity: int
    global_limit: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.max_requests_per_second <= 0:
            msg = "max_requests_per_second must be positive"
            raise ValueError(msg)
        if self.burst_capacity < 1:
            msg = "burst_capacity must be at least 1"
            raise ValueError(msg)
        if self.burst_capacity < self.max_requests_per_second:
            msg = "burst_capacity should be >= max_requests_per_second"
            raise ValueError(msg)


# Predefined profiles for common use cases
PROFILES: dict[RateLimitProfile, RateLimitConfig] = {
    RateLimitProfile.CONSERVATIVE: RateLimitConfig(
        max_requests_per_second=5.0,
        burst_capacity=15,
        global_limit=True,
        description="Conservative rate limiting for email APIs and external services with strict limits",
    ),
    RateLimitProfile.MODERATE: RateLimitConfig(
        max_requests_per_second=10.0,
        burst_capacity=20,
        global_limit=True,
        description="Moderate rate limiting for standard APIs and services",
    ),
    RateLimitProfile.AGGRESSIVE: RateLimitConfig(
        max_requests_per_second=15.0,
        burst_capacity=40,
        global_limit=True,
        description="Aggressive rate limiting for core infrastructure and framework operations",
    ),
}


# Server-specific configurations (derived from Phase 3 implementation)
SERVER_CONFIGS: dict[str, RateLimitConfig] = {
    # Core infrastructure (aggressive profile)
    "acb": RateLimitConfig(
        max_requests_per_second=15.0,
        burst_capacity=40,
        global_limit=True,
        description="ACB framework server - high throughput for local operations",
    ),
    "fastblocks": RateLimitConfig(
        max_requests_per_second=15.0,
        burst_capacity=40,
        global_limit=True,
        description="FastBlocks framework server - inherits ACB configuration",
    ),
    # Standard APIs (moderate profile)
    "session-mgmt-mcp": RateLimitConfig(
        max_requests_per_second=12.0,
        burst_capacity=16,
        global_limit=True,
        description="Session management MCP server - balanced throughput",
    ),
    "crackerjack": RateLimitConfig(
        max_requests_per_second=12.0,
        burst_capacity=35,  # Higher burst for test/lint operations
        global_limit=True,
        description="Code quality MCP server - allows test/lint spikes",
    ),
    "opera-cloud-mcp": RateLimitConfig(
        max_requests_per_second=10.0,
        burst_capacity=20,
        global_limit=True,
        description="Opera Cloud PMS API - moderate rate limiting",
    ),
    "unifi-mcp": RateLimitConfig(
        max_requests_per_second=10.0,
        burst_capacity=20,
        global_limit=True,
        description="UniFi network controller API - moderate rate limiting",
    ),
    # External APIs with specific limits
    "raindropio-mcp": RateLimitConfig(
        max_requests_per_second=8.0,
        burst_capacity=16,
        global_limit=True,
        description="Raindrop.io API - respects API rate limits",
    ),
    "mailgun-mcp": RateLimitConfig(
        max_requests_per_second=5.0,
        burst_capacity=15,
        global_limit=True,
        description="Mailgun email API - conservative rate limiting",
    ),
    # Optional rate limiting
    "excalidraw-mcp": RateLimitConfig(
        max_requests_per_second=12.0,
        burst_capacity=16,
        global_limit=True,
        description="Excalidraw canvas management - optional rate limiting",
    ),
}


def get_config_for_server(server_name: str) -> RateLimitConfig:
    """Get rate limit configuration for a specific server.

    Args:
        server_name: Name of the MCP server (e.g., "acb", "mailgun-mcp")

    Returns:
        RateLimitConfig for the specified server

    Raises:
        KeyError: If server_name is not in SERVER_CONFIGS

    Example:
        >>> config = get_config_for_server("acb")
        >>> print(config.max_requests_per_second)
        15.0
    """
    return SERVER_CONFIGS[server_name]


def get_profile_config(profile: RateLimitProfile) -> RateLimitConfig:
    """Get rate limit configuration for a predefined profile.

    Args:
        profile: RateLimitProfile enum value

    Returns:
        RateLimitConfig for the specified profile

    Example:
        >>> config = get_profile_config(RateLimitProfile.MODERATE)
        >>> print(config.description)
        Moderate rate limiting for standard APIs and services
    """
    return PROFILES[profile]


def create_custom_config(
    max_requests_per_second: float,
    burst_capacity: int,
    *,
    global_limit: bool = True,
    description: str = "",
) -> RateLimitConfig:
    """Create a custom rate limit configuration.

    Args:
        max_requests_per_second: Sustainable request rate
        burst_capacity: Maximum burst requests
        global_limit: Apply limits globally (default: True)
        description: Human-readable description

    Returns:
        Validated RateLimitConfig

    Raises:
        ValueError: If configuration values are invalid

    Example:
        >>> config = create_custom_config(
        ...     max_requests_per_second=20.0,
        ...     burst_capacity=50,
        ...     description="Custom high-throughput config"
        ... )
    """
    return RateLimitConfig(
        max_requests_per_second=max_requests_per_second,
        burst_capacity=burst_capacity,
        global_limit=global_limit,
        description=description,
    )
