"""队列后端抽象：支持内存队列与 Redis 队列实现。"""

from __future__ import annotations

import asyncio

try:
    from redis.asyncio import Redis
except Exception:  # pragma: no cover
    Redis = None


class QueueBackend:
    """队列后端抽象接口。"""

    async def enqueue(self, item: str) -> None:  # pragma: no cover
        raise NotImplementedError

    async def dequeue(self, timeout_seconds: float) -> str | None:  # pragma: no cover
        raise NotImplementedError


class InMemoryQueueBackend(QueueBackend):
    """内存队列实现，适用于本地开发与测试环境。"""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    async def enqueue(self, item: str) -> None:
        await self._queue.put(item)

    async def dequeue(self, timeout_seconds: float) -> str | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None


class RedisQueueBackend(QueueBackend):
    """Redis 队列实现，适用于可横向扩展的生产部署。"""

    def __init__(self, redis_url: str, queue_name: str) -> None:
        if Redis is None:
            raise RuntimeError("redis package is not available")
        self._client = Redis.from_url(redis_url, decode_responses=True)
        self._queue_name = queue_name

    async def enqueue(self, item: str) -> None:
        await self._client.rpush(self._queue_name, item)

    async def dequeue(self, timeout_seconds: float) -> str | None:
        result = await self._client.blpop(self._queue_name, timeout=int(max(timeout_seconds, 1)))
        if result is None:
            return None
        _, value = result
        return value



