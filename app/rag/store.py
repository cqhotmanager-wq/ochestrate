"""知识存储门面：支持内存与持久化仓储双模式。"""

from __future__ import annotations
from app.schemas.specs import KnowledgeChunk
from app.storage.repositories.knowledge_repo import KnowledgeRepository


class KnowledgeStore:
    def __init__(self, repository: KnowledgeRepository | None = None) -> None:
        self._repository = repository
        self._chunks: list[KnowledgeChunk] = []

    def add_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        if self._repository is not None:
            self._repository.add_chunks(chunks)
            return
        self._chunks.extend(chunks)

    def search(self, tenant_id: str, query: str, limit: int = 5) -> list[KnowledgeChunk]:
        if self._repository is not None:
            return self._repository.search(tenant_id=tenant_id, query=query, limit=limit)

        normalized = query.lower().strip()
        candidates = [c for c in self._chunks if c.tenant_id == tenant_id]
        if not normalized:
            return candidates[:limit]

        scored: list[tuple[int, KnowledgeChunk]] = []
        for chunk in candidates:
            score = sum(1 for token in normalized.split() if token in chunk.content.lower())
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:limit]]


class InMemoryKnowledgeStore(KnowledgeStore):
    def __init__(self) -> None:
        super().__init__(repository=None)



