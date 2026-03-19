"""知识仓储：保存知识分块并执行检索排序。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.schemas.specs import KnowledgeChunk
from app.storage.models import KnowledgeChunkORM


class KnowledgeRepository:
    def __init__(self, session_factory: sessionmaker[Session] | None) -> None:
        # 步骤：执行 `__init__` 的核心处理逻辑。
        self._session_factory = session_factory
        self._mem: list[KnowledgeChunk] = []

    def add_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        # 步骤：执行 `add_chunks` 的核心处理逻辑。
        if not chunks:
            return

        if self._session_factory is None:
            self._mem.extend(chunks)
            return

        with self._session_factory() as session:
            for chunk in chunks:
                existing = session.scalar(
                    select(KnowledgeChunkORM).where(
                        KnowledgeChunkORM.tenant_id == chunk.tenant_id,
                        KnowledgeChunkORM.source_id == chunk.source_id,
                        KnowledgeChunkORM.chunk_id == chunk.chunk_id,
                    )
                )
                if existing is None:
                    session.add(
                        KnowledgeChunkORM(
                            tenant_id=chunk.tenant_id,
                            source_id=chunk.source_id,
                            chunk_id=chunk.chunk_id,
                            content=chunk.content,
                            metadata_json=chunk.metadata,
                        )
                    )
                else:
                    existing.content = chunk.content
                    existing.metadata_json = chunk.metadata
            session.commit()

    def search(self, tenant_id: str, query: str, limit: int = 5) -> list[KnowledgeChunk]:
        # 步骤：执行 `search` 的核心处理逻辑。
        normalized = query.lower().strip()

        if self._session_factory is None:
            candidates = [c for c in self._mem if c.tenant_id == tenant_id]
            return self._rank(candidates, normalized, limit)

        with self._session_factory() as session:
            rows = (
                session.query(KnowledgeChunkORM)
                .filter(KnowledgeChunkORM.tenant_id == tenant_id)
                .order_by(KnowledgeChunkORM.created_at.desc())
                .limit(300)
                .all()
            )

        chunks = [
            KnowledgeChunk(
                tenant_id=row.tenant_id,
                source_id=row.source_id,
                chunk_id=row.chunk_id,
                content=row.content,
                metadata=row.metadata_json or {},
            )
            for row in rows
        ]
        return self._rank(chunks, normalized, limit)

    @staticmethod
    def _rank(chunks: list[KnowledgeChunk], normalized_query: str, limit: int) -> list[KnowledgeChunk]:
        # 步骤：执行 `_rank` 的核心处理逻辑。
        if not normalized_query:
            return chunks[:limit]

        tokens = [token for token in normalized_query.split() if token]
        scored: list[tuple[int, KnowledgeChunk]] = []
        for chunk in chunks:
            content = chunk.content.lower()
            score = sum(1 for token in tokens if token in content)
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:limit]]


