"""Base mixin for MCP server lifecycle management.

Provides reusable template methods for common Oneiric runtime operations:
startup/shutdown snapshots, health check building, and runtime initialization.

This mixin eliminates ~120 lines of boilerplate per server while allowing
customization through template method pattern.

Example:
    >>> from mcp_common.server import BaseOneiricServerMixin, create_runtime_components
    >>>
    >>> class MyMCPServer(BaseOneiricServerMixin):
    ...     def __init__(self, config):
    ...         self.config = config
    ...         self.runtime = create_runtime_components("my-server", ".oneiric_cache")
    >>>
    >>>     async def startup(self):
    ...         await self.runtime.initialize()
    ...         await self._create_startup_snapshot(custom_components={
    ...             "api": {"status": "connected"}
    ...         })
    >>>
    >>>     async def health_check(self):
    ...         base_components = await self._build_health_components()
    ...         # Add server-specific components
    ...         base_components.extend([...])
    ...         return self.runtime.health_monitor.create_health_response(base_components)
"""

from __future__ import annotations

import time
from typing import Any

from oneiric.runtime.mcp_health import (
    HealthStatus,
)

from mcp_common.server.runtime import create_runtime_components


class BaseOneiricServerMixin:
    """Base mixin providing reusable Oneiric lifecycle methods.

    This mixin provides template methods for common server operations while
    allowing customization through overriding. It follows the Template Method
    pattern from GoF design patterns.

    Required Attributes:
        runtime: RuntimeComponents instance (from create_runtime_components())
        config: Server configuration object (typically OneiricMCPConfig subclass)

    Template Methods (call these in your server):
        - _init_runtime_components(): Initialize runtime components
        - _create_startup_snapshot(): Create startup snapshot with custom components
        - _create_shutdown_snapshot(): Create shutdown snapshot
        - _build_health_components(): Build health check component list

    Example:
        >>> class MyServer(BaseOneiricServerMixin):
        ...     def __init__(self, config):
        ...         self.config = config
        ...         self.runtime = self._init_runtime_components("my-server")
        >>>
        ...     async def startup(self):
        ...         await self.runtime.initialize()
        ...         await self._create_startup_snapshot()
        >>>
        ...     async def shutdown(self):
        ...         await self._create_shutdown_snapshot()
        ...         await self.runtime.cleanup()
    """

    def _init_runtime_components(
        self,
        server_name: str,
        cache_dir: str | None = None,
    ) -> Any:
        """Initialize Oneiric runtime components.

        This is a convenience wrapper around create_runtime_components()
        that uses self.config.cache_dir if cache_dir is not provided.

        Args:
            server_name: Server identifier (e.g., 'my-mcp-server')
            cache_dir: Optional cache directory (defaults to config.cache_dir)

        Returns:
            RuntimeComponents instance

        Example:
            >>> class MyServer(BaseOneiricServerMixin):
            ...     def __init__(self, config):
            ...         self.config = config
            ...         self.runtime = self._init_runtime_components("my-server")
            >>>
            ...     # Or specify custom cache_dir
            ...     self.runtime = self._init_runtime_components(
            ...         "my-server",
            ...         cache_dir="/tmp/my-cache"
            ...     )
        """
        # Use config.cache_dir if cache_dir not provided
        if cache_dir is None:
            cache_dir = getattr(self.config, "cache_dir", None) or ".oneiric_cache"

        return create_runtime_components(server_name, cache_dir)

    async def _create_startup_snapshot(
        self,
        custom_components: dict[str, Any] | None = None,
    ) -> None:
        """Create a startup snapshot with standard and custom components.

        This template method creates a snapshot containing:
        - Standard server status (started, timestamp, config)
        - Any custom components provided

        Args:
            custom_components: Optional dict of additional components to include.
                Merged with standard components. Use nested dicts for organization.

        Example:
            >>> await self._create_startup_snapshot(custom_components={
            ...     "api": {
            ...         "status": "connected",
            ...         "endpoint": "https://api.example.com"
            ...     },
            ...     "cache": {
            ...         "status": "initialized",
            ...         "entries": 42
            ...     }
            ... })

        Before (20 lines):
            ```python
            components = {
                "server": {
                    "status": "started",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "config": {
                        "http_port": self.config.http_port,
                        "http_host": self.config.http_host,
                        "debug": self.config.debug,
                    },
                },
            }
            await self.snapshot_manager.create_snapshot(components)
            ```

        After (3 lines):
            ```python
            await self._create_startup_snapshot()
            # Or with custom components
            await self._create_startup_snapshot(custom_components={"api": {"status": "connected"}})
            ```
        """
        # Build standard components
        components = {
            "server": {
                "status": "started",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "config": self._extract_config_snapshot(),
            },
        }

        # Merge custom components if provided
        if custom_components:
            components.update(custom_components)

        # Create snapshot
        await self.runtime.snapshot_manager.create_snapshot(components)

    async def _create_shutdown_snapshot(self) -> None:
        """Create a shutdown snapshot.

        Creates a simple snapshot indicating the server has stopped.

        Example:
            >>> class MyServer(BaseOneiricServerMixin):
            ...     async def shutdown(self):
            ...         await self._create_shutdown_snapshot()
            ...         await self.runtime.cleanup()
        """
        components = {
            "server": {
                "status": "stopped",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        }

        await self.runtime.snapshot_manager.create_snapshot(components)

    async def _build_health_components(self) -> list[Any]:
        """Build standard health check components.

        This template method creates health components for:
        - Cache status (entries, initialized)
        - Snapshot status (current snapshot exists)

        Returns:
            List of component health objects (from health_monitor.create_component_health())

        Example:
            >>> class MyServer(BaseOneiricServerMixin):
            ...     async def health_check(self):
            ...         # Get base components
            ...         components = await self._build_health_components()
            ...
            ...         # Add server-specific components
            ...         components.append(
            ...             self.runtime.health_monitor.create_component_health(
            ...                 name="api",
            ...                 status=HealthStatus.HEALTHY,
            ...                 details={"endpoint": self.config.api_url}
            ...             )
            ...         )
            ...
            ...         # Create response
            ...         return self.runtime.health_monitor.create_health_response(components)

        Before (15 lines):
            ```python
            cache_stats = await self.cache_manager.get_cache_stats()
            components = [
                self.health_monitor.create_component_health(
                    name="cache",
                    status=HealthStatus.HEALTHY,
                    details={
                        "entries": cache_stats["total_entries"],
                        "initialized": cache_stats["initialized"],
                    },
                ),
                self.health_monitor.create_component_health(
                    name="snapshot",
                    status=HealthStatus.HEALTHY,
                    details={
                        "initialized": self.snapshot_manager.current_snapshot is not None
                    },
                ),
            ]
            return components
            ```

        After (3 lines):
            ```python
            components = await self._build_health_components()
            # Add custom components...
            return self.runtime.health_monitor.create_health_response(components)
            ```
        """
        # Get cache stats
        cache_stats = await self.runtime.cache_manager.get_cache_stats()

        # Build and return standard components
        return [
            self.runtime.health_monitor.create_component_health(
                name="cache",
                status=HealthStatus.HEALTHY,
                details={
                    "entries": cache_stats["total_entries"],
                    "initialized": cache_stats["initialized"],
                },
            ),
            self.runtime.health_monitor.create_component_health(
                name="snapshot",
                status=HealthStatus.HEALTHY,
                details={"initialized": self.runtime.snapshot_manager.current_snapshot is not None},
            ),
        ]

    def _extract_config_snapshot(self) -> dict[str, Any]:
        """Extract configuration values for snapshots.

        This method extracts common configuration fields for inclusion in
        startup snapshots. Override to add server-specific fields.

        Returns:
            Dict with config values (http_port, http_host, debug, etc.)

        Example:
            >>> def _extract_config_snapshot(self):
            ...     base = super()._extract_config_snapshot()
            ...     base["custom_field"] = self.config.custom_value
            ...     return base
        """
        config_snapshot: dict[str, Any] = {}

        # Extract common config fields if they exist
        if hasattr(self.config, "http_port"):
            config_snapshot["http_port"] = self.config.http_port
        if hasattr(self.config, "http_host"):
            config_snapshot["http_host"] = self.config.http_host
        if hasattr(self.config, "debug"):
            config_snapshot["debug"] = self.config.debug
        if hasattr(self.config, "enable_http_transport"):
            config_snapshot["enable_http_transport"] = self.config.enable_http_transport

        return config_snapshot
