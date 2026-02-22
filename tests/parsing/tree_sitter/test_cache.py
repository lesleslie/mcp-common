"""Tests for tree-sitter content-hash cache."""

from __future__ import annotations

import pytest

from mcp_common.parsing.tree_sitter.cache import (
    CacheStats,
    ContentHashLRUCache,
)
from mcp_common.parsing.tree_sitter.models import (
    ParseResult,
    SupportedLanguage,
)


class TestContentHashLRUCache:
    """Tests for ContentHashLRUCache."""

    def test_basic_set_and_get(self) -> None:
        cache = ContentHashLRUCache[str](max_size=10)
        content = b"test content"

        cache.set(content, "result")
        result = cache.get(content)

        assert result == "result"

    def test_cache_miss(self) -> None:
        cache = ContentHashLRUCache[str](max_size=10)

        result = cache.get(b"not in cache")

        assert result is None

    def test_same_content_same_hash(self) -> None:
        cache = ContentHashLRUCache[str](max_size=10)
        content = b"same content"

        cache.set(content, "result1")
        # Same content should hit same cache entry
        result = cache.get(content)

        assert result == "result1"

    def test_different_content_different_hash(self) -> None:
        cache = ContentHashLRUCache[str](max_size=10)

        cache.set(b"content1", "result1")
        cache.set(b"content2", "result2")

        assert cache.get(b"content1") == "result1"
        assert cache.get(b"content2") == "result2"

    def test_lru_eviction(self) -> None:
        cache = ContentHashLRUCache[str](max_size=3)

        cache.set(b"a", "a")
        cache.set(b"b", "b")
        cache.set(b"c", "c")
        cache.set(b"d", "d")  # Should evict "a"

        stats = cache.get_stats()
        assert stats.evictions == 1
        assert cache.get(b"a") is None
        assert cache.get(b"b") == "b"

    def test_access_updates_lru(self) -> None:
        cache = ContentHashLRUCache[str](max_size=3)

        cache.set(b"a", "a")
        cache.set(b"b", "b")
        cache.set(b"c", "c")

        # Access "a" to make it most recently used
        cache.get(b"a")

        # Add new entry - should evict "b" (oldest)
        cache.set(b"d", "d")

        assert cache.get(b"a") == "a"  # Still there
        assert cache.get(b"b") is None  # Evicted

    def test_stats_tracking(self) -> None:
        cache = ContentHashLRUCache[str](max_size=10)

        # Miss
        cache.get(b"miss")

        # Set and hit
        cache.set(b"content", "result")
        cache.get(b"content")
        cache.get(b"content")

        stats = cache.get_stats()
        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.total_requests == 3
        assert stats.hit_rate == 2 / 3

    def test_clear(self) -> None:
        cache = ContentHashLRUCache[str](max_size=10)

        cache.set(b"a", "a")
        cache.set(b"b", "b")

        count = cache.clear()

        assert count == 2
        assert cache.get(b"a") is None
        assert cache.get(b"b") is None

    def test_invalidate(self) -> None:
        cache = ContentHashLRUCache[str](max_size=10)

        cache.set(b"content", "result")

        invalidated = cache.invalidate(b"content")
        assert invalidated is True

        assert cache.get(b"content") is None

        # Invalidate non-existent
        invalidated = cache.invalidate(b"not there")
        assert invalidated is False


class TestCacheStats:
    """Tests for CacheStats."""

    def test_to_dict(self) -> None:
        stats = CacheStats(
            hits=10,
            misses=5,
            evictions=2,
            cache_size=3,
            total_requests=15,
            hit_rate=0.667,
        )

        d = stats.to_dict()

        assert d["hits"] == 10
        assert d["misses"] == 5
        assert d["evictions"] == 2
        assert d["cache_size"] == 3
        assert d["total_requests"] == 15
        assert d["hit_rate"] == 0.667


class TestParseResultCache:
    """Tests for ParseResult-specific cache usage."""

    def test_cache_parse_results(self) -> None:
        cache = ContentHashLRUCache[ParseResult](max_size=10)

        result = ParseResult(
            success=True,
            file_path="test.py",
            language=SupportedLanguage.PYTHON,
            parse_time_ms=5.0,
        )

        content = b"def foo(): pass"
        cache.set(content, result)

        cached = cache.get(content)
        assert cached is not None
        assert cached.success
        assert cached.file_path == "test.py"
