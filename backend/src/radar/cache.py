"""Valkey/Redis access: a best-effort cache, locks and pub/sub.

Cache reads and writes never raise. A cache outage slows the system down but
must not take it down, so every failure degrades to a miss.
"""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any
from uuid import uuid4

import orjson
from redis.asyncio import Redis
from redis.exceptions import RedisError

from radar.config import get_settings
from radar.logging import get_logger

log = get_logger(__name__)

_RELEASE_LOCK = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


@lru_cache
def get_redis() -> Redis:
    return Redis.from_url(
        get_settings().cache_url,
        socket_timeout=5,
        socket_connect_timeout=3,
        health_check_interval=30,
    )


class Cache:
    def __init__(self, redis: Redis, namespace: str = "radar") -> None:
        self._redis = redis
        self._ns = namespace

    def _key(self, key: str) -> str:
        return f"{self._ns}:{key}"

    async def get_json(self, key: str) -> Any | None:
        try:
            raw = await self._redis.get(self._key(key))
        except RedisError as exc:
            log.warning("cache_get_failed", key=key, error=str(exc))
            return None
        return orjson.loads(raw) if raw is not None else None

    async def set_json(self, key: str, value: Any, ttl: int) -> None:
        try:
            await self._redis.set(self._key(key), orjson.dumps(value), ex=ttl)
        except RedisError as exc:
            log.warning("cache_set_failed", key=key, error=str(exc))

    async def get_bytes(self, key: str) -> bytes | None:
        try:
            raw = await self._redis.get(self._key(key))
        except RedisError as exc:
            log.warning("cache_get_failed", key=key, error=str(exc))
            return None
        return raw if isinstance(raw, bytes) else None

    async def set_bytes(self, key: str, value: bytes, ttl: int) -> None:
        try:
            await self._redis.set(self._key(key), value, ex=ttl)
        except RedisError as exc:
            log.warning("cache_set_failed", key=key, error=str(exc))

    async def delete(self, *keys: str) -> None:
        if not keys:
            return
        try:
            await self._redis.delete(*(self._key(key) for key in keys))
        except RedisError as exc:
            log.warning("cache_delete_failed", error=str(exc))

    async def cached_json(self, key: str, ttl: int, produce: Callable[[], Awaitable[Any]]) -> Any:
        hit = await self.get_json(key)
        if hit is not None:
            return hit
        value = await produce()
        await self.set_json(key, value, ttl)
        return value

    @asynccontextmanager
    async def lock(self, name: str, ttl: int) -> AsyncIterator[bool]:
        """Non-blocking distributed lock. Yields False when someone else holds it.

        If the lock service itself is down we proceed: the guarded operations
        are idempotent, and skipping them would stall ingestion entirely.
        """
        token = uuid4().hex
        key = self._key(f"lock:{name}")
        try:
            acquired = bool(await self._redis.set(key, token, nx=True, ex=ttl))
        except RedisError as exc:
            log.warning("lock_unavailable", name=name, error=str(exc))
            yield True
            return
        try:
            yield acquired
        finally:
            if acquired:
                try:
                    await self._redis.eval(_RELEASE_LOCK, 1, key, token)
                except RedisError as exc:
                    log.warning("lock_release_failed", name=name, error=str(exc))

    async def hit_rate_limit(self, bucket: str, limit: int, window: int = 60) -> bool:
        """Fixed-window counter. Returns True when the caller is over the limit."""
        key = self._key(f"rl:{bucket}")
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, window, nx=True)
                count, _ = await pipe.execute()
        except RedisError as exc:
            log.warning("rate_limit_unavailable", error=str(exc))
            return False
        return int(count) > limit

    async def is_over_limit(self, bucket: str, limit: int) -> bool:
        """Has `bucket` already passed `limit` in its current window? Does not count."""
        try:
            count = await self._redis.get(self._key(f"rl:{bucket}"))
        except RedisError as exc:
            log.warning("rate_limit_unavailable", error=str(exc))
            return False
        return count is not None and int(count) > limit

    async def get_int(self, key: str) -> int:
        """A counter; 0 when it is missing or the server is unreachable."""
        try:
            raw = await self._redis.get(self._key(key))
        except RedisError as exc:
            log.warning("cache_get_failed", key=key, error=str(exc))
            return 0
        return int(raw) if raw is not None else 0

    async def incr(self, key: str, ttl: int | None = None) -> int | None:
        """Increment a counter; None when the server is unreachable."""
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.incr(self._key(key))
                if ttl is not None:
                    pipe.expire(self._key(key), ttl)
                results = await pipe.execute()
        except RedisError as exc:
            log.warning("cache_incr_failed", key=key, error=str(exc))
            return None
        return int(results[0])

    async def decr(self, key: str) -> None:
        try:
            await self._redis.decr(self._key(key))
        except RedisError as exc:
            log.warning("cache_decr_failed", key=key, error=str(exc))

    async def publish(self, channel: str, payload: dict[str, Any]) -> None:
        try:
            await self._redis.publish(self._key(channel), orjson.dumps(payload))
        except RedisError as exc:
            log.warning("publish_failed", channel=channel, error=str(exc))

    async def subscribe(self, channel: str) -> AsyncGenerator[dict[str, Any] | None]:
        """Yield messages from a channel; None is a heartbeat tick every second.

        The first value is always None and is produced as soon as the
        subscription is active, so a caller can subscribe, then read the
        current state from the database without missing an update in between.

        If the server goes away, the generator keeps ticking without messages
        instead of raising, and re-subscribes once the server answers again.
        Callers poll the database as a backstop, so a progress stream degrades
        to slower updates rather than breaks.
        """
        pubsub = self._redis.pubsub()
        connected = True
        try:
            try:
                await pubsub.subscribe(self._key(channel))
            except RedisError as exc:
                log.warning("subscribe_failed", channel=channel, error=str(exc))
                connected = False
            yield None
            while True:
                if not connected:
                    # Keep ticking for the caller and try to come back.
                    await asyncio.sleep(1.0)
                    try:
                        await pubsub.subscribe(self._key(channel))
                        connected = True
                    except RedisError:
                        connected = False
                    yield None
                    continue
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                except RedisError as exc:
                    log.warning("subscription_lost", channel=channel, error=str(exc))
                    connected = False
                    continue
                yield orjson.loads(message["data"]) if message else None
        finally:
            try:
                await pubsub.unsubscribe()
                await pubsub.aclose()  # type: ignore[no-untyped-call]
            except RedisError as exc:
                log.warning("unsubscribe_failed", channel=channel, error=str(exc))

    async def ping(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except RedisError:
            return False


@lru_cache
def get_cache() -> Cache:
    return Cache(get_redis())
