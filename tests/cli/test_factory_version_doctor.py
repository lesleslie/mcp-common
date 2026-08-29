"""Tests for version + doctor commands in MCPServerCLIFactory."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner
from importlib.metadata import PackageNotFoundError

from mcp_common.cli.factory import MCPServerCLIFactory


@pytest.fixture
def factory():
    return MCPServerCLIFactory(server_name="test-server")


@pytest.fixture
def mcp_factory():
    return MCPServerCLIFactory(server_name="test-mcp-server", use_mcp_subcommand=True)


def test_help_lists_version_and_doctor(factory):
    runner = CliRunner()
    result = runner.invoke(factory.create_app(), ["--help"])
    assert result.exit_code == 0
    assert "version" in result.output
    assert "doctor" in result.output


def test_version_command_prints_installed_version(factory, monkeypatch):
    monkeypatch.setattr("importlib.metadata.version", lambda name: "1.2.3")
    runner = CliRunner()
    result = runner.invoke(factory.create_app(), ["version"])
    assert result.exit_code == 0
    assert "test-server: 1.2.3" in result.output


def test_version_handles_package_not_found(factory, monkeypatch):
    def fake_version(name):
        raise PackageNotFoundError(name)
    monkeypatch.setattr("importlib.metadata.version", fake_version)
    runner = CliRunner()
    result = runner.invoke(factory.create_app(), ["version"])
    assert result.exit_code == 0
    assert "test-server: (not installed)" in result.output


def test_doctor_emits_json_with_checks(factory, tmp_path, monkeypatch):
    monkeypatch.setattr(factory.settings, "cache_root", tmp_path)
    runner = CliRunner()
    result = runner.invoke(factory.create_app(), ["doctor", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "checks" in payload
    assert "settings" in payload["checks"]
    assert "cache_writable" in payload["checks"]
    assert payload["checks"]["settings"]["status"] == "ok"


def test_doctor_emits_text_lines(factory, tmp_path, monkeypatch):
    monkeypatch.setattr(factory.settings, "cache_root", tmp_path)
    runner = CliRunner()
    result = runner.invoke(factory.create_app(), ["doctor"])
    assert result.exit_code == 0
    assert "settings: ok" in result.output
    assert "cache_writable: ok" in result.output


def test_doctor_with_use_mcp_subcommand(mcp_factory, tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_factory.settings, "cache_root", tmp_path)
    runner = CliRunner()
    result = runner.invoke(mcp_factory.create_app(), ["mcp", "doctor"])
    assert result.exit_code == 0
    assert "settings: ok" in result.output


def test_doctor_handles_unwritable_cache_root(factory, tmp_path, monkeypatch):
    """Exercise the OSError branch: cache_root that can't be created."""
    # Point cache_root at a path under a non-writable parent.
    readonly_parent = tmp_path / "readonly"
    readonly_parent.mkdir()
    readonly_parent.chmod(0o555)
    unwritable = readonly_parent / "cache"
    monkeypatch.setattr(factory.settings, "cache_root", unwritable)
    runner = CliRunner()
    result = runner.invoke(factory.create_app(), ["doctor", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["checks"]["cache_writable"]["status"] == "error"
    assert "cache_writable" in payload["checks"]


def test_doctor_json_flag_is_local_typer_option(factory, tmp_path, monkeypatch):
    """Pin contract: --json is a per-command Typer option on factory commands.

    The factory does NOT register a global --json callback (that's a
    OneiricCLIBase feature). This test verifies the --json flag works
    on `doctor` via Typer's local-option parsing, not via ctx.obj.

    NOTE: Typer 0.27 parses per-command options only AFTER the
    subcommand name (so ``[--json, doctor]`` is rejected with exit 2,
    matching the existing ``["status", "--json"]`` factory convention).
    """
    monkeypatch.setattr(factory.settings, "cache_root", tmp_path)
    runner = CliRunner()
    # `--json` placed AFTER the subcommand (Typer local-option context).
    result = runner.invoke(factory.create_app(), ["doctor", "--json"])
    assert result.exit_code == 0
    # Output must be parseable JSON.
    payload = json.loads(result.output)
    assert "checks" in payload
