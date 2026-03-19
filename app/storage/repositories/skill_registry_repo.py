"""Persistence repository for skill registry metadata and embeddings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.storage.models import SkillRegistryEntryORM


@dataclass
class SkillRegistryRecord:
    tenant_id: str
    skill_name: str
    description: str
    skill_path: str
    tools: list[str]
    embedding: list[float]
    source: str = "skill_md"


class SkillRegistryRepository:
    def __init__(self, session_factory: sessionmaker[Session] | None) -> None:
        self._session_factory = session_factory
        self._mem: dict[tuple[str, str], SkillRegistryRecord] = {}

    def upsert(self, record: SkillRegistryRecord) -> None:
        key = (record.tenant_id, record.skill_name)
        if self._session_factory is None:
            self._mem[key] = record
            return

        with self._session_factory() as session:
            row = session.scalar(
                select(SkillRegistryEntryORM).where(
                    SkillRegistryEntryORM.tenant_id == record.tenant_id,
                    SkillRegistryEntryORM.skill_name == record.skill_name,
                )
            )
            if row is None:
                row = SkillRegistryEntryORM(
                    tenant_id=record.tenant_id,
                    skill_name=record.skill_name,
                    description=record.description,
                    skill_path=record.skill_path,
                    tools_json=record.tools,
                    embedding_json=record.embedding,
                    source=record.source,
                )
                session.add(row)
            else:
                row.description = record.description
                row.skill_path = record.skill_path
                row.tools_json = record.tools
                row.embedding_json = record.embedding
                row.source = record.source
            session.commit()

    def list_by_tenant(self, tenant_id: str) -> list[SkillRegistryRecord]:
        if self._session_factory is None:
            return [v for (t, _), v in self._mem.items() if t == tenant_id]

        with self._session_factory() as session:
            rows = (
                session.query(SkillRegistryEntryORM)
                .filter(SkillRegistryEntryORM.tenant_id == tenant_id)
                .order_by(SkillRegistryEntryORM.updated_at.desc())
                .all()
            )
        return [
            SkillRegistryRecord(
                tenant_id=row.tenant_id,
                skill_name=row.skill_name,
                description=row.description,
                skill_path=row.skill_path,
                tools=list(row.tools_json or []),
                embedding=list(row.embedding_json or []),
                source=row.source,
            )
            for row in rows
        ]

    @staticmethod
    def now_utc() -> datetime:
        return datetime.now(timezone.utc)
