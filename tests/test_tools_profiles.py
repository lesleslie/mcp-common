"""Tests for mcp_common.tools.profiles — ToolProfile enum and MANDATORY_TOOLS."""

import os
from mcp_common.tools.profiles import MANDATORY_TOOLS, ToolProfile


# ---------------------------------------------------------------------------
# 1. Enum values
# ---------------------------------------------------------------------------


class TestEnumValues:
    def test_minimal_exists(self) -> None:
        assert ToolProfile.MINIMAL == "minimal"

    def test_standard_exists(self) -> None:
        assert ToolProfile.STANDARD == "standard"

    def test_full_exists(self) -> None:
        assert ToolProfile.FULL == "full"

    def test_all_values_present(self) -> None:
        expected = {"minimal", "standard", "full"}
        actual = {member.value for member in ToolProfile}
        assert actual == expected


# ---------------------------------------------------------------------------
# 2. Comparison operators
# ---------------------------------------------------------------------------


class TestComparisons:
    def test_minimal_less_than_standard(self) -> None:
        assert ToolProfile.MINIMAL < ToolProfile.STANDARD

    def test_standard_less_than_full(self) -> None:
        assert ToolProfile.STANDARD < ToolProfile.FULL

    def test_minimal_less_than_full(self) -> None:
        assert ToolProfile.MINIMAL < ToolProfile.FULL

    def test_full_greater_than_standard(self) -> None:
        assert ToolProfile.FULL > ToolProfile.STANDARD

    def test_standard_greater_than_minimal(self) -> None:
        assert ToolProfile.STANDARD > ToolProfile.MINIMAL

    def test_full_greater_or_equal_standard(self) -> None:
        assert ToolProfile.FULL >= ToolProfile.STANDARD

    def test_standard_greater_or_equal_standard(self) -> None:
        assert ToolProfile.STANDARD >= ToolProfile.STANDARD

    def test_minimal_less_or_equal_standard(self) -> None:
        assert ToolProfile.MINIMAL <= ToolProfile.STANDARD

    def test_standard_less_or_equal_standard(self) -> None:
        assert ToolProfile.STANDARD <= ToolProfile.STANDARD

    def test_minimal_less_or_equal_minimal(self) -> None:
        assert ToolProfile.MINIMAL <= ToolProfile.MINIMAL

    def test_full_greater_or_equal_full(self) -> None:
        assert ToolProfile.FULL >= ToolProfile.FULL

    def test_ge_returns_not_implemented_for_non_profile(self) -> None:
        result = ToolProfile.FULL.__ge__("full")
        assert result is NotImplemented

    def test_gt_returns_not_implemented_for_non_profile(self) -> None:
        result = ToolProfile.FULL.__gt__("full")
        assert result is NotImplemented

    def test_le_returns_not_implemented_for_non_profile(self) -> None:
        result = ToolProfile.FULL.__le__("full")
        assert result is NotImplemented

    def test_lt_returns_not_implemented_for_non_profile(self) -> None:
        result = ToolProfile.FULL.__lt__("full")
        assert result is NotImplemented


# ---------------------------------------------------------------------------
# 3–9. from_string
# ---------------------------------------------------------------------------


class TestFromString:
    def test_valid_name_lowercase(self) -> None:
        assert ToolProfile.from_string("minimal") == ToolProfile.MINIMAL
        assert ToolProfile.from_string("standard") == ToolProfile.STANDARD
        assert ToolProfile.from_string("full") == ToolProfile.FULL

    def test_valid_name_uppercase(self) -> None:
        assert ToolProfile.from_string("MINIMAL") == ToolProfile.MINIMAL
        assert ToolProfile.from_string("STANDARD") == ToolProfile.STANDARD
        assert ToolProfile.from_string("FULL") == ToolProfile.FULL

    def test_valid_name_mixed_case(self) -> None:
        assert ToolProfile.from_string("Minimal") == ToolProfile.MINIMAL
        assert ToolProfile.from_string("StAnDaRd") == ToolProfile.STANDARD
        assert ToolProfile.from_string("FuLl") == ToolProfile.FULL

    def test_invalid_name_returns_default_full(self) -> None:
        assert ToolProfile.from_string("bogus") == ToolProfile.FULL

    def test_none_returns_default_full(self) -> None:
        assert ToolProfile.from_string(None) == ToolProfile.FULL

    def test_empty_string_returns_default_full(self) -> None:
        assert ToolProfile.from_string("") == ToolProfile.FULL

    def test_whitespace_padded_name(self) -> None:
        assert ToolProfile.from_string("  minimal  ") == ToolProfile.MINIMAL
        assert ToolProfile.from_string("\tstandard\n") == ToolProfile.STANDARD
        assert ToolProfile.from_string("  full  ") == ToolProfile.FULL

    def test_custom_default(self) -> None:
        assert ToolProfile.from_string("bad", default=ToolProfile.MINIMAL) == ToolProfile.MINIMAL
        assert ToolProfile.from_string(None, default=ToolProfile.STANDARD) == ToolProfile.STANDARD

    def test_whitespace_only_returns_default(self) -> None:
        assert ToolProfile.from_string("   ") == ToolProfile.FULL


# ---------------------------------------------------------------------------
# 10–11. from_env
# ---------------------------------------------------------------------------


class TestFromEnv:
    def test_reads_env_var(self, monkeypatch: object) -> None:
        monkeypatch.setenv("TEST_TOOL_PROFILE", "standard")  # type: ignore[union-attr]
        assert ToolProfile.from_env("TEST_TOOL_PROFILE") == ToolProfile.STANDARD

    def test_missing_env_var_returns_default(self, monkeypatch: object) -> None:
        monkeypatch.delenv("MISSING_TOOL_PROFILE", raising=False)  # type: ignore[union-attr]
        assert ToolProfile.from_env("MISSING_TOOL_PROFILE") == ToolProfile.FULL

    def test_env_var_custom_default(self, monkeypatch: object) -> None:
        monkeypatch.delenv("NOPE_TOOL_PROFILE", raising=False)  # type: ignore[union-attr]
        assert (
            ToolProfile.from_env("NOPE_TOOL_PROFILE", default=ToolProfile.MINIMAL)
            == ToolProfile.MINIMAL
        )

    def test_env_var_with_invalid_value_returns_default(self, monkeypatch: object) -> None:
        monkeypatch.setenv("BAD_TOOL_PROFILE", "nope")  # type: ignore[union-attr]
        assert ToolProfile.from_env("BAD_TOOL_PROFILE") == ToolProfile.FULL


# ---------------------------------------------------------------------------
# 12. MANDATORY_TOOLS
# ---------------------------------------------------------------------------


class TestMandatoryTools:
    def test_contains_expected_tools(self) -> None:
        expected = {"get_liveness", "get_readiness", "health_check", "health_check_all"}
        assert MANDATORY_TOOLS == expected

    def test_is_a_set(self) -> None:
        assert isinstance(MANDATORY_TOOLS, set)

    def test_size(self) -> None:
        assert len(MANDATORY_TOOLS) == 4
