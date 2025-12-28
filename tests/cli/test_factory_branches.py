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


def test_start_permission_error_json(factory: MCPServerCLIFactory, runner: CliRunner) -> None:
    with patch("mcp_common.cli.factory.validate_cache_ownership") as validate_mock:
        validate_mock.side_effect = PermissionError("nope")
        app = factory.create_app()
        result = runner.invoke(app, ["start", "--json"])

    assert result.exit_code == ExitCode.PERMISSION_ERROR
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"
    assert payload["error"] == "permission"


def test_start_permission_error_text(factory: MCPServerCLIFactory, runner: CliRunner) -> None:
    with patch("mcp_common.cli.factory.validate_cache_ownership") as validate_mock:
        validate_mock.side_effect = PermissionError("nope")
        app = factory.create_app()
        result = runner.invoke(app, ["start"])

    assert result.exit_code == ExitCode.PERMISSION_ERROR
    assert "Permission error" in result.stdout


def test_start_already_running_json(factory: MCPServerCLIFactory, runner: CliRunner) -> None:
    write_pid_file(factory.settings.pid_path(), os.getpid())

    with patch("mcp_common.cli.factory.is_process_alive", return_value=True):
        app = factory.create_app()
        result = runner.invoke(app, ["start", "--json"])

    assert result.exit_code == ExitCode.SERVER_ALREADY_RUNNING
    payload = json.loads(result.stdout)
    assert payload["error"] == "already_running"


def test_start_with_handler_outputs_status(factory: MCPServerCLIFactory, runner: CliRunner) -> None:
    called: list[bool] = []

    def start() -> None:
        called.append(True)

    factory.start_handler = start
    app = factory.create_app()
    result = runner.invoke(app, ["start"])

    assert result.exit_code == ExitCode.SUCCESS
    assert "Starting server" in result.stdout
    assert called == [True]


def test_execute_start_handler_json(
    factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture
) -> None:
    called: list[bool] = []

    def start() -> None:
        called.append(True)

    factory.start_handler = start
    factory._execute_start_handler(json_output=True)

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "starting"
    assert called == [True]


def test_execute_start_handler_ready_json(
    factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture
) -> None:
    factory.start_handler = None
    factory._execute_start_handler(json_output=True)

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ready"


def test_execute_start_handler_ready_text(
    factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture
) -> None:
    factory.start_handler = None
    factory._execute_start_handler(json_output=False)

    assert "Server started" in capsys.readouterr().out


def test_validate_cache_and_check_process_stale_pid_text(
    factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture
) -> None:
    with patch("mcp_common.cli.factory.validate_cache_ownership"):
        with patch.object(factory, "_handle_stale_pid", return_value=(False, "Stale PID file")):
            with pytest.raises(SystemExit) as excinfo:
                factory._validate_cache_and_check_process(force=False, json_output=False)

    assert excinfo.value.code == ExitCode.STALE_PID
    assert "Stale PID file" in capsys.readouterr().out


def test_handle_stale_pid_corrupted_force(
    factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture
) -> None:
    pid_path = factory.settings.pid_path()
    pid_path.write_text("bad")

    can_continue, message = factory._handle_stale_pid(pid_path, force=True)

    assert can_continue is True
    assert "Removed corrupted PID file" in message
    assert not pid_path.exists()


def test_handle_stale_pid_stale_force(factory: MCPServerCLIFactory) -> None:
    pid_path = factory.settings.pid_path()
    pid_path.write_text("999999")

    with patch("mcp_common.cli.factory.is_process_alive", return_value=False):
        can_continue, message = factory._handle_stale_pid(pid_path, force=True)

    assert can_continue is True
    assert "Removed stale PID file" in message
    assert not pid_path.exists()


def test_get_server_pid_not_running_json(
    factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        factory._get_server_pid(json_output=True)

    assert excinfo.value.code == ExitCode.SERVER_NOT_RUNNING
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "not_running"


def test_get_server_pid_corrupted_json(
    factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture
) -> None:
    factory.settings.pid_path().write_text("bad")

    with pytest.raises(SystemExit) as excinfo:
        factory._get_server_pid(json_output=True)

    assert excinfo.value.code == ExitCode.GENERAL_ERROR
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "corrupted_pid"


def test_get_server_pid_invalid_text(
    factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture
) -> None:
    write_pid_file(factory.settings.pid_path(), os.getpid())

    with patch("mcp_common.cli.factory.validate_pid_integrity", return_value=(False, "bad")):
        with pytest.raises(SystemExit) as excinfo:
            factory._get_server_pid(json_output=False)

    assert excinfo.value.code == ExitCode.GENERAL_ERROR
    assert "PID file failed integrity checks" in capsys.readouterr().out


def test_validate_and_stop_server_process_not_found_json(
    factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture
) -> None:
    write_pid_file(factory.settings.pid_path(), os.getpid())

    with patch("mcp_common.cli.factory.os.kill", side_effect=ProcessLookupError):
        with pytest.raises(SystemExit) as excinfo:
            factory._validate_and_stop_server(os.getpid(), timeout=1, force=False, json_output=True)

    assert excinfo.value.code == ExitCode.SUCCESS
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "not_running"


def test_validate_and_stop_server_wait_success(factory: MCPServerCLIFactory) -> None:
    with patch("mcp_common.cli.factory.os.kill"):
        with patch.object(factory, "_wait_for_shutdown", return_value=True):
            with pytest.raises(SystemExit) as excinfo:
                factory._validate_and_stop_server(
                    os.getpid(), timeout=1, force=False, json_output=False
                )

    assert excinfo.value.code == ExitCode.SUCCESS


def test_wait_for_shutdown_calls_sleep(factory: MCPServerCLIFactory) -> None:
    class DummyPath:
        def exists(self) -> bool:
            return True

    class DummySettings:
        def __init__(self, pid_path: DummyPath) -> None:
            self._pid_path = pid_path

        def pid_path(self) -> DummyPath:
            return self._pid_path

    factory.settings = DummySettings(DummyPath())
    sleep_calls: list[float] = []

    with patch(
        "mcp_common.cli.factory.time.sleep", side_effect=lambda val: sleep_calls.append(val)
    ):
        assert factory._wait_for_shutdown(timeout=1, json_output=False) is False

    assert sleep_calls


def test_status_corrupted_pid_json(factory: MCPServerCLIFactory, runner: CliRunner) -> None:
    factory.settings.pid_path().write_text("bad-pid")

    app = factory.create_app()
    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == ExitCode.GENERAL_ERROR
    payload = json.loads(result.stdout)
    assert payload["error"] == "corrupted_pid"


def test_status_corrupted_pid_text(factory: MCPServerCLIFactory, runner: CliRunner) -> None:
    factory.settings.pid_path().write_text("bad-pid")

    app = factory.create_app()
    result = runner.invoke(app, ["status"])

    assert result.exit_code == ExitCode.GENERAL_ERROR
    assert "Corrupted PID file" in result.stdout


def test_status_not_running_json(factory: MCPServerCLIFactory, runner: CliRunner) -> None:
    app = factory.create_app()
    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == ExitCode.SERVER_NOT_RUNNING
    payload = json.loads(result.stdout)
    assert payload["status"] == "not_running"


def test_status_stale_pid_json(factory: MCPServerCLIFactory, runner: CliRunner) -> None:
    write_pid_file(factory.settings.pid_path(), os.getpid())

    with patch("mcp_common.cli.factory.is_process_alive", return_value=False):
        app = factory.create_app()
        result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == ExitCode.STALE_PID
    payload = json.loads(result.stdout)
    assert payload["status"] == "stale_pid"


def test_stop_invalid_pid_json(factory: MCPServerCLIFactory, runner: CliRunner) -> None:
    write_pid_file(factory.settings.pid_path(), os.getpid())

    with patch("mcp_common.cli.factory.validate_pid_integrity", return_value=(False, "bad")):
        app = factory.create_app()
        result = runner.invoke(app, ["stop", "--json"])

    assert result.exit_code == ExitCode.GENERAL_ERROR
    payload = json.loads(result.stdout)
    assert payload["error"] == "invalid_pid"


def test_stop_process_not_found_removes_pid(
    factory: MCPServerCLIFactory, runner: CliRunner
) -> None:
    write_pid_file(factory.settings.pid_path(), os.getpid())

    with patch("mcp_common.cli.factory.validate_pid_integrity", return_value=(True, "ok")):
        with patch("mcp_common.cli.factory.os.kill", side_effect=ProcessLookupError):
            app = factory.create_app()
            result = runner.invoke(app, ["stop"])

    assert result.exit_code == ExitCode.SUCCESS
    assert "Process not found" in result.stdout
    assert not factory.settings.pid_path().exists()


def test_stop_timeout_json(factory: MCPServerCLIFactory, runner: CliRunner) -> None:
    write_pid_file(factory.settings.pid_path(), os.getpid())

    with patch("mcp_common.cli.factory.validate_pid_integrity", return_value=(True, "ok")):
        with patch("mcp_common.cli.factory.os.kill"):
            with patch.object(factory, "_wait_for_shutdown", return_value=False):
                app = factory.create_app()
                result = runner.invoke(app, ["stop", "--json"])

    assert result.exit_code == ExitCode.TIMEOUT
    payload = json.loads(result.stdout)
    assert payload["status"] == "timeout"


def test_handle_timeout_text(factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit) as excinfo:
        factory._handle_timeout(os.getpid(), force=False, json_output=False)

    assert excinfo.value.code == ExitCode.TIMEOUT
    assert "Shutdown timed out" in capsys.readouterr().out


def test_force_kill_server_success_json(
    factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture
) -> None:
    write_pid_file(factory.settings.pid_path(), os.getpid())

    with patch("mcp_common.cli.factory.os.kill"), pytest.raises(SystemExit) as excinfo:
        factory._force_kill_server(os.getpid(), json_output=True)

    assert excinfo.value.code == ExitCode.SUCCESS
    assert json.loads(capsys.readouterr().out)["status"] == "killed"
    assert not factory.settings.pid_path().exists()


def test_force_kill_server_process_not_found_json(
    factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture
) -> None:
    write_pid_file(factory.settings.pid_path(), os.getpid())

    with patch("mcp_common.cli.factory.os.kill", side_effect=ProcessLookupError):
        with pytest.raises(SystemExit) as excinfo:
            factory._force_kill_server(os.getpid(), json_output=True)

    assert excinfo.value.code == ExitCode.SUCCESS
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "not_running"
    assert not factory.settings.pid_path().exists()


def test_force_kill_server_process_not_found(
    factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture
) -> None:
    write_pid_file(factory.settings.pid_path(), os.getpid())

    with patch("mcp_common.cli.factory.os.kill", side_effect=ProcessLookupError):
        with pytest.raises(SystemExit) as excinfo:
            factory._force_kill_server(os.getpid(), json_output=False)

    assert excinfo.value.code == ExitCode.SUCCESS
    assert "Process not found; removed PID file" in capsys.readouterr().out
    assert not factory.settings.pid_path().exists()


def test_wait_for_shutdown_returns_true(
    factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture
) -> None:
    pid_path = factory.settings.pid_path()
    write_pid_file(pid_path, os.getpid())
    pid_path.unlink()

    assert factory._wait_for_shutdown(timeout=1, json_output=False) is True
    assert "Server stopped" in capsys.readouterr().out


def test_wait_for_shutdown_json(
    factory: MCPServerCLIFactory, capsys: pytest.CaptureFixture
) -> None:
    class DummyPath:
        def exists(self) -> bool:
            return False

    class DummySettings:
        def __init__(self, pid_path: DummyPath) -> None:
            self._pid_path = pid_path

        def pid_path(self) -> DummyPath:
            return self._pid_path

    factory.settings = DummySettings(DummyPath())
    assert factory._wait_for_shutdown(timeout=1, json_output=True) is True
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "stopped"


def test_restart_force_removes_stale_pid(
    factory: MCPServerCLIFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_pid_file(factory.settings.pid_path(), os.getpid())
    monkeypatch.setattr(factory, "_cmd_stop", Mock())
    monkeypatch.setattr("mcp_common.cli.factory.time.sleep", lambda _val: None)

    start_called: list[bool] = []

    def fake_start(**_kwargs) -> None:
        start_called.append(True)
        raise SystemExit(ExitCode.SUCCESS)

    monkeypatch.setattr(factory, "_cmd_start", fake_start)

    with pytest.raises(SystemExit) as excinfo:
        factory._cmd_restart(force=True)

    assert excinfo.value.code == ExitCode.SUCCESS
    assert not factory.settings.pid_path().exists()
    assert start_called == [True]


def test_restart_pid_file_still_present_json(
    factory: MCPServerCLIFactory, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(factory, "_cmd_stop", Mock())
    monkeypatch.setattr(factory, "_cmd_start", Mock())
    monkeypatch.setattr(factory, "_wait_for_pid_removal", lambda *_args: False)

    with pytest.raises(SystemExit) as excinfo:
        factory._cmd_restart(json_output=True)

    assert excinfo.value.code == ExitCode.GENERAL_ERROR
    assert capsys.readouterr().out == ""


def test_wait_for_pid_removal_json_error(
    factory: MCPServerCLIFactory, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    class DummyPath:
        def exists(self) -> bool:
            return True

        def unlink(self, missing_ok: bool = True) -> None:
            return None

    class DummySettings:
        def __init__(self, pid_path: DummyPath) -> None:
            self._pid_path = pid_path

        def pid_path(self) -> DummyPath:
            return self._pid_path

    factory.settings = DummySettings(DummyPath())
    monkeypatch.setattr("mcp_common.cli.factory.time.sleep", lambda _val: None)

    assert factory._wait_for_pid_removal(json_output=True, force=False) is False
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "restart_failed"


def test_wait_for_pid_removal_text_error(
    factory: MCPServerCLIFactory, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    class DummyPath:
        def exists(self) -> bool:
            return True

        def unlink(self, missing_ok: bool = True) -> None:
            return None

    class DummySettings:
        def __init__(self, pid_path: DummyPath) -> None:
            self._pid_path = pid_path

        def pid_path(self) -> DummyPath:
            return self._pid_path

    factory.settings = DummySettings(DummyPath())
    monkeypatch.setattr("mcp_common.cli.factory.time.sleep", lambda _val: None)

    assert factory._wait_for_pid_removal(json_output=False, force=False) is False
    assert "PID file still present after stop" in capsys.readouterr().out


def test_wait_for_pid_removal_success(factory: MCPServerCLIFactory) -> None:
    class DummyPath:
        def exists(self) -> bool:
            return False

    class DummySettings:
        def __init__(self, pid_path: DummyPath) -> None:
            self._pid_path = pid_path

        def pid_path(self) -> DummyPath:
            return self._pid_path

    factory.settings = DummySettings(DummyPath())
    assert factory._wait_for_pid_removal(json_output=False, force=False) is True


def test_status_json_includes_snapshot_age(factory: MCPServerCLIFactory, runner: CliRunner) -> None:
    write_pid_file(factory.settings.pid_path(), os.getpid())
    snapshot = RuntimeHealthSnapshot(orchestrator_pid=os.getpid())
    write_runtime_health(factory.settings.health_snapshot_path(), snapshot)

    with patch("mcp_common.cli.factory.is_process_alive", return_value=True):
        app = factory.create_app()
        result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == ExitCode.SUCCESS
    payload = json.loads(result.stdout)
    assert payload["status"] == "running"
    assert "snapshot_age_seconds" in payload


def test_register_signal_handlers_shutdown(
    factory: MCPServerCLIFactory, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    snapshot = RuntimeHealthSnapshot(orchestrator_pid=os.getpid(), watchers_running=True)
    write_runtime_health(factory.settings.health_snapshot_path(), snapshot)
    write_pid_file(factory.settings.pid_path(), os.getpid())

    handlers: list[object] = []

    class DummySignalHandler:
        def __init__(self, on_shutdown, on_reload=None) -> None:
            self.on_shutdown = on_shutdown
            handlers.append(self)

        def register(self) -> None:
            return None

    monkeypatch.setattr("mcp_common.cli.factory.SignalHandler", DummySignalHandler)

    factory._register_signal_handlers(os.getpid(), json_output=False)
    handlers[0].on_shutdown()

    updated = load_runtime_health(factory.settings.health_snapshot_path())
    assert updated.watchers_running is False
    assert not factory.settings.pid_path().exists()
    assert "Server stopped" in capsys.readouterr().out


def test_register_signal_handlers_shutdown_json_no_output(
    factory: MCPServerCLIFactory, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    snapshot = RuntimeHealthSnapshot(orchestrator_pid=os.getpid(), watchers_running=True)
    write_runtime_health(factory.settings.health_snapshot_path(), snapshot)
    write_pid_file(factory.settings.pid_path(), os.getpid())

    handlers: list[object] = []

    class DummySignalHandler:
        def __init__(self, on_shutdown, on_reload=None) -> None:
            self.on_shutdown = on_shutdown
            handlers.append(self)

        def register(self) -> None:
            return None

    monkeypatch.setattr("mcp_common.cli.factory.SignalHandler", DummySignalHandler)

    factory._register_signal_handlers(os.getpid(), json_output=True)
    handlers[0].on_shutdown()

    updated = load_runtime_health(factory.settings.health_snapshot_path())
    assert updated.watchers_running is False
    assert not factory.settings.pid_path().exists()
    assert capsys.readouterr().out == ""


def test_health_outputs_last_remote_error(factory: MCPServerCLIFactory, runner: CliRunner) -> None:
    snapshot = RuntimeHealthSnapshot(
        orchestrator_pid=os.getpid(),
        watchers_running=True,
        last_remote_error="boom",
    )
    write_runtime_health(factory.settings.health_snapshot_path(), snapshot)

    app = factory.create_app()
    result = runner.invoke(app, ["health"])

    assert result.exit_code == ExitCode.SUCCESS
    assert "Last remote error: boom" in result.stdout
