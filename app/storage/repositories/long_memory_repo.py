"""Persistence repository for long-term memory records and embeddings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.embeddings.service import EmbeddingService
from app.storage.models import LongTermMemoryORM


@dataclass
class LongTermMemoryRecord:
    tenant_id: str
    user_id: str
    task: str
    solution: str
    success: bool
    lessons_learned: str | None
    tags: list[str]
    embedding: list[float]
    expires_at: datetime


class LongTermMemoryRepository:
    def __init__(self, session_factory: sessionmaker[Session] | None) -> None:
        self._session_factory = session_factory
        self._mem: list[LongTermMemoryRecord] = []

    def add(self, record: LongTermMemoryRecord) -> None:
        if self._session_factory is None:
            self._mem.append(record)
            return

        with self._session_factory() as session:
            session.add(
                LongTermMemoryORM(
                    tenant_id=record.tenant_id,
                    user_id=record.user_id,
                    task=record.task,
                    solution=record.solution,
                    success=record.success,
                    lessons_learned=record.lessons_learned,
                    tags_json=record.tags,
                    embedding_json=record.embedding,
                    expires_at=record.expires_at,
                )
            )
            session.commit()

    def search(self, tenant_id: str, user_id: str, query_embedding: list[float], limit: int = 5) -> list[LongTermMemoryRecord]:
        now = self.now_utc()
        if self._session_factory is None:
            candidates = [
                item
                for item in self._mem
                if item.tenant_id == tenant_id and item.user_id == user_id and item.expires_at > now
            ]
            return self._rank(candidates, query_embedding, limit)

        with self._session_factory() as session:
            rows = (
                session.query(LongTermMemoryORM)
                .filter(
                    LongTermMemoryORM.tenant_id == tenant_id,
                    LongTermMemoryORM.user_id == user_id,
                    LongTermMemoryORM.expires_at > now,
                )
                .order_by(LongTermMemoryORM.created_at.desc())
                .limit(400)
                .all()
            )

        candidates = [
            LongTermMemoryRecord(
                tenant_id=row.tenant_id,
                user_id=row.user_id,
                task=row.task,
                solution=row.solution,
                success=row.success,
                lessons_learned=row.lessons_learned,
                tags=list(row.tags_json or []),
                embedding=list(row.embedding_json or []),
                expires_at=row.expires_at,
            )
            for row in rows
        ]
        return self._rank(candidates, query_embedding, limit)

    @staticmethod
    def _rank(
        candidates: list[LongTermMemoryRecord],
        query_embedding: list[float],
        limit: int,
    ) -> list[LongTermMemoryRecord]:
        scored: list[tuple[float, LongTermMemoryRecord]] = []
        for item in candidates:
            score = EmbeddingService.cosine_similarity(query_embedding, item.embedding)
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    @staticmethod
    def now_utc() -> datetime:
        return datetime.now(timezone.utc)
