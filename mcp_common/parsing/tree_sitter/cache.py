"""Content-hash LRU cache for parsed ASTs.

Uses content hash (SHA-256) instead of mtime for cache keys.

Benefits:
- No false invalidation on metadata changes
- Works with content from any source (file, string, network)
- Deterministic cache keys
- Safe for distributed systems
"""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Generic, TypeVar

from mcp_common.parsing.tree_sitter.models import ParseResult

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """Cached result with content hash and metadata."""

    result: T
    content_hash: str
    cached_at: float = field(default_factory=time.time)
    access_count: int = 0
    size_bytes: int = 0


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    cache_size: int = 0
    total_requests: int = 0
    hit_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "cache_size": self.cache_size,
            "total_requests": self.total_requests,
            "hit_rate": round(self.hit_rate, 3),
        }


class ContentHashLRUCache(Generic[T]):
    """Thread-safe LRU cache using content hash.

    Uses SHA-256 hash of content as cache key instead of file mtime.
    This provides more reliable caching across different storage backends.

    Example:
        >>> cache = ContentHashLRUCache[ParseResult](max_size=1000)
        >>> content = b"def foo(): pass"
        >>> result = cache.get(content)
        >>> if result is None:
        ...     result = parse(content)
        ...     cache.set(content, result)
    """

    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: int = 3600,
    ) -> None:
        """Initialize the cache.

        Args:
            max_size: Maximum number of entries
            ttl_seconds: Time-to-live in seconds (default 1 hour)
        """
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._lock = RLock()
        self._stats = CacheStats()

    def _hash_content(self, content: bytes) -> str:
        """Compute SHA-256 hash of content.

        Uses first 16 characters for shorter keys while
        maintaining low collision probability.
        """
        return hashlib.sha256(content).hexdigest()[:16]

    def get(self, content: bytes) -> T | None:
        """Get cached result by content hash.

        Args:
            content: Raw bytes to hash for cache lookup

        Returns:
            Cached result or None if not found/expired
        """
        content_hash = self._hash_content(content)

        with self._lock:
            if content_hash not in self._cache:
                self._stats.misses += 1
                self._stats.total_requests += 1
                return None

            entry = self._cache[content_hash]

            # Check TTL
            if time.time() - entry.cached_at > self._ttl_seconds:
                del self._cache[content_hash]
                self._stats.cache_size = len(self._cache)
                self._stats.misses += 1
                self._stats.total_requests += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(content_hash)
            entry.access_count += 1
            self._stats.hits += 1
            self._stats.total_requests += 1
            self._stats.hit_rate = (
                self._stats.hits / self._stats.total_requests
                if self._stats.total_requests > 0
                else 0.0
            )

            return entry.result

    def set(
        self,
        content: bytes,
        result: T,
        size_bytes: int | None = None,
    ) -> None:
        """Cache result by content hash.

        Args:
            content: Raw bytes to hash for cache key
            result: Parsed result to cache
            size_bytes: Optional size hint for memory tracking
        """
        content_hash = self._hash_content(content)

        with self._lock:
            # Evict if at capacity
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
                self._stats.evictions += 1

            self._cache[content_hash] = CacheEntry(
                result=result,
                content_hash=content_hash,
                size_bytes=size_bytes or len(content),
            )
            self._stats.cache_size = len(self._cache)

    def invalidate(self, content: bytes) -> bool:
        """Remove entry from cache.

        Args:
            content: Raw bytes to hash for cache lookup

        Returns:
            True if entry was removed, False if not found
        """
        content_hash = self._hash_content(content)

        with self._lock:
            if content_hash in self._cache:
                del self._cache[content_hash]
                self._stats.cache_size = len(self._cache)
                return True
            return False

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._stats.cache_size = 0
            return count

    def get_stats(self) -> CacheStats:
        """Get cache statistics.

        Returns snapshot of current statistics.
        """
        with self._lock:
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                cache_size=len(self._cache),
                total_requests=self._stats.total_requests,
                hit_rate=self._stats.hit_rate,
            )

    def prune_expired(self) -> int:
        """Remove expired entries.

        Returns:
            Number of entries removed
        """
        now = time.time()
        count = 0

        with self._lock:
            expired = [
                h for h, e in self._cache.items()
                if now - e.cached_at > self._ttl_seconds
            ]
            for h in expired:
                del self._cache[h]
                count += 1
            self._stats.cache_size = len(self._cache)

        return count


# Type alias for common use case
ParseResultCache = ContentHashLRUCache[ParseResult]
