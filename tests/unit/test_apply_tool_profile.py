"""Unit tests for apply_tool_profile() helper. Uses monkeypatch for env isolation."""
from __future__ import annotations

import pytest

from mcp_common.tools import ToolProfile, MANDATORY_TOOLS
from mcp_common.tools.dispatch import (
    ALL_TOOLS,
    InvalidProfileError,
    apply_tool_profile,
)


def test_all_tools_is_sentinel_class():
    """ALL_TOOLS is a class (sentinel), not the string 'all_tools'."""
    assert isinstance(ALL_TOOLS, type)
    assert ALL_TOOLS.__name__ == "ALL_TOOLS"


def test_unset_env_falls_through_to_full(monkeypatch):
    """Per spec §1, UNSET env var defaults to FULL (matches existing ToolProfile.from_env)."""
    monkeypatch.delenv("TEST_PROFILE", raising=False)
    # Should NOT raise InvalidProfileError; falls through to FULL
    apply_tool_profile(
        server=None,  # type: ignore
        profile_env_var="TEST_PROFILE",
        registrations={
            ToolProfile.MINIMAL: [],
            ToolProfile.STANDARD: [],
            ToolProfile.FULL: ALL_TOOLS,
        },
        registration_map={},
        register_all_fn=lambda s: None,
    )


def test_invalid_profile_error_on_set_but_empty(monkeypatch):
    """SET-BUT-EMPTY env var raises InvalidProfileError."""
    monkeypatch.setenv("TEST_PROFILE", "")
    with pytest.raises(InvalidProfileError):
        apply_tool_profile(
            server=None,  # type: ignore
            profile_env_var="TEST_PROFILE",
            registrations={},
            registration_map={},
            register_all_fn=lambda s: None,
        )


def test_invalid_profile_error_on_whitespace(monkeypatch):
    monkeypatch.setenv("TEST_PROFILE", "   ")
    with pytest.raises(InvalidProfileError):
        apply_tool_profile(
            server=None,  # type: ignore
            profile_env_var="TEST_PROFILE",
            registrations={},
            registration_map={},
            register_all_fn=lambda s: None,
        )


def test_invalid_profile_error_on_unknown_value(monkeypatch):
    monkeypatch.setenv("TEST_PROFILE", "bogus")
    with pytest.raises(InvalidProfileError):
        apply_tool_profile(
            server=None,  # type: ignore
            profile_env_var="TEST_PROFILE",
            registrations={},
            registration_map={},
            register_all_fn=lambda s: None,
        )


def test_valid_profiles_accepted(monkeypatch):
    """lowercase, uppercase, mixed case all accepted for valid profile names."""
    for value in ("minimal", "MINIMAL", "Minimal", "standard", "full", "FULL"):
        monkeypatch.setenv("TEST_PROFILE", value)
        apply_tool_profile(
            server=None,  # type: ignore
            profile_env_var="TEST_PROFILE",
            registrations={
                ToolProfile.MINIMAL: [],
                ToolProfile.STANDARD: [],
                ToolProfile.FULL: ALL_TOOLS,
            },
            registration_map={},
            register_all_fn=lambda s: None,
        )


def test_all_tools_at_full_requires_register_all_fn(monkeypatch):
    """ALL_TOOLS at FULL but register_all_fn=None raises ValueError."""
    monkeypatch.setenv("TEST_PROFILE", "full")
    with pytest.raises(ValueError, match="register_all_fn"):
        apply_tool_profile(
            server=None,  # type: ignore
            profile_env_var="TEST_PROFILE",
            registrations={
                ToolProfile.MINIMAL: [],
                ToolProfile.STANDARD: [],
                ToolProfile.FULL: ALL_TOOLS,
            },
            registration_map={},
            register_all_fn=None,  # type: ignore
        )


def test_yaml_loader_fallback(monkeypatch):
    """Unset env var falls through to yaml_loader()."""
    from mcp_common.tools.dispatch import _resolve_profile

    monkeypatch.delenv("TEST_PROFILE", raising=False)
    profile = _resolve_profile(
        "TEST_PROFILE",
        yaml_loader=lambda: {"tool_profile": "minimal"},
    )
    assert profile == ToolProfile.MINIMAL


def test_yaml_loader_returns_invalid_raises(monkeypatch):
    """yaml_loader returning an invalid value raises InvalidProfileError."""
    from mcp_common.tools.dispatch import _resolve_profile

    monkeypatch.delenv("TEST_PROFILE", raising=False)
    with pytest.raises(InvalidProfileError):
        _resolve_profile(
            "TEST_PROFILE",
            yaml_loader=lambda: {"tool_profile": "not-a-real-profile"},
        )


def test_yaml_loader_exception_treated_as_empty(monkeypatch):
    """yaml_loader raising is treated as empty → defaults to FULL."""
    from mcp_common.tools.dispatch import _resolve_profile

    def boom() -> None:
        raise RuntimeError("yaml error")

    monkeypatch.delenv("TEST_PROFILE", raising=False)
    profile = _resolve_profile("TEST_PROFILE", yaml_loader=boom)
    assert profile == ToolProfile.FULL
