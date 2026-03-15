from __future__ import annotations

"""知识分块存储（内存版）。

生产环境可替换为 Milvus + 外部关键词索引。
"""

from app.schemas.specs import KnowledgeChunk


class InMemoryKnowledgeStore:
    def __init__(self) -> None:
        self._chunks: list[KnowledgeChunk] = []

    def add_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        self._chunks.extend(chunks)

    def search(self, tenant_id: str, query: str, limit: int = 5) -> list[KnowledgeChunk]:
        # tenant 级过滤，保证多租户数据隔离。
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
