from __future__ import annotations

"""Retriever Agent：封装检索层，返回可引用证据。"""

from app.rag.retriever import HybridRetriever
from app.schemas.api import Citation, UnifiedRequest


class RetrieverAgent:
    def __init__(self, retriever: HybridRetriever) -> None:
        self._retriever = retriever

    def retrieve(self, request: UnifiedRequest) -> list[Citation]:
        return self._retriever.retrieve(tenant_id=request.tenant_id, query=request.input, limit=5)
