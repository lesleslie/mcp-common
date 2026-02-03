"""Benchmarks for validation performance."""

import pytest
from mcp_common.security.api_keys import validate_api_key_format


class TestValidationBenchmarks:
    """Benchmark validation operations."""

    @pytest.mark.benchmark(group="validation", min_rounds=1000)
    def test_openai_validation(self, benchmark):
        """Benchmark OpenAI API key validation."""
        # Valid OpenAI key: sk- + exactly 48 alphanumeric chars
        key = "sk-" + "1234567890abcdefghijklmnopqrstuvwxyz" + "123456789012"

        result = benchmark(validate_api_key_format, key, provider="openai")
        assert result == key

    @pytest.mark.benchmark(group="validation", min_rounds=1000)
    def test_anthropic_validation(self, benchmark):
        """Benchmark Anthropic API key validation."""
        # Valid Anthropic key: sk-ant- + 95+ chars (total >102)
        key = "sk-ant-api03-" + "1234567890abcdefghijklmnopqrstuvwxyz" * 3

        result = benchmark(validate_api_key_format, key, provider="anthropic")
        assert result == key

    @pytest.mark.benchmark(group="validation", min_rounds=1000)
    def test_generic_validation(self, benchmark):
        """Benchmark generic API key validation."""
        key = "my-secret-api-key-12345678"

        result = benchmark(validate_api_key_format, key)
        assert result == key

    @pytest.mark.benchmark(group="validation", min_rounds=1000)
    def test_validation_too_short(self, benchmark):
        """Benchmark validation that should fail (too short)."""
        key = "short"

        # Should raise validation error
        with pytest.raises(Exception):
            result = benchmark(validate_api_key_format, key, provider="openai")

    @pytest.mark.benchmark(group="validation", min_rounds=1000)
    def test_batch_validation(self, benchmark):
        """Benchmark batch validation of multiple keys."""
        # Valid OpenAI key: sk- + exactly 48 chars
        openai_key = "sk-" + "1234567890abcdefghijklmnopqrstuvwxyz" + "123456789012"
        # Valid Anthropic key: sk-ant- + 95+ chars
        anthropic_key = "sk-ant-api03-" + "1234567890abcdefghijklmnopqrstuvwxyz" * 3
        # Valid generic key: 16+ chars
        generic_key = "my-secret-api-key-12345678"

        keys = [openai_key, anthropic_key, generic_key]

        def validate_all():
            return [validate_api_key_format(key) for key in keys]

        result = benchmark(validate_all)
        assert len(result) == 3
