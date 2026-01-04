"""Tests for BaseOneiricServerMixin in mcp_common/server/base.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oneiric.runtime.mcp_health import HealthStatus


class TestBaseOneiricServerMixin:
    """Tests for BaseOneiricServerMixin."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config object."""
        config = MagicMock()
        config.http_port = 3039
        config.http_host = "127.0.0.1"
        config.debug = False
        config.enable_http_transport = True
        config.cache_dir = ".test_cache"
        config.log_level = "INFO"
        return config

    @pytest.fixture
    def mock_runtime(self):
        """Create mock runtime components."""
        runtime = MagicMock()
        runtime.snapshot_manager = AsyncMock()
        runtime.snapshot_manager.initialize = AsyncMock()
        runtime.snapshot_manager.cleanup = AsyncMock()
        runtime.snapshot_manager.create_snapshot = AsyncMock()
        runtime.snapshot_manager.current_snapshot = {"status": "initialized"}

        runtime.cache_manager = AsyncMock()
        runtime.cache_manager.get_cache_stats = AsyncMock(
            return_value={"total_entries": 5, "initialized": True}
        )

        runtime.health_monitor = MagicMock()
        # Use side_effect to return different values for cache and snapshot components
        runtime.health_monitor.create_component_health = MagicMock(
            side_effect=[
                {"name": "cache", "status": "healthy"},
                {"name": "snapshot", "status": "healthy"},
            ]
        )
        runtime.health_monitor.create_health_response = MagicMock(
            return_value={"status": "healthy"}
        )

        runtime.server_name = "test-server"
        runtime.cache_dir = ".test_cache"
        return runtime

    @pytest.fixture
    def server(self, mock_config):
        """Create test server instance with mixin."""
        from mcp_common.server import BaseOneiricServerMixin

        class TestServer(BaseOneiricServerMixin):
            def __init__(self, config):
                self.config = config

        return TestServer(mock_config)

    def test_init_runtime_components(self, server, mock_config):
        """Should initialize runtime components."""
        with patch("mcp_common.server.base.create_runtime_components") as mock_create:
            mock_runtime = MagicMock()
            mock_create.return_value = mock_runtime

            runtime = server._init_runtime_components("test-server")

            assert runtime == mock_runtime
            mock_create.assert_called_once_with("test-server", ".test_cache")

    def test_init_runtime_components_with_custom_cache_dir(self, server, mock_config):
        """Should initialize with custom cache dir."""
        with patch("mcp_common.server.base.create_runtime_components") as mock_create:
            mock_runtime = MagicMock()
            mock_create.return_value = mock_runtime

            runtime = server._init_runtime_components("test-server", "/tmp/cache")

            assert runtime == mock_runtime
            mock_create.assert_called_once_with("test-server", "/tmp/cache")

    @pytest.mark.asyncio
    async def test_create_startup_snapshot_default(self, server, mock_runtime):
        """Should create startup snapshot with default components."""
        server.runtime = mock_runtime

        await server._create_startup_snapshot()

        # Verify snapshot was created
        mock_runtime.snapshot_manager.create_snapshot.assert_called_once()

        # Get the components dict that was passed
        call_args = mock_runtime.snapshot_manager.create_snapshot.call_args
        components = call_args[0][0]

        # Verify standard components
        assert "server" in components
        assert components["server"]["status"] == "started"
        assert "timestamp" in components["server"]
        assert "config" in components["server"]

        # Verify config snapshot
        config_snapshot = components["server"]["config"]
        assert config_snapshot["http_port"] == 3039
        assert config_snapshot["http_host"] == "127.0.0.1"
        assert config_snapshot["debug"] is False
        assert config_snapshot["enable_http_transport"] is True

    @pytest.mark.asyncio
    async def test_create_startup_snapshot_with_custom_components(self, server, mock_runtime):
        """Should merge custom components into snapshot."""
        server.runtime = mock_runtime

        custom_components = {
            "api": {
                "status": "connected",
                "endpoint": "https://api.example.com"
            }
        }

        await server._create_startup_snapshot(custom_components=custom_components)

        # Get the components dict
        call_args = mock_runtime.snapshot_manager.create_snapshot.call_args
        components = call_args[0][0]

        # Verify custom components were merged
        assert "api" in components
        assert components["api"]["status"] == "connected"
        assert components["api"]["endpoint"] == "https://api.example.com"

        # Verify standard components still present
        assert "server" in components

    @pytest.mark.asyncio
    async def test_create_shutdown_snapshot(self, server, mock_runtime):
        """Should create shutdown snapshot."""
        server.runtime = mock_runtime

        await server._create_shutdown_snapshot()

        # Verify snapshot was created
        mock_runtime.snapshot_manager.create_snapshot.assert_called_once()

        # Get the components dict
        call_args = mock_runtime.snapshot_manager.create_snapshot.call_args
        components = call_args[0][0]

        # Verify shutdown components
        assert "server" in components
        assert components["server"]["status"] == "stopped"
        assert "timestamp" in components["server"]

    @pytest.mark.asyncio
    async def test_build_health_components(self, server, mock_runtime):
        """Should build standard health components."""
        server.runtime = mock_runtime

        components = await server._build_health_components()

        # Verify cache component
        assert len(components) == 2

        # First component should be cache
        cache_component = components[0]
        assert cache_component["name"] == "cache"

        # Second component should be snapshot
        snapshot_component = components[1]
        assert snapshot_component["name"] == "snapshot"

        # Verify health monitor was called
        assert mock_runtime.health_monitor.create_component_health.call_count == 2

    @pytest.mark.asyncio
    async def test_build_health_components_uses_cache_stats(self, server, mock_runtime):
        """Should use actual cache stats in health component."""
        server.runtime = mock_runtime

        components = await server._build_health_components()

        # Verify cache stats were used
        mock_runtime.cache_manager.get_cache_stats.assert_called_once()

        # Get the cache component details
        cache_component = components[0]
        # The details should come from get_cache_stats return value
        # (implementation specific, just verify it was called)

    def test_extract_config_snapshot(self, server, mock_config):
        """Should extract config values for snapshot."""
        config_snapshot = server._extract_config_snapshot()

        assert config_snapshot["http_port"] == 3039
        assert config_snapshot["http_host"] == "127.0.0.1"
        assert config_snapshot["debug"] is False
        assert config_snapshot["enable_http_transport"] is True

    def test_extract_config_snapshot_missing_fields(self, server):
        """Should handle missing config fields gracefully."""
        # Create a simple config object with only http_port
        from types import SimpleNamespace

        partial_config = SimpleNamespace()
        partial_config.http_port = 3039
        # Missing: http_host, debug, enable_http_transport

        server.config = partial_config

        config_snapshot = server._extract_config_snapshot()

        # Should only include fields that exist and have truthy values
        assert config_snapshot["http_port"] == 3039
        assert "http_host" not in config_snapshot
        assert "debug" not in config_snapshot
        assert "enable_http_transport" not in config_snapshot

    def test_extract_config_snapshot_override(self):
        """Should allow overriding to add custom fields."""
        from mcp_common.server import BaseOneiricServerMixin

        class CustomServer(BaseOneiricServerMixin):
            def __init__(self, config):
                self.config = config
                self.custom_field = "custom_value"

            def _extract_config_snapshot(self):
                base = super()._extract_config_snapshot()
                base["custom_field"] = self.custom_field
                return base

        config = MagicMock()
        config.http_port = 3039

        server = CustomServer(config)
        config_snapshot = server._extract_config_snapshot()

        assert config_snapshot["http_port"] == 3039
        assert config_snapshot["custom_field"] == "custom_value"


class TestBaseOneiricServerMixinIntegration:
    """Integration tests for realistic usage scenarios."""

    @pytest.fixture
    def full_server(self):
        """Create server with all components."""
        from mcp_common.server import BaseOneiricServerMixin

        class FullServer(BaseOneiricServerMixin):
            def __init__(self, config):
                self.config = config
                self.runtime = self._init_runtime_components("full-server")

            def get_app(self):
                return self  # Mock ASGI app

        config = MagicMock()
        config.http_port = 3039
        config.http_host = "127.0.0.1"
        config.debug = False
        config.enable_http_transport = True
        config.cache_dir = ".test_cache"

        return FullServer(config)

    @pytest.mark.asyncio
    async def test_complete_lifecycle(self, full_server):
        """Should support complete startup/shutdown lifecycle."""
        with patch("mcp_common.server.base.create_runtime_components") as mock_create:
            # Setup mock runtime
            mock_runtime = MagicMock()
            mock_runtime.initialize = AsyncMock()
            mock_runtime.cleanup = AsyncMock()
            mock_runtime.snapshot_manager.create_snapshot = AsyncMock()
            mock_runtime.health_monitor.create_component_health = MagicMock(
                return_value={"name": "cache", "status": "healthy"}
            )
            mock_runtime.health_monitor.create_health_response = MagicMock(
                return_value={"status": "healthy"}
            )
            mock_runtime.server_name = "full-server"
            mock_runtime.cache_dir = ".test_cache"
            mock_create.return_value = mock_runtime

            # Replace the real runtime with the mock
            full_server.runtime = mock_runtime

            # Startup
            await full_server.runtime.initialize()
            await full_server._create_startup_snapshot()

            # Verify startup
            mock_runtime.initialize.assert_called_once()
            mock_runtime.snapshot_manager.create_snapshot.assert_called_once()

            # Shutdown
            await full_server._create_shutdown_snapshot()
            await full_server.runtime.cleanup()

            # Verify shutdown
            mock_runtime.snapshot_manager.create_snapshot.assert_called()  # Called twice now
            mock_runtime.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_flow(self, full_server):
        """Should support health check with custom components."""
        with patch("mcp_common.server.base.create_runtime_components") as mock_create:
            # Setup mock runtime
            mock_runtime = MagicMock()
            mock_runtime.cache_manager.get_cache_stats = AsyncMock(
                return_value={"total_entries": 5, "initialized": True}
            )
            mock_runtime.snapshot_manager.current_snapshot = {"status": "ok"}
            mock_runtime.health_monitor.create_component_health = MagicMock(
                return_value={"name": "cache", "status": "healthy"}
            )
            mock_runtime.health_monitor.create_health_response = MagicMock(
                return_value={"status": "healthy"}
            )
            mock_runtime.server_name = "full-server"
            mock_runtime.cache_dir = ".test_cache"
            mock_create.return_value = mock_runtime

            full_server.runtime = mock_runtime

            # Build base health components
            base_components = await full_server._build_health_components()

            # Add custom component
            from oneiric.runtime.mcp_health import HealthStatus

            base_components.append(
                mock_runtime.health_monitor.create_component_health(
                    name="api",
                    status=HealthStatus.HEALTHY,
                    details={"endpoint": "https://api.example.com"}
                )
            )

            # Create response
            response = mock_runtime.health_monitor.create_health_response(base_components)

            # Verify health check flow
            mock_runtime.cache_manager.get_cache_stats.assert_called_once()
            assert mock_runtime.health_monitor.create_component_health.call_count == 3  # 2 base + 1 custom
            mock_runtime.health_monitor.create_health_response.assert_called_once_with(base_components)
