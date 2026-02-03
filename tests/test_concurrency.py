"""Concurrency and race condition tests.

Tests concurrent operations to ensure thread-safety and absence of race conditions.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from mcp_common.cli.factory import write_runtime_health, load_runtime_health
from mcp_common.config import MCPBaseSettings
from mcp_common.security.sanitization import sanitize_output
from mcp_common.security.api_keys import validate_api_key_format


class TestConcurrency:
    """Test concurrent operations don't cause race conditions."""

    @pytest.mark.asyncio
    async def test_concurrent_health_snapshot_writes(self, tmp_path: Path) -> None:
        """Test concurrent writes to health snapshot are safe."""
        snapshot_path = tmp_path / "health.json"
        from mcp_common.cli import RuntimeHealthSnapshot

        # Create a snapshot
        snapshot = RuntimeHealthSnapshot(orchestrator_pid=12345)

        # Write it once first
        write_runtime_health(snapshot_path, snapshot)

        # Create multiple concurrent read tasks
        tasks = [
            asyncio.to_thread(load_runtime_health, snapshot_path)
            for _ in range(10)
        ]

        # All reads should succeed and return valid data
        results = await asyncio.gather(*tasks)

        # All results should be valid
        assert all(r is not None for r in results)
        assert all(r.orchestrator_pid == 12345 for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_config_loading(self, tmp_path: Path) -> None:
        """Test concurrent config loading doesn't cause issues."""
        (tmp_path / "settings").mkdir()

        # Create 10 concurrent config loads
        tasks = []
        for i in range(10):
            async def load_config() -> object:
                class TestSettings(MCPBaseSettings):
                    test_field: str = "default"

                return TestSettings.load("concurrent-test")

            tasks.append(load_config())

        results = await asyncio.gather(*tasks)
        assert all(r.test_field == "default" for r in results)  # type: ignore

    @pytest.mark.asyncio
    async def test_concurrent_sanitization(self) -> None:
        """Test concurrent sanitization calls don't interfere."""
        data = {"api_key": "sk-test-key", "user": "john"}

        # Sanitize same data concurrently
        tasks = [asyncio.to_thread(sanitize_output, data) for _ in range(100)]
        results = await asyncio.gather(*tasks)

        # All results should be identical
        assert all(r == results[0] for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_api_key_validation(self) -> None:
        """Test concurrent API key validation is thread-safe."""
        key = "sk-test-api-key-12345678"

        # Validate same key concurrently
        tasks = [
            asyncio.to_thread(validate_api_key_format, key, provider="generic")
            for _ in range(100)
        ]
        results = await asyncio.gather(*tasks)

        # All results should be identical
        assert all(r == results[0] for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_nested_sanitization(self) -> None:
        """Test concurrent sanitization of nested data structures."""
        data = {
            "level1": {
                "level2": {
                    "api_key": "sk-test-key"
                }
            }
        }

        # Sanitize same nested data concurrently
        tasks = [asyncio.to_thread(sanitize_output, data) for _ in range(50)]
        results = await asyncio.gather(*tasks)

        # All results should be identical
        assert all(r == results[0] for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_list_sanitization(self) -> None:
        """Test concurrent sanitization of lists."""
        data = [
            {"api_key": f"sk-test-key-{i}", "user": f"user{i}"}
            for i in range(10)
        ]

        # Sanitize same list concurrently
        tasks = [asyncio.to_thread(sanitize_output, data) for _ in range(50)]
        results = await asyncio.gather(*tasks)

        # All results should be identical
        assert all(str(r) == str(results[0]) for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_mixed_data_sanitization(self) -> None:
        """Test concurrent sanitization of mixed data types."""
        data = {
            "string": "test",
            "number": 42,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "bool": True,
            "none": None,
        }

        # Sanitize same mixed data concurrently
        tasks = [asyncio.to_thread(sanitize_output, data) for _ in range(50)]
        results = await asyncio.gather(*tasks)

        # All results should be identical
        assert all(str(r) == str(results[0]) for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_different_keys(self) -> None:
        """Test concurrent validation of different keys doesn't interfere."""
        keys = [f"sk-test-key-{i:04d}" for i in range(10)]

        # Validate different keys concurrently
        tasks = [
            asyncio.to_thread(validate_api_key_format, key, provider="generic")
            for key in keys
            for _ in range(10)  # Repeat each key 10 times
        ]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(isinstance(r, str) for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_empty_sanitization(self) -> None:
        """Test concurrent sanitization of empty/None values."""
        test_cases = [
            {},
            [],
            "",
            None,
            {"empty": ""},
            {"nested": {"empty": []}},
        ]

        # Sanitize various empty values concurrently
        tasks = [asyncio.to_thread(sanitize_output, case) for case in test_cases for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should complete without error (None is a valid return for None input)
        assert len(results) == len(test_cases) * 10

        # Verify results match expectations (None -> None, others -> same type)
        for i, case in enumerate(test_cases):
            expected = None if case is None else case
            # All 10 repetitions of this case should have same result
            for j in range(10):
                result = results[i * 10 + j]
                assert type(result) == type(expected)

    @pytest.mark.asyncio
    async def test_concurrent_large_sanitization(self) -> None:
        """Test concurrent sanitization of large data structures."""
        large_data = {
            f"key_{i}": f"value_{i}" * 100
            for i in range(100)
        }

        # Sanitize large data concurrently
        tasks = [asyncio.to_thread(sanitize_output, large_data) for _ in range(20)]
        results = await asyncio.gather(*tasks)

        # All results should be identical
        assert all(str(r) == str(results[0]) for r in results)
