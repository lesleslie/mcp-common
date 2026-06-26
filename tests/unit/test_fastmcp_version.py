"""Regression tests for Plan 7 Phase 1 (mcp-common foundation).

Plan 7 requires every FastMCP consumer in the Bodai ecosystem to run on
FastMCP 3.4.0 or newer. mcp-common is the foundation package, so we
enforce the floor here with a version-assertion regression test and a
small suite of re-export surface tests.
"""

from __future__ import annotations

import importlib.util

import pytest


def test_fastmcp_version_meets_plan7_baseline() -> None:
    """FastMCP must be >=3.4.0 (Plan 7 floor).

    Bumping this threshold is a deliberate decision. Drop it only if a
    new sub-plan lowers the bar for the whole ecosystem.
    """
    import fastmcp
    from packaging.version import Version

    installed = Version(fastmcp.__version__)
    baseline = Version("3.4.0")
    if installed < baseline:
        msg = (
            f"Plan 7 requires fastmcp>={baseline}, found {installed}. "
            "Bump the pin in pyproject.toml and update this assertion."
        )
        raise AssertionError(msg)


def test_fastmcp_module_importable() -> None:
    """Sanity check: fastmcp must be importable in the test environment."""
    spec = importlib.util.find_spec("fastmcp")
    if spec is None:
        msg = "fastmcp must be installed for mcp-common"
        raise AssertionError(msg)


def test_rate_limiting_module_importable() -> None:
    """The docstring of mcp_common.server.availability claims the
    fastmcp.server.middleware.rate_limiting module exists. Verify it."""
    spec = importlib.util.find_spec("fastmcp.server.middleware.rate_limiting")
    if spec is None:
        msg = (
            "fastmcp.server.middleware.rate_limiting must exist on "
            "FastMCP 3.4+; check the docstring of "
            "mcp_common.server.availability.check_rate_limiting_available."
        )
        raise AssertionError(msg)


class TestMcpCommonFastmcpReexports:
    """Verify the centralized re-export surface from mcp_common.fastmcp."""

    def test_module_importable(self) -> None:
        spec = importlib.util.find_spec("mcp_common.fastmcp")
        if spec is None:
            msg = "mcp_common.fastmcp package must exist (Plan 7 Phase 1)"
            raise AssertionError(msg)

    def test_reexports_fastmcp_class(self) -> None:
        from mcp_common.fastmcp import FastMCP
        from fastmcp import FastMCP as RawFastMCP

        if FastMCP is not RawFastMCP:
            msg = "mcp_common.fastmcp.FastMCP must be the same class as fastmcp.FastMCP"
            raise AssertionError(msg)

    def test_reexports_context_class(self) -> None:
        from mcp_common.fastmcp import Context
        from fastmcp import Context as RawContext

        if Context is not RawContext:
            msg = "mcp_common.fastmcp.Context must be the same class as fastmcp.Context"
            raise AssertionError(msg)

    def test_reexports_middleware_base(self) -> None:
        from mcp_common.fastmcp import Middleware
        from fastmcp.server.middleware import Middleware as RawMiddleware

        if Middleware is not RawMiddleware:
            msg = (
                "mcp_common.fastmcp.Middleware must be the same class as "
                "fastmcp.server.middleware.Middleware"
            )
            raise AssertionError(msg)

    def test_reexports_middleware_context(self) -> None:
        from mcp_common.fastmcp import MiddlewareContext
        from fastmcp.server.middleware import MiddlewareContext as RawContext

        if MiddlewareContext is not RawContext:
            msg = (
                "mcp_common.fastmcp.MiddlewareContext must be the same "
                "class as fastmcp.server.middleware.MiddlewareContext"
            )
            raise AssertionError(msg)

    def test_reexports_oneiric_mcp_config(self) -> None:
        from mcp_common.fastmcp import OneiricMCPConfig
        from oneiric.core.config import OneiricMCPConfig as RawConfig

        if OneiricMCPConfig is not RawConfig:
            msg = (
                "mcp_common.fastmcp.OneiricMCPConfig must be the same "
                "class as oneiric.core.config.OneiricMCPConfig"
            )
            raise AssertionError(msg)

    def test_reexport_rate_limiting_middleware(self) -> None:
        """The plan also wants RateLimitingMiddleware re-exported so
        consumers don't have to know the deep path."""
        from mcp_common.fastmcp import RateLimitingMiddleware

        # The class itself is sufficient — a deeper behavioral test
        # belongs in the upstream FastMCP test suite.
        if RateLimitingMiddleware.__name__ != "RateLimitingMiddleware":
            msg = "Expected the RateLimitingMiddleware class"
            raise AssertionError(msg)

    def test_reexports_listed_in_all(self) -> None:
        import mcp_common.fastmcp as mod

        expected = {
            "FastMCP",
            "Context",
            "Middleware",
            "MiddlewareContext",
            "OneiricMCPConfig",
            "RateLimitingMiddleware",
        }
        missing = expected - set(mod.__all__)
        if missing:
            msg = f"mcp_common.fastmcp.__all__ missing entries: {sorted(missing)}"
            raise AssertionError(msg)


class TestMCPBaseSettingsDeprecationWarning:
    """MCPBaseSettings is deprecated in favor of OneiricMCPConfig.
    Subclass instantiation must still work for backward compatibility,
    but it must emit a DeprecationWarning so consumers see the message
    and migrate.
    """

    def test_subclass_emits_deprecation_warning(self) -> None:
        from mcp_common.config import MCPBaseSettings

        class _LegacySettings(MCPBaseSettings):
            pass

        with pytest.warns(DeprecationWarning, match="OneiricMCPConfig"):
            _LegacySettings()

    def test_direct_instantiation_emits_deprecation_warning(self) -> None:
        from mcp_common.config import MCPBaseSettings

        with pytest.warns(DeprecationWarning, match="OneiricMCPConfig"):
            MCPBaseSettings()

    def test_warning_message_is_actionable(self) -> None:
        """The deprecation message must include a pointer to the
        replacement path so consumers know what to import."""
        from mcp_common.config import MCPBaseSettings

        with pytest.warns(DeprecationWarning) as record:
            MCPBaseSettings()

        # Every emitted warning should mention the new path.
        for warning in record:
            assert "OneiricMCPConfig" in str(warning.message), (
                f"Warning does not mention replacement: {warning.message!r}"
            )
