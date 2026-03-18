"""长期记忆存储：按租户用户保存带 TTL 的记忆记录。"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone

from app.schemas.specs import MemoryRecord


class LongTermMemoryStore:
    def __init__(self, default_ttl_days: int) -> None:
        self._default_ttl_days = default_ttl_days
        self._records: list[MemoryRecord] = []

    def add(
        self,
        tenant_id: str,
        user_id: str,
        content: str,
        tags: list[str] | None = None,
        ttl_days: int | None = None,
    ) -> MemoryRecord:
        # 支持按写入时覆盖 TTL，满足“用户/部门可配置”的保留策略。
        now = datetime.now(timezone.utc)
        expire_days = ttl_days if ttl_days is not None else self._default_ttl_days
        record = MemoryRecord(
            tenant_id=tenant_id,
            user_id=user_id,
            content=content,
            tags=tags or [],
            created_at=now,
            expires_at=now + timedelta(days=expire_days),
        )
        self._records.append(record)
        return record

    def search(self, tenant_id: str, user_id: str, query: str, limit: int = 5) -> list[MemoryRecord]:
        # 检索时自动过滤过期数据。
        now = datetime.now(timezone.utc)
        normalized = query.lower()
        valid = [
            r
            for r in self._records
            if r.tenant_id == tenant_id
            and r.user_id == user_id
            and r.expires_at > now
            and (normalized in r.content.lower() or not normalized)
        ]
        return valid[:limit]


