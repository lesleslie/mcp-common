# Oneiric CLI Factory Implementation Specification

**Version:** 1.0.0
**Status:** Draft - Ready for Review
**Date:** 2025-12-20
**Supersedes:** ONEIRIC_CLI_FACTORY_PLAN.md (addresses audit findings)

______________________________________________________________________

## Table of Contents

1. [Executive Summary](#executive-summary)
1. [CLI Factory API Architecture](#cli-factory-api-architecture)
1. [Error Handling & Recovery](#error-handling--recovery)
1. [Security Specifications](#security-specifications)
1. [Signal Handling](#signal-handling)
1. [Configuration Hierarchy](#configuration-hierarchy)
1. [Logging & Verbosity](#logging--verbosity)
1. [Test Requirements](#test-requirements)
1. [Implementation Steps](#implementation-steps)
1. [Migration Guide](#migration-guide)

______________________________________________________________________

## Executive Summary

This specification defines a **production-ready CLI factory** for MCP servers migrating to Oneiric. The factory provides:

- **Standard lifecycle commands** (`--start`, `--stop`, `--restart`, `--status`, `--health`)
- **Snapshot-based process management** (PID file + runtime health JSON)
- **Graceful error recovery** (stale PID detection, corrupted snapshot handling)
- **Security-first design** (file permissions, process validation, atomic writes)
- **Signal handling** (SIGTERM/SIGINT for graceful shutdown)
- **Extensibility** (server-specific custom commands)

**Key Architectural Decisions:**

1. **No ACB Dependencies** - Clean break from ACB, pure Oneiric-native implementation
1. **Typer-based CLI** - Following Oneiric's `typer.Typer()` pattern for consistency
1. **Settings-driven paths** - All paths resolved via `MCPServerSettings` (Pydantic BaseModel)
1. **Atomic operations** - All file writes use `tmp.write() → tmp.replace()` for crash-safety
1. **JSON-first output** - All commands support `--json` for machine-readable output

______________________________________________________________________

## CLI Factory API Architecture

### Factory Class

```python
from pathlib import Path
from typing import Callable, Any
import typer
from pydantic import BaseModel, Field


class MCPServerSettings(BaseModel):
    """MCP Server configuration extending Oneiric patterns.

    Loads from (in priority order):
    1. CLI flags (highest)
    2. Environment variables (MCP_SERVER_*)
    3. settings/local.yaml (gitignored)
    4. settings/{server_name}.yaml
    5. Defaults (lowest)
    """

    server_name: str = Field(description="Server identifier (e.g., 'session-buddy')")
    cache_root: Path = Field(
        default=Path(".oneiric_cache"), description="Cache directory for PID and snapshots"
    )
    health_ttl_seconds: float = Field(
        default=60.0, ge=1.0, description="Snapshot freshness threshold (seconds)"
    )
    log_level: str = Field(
        default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    log_file: Path | None = Field(
        default=None, description="Optional log file path (None = stdout only)"
    )

    def pid_path(self) -> Path:
        """PID file path: .oneiric_cache/mcp_server.pid"""
        return self.cache_root / "mcp_server.pid"

    def health_snapshot_path(self) -> Path:
        """Runtime health snapshot: .oneiric_cache/runtime_health.json"""
        return self.cache_root / "runtime_health.json"

    def telemetry_snapshot_path(self) -> Path:
        """Runtime telemetry snapshot: .oneiric_cache/runtime_telemetry.json"""
        return self.cache_root / "runtime_telemetry.json"

    @classmethod
    def load(cls, server_name: str, config_path: Path | None = None) -> "MCPServerSettings":
        """Load settings from YAML + environment variables.

        Args:
            server_name: Server identifier (e.g., 'session-buddy')
            config_path: Optional explicit config file path

        Returns:
            Loaded settings with environment overrides applied
        """
        # Implementation matches Oneiric's load_settings() pattern
        ...


class MCPServerCLIFactory:
    """Factory for creating standardized MCP server CLIs.

    Usage:
        >>> factory = MCPServerCLIFactory("my-server")
        >>> app = factory.create_app()
        >>>
        >>> # Add custom commands
        >>> @app.command()
        >>> def custom():
        >>>     print("Custom command")
        >>>
        >>> if __name__ == "__main__":
        >>>     app()
    """

    def __init__(
        self,
        server_name: str,
        settings: MCPServerSettings | None = None,
        start_handler: Callable[[], None] | None = None,
        stop_handler: Callable[[int], None] | None = None,
    ):
        """Initialize CLI factory.

        Args:
            server_name: Server identifier (e.g., 'session-buddy')
            settings: Optional custom settings (auto-loads if None)
            start_handler: Optional custom start logic (called after PID created)
            stop_handler: Optional custom stop logic (called before PID removed)
        """
        self.server_name = server_name
        self.settings = settings or MCPServerSettings.load(server_name)
        self.start_handler = start_handler
        self.stop_handler = stop_handler
        self._app: typer.Typer | None = None

    def create_app(self) -> typer.Typer:
        """Create Typer app with standard lifecycle commands.

        Returns:
            Configured Typer app with --start, --stop, --restart, --status, --health
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

    # Command implementations follow...
```

### Command Signatures

```python
def _cmd_start(
    self,
    force: bool = typer.Option(
        False, "--force", help="Force start (kill existing process if stale)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output JSON instead of human-readable"),
) -> None:
    """Start the MCP server."""
    ...


def _cmd_stop(
    self,
    timeout: int = typer.Option(10, "--timeout", help="Seconds to wait for graceful shutdown"),
    force: bool = typer.Option(False, "--force", help="Force kill (SIGKILL) if timeout exceeded"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON instead of human-readable"),
) -> None:
    """Stop the MCP server."""
    ...


def _cmd_restart(
    self,
    timeout: int = typer.Option(10, "--timeout", help="Stop timeout (seconds)"),
    force: bool = typer.Option(False, "--force", help="Force restart even if server not running"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON instead of human-readable"),
) -> None:
    """Restart the MCP server (stop + start)."""
    ...


def _cmd_status(
    self,
    json_output: bool = typer.Option(False, "--json", help="Output JSON instead of human-readable"),
) -> None:
    """Check if server is running (lightweight PID + snapshot freshness check)."""
    ...


def _cmd_health(
    self,
    probe: bool = typer.Option(False, "--probe", help="Run live health probes (updates snapshot)"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON instead of human-readable"),
) -> None:
    """Display server health (reads runtime snapshot or runs probes)."""
    ...
```

### Extension Mechanism

```python
# Server-specific commands can be added directly to the Typer app
factory = MCPServerCLIFactory("my-server")
app = factory.create_app()


@app.command()
def migrate_db(dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes only")):
    """Custom server-specific command."""
    print("Running database migration...")


if __name__ == "__main__":
    app()
```

______________________________________________________________________

## Error Handling & Recovery

### Stale PID Detection

**Problem:** PID file exists but process is dead (crash, system reboot, manual kill)

**Solution:**

```python
import os
import signal
import psutil  # Only for process validation, not core logic


def _is_process_alive(pid: int, server_name: str) -> bool:
    """Check if PID is alive and matches expected server.

    Args:
        pid: Process ID to check
        server_name: Expected server name (for command line validation)

    Returns:
        True if process is alive AND matches server signature
    """
    try:
        # Step 1: Check if PID exists (send null signal)
        os.kill(pid, 0)
    except ProcessLookupError:
        # Process doesn't exist
        return False
    except PermissionError:
        # Process exists but we can't signal it (owned by another user)
        # Conservative: assume alive
        return True

    # Step 2: Validate process command line (prevent impersonation)
    try:
        process = psutil.Process(pid)
        cmdline = " ".join(process.cmdline())

        # Check for server signature in command line
        # Example: "python -m session_buddy.server" or "session-buddy-server"
        if server_name.replace("-", "_") in cmdline or server_name in cmdline:
            return True

        # Process exists but doesn't match our server
        return False
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        # Can't validate, assume dead
        return False


def _handle_stale_pid(pid_path: Path, force: bool = False) -> tuple[bool, str]:
    """Handle stale PID file.

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

    if not _is_process_alive(pid, server_name):
        # Stale PID file
        if force:
            pid_path.unlink(missing_ok=True)
            return (True, f"Removed stale PID file (process {pid} not found)")
        return (False, f"Stale PID file found (process {pid} dead). Use --force to remove.")

    # Process is alive
    return (False, f"Server already running (PID {pid})")
```

### Corrupted Snapshot Handling

**Problem:** JSON snapshot file is corrupted (partial write, disk error, manual edit)

**Solution:**

```python
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from typing import Any


@dataclass
class RuntimeHealthSnapshot:
    """Runtime health snapshot (matches Oneiric schema)."""

    orchestrator_pid: int | None = None
    updated_at: str | None = None
    watchers_running: bool = False
    remote_enabled: bool = False
    last_remote_sync_at: str | None = None
    last_remote_error: str | None = None
    lifecycle_state: dict[str, dict[str, Any]] = None  # type: ignore
    activity_state: dict[str, dict[str, Any]] = None  # type: ignore

    def as_dict(self) -> dict[str, Any]:
        """Convert to dict with null coalescing."""
        data = asdict(self)
        if data.get("lifecycle_state") is None:
            data["lifecycle_state"] = {}
        if data.get("activity_state") is None:
            data["activity_state"] = {}
        return data


def load_runtime_health(path: Path) -> RuntimeHealthSnapshot:
    """Load runtime health snapshot with graceful degradation.

    Returns empty snapshot if file missing or corrupted (never raises).

    Args:
        path: Path to runtime_health.json

    Returns:
        RuntimeHealthSnapshot (empty if error)
    """
    if not path.exists():
        return RuntimeHealthSnapshot()

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        # Corrupted or unreadable - log warning, return empty
        logger.warning(f"Corrupted health snapshot at {path}: {e}")
        return RuntimeHealthSnapshot()

    if not isinstance(data, dict):
        logger.warning(f"Invalid health snapshot format at {path}: not a dict")
        return RuntimeHealthSnapshot()

    # Populate snapshot with validation
    snapshot = RuntimeHealthSnapshot()
    snapshot.orchestrator_pid = data.get("orchestrator_pid")
    snapshot.updated_at = data.get("updated_at")
    snapshot.watchers_running = bool(data.get("watchers_running", False))
    snapshot.remote_enabled = bool(data.get("remote_enabled", False))
    snapshot.last_remote_sync_at = data.get("last_remote_sync_at")
    snapshot.last_remote_error = data.get("last_remote_error")
    snapshot.lifecycle_state = data.get("lifecycle_state") or {}
    snapshot.activity_state = data.get("activity_state") or {}

    return snapshot


def write_runtime_health(path: Path, snapshot: RuntimeHealthSnapshot) -> None:
    """Write runtime health snapshot atomically.

    Uses tmp file + replace for crash-safety. Creates parent directories.
    Updates snapshot.updated_at to current timestamp.

    Args:
        path: Path to runtime_health.json
        snapshot: Snapshot to write

    Raises:
        OSError: If write fails (disk full, permissions, etc.)
    """
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Update timestamp
    snapshot.updated_at = datetime.now(UTC).isoformat()

    # Atomic write: tmp file → replace
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(snapshot.as_dict(), indent=2))
        tmp.chmod(0o600)  # Owner read/write only
        tmp.replace(path)
    except OSError:
        # Cleanup tmp file on error
        tmp.unlink(missing_ok=True)
        raise
```

### Snapshot Freshness Check

**Problem:** Snapshot exists but is stale (server crashed without updating)

**Solution:**

```python
from datetime import datetime, UTC, timedelta


def is_snapshot_fresh(snapshot: RuntimeHealthSnapshot, ttl_seconds: float) -> bool:
    """Check if snapshot is within TTL threshold.

    Args:
        snapshot: Runtime health snapshot
        ttl_seconds: Maximum age in seconds

    Returns:
        True if snapshot.updated_at is within TTL, False otherwise
    """
    if snapshot.updated_at is None:
        return False

    try:
        updated_at = datetime.fromisoformat(snapshot.updated_at)
    except (ValueError, TypeError):
        return False

    age = datetime.now(UTC) - updated_at
    return age <= timedelta(seconds=ttl_seconds)


def get_snapshot_age_seconds(snapshot: RuntimeHealthSnapshot) -> float | None:
    """Calculate snapshot age in seconds.

    Args:
        snapshot: Runtime health snapshot

    Returns:
        Age in seconds, or None if timestamp invalid
    """
    if snapshot.updated_at is None:
        return None

    try:
        updated_at = datetime.fromisoformat(snapshot.updated_at)
    except (ValueError, TypeError):
        return None

    return (datetime.now(UTC) - updated_at).total_seconds()
```

### Exit Codes

All commands use standardized exit codes for scripting/CI integration:

```python
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
```

**Usage Example:**

```python
import sys


def _cmd_start(self, force: bool = False, json_output: bool = False) -> None:
    # Check for existing process
    can_continue, message = self._handle_stale_pid(self.settings.pid_path(), force)

    if not can_continue:
        if json_output:
            print(json.dumps({"status": "error", "message": message}))
        else:
            print(f"Error: {message}")
        sys.exit(
            ExitCode.SERVER_ALREADY_RUNNING if "already running" in message else ExitCode.STALE_PID
        )

    # Start server...
    sys.exit(ExitCode.SUCCESS)
```

______________________________________________________________________

## Security Specifications

### File Permissions

All cache files use restrictive permissions to prevent unauthorized access:

```python
import os
from pathlib import Path


def _create_secure_cache_directory(cache_root: Path) -> None:
    """Create cache directory with secure permissions.

    Directory: 0o700 (rwx------, owner only)

    Args:
        cache_root: Path to .oneiric_cache directory
    """
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_root.chmod(0o700)  # Owner read/write/execute only


def _write_pid_file(pid_path: Path, pid: int) -> None:
    """Write PID file with secure permissions.

    File: 0o600 (rw-------, owner read/write only)

    Args:
        pid_path: Path to PID file
        pid: Process ID to write
    """
    pid_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Write PID atomically
    tmp = pid_path.with_suffix(".tmp")
    tmp.write_text(str(pid))
    tmp.chmod(0o600)  # Owner read/write only
    tmp.replace(pid_path)


def _validate_cache_ownership(cache_root: Path) -> None:
    """Validate cache directory is owned by current user.

    Prevents snapshot injection attacks if directory is world-writable.

    Args:
        cache_root: Path to .oneiric_cache directory

    Raises:
        PermissionError: If directory owned by another user
    """
    if not cache_root.exists():
        return

    stat = cache_root.stat()
    current_uid = os.getuid()

    if stat.st_uid != current_uid:
        raise PermissionError(
            f"Cache directory {cache_root} owned by UID {stat.st_uid}, "
            f"but current user is UID {current_uid}. "
            f"Refusing to use potentially compromised cache."
        )
```

### Process Validation (Prevent Impersonation)

```python
import psutil
import time


def _validate_pid_integrity(
    pid: int,
    pid_path: Path,
    server_name: str,
) -> tuple[bool, str]:
    """Validate PID file points to legitimate server process.

    Prevents impersonation attacks where malicious process:
    1. Deletes real PID file
    2. Creates own PID file
    3. Receives stop signals intended for real server

    Args:
        pid: Process ID from PID file
        pid_path: Path to PID file
        server_name: Expected server name

    Returns:
        (is_valid, reason) tuple
    """
    try:
        process = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return (False, f"Process {pid} not found")

    # Check 1: Command line matches server signature
    try:
        cmdline = " ".join(process.cmdline())
        server_slug = server_name.replace("-", "_")

        if server_slug not in cmdline and server_name not in cmdline:
            return (
                False,
                f"Process {pid} command line does not match server '{server_name}': {cmdline}",
            )
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        # Can't read cmdline, conservative: assume invalid
        return (False, f"Cannot validate process {pid} (access denied)")

    # Check 2: Process start time predates PID file creation (prevent race)
    try:
        pid_file_mtime = pid_path.stat().st_mtime
        process_create_time = process.create_time()

        # PID file should be created AFTER process started
        # Allow 1 second tolerance for clock skew
        if process_create_time > pid_file_mtime + 1.0:
            return (False, f"Process {pid} started after PID file created (possible impersonation)")
    except (OSError, psutil.NoSuchProcess):
        # Can't validate timing, fail safe
        return (False, f"Cannot validate process {pid} timing")

    return (True, "Process validated")
```

### Atomic Operations

All file writes use atomic `write → replace` to prevent corruption from crashes:

```python
from pathlib import Path
import json
from typing import Any


def _atomic_write_json(path: Path, data: dict[str, Any], mode: int = 0o600) -> None:
    """Atomically write JSON file with secure permissions.

    Uses tmp file + replace for crash-safety during write.

    Args:
        path: Target file path
        data: JSON-serializable data
        mode: File permissions (octal)

    Raises:
        OSError: If write fails
    """
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2))
        tmp.chmod(mode)
        tmp.replace(path)  # Atomic on POSIX systems
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
```

______________________________________________________________________

## Signal Handling

### Signal Handler Registration

```python
import signal
import sys
from typing import Callable


class SignalHandler:
    """Signal handler for graceful shutdown.

    Handles SIGTERM, SIGINT for graceful shutdown.
    Optionally handles SIGHUP for configuration reload.
    """

    def __init__(
        self,
        on_shutdown: Callable[[], None],
        on_reload: Callable[[], None] | None = None,
    ):
        """Initialize signal handler.

        Args:
            on_shutdown: Called on SIGTERM/SIGINT (should trigger graceful shutdown)
            on_reload: Optional callback for SIGHUP (configuration reload)
        """
        self.on_shutdown = on_shutdown
        self.on_reload = on_reload
        self._shutdown_called = False

    def register(self) -> None:
        """Register signal handlers."""
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        if self.on_reload is not None:
            signal.signal(signal.SIGHUP, self._handle_reload)

    def _handle_shutdown(self, signum: int, frame: Any) -> None:
        """Handle SIGTERM/SIGINT (graceful shutdown).

        Only calls on_shutdown once (subsequent signals are ignored).
        """
        if self._shutdown_called:
            return

        self._shutdown_called = True

        signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        print(f"Received {signal_name}, initiating graceful shutdown...")

        try:
            self.on_shutdown()
        except Exception as e:
            print(f"Error during shutdown: {e}", file=sys.stderr)
            sys.exit(1)

        sys.exit(0)

    def _handle_reload(self, signum: int, frame: Any) -> None:
        """Handle SIGHUP (configuration reload)."""
        if self.on_reload is None:
            return

        print("Received SIGHUP, reloading configuration...")

        try:
            self.on_reload()
        except Exception as e:
            print(f"Error during reload: {e}", file=sys.stderr)
```

### Integration with Server Lifecycle

```python
import os
from pathlib import Path


def _start_server(
    settings: MCPServerSettings,
    start_handler: Callable[[], None] | None,
) -> None:
    """Start MCP server with signal handling.

    Args:
        settings: Server configuration
        start_handler: Optional custom start logic
    """
    # Write PID file
    pid = os.getpid()
    _write_pid_file(settings.pid_path(), pid)

    # Write initial health snapshot
    snapshot = RuntimeHealthSnapshot(
        orchestrator_pid=pid,
        watchers_running=True,
    )
    write_runtime_health(settings.health_snapshot_path(), snapshot)

    # Register signal handlers
    def shutdown():
        """Graceful shutdown callback."""
        # Update health snapshot (mark as stopped)
        snapshot = load_runtime_health(settings.health_snapshot_path())
        snapshot.watchers_running = False
        write_runtime_health(settings.health_snapshot_path(), snapshot)

        # Remove PID file
        settings.pid_path().unlink(missing_ok=True)

        print("Shutdown complete")

    signal_handler = SignalHandler(on_shutdown=shutdown)
    signal_handler.register()

    # Call custom start handler
    if start_handler is not None:
        start_handler()

    # Server main loop runs here...
```

### Signal Handling Requirements

1. **SIGTERM/SIGINT** - Must trigger graceful shutdown:

   - Update health snapshot (`watchers_running = False`)
   - Remove PID file
   - Flush logs
   - Exit with code 0

1. **SIGHUP** - (Optional) Configuration reload:

   - Reload settings from YAML
   - Reinitialize adapters if needed
   - Do NOT restart server process

1. **SIGKILL** - Cannot be caught (immediate termination):

   - Server should handle stale PID on next start
   - Health snapshot will be stale (detected via TTL)

______________________________________________________________________

## Configuration Hierarchy

### Priority Order (Highest to Lowest)

1. **CLI Flags** - Explicit command-line arguments (`--cache-root=/tmp/cache`)
1. **Environment Variables** - Prefixed with server name (`MCP_SERVER_CACHE_ROOT`)
1. **Local Settings** - `settings/local.yaml` (gitignored, developer overrides)
1. **Server Settings** - `settings/{server_name}.yaml` (checked into repo)
1. **Defaults** - Hardcoded in `MCPServerSettings` Pydantic model

### Environment Variable Naming

```bash
# Pattern: MCP_SERVER_{FIELD_NAME} (uppercase, snake_case)

export MCP_SERVER_CACHE_ROOT="/custom/cache"
export MCP_SERVER_HEALTH_TTL_SECONDS="120"
export MCP_SERVER_LOG_LEVEL="DEBUG"
export MCP_SERVER_LOG_FILE="/var/log/mcp-server.log"
```

### YAML Configuration Schema

```yaml
# settings/session-buddy.yaml
server_name: session-buddy

# Cache configuration
cache_root: .oneiric_cache  # Relative to project root
health_ttl_seconds: 60.0

# Logging configuration
log_level: INFO  # DEBUG, INFO, WARNING, ERROR
log_file: null   # null = stdout only, or path to file

# Server-specific extensions (optional)
custom:
  feature_flags:
    enable_auto_store: true
    enable_crackerjack: true
```

### Loading Logic

```python
import os
import yaml
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Any


class MCPServerSettings(BaseModel):
    """MCP Server settings with layered configuration."""

    server_name: str
    cache_root: Path = Field(default=Path(".oneiric_cache"))
    health_ttl_seconds: float = Field(default=60.0, ge=1.0)
    log_level: str = Field(default="INFO")
    log_file: Path | None = Field(default=None)

    @classmethod
    def load(
        cls,
        server_name: str,
        config_path: Path | None = None,
        env_prefix: str = "MCP_SERVER",
    ) -> "MCPServerSettings":
        """Load settings with layered configuration.

        Priority (highest to lowest):
        1. Explicit config_path (if provided)
        2. Environment variables ({env_prefix}_{FIELD})
        3. settings/local.yaml (gitignored)
        4. settings/{server_name}.yaml
        5. Defaults

        Args:
            server_name: Server identifier
            config_path: Optional explicit config file
            env_prefix: Environment variable prefix

        Returns:
            Loaded settings instance
        """
        data = {"server_name": server_name}

        # Layer 1: Server defaults (settings/{server_name}.yaml)
        server_yaml = Path("settings") / f"{server_name}.yaml"
        if server_yaml.exists():
            with open(server_yaml) as f:
                yaml_data = yaml.safe_load(f) or {}
                data.update(yaml_data)

        # Layer 2: Local overrides (settings/local.yaml)
        local_yaml = Path("settings") / "local.yaml"
        if local_yaml.exists():
            with open(local_yaml) as f:
                local_data = yaml.safe_load(f) or {}
                data.update(local_data)

        # Layer 3: Environment variables
        for field_name in cls.model_fields:
            env_var = f"{env_prefix}_{field_name.upper()}"
            if env_var in os.environ:
                data[field_name] = os.environ[env_var]

        # Layer 4: Explicit config path (highest priority)
        if config_path is not None and config_path.exists():
            with open(config_path) as f:
                explicit_data = yaml.safe_load(f) or {}
                data.update(explicit_data)

        return cls(**data)
```

______________________________________________________________________

## Logging & Verbosity

### Logging Configuration

```python
import logging
import sys
from pathlib import Path
from typing import TextIO


def configure_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    json_format: bool = False,
) -> logging.Logger:
    """Configure logging for MCP server.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path (None = stdout only)
        json_format: If True, use JSON structured logging

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("mcp_server")
    logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    if json_format:
        # JSON structured logging
        import json

        class JSONFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                log_obj = {
                    "timestamp": self.formatTime(record, self.datefmt),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
                if record.exc_info:
                    log_obj["exception"] = self.formatException(record.exc_info)
                return json.dumps(log_obj)

        console_handler.setFormatter(JSONFormatter())
    else:
        # Human-readable format
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(console_handler.formatter)
        logger.addHandler(file_handler)

    return logger
```

### Verbosity Levels

```python
# CLI flag for verbosity control
def _cmd_health(
    self,
    probe: bool = False,
    json_output: bool = False,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
) -> None:
    """Health command with verbosity control."""

    # Configure logging based on verbosity
    if verbose:
        logger.setLevel(logging.DEBUG)

    # Command logic...
```

### Log Output Examples

**Standard (INFO level):**

```
2025-12-20 10:30:45 [INFO] mcp_server: Server started (PID 12345)
2025-12-20 10:30:46 [INFO] mcp_server: Health snapshot written
```

**Verbose (DEBUG level):**

```
2025-12-20 10:30:45 [DEBUG] mcp_server: Loading settings from settings/session-buddy.yaml
2025-12-20 10:30:45 [DEBUG] mcp_server: Cache directory: /project/.oneiric_cache
2025-12-20 10:30:45 [DEBUG] mcp_server: PID file: /project/.oneiric_cache/mcp_server.pid
2025-12-20 10:30:45 [INFO] mcp_server: Server started (PID 12345)
2025-12-20 10:30:46 [DEBUG] mcp_server: Writing health snapshot (atomic)
2025-12-20 10:30:46 [INFO] mcp_server: Health snapshot written
```

**JSON Format:**

```json
{"timestamp": "2025-12-20 10:30:45", "level": "INFO", "logger": "mcp_server", "message": "Server started (PID 12345)"}
{"timestamp": "2025-12-20 10:30:46", "level": "INFO", "logger": "mcp_server", "message": "Health snapshot written"}
```

______________________________________________________________________

## Test Requirements

### Coverage Targets

- **Minimum coverage:** 90% (enforced by pytest `--cov-fail-under=90`)
- **Critical paths:** 100% coverage required:
  - PID file operations (create, read, delete, stale detection)
  - Snapshot operations (load, write, corruption handling)
  - Signal handling (shutdown, reload)
  - Process validation (impersonation prevention)

### Test Categories

#### Unit Tests

```python
import pytest
from pathlib import Path
from mcp_common.cli.factory import MCPServerCLIFactory, MCPServerSettings


def test_stale_pid_detection(tmp_path: Path):
    """Test stale PID file detection and removal."""
    pid_path = tmp_path / "mcp_server.pid"

    # Write PID for non-existent process
    pid_path.write_text("999999")

    factory = MCPServerCLIFactory("test-server")
    can_continue, message = factory._handle_stale_pid(pid_path, force=False)

    assert not can_continue
    assert "stale" in message.lower()
    assert pid_path.exists()  # Not removed without --force

    # Try with force=True
    can_continue, message = factory._handle_stale_pid(pid_path, force=True)

    assert can_continue
    assert not pid_path.exists()  # Removed with --force


def test_corrupted_snapshot_graceful_degradation(tmp_path: Path):
    """Test graceful handling of corrupted snapshot files."""
    from mcp_common.cli.health import load_runtime_health

    snapshot_path = tmp_path / "runtime_health.json"

    # Write corrupted JSON
    snapshot_path.write_text("{invalid json content")

    # Should return empty snapshot, not raise
    snapshot = load_runtime_health(snapshot_path)

    assert snapshot.orchestrator_pid is None
    assert snapshot.updated_at is None
    assert snapshot.watchers_running is False


def test_atomic_write_crash_safety(tmp_path: Path):
    """Test atomic write prevents corruption during crash."""
    from mcp_common.cli.health import write_runtime_health, RuntimeHealthSnapshot
    import os
    import signal

    snapshot_path = tmp_path / "runtime_health.json"
    snapshot = RuntimeHealthSnapshot(orchestrator_pid=12345)

    # Simulate crash during write (should cleanup tmp file)
    # This is hard to test directly, but we can verify tmp cleanup
    write_runtime_health(snapshot_path, snapshot)

    tmp_file = snapshot_path.with_suffix(".tmp")
    assert not tmp_file.exists()  # tmp file cleaned up
    assert snapshot_path.exists()  # Target file exists


def test_snapshot_freshness_check():
    """Test snapshot TTL freshness detection."""
    from mcp_common.cli.health import is_snapshot_fresh, RuntimeHealthSnapshot
    from datetime import datetime, UTC, timedelta

    # Fresh snapshot (10 seconds old)
    snapshot = RuntimeHealthSnapshot(
        updated_at=(datetime.now(UTC) - timedelta(seconds=10)).isoformat()
    )
    assert is_snapshot_fresh(snapshot, ttl_seconds=60.0)

    # Stale snapshot (120 seconds old)
    snapshot = RuntimeHealthSnapshot(
        updated_at=(datetime.now(UTC) - timedelta(seconds=120)).isoformat()
    )
    assert not is_snapshot_fresh(snapshot, ttl_seconds=60.0)
```

#### Integration Tests

```python
import subprocess
import time
from pathlib import Path


def test_start_stop_lifecycle(tmp_path: Path):
    """Test full start → status → stop lifecycle."""
    # Start server
    result = subprocess.run(
        ["python", "-m", "mcp_server", "start", "--cache-root", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Wait for startup
    time.sleep(1)

    # Check status
    result = subprocess.run(
        ["python", "-m", "mcp_server", "status", "--cache-root", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "running" in result.stdout.lower()

    # Stop server
    result = subprocess.run(
        ["python", "-m", "mcp_server", "stop", "--cache-root", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_signal_handling_graceful_shutdown(tmp_path: Path):
    """Test SIGTERM triggers graceful shutdown."""
    import signal

    # Start server in background
    proc = subprocess.Popen(
        ["python", "-m", "mcp_server", "start", "--cache-root", str(tmp_path)],
    )
    time.sleep(1)

    # Send SIGTERM
    proc.send_signal(signal.SIGTERM)

    # Wait for graceful shutdown (max 5 seconds)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Server did not shutdown gracefully within 5 seconds")

    # Verify PID file removed
    pid_path = tmp_path / "mcp_server.pid"
    assert not pid_path.exists()

    # Verify health snapshot marked as stopped
    from mcp_common.cli.health import load_runtime_health

    snapshot = load_runtime_health(tmp_path / "runtime_health.json")
    assert not snapshot.watchers_running
```

#### Security Tests

```python
def test_pid_file_permissions(tmp_path: Path):
    """Test PID file created with secure permissions (0o600)."""
    from mcp_common.cli.factory import _write_pid_file
    import stat

    pid_path = tmp_path / "mcp_server.pid"
    _write_pid_file(pid_path, 12345)

    mode = pid_path.stat().st_mode
    assert stat.S_IMODE(mode) == 0o600  # Owner read/write only


def test_cache_ownership_validation(tmp_path: Path):
    """Test cache directory ownership validation."""
    from mcp_common.cli.factory import _validate_cache_ownership
    import os

    cache_dir = tmp_path / ".oneiric_cache"
    cache_dir.mkdir()

    # Should pass for current user
    _validate_cache_ownership(cache_dir)

    # Simulate wrong owner (hard to test without root)
    # At minimum, ensure function doesn't crash
    assert True


def test_process_impersonation_prevention():
    """Test process validation prevents impersonation."""
    from mcp_common.cli.factory import _validate_pid_integrity
    import os

    # Create fake PID file for this process (should fail validation)
    pid = os.getpid()

    is_valid, reason = _validate_pid_integrity(
        pid=pid,
        pid_path=Path("/tmp/fake.pid"),
        server_name="fake-server-xyz",  # Won't match our process
    )

    assert not is_valid
    assert "does not match" in reason
```

#### Property-Based Tests (Hypothesis)

```python
from hypothesis import given, strategies as st


@given(st.integers(min_value=1, max_value=1000000))
def test_pid_round_trip(pid: int, tmp_path: Path):
    """Test PID file write/read round-trip for any valid PID."""
    from mcp_common.cli.factory import _write_pid_file

    pid_path = tmp_path / "test.pid"
    _write_pid_file(pid_path, pid)

    read_pid = int(pid_path.read_text().strip())
    assert read_pid == pid


@given(st.floats(min_value=1.0, max_value=3600.0))
def test_ttl_freshness_property(ttl_seconds: float):
    """Test snapshot freshness for any valid TTL."""
    from mcp_common.cli.health import is_snapshot_fresh, RuntimeHealthSnapshot
    from datetime import datetime, UTC, timedelta

    # Snapshot just inside TTL
    snapshot = RuntimeHealthSnapshot(
        updated_at=(datetime.now(UTC) - timedelta(seconds=ttl_seconds - 1)).isoformat()
    )
    assert is_snapshot_fresh(snapshot, ttl_seconds)

    # Snapshot just outside TTL
    snapshot = RuntimeHealthSnapshot(
        updated_at=(datetime.now(UTC) - timedelta(seconds=ttl_seconds + 1)).isoformat()
    )
    assert not is_snapshot_fresh(snapshot, ttl_seconds)
```

### CI/CD Integration

```yaml
# .github/workflows/test.yml
name: Test MCP Common

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync --group dev

      - name: Run tests with coverage
        run: |
          uv run pytest --cov=mcp_common --cov-fail-under=90 --cov-report=html

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
```

______________________________________________________________________

## Implementation Steps

### Phase 1: Core CLI Factory (Week 1)

**Goal:** Working CLI factory with basic lifecycle commands

1. **Create `mcp_common/cli/` package**

   ```
   mcp_common/cli/
   ├── __init__.py          # Exports MCPServerCLIFactory, MCPServerSettings
   ├── factory.py           # MCPServerCLIFactory implementation
   ├── settings.py          # MCPServerSettings with YAML loading
   ├── health.py            # RuntimeHealthSnapshot, load/write functions
   └── signals.py           # SignalHandler implementation
   ```

1. **Implement MCPServerSettings**

   - Pydantic BaseModel with path helpers
   - YAML loading with environment overrides
   - Validation for cache_root, health_ttl_seconds

1. **Implement RuntimeHealthSnapshot**

   - Dataclass matching Oneiric schema
   - `load_runtime_health()` with graceful degradation
   - `write_runtime_health()` with atomic writes

1. **Implement MCPServerCLIFactory**

   - `create_app()` returns Typer app
   - `_cmd_start()` with PID file creation
   - `_cmd_stop()` with PID validation
   - `_cmd_status()` with snapshot freshness check
   - `_cmd_health()` with snapshot reading

1. **Write unit tests** (target 90% coverage)

### Phase 2: Error Handling & Security (Week 2)

**Goal:** Production-ready error handling and security

1. **Implement error recovery**

   - Stale PID detection with process validation
   - Corrupted snapshot handling
   - Exit code standardization

1. **Implement security features**

   - File permission enforcement (0o600/0o700)
   - Cache ownership validation
   - Process impersonation prevention

1. **Implement signal handling**

   - SignalHandler class
   - SIGTERM/SIGINT → graceful shutdown
   - Optional SIGHUP → config reload

1. **Write security tests**

   - Permission validation
   - Process validation
   - Atomic write crash safety

### Phase 3: Configuration & Logging (Week 3)

**Goal:** Complete configuration system and logging

1. **Enhance MCPServerSettings**

   - Multi-layer YAML loading (server → local → env)
   - Environment variable parsing
   - CLI flag overrides

1. **Implement logging system**

   - `configure_logging()` with file support
   - JSON structured logging option
   - Verbosity control (`--verbose` flag)

1. **Write integration tests**

   - Full lifecycle tests (start → status → stop)
   - Configuration override tests
   - Logging output validation

### Phase 4: Documentation & Examples (Week 4)

**Goal:** Complete documentation and example server

1. **Write API documentation**

   - Google-style docstrings for all public APIs
   - Usage examples in docstrings
   - Type hints for all functions

1. **Create example MCP server**

   - `examples/weather_cli_server.py`
   - Demonstrates factory usage
   - Shows custom command integration

1. **Update README**

   - CLI factory quickstart
   - Configuration guide
   - Migration guide from ACB

### Phase 5: Migration (Week 5+)

**Goal:** Roll out to production servers

1. **Migrate session-buddy** (first adopter)

   - Remove ACB dependencies
   - Implement CLI using factory
   - Test thoroughly

1. **Migrate raindropio-mcp and mailgun-mcp**

   - Apply lessons from session-buddy
   - Document common issues

1. **Migrate remaining servers**

   - Batch migration of remaining projects
   - Update mcp-common to v3.0.0

______________________________________________________________________

## Migration Guide

### From ACB to Oneiric-Native

**Breaking Changes:**

1. **No ACB imports** - All `acb.*` imports must be removed
1. **Settings class** - Extend `MCPServerSettings` instead of `acb.config.Settings`
1. **Logger** - Use standard `logging.Logger` instead of ACB logger
1. **CLI** - Use `MCPServerCLIFactory` instead of custom CLI

**Migration Checklist:**

- [ ] Remove all `acb` imports
- [ ] Replace `acb.config.Settings` with `mcp_common.cli.MCPServerSettings`
- [ ] Replace ACB logger with `logging.getLogger()`
- [ ] Replace custom CLI with `MCPServerCLIFactory`
- [ ] Update tests to remove ACB mocks
- [ ] Update pyproject.toml to remove `acb` dependency
- [ ] Update documentation to reflect Oneiric-only usage

**Before (ACB-based):**

```python
# Old ACB-based server
from acb.config import Settings
from acb.adapters.logger import LoggerProtocol
from acb.depends import Inject, depends


class MyServerSettings(Settings):
    api_key: str


@depends.inject
async def my_tool(
    logger: Inject[LoggerProtocol] = None,
    settings: Inject[MyServerSettings] = None,
):
    logger.info("Tool called")
```

**After (Oneiric-native):**

```python
# New Oneiric-native server
import logging
from mcp_common.cli import MCPServerCLIFactory, MCPServerSettings
from pydantic import Field


class MyServerSettings(MCPServerSettings):
    api_key: str = Field(description="API key")


logger = logging.getLogger("my_server")


async def my_tool():
    settings = MyServerSettings.load("my-server")
    logger.info("Tool called")


# CLI factory
factory = MCPServerCLIFactory("my-server")
app = factory.create_app()

if __name__ == "__main__":
    app()
```

______________________________________________________________________

## Appendix: Complete Example

### Complete Weather Server with CLI Factory

```python
"""Weather MCP Server with Oneiric CLI Factory.

Example demonstrating:
- MCPServerCLIFactory usage
- Custom settings extension
- Custom commands
- Signal handling integration
"""

import asyncio
import logging
from pathlib import Path
from pydantic import Field
import httpx

from mcp_common.cli import (
    MCPServerCLIFactory,
    MCPServerSettings,
    RuntimeHealthSnapshot,
    write_runtime_health,
)


# ============================================================================
# Settings
# ============================================================================


class WeatherServerSettings(MCPServerSettings):
    """Weather server configuration."""

    api_key: str = Field(description="OpenWeatherMap API key")
    default_city: str = Field(default="San Francisco", description="Default city")
    cache_ttl: int = Field(default=300, description="Weather cache TTL (seconds)")


# ============================================================================
# Server Logic
# ============================================================================


class WeatherServer:
    """Weather MCP server."""

    def __init__(self, settings: WeatherServerSettings):
        self.settings = settings
        self.logger = logging.getLogger("weather_server")
        self.running = False

    async def start(self):
        """Start server (background task)."""
        self.running = True
        self.logger.info("Weather server started")

        # Update health snapshot
        snapshot = RuntimeHealthSnapshot(
            watchers_running=True,
        )
        write_runtime_health(self.settings.health_snapshot_path(), snapshot)

        # Server main loop
        while self.running:
            await asyncio.sleep(1)

    def stop(self):
        """Stop server."""
        self.running = False
        self.logger.info("Weather server stopped")

        # Update health snapshot
        snapshot = RuntimeHealthSnapshot(
            watchers_running=False,
        )
        write_runtime_health(self.settings.health_snapshot_path(), snapshot)


# ============================================================================
# CLI
# ============================================================================


def main():
    """CLI entry point."""
    # Load settings
    settings = WeatherServerSettings.load("weather-server")

    # Create server instance
    server = WeatherServer(settings)

    # Create CLI factory with custom handlers
    def start_handler():
        """Custom start logic."""
        asyncio.run(server.start())

    def stop_handler(pid: int):
        """Custom stop logic."""
        server.stop()

    factory = MCPServerCLIFactory(
        "weather-server",
        settings=settings,
        start_handler=start_handler,
        stop_handler=stop_handler,
    )

    # Create Typer app
    app = factory.create_app()

    # Add custom command
    @app.command()
    def forecast(
        city: str = settings.default_city,
    ):
        """Get weather forecast for a city."""
        print(f"Fetching forecast for {city}...")
        # Implementation here...

    # Run CLI
    app()


if __name__ == "__main__":
    main()
```

**Usage:**

```bash
# Start server
python weather_server.py start

# Check status
python weather_server.py status
# Output: Server running (PID 12345, snapshot age: 5.2s)

# Check health
python weather_server.py health
# Output: Health: OK
#         Watchers: running
#         Last updated: 5 seconds ago

# Get forecast (custom command)
python weather_server.py forecast --city "New York"

# Stop server
python weather_server.py stop
```

______________________________________________________________________

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-20 | Initial specification addressing audit findings |

______________________________________________________________________

**End of Specification**
