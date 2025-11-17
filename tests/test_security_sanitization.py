"""Tests for input and output sanitization utilities.

Tests comprehensive sanitization to prevent:
- API key exposure in logs
- Path traversal attacks
- XSS in HTML outputs
- Sensitive data leakage
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from mcp_common.security.sanitization import (
    API_KEY_PATTERN,
    SENSITIVE_PATTERNS,
    mask_sensitive_data,
    sanitize_dict_for_logging,
    sanitize_input,
    sanitize_output,
    sanitize_path,
)


class TestSanitizeOutput:
    """Test sanitize_output for masking sensitive data in outputs."""

    def test_sanitize_openai_key_in_string(self) -> None:
        """Should mask OpenAI API keys in strings."""
        data = "Using API key: sk-" + "a" * 48
        result = sanitize_output(data)
        assert "[REDACTED-OPENAI]" in result
        assert "sk-" + "a" * 48 not in result

    def test_sanitize_anthropic_key_in_string(self) -> None:
        """Should mask Anthropic API keys in strings."""
        data = "API key: sk-ant-" + "a" * 95
        result = sanitize_output(data)
        assert "[REDACTED-ANTHROPIC]" in result
        assert "sk-ant-" not in result

    def test_sanitize_github_token_in_string(self) -> None:
        """Should mask GitHub tokens in strings."""
        data = "Token: ghp_" + "a" * 36
        result = sanitize_output(data)
        assert "[REDACTED-GITHUB]" in result
        assert "ghp_" + "a" * 36 not in result

    def test_sanitize_jwt_token_in_string(self) -> None:
        """Should mask JWT tokens in strings."""
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        )
        data = f"Authorization: Bearer {jwt}"
        result = sanitize_output(data)
        assert "[REDACTED-JWT]" in result
        assert jwt not in result

    def test_sanitize_generic_hex_keys(self) -> None:
        """Should mask long hex strings (potential keys)."""
        hex_key = "0" * 32
        data = f"Key: {hex_key}"
        result = sanitize_output(data)
        assert "[REDACTED-GENERIC_HEX]" in result
        assert hex_key not in result

    def test_sanitize_nested_dict(self) -> None:
        """Should recursively sanitize nested dictionaries."""
        data = {
            "config": {
                "api_key": "sk-" + "a" * 48,
                "safe_value": "this is fine",
            }
        }
        result = sanitize_output(data)

        assert isinstance(result["config"], dict)
        assert "[REDACTED-OPENAI]" in result["config"]["api_key"]
        assert result["config"]["safe_value"] == "this is fine"

    def test_sanitize_list_of_strings(self) -> None:
        """Should sanitize lists of strings."""
        data = [
            "Normal text",
            "API key: sk-" + "a" * 48,
            "More normal text",
        ]
        result = sanitize_output(data)

        assert result[0] == "Normal text"
        assert "[REDACTED-OPENAI]" in result[1]
        assert result[2] == "More normal text"

    def test_sanitize_mixed_types(self) -> None:
        """Should handle mixed types (int, float, bool, None)."""
        data = {
            "number": 42,
            "decimal": math.pi,
            "flag": True,
            "nothing": None,
            "text": "sk-" + "a" * 48,
        }
        result = sanitize_output(data)

        assert result["number"] == 42
        assert result["decimal"] == math.pi
        assert result["flag"] is True
        assert result["nothing"] is None
        assert "[REDACTED-OPENAI]" in result["text"]

    def test_sanitize_with_custom_patterns(self) -> None:
        """Should apply custom regex patterns."""
        data = "Secret code: ABC123XYZ"
        result = sanitize_output(data, mask_patterns=[r"ABC\d+XYZ"])

        assert "[REDACTED]" in result
        assert "ABC123XYZ" not in result

    def test_sanitize_with_mask_keys_disabled(self) -> None:
        """Should skip key masking when mask_keys=False."""
        data = "API key: sk-" + "a" * 48
        result = sanitize_output(data, mask_keys=False)

        # Should not mask when disabled
        assert "[REDACTED" not in result


class TestSanitizeDictForLogging:
    """Test sanitize_dict_for_logging for safe log output."""

    def test_sanitize_api_key_field(self) -> None:
        """Should mask fields named 'api_key'."""
        data = {"api_key": "secret123", "user": "john"}
        result = sanitize_dict_for_logging(data)

        assert result["api_key"] == "***"
        assert result["user"] == "john"

    def test_sanitize_password_field(self) -> None:
        """Should mask fields named 'password'."""
        data = {"password": "secret123", "username": "john"}
        result = sanitize_dict_for_logging(data)

        assert result["password"] == "***"
        assert result["username"] == "john"

    def test_sanitize_token_field(self) -> None:
        """Should mask fields named 'token'."""
        data = {"token": "abc123", "status": "active"}
        result = sanitize_dict_for_logging(data)

        assert result["token"] == "***"
        assert result["status"] == "active"

    def test_sanitize_case_insensitive(self) -> None:
        """Should match field names case-insensitively."""
        data = {
            "API_KEY": "secret",
            "Password": "secret",
            "TOKEN": "secret",
            "safe": "value",
        }
        result = sanitize_dict_for_logging(data)

        assert result["API_KEY"] == "***"
        assert result["Password"] == "***"
        assert result["TOKEN"] == "***"
        assert result["safe"] == "value"

    def test_sanitize_nested_dict(self) -> None:
        """Should recursively sanitize nested dictionaries."""
        data = {
            "config": {
                "api_key": "secret",
                "timeout": 30,
            }
        }
        result = sanitize_dict_for_logging(data)

        assert result["config"]["api_key"] == "***"
        assert result["config"]["timeout"] == 30

    def test_sanitize_list_of_dicts(self) -> None:
        """Should sanitize dictionaries within lists."""
        data = {
            "users": [
                {"username": "john", "password": "secret1"},
                {"username": "jane", "password": "secret2"},
            ]
        }
        result = sanitize_dict_for_logging(data)

        assert result["users"][0]["username"] == "john"
        assert result["users"][0]["password"] == "***"
        assert result["users"][1]["password"] == "***"

    def test_sanitize_with_custom_sensitive_keys(self) -> None:
        """Should accept additional sensitive keys."""
        data = {"custom_secret": "value", "api_key": "value"}
        result = sanitize_dict_for_logging(data, sensitive_keys={"custom_secret"})

        assert result["custom_secret"] == "***"
        assert result["api_key"] == "***"

    def test_sanitize_common_sensitive_patterns(self) -> None:
        """Should recognize common sensitive field patterns."""
        data = {
            "apikey": "secret",
            "api-key": "secret",
            "secret_key": "secret",
            "bearer": "secret",
            "authorization": "secret",
            "credential": "secret",
            "private_key": "secret",
        }
        result = sanitize_dict_for_logging(data)

        for key in data:
            assert result[key] == "***", f"Failed to mask {key}"


class TestSanitizePath:
    """Test sanitize_path for preventing path traversal attacks."""

    def test_sanitize_relative_path(self) -> None:
        """Should accept safe relative paths."""
        result = sanitize_path("data/files/test.txt")
        assert result == Path("data/files/test.txt")

    def test_sanitize_rejects_parent_directory(self) -> None:
        """Should reject paths with '..' components."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            sanitize_path("../../etc/passwd")

    def test_sanitize_rejects_absolute_paths_by_default(self) -> None:
        """Should reject absolute paths by default."""
        with pytest.raises(ValueError, match="Absolute paths not allowed"):
            sanitize_path("/etc/passwd")

    def test_sanitize_allows_absolute_with_flag(self) -> None:
        """Should allow absolute paths when allow_absolute=True."""
        result = sanitize_path("/tmp/safe_file.txt", allow_absolute=True)
        assert result == Path("/tmp/safe_file.txt")

    def test_sanitize_rejects_system_directories(self) -> None:
        """Should reject access to system directories."""
        system_dirs = ["/etc/passwd", "/sys/config", "/proc/cpuinfo", "/boot/grub", "/root/.ssh"]

        for path in system_dirs:
            with pytest.raises(ValueError, match="Access to system directory denied"):
                sanitize_path(path, allow_absolute=True)

    def test_sanitize_with_base_dir(self) -> None:
        """Should confine paths to base_dir."""
        result = sanitize_path("data/file.txt", base_dir="/app")
        assert result == Path("data/file.txt")

    def test_sanitize_rejects_escape_from_base_dir(self) -> None:
        """Should reject paths that escape base_dir."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            sanitize_path("../../../etc/passwd", base_dir="/app/data")

    def test_sanitize_accepts_path_object(self) -> None:
        """Should accept Path objects as input."""
        result = sanitize_path(Path("data/file.txt"))
        assert result == Path("data/file.txt")


class TestSanitizeInput:
    """Test sanitize_input for validating user input strings."""

    def test_sanitize_basic_string(self) -> None:
        """Should accept and strip basic strings."""
        result = sanitize_input("  hello world  ")
        assert result == "hello world"

    def test_sanitize_rejects_non_string(self) -> None:
        """Should reject non-string inputs."""
        with pytest.raises(ValueError, match="Expected string"):
            sanitize_input(123)  # type: ignore

    def test_sanitize_enforces_max_length(self) -> None:
        """Should reject strings exceeding max_length."""
        with pytest.raises(ValueError, match="exceeds maximum length"):
            sanitize_input("a" * 101, max_length=100)

    def test_sanitize_allows_valid_length(self) -> None:
        """Should accept strings within max_length."""
        result = sanitize_input("a" * 100, max_length=100)
        assert result == "a" * 100

    def test_sanitize_strips_html_tags(self) -> None:
        """Should remove HTML tags when strip_html=True."""
        result = sanitize_input("<script>alert('xss')</script>hello", strip_html=True)
        # Regex strips tags but preserves content between tags
        assert result == "alert('xss')hello"
        assert "<script>" not in result

    def test_sanitize_preserves_content_without_strip_html(self) -> None:
        """Should preserve HTML when strip_html=False."""
        result = sanitize_input("<b>bold</b>", strip_html=False)
        assert result == "<b>bold</b>"

    def test_sanitize_enforces_allowed_chars(self) -> None:
        """Should reject strings with disallowed characters."""
        with pytest.raises(ValueError, match="contains disallowed characters"):
            sanitize_input("hello123", allowed_chars="a-z")

    def test_sanitize_accepts_allowed_chars(self) -> None:
        """Should accept strings with only allowed characters."""
        result = sanitize_input("hello", allowed_chars="a-z")
        assert result == "hello"

    def test_sanitize_complex_xss_attempt(self) -> None:
        """Should neutralize complex XSS attempts."""
        xss = "<img src=x onerror=alert('XSS')>Valid content"
        result = sanitize_input(xss, strip_html=True)
        assert "Valid content" in result
        assert "<img" not in result
        assert "onerror" not in result


class TestMaskSensitiveData:
    """Test mask_sensitive_data for masking keys in text."""

    def test_mask_openai_key(self) -> None:
        """Should mask OpenAI keys in text."""
        text = "Using API key: sk-" + "a" * 48
        result = mask_sensitive_data(text)

        assert "sk-..." in result
        assert result.endswith(("a" * 48)[-4:])

    def test_mask_anthropic_key(self) -> None:
        """Should mask Anthropic keys in text."""
        text = "Key: sk-ant-" + "a" * 95
        result = mask_sensitive_data(text)

        assert "sk-..." in result

    def test_mask_github_token(self) -> None:
        """Should mask GitHub tokens in text."""
        text = "Token: ghp_" + "a" * 36
        result = mask_sensitive_data(text)

        assert "ghp..." in result

    def test_mask_multiple_keys(self) -> None:
        """Should mask multiple keys in same text."""
        text = f"OpenAI: sk-{'a' * 48}, GitHub: ghp_{'b' * 36}"
        result = mask_sensitive_data(text)

        assert "sk-..." in result
        assert "ghp..." in result
        assert "a" * 48 not in result
        assert "b" * 36 not in result

    def test_mask_custom_visible_chars(self) -> None:
        """Should respect custom visible_chars parameter."""
        text = "Key: sk-" + "a" * 48
        result = mask_sensitive_data(text, visible_chars=6)

        assert result.endswith("aaaaaa")

    def test_mask_very_short_key(self) -> None:
        """Should pass through very short keys that don't match patterns."""
        text = "Key: abc"
        result = mask_sensitive_data(text, visible_chars=10)

        # Very short keys that don't match any pattern pass through unchanged
        assert result == text


class TestSensitivePatterns:
    """Test that SENSITIVE_PATTERNS are comprehensive."""

    def test_all_patterns_compile(self) -> None:
        """All sensitive patterns should be valid regex."""
        import re

        for name, pattern in SENSITIVE_PATTERNS.items():
            try:
                pattern.search("test")
            except re.error as e:
                pytest.fail(f"Pattern {name} is invalid: {e}")

    def test_openai_pattern_matches(self) -> None:
        """OpenAI pattern should match valid keys."""
        pattern = SENSITIVE_PATTERNS["openai"]
        assert pattern.search("sk-" + "a" * 48)

    def test_anthropic_pattern_matches(self) -> None:
        """Anthropic pattern should match valid keys."""
        pattern = SENSITIVE_PATTERNS["anthropic"]
        assert pattern.search("sk-ant-" + "a" * 95)

    def test_github_pattern_matches(self) -> None:
        """GitHub pattern should match valid tokens."""
        pattern = SENSITIVE_PATTERNS["github"]
        assert pattern.search("ghp_" + "a" * 36)
        assert pattern.search("ghs_" + "a" * 40)

    def test_jwt_pattern_matches(self) -> None:
        """JWT pattern should match valid tokens."""
        pattern = SENSITIVE_PATTERNS["jwt"]
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        )
        assert pattern.search(jwt)

    def test_generic_hex_pattern_matches(self) -> None:
        """Generic hex pattern should match long hex strings."""
        pattern = SENSITIVE_PATTERNS["generic_hex"]
        assert pattern.search("0" * 32)
        assert pattern.search("abcdef123456" * 3)


class TestAPIKeyPattern:
    """Test API_KEY_PATTERN for generic detection."""

    def test_pattern_matches_api_key_assignment(self) -> None:
        """Should detect 'api_key = value' patterns."""
        text = "api_key = abc123def456ghi789"
        assert API_KEY_PATTERN.search(text)

    def test_pattern_matches_token_assignment(self) -> None:
        """Should detect 'token: value' patterns."""
        text = "token: abc123def456ghi789"
        assert API_KEY_PATTERN.search(text)

    def test_pattern_matches_various_formats(self) -> None:
        """Should detect various assignment formats."""
        patterns = [
            "api_key='abc123def456ghi789'",
            'api-key="abc123def456ghi789"',
            "secret=abc123def456ghi789",
            "password: abc123def456ghi789",
            "bearer: abc123def456ghi789",  # Pattern requires : or = after bearer
        ]

        for text in patterns:
            assert API_KEY_PATTERN.search(text), f"Failed to match: {text}"

    def test_pattern_requires_minimum_length(self) -> None:
        """Should only match strings ≥16 characters."""
        assert not API_KEY_PATTERN.search("api_key=short")
        assert API_KEY_PATTERN.search("api_key=" + "a" * 16)
