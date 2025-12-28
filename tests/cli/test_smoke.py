"""Smoke tests for CLI factory components.

Basic tests to verify core components are importable and functional.
"""

import os
from pathlib import Path

from mcp_common.cli import (
    MCPServerCLIFactory,
    MCPServerSettings,
    RuntimeHealthSnapshot,
    SignalHandler,
    load_runtime_health,
    write_runtime_health,
)
from mcp_common.cli.security import (
    create_secure_cache_directory,
    is_process_alive,
    write_pid_file,
)


def test_import_all_components():
    """Test all CLI components are importable."""
    assert MCPServerCLIFactory is not None
    assert MCPServerSettings is not None
    assert RuntimeHealthSnapshot is not None
    assert SignalHandler is not None
    assert load_runtime_health is not None
    assert write_runtime_health is not None


def test_settings_basic(tmp_path: Path):
    """Test basic MCPServerSettings creation."""
    settings = MCPServerSettings(server_name="test-server")

    assert settings.server_name == "test-server"
    assert settings.cache_root == Path(".oneiric_cache")
    assert settings.health_ttl_seconds == 60.0
    assert settings.log_level == "INFO"
    assert settings.log_file is None


def test_settings_path_helpers(tmp_path: Path):
    """Test MCPServerSettings path helpers."""
    settings = MCPServerSettings(server_name="test", cache_root=tmp_path)

    assert settings.pid_path() == tmp_path / "mcp_server.pid"
    assert settings.health_snapshot_path() == tmp_path / "runtime_health.json"
    assert settings.telemetry_snapshot_path() == tmp_path / "runtime_telemetry.json"


def test_runtime_health_snapshot_basic():
    """Test RuntimeHealthSnapshot creation."""
    snapshot = RuntimeHealthSnapshot(
        orchestrator_pid=12345,
        watchers_running=True,
    )

    assert snapshot.orchestrator_pid == 12345
    assert snapshot.watchers_running is True
    assert snapshot.remote_enabled is False


def test_runtime_health_snapshot_as_dict():
    """Test RuntimeHealthSnapshot.as_dict() null coalescing."""
    snapshot = RuntimeHealthSnapshot()

    data = snapshot.as_dict()

    assert isinstance(data, dict)
    assert data["lifecycle_state"] == {}
    assert data["activity_state"] == {}
    assert data["watchers_running"] is False


def test_write_and_load_health_snapshot(tmp_path: Path):
    """Test health snapshot write/read round-trip."""
    snapshot_path = tmp_path / "health.json"

    # Write snapshot
    snapshot = RuntimeHealthSnapshot(
        orchestrator_pid=os.getpid(),
        watchers_running=True,
    )
    write_runtime_health(snapshot_path, snapshot)

    # Verify file exists and has secure permissions
    assert snapshot_path.exists()
    stat = snapshot_path.stat()
    assert stat.st_mode & 0o777 == 0o600  # Owner read/write only

    # Read snapshot back
    loaded = load_runtime_health(snapshot_path)

    assert loaded.orchestrator_pid == os.getpid()
    assert loaded.watchers_running is True
    assert loaded.updated_at is not None


def test_load_health_snapshot_missing_file(tmp_path: Path):
    """Test load_runtime_health gracefully handles missing file."""
    snapshot_path = tmp_path / "missing.json"

    snapshot = load_runtime_health(snapshot_path)

    # Should return empty snapshot, not raise
    assert snapshot.orchestrator_pid is None
    assert snapshot.watchers_running is False


def test_load_health_snapshot_corrupted(tmp_path: Path):
    """Test load_runtime_health gracefully handles corrupted file."""
    snapshot_path = tmp_path / "corrupted.json"
    snapshot_path.write_text("{invalid json content")

    snapshot = load_runtime_health(snapshot_path)

    # Should return empty snapshot, not raise
    assert snapshot.orchestrator_pid is None
    assert snapshot.watchers_running is False


def test_write_pid_file(tmp_path: Path):
    """Test PID file creation with secure permissions."""
    pid_path = tmp_path / "test.pid"

    write_pid_file(pid_path, 12345)

    assert pid_path.exists()
    assert pid_path.read_text() == "12345"

    # Verify secure permissions
    stat = pid_path.stat()
    assert stat.st_mode & 0o777 == 0o600  # Owner read/write only


def test_create_secure_cache_directory(tmp_path: Path):
    """Test cache directory creation with secure permissions."""
    cache_dir = tmp_path / ".oneiric_cache"

    create_secure_cache_directory(cache_dir)

    assert cache_dir.exists()
    assert cache_dir.is_dir()

    # Verify secure permissions
    stat = cache_dir.stat()
    assert stat.st_mode & 0o777 == 0o700  # Owner read/write/execute only


def test_is_process_alive_current_process():
    """Test is_process_alive for current Python process."""
    current_pid = os.getpid()

    # Should return True for python process
    # Note: server_name won't match, but process exists
    is_alive = is_process_alive(current_pid, "python")

    # Should be True because "python" is in command line
    assert is_alive is True


def test_is_process_alive_nonexistent():
    """Test is_process_alive for nonexistent PID."""
    fake_pid = 999999

    is_alive = is_process_alive(fake_pid, "test-server")

    assert is_alive is False


def test_factory_basic_creation():
    """Test MCPServerCLIFactory basic instantiation."""
    factory = MCPServerCLIFactory("test-server")

    assert factory.server_name == "test-server"
    assert factory.settings.server_name == "test-server"
    assert factory.start_handler is None
    assert factory.stop_handler is None


def test_factory_create_app():
    """Test MCPServerCLIFactory creates Typer app."""
    factory = MCPServerCLIFactory("test-server")

    app = factory.create_app()

    assert app is not None
    # Verify app is reusable (cached)
    assert factory.create_app() is app


def test_signal_handler_basic():
    """Test SignalHandler basic instantiation."""
    called = []

    def shutdown() -> None:
        called.append("shutdown")

    handler = SignalHandler(on_shutdown=shutdown)

    assert handler.on_shutdown is shutdown
    assert handler.on_reload is None
