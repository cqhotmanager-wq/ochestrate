"""知识摄取：将原始文本切分为可检索知识分块。"""

from __future__ import annotations
import hashlib

from app.schemas.specs import KnowledgeChunk

try:
    from llama_index.core.node_parser import SentenceSplitter
except Exception:  # pragma: no cover - optional runtime dependency
    SentenceSplitter = None


class IngestionPipeline:
    def __init__(self) -> None:
        # 优先使用 LlamaIndex 的句子分割器；不可用时回退到固定长度切分。
        self._splitter = SentenceSplitter(chunk_size=512, chunk_overlap=64) if SentenceSplitter else None

    def ingest_text(self, tenant_id: str, source_id: str, text: str, chunk_size: int = 600) -> list[KnowledgeChunk]:
        """摄取文本并输出知识分块。"""
        # 步骤：执行 `ingest_text` 的核心处理逻辑。
        chunks: list[KnowledgeChunk] = []
        raw_chunks: list[str] = []
        if self._splitter is not None:
            for idx, content in enumerate(self._splitter.split_text(text)):
                raw_chunks.append(content)
        else:
            for idx in range(0, len(text), chunk_size):
                raw_chunks.append(text[idx : idx + chunk_size])

        for idx, content in enumerate(raw_chunks):
            chunk_id = hashlib.md5(f"{source_id}:{idx}".encode("utf-8")).hexdigest()
            chunks.append(
                KnowledgeChunk(
                    tenant_id=tenant_id,
                    source_id=source_id,
                    chunk_id=chunk_id,
                    content=content,
                    metadata={"index": idx},
                )
            )
        return chunks


