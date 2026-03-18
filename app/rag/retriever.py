"""检索器：把知识分块检索结果转换为引用对象。"""

from __future__ import annotations
from app.schemas.api import Citation
from app.rag.store import KnowledgeStore


class HybridRetriever:
    def __init__(self, store: KnowledgeStore) -> None:
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


