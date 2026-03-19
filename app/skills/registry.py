"""Skill registry synchronization and vector retrieval."""

from __future__ import annotations

from typing import Any

from app.embeddings.service import EmbeddingService
from app.schemas.api import SkillMatch
from app.skills.context import SkillContextService
from app.storage.repositories.skill_registry_repo import SkillRegistryRecord, SkillRegistryRepository
from app.storage.vector_gateway import VectorStoreGateway


class SkillRegistryService:
    def __init__(
        self,
        context_service: SkillContextService,
        repository: SkillRegistryRepository,
        embedding_service: EmbeddingService,
        vector_gateway: VectorStoreGateway,
    ) -> None:
        self._context_service = context_service
        self._repo = repository
        self._embedding = embedding_service
        self._vectors = vector_gateway

    def sync(self, tenant_id: str, known_tools: list[str]) -> list[SkillRegistryRecord]:
        namespace = self._namespace(tenant_id)
        records: list[SkillRegistryRecord] = []
        for item in self._context_service.load():
            tools = self._infer_tools(item.description, known_tools)
            text = f"{item.name}\n{item.description}".strip()
            embedding = self._embedding.embed_text(text)
            record = SkillRegistryRecord(
                tenant_id=tenant_id,
                skill_name=item.name,
                description=item.description,
                skill_path=item.skill_path,
                tools=tools,
                embedding=embedding,
                source="skill_center" if item.explicit_enabled else "skill_md",
            )
            self._repo.upsert(record)
            self._vectors.upsert(
                namespace=namespace,
                item_id=item.name,
                vector=embedding,
                metadata={
                    "skill_name": item.name,
                    "description": item.description,
                    "skill_path": item.skill_path,
                    "tools": tools,
                },
            )
            records.append(record)
        return records

    def retrieve(self, tenant_id: str, query: str, top_k: int = 5) -> list[SkillMatch]:
        namespace = self._namespace(tenant_id)
        query_embedding = self._embedding.embed_text(query)
        hits = self._vectors.search(namespace=namespace, vector=query_embedding, top_k=top_k)
        by_name = {r.skill_name: r for r in self._repo.list_by_tenant(tenant_id)}

        results: list[SkillMatch] = []
        for hit in hits:
            record = by_name.get(hit.item_id)
            metadata: dict[str, Any] = hit.metadata or {}
            if record is None:
                results.append(
                    SkillMatch(
                        name=str(metadata.get("skill_name", hit.item_id)),
                        description=str(metadata.get("description", "")),
                        score=hit.score,
                        skill_path=str(metadata.get("skill_path", "")),
                        tools=list(metadata.get("tools", [])),
                    )
                )
                continue
            results.append(
                SkillMatch(
                    name=record.skill_name,
                    description=record.description,
                    score=hit.score,
                    skill_path=record.skill_path,
                    tools=record.tools,
                )
            )
        return results

    @staticmethod
    def _infer_tools(description: str, known_tools: list[str]) -> list[str]:
        normalized = description.lower()
        return [tool for tool in known_tools if tool.lower() in normalized]

    @staticmethod
    def _namespace(tenant_id: str) -> str:
        return f"skills:{tenant_id}"
