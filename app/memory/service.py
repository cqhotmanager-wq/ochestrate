"""记忆服务门面：统一封装短期与长期记忆读写接口。"""

from __future__ import annotations
from app.memory.long_term import LongTermMemoryStore
from app.memory.short_term import ShortTermMemoryStore
from app.schemas.api import MemoryUpdate


class MemoryService:
    def __init__(self, short_turns: int, long_ttl_days: int) -> None:
        self._short = ShortTermMemoryStore(max_turns=short_turns)
        self._long = LongTermMemoryStore(default_ttl_days=long_ttl_days)

    @staticmethod
    def _session_key(tenant_id: str, user_id: str, session_id: str) -> str:
        # 会话主键格式：tenant:user:session
        return f"{tenant_id}:{user_id}:{session_id}"

    def write_short(self, tenant_id: str, user_id: str, session_id: str, content: str) -> MemoryUpdate:
        key = self._session_key(tenant_id, user_id, session_id)
        self._short.add_turn(key, content)
        return MemoryUpdate(memory_type="short", content=content)

    def read_short(self, tenant_id: str, user_id: str, session_id: str) -> list[str]:
        key = self._session_key(tenant_id, user_id, session_id)
        return self._short.window(key)

    def write_long(
        self,
        tenant_id: str,
        user_id: str,
        content: str,
        tags: list[str] | None = None,
        ttl_days: int | None = None,
    ) -> MemoryUpdate:
        self._long.add(tenant_id=tenant_id, user_id=user_id, content=content, tags=tags, ttl_days=ttl_days)
        return MemoryUpdate(memory_type="long", content=content)

    def read_long(self, tenant_id: str, user_id: str, query: str, limit: int = 5) -> list[str]:
        return [r.content for r in self._long.search(tenant_id=tenant_id, user_id=user_id, query=query, limit=limit)]


