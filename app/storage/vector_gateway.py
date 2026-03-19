"""Vector store gateway with optional Milvus backend and in-memory fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.embeddings.service import EmbeddingService

try:
    from pymilvus import MilvusClient
except Exception:  # pragma: no cover
    MilvusClient = None


@dataclass
class VectorSearchHit:
    item_id: str
    score: float
    metadata: dict[str, Any]


class VectorStoreGateway:
    def __init__(
        self,
        milvus_uri: str,
        collection_name: str = "agent_vectors",
        dimension: int = 64,
        use_milvus: bool = True,
    ) -> None:
        self._milvus_uri = milvus_uri
        self._collection_name = collection_name
        self._dimension = dimension
        self._memory: dict[str, dict[str, tuple[list[float], dict[str, Any]]]] = {}
        self._client = None

        if use_milvus and MilvusClient is not None:
            try:
                self._client = MilvusClient(uri=milvus_uri)
                self._ensure_collection()
            except Exception:
                self._client = None

    def _ensure_collection(self) -> None:
        if self._client is None:
            return
        if self._client.has_collection(self._collection_name):
            return
        self._client.create_collection(
            collection_name=self._collection_name,
            dimension=self._dimension,
            primary_field_name="id",
            id_type="string",
            vector_field_name="vector",
            metric_type="COSINE",
            consistency_level="Strong",
            auto_id=False,
        )

    def upsert(self, namespace: str, item_id: str, vector: list[float], metadata: dict[str, Any]) -> None:
        self._memory.setdefault(namespace, {})[item_id] = (vector, metadata)
        if self._client is None:
            return

        payload = {
            "id": f"{namespace}:{item_id}",
            "namespace": namespace,
            "item_id": item_id,
            "vector": vector,
            "metadata": metadata,
        }
        self._client.upsert(collection_name=self._collection_name, data=[payload])

    def search(self, namespace: str, vector: list[float], top_k: int = 5) -> list[VectorSearchHit]:
        if self._client is not None:
            try:
                response = self._client.search(
                    collection_name=self._collection_name,
                    data=[vector],
                    limit=top_k,
                    filter=f'namespace == "{namespace}"',
                    output_fields=["item_id", "metadata"],
                )
                hits = response[0] if response else []
                return [
                    VectorSearchHit(
                        item_id=str(hit.get("entity", {}).get("item_id", "")),
                        score=float(hit.get("distance", 0.0)),
                        metadata=dict(hit.get("entity", {}).get("metadata", {})),
                    )
                    for hit in hits
                ]
            except Exception:
                pass

        namespace_store = self._memory.get(namespace, {})
        scored: list[VectorSearchHit] = []
        for item_id, (candidate_vector, metadata) in namespace_store.items():
            score = EmbeddingService.cosine_similarity(vector, candidate_vector)
            scored.append(VectorSearchHit(item_id=item_id, score=score, metadata=metadata))
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]
