from __future__ import annotations

"""混合检索器：将知识分块转换为可返回的引用结果。"""

from app.schemas.api import Citation
from app.rag.store import InMemoryKnowledgeStore


class HybridRetriever:
    def __init__(self, store: InMemoryKnowledgeStore) -> None:
        self._store = store

    def retrieve(self, tenant_id: str, query: str, limit: int = 5) -> list[Citation]:
        # 当前实现使用简单排序，后续可替换为向量+关键词+元数据混合重排。
        chunks = self._store.search(tenant_id=tenant_id, query=query, limit=limit)
        citations: list[Citation] = []
        for idx, chunk in enumerate(chunks):
            citations.append(
                Citation(
                    source_id=chunk.source_id,
                    chunk_id=chunk.chunk_id,
                    snippet=chunk.content[:200],
                    score=max(0.1, 1.0 - idx * 0.1),
                )
            )
        return citations
