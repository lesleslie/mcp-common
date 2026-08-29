"""Tests for MCPServerCLIFactory.register_lifecycle_handlers (Plan Task 3.2.6).

register_lifecycle_handlers lets a OneiricCLIBase subclass add the
standard lifecycle commands (start/stop/restart/status/health) to its
own typer.Typer instead of using create_app().
"""
from __future__ import annotations

import typer
from typer.testing import CliRunner

from mcp_common.cli.factory import MCPServerCLIFactory


def test_register_lifecycle_handlers_mounts_start_stop_etc() -> None:
    """All five lifecycle commands should appear in the app's --help output."""
    app = typer.Typer()
    factory = MCPServerCLIFactory(server_name="test-server")
    factory.register_lifecycle_handlers(app)
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    for cmd in ("start", "stop", "restart", "status", "health"):
        assert cmd in result.output, f"missing '{cmd}' in: {result.output!r}"


def test_create_handlers_returns_dict() -> None:
    """create_handlers returns the five lifecycle handler bindings."""
    factory = MCPServerCLIFactory(server_name="test-server")
    handlers = factory.create_handlers()
    assert set(handlers) == {"start", "stop", "restart", "status", "health"}
    for name, handler in handlers.items():
        assert callable(handler), f"{name} handler is not callable"