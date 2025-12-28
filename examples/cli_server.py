"""Example Oneiric-native MCP server using CLI factory for lifecycle management.

This example demonstrates:
- MCPServerCLIFactory for standardized CLI (start/stop/restart/status/health)
- MCPServerSettings with YAML + environment variable configuration
- Custom start/stop handlers for server lifecycle
- Health probe integration
- Signal handling for graceful shutdown
- Custom CLI commands via Typer

Run this example:
    python examples/cli_server.py start
    python examples/cli_server.py status
    python examples/cli_server.py health
    python examples/cli_server.py stop

Or install and run:
    pip install -e .
    cli-server start
"""

from __future__ import annotations

import time

import typer

from mcp_common.cli import (
    MCPServerCLIFactory,
    MCPServerSettings,
    RuntimeHealthSnapshot,
)
from mcp_common.cli.health import load_runtime_health


class ExampleServerSettings(MCPServerSettings):
    """Example server settings extending MCPServerSettings.

    Configuration loading order (later overrides earlier):
    1. Default values (below)
    2. settings/example-server.yaml (committed)
    3. settings/local.yaml (gitignored, for development)
    4. Environment variables: MCP_SERVER_{FIELD}

    Example YAML (settings/example-server.yaml):
        server_name: "Example MCP Server"
        cache_root: .oneiric_cache
        health_ttl_seconds: 60.0
        log_level: INFO
        custom_port: 8080
        custom_feature_enabled: true

    Example env vars:
        export MCP_SERVER_LOG_LEVEL=DEBUG
        export MCP_SERVER_CUSTOM_PORT=9090
    """

    # Custom server-specific fields
    custom_port: int = 8080
    custom_feature_enabled: bool = True


# Global server state (simulating a running server)
server_state = {
    "running": False,
    "started_at": None,
    "request_count": 0,
}


def start_handler() -> None:
    """Custom start handler - called after PID file created.

    This is where you would:
    - Initialize your MCP server (FastMCP, etc.)
    - Start background tasks
    - Connect to databases
    - Open file handles
    """

    # Simulate server initialization
    server_state["running"] = True
    server_state["started_at"] = time.time()
    server_state["request_count"] = 0

    # For this example, we'll just sleep to keep the process alive
    try:
        while True:
            time.sleep(1)
            # Simulate processing requests
            if server_state["running"]:
                server_state["request_count"] += 1
    except KeyboardInterrupt:
        pass


def stop_handler(_pid: int) -> None:
    """Custom stop handler - called before PID file removed.

    This is where you would:
    - Gracefully shutdown MCP server
    - Close database connections
    - Flush buffers
    - Clean up resources

    Args:
        _pid: Process ID being stopped (unused in this example)
    """

    # Simulate cleanup
    server_state["running"] = False


def health_probe_handler() -> RuntimeHealthSnapshot:
    """Custom health probe - called by `cli-server health --probe`.

    This is where you would:
    - Check database connectivity
    - Verify external API health
    - Check resource usage
    - Validate component states

    Returns:
        RuntimeHealthSnapshot with current health state
    """
    # In a real server, you'd check actual health here
    is_healthy = server_state["running"]

    return RuntimeHealthSnapshot(
        orchestrator_pid=None,  # Will be filled by CLI
        watchers_running=is_healthy,
        remote_enabled=False,
        lifecycle_state={
            "started_at": server_state.get("started_at"),
            "uptime_seconds": (
                time.time() - server_state["started_at"] if server_state.get("started_at") else 0
            ),
        },
        activity_state={
            "requests_handled": server_state.get("request_count", 0),
            "current_status": "healthy" if is_healthy else "degraded",
        },
    )


def _create_config_command(app: typer.Typer, settings: MCPServerSettings) -> None:
    """Create the config command for the CLI app."""

    @app.command()
    def config() -> None:
        """Display current server configuration."""

        # Show custom settings if we have them
        if isinstance(settings, ExampleServerSettings):
            pass
        else:
            pass


def _create_paths_command(app: typer.Typer, settings: MCPServerSettings) -> None:
    """Create the paths command for the CLI app."""

    @app.command()
    def paths() -> None:
        """Display cache file paths."""

        # Check if files exist
        for _name, path in [
            ("PID", settings.pid_path()),
            ("Health", settings.health_snapshot_path()),
            ("Telemetry", settings.telemetry_snapshot_path()),
        ]:
            "✅ exists" if path.exists() else "❌ missing"


def _create_stats_command(app: typer.Typer, settings: MCPServerSettings) -> None:
    """Create the stats command for the CLI app."""

    @app.command()
    def stats() -> None:
        """Display server statistics (requires server running)."""
        snapshot_path = settings.health_snapshot_path()

        if not snapshot_path.exists():
            raise typer.Exit(1)

        snapshot = load_runtime_health(snapshot_path)

        if snapshot.lifecycle_state:
            for _key, _value in snapshot.lifecycle_state.items():
                pass

        if snapshot.activity_state:
            for _key, _value in snapshot.activity_state.items():
                pass


def create_cli() -> typer.Typer:
    """Create CLI application with lifecycle commands + custom commands.

    Returns:
        Typer app with all commands registered
    """
    # Load settings (YAML + env vars)
    settings = MCPServerSettings.load("example-server")

    # Create CLI factory with custom handlers
    factory = MCPServerCLIFactory(
        server_name="example-server",
        settings=settings,
        start_handler=start_handler,
        stop_handler=stop_handler,
        health_probe_handler=health_probe_handler,
    )

    # Create Typer app with standard lifecycle commands
    app = factory.create_app()

    # Add custom server-specific commands
    _create_config_command(app, settings)
    _create_paths_command(app, settings)
    _create_stats_command(app, settings)

    return app


def main() -> None:
    """Main entry point."""
    app = create_cli()
    app()


if __name__ == "__main__":
    main()
