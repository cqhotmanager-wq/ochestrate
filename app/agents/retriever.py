"""检索智能体：调用 RAG 检索层并返回可引用证据。"""

from __future__ import annotations
from app.rag.retriever import HybridRetriever
from app.schemas.api import Citation, UnifiedRequest


class RetrieverAgent:
    def __init__(self, retriever: HybridRetriever) -> None:
        self._retriever = retriever

    def retrieve(self, request: UnifiedRequest) -> list[Citation]:
        return self._retriever.retrieve(tenant_id=request.tenant_id, query=request.input, limit=5)


