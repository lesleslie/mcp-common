"""Comprehensive tests for mcp_common.cli.factory.

Covers all public functions, classes, and edge cases in MCPServerCLIFactory
and ExitCode that were previously uncovered.
"""

import json
import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from mcp_common.cli.factory import ExitCode, MCPServerCLIFactory
from mcp_common.cli.health import (
    RuntimeHealthSnapshot,
    load_runtime_health,
    write_runtime_health,
)
from mcp_common.cli.security import write_pid_file
from mcp_common.cli.settings import MCPServerSettings


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def test_settings(tmp_path: Path) -> MCPServerSettings:
    return MCPServerSettings(
        server_name="test-server",
        cache_root=tmp_path,
        health_ttl_seconds=60.0,
    )


@pytest.fixture
def factory(test_settings: MCPServerSettings) -> MCPServerCLIFactory:
    return MCPServerCLIFactory("test-server", settings=test_settings)


# ---------------------------------------------------------------------------
# ExitCode
# ---------------------------------------------------------------------------


class TestExitCode:
    """Exit code constants."""

    def test_success_is_zero(self) -> None:
        assert ExitCode.SUCCESS == 0

    def test_all_codes_are_integers(self) -> None:
        for name in dir(ExitCode):
            if name.isupper():
                assert isinstance(getattr(ExitCode, name), int)


# ---------------------------------------------------------------------------
# create_server_cli classmethod
# ---------------------------------------------------------------------------


class TestCreateServerCli:
    """Test the create_server_cli classmethod (server-class pattern)."""

    def test_returns_factory_instance(self) -> None:
        """create_server_cli returns an MCPServerCLIFactory."""

        class FakeConfig:
            pass

        class FakeServer:
            def __init__(self, config: object) -> None:
                self.config = config

            async def startup(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

            def get_app(self) -> object:
                return Mock()

        result = MCPServerCLIFactory.create_server_cli(
            server_class=FakeServer,
            config_class=FakeConfig,
            name="fake-server",
        )

        assert isinstance(result, MCPServerCLIFactory)
        assert result.server_name == "fake-server"
        assert result.start_handler is not None
        assert result.stop_handler is not None
        assert result.health_probe_handler is not None

    def test_start_handler_creates_server_instance(self) -> None:
        """start_handler creates config and server instances."""
        instances: dict[str, object] = {}

        class FakeConfig:
            def __init__(self) -> None:
                instances["config"] = self
                self.http_host = "127.0.0.1"
                self.http_port = 9999
                self.log_level = "info"

        class FakeServer:
            def __init__(self, config: object) -> None:
                instances["server"] = self
                self.config = config

            async def startup(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

            def get_app(self) -> object:
                return Mock()

        factory = MCPServerCLIFactory.create_server_cli(
            server_class=FakeServer,
            config_class=FakeConfig,
            name="fake",
        )

        with patch("mcp_common.cli.factory.asyncio.run"), \
             patch("mcp_common.cli.factory.uvicorn.run"):
            factory.start_handler()

        assert "config" in instances
        assert "server" in instances

    def test_health_probe_handler_server_none(self) -> None:
        """health_probe_handler returns not-running when server not created."""

        class FakeConfig:
            pass

        class FakeServer:
            def __init__(self, config: object) -> None:
                self.config = config

            async def startup(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

            def get_app(self) -> object:
                return Mock()

        factory = MCPServerCLIFactory.create_server_cli(
            server_class=FakeServer,
            config_class=FakeConfig,
            name="fake",
        )

        snapshot = factory.health_probe_handler()
        assert snapshot.watchers_running is False

    def test_health_probe_handler_no_health_check_method(self) -> None:
        """health_probe_handler assumes healthy when server has no health_check."""

        class FakeConfig:
            pass

        class FakeServer:
            def __init__(self, config: object) -> None:
                self.config = config

            async def startup(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

            def get_app(self) -> object:
                return Mock()

        factory = MCPServerCLIFactory.create_server_cli(
            server_class=FakeServer,
            config_class=FakeConfig,
            name="fake",
        )

        with patch("mcp_common.cli.factory.asyncio.run"), \
             patch("mcp_common.cli.factory.uvicorn.run"):
            factory.start_handler()

        snapshot = factory.health_probe_handler()
        assert snapshot.watchers_running is True

    def test_health_probe_handler_with_health_check_healthy(self) -> None:
        """health_probe_handler calls health_check method when available."""

        class FakeConfig:
            pass

        health_response = Mock()
        health_response.status = "healthy"

        class FakeServer:
            def __init__(self, config: object) -> None:
                self.config = config

            async def startup(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

            async def health_check(self) -> Mock:
                return health_response

            def get_app(self) -> object:
                return Mock()

        factory = MCPServerCLIFactory.create_server_cli(
            server_class=FakeServer,
            config_class=FakeConfig,
            name="fake",
        )

        with patch("mcp_common.cli.factory.asyncio.run"), \
             patch("mcp_common.cli.factory.uvicorn.run"):
            factory.start_handler()

        snapshot = factory.health_probe_handler()
        assert snapshot.watchers_running is True

    def test_health_probe_handler_with_health_check_unhealthy(self) -> None:
        """health_probe_handler returns not-running for unhealthy response."""

        class FakeConfig:
            pass

        health_response = Mock()
        health_response.status = "unhealthy"

        class FakeServer:
            def __init__(self, config: object) -> None:
                self.config = config

            async def startup(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

            async def health_check(self) -> Mock:
                return health_response

            def get_app(self) -> object:
                return Mock()

        factory = MCPServerCLIFactory.create_server_cli(
            server_class=FakeServer,
            config_class=FakeConfig,
            name="fake",
        )

        with patch("mcp_common.cli.factory.asyncio.run"), \
             patch("mcp_common.cli.factory.uvicorn.run"):
            factory.start_handler()

        snapshot = factory.health_probe_handler()
        assert snapshot.watchers_running is False

    def test_use_mcp_subcommand_parameter(self) -> None:
        """use_mcp_subcommand is forwarded to the factory."""

        class FakeConfig:
            pass

        class FakeServer:
            def __init__(self, config: object) -> None:
                self.config = config

            async def startup(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

            def get_app(self) -> object:
                return Mock()

        factory = MCPServerCLIFactory.create_server_cli(
            server_class=FakeServer,
            config_class=FakeConfig,
            name="fake",
            use_mcp_subcommand=True,
        )

        assert factory.use_mcp_subcommand is True

    def test_stop_handler_calls_shutdown(self) -> None:
        """stop_handler invokes server.shutdown via asyncio.run."""
        shutdown_called: list[bool] = []

        class FakeConfig:
            pass

        class FakeServer:
            def __init__(self, config: object) -> None:
                self.config = config

            async def startup(self) -> None:
                pass

            async def shutdown(self) -> None:
                shutdown_called.append(True)

            def get_app(self) -> object:
                return Mock()

        factory = MCPServerCLIFactory.create_server_cli(
            server_class=FakeServer,
            config_class=FakeConfig,
            name="fake",
        )

        with patch("mcp_common.cli.factory.asyncio.run"), \
             patch("mcp_common.cli.factory.uvicorn.run"):
            factory.start_handler()

        # asyncio.run is patched to be a no-op, so the shutdown coroutine
        # is created but never awaited. Verify the stop_handler itself
        # runs without error when _server_instance is not None.
        with patch("mcp_common.cli.factory.asyncio.run") as run_mock:
            factory.stop_handler(os.getpid())
            # asyncio.run was called with a coroutine
            assert run_mock.called


# ---------------------------------------------------------------------------
# create_app with use_mcp_subcommand=True
# ---------------------------------------------------------------------------


class TestCreateAppWithMcpSubcommand:
    """Test app creation with mcp subcommand structure."""

    def test_create_app_mcp_subcommand(self, factory: MCPServerCLIFactory) -> None:
        """App with use_mcp_subcommand has 'mcp' subcommand group."""
        factory.use_mcp_subcommand = True
        factory._app = None  # Reset cached app

        app = factory.create_app()

        assert app is not None
        # With use_mcp_subcommand=True, standard commands (start, stop, etc.)
        # are NOT at the root level; they are under 'mcp' sub-typer.
        # The root only has 'mcp' registered as a command.
        # Typer sub-typer groups appear as commands on the parent.
        # Verify that standard lifecycle commands are NOT at root level.
        root_names = [cmd.name for cmd in app.registered_commands]
        assert "start" not in root_names
        assert "stop" not in root_names

    def test_create_app_caching_with_mcp_subcommand(
        self, factory: MCPServerCLIFactory,
    ) -> None:
        """App is cached even with use_mcp_subcommand."""
        factory.use_mcp_subcommand = True
        factory._app = None

        app1 = factory.create_app()
        app2 = factory.create_app()

        assert app1 is app2


# ---------------------------------------------------------------------------
# _emit_not_running, _emit_corrupted_pid, _emit_stale_pid
# ---------------------------------------------------------------------------


class TestEmitHelpers:
    """Test helper methods that emit output and exit."""

    def test_emit_not_running_json(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            factory._emit_not_running(json_output=True)

        assert exc.value.code == ExitCode.SERVER_NOT_RUNNING
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "not_running"

    def test_emit_not_running_text(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            factory._emit_not_running(json_output=False)

        assert exc.value.code == ExitCode.SERVER_NOT_RUNNING
        assert "not running" in capsys.readouterr().out.lower()

    def test_emit_corrupted_pid_json(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            factory._emit_corrupted_pid(json_output=True)

        assert exc.value.code == ExitCode.GENERAL_ERROR
        payload = json.loads(capsys.readouterr().out)
        assert payload["error"] == "corrupted_pid"

    def test_emit_corrupted_pid_text(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            factory._emit_corrupted_pid(json_output=False)

        assert exc.value.code == ExitCode.GENERAL_ERROR
        assert "Corrupted PID" in capsys.readouterr().out

    def test_emit_stale_pid_json(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            factory._emit_stale_pid(99999, json_output=True)

        assert exc.value.code == ExitCode.STALE_PID
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "stale_pid"
        assert payload["pid"] == 99999

    def test_emit_stale_pid_text(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        # _emit_stale_pid uses typer.echo which writes to stdout via capsys
        # but sys.exit may interfere with capture. Use monkeypatch on sys.exit
        # to prevent actual exit, then read output.
        output_lines: list[str] = []

        with patch("mcp_common.cli.factory.typer.echo", side_effect=lambda msg: output_lines.append(msg)), \
             patch("mcp_common.cli.factory.sys.exit") as exit_mock:
            factory._emit_stale_pid(12345, json_output=False)

        exit_mock.assert_called_once_with(ExitCode.STALE_PID)
        combined = " ".join(output_lines)
        assert "12345" in combined


# ---------------------------------------------------------------------------
# _read_pid_or_exit, _ensure_process_alive_or_exit
# ---------------------------------------------------------------------------


class TestReadPidOrExit:
    """Test _read_pid_or_exit and _ensure_process_alive_or_exit."""

    def test_read_pid_not_running(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            factory._read_pid_or_exit(json_output=True)

        assert exc.value.code == ExitCode.SERVER_NOT_RUNNING
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "not_running"

    def test_read_pid_corrupted(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        factory.settings.pid_path().write_text("garbage")

        with pytest.raises(SystemExit) as exc:
            factory._read_pid_or_exit(json_output=False)

        assert exc.value.code == ExitCode.GENERAL_ERROR
        assert "Corrupted" in capsys.readouterr().out

    def test_read_pid_success(self, factory: MCPServerCLIFactory) -> None:
        pid = 12345
        write_pid_file(factory.settings.pid_path(), pid)

        result = factory._read_pid_or_exit(json_output=False)
        assert result == pid

    def test_ensure_process_alive_stale(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        with patch("mcp_common.cli.factory.is_process_alive", return_value=False):
            with pytest.raises(SystemExit) as exc:
                factory._ensure_process_alive_or_exit(99999, json_output=True)

        assert exc.value.code == ExitCode.STALE_PID
        payload = json.loads(capsys.readouterr().out)
        assert payload["pid"] == 99999

    def test_ensure_process_alive_ok(self, factory: MCPServerCLIFactory) -> None:
        with patch("mcp_common.cli.factory.is_process_alive", return_value=True):
            # Should NOT raise
            factory._ensure_process_alive_or_exit(os.getpid(), json_output=False)


# ---------------------------------------------------------------------------
# _emit_status_output (text mode with None age, json mode)
# ---------------------------------------------------------------------------


class TestEmitStatusOutput:
    """Test _emit_status_output helper."""

    def test_text_with_age(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            watchers_running=True,
        )
        write_runtime_health(factory.settings.health_snapshot_path(), snapshot)

        loaded = load_runtime_health(factory.settings.health_snapshot_path())
        factory._emit_status_output(12345, loaded, json_output=False)

        output = capsys.readouterr().out
        assert "PID 12345" in output
        assert "Snapshot age:" in output

    def test_text_with_no_age(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        """Text output when snapshot has no updated_at shows N/A."""
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            watchers_running=True,
            updated_at=None,
        )
        factory._emit_status_output(12345, snapshot, json_output=False)

        output = capsys.readouterr().out
        assert "PID 12345" in output
        assert "N/A" in output

    def test_json_output(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            watchers_running=True,
        )
        write_runtime_health(factory.settings.health_snapshot_path(), snapshot)

        loaded = load_runtime_health(factory.settings.health_snapshot_path())
        factory._emit_status_output(12345, loaded, json_output=True)

        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "running"
        assert payload["pid"] == 12345
        assert "snapshot_age_seconds" in payload
        assert "snapshot_fresh" in payload


# ---------------------------------------------------------------------------
# _get_health_snapshot (without probe)
# ---------------------------------------------------------------------------


class TestGetHealthSnapshot:
    """Test _get_health_snapshot helper."""

    def test_without_probe_loads_from_file(
        self, factory: MCPServerCLIFactory,
    ) -> None:
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=11111,
            watchers_running=False,
        )
        write_runtime_health(factory.settings.health_snapshot_path(), snapshot)

        result = factory._get_health_snapshot(probe=False)

        assert result.orchestrator_pid == 11111
        assert result.watchers_running is False

    def test_with_probe_calls_handler(
        self, factory: MCPServerCLIFactory,
    ) -> None:
        probe_snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=22222,
            watchers_running=True,
        )

        def probe() -> RuntimeHealthSnapshot:
            return probe_snapshot

        factory.health_probe_handler = probe
        result = factory._get_health_snapshot(probe=True)

        assert result.orchestrator_pid == 22222
        assert result.watchers_running is True

        # Verify it was written to disk
        loaded = load_runtime_health(factory.settings.health_snapshot_path())
        assert loaded.orchestrator_pid == 22222

    def test_with_probe_no_handler_loads_from_file(
        self, factory: MCPServerCLIFactory,
    ) -> None:
        """When probe=True but no handler, falls back to file."""
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=33333,
            watchers_running=True,
        )
        write_runtime_health(factory.settings.health_snapshot_path(), snapshot)

        factory.health_probe_handler = None
        result = factory._get_health_snapshot(probe=True)

        assert result.orchestrator_pid == 33333


# ---------------------------------------------------------------------------
# _emit_health_snapshot (text with None pid)
# ---------------------------------------------------------------------------


class TestEmitHealthSnapshot:
    """Test _emit_health_snapshot helper."""

    def test_text_with_pid(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            watchers_running=True,
        )
        factory._emit_health_snapshot(snapshot, json_output=False)

        output = capsys.readouterr().out
        assert "Orchestrator PID: 12345" in output
        assert "Watchers: running" in output

    def test_text_with_none_pid(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        """When orchestrator_pid is None, display N/A for both PID and watchers."""
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=None,
            watchers_running=True,
        )
        factory._emit_health_snapshot(snapshot, json_output=False)

        output = capsys.readouterr().out
        assert "N/A" in output
        # Watchers should also show N/A when pid is None
        assert "Watchers: N/A" in output

    def test_text_watchers_stopped(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            watchers_running=False,
        )
        factory._emit_health_snapshot(snapshot, json_output=False)

        output = capsys.readouterr().out
        assert "Watchers: stopped" in output

    def test_text_snapshot_age_with_timestamp(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            watchers_running=True,
        )
        write_runtime_health(factory.settings.health_snapshot_path(), snapshot)
        loaded = load_runtime_health(factory.settings.health_snapshot_path())

        factory._emit_health_snapshot(loaded, json_output=False)

        output = capsys.readouterr().out
        assert "Snapshot age:" in output

    def test_text_snapshot_age_none(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        """When snapshot has no updated_at, age shows N/A."""
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            watchers_running=True,
            updated_at=None,
        )
        factory._emit_health_snapshot(snapshot, json_output=False)

        output = capsys.readouterr().out
        assert "Snapshot age: N/A" in output

    def test_json_output(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            watchers_running=True,
            remote_enabled=True,
        )
        factory._emit_health_snapshot(snapshot, json_output=True)

        payload = json.loads(capsys.readouterr().out)
        assert payload["orchestrator_pid"] == 12345
        assert payload["watchers_running"] is True
        assert payload["remote_enabled"] is True
        # as_dict() should null-coalesce lifecycle_state and activity_state
        assert payload["lifecycle_state"] == {}
        assert payload["activity_state"] == {}

    def test_text_no_last_remote_error(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        """When last_remote_error is None, no error line is printed."""
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            watchers_running=True,
            last_remote_error=None,
        )
        factory._emit_health_snapshot(snapshot, json_output=False)

        output = capsys.readouterr().out
        assert "Last remote error" not in output

    def test_text_with_last_remote_error(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=12345,
            watchers_running=True,
            last_remote_error="connection refused",
        )
        factory._emit_health_snapshot(snapshot, json_output=False)

        output = capsys.readouterr().out
        assert "Last remote error: connection refused" in output


# ---------------------------------------------------------------------------
# _write_pid_and_health_snapshot
# ---------------------------------------------------------------------------


class TestWritePidAndHealthSnapshot:
    """Test _write_pid_and_health_snapshot helper."""

    def test_writes_pid_and_snapshot(self, factory: MCPServerCLIFactory) -> None:
        pid = factory._write_pid_and_health_snapshot()

        assert pid == os.getpid()
        assert factory.settings.pid_path().exists()
        assert factory.settings.health_snapshot_path().exists()

        snapshot = load_runtime_health(factory.settings.health_snapshot_path())
        assert snapshot.orchestrator_pid == pid
        assert snapshot.watchers_running is True


# ---------------------------------------------------------------------------
# _validate_and_stop_server with force kill path
# ---------------------------------------------------------------------------


class TestValidateAndStopServerForceKill:
    """Test the force-kill path when graceful shutdown times out."""

    def test_force_kill_after_timeout(
        self, factory: MCPServerCLIFactory,
    ) -> None:
        write_pid_file(factory.settings.pid_path(), os.getpid())

        def fake_force_kill(pid: int, json_output: bool) -> None:
            """Mimics _force_kill_server raising SystemExit."""
            raise SystemExit(ExitCode.SUCCESS)

        with patch("mcp_common.cli.factory.os.kill"), \
             patch.object(factory, "_wait_for_shutdown", return_value=False), \
             patch.object(factory, "_force_kill_server", side_effect=fake_force_kill) as kill_mock:
            with pytest.raises(SystemExit) as exc:
                factory._validate_and_stop_server(
                    os.getpid(), timeout=1, force=True, json_output=False,
                )

        assert exc.value.code == ExitCode.SUCCESS
        kill_mock.assert_called_once_with(os.getpid(), False)


# ---------------------------------------------------------------------------
# _handle_timeout json mode
# ---------------------------------------------------------------------------


class TestHandleTimeoutJson:
    """Test _handle_timeout with json output."""

    def test_handle_timeout_json(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            factory._handle_timeout(os.getpid(), force=False, json_output=True)

        assert exc.value.code == ExitCode.TIMEOUT
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "timeout"
        assert "timed out" in payload["message"].lower()

    def test_handle_timeout_json_calls_force_kill(
        self, factory: MCPServerCLIFactory,
    ) -> None:
        def fake_force_kill(pid: int, json_output: bool) -> None:
            raise SystemExit(ExitCode.SUCCESS)

        with patch.object(factory, "_force_kill_server", side_effect=fake_force_kill) as kill_mock:
            with pytest.raises(SystemExit) as exc:
                factory._handle_timeout(os.getpid(), force=True, json_output=True)

        assert exc.value.code == ExitCode.SUCCESS
        kill_mock.assert_called_once_with(os.getpid(), True)


# ---------------------------------------------------------------------------
# _force_kill_server text mode success
# ---------------------------------------------------------------------------


class TestForceKillServerText:
    """Test _force_kill_server text mode."""

    def test_force_kill_text_success(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        write_pid_file(factory.settings.pid_path(), os.getpid())

        with patch("mcp_common.cli.factory.os.kill"):
            with pytest.raises(SystemExit) as exc:
                factory._force_kill_server(os.getpid(), json_output=False)

        assert exc.value.code == ExitCode.SUCCESS
        assert "Server killed" in capsys.readouterr().out
        assert not factory.settings.pid_path().exists()


# ---------------------------------------------------------------------------
# _validate_cache_and_check_process already_running json
# ---------------------------------------------------------------------------


class TestValidateCacheAlreadyRunningJson:
    """Test _validate_cache_and_check_process with already-running json output."""

    def test_already_running_json(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        write_pid_file(factory.settings.pid_path(), os.getpid())

        with patch("mcp_common.cli.factory.validate_cache_ownership"), \
             patch.object(
                 factory,
                 "_handle_stale_pid",
                 return_value=(False, "Server already running (PID 12345)"),
             ):
            with pytest.raises(SystemExit) as exc:
                factory._validate_cache_and_check_process(
                    force=False, json_output=True,
                )

        assert exc.value.code == ExitCode.SERVER_ALREADY_RUNNING
        payload = json.loads(capsys.readouterr().out)
        assert payload["error"] == "already_running"

    def test_stale_pid_json(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        """Stale PID message maps to 'stale_pid' error type in JSON."""
        with patch("mcp_common.cli.factory.validate_cache_ownership"), \
             patch.object(
                 factory,
                 "_handle_stale_pid",
                 return_value=(False, "Stale PID file found (process 99999 dead)"),
             ):
            with pytest.raises(SystemExit) as exc:
                factory._validate_cache_and_check_process(
                    force=False, json_output=True,
                )

        assert exc.value.code == ExitCode.STALE_PID
        payload = json.loads(capsys.readouterr().out)
        assert payload["error"] == "stale_pid"


# ---------------------------------------------------------------------------
# _wait_for_shutdown json success
# ---------------------------------------------------------------------------


class TestWaitForShutdownJson:
    """Test _wait_for_shutdown returns json output when file disappears."""

    def test_json_success_output(
        self, factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture,
    ) -> None:
        pid_path = factory.settings.pid_path()
        write_pid_file(pid_path, os.getpid())

        # Immediately remove the file so the first check sees it gone
        pid_path.unlink()

        result = factory._wait_for_shutdown(timeout=1, json_output=True)
        assert result is True
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "stopped"


# ---------------------------------------------------------------------------
# _cmd_start integration: verifies internal call ordering
# ---------------------------------------------------------------------------


class TestCmdStartFullFlow:
    """Test _cmd_start internal method call ordering."""

    def test_start_calls_all_steps(
        self, factory: MCPServerCLIFactory, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[str] = []

        original_validate = factory._validate_cache_and_check_process
        original_write = factory._write_pid_and_health_snapshot
        original_register = factory._register_signal_handlers
        original_execute = factory._execute_start_handler

        def track_validate(*args, **kwargs):
            calls.append("validate")
            return original_validate(*args, **kwargs)

        def track_write(*args, **kwargs):
            calls.append("write")
            return original_write(*args, **kwargs)

        def track_register(*args, **kwargs):
            calls.append("register")
            return original_register(*args, **kwargs)

        def track_execute(*args, **kwargs):
            calls.append("execute")
            raise SystemExit(ExitCode.SUCCESS)

        monkeypatch.setattr(factory, "_validate_cache_and_check_process", track_validate)
        monkeypatch.setattr(factory, "_write_pid_and_health_snapshot", track_write)
        monkeypatch.setattr(factory, "_register_signal_handlers", track_register)
        monkeypatch.setattr(factory, "_execute_start_handler", track_execute)

        with patch("mcp_common.cli.factory.validate_cache_ownership"):
            with pytest.raises(SystemExit) as exc:
                factory._cmd_start(force=False, json_output=False)

        assert exc.value.code == ExitCode.SUCCESS
        assert calls == ["validate", "write", "register", "execute"]


# ---------------------------------------------------------------------------
# Health command: text output without snapshot
# ---------------------------------------------------------------------------


class TestHealthCommandNoSnapshot:
    """Test health command when no snapshot file exists."""

    def test_health_text_no_snapshot(
        self, factory: MCPServerCLIFactory, runner: CliRunner,
    ) -> None:
        """Health shows N/A when no snapshot exists."""
        app = factory.create_app()
        result = runner.invoke(app, ["health"])

        assert result.exit_code == ExitCode.SUCCESS
        assert "N/A" in result.stdout


# ---------------------------------------------------------------------------
# Factory with use_mcp_subcommand
# ---------------------------------------------------------------------------


class TestFactoryWithMcpSubcommand:
    """Test factory initialization with use_mcp_subcommand flag."""

    def test_init_with_mcp_subcommand_true(
        self, test_settings: MCPServerSettings,
    ) -> None:
        factory = MCPServerCLIFactory(
            "test-server",
            settings=test_settings,
            use_mcp_subcommand=True,
        )
        assert factory.use_mcp_subcommand is True

    def test_init_with_mcp_subcommand_false(
        self, test_settings: MCPServerSettings,
    ) -> None:
        factory = MCPServerCLIFactory(
            "test-server",
            settings=test_settings,
            use_mcp_subcommand=False,
        )
        assert factory.use_mcp_subcommand is False
