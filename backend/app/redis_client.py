"""Redis client — shared by rate limiter, JWT blacklist, and cache."""
import redis
import os

_redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
_pool = redis.ConnectionPool.from_url(_redis_url, max_connections=50)
redis_client = redis.Redis.from_pool(_pool)

def redis_rate_check(key: str, max_requests: int = 60, window: int = 60) -> bool:
    """Rate limiter backed by Redis. Returns True if allowed."""
    try:
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, window)
        return count <= max_requests
    except redis.RedisError:
        return True  # Fail-open if Redis is down

def redis_blacklist_add(token_hash: str, ttl: int = 604800):
    """Add token to JWT blacklist with TTL."""
    try:
        redis_client.setex(f"bl:{token_hash}", ttl, "1")
    except redis.RedisError:
        pass

def redis_blacklist_check(token_hash: str) -> bool:
    """Check if token is blacklisted."""
    try:
        return redis_client.exists(f"bl:{token_hash}") == 1
    except redis.RedisError:
        return False

def redis_cache_get(key: str) -> str | None:
    try:
        val = redis_client.get(key)
        return val.decode() if val else None
    except redis.RedisError:
        return None

def redis_cache_set(key: str, value: str, ttl: int = 300):
    try:
        redis_client.setex(key, ttl, value)
    except redis.RedisError:
        pass

def redis_cache_delete(key: str):
    try:
        redis_client.delete(key)
    except redis.RedisError:
        pass
