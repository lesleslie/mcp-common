"""Additional tests for sanitization utilities.

Covers edge cases and uncovered branches in:
- _sanitize_string (private helper)
- sanitize_output (recursive sanitization)
- sanitize_dict_for_logging (key-based masking)
- sanitize_path (traversal prevention)
- sanitize_input (input validation)
- mask_sensitive_data (pattern-based masking)
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from mcp_common.security.sanitization import (
    SENSITIVE_PATTERNS,
    _sanitize_string,
    mask_sensitive_data,
    sanitize_dict_for_logging,
    sanitize_input,
    sanitize_output,
    sanitize_path,
)


# ---------------------------------------------------------------------------
# _sanitize_string (private helper)
# ---------------------------------------------------------------------------


class TestSanitizeString:
    """Tests for the private _sanitize_string helper function."""

    def test_no_sensitive_data_returns_early(self) -> None:
        """Strings without sensitive patterns should be returned unchanged (early exit)."""
        text = "hello world, this is safe"
        result = _sanitize_string(text)
        assert result is text

    def test_empty_string_returns_early(self) -> None:
        """Empty string should be returned unchanged."""
        result = _sanitize_string("")
        assert result == ""

    def test_openai_key_masked(self) -> None:
        """OpenAI API keys (sk- followed by 48 alphanumeric chars) should be redacted."""
        key = "sk-" + "a" * 48
        result = _sanitize_string(f"Using key: {key}")
        assert "[REDACTED-OPENAI]" in result
        assert key not in result

    def test_anthropic_key_masked(self) -> None:
        """Anthropic API keys (sk-ant- followed by 95+ chars) should be redacted."""
        key = "sk-ant-" + "b" * 95
        result = _sanitize_string(f"Key: {key}")
        assert "[REDACTED-ANTHROPIC]" in result
        assert key not in result

    def test_github_token_masked(self) -> None:
        """GitHub tokens (ghp_ or ghs_ followed by 36+ chars) should be redacted."""
        key = "ghp_" + "c" * 36
        result = _sanitize_string(f"Token: {key}")
        assert "[REDACTED-GITHUB]" in result
        assert key not in result

    def test_github_sso_token_masked(self) -> None:
        """GitHub SSO tokens (ghs_ prefix) should be redacted."""
        key = "ghs_" + "d" * 40
        result = _sanitize_string(f"SSO Token: {key}")
        assert "[REDACTED-GITHUB]" in result

    def test_jwt_masked(self) -> None:
        """JWT tokens (three base64url segments separated by dots) should be redacted."""
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
            ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        )
        result = _sanitize_string(f"Authorization: Bearer {jwt}")
        assert "[REDACTED-JWT]" in result
        assert jwt not in result

    def test_generic_hex_masked(self) -> None:
        """Long hex strings (32+ hex chars) should be redacted."""
        hex_str = "a" * 32
        result = _sanitize_string(f"Key: {hex_str}")
        assert "[REDACTED-GENERIC_HEX]" in result
        assert hex_str not in result

    def test_generic_hex_short_not_masked(self) -> None:
        """Short hex strings (< 32 chars) should NOT be masked."""
        hex_str = "a" * 31
        result = _sanitize_string(f"Key: {hex_str}")
        assert "[REDACTED-GENERIC_HEX]" not in result
        assert hex_str in result

    def test_custom_pattern_masked(self) -> None:
        """Custom regex patterns should be masked."""
        result = _sanitize_string("code ABC123XYZ", mask_patterns=[r"ABC\d+XYZ"])
        assert "[REDACTED]" in result
        assert "ABC123XYZ" not in result

    def test_mask_keys_false_skips_sensitive_patterns(self) -> None:
        """When mask_keys=False, SENSITIVE_PATTERNS should not be applied."""
        key = "sk-" + "a" * 48
        result = _sanitize_string(f"Using key: {key}", mask_keys=False)
        assert "[REDACTED" not in result
        assert key in result

    def test_mask_keys_false_with_custom_patterns(self) -> None:
        """Custom patterns should still be applied when mask_keys=False."""
        result = _sanitize_string(
            "code ABC123XYZ", mask_keys=False, mask_patterns=[r"ABC\d+XYZ"]
        )
        assert "[REDACTED]" in result
        assert "ABC123XYZ" not in result

    def test_mask_keys_false_with_sensitive_and_custom(self) -> None:
        """mask_keys=False skips sensitive patterns but applies custom ones."""
        openai_key = "sk-" + "a" * 48
        result = _sanitize_string(
            f"openai={openai_key} custom=ABC123XYZ",
            mask_keys=False,
            mask_patterns=[r"ABC\d+XYZ"],
        )
        # Custom pattern should be masked
        assert "[REDACTED]" in result
        assert "ABC123XYZ" not in result
        # Sensitive pattern should NOT be masked
        assert openai_key in result

    def test_mask_keys_true_with_custom_pattern_no_sensitive_match(self) -> None:
        """Custom patterns should be applied even when no sensitive patterns match."""
        result = _sanitize_string(
            "safe text with ABC123XYZ inside",
            mask_keys=True,
            mask_patterns=[r"ABC\d+XYZ"],
        )
        assert "[REDACTED]" in result
        assert "ABC123XYZ" not in result
        assert "safe text with" in result

    def test_multiple_sensitive_patterns_in_one_string(self) -> None:
        """Multiple different sensitive patterns in one string should all be masked."""
        openai_key = "sk-" + "a" * 48
        hex_key = "0" * 32
        result = _sanitize_string(f"openai={openai_key} hex={hex_key}")
        assert "[REDACTED-OPENAI]" in result
        assert "[REDACTED-GENERIC_HEX]" in result

    def test_no_custom_patterns_and_no_sensitive_data(self) -> None:
        """When mask_patterns is empty list and no sensitive data, return early."""
        result = _sanitize_string("safe text", mask_patterns=[])
        assert result == "safe text"


# ---------------------------------------------------------------------------
# sanitize_output (recursive sanitization)
# ---------------------------------------------------------------------------


class TestSanitizeOutputAdditional:
    """Additional tests for sanitize_output covering edge cases."""

    def test_empty_dict(self) -> None:
        """Empty dict should be returned as-is."""
        result = sanitize_output({})
        assert result == {}

    def test_empty_list(self) -> None:
        """Empty list should be returned as-is."""
        result = sanitize_output([])
        assert result == []

    def test_safe_string_unchanged(self) -> None:
        """String without sensitive patterns should be returned unchanged."""
        text = "Hello, world!"
        result = sanitize_output(text)
        assert result == text

    def test_deeply_nested_structure(self) -> None:
        """Deeply nested dicts/lists should be recursively sanitized."""
        data = {
            "level1": {
                "level2": [
                    {"key": "sk-" + "a" * 48, "safe": "value"},
                    "normal string",
                ],
                "level2b": {"nested_key": "ghp_" + "b" * 36},
            }
        }
        result = sanitize_output(data)
        assert "[REDACTED-OPENAI]" in result["level1"]["level2"][0]["key"]
        assert result["level1"]["level2"][0]["safe"] == "value"
        assert result["level1"]["level2"][1] == "normal string"
        assert "[REDACTED-GITHUB]" in result["level1"]["level2b"]["nested_key"]

    def test_mask_keys_false_with_mask_patterns(self) -> None:
        """mask_keys=False with mask_patterns should only apply custom patterns."""
        data = {"openai_key": "sk-" + "a" * 48, "custom": "ABC123XYZ"}
        result = sanitize_output(data, mask_keys=False, mask_patterns=[r"ABC\d+XYZ"])
        assert result["openai_key"] == "sk-" + "a" * 48  # not masked
        assert "[REDACTED]" in result["custom"]

    def test_list_with_non_string_items(self) -> None:
        """Lists with mixed types should handle non-string items gracefully."""
        data = [42, 3.14, True, None, "sk-" + "a" * 48, {"nested": "value"}]
        result = sanitize_output(data)
        assert result[0] == 42
        assert result[1] == 3.14
        assert result[2] is True
        assert result[3] is None
        assert "[REDACTED-OPENAI]" in result[4]
        assert result[5] == {"nested": "value"}

    def test_dict_with_list_of_strings(self) -> None:
        """Dict containing a list of strings should sanitize each string."""
        data = {"items": ["safe", "sk-" + "a" * 48, "also safe"]}
        result = sanitize_output(data)
        assert result["items"][0] == "safe"
        assert "[REDACTED-OPENAI]" in result["items"][1]
        assert result["items"][2] == "also safe"

    def test_returns_new_object_not_same_reference(self) -> None:
        """Sanitize should return new objects, not modify in place."""
        original = {"key": "sk-" + "a" * 48}
        result = sanitize_output(original)
        assert result is not original
        assert "sk-" + "a" * 48 not in str(result)


# ---------------------------------------------------------------------------
# sanitize_dict_for_logging (key-based masking)
# ---------------------------------------------------------------------------


class TestSanitizeDictForLoggingAdditional:
    """Additional tests for sanitize_dict_for_logging."""

    def test_empty_dict(self) -> None:
        """Empty dict should be returned as empty dict."""
        result = sanitize_dict_for_logging({})
        assert result == {}

    def test_pwd_key_masked(self) -> None:
        """Keys containing 'pwd' should be masked."""
        result = sanitize_dict_for_logging({"pwd": "secret123", "name": "user"})
        assert result["pwd"] == "***"
        assert result["name"] == "user"

    def test_passwd_key_masked(self) -> None:
        """Keys containing 'passwd' should be masked."""
        result = sanitize_dict_for_logging({"my_passwd": "secret"})
        assert result["my_passwd"] == "***"

    def test_none_sensitive_keys(self) -> None:
        """None as sensitive_keys should use only defaults."""
        result = sanitize_dict_for_logging({"api_key": "secret", "safe": "value"})
        assert result["api_key"] == "***"
        assert result["safe"] == "value"

    def test_non_dict_items_in_list_pass_through(self) -> None:
        """Non-dict items in a list should pass through unchanged."""
        data = {"items": ["string", 42, None, True]}
        result = sanitize_dict_for_logging(data)
        assert result["items"] == ["string", 42, None, True]

    def test_multiple_nesting_levels(self) -> None:
        """Triple-nested dicts should all be sanitized."""
        data = {
            "outer": {
                "middle": {
                    "api_key": "deep_secret",
                    "inner_safe": "value",
                }
            }
        }
        result = sanitize_dict_for_logging(data)
        assert result["outer"]["middle"]["api_key"] == "***"
        assert result["outer"]["middle"]["inner_safe"] == "value"

    def test_key_containing_secret_substring(self) -> None:
        """Keys containing 'secret' as a substring should be masked."""
        result = sanitize_dict_for_logging({"my_secret_value": "hidden"})
        assert result["my_secret_value"] == "***"

    def test_key_containing_auth_substring(self) -> None:
        """Keys containing 'auth' as a substring should be masked."""
        result = sanitize_dict_for_logging({"auth_token": "hidden"})
        assert result["auth_token"] == "***"

    def test_key_containing_credential_substring(self) -> None:
        """Keys containing 'credential' as a substring should be masked."""
        result = sanitize_dict_for_logging({"user_credential": "hidden"})
        assert result["user_credential"] == "***"

    def test_list_of_dicts_with_safe_keys(self) -> None:
        """Dicts in lists with non-sensitive keys should preserve values."""
        data = {
            "users": [
                {"name": "Alice", "role": "admin"},
                {"name": "Bob", "role": "user"},
            ]
        }
        result = sanitize_dict_for_logging(data)
        assert result["users"][0] == {"name": "Alice", "role": "admin"}
        assert result["users"][1] == {"name": "Bob", "role": "user"}

    def test_custom_sensitive_key_with_sensitive_in_name(self) -> None:
        """Custom key should be merged with defaults, not replace them."""
        data = {"api_key": "v1", "custom_field": "v2", "token": "v3"}
        result = sanitize_dict_for_logging(
            data, sensitive_keys={"custom_field"}
        )
        assert result["api_key"] == "***"
        assert result["custom_field"] == "***"
        assert result["token"] == "***"

    def test_integer_value_with_sensitive_key(self) -> None:
        """Integer values for sensitive keys should be masked."""
        result = sanitize_dict_for_logging({"port": 8080, "api_key": 12345})
        assert result["port"] == 8080
        assert result["api_key"] == "***"


# ---------------------------------------------------------------------------
# sanitize_path (traversal prevention)
# ---------------------------------------------------------------------------


class TestSanitizePathAdditional:
    """Additional tests for sanitize_path."""

    def test_normal_relative_path_returns_path_object(self) -> None:
        """Normal relative path should return a Path object."""
        result = sanitize_path("data/files/test.txt")
        assert isinstance(result, Path)
        assert str(result) == "data/files/test.txt"

    def test_path_traversal_single_parent(self) -> None:
        """Single '..' should raise ValueError."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            sanitize_path("../etc/passwd")

    def test_path_traversal_mid_component(self) -> None:
        """'..' in middle of path should raise ValueError."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            sanitize_path("foo/../etc/passwd")

    def test_absolute_path_rejected_by_default(self) -> None:
        """Absolute paths should raise ValueError by default."""
        with pytest.raises(ValueError, match="Absolute paths not allowed"):
            sanitize_path("/tmp/file.txt")

    def test_absolute_path_allowed_with_flag(self) -> None:
        """Absolute paths should be allowed when allow_absolute=True."""
        result = sanitize_path("/tmp/safe_file.txt", allow_absolute=True)
        assert result == Path("/tmp/safe_file.txt")

    def test_system_dir_etc(self) -> None:
        """Access to /etc should raise ValueError."""
        with pytest.raises(ValueError, match="Access to system directory denied"):
            sanitize_path("/etc/shadow", allow_absolute=True)

    def test_system_dir_sys(self) -> None:
        """Access to /sys should raise ValueError."""
        with pytest.raises(ValueError, match="Access to system directory denied"):
            sanitize_path("/sys/kernel/notes", allow_absolute=True)

    def test_system_dir_proc(self) -> None:
        """Access to /proc should raise ValueError."""
        with pytest.raises(ValueError, match="Access to system directory denied"):
            sanitize_path("/proc/self/mem", allow_absolute=True)

    def test_system_dir_boot(self) -> None:
        """Access to /boot should raise ValueError."""
        with pytest.raises(ValueError, match="Access to system directory denied"):
            sanitize_path("/boot/grub/grub.cfg", allow_absolute=True)

    def test_system_dir_root(self) -> None:
        """Access to /root should raise ValueError."""
        with pytest.raises(ValueError, match="Access to system directory denied"):
            sanitize_path("/root/.ssh/id_rsa", allow_absolute=True)

    def test_safe_absolute_path_not_system(self) -> None:
        """Safe absolute path (not system dir) should be allowed."""
        result = sanitize_path("/var/log/app.log", allow_absolute=True)
        assert result == Path("/var/log/app.log")

    def test_path_within_base_dir(self) -> None:
        """Path within base_dir should be accepted."""
        result = sanitize_path("data/file.txt", base_dir="/app")
        assert result == Path("data/file.txt")

    def test_path_escapes_base_dir_with_traversal(self) -> None:
        """Path with '..' escaping base_dir should raise ValueError."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            sanitize_path("../etc/passwd", base_dir="/app/data")

    def test_path_escapes_base_dir_absolute(self) -> None:
        """Absolute path outside base_dir should raise ValueError."""
        with pytest.raises(ValueError, match="escapes base directory"):
            sanitize_path("/tmp/evil.txt", base_dir="/app/data", allow_absolute=True)

    def test_path_object_input(self) -> None:
        """Path object input should be handled correctly."""
        result = sanitize_path(Path("data/file.txt"))
        assert result == Path("data/file.txt")

    def test_path_object_with_base_dir(self) -> None:
        """Path object with base_dir should be handled correctly."""
        result = sanitize_path(Path("subdir/file.txt"), base_dir="/app")
        assert result == Path("subdir/file.txt")

    def test_dot_filename_allowed(self) -> None:
        """Filenames starting with dot (but not '..') should be allowed."""
        result = sanitize_path(".env")
        assert result == Path(".env")

    def test_current_dir_reference_allowed(self) -> None:
        """Single dot '.' in path should be allowed."""
        result = sanitize_path("./data/file.txt")
        assert result == Path("data/file.txt")

    def test_empty_string_path(self) -> None:
        """Empty string path should return Path('.')."""
        result = sanitize_path("")
        assert result == Path(".")

    def test_base_dir_with_path_object(self) -> None:
        """base_dir as Path object should work."""
        result = sanitize_path("file.txt", base_dir=Path("/app"))
        assert result == Path("file.txt")


# ---------------------------------------------------------------------------
# sanitize_input (input validation)
# ---------------------------------------------------------------------------


class TestSanitizeInputAdditional:
    """Additional tests for sanitize_input."""

    def test_normal_string_returns_stripped(self) -> None:
        """Normal string should be stripped and returned."""
        result = sanitize_input("  hello world  ")
        assert result == "hello world"

    def test_max_length_violation(self) -> None:
        """String exceeding max_length should raise ValueError."""
        with pytest.raises(ValueError, match="exceeds maximum length of 10"):
            sanitize_input("a" * 11, max_length=10)

    def test_max_length_exact(self) -> None:
        """String at exactly max_length should be accepted."""
        result = sanitize_input("a" * 10, max_length=10)
        assert result == "a" * 10

    def test_allowed_chars_violation(self) -> None:
        """String with disallowed characters should raise ValueError."""
        with pytest.raises(ValueError, match="contains disallowed characters"):
            sanitize_input("hello123", allowed_chars="a-z")

    def test_allowed_chars_valid(self) -> None:
        """String with only allowed characters should be accepted."""
        result = sanitize_input("hello", allowed_chars="a-z")
        assert result == "hello"

    def test_strip_html_removes_tags(self) -> None:
        """HTML tags should be stripped when strip_html=True."""
        result = sanitize_input("<b>bold</b> and <i>italic</i>", strip_html=True)
        assert result == "bold and italic"
        assert "<b>" not in result
        assert "<i>" not in result

    def test_strip_html_with_script_tag(self) -> None:
        """Script tags should be removed."""
        result = sanitize_input(
            "<script>alert('xss')</script>safe content", strip_html=True
        )
        assert "safe content" in result
        assert "<script>" not in result

    def test_non_string_raises_value_error(self) -> None:
        """Non-string input should raise ValueError."""
        with pytest.raises(ValueError, match="Expected string"):
            sanitize_input(123)  # type: ignore

    def test_none_raises_value_error(self) -> None:
        """None input should raise ValueError."""
        with pytest.raises(ValueError, match="Expected string"):
            sanitize_input(None)  # type: ignore

    def test_list_raises_value_error(self) -> None:
        """List input should raise ValueError."""
        with pytest.raises(ValueError, match="Expected string"):
            sanitize_input(["a", "b"])  # type: ignore

    def test_strip_html_and_max_length(self) -> None:
        """strip_html should apply before max_length check."""
        # After stripping HTML, the content is short enough
        result = sanitize_input(
            "<b>hi</b>", strip_html=True, max_length=10
        )
        assert result == "hi"

    def test_strip_html_exceeds_max_length(self) -> None:
        """After HTML stripping, if content still exceeds max_length, should raise."""
        with pytest.raises(ValueError, match="exceeds maximum length"):
            sanitize_input(
                "<b>" + "a" * 20 + "</b>", strip_html=True, max_length=10
            )

    def test_allowed_chars_after_html_strip(self) -> None:
        """allowed_chars should validate the stripped content, not the HTML."""
        result = sanitize_input(
            "<b>hello</b>", strip_html=True, allowed_chars="a-z"
        )
        assert result == "hello"

    def test_all_constraints_combined(self) -> None:
        """strip_html + max_length + allowed_chars should all work together."""
        result = sanitize_input(
            "<b>hello</b>", strip_html=True, max_length=10, allowed_chars="a-z"
        )
        assert result == "hello"

    def test_empty_string_returns_empty(self) -> None:
        """Empty string should return empty string."""
        result = sanitize_input("")
        assert result == ""

    def test_no_max_length_no_limit(self) -> None:
        """Without max_length, very long strings should be accepted."""
        long_str = "a" * 10000
        result = sanitize_input(long_str)
        assert result == long_str

    def test_whitespace_only_returns_empty(self) -> None:
        """Whitespace-only string should be stripped to empty."""
        result = sanitize_input("   ")
        assert result == ""

    def test_allowed_chars_with_digits(self) -> None:
        """allowed_chars pattern should support digits."""
        result = sanitize_input("12345", allowed_chars="0-9")
        assert result == "12345"

    def test_allowed_chars_with_alphanumeric(self) -> None:
        """allowed_chars pattern should support alphanumeric."""
        result = sanitize_input("abc123", allowed_chars="a-zA-Z0-9")
        assert result == "abc123"

    def test_newline_in_input(self) -> None:
        """Newlines should be preserved (no strip_html)."""
        result = sanitize_input("hello\nworld")
        assert result == "hello\nworld"


# ---------------------------------------------------------------------------
# mask_sensitive_data (pattern-based masking)
# ---------------------------------------------------------------------------


class TestMaskSensitiveDataAdditional:
    """Additional tests for mask_sensitive_data."""

    def test_no_sensitive_data_unchanged(self) -> None:
        """Text without any sensitive patterns should be unchanged."""
        text = "Hello, this is safe text with no keys."
        result = mask_sensitive_data(text)
        assert result == text

    def test_openai_key_masked(self) -> None:
        """OpenAI key should be masked showing first 3 and last 4 chars."""
        key = "sk-" + "a" * 48
        text = f"Using key: {key}"
        result = mask_sensitive_data(text)
        assert "sk-..." in result
        assert result.endswith("aaaa")

    def test_anthropic_key_masked(self) -> None:
        """Anthropic key should be masked."""
        key = "sk-ant-" + "b" * 95
        text = f"Key: {key}"
        result = mask_sensitive_data(text)
        assert "sk-..." in result
        assert "***" not in result or len(key) <= 7  # key is long, so partial mask

    def test_github_token_masked(self) -> None:
        """GitHub token should be masked."""
        key = "ghp_" + "c" * 36
        text = f"Token: {key}"
        result = mask_sensitive_data(text)
        assert "ghp..." in result

    def test_generic_hex_key_masked(self) -> None:
        """Generic hex strings (32+ chars) should be masked."""
        hex_str = "d" * 32
        text = f"Key: {hex_str}"
        result = mask_sensitive_data(text)
        assert hex_str not in result
        assert "..." in result

    def test_jwt_masked(self) -> None:
        """JWT tokens should be masked."""
        jwt = (
            "eyJhbGciOiJIUzI1NiJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
            ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        )
        text = f"Bearer {jwt}"
        result = mask_sensitive_data(text)
        assert jwt not in result
        assert "..." in result

    def test_short_value_masked_as_asterisks(self) -> None:
        """Values shorter than visible_chars+3 should be replaced with ***."""
        # generic_hex matches at 32 chars; visible_chars=100 makes key too short
        hex_str = "a" * 32
        text = f"Key: {hex_str}"
        result = mask_sensitive_data(text, visible_chars=100)
        assert "***" in result

    def test_custom_visible_chars(self) -> None:
        """Custom visible_chars should show that many characters at the end."""
        key = "sk-" + "a" * 48
        text = f"Key: {key}"
        result = mask_sensitive_data(text, visible_chars=8)
        assert result.endswith("aaaaaaaa")

    def test_multiple_keys_in_same_text(self) -> None:
        """Multiple sensitive patterns in same text should all be masked."""
        openai_key = "sk-" + "a" * 48
        github_token = "ghp_" + "b" * 36
        text = f"OpenAI: {openai_key}, GitHub: {github_token}"
        result = mask_sensitive_data(text)
        assert openai_key not in result
        assert github_token not in result
        assert "sk-..." in result
        assert "ghp..." in result

    def test_no_masking_when_visible_chars_equals_zero(self) -> None:
        """visible_chars=0 should still mask (shows first 3 and last 0)."""
        key = "sk-" + "a" * 48
        text = f"Key: {key}"
        result = mask_sensitive_data(text, visible_chars=0)
        assert key not in result

    def test_short_text_no_pattern_match(self) -> None:
        """Short text that doesn't match any pattern should pass through."""
        text = "abc123"
        result = mask_sensitive_data(text)
        assert result == text

    def test_mask_preserves_surrounding_text(self) -> None:
        """Masking should preserve all non-sensitive text around keys."""
        key = "sk-" + "a" * 48
        text = f"prefix {key} suffix"
        result = mask_sensitive_data(text)
        assert "prefix " in result
        assert " suffix" in result
        assert key not in result


# ---------------------------------------------------------------------------
# SENSITIVE_PATTERNS (regex patterns)
# ---------------------------------------------------------------------------


class TestSensitivePatternsAdditional:
    """Additional tests for SENSITIVE_PATTERNS regex patterns."""

    def test_openai_pattern_exact_length(self) -> None:
        """OpenAI pattern requires exactly 48 chars after sk- prefix."""
        pattern = SENSITIVE_PATTERNS["openai"]
        # 47 chars after sk- should NOT match
        assert not pattern.search("sk-" + "a" * 47)
        # 48 chars after sk- should match
        assert pattern.search("sk-" + "a" * 48)

    def test_anthropic_pattern_minimum_length(self) -> None:
        """Anthropic pattern requires at least 95 chars after sk-ant-."""
        pattern = SENSITIVE_PATTERNS["anthropic"]
        assert not pattern.search("sk-ant-" + "a" * 94)
        assert pattern.search("sk-ant-" + "a" * 95)

    def test_github_pattern_ghs_prefix(self) -> None:
        """GitHub pattern should match ghs_ (SSO) prefix."""
        pattern = SENSITIVE_PATTERNS["github"]
        assert pattern.search("ghs_" + "a" * 36)

    def test_github_pattern_github_app_prefix(self) -> None:
        """GitHub pattern should NOT match arbitrary prefixes."""
        pattern = SENSITIVE_PATTERNS["github"]
        assert not pattern.search("ghx_" + "a" * 36)

    def test_jwt_pattern_three_segments(self) -> None:
        """JWT pattern requires three dot-separated base64url segments."""
        pattern = SENSITIVE_PATTERNS["jwt"]
        # Two segments should not match
        assert not pattern.search("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0")
        # Three segments should match
        assert pattern.search(
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N"
        )

    def test_generic_hex_31_chars_no_match(self) -> None:
        """Generic hex pattern requires at least 32 characters."""
        pattern = SENSITIVE_PATTERNS["generic_hex"]
        assert not pattern.search("a" * 31)
        assert pattern.search("a" * 32)

    def test_generic_hex_lowercase_only(self) -> None:
        """Generic hex pattern only matches lowercase hex (not uppercase)."""
        pattern = SENSITIVE_PATTERNS["generic_hex"]
        # Lowercase hex should match
        assert pattern.search("abcdef1234567890abcdef1234567890ab")
        # Uppercase hex should NOT match (pattern is [0-9a-f])
        assert not pattern.search("ABCDEF1234567890ABCDEF1234567890AB")

    def test_generic_hex_word_boundary(self) -> None:
        """Generic hex pattern should use word boundaries."""
        pattern = SENSITIVE_PATTERNS["generic_hex"]
        # 32 hex chars preceded by a letter should NOT match (word boundary)
        assert not pattern.search("x" + "a" * 32)
        # 32 hex chars preceded by space should match
        assert pattern.search(" " + "a" * 32)
