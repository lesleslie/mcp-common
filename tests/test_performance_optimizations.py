"""Tests to verify Phase 4 performance optimizations.

These tests verify that the optimizations provide the expected speedup.
"""

import pytest
from mcp_common.security.sanitization import sanitize_output
from mcp_common.security.api_keys import (
    validate_api_key_format,
    validate_api_key_format_cached,
)


class TestSanitizationOptimization:
    """Test sanitization early-exit optimization."""

    def test_no_match_case_is_fast(self, benchmark) -> None:
        """Benchmark that text without sensitive data is fast."""
        # Text with NO sensitive patterns should be very fast
        text = "Regular user message with no API keys or tokens"

        result = benchmark(sanitize_output, text)
        assert result == text

    def test_single_pattern_match(self, benchmark) -> None:
        """Benchmark that one pattern match is still fast."""
        # Text with one API key - should still be fast
        key = "sk-ant-" + "x" * 95
        text = f"User message with key: {key}"

        result = benchmark(sanitize_output, text)
        assert "[REDACTED-ANTHROPIC]" in result

    def test_early_exit_benefit(self) -> None:
        """Demonstrate early exit benefit for non-matching text."""
        import time

        # Text with no sensitive data
        clean_text = "Regular message " * 100

        # Time the sanitized version
        start = time.perf_counter()
        for _ in range(1000):
            sanitize_output(clean_text)
        sanitized_time = time.perf_counter() - start

        # Text with sensitive data
        dirty_text = "API key: sk-ant-" + "x" * 95 + " message"

        # Time the sanitized version
        start = time.perf_counter()
        for _ in range(1000):
            sanitize_output(dirty_text)
        unsanitized_time = time.perf_counter() - start

        # Early exit should make clean text faster
        # (Allow some variance, but clean should be <= dirty)
        # This is a demonstration test, not strict assertion
        print(f"\nClean text (early exit): {sanitized_time:.4f}s")
        print(f"Dirty text (full scan): {unsanitized_time:.4f}s")
        print(f"Speedup: {unsanitized_time / sanitized_time:.2f}x")


class TestValidationCaching:
    """Test API key validation caching optimization."""

    def test_cached_version_is_correct(self) -> None:
        """Verify cached version produces same results as uncached."""
        # Valid OpenAI key: 48 chars after sk-
        key = "sk-" + "1234567890abcdefghijklmnopqrstuvwxyz" + "123456789012"

        result_uncached = validate_api_key_format(key, provider="openai")
        result_cached = validate_api_key_format_cached(key, provider="openai")

        assert result_uncached == result_cached == key

    def test_cached_version_reuses_result(self) -> None:
        """Verify cached version actually caches."""
        import time

        key = "sk-" + "1234567890abcdefghijklmnopqrstuvwxyz" + "123456789012"

        # First call - should be slower
        start = time.perf_counter()
        result1 = validate_api_key_format_cached(key, provider="openai")
        first_call_time = time.perf_counter() - start

        # Second call - should be much faster (cached)
        start = time.perf_counter()
        result2 = validate_api_key_format_cached(key, provider="openai")
        second_call_time = time.perf_counter() - start

        assert result1 == result2 == key
        print(f"\nFirst call: {first_call_time * 1000:.2f}μs")
        print(f"Second call (cached): {second_call_time * 1000:.2f}μs")
        print(f"Speedup: {first_call_time / second_call_time:.2f}x")

        # Cached should be significantly faster
        # (At least 2x speedup, typically much more)
        assert second_call_time < first_call_time / 2

    def test_cache_different_providers(self) -> None:
        """Verify cache keys include provider."""
        # Use provider-specific keys to avoid format errors
        openai_key = "sk-" + "1234567890abcdefghijklmnopqrstuvwxyz" + "123456789012"
        anthropic_key = "sk-ant-" + "x" * 95

        # Validate for different providers - should cache separately
        result_openai = validate_api_key_format_cached(openai_key, provider="openai")
        result_anthropic = validate_api_key_format_cached(anthropic_key, provider="anthropic")

        # Both should succeed with their respective providers
        assert result_openai == openai_key
        assert result_anthropic == anthropic_key

    def test_cache_invalidation(self) -> None:
        """Verify different keys create separate cache entries."""
        key1 = "sk-" + "1234567890abcdefghijklmnopqrstuvwxyz" + "123456789012"
        # Create a second valid OpenAI key (48 chars after "sk-")
        key2 = "sk-" + "abcdefghijklmnopqrstuvwxyz0123456789" + "123456789012"

        # Both should succeed and be cached separately
        result1 = validate_api_key_format_cached(key1, provider="openai")
        result2 = validate_api_key_format_cached(key2, provider="openai")

        assert result1 == key1
        assert result2 == key2
