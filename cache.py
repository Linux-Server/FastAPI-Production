import json
import os

from redis.asyncio import Redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "10"))  # seconds

redis = Redis.from_url(REDIS_URL, decode_responses=True)


def _cache_key(prefix: str, **kwargs) -> str:
    parts = [prefix] + [f"{k}={v}" for k, v in sorted(kwargs.items()) if v is not None]
    return ":".join(parts)


async def get_cache(prefix: str, **kwargs) -> dict | None:
    key = _cache_key(prefix, **kwargs)
    data = await redis.get(key)
    if data:
        return json.loads(data)
    return None


async def set_cache(value: dict, prefix: str, **kwargs) -> None:
    key = _cache_key(prefix, **kwargs)
    await redis.set(key, json.dumps(value), ex=CACHE_TTL)


async def invalidate_cache(prefix: str) -> None:
    keys = []
    async for key in redis.scan_iter(f"{prefix}:*"):
        keys.append(key)
    if keys:
        await redis.delete(*keys)
