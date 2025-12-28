"""MCP Server CLI factory for Oneiric-native servers.

Provides a production-ready factory for creating standardized MCP server
CLIs with lifecycle management, health monitoring, and graceful shutdown.
"""

import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

import typer

from mcp_common.cli.health import (
    RuntimeHealthSnapshot,
    get_snapshot_age_seconds,
    is_snapshot_fresh,
    load_runtime_health,
    write_runtime_health,
)
from mcp_common.cli.security import (
    is_process_alive,
    validate_cache_ownership,
    validate_pid_integrity,
    write_pid_file,
)
from mcp_common.cli.settings import MCPServerSettings
from mcp_common.cli.signals import SignalHandler


class ExitCode:
    """Standard exit codes for MCP server CLI."""

    SUCCESS = 0  # Operation succeeded
    GENERAL_ERROR = 1  # General failure (unspecified)
    SERVER_NOT_RUNNING = 2  # Server not running (status/stop)
    SERVER_ALREADY_RUNNING = 3  # Server already running (start)
    HEALTH_CHECK_FAILED = 4  # Health check failed
    CONFIGURATION_ERROR = 5  # Invalid configuration
    PERMISSION_ERROR = 6  # Insufficient permissions
    TIMEOUT = 7  # Operation timeout
    STALE_PID = 8  # Stale PID file (use --force)


class MCPServerCLIFactory:
    """Factory for creating standardized MCP server CLIs.

    Creates Typer-based CLIs with standard lifecycle commands (start, stop,
    restart, status, health) and extensibility for server-specific commands.

    Example:
        >>> factory = MCPServerCLIFactory("my-server")
        >>> app = factory.create_app()
        >>>
        >>> @app.command()
        >>> def custom():
        ...     print("Custom command")
        >>>
        >>> if __name__ == "__main__":
        ...     app()
    """

    def __init__(
        self,
        server_name: str,
        settings: MCPServerSettings | None = None,
        start_handler: Callable[[], None] | None = None,
        stop_handler: Callable[[int], None] | None = None,
        health_probe_handler: Callable[[], RuntimeHealthSnapshot] | None = None,
    ) -> None:
        """Initialize CLI factory.

        Args:
            server_name: Server identifier (e.g., 'session-buddy')
            settings: Optional custom settings (auto-loads if None)
            start_handler: Optional custom start logic (called after PID created)
            stop_handler: Optional custom stop logic (called before PID removed)
            health_probe_handler: Optional health probe logic (for --health --probe)
        """
        self.server_name = server_name
        self.settings = settings or MCPServerSettings.load(server_name)
        self.start_handler = start_handler
        self.stop_handler = stop_handler
        self.health_probe_handler = health_probe_handler
        self._app: typer.Typer | None = None

    def create_app(self) -> typer.Typer:
        """Create Typer app with standard lifecycle commands.

        Returns:
            Configured Typer app with start, stop, restart, status, health commands
        """
        if self._app is not None:
            return self._app

        app = typer.Typer(
            help=f"{self.server_name} MCP Server CLI",
            add_completion=False,
        )

        # Register standard commands
        app.command("start")(self._cmd_start)
        app.command("stop")(self._cmd_stop)
        app.command("restart")(self._cmd_restart)
        app.command("status")(self._cmd_status)
        app.command("health")(self._cmd_health)

        self._app = app
        return app

    def _handle_stale_pid(self, pid_path: Path, force: bool = False) -> tuple[bool, str]:
        """Handle stale PID file detection and recovery.

        Args:
            pid_path: Path to PID file
            force: If True, remove stale PID file automatically

        Returns:
            (should_continue, message) tuple
        """
        if not pid_path.exists():
            return (True, "No PID file found")

        try:
            pid = int(pid_path.read_text().strip())
        except (ValueError, OSError) as e:
            # Corrupted PID file
            if force:
                pid_path.unlink(missing_ok=True)
                return (True, f"Removed corrupted PID file: {e}")
            return (False, f"Corrupted PID file (use --force to remove): {e}")

        if not is_process_alive(pid, self.server_name):
            # Stale PID file
            if force:
                pid_path.unlink(missing_ok=True)
                return (True, f"Removed stale PID file (process {pid} not found)")
            return (False, f"Stale PID file found (process {pid} dead). Use --force to remove.")

        # Process is alive
        return (False, f"Server already running (PID {pid})")

    def _cmd_start(
        self,
        force: bool = typer.Option(
            False, "--force", help="Force start (kill existing process if stale)"
        ),
        json_output: bool = typer.Option(False, "--json", help="Output JSON instead of text"),
    ) -> None:
        """Start the MCP server."""
        self._validate_cache_and_check_process(force, json_output)
        pid = self._write_pid_and_health_snapshot()
        self._register_signal_handlers(pid, json_output)
        self._execute_start_handler(json_output)
        sys.exit(ExitCode.SUCCESS)

    def _validate_cache_and_check_process(self, force: bool, json_output: bool) -> None:
        """Validate cache ownership and check for existing process."""
        # Validate cache ownership
        try:
            validate_cache_ownership(self.settings.cache_root)
        except PermissionError as exc:
            if json_output:
                typer.echo(
                    json.dumps(
                        {
                            "status": "error",
                            "error": "permission",
                            "message": str(exc),
                        }
                    )
                )
            else:
                typer.echo(f"Permission error: {exc}")
            sys.exit(ExitCode.PERMISSION_ERROR)

        # Check for existing process
        can_continue, message = self._handle_stale_pid(self.settings.pid_path(), force)

        if not can_continue:
            if json_output:
                error_type = "stale_pid" if "stale" in message.lower() else "already_running"
                typer.echo(
                    json.dumps(
                        {
                            "status": "error",
                            "error": error_type,
                            "message": message,
                        }
                    )
                )
            else:
                typer.echo(message)

            exit_code = (
                ExitCode.SERVER_ALREADY_RUNNING
                if "already running" in message
                else ExitCode.STALE_PID
            )
            sys.exit(exit_code)

    def _write_pid_and_health_snapshot(self) -> int:
        """Write PID file and initial health snapshot."""
        # Write PID file
        pid = os.getpid()
        write_pid_file(self.settings.pid_path(), pid)

        # Write initial health snapshot
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=pid,
            watchers_running=True,
        )
        write_runtime_health(self.settings.health_snapshot_path(), snapshot)
        return pid

    def _register_signal_handlers(self, pid: int, json_output: bool) -> None:
        """Register signal handlers for graceful shutdown."""

        def shutdown() -> None:
            """Graceful shutdown callback."""
            # Update health snapshot (mark as stopped)
            snapshot = load_runtime_health(self.settings.health_snapshot_path())
            snapshot.watchers_running = False
            write_runtime_health(self.settings.health_snapshot_path(), snapshot)

            # Remove PID file
            self.settings.pid_path().unlink(missing_ok=True)

            if not json_output:
                typer.echo("Server stopped")

        signal_handler = SignalHandler(on_shutdown=shutdown)
        signal_handler.register()

    def _execute_start_handler(self, json_output: bool) -> None:
        """Execute the custom start handler if provided."""
        if self.start_handler is not None:
            if json_output:
                typer.echo(json.dumps({"status": "starting", "message": "Starting server"}))
            else:
                typer.echo("Starting server")
            self.start_handler()
        elif json_output:
            typer.echo(json.dumps({"status": "ready", "message": "Server started"}))
        else:
            typer.echo("Server started")

    def _cmd_stop(
        self,
        timeout: int = typer.Option(10, "--timeout", help="Seconds to wait for shutdown"),
        force: bool = typer.Option(False, "--force", help="Force kill (SIGKILL) if timeout"),
        json_output: bool = typer.Option(False, "--json", help="Output JSON instead of text"),
    ) -> None:
        """Stop the MCP server."""
        pid = self._get_server_pid(json_output)
        self._validate_and_stop_server(pid, timeout, force, json_output)

    def _get_server_pid(self, json_output: bool) -> int:
        """Get the server PID from the PID file."""
        pid_path = self.settings.pid_path()

        if not pid_path.exists():
            if json_output:
                typer.echo(json.dumps({"status": "not_running", "message": "Server not running"}))
            else:
                typer.echo("Server not running")
            sys.exit(ExitCode.SERVER_NOT_RUNNING)

        try:
            pid = int(pid_path.read_text().strip())
        except (ValueError, OSError):
            if json_output:
                typer.echo(
                    json.dumps(
                        {
                            "status": "error",
                            "error": "corrupted_pid",
                            "message": "Corrupted PID file",
                        }
                    )
                )
            else:
                typer.echo("Corrupted PID file")
            sys.exit(ExitCode.GENERAL_ERROR)

        # Validate PID integrity
        is_valid, _reason = validate_pid_integrity(pid, pid_path, self.server_name)
        if not is_valid:
            if json_output:
                typer.echo(
                    json.dumps(
                        {
                            "status": "error",
                            "error": "invalid_pid",
                            "message": "PID file failed integrity checks",
                        }
                    )
                )
            else:
                typer.echo("PID file failed integrity checks")
            sys.exit(ExitCode.GENERAL_ERROR)

        return pid

    def _validate_and_stop_server(
        self, pid: int, timeout: int, force: bool, json_output: bool
    ) -> None:
        """Validate and stop the server process."""
        # Call custom stop handler
        if self.stop_handler is not None:
            self.stop_handler(pid)

        # Send SIGTERM for graceful shutdown
        try:
            os.kill(pid, 15)  # SIGTERM
        except ProcessLookupError:
            if json_output:
                typer.echo(json.dumps({"status": "not_running", "message": "Process not found"}))
            else:
                typer.echo("Process not found; removing stale PID file")
            self.settings.pid_path().unlink(missing_ok=True)
            sys.exit(ExitCode.SUCCESS)

        # Wait for graceful shutdown
        if self._wait_for_shutdown(timeout, json_output):
            sys.exit(ExitCode.SUCCESS)

        # Handle timeout
        self._handle_timeout(pid, force, json_output)

    def _wait_for_shutdown(self, timeout: int, json_output: bool) -> bool:
        """Wait for the server to shut down gracefully."""
        pid_path = self.settings.pid_path()
        for _ in range(timeout * 10):  # Check every 0.1s
            if not pid_path.exists():
                if json_output:
                    typer.echo(json.dumps({"status": "stopped", "message": "Server stopped"}))
                else:
                    typer.echo("Server stopped")
                return True
            time.sleep(0.1)
        return False

    def _handle_timeout(self, pid: int, force: bool, json_output: bool) -> None:
        """Handle timeout scenario when stopping server."""
        if force:
            self._force_kill_server(pid, json_output)
        else:
            if json_output:
                typer.echo(
                    json.dumps(
                        {
                            "status": "timeout",
                            "message": "Shutdown timed out",
                        }
                    )
                )
            else:
                typer.echo("Shutdown timed out")
            sys.exit(ExitCode.TIMEOUT)

    def _force_kill_server(self, pid: int, json_output: bool) -> None:
        """Force kill the server process."""
        try:
            os.kill(pid, 9)  # SIGKILL
            self.settings.pid_path().unlink(missing_ok=True)
            if json_output:
                typer.echo(json.dumps({"status": "killed", "message": "Server killed"}))
            else:
                typer.echo("Server killed")
        except ProcessLookupError:
            self.settings.pid_path().unlink(missing_ok=True)
            if json_output:
                typer.echo(json.dumps({"status": "not_running", "message": "Process not found"}))
            else:
                typer.echo("Process not found; removed PID file")
        sys.exit(ExitCode.SUCCESS)

    def _cmd_restart(
        self,
        timeout: int = typer.Option(10, "--timeout", help="Stop timeout (seconds)"),
        force: bool = typer.Option(False, "--force", help="Force restart if server not running"),
        json_output: bool = typer.Option(False, "--json", help="Output JSON instead of text"),
    ) -> None:
        """Restart the MCP server (stop + start)."""
        # Stop server
        self._cmd_stop(timeout=timeout, force=force, json_output=json_output)

        if not self._wait_for_pid_removal(json_output, force):
            sys.exit(ExitCode.GENERAL_ERROR)

        # Start server
        self._cmd_start(force=force, json_output=json_output)

    def _wait_for_pid_removal(self, json_output: bool, force: bool) -> bool:
        """Wait for PID file removal after stop."""
        pid_path = self.settings.pid_path()
        for _ in range(50):  # 50 * 0.1s = 5s
            if not pid_path.exists():
                return True
            time.sleep(0.1)

        if force:
            pid_path.unlink(missing_ok=True)
            return True

        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "status": "error",
                        "error": "restart_failed",
                        "message": "PID file still present after stop",
                    }
                )
            )
        else:
            typer.echo("PID file still present after stop")
        return False

    def _emit_not_running(self, json_output: bool) -> None:
        """Emit not-running output and exit."""
        if json_output:
            typer.echo(json.dumps({"status": "not_running", "message": "Server not running"}))
        else:
            typer.echo("Server not running")
        sys.exit(ExitCode.SERVER_NOT_RUNNING)

    def _emit_corrupted_pid(self, json_output: bool) -> None:
        """Emit corrupted PID output and exit."""
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "status": "error",
                        "error": "corrupted_pid",
                        "message": "Corrupted PID file",
                    }
                )
            )
        else:
            typer.echo("Corrupted PID file")
        sys.exit(ExitCode.GENERAL_ERROR)

    def _emit_stale_pid(self, pid: int, json_output: bool) -> None:
        """Emit stale PID output and exit."""
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "status": "stale_pid",
                        "pid": pid,
                        "message": "Stale PID file; process not found",
                    }
                )
            )
        else:
            typer.echo(f"Stale PID file; process {pid} not found")
        sys.exit(ExitCode.STALE_PID)

    def _read_pid_or_exit(self, json_output: bool) -> int:
        """Read PID from file or exit with message."""
        pid_path = self.settings.pid_path()

        if not pid_path.exists():
            self._emit_not_running(json_output)

        try:
            return int(pid_path.read_text().strip())
        except (ValueError, OSError):
            self._emit_corrupted_pid(json_output)

        msg = "Unreachable: PID read should exit or return"
        raise AssertionError(msg)

    def _ensure_process_alive_or_exit(self, pid: int, json_output: bool) -> None:
        """Ensure PID is alive or exit with stale PID response."""
        if not is_process_alive(pid, self.server_name):
            self._emit_stale_pid(pid, json_output)

    def _emit_status_output(
        self,
        pid: int,
        snapshot: RuntimeHealthSnapshot,
        json_output: bool,
    ) -> None:
        """Emit status output for running server."""
        age = get_snapshot_age_seconds(snapshot)
        snapshot_fresh = is_snapshot_fresh(snapshot, self.settings.health_ttl_seconds)

        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "status": "running",
                        "pid": pid,
                        "snapshot_age_seconds": age,
                        "snapshot_fresh": snapshot_fresh,
                    }
                )
            )
            return

        typer.echo(f"Server running (PID {pid})")
        if age is not None:
            typer.echo(f"Snapshot age: {age:.1f}s")
        else:
            typer.echo("Snapshot age: N/A")

    def _get_health_snapshot(self, probe: bool) -> RuntimeHealthSnapshot:
        """Return latest health snapshot, optionally running probe."""
        if probe and self.health_probe_handler is not None:
            snapshot = self.health_probe_handler()
            write_runtime_health(self.settings.health_snapshot_path(), snapshot)
            return snapshot

        return load_runtime_health(self.settings.health_snapshot_path())

    def _emit_health_snapshot(self, snapshot: RuntimeHealthSnapshot, json_output: bool) -> None:
        """Emit health snapshot output."""
        if json_output:
            typer.echo(json.dumps(snapshot.as_dict()))
            return

        pid_value = snapshot.orchestrator_pid
        pid_display = str(pid_value) if pid_value is not None else "N/A"
        typer.echo(f"Orchestrator PID: {pid_display}")
        watchers_display = "running" if snapshot.watchers_running else "stopped"
        if pid_value is None:
            watchers_display = "N/A"
        typer.echo(f"Watchers: {watchers_display}")
        typer.echo(f"Remote enabled: {snapshot.remote_enabled}")
        age = get_snapshot_age_seconds(snapshot)
        if age is not None:
            typer.echo(f"Snapshot age: {age:.1f}s")
        else:
            typer.echo("Snapshot age: N/A")

        if snapshot.last_remote_error:
            typer.echo(f"Last remote error: {snapshot.last_remote_error}")

    def _cmd_status(
        self,
        json_output: bool = typer.Option(False, "--json", help="Output JSON instead of text"),
    ) -> None:
        """Check if server is running (lightweight check)."""
        pid = self._read_pid_or_exit(json_output)
        self._ensure_process_alive_or_exit(pid, json_output)
        snapshot = load_runtime_health(self.settings.health_snapshot_path())
        self._emit_status_output(pid, snapshot, json_output)

        sys.exit(ExitCode.SUCCESS)

    def _cmd_health(
        self,
        probe: bool = typer.Option(False, "--probe", help="Run live health probes"),
        json_output: bool = typer.Option(False, "--json", help="Output JSON instead of text"),
    ) -> None:
        """Display server health (snapshot or live probe)."""
        snapshot = self._get_health_snapshot(probe)
        self._emit_health_snapshot(snapshot, json_output)

        sys.exit(ExitCode.SUCCESS)
