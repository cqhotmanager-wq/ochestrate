"""Milvus 适配器：负责向量存储连通性检查。"""

from __future__ import annotations
try:
    from pymilvus import connections
except Exception:  # pragma: no cover - optional dependency at runtime
    connections = None


class MilvusAdapter:
    def __init__(self, uri: str) -> None:
        self._uri = uri

    def healthcheck(self) -> bool:
        # 仅做连通性检查，不进行集合级别校验。
        if connections is None:
            return False
        try:
            connections.connect(alias="default", uri=self._uri)
            return True
        except Exception:
            return False


