"""
Cache abstraction: Redis wrapper for query result caching and embedding cache.
Graceful degradation when Redis is unavailable.
"""

import logging
import hashlib
import json
import pickle
from typing import Optional, Any, Dict, Union
from datetime import timedelta

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("redis-py not installed; caching disabled")

logger = logging.getLogger(__name__)


class Cache:
    """Simple key-value cache with TTL, backed by Redis or in-memory dict."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        prefix: str = "verity:",
        default_ttl: int = 3600,
    ):
        """
        Initialize cache.

        Args:
            redis_url: Redis connection URL (redis://localhost:6379/0)
            prefix: Key namespace prefix
            default_ttl: Default TTL in seconds
        """
        self.prefix = prefix
        self.default_ttl = default_ttl
        self.client: Optional["redis.Redis"] = None
        self.fallback: Dict[str, Any] = {}  # In-memory if Redis unavailable

        if REDIS_AVAILABLE and redis_url:
            try:
                self.client = redis.from_url(redis_url, decode_responses=False)
                self.client.ping()
                logger.info(f"Redis cache connected at {redis_url}")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}; using in-memory fallback")
                self.client = None

    def _key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve cached value."""
        full_key = self._key(key)

        if self.client:
            try:
                value = self.client.get(full_key)
                if value is not None:
                    return pickle.loads(value)
            except Exception as e:
                logger.error(f"Redis get error: {e}")

        return self.fallback.get(key, default)

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Store value in cache.

        Args:
            key: Cache key
            value: Any JSON/pickle-serializable object
            ttl: Time-to-live in seconds (default: self.default_ttl)

        Returns:
            True if successful
        """
        full_key = self._key(key)
        ttl = ttl or self.default_ttl

        # Serialize
        try:
            serialized = pickle.dumps(value)
        except Exception as e:
            logger.error(f"Cache serialization failed: {e}")
            return False

        if self.client:
            try:
                self.client.setex(full_key, ttl, serialized)
                return True
            except Exception as e:
                logger.error(f"Redis setex error: {e}")

        # Fallback in-memory
        self.fallback[key] = value
        return True

    def delete(self, key: str) -> bool:
        """Remove entry from cache."""
        full_key = self._key(key)
        if self.client:
            try:
                self.client.delete(full_key)
                return True
            except Exception:
                pass
        self.fallback.pop(key, None)
        return True

    def clear(self):
        """Clear all keys in this namespace (dangerous!)."""
        if self.client:
            try:
                pattern = f"{self.prefix}*"
                keys = self.client.keys(pattern)
                if keys:
                    self.client.delete(*keys)
            except Exception as e:
                logger.error(f"Redis clear error: {e}")
        self.fallback.clear()

    def get_or_compute(
        self,
        key: str,
        compute_func,
        ttl: Optional[int] = None,
    ) -> Any:
        """
        Get from cache or compute and store if missing.

        Args:
            key: Cache key
            compute_func: Callable that returns value to cache
            ttl: Optional TTL override

        Returns:
            Cached or computed value
        """
        cached = self.get(key)
        if cached is not None:
            return cached

        value = compute_func()
        self.set(key, value, ttl=ttl)
        return value

    def info(self) -> Dict[str, Any]:
        """Return cache statistics."""
        if self.client:
            try:
                info = self.client.info()
                return {
                    "type": "redis",
                    "connected": True,
                    "keys": self.client.dbsize(),
                    "memory_used": info.get("used_memory_human", "unknown"),
                }
            except Exception:
                pass
        return {
            "type": "memory",
            "connected": False,
            "keys": len(self.fallback),
        }
