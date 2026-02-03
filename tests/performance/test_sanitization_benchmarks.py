"""Benchmarks for sanitization performance."""

import pytest
from mcp_common.security.sanitization import sanitize_output, mask_sensitive_data


class TestSanitizationBenchmarks:
    """Benchmark sanitization operations."""

    @pytest.mark.benchmark(group="sanitization", min_rounds=100)
    def test_mask_api_key(self, benchmark):
        """Benchmark API key masking."""
        # Valid Anthropic key: sk-ant- + 95+ chars
        key = "sk-ant-" + "x" * 95
        data = {"api_key": key, "user": "john"}

        result = benchmark(sanitize_output, data)
        assert "[REDACTED-ANTHROPIC]" in str(result)

    @pytest.mark.benchmark(group="sanitization", min_rounds=100)
    def test_mask_long_text(self, benchmark):
        """Benchmark masking in long text (1KB)."""
        # Valid Anthropic key: sk-ant- + 95+ chars
        key = "sk-ant-" + "y" * 95
        text = "x" * 1024 + " " + key + " " + "y" * 1024

        result = benchmark(mask_sensitive_data, text)
        # mask_sensitive_data() shows first 3 + last 4 chars, e.g., "sk-...yyyy"
        # Check that the key is not fully visible
        assert key not in result
        assert "..." in result

    @pytest.mark.benchmark(group="sanitization", min_rounds=100)
    def test_sanitize_nested_dict(self, benchmark):
        """Benchmark sanitization of nested dictionary."""
        # Valid Anthropic key: sk-ant- + 95+ chars
        key = "sk-ant-" + "z" * 95
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "api_key": key
                    }
                }
            }
        }

        result = benchmark(sanitize_output, data)
        assert "[REDACTED-ANTHROPIC]" in str(result)

    @pytest.mark.benchmark(group="sanitization", min_rounds=100)
    def test_sanitize_no_match(self, benchmark):
        """Benchmark sanitization when no sensitive data exists."""
        data = {"user": "john", "email": "john@example.com"}

        result = benchmark(sanitize_output, data)
        assert "john" in str(result)

    @pytest.mark.benchmark(group="sanitization", min_rounds=100)
    def test_sanitize_large_dict(self, benchmark):
        """Benchmark sanitization of large dictionary (100 keys)."""
        # Valid Anthropic key: sk-ant- + 95+ chars
        key = "sk-ant-" + "w" * 95
        data = {f"key_{i}": f"value_{i}" for i in range(100)}
        data["api_key"] = key

        result = benchmark(sanitize_output, data)
        assert "[REDACTED-ANTHROPIC]" in str(result)
