"""
Redis cache service — wraps redis-py with JSON serialization and TTL support.
Falls back to a TTL-aware in-memory dict when Redis is unavailable (dev/test).
"""
import json
import logging
import os
import time
import fnmatch
from typing import Any, Optional

logger = logging.getLogger(__name__)

_redis_client = None
_redis_unavailable = False
# In-memory fallback stores (value, expire_at) tuples
_fallback: dict = {}   # key -> (serialized_value, expire_at_epoch)


def _get_client():
    global _redis_client, _redis_unavailable
    if _redis_unavailable:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        _redis_client = redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        _redis_client.ping()
        logger.info(f"[CACHE] Redis connected: {url}")
    except Exception as e:
        logger.warning(f"[CACHE] Redis unavailable ({e}), using in-memory fallback")
        _redis_client = None
        _redis_unavailable = True
    return _redis_client


def _fallback_get(key: str) -> Optional[str]:
    """Get from in-memory fallback, respecting TTL."""
    entry = _fallback.get(key)
    if entry is None:
        return None
    value, expire_at = entry
    if expire_at and time.time() > expire_at:
        _fallback.pop(key, None)
        return None
    return value


def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    """Store value in cache with TTL (seconds)."""
    client = _get_client()
    try:
        serialized = json.dumps(value)
        if client:
            client.setex(key, ttl, serialized)
        else:
            _fallback[key] = (serialized, time.time() + ttl if ttl else None)
        return True
    except Exception as e:
        logger.error(f"[CACHE] set error for {key}: {e}")
        return False


def cache_get(key: str) -> Optional[Any]:
    """Retrieve value from cache. Returns None on miss or expiry."""
    client = _get_client()
    try:
        raw = client.get(key) if client else _fallback_get(key)
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.error(f"[CACHE] get error for {key}: {e}")
        return None


def cache_delete(key: str) -> bool:
    """Invalidate a cache key."""
    client = _get_client()
    try:
        if client:
            client.delete(key)
        else:
            _fallback.pop(key, None)
        return True
    except Exception as e:
        logger.error(f"[CACHE] delete error for {key}: {e}")
        return False


def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching a glob pattern."""
    client = _get_client()
    deleted = 0
    if not client:
        keys_to_delete = [k for k in list(_fallback.keys()) if fnmatch.fnmatch(k, pattern)]
        for k in keys_to_delete:
            _fallback.pop(k, None)
            deleted += 1
        return deleted
    try:
        keys = client.keys(pattern)
        if keys:
            return client.delete(*keys)
        return 0
    except Exception as e:
        logger.error(f"[CACHE] delete_pattern error: {e}")
        return 0


def cache_stats() -> dict:
    """Return cache backend info for monitoring."""
    client = _get_client()
    if client:
        try:
            info = client.info('memory')
            return {
                'backend': 'redis',
                'used_memory_human': info.get('used_memory_human', 'N/A'),
                'connected_clients': client.info('clients').get('connected_clients', 0),
            }
        except Exception:
            pass
    # In-memory fallback stats
    now = time.time()
    live = sum(1 for _, (_, exp) in _fallback.items() if not exp or exp > now)
    return {'backend': 'memory', 'live_keys': live, 'total_keys': len(_fallback)}
