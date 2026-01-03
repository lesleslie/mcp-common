"""Tests for runtime component factory in mcp_common/server/runtime.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestRuntimeComponents:
    """Tests for RuntimeComponents dataclass."""

    @pytest.fixture
    def mock_snapshot_manager(self):
        """Create mock snapshot manager."""
        manager = AsyncMock()
        manager.initialize = AsyncMock()
        manager.cleanup = AsyncMock()
        manager.create_snapshot = AsyncMock()
        return manager

    @pytest.fixture
    def mock_cache_manager(self):
        """Create mock cache manager."""
        manager = AsyncMock()
        manager.initialize = AsyncMock()
        manager.cleanup = AsyncMock()
        manager.get_cache_stats = AsyncMock(return_value={"total_entries": 10, "initialized": True})
        return manager

    @pytest.fixture
    def mock_health_monitor(self):
        """Create mock health monitor."""
        monitor = MagicMock()
        monitor.create_component_health = MagicMock(return_value={"name": "test", "status": "healthy"})
        monitor.create_health_response = MagicMock(return_value={"status": "healthy"})
        return monitor

    @pytest.fixture
    def runtime_components(self, mock_snapshot_manager, mock_cache_manager, mock_health_monitor):
        """Create RuntimeComponents fixture."""
        from mcp_common.server import RuntimeComponents

        return RuntimeComponents(
            server_name="test-server",
            cache_dir=".test_cache",
            snapshot_manager=mock_snapshot_manager,
            cache_manager=mock_cache_manager,
            health_monitor=mock_health_monitor,
        )

    def test_attributes_set_correctly(self, runtime_components):
        """Should set all attributes correctly."""
        assert runtime_components.server_name == "test-server"
        assert runtime_components.cache_dir == ".test_cache"
        assert runtime_components.snapshot_manager is not None
        assert runtime_components.cache_manager is not None
        assert runtime_components.health_monitor is not None

    @pytest.mark.asyncio
    async def test_initialize_calls_all_managers(self, runtime_components):
        """Should call initialize on all managers."""
        await runtime_components.initialize()

        runtime_components.snapshot_manager.initialize.assert_called_once()
        runtime_components.cache_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_calls_all_managers(self, runtime_components):
        """Should call cleanup on all managers."""
        await runtime_components.cleanup()

        runtime_components.snapshot_manager.cleanup.assert_called_once()
        runtime_components.cache_manager.cleanup.assert_called_once()


class TestCreateRuntimeComponents:
    """Tests for create_runtime_components() factory function."""

    @patch("mcp_common.server.runtime.RuntimeSnapshotManager")
    @patch("mcp_common.server.runtime.RuntimeCacheManager")
    @patch("mcp_common.server.runtime.HealthMonitor")
    def test_creates_all_components(self, mock_health_monitor, mock_cache_manager, mock_snapshot_manager):
        """Should create all runtime components."""
        from mcp_common.server import create_runtime_components

        runtime = create_runtime_components("test-server", ".test_cache")

        # Verify all managers were created
        mock_snapshot_manager.assert_called_once_with(
            cache_dir=".test_cache",
            server_name="test-server",
        )
        mock_cache_manager.assert_called_once_with(
            cache_dir=".test_cache",
            server_name="test-server",
        )
        mock_health_monitor.assert_called_once_with(
            server_name="test-server"
        )

    @patch("mcp_common.server.runtime.RuntimeSnapshotManager")
    @patch("mcp_common.server.runtime.RuntimeCacheManager")
    @patch("mcp_common.server.runtime.HealthMonitor")
    def test_returns_runtime_components_instance(self, mock_health_monitor, mock_cache_manager, mock_snapshot_manager):
        """Should return RuntimeComponents instance."""
        from mcp_common.server import create_runtime_components, RuntimeComponents

        runtime = create_runtime_components("test-server", ".test_cache")

        assert isinstance(runtime, RuntimeComponents)
        assert runtime.server_name == "test-server"
        assert runtime.cache_dir == ".test_cache"
        assert runtime.snapshot_manager == mock_snapshot_manager.return_value
        assert runtime.cache_manager == mock_cache_manager.return_value
        assert runtime.health_monitor == mock_health_monitor.return_value

    @patch("mcp_common.server.runtime.RuntimeSnapshotManager")
    @patch("mcp_common.server.runtime.RuntimeCacheManager")
    @patch("mcp_common.server.runtime.HealthMonitor")
    @pytest.mark.asyncio
    async def test_runtime_can_be_initialized(self, mock_health_monitor, mock_cache_manager, mock_snapshot_manager):
        """Should allow runtime to be initialized."""
        from mcp_common.server import create_runtime_components

        runtime = create_runtime_components("test-server", ".test_cache")

        # Mock the initialize methods
        runtime.snapshot_manager.initialize = AsyncMock()
        runtime.cache_manager.initialize = AsyncMock()

        # Initialize should work
        await runtime.initialize()

        runtime.snapshot_manager.initialize.assert_called_once()
        runtime.cache_manager.initialize.assert_called_once()

    @patch("mcp_common.server.runtime.RuntimeSnapshotManager")
    @patch("mcp_common.server.runtime.RuntimeCacheManager")
    @patch("mcp_common.server.runtime.HealthMonitor")
    @pytest.mark.asyncio
    async def test_runtime_can_be_cleaned_up(self, mock_health_monitor, mock_cache_manager, mock_snapshot_manager):
        """Should allow runtime to be cleaned up."""
        from mcp_common.server import create_runtime_components

        runtime = create_runtime_components("test-server", ".test_cache")

        # Mock the cleanup methods
        runtime.snapshot_manager.cleanup = AsyncMock()
        runtime.cache_manager.cleanup = AsyncMock()

        # Cleanup should work
        await runtime.cleanup()

        runtime.snapshot_manager.cleanup.assert_called_once()
        runtime.cache_manager.cleanup.assert_called_once()


class TestCreateRuntimeComponentsRealWorld:
    """Real-world usage tests with actual Oneiric components."""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_initializes_actual_components(self):
        """Should initialize actual Oneiric runtime components."""
        from mcp_common.server import create_runtime_components
        import tempfile
        import shutil

        # Use temp directory for cache
        cache_dir = tempfile.mkdtemp()

        try:
            runtime = create_runtime_components("test-server", cache_dir)

            # Initialize
            await runtime.initialize()

            # Verify components are actual instances
            from oneiric.runtime.cache import RuntimeCacheManager
            from oneiric.runtime.mcp_health import HealthMonitor
            from oneiric.runtime.snapshot import RuntimeSnapshotManager

            assert isinstance(runtime.snapshot_manager, RuntimeSnapshotManager)
            assert isinstance(runtime.cache_manager, RuntimeCacheManager)
            assert isinstance(runtime.health_monitor, HealthMonitor)

            # Cleanup
            await runtime.cleanup()
        finally:
            # Cleanup temp directory
            shutil.rmtree(cache_dir, ignore_errors=True)

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_snapshot_and_cache_operations(self):
        """Should support snapshot and cache operations."""
        from mcp_common.server import create_runtime_components
        import tempfile
        import shutil
        import time

        cache_dir = tempfile.mkdtemp()

        try:
            runtime = create_runtime_components("test-server", cache_dir)

            await runtime.initialize()

            # Test snapshot creation
            components = {
                "server": {
                    "status": "started",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            }
            await runtime.snapshot_manager.create_snapshot(components)

            # Test cache operations
            await runtime.cache_manager.set("test_key", "test_value", ttl=60)
            value = await runtime.cache_manager.get("test_key")
            assert value == "test_value"

            # Test cache stats
            stats = await runtime.cache_manager.get_cache_stats()
            assert "total_entries" in stats
            assert stats["total_entries"] >= 1

            # Cleanup
            await runtime.cleanup()
        finally:
            shutil.rmtree(cache_dir, ignore_errors=True)
