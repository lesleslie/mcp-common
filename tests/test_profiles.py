"""Tests for mcp_common.profiles — MinimalServer, StandardServer, FullServer."""

from __future__ import annotations

import re
from typing import Any

import pytest

from mcp_common.profiles import FullServer, MinimalServer, StandardServer
from mcp_common.profiles.full import (
    FullServerSettings,
)
from mcp_common.profiles.minimal import (
    MinimalServerSettings,
)
from mcp_common.profiles.standard import (
    StandardServerSettings,
)


# ---------------------------------------------------------------------------
# MinimalServer
# ---------------------------------------------------------------------------


class TestMinimalServerInit:
    """Test MinimalServer construction."""

    def test_default_name(self) -> None:
        server = MinimalServer(name="test-minimal")
        assert server.name == "test-minimal"

    def test_default_tools_dict_empty(self) -> None:
        server = MinimalServer(name="test-minimal")
        assert server.list_tools() == []

    def test_no_resources_attribute(self) -> None:
        server = MinimalServer(name="test-minimal")
        assert not hasattr(server, "list_resources")

    def test_no_prompts_attribute(self) -> None:
        server = MinimalServer(name="test-minimal")
        assert not hasattr(server, "list_prompts")

    def test_settings_created_by_default(self) -> None:
        server = MinimalServer(name="test-minimal")
        assert isinstance(server.settings, MinimalServerSettings)

    def test_custom_settings_accepted(self) -> None:
        custom = MinimalServerSettings(server_name="Custom")
        server = MinimalServer(name="test-minimal", settings=custom)
        assert server.settings is custom

    def test_settings_inherits_mcp_base_settings(self) -> None:
        from mcp_common.config import MCPBaseSettings

        assert issubclass(MinimalServerSettings, MCPBaseSettings)


class TestMinimalServerToolRegistration:
    """Test tool decorator on MinimalServer."""

    def test_register_tool_with_decorator(self) -> None:
        server = MinimalServer(name="test-minimal")

        @server.tool()
        def my_tool() -> str:
            return "hello"

        assert "my_tool" in server.list_tools()

    def test_register_tool_with_custom_name(self) -> None:
        server = MinimalServer(name="test-minimal")

        @server.tool(name="custom-name")
        def some_func() -> str:
            return "hello"

        assert "custom-name" in server.list_tools()

    def test_get_tool_returns_function(self) -> None:
        server = MinimalServer(name="test-minimal")

        @server.tool()
        def my_tool() -> str:
            return "hello"

        assert server.get_tool("my_tool") is my_tool

    def test_get_tool_missing_returns_none(self) -> None:
        server = MinimalServer(name="test-minimal")
        assert server.get_tool("nonexistent") is None

    def test_register_multiple_tools(self) -> None:
        server = MinimalServer(name="test-minimal")

        @server.tool()
        def tool_a() -> None:
            pass

        @server.tool()
        def tool_b() -> None:
            pass

        assert set(server.list_tools()) == {"tool_a", "tool_b"}


class TestMinimalServerHealthCheck:
    """Test health_check method on MinimalServer."""

    def test_returns_healthy_status(self) -> None:
        server = MinimalServer(name="test-minimal")
        health = server.health_check()
        assert health["status"] == "healthy"

    def test_includes_server_name(self) -> None:
        server = MinimalServer(name="my-test-server")
        health = server.health_check()
        assert health["server"] == "my-test-server"

    def test_includes_tool_count(self) -> None:
        server = MinimalServer(name="test-minimal")

        @server.tool()
        def t1() -> None:
            pass

        @server.tool()
        def t2() -> None:
            pass

        health = server.health_check()
        assert health["tools"] == 2

    def test_zero_tools(self) -> None:
        server = MinimalServer(name="test-minimal")
        health = server.health_check()
        assert health["tools"] == 0

    def test_keys_are_basic(self) -> None:
        server = MinimalServer(name="test-minimal")
        health = server.health_check()
        assert set(health.keys()) == {"status", "server", "tools"}


class TestMinimalServerRun:
    """Test that run() raises NotImplementedError."""

    def test_run_raises_not_implemented(self) -> None:
        server = MinimalServer(name="test-minimal")
        with pytest.raises(NotImplementedError, match="MinimalServer.run"):
            server.run()

    def test_run_kwargs_ignored_in_error(self) -> None:
        server = MinimalServer(name="test-minimal")
        with pytest.raises(NotImplementedError):
            server.run(host="localhost", port=8000)


# ---------------------------------------------------------------------------
# StandardServer
# ---------------------------------------------------------------------------


class TestStandardServerInit:
    """Test StandardServer construction."""

    def test_default_name(self) -> None:
        server = StandardServer(name="test-standard")
        assert server.name == "test-standard"

    def test_default_description(self) -> None:
        server = StandardServer(name="test-standard")
        assert server.description == "Standard MCP Server"

    def test_custom_description(self) -> None:
        server = StandardServer(name="test-standard", description="My desc")
        assert server.description == "My desc"

    def test_empty_tools_and_resources(self) -> None:
        server = StandardServer(name="test-standard")
        assert server.list_tools() == []
        assert server.list_resources() == []

    def test_settings_created_by_default(self) -> None:
        server = StandardServer(name="test-standard")
        assert isinstance(server.settings, StandardServerSettings)

    def test_custom_settings_accepted(self) -> None:
        custom = StandardServerSettings(server_name="Custom")
        server = StandardServer(name="test-standard", settings=custom)
        assert server.settings is custom

    def test_no_prompts_attribute(self) -> None:
        server = StandardServer(name="test-standard")
        assert not hasattr(server, "list_prompts")


class TestStandardServerToolRegistration:
    """Test tool decorator on StandardServer."""

    def test_register_tool(self) -> None:
        server = StandardServer(name="test-standard")

        @server.tool()
        def search(query: str) -> dict:
            return {}

        assert "search" in server.list_tools()

    def test_register_tool_custom_name(self) -> None:
        server = StandardServer(name="test-standard")

        @server.tool(name="my-search")
        def search() -> None:
            pass

        assert "my-search" in server.list_tools()

    def test_get_tool_returns_function(self) -> None:
        server = StandardServer(name="test-standard")

        @server.tool()
        def my_func() -> str:
            return "ok"

        assert server.get_tool("my_func") is my_func

    def test_get_tool_missing_returns_none(self) -> None:
        server = StandardServer(name="test-standard")
        assert server.get_tool("nonexistent") is None


class TestStandardServerResourceRegistration:
    """Test resource decorator on StandardServer."""

    def test_register_resource(self) -> None:
        server = StandardServer(name="test-standard")

        @server.resource("config://{name}")
        def get_config(name: str) -> dict:
            return {}

        assert "config://{name}" in server.list_resources()

    def test_get_resource_returns_function(self) -> None:
        server = StandardServer(name="test-standard")

        @server.resource("data://{table}")
        def get_data(table: str) -> str:
            return ""

        assert server.get_resource("data://{table}") is get_data

    def test_get_resource_missing_returns_none(self) -> None:
        server = StandardServer(name="test-standard")
        assert server.get_resource("nonexistent") is None

    def test_register_multiple_resources(self) -> None:
        server = StandardServer(name="test-standard")

        @server.resource("config://{name}")
        def r1(name: str) -> None:
            pass

        @server.resource("data://{table}")
        def r2(table: str) -> None:
            pass

        assert set(server.list_resources()) == {"config://{name}", "data://{table}"}


class TestStandardServerHealthCheck:
    """Test health_check method on StandardServer."""

    def test_returns_healthy(self) -> None:
        server = StandardServer(name="test-standard")
        assert server.health_check()["status"] == "healthy"

    def test_includes_server_name(self) -> None:
        server = StandardServer(name="my-std")
        assert server.health_check()["server"] == "my-std"

    def test_includes_description(self) -> None:
        server = StandardServer(name="s", description="Test Desc")
        assert server.health_check()["description"] == "Test Desc"

    def test_includes_tool_and_resource_counts(self) -> None:
        server = StandardServer(name="s")

        @server.tool()
        def t1() -> None:
            pass

        @server.resource("r://{x}")
        def r1(x: str) -> None:
            pass

        health = server.health_check()
        assert health["tools"] == 1
        assert health["resources"] == 1

    def test_expected_keys(self) -> None:
        server = StandardServer(name="s")
        health = server.health_check()
        assert set(health.keys()) == {"status", "server", "description", "tools", "resources"}


class TestStandardServerRun:
    """Test that run() raises NotImplementedError."""

    def test_run_raises_not_implemented(self) -> None:
        server = StandardServer(name="test-standard")
        with pytest.raises(NotImplementedError, match="StandardServer.run"):
            server.run()


# ---------------------------------------------------------------------------
# FullServer
# ---------------------------------------------------------------------------


class TestFullServerInit:
    """Test FullServer construction."""

    def test_default_name(self) -> None:
        server = FullServer(name="test-full")
        assert server.name == "test-full"

    def test_default_description(self) -> None:
        server = FullServer(name="test-full")
        assert server.description == "Full MCP Server"

    def test_custom_description(self) -> None:
        server = FullServer(name="test-full", description="Prod server")
        assert server.description == "Prod server"

    def test_default_auth_is_none(self) -> None:
        server = FullServer(name="test-full")
        assert server.auth is None

    def test_default_telemetry_is_none(self) -> None:
        server = FullServer(name="test-full")
        assert server.telemetry is None

    def test_auth_backend_stored(self) -> None:
        backend = object()  # use plain object as a stand-in
        server = FullServer(name="test-full", auth=backend)  # type: ignore[arg-type]
        assert server.auth is backend

    def test_telemetry_backend_stored(self) -> None:
        backend = object()
        server = FullServer(name="test-full", telemetry=backend)  # type: ignore[arg-type]
        assert server.telemetry is backend

    def test_settings_created_by_default(self) -> None:
        server = FullServer(name="test-full")
        assert isinstance(server.settings, FullServerSettings)

    def test_custom_settings_accepted(self) -> None:
        custom = FullServerSettings(server_name="Custom")
        server = FullServer(name="test-full", settings=custom)
        assert server.settings is custom

    def test_empty_tools_resources_prompts(self) -> None:
        server = FullServer(name="test-full")
        assert server.list_tools() == []
        assert server.list_resources() == []
        assert server.list_prompts() == []


class TestFullServerToolRegistration:
    """Test tool decorator on FullServer."""

    def test_register_tool(self) -> None:
        server = FullServer(name="test-full")

        @server.tool()
        def process(data: dict) -> dict:
            return data

        assert "process" in server.list_tools()

    def test_register_tool_custom_name(self) -> None:
        server = FullServer(name="test-full")

        @server.tool(name="custom")
        def some_func() -> None:
            pass

        assert "custom" in server.list_tools()

    def test_get_tool_returns_function(self) -> None:
        server = FullServer(name="test-full")

        @server.tool()
        def my_tool() -> str:
            return "result"

        assert server.get_tool("my_tool") is my_tool

    def test_get_tool_missing_returns_none(self) -> None:
        server = FullServer(name="test-full")
        assert server.get_tool("nonexistent") is None


class TestFullServerResourceRegistration:
    """Test resource decorator on FullServer."""

    def test_register_resource(self) -> None:
        server = FullServer(name="test-full")

        @server.resource("data://{id}")
        def get_data(id: str) -> str:
            return ""

        assert "data://{id}" in server.list_resources()

    def test_get_resource_returns_function(self) -> None:
        server = FullServer(name="test-full")

        @server.resource("cfg://{n}")
        def cfg(n: str) -> dict:
            return {}

        assert server.get_resource("cfg://{n}") is cfg

    def test_get_resource_missing_returns_none(self) -> None:
        server = FullServer(name="test-full")
        assert server.get_resource("nope") is None


class TestFullServerPromptRegistration:
    """Test prompt decorator on FullServer."""

    def test_register_prompt(self) -> None:
        server = FullServer(name="test-full")

        @server.prompt("analyze")
        def analyze_prompt(data: str) -> str:
            return f"Analyze: {data}"

        assert "analyze" in server.list_prompts()

    def test_register_prompt_defaults_to_function_name(self) -> None:
        server = FullServer(name="test-full")

        @server.prompt()
        def summarize() -> str:
            return "summary"

        assert "summarize" in server.list_prompts()

    def test_get_prompt_returns_function(self) -> None:
        server = FullServer(name="test-full")

        @server.prompt("review")
        def review_fn() -> str:
            return "ok"

        assert server.get_prompt("review") is review_fn

    def test_get_prompt_missing_returns_none(self) -> None:
        server = FullServer(name="test-full")
        assert server.get_prompt("nonexistent") is None


class TestFullServerHealthCheck:
    """Test health_check method on FullServer."""

    def test_returns_healthy(self) -> None:
        server = FullServer(name="test-full")
        assert server.health_check()["status"] == "healthy"

    def test_includes_server_name(self) -> None:
        server = FullServer(name="prod-server")
        assert server.health_check()["server"] == "prod-server"

    def test_includes_description(self) -> None:
        server = FullServer(name="f", description="My Full Server")
        assert server.health_check()["description"] == "My Full Server"

    def test_auth_disabled_when_none(self) -> None:
        server = FullServer(name="f")
        health = server.health_check()
        assert health["auth"]["enabled"] is False
        assert health["auth"]["type"] is None

    def test_auth_enabled_when_backend_set(self) -> None:
        from mcp_common.profiles.full import AuthBackend

        class MyAuth(AuthBackend):
            pass

        server = FullServer(name="f", auth=MyAuth())
        health = server.health_check()
        assert health["auth"]["enabled"] is True
        assert health["auth"]["type"] == "MyAuth"

    def test_telemetry_disabled_when_none(self) -> None:
        server = FullServer(name="f")
        health = server.health_check()
        assert health["telemetry"]["enabled"] is False
        assert health["telemetry"]["type"] is None

    def test_telemetry_enabled_when_backend_set(self) -> None:
        from mcp_common.profiles.full import TelemetryBackend

        class MyTelemetry(TelemetryBackend):
            pass

        server = FullServer(name="f", telemetry=MyTelemetry())
        health = server.health_check()
        assert health["telemetry"]["enabled"] is True
        assert health["telemetry"]["type"] == "MyTelemetry"

    def test_includes_tool_resource_prompt_counts(self) -> None:
        server = FullServer(name="f")

        @server.tool()
        def t1() -> None:
            pass

        @server.resource("r://{x}")
        def r1(x: str) -> None:
            pass

        @server.prompt("p1")
        def p1() -> str:
            return ""

        health = server.health_check()
        assert health["tools"] == 1
        assert health["resources"] == 1
        assert health["prompts"] == 1

    def test_expected_keys(self) -> None:
        server = FullServer(name="f")
        health = server.health_check()
        expected_keys = {
            "status",
            "server",
            "description",
            "tools",
            "resources",
            "prompts",
            "auth",
            "telemetry",
            "workers",
        }
        assert set(health.keys()) == expected_keys

    def test_workers_from_settings(self) -> None:
        server = FullServer(name="f")
        assert server.health_check()["workers"] == 1  # default

    def test_workers_custom_settings(self) -> None:
        custom = FullServerSettings(server_name="Custom", workers=8)
        server = FullServer(name="f", settings=custom)
        assert server.health_check()["workers"] == 8


class TestFullServerRun:
    """Test that run() raises NotImplementedError."""

    def test_run_raises_not_implemented(self) -> None:
        server = FullServer(name="test-full")
        with pytest.raises(NotImplementedError, match="FullServer.run"):
            server.run()

    def test_run_with_workers_raises(self) -> None:
        server = FullServer(name="test-full")
        with pytest.raises(NotImplementedError):
            server.run(workers=4)


# ---------------------------------------------------------------------------
# Settings classes
# ---------------------------------------------------------------------------


class TestMinimalServerSettings:
    """Test MinimalServerSettings configuration."""

    def test_inherits_mcp_base_settings(self) -> None:
        # MinimalServerSettings is a Pydantic model subclass of MCPBaseSettings
        s = MinimalServerSettings()
        assert hasattr(s, "server_name")
        assert hasattr(s, "log_level")
        assert hasattr(s, "enable_debug_mode")

    def test_defaults(self) -> None:
        s = MinimalServerSettings()
        assert s.server_name == "MCP Server"
        assert s.log_level == "INFO"
        assert s.enable_debug_mode is False


class TestStandardServerSettings:
    """Test StandardServerSettings configuration."""

    def test_inherits_mcp_base_settings(self) -> None:
        s = StandardServerSettings()
        assert hasattr(s, "server_name")
        assert hasattr(s, "log_level")

    def test_default_description(self) -> None:
        s = StandardServerSettings()
        assert s.description == "Standard MCP Server"

    def test_enable_resources_default(self) -> None:
        s = StandardServerSettings()
        assert s.enable_resources is True

    def test_custom_description(self) -> None:
        s = StandardServerSettings(description="Custom")
        assert s.description == "Custom"

    def test_custom_enable_resources(self) -> None:
        s = StandardServerSettings(enable_resources=False)
        assert s.enable_resources is False


class TestFullServerSettings:
    """Test FullServerSettings configuration."""

    def test_inherits_mcp_base_settings(self) -> None:
        s = FullServerSettings()
        assert hasattr(s, "server_name")
        assert hasattr(s, "log_level")

    def test_default_description(self) -> None:
        s = FullServerSettings()
        assert s.description == "Full MCP Server"

    def test_auth_enabled_default(self) -> None:
        s = FullServerSettings()
        assert s.auth_enabled is False

    def test_telemetry_enabled_default(self) -> None:
        s = FullServerSettings()
        assert s.telemetry_enabled is False

    def test_workers_default(self) -> None:
        s = FullServerSettings()
        assert s.workers == 1

    def test_enable_prompts_default(self) -> None:
        s = FullServerSettings()
        assert s.enable_prompts is True

    def test_custom_values(self) -> None:
        s = FullServerSettings(
            description="Custom Full",
            auth_enabled=True,
            telemetry_enabled=True,
            workers=4,
            enable_prompts=False,
        )
        assert s.description == "Custom Full"
        assert s.auth_enabled is True
        assert s.telemetry_enabled is True
        assert s.workers == 4
        assert s.enable_prompts is False


# ---------------------------------------------------------------------------
# __init__.py exports
# ---------------------------------------------------------------------------


class TestPackageExports:
    """Test that __init__.py re-exports all three server classes."""

    def test_minimal_server_importable(self) -> None:
        from mcp_common.profiles import MinimalServer as MS

        assert MS is MinimalServer

    def test_standard_server_importable(self) -> None:
        from mcp_common.profiles import StandardServer as SS

        assert SS is StandardServer

    def test_full_server_importable(self) -> None:
        from mcp_common.profiles import FullServer as FS

        assert FS is FullServer

    def test_all_exports(self) -> None:
        import mcp_common.profiles as mod

        assert set(mod.__all__) == {"MinimalServer", "StandardServer", "FullServer"}


# ---------------------------------------------------------------------------
# Profile feature progression (minimal < standard < full)
# ---------------------------------------------------------------------------


class TestFeatureProgression:
    """Verify that each profile layer adds features on top of the previous."""

    def test_minimal_has_tools_only(self) -> None:
        server = MinimalServer(name="m")
        assert hasattr(server, "list_tools")
        assert not hasattr(server, "list_resources")
        assert not hasattr(server, "list_prompts")

    def test_standard_adds_resources(self) -> None:
        server = StandardServer(name="s")
        assert hasattr(server, "list_tools")
        assert hasattr(server, "list_resources")
        assert not hasattr(server, "list_prompts")

    def test_full_adds_prompts_and_backends(self) -> None:
        server = FullServer(name="f")
        assert hasattr(server, "list_tools")
        assert hasattr(server, "list_resources")
        assert hasattr(server, "list_prompts")
        assert hasattr(server, "auth")
        assert hasattr(server, "telemetry")

    def test_all_share_tool_decorator_pattern(self) -> None:
        """Tool registration works the same way across all profiles."""

        def register_tool(server: Any, name: str) -> None:
            @server.tool(name=name)
            def dummy() -> None:
                pass

        m = MinimalServer(name="m")
        s = StandardServer(name="s")
        f = FullServer(name="f")

        register_tool(m, "t1")
        register_tool(s, "t1")
        register_tool(f, "t1")

        assert "t1" in m.list_tools()
        assert "t1" in s.list_tools()
        assert "t1" in f.list_tools()

    def test_health_check_complexity_increases(self) -> None:
        """Each profile returns more keys in its health check."""
        m = MinimalServer(name="m").health_check()
        s = StandardServer(name="s").health_check()
        f = FullServer(name="f").health_check()

        assert len(set(m.keys())) < len(set(s.keys())) < len(set(f.keys()))


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and defensive checks."""

    def test_duplicate_tool_registration_overwrites(self) -> None:
        server = MinimalServer(name="m")

        @server.tool()
        def my_tool() -> str:
            return "first"

        first_ref = server.get_tool("my_tool")

        @server.tool()
        def my_tool() -> str:  # noqa: F811 — intentional redefinition
            return "second"

        # The second registration overwrites the first
        assert server.get_tool("my_tool") is not first_ref

    def test_tool_decorator_returns_original_function(self) -> None:
        server = MinimalServer(name="m")

        def original() -> str:
            return "hello"

        decorated = server.tool()(original)
        assert decorated is original

    def test_resource_decorator_returns_original_function(self) -> None:
        server = StandardServer(name="s")

        def original() -> str:
            return "hello"

        decorated = server.resource("r://{x}")(original)
        assert decorated is original

    def test_prompt_decorator_returns_original_function(self) -> None:
        server = FullServer(name="f")

        def original() -> str:
            return "hello"

        decorated = server.prompt("p")(original)
        assert decorated is original

    def test_full_server_with_both_backends(self) -> None:
        from mcp_common.profiles.full import AuthBackend, TelemetryBackend

        class FakeAuth(AuthBackend):
            pass

        class FakeTelemetry(TelemetryBackend):
            pass

        server = FullServer(
            name="f",
            auth=FakeAuth(),
            telemetry=FakeTelemetry(),
        )
        health = server.health_check()
        assert health["auth"]["enabled"] is True
        assert health["telemetry"]["enabled"] is True
