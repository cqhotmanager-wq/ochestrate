"""Memory facade for short-term session window and long-term persistent retrieval."""

from __future__ import annotations

from datetime import timedelta

from app.embeddings.service import EmbeddingService
from app.memory.long_term import LongTermMemoryStore
from app.memory.short_term import ShortTermMemoryStore
from app.schemas.api import MemoryUpdate
from app.storage.repositories.long_memory_repo import LongTermMemoryRecord, LongTermMemoryRepository
from app.storage.vector_gateway import VectorStoreGateway


class MemoryService:
    def __init__(
        self,
        short_turns: int,
        long_ttl_days: int,
        long_term_repository: LongTermMemoryRepository | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_gateway: VectorStoreGateway | None = None,
    ) -> None:
        self._short = ShortTermMemoryStore(max_turns=short_turns)
        self._legacy_long = LongTermMemoryStore(default_ttl_days=long_ttl_days)
        self._long_repo = long_term_repository
        self._embedding = embedding_service
        self._vectors = vector_gateway
        self._long_ttl_days = long_ttl_days

    @staticmethod
    def _session_key(tenant_id: str, user_id: str, session_id: str) -> str:
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
        self.record_outcome(
            tenant_id=tenant_id,
            user_id=user_id,
            task=content,
            solution=content,
            success=True,
            lessons_learned=None,
            tags=tags,
            ttl_days=ttl_days,
        )
        return MemoryUpdate(memory_type="long", content=content)

    def record_outcome(
        self,
        tenant_id: str,
        user_id: str,
        task: str,
        solution: str,
        success: bool,
        lessons_learned: str | None,
        tags: list[str] | None = None,
        ttl_days: int | None = None,
    ) -> None:
        if self._long_repo is None or self._embedding is None:
            self._legacy_long.add(
                tenant_id=tenant_id,
                user_id=user_id,
                content=f"task:{task}\nsolution:{solution}",
                tags=tags,
                ttl_days=ttl_days,
            )
            return

        ttl = ttl_days if ttl_days is not None else self._long_ttl_days
        now = self._long_repo.now_utc()
        expires_at = now + timedelta(days=ttl)
        text = f"{task}\n{solution}\n{lessons_learned or ''}".strip()
        embedding = self._embedding.embed_text(text)
        record = LongTermMemoryRecord(
            tenant_id=tenant_id,
            user_id=user_id,
            task=task,
            solution=solution,
            success=success,
            lessons_learned=lessons_learned,
            tags=tags or [],
            embedding=embedding,
            expires_at=expires_at,
        )
        self._long_repo.add(record)
        if self._vectors is not None:
            item_id = f"{tenant_id}:{user_id}:{int(now.timestamp() * 1000)}"
            self._vectors.upsert(
                namespace=self._namespace(tenant_id, user_id),
                item_id=item_id,
                vector=embedding,
                metadata={
                    "task": task,
                    "solution": solution,
                    "success": success,
                    "lessons_learned": lessons_learned or "",
                    "tags": tags or [],
                },
            )

    def read_long(self, tenant_id: str, user_id: str, query: str, limit: int = 5) -> list[str]:
        if self._long_repo is None or self._embedding is None:
            return [
                r.content
                for r in self._legacy_long.search(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    query=query,
                    limit=limit,
                )
            ]

        query_embedding = self._embedding.embed_text(query)
        records = self._long_repo.search(
            tenant_id=tenant_id,
            user_id=user_id,
            query_embedding=query_embedding,
            limit=limit,
        )
        return [
            f"task:{r.task}\nsolution:{r.solution}\nlessons:{r.lessons_learned or ''}"
            for r in records
        ]

    @staticmethod
    def _namespace(tenant_id: str, user_id: str) -> str:
        return f"long_memory:{tenant_id}:{user_id}"
