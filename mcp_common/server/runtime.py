"""Runtime component factory for MCP servers.

Provides centralized initialization and lifecycle management for Oneiric
runtime components (snapshot manager, cache manager, health monitor).

This factory eliminates ~30 lines of boilerplate per server.

Example:
    >>> from mcp_common.server import create_runtime_components
    >>>
    >>> # Initialize all runtime components in one call
    >>> runtime = create_runtime_components("my-server", ".oneiric_cache")
    >>>
    >>> # Use the components
    >>> await runtime.initialize()
    >>> await runtime.snapshot_manager.create_snapshot({"status": "started"})
    >>>
    >>> # Cleanup on shutdown
    >>> await runtime.cleanup()
"""

from __future__ import annotations

from dataclasses import dataclass

from oneiric.runtime.cache import RuntimeCacheManager
from oneiric.runtime.mcp_health import HealthMonitor
from oneiric.runtime.snapshot import RuntimeSnapshotManager


@dataclass
class RuntimeComponents:
    """Container for Oneiric runtime components.

    Attributes:
        server_name: Server identifier for logging and monitoring
        cache_dir: Directory for runtime data (snapshots, cache)
        snapshot_manager: Manages runtime state snapshots
        cache_manager: Manages cached data with TTL
        health_monitor: Tracks component health status

    Example:
        >>> runtime = create_runtime_components("my-server", ".oneiric_cache")
        >>> print(runtime.server_name)
        'my-server'
        >>> await runtime.initialize()
    """

    server_name: str
    cache_dir: str
    snapshot_manager: RuntimeSnapshotManager
    cache_manager: RuntimeCacheManager
    health_monitor: HealthMonitor

    async def initialize(self) -> None:
        """Initialize all runtime components.

        This method must be called before using any of the components.

        Example:
            >>> runtime = create_runtime_components("my-server", ".oneiric_cache")
            >>> await runtime.initialize()
        """
        await self.snapshot_manager.initialize()
        await self.cache_manager.initialize()

    async def cleanup(self) -> None:
        """Cleanup all runtime components.

        Call this during server shutdown to release resources.

        Example:
            >>> try:
            ...     await server.run()
            ... finally:
            ...     await runtime.cleanup()
        """
        await self.snapshot_manager.cleanup()
        await self.cache_manager.cleanup()


def create_runtime_components(
    server_name: str,
    cache_dir: str,
) -> RuntimeComponents:
    """Factory function to create initialized runtime components.

    This eliminates ~30 lines of boilerplate code per server.

    Args:
        server_name: Server identifier (e.g., 'raindropio-mcp', 'mailgun-mcp')
            Used for logging, monitoring, and cache organization.
        cache_dir: Directory for runtime data storage
            Defaults to '.oneiric_cache' in most servers.

    Returns:
        RuntimeComponents container with initialized (but not started) components.

        Call `await runtime.initialize()` before using the components.

    Example:
        >>> from mcp_common.server import create_runtime_components
        >>>
        >>> class MyServer:
        ...     def __init__(self, config):
        ...         self.runtime = create_runtime_components(
        ...             server_name="my-server",
        ...             cache_dir=".oneiric_cache"
        ...         )
        >>>
        ...     async def startup(self):
        ...         await self.runtime.initialize()
        ...         # Server is ready
        >>>
        ...     async def shutdown(self):
        ...         await self.runtime.cleanup()
        ...         # Resources released

    Before (30 lines):
        ```python
        self.snapshot_manager = RuntimeSnapshotManager(
            cache_dir=".oneiric_cache",
            server_name="my-server",
        )
        self.cache_manager = RuntimeCacheManager(
            cache_dir=".oneiric_cache",
            server_name="my-server",
        )
        self.health_monitor = HealthMonitor(server_name="my-server")

        await self.snapshot_manager.initialize()
        await self.cache_manager.initialize()
        ```

    After (3 lines):
        ```python
        self.runtime = create_runtime_components("my-server", ".oneiric_cache")
        await self.runtime.initialize()
        ```
    """
    # Create snapshot manager
    snapshot_manager = RuntimeSnapshotManager(
        cache_dir=cache_dir,
        server_name=server_name,
    )

    # Create cache manager
    cache_manager = RuntimeCacheManager(
        cache_dir=cache_dir,
        server_name=server_name,
    )

    # Create health monitor
    health_monitor = HealthMonitor(server_name=server_name)

    # Return container
    return RuntimeComponents(
        server_name=server_name,
        cache_dir=cache_dir,
        snapshot_manager=snapshot_manager,
        cache_manager=cache_manager,
        health_monitor=health_monitor,
    )
