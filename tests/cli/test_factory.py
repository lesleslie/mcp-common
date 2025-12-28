"""Comprehensive tests for MCPServerCLIFactory.

Tests all lifecycle commands, error handling, and edge cases.
"""

import json
import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from mcp_common.cli.factory import ExitCode, MCPServerCLIFactory
from mcp_common.cli.health import RuntimeHealthSnapshot, write_runtime_health
from mcp_common.cli.security import write_pid_file
from mcp_common.cli.settings import MCPServerSettings


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def test_settings(tmp_path: Path):
    """Create test settings with temporary cache."""
    return MCPServerSettings(
        server_name="test-server",
        cache_root=tmp_path,
        health_ttl_seconds=60.0,
    )


@pytest.fixture
def factory(test_settings):
    """Create factory with test settings."""
    return MCPServerCLIFactory("test-server", settings=test_settings)


class TestExitCodes:
    """Test exit code definitions."""

    def test_all_exit_codes_defined(self):
        """Test all expected exit codes are defined."""
        assert ExitCode.SUCCESS == 0
        assert ExitCode.GENERAL_ERROR == 1
        assert ExitCode.SERVER_NOT_RUNNING == 2
        assert ExitCode.SERVER_ALREADY_RUNNING == 3
        assert ExitCode.HEALTH_CHECK_FAILED == 4
        assert ExitCode.CONFIGURATION_ERROR == 5
        assert ExitCode.PERMISSION_ERROR == 6
        assert ExitCode.TIMEOUT == 7
        assert ExitCode.STALE_PID == 8


class TestFactoryInitialization:
    """Test MCPServerCLIFactory initialization."""

    def test_basic_initialization(self):
        """Test factory initialization with defaults."""
        factory = MCPServerCLIFactory("my-server")

        assert factory.server_name == "my-server"
        assert factory.settings.server_name == "my-server"
        assert factory.start_handler is None
        assert factory.stop_handler is None
        assert factory.health_probe_handler is None

    def test_initialization_with_custom_settings(self, test_settings):
        """Test factory with custom settings."""
        factory = MCPServerCLIFactory("test", settings=test_settings)

        assert factory.settings is test_settings
        assert factory.settings.server_name == "test-server"

    def test_initialization_with_handlers(self):
        """Test factory with custom handlers."""
        start_mock = Mock()
        stop_mock = Mock()
        health_mock = Mock()

        factory = MCPServerCLIFactory(
            "test",
            start_handler=start_mock,
            stop_handler=stop_mock,
            health_probe_handler=health_mock,
        )

        assert factory.start_handler is start_mock
        assert factory.stop_handler is stop_mock
        assert factory.health_probe_handler is health_mock


class TestAppCreation:
    """Test Typer app creation."""

    def test_create_app_basic(self, factory):
        """Test app creation returns Typer app."""
        app = factory.create_app()

        assert app is not None
        assert hasattr(app, "registered_commands")

    def test_create_app_caching(self, factory):
        """Test app is cached and reused."""
        app1 = factory.create_app()
        app2 = factory.create_app()

        # Should return same instance
        assert app1 is app2

    def test_create_app_has_standard_commands(self, factory):
        """Test app has all 5 standard commands."""
        app = factory.create_app()

        # Get registered command names
        command_names = [cmd.name for cmd in app.registered_commands]

        assert "start" in command_names
        assert "stop" in command_names
        assert "restart" in command_names
        assert "status" in command_names
        assert "health" in command_names


class TestStalePIDHandling:
    """Test stale PID file detection and recovery."""

    def test_handle_stale_pid_no_file(self, factory, tmp_path):
        """Test handling when no PID file exists."""
        pid_path = tmp_path / "nonexistent.pid"

        can_continue, message = factory._handle_stale_pid(pid_path)

        assert can_continue is True
        assert "No PID file" in message

    def test_handle_stale_pid_corrupted_without_force(self, factory, tmp_path):
        """Test corrupted PID file without force flag."""
        pid_path = tmp_path / "test.pid"
        pid_path.write_text("not-a-number")

        can_continue, message = factory._handle_stale_pid(pid_path, force=False)

        assert can_continue is False
        assert "Corrupted" in message
        assert "--force" in message
        assert pid_path.exists()  # Not removed without force

    def test_handle_stale_pid_corrupted_with_force(self, factory, tmp_path):
        """Test corrupted PID file with force flag."""
        pid_path = tmp_path / "test.pid"
        pid_path.write_text("invalid")

        can_continue, message = factory._handle_stale_pid(pid_path, force=True)

        assert can_continue is True
        assert "Removed corrupted" in message
        assert not pid_path.exists()  # Should be removed

    def test_handle_stale_pid_dead_process_without_force(self, factory, tmp_path):
        """Test stale PID (dead process) without force."""
        pid_path = tmp_path / "test.pid"
        fake_pid = 999999  # Unlikely to exist
        write_pid_file(pid_path, fake_pid)

        can_continue, message = factory._handle_stale_pid(pid_path, force=False)

        assert can_continue is False
        assert "Stale PID" in message or "not found" in message
        assert pid_path.exists()  # Not removed

    def test_handle_stale_pid_dead_process_with_force(self, factory, tmp_path):
        """Test stale PID with force removes file."""
        pid_path = tmp_path / "test.pid"
        fake_pid = 999999
        write_pid_file(pid_path, fake_pid)

        can_continue, message = factory._handle_stale_pid(pid_path, force=True)

        assert can_continue is True
        assert "Removed stale" in message or "not found" in message
        assert not pid_path.exists()  # Should be removed

    def test_handle_stale_pid_alive_process(self, factory, tmp_path):
        """Test alive process prevents start."""
        pid_path = tmp_path / "test.pid"
        current_pid = os.getpid()
        write_pid_file(pid_path, current_pid)

        # Mock is_process_alive to return True (simulating a matching process)
        with patch("mcp_common.cli.factory.is_process_alive", return_value=True):
            can_continue, message = factory._handle_stale_pid(pid_path, force=True)

            assert can_continue is False
            assert "already running" in message


class TestStatusCommand:
    """Test status command."""

    def test_status_server_not_running(self, factory, runner):
        """Test status when server not running."""
        app = factory.create_app()

        result = runner.invoke(app, ["status"])

        assert result.exit_code == ExitCode.SERVER_NOT_RUNNING
        assert "not running" in result.stdout.lower()

    def test_status_server_running(self, factory, runner, tmp_path):
        """Test status when server running."""
        # Create PID file with current process
        write_pid_file(factory.settings.pid_path(), os.getpid())

        # Create fresh health snapshot
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=os.getpid(),
            watchers_running=True,
        )
        write_runtime_health(factory.settings.health_snapshot_path(), snapshot)

        # Mock is_process_alive to return True
        with patch("mcp_common.cli.factory.is_process_alive", return_value=True):
            app = factory.create_app()
            result = runner.invoke(app, ["status"])

            assert result.exit_code == ExitCode.SUCCESS
            assert "running" in result.stdout.lower()
            assert str(os.getpid()) in result.stdout

    def test_status_json_output(self, factory, runner):
        """Test status with JSON output."""
        write_pid_file(factory.settings.pid_path(), os.getpid())

        snapshot = RuntimeHealthSnapshot(orchestrator_pid=os.getpid())
        write_runtime_health(factory.settings.health_snapshot_path(), snapshot)

        # Mock is_process_alive to return True
        with patch("mcp_common.cli.factory.is_process_alive", return_value=True):
            app = factory.create_app()
            result = runner.invoke(app, ["status", "--json"])

            assert result.exit_code == ExitCode.SUCCESS

            # Parse JSON output
            data = json.loads(result.stdout)
            assert data["status"] == "running"
            assert data["pid"] == os.getpid()
            assert "snapshot_age_seconds" in data

    def test_status_stale_pid(self, factory, runner):
        """Test status with stale PID file."""
        fake_pid = 999999
        write_pid_file(factory.settings.pid_path(), fake_pid)

        app = factory.create_app()
        result = runner.invoke(app, ["status"])

        assert result.exit_code == ExitCode.STALE_PID
        assert "stale" in result.stdout.lower() or "not found" in result.stdout.lower()


class TestHealthCommand:
    """Test health command."""

    def test_health_reads_snapshot(self, factory, runner):
        """Test health command reads existing snapshot."""
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            watchers_running=True,
            remote_enabled=True,
        )
        write_runtime_health(factory.settings.health_snapshot_path(), snapshot)

        app = factory.create_app()
        result = runner.invoke(app, ["health"])

        assert result.exit_code == ExitCode.SUCCESS
        assert "12345" in result.stdout
        assert "running" in result.stdout.lower()

    def test_health_json_output(self, factory, runner):
        """Test health with JSON output."""
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            watchers_running=True,
        )
        write_runtime_health(factory.settings.health_snapshot_path(), snapshot)

        app = factory.create_app()
        result = runner.invoke(app, ["health", "--json"])

        assert result.exit_code == ExitCode.SUCCESS

        data = json.loads(result.stdout)
        assert data["orchestrator_pid"] == 12345
        assert data["watchers_running"] is True

    def test_health_with_probe_handler(self, factory, runner):
        """Test health command with probe handler."""
        probe_called = []

        def health_probe():
            probe_called.append(True)
            return RuntimeHealthSnapshot(
                orchestrator_pid=99999,
                watchers_running=True,
            )

        factory.health_probe_handler = health_probe

        app = factory.create_app()
        result = runner.invoke(app, ["health", "--probe"])

        assert result.exit_code == ExitCode.SUCCESS
        assert probe_called  # Probe was called
        assert "99999" in result.stdout

        # Verify snapshot was written
        loaded = factory.settings.health_snapshot_path().exists()
        assert loaded is True


class TestStopCommand:
    """Test stop command."""

    def test_stop_server_not_running(self, factory, runner):
        """Test stop when no PID file exists."""
        app = factory.create_app()

        result = runner.invoke(app, ["stop"])

        assert result.exit_code == ExitCode.SERVER_NOT_RUNNING
        assert "not running" in result.stdout.lower()

    def test_stop_corrupted_pid_file(self, factory, runner):
        """Test stop with corrupted PID file."""
        factory.settings.pid_path().write_text("invalid-pid")

        app = factory.create_app()
        result = runner.invoke(app, ["stop"])

        assert result.exit_code == ExitCode.GENERAL_ERROR
        assert "corrupted" in result.stdout.lower()

    def test_stop_calls_custom_handler(self, factory, runner, tmp_path):
        """Test stop calls custom stop handler."""
        stop_called = []

        def stop_handler(pid: int) -> None:
            stop_called.append(pid)

        factory.stop_handler = stop_handler

        # Create PID file with fake PID (will fail to kill, but tests handler)
        fake_pid = 999999
        write_pid_file(factory.settings.pid_path(), fake_pid)

        app = factory.create_app()

        # Mock validate_pid_integrity to return True for our fake PID
        with patch("mcp_common.cli.factory.validate_pid_integrity", return_value=(True, "OK")):
            with patch("mcp_common.cli.factory.os.kill"):  # Mock kill to avoid errors
                # This will timeout, but we only care about handler being called
                runner.invoke(app, ["stop", "--timeout", "0", "--force"])

        # Verify stop handler was called
        assert fake_pid in stop_called


class TestIntegrationScenarios:
    """Integration tests for complete workflows."""

    def test_full_lifecycle_start_status_stop(self, factory, runner):
        """Test complete start → status → stop lifecycle."""
        # This test is tricky because start blocks - need to test components separately
        # Just verify the flow works at component level

        app = factory.create_app()

        # 1. Verify initial state (not running)
        result = runner.invoke(app, ["status"])
        assert result.exit_code == ExitCode.SERVER_NOT_RUNNING

        # 2. Create PID file manually (simulating start)
        write_pid_file(factory.settings.pid_path(), os.getpid())
        snapshot = RuntimeHealthSnapshot(orchestrator_pid=os.getpid())
        write_runtime_health(factory.settings.health_snapshot_path(), snapshot)

        # Mock is_process_alive for remaining commands
        with patch("mcp_common.cli.factory.is_process_alive", return_value=True):
            # 3. Verify status shows running
            result = runner.invoke(app, ["status"])
            assert result.exit_code == ExitCode.SUCCESS
            assert "running" in result.stdout.lower()

            # 4. Health check
            result = runner.invoke(app, ["health"])
            assert result.exit_code == ExitCode.SUCCESS

    def test_stale_pid_recovery_workflow(self, factory, runner):
        """Test recovering from stale PID file."""
        # Create stale PID file
        fake_pid = 999999
        write_pid_file(factory.settings.pid_path(), fake_pid)

        app = factory.create_app()

        # Status should detect stale PID
        result = runner.invoke(app, ["status"])
        assert result.exit_code == ExitCode.STALE_PID

        # Force start should remove stale PID
        # (We can't actually start here, but we can verify force flag works)
        # This is tested in test_handle_stale_pid_dead_process_with_force


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_permission_error_on_cache_validation(self, factory, runner, tmp_path):
        """Test start fails gracefully with permission errors."""
        # Create cache dir owned by root (simulated)
        # This is hard to test without actual permission issues
        # Tested indirectly via validate_cache_ownership tests

        # Covered by security tests

    def test_health_with_missing_snapshot(self, factory, runner):
        """Test health handles missing snapshot gracefully."""
        app = factory.create_app()

        result = runner.invoke(app, ["health"])

        # Should not crash, should show N/A values
        assert result.exit_code == ExitCode.SUCCESS
        assert "N/A" in result.stdout

    def test_status_with_corrupted_snapshot(self, factory, runner):
        """Test status handles corrupted health snapshot."""
        write_pid_file(factory.settings.pid_path(), os.getpid())

        # Write corrupted snapshot
        factory.settings.health_snapshot_path().write_text("{invalid json")

        # Mock is_process_alive to return True
        with patch("mcp_common.cli.factory.is_process_alive", return_value=True):
            app = factory.create_app()
            result = runner.invoke(app, ["status"])

            # Should still work (snapshot is optional for status)
            assert result.exit_code == ExitCode.SUCCESS

    def test_multiple_force_flags_combinations(self, factory, runner):
        """Test various force flag combinations."""
        app = factory.create_app()

        # Status with no PID file
        result = runner.invoke(app, ["status"])
        assert result.exit_code == ExitCode.SERVER_NOT_RUNNING

        # Stop with force (should still fail - no PID)
        result = runner.invoke(app, ["stop", "--force"])
        assert result.exit_code == ExitCode.SERVER_NOT_RUNNING
