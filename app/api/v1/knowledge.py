"""知识摄取接口：把文本切分为知识分块并写入知识库。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.request_context import bind_ingest_auth
from app.auth.deps import require_auth_context
from app.auth.schemas import AuthContext
from app.core.dependencies import ServiceContainer, get_container
from app.schemas.api import IngestTextRequest

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/ingest-text")
def ingest_text(
    payload: IngestTextRequest,
    auth: AuthContext = Depends(require_auth_context),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, object]:
    # 步骤：执行 `ingest_text` 的核心处理逻辑。
    scoped_payload = bind_ingest_auth(payload, auth)
    chunks = container.ingestion_pipeline.ingest_text(
        tenant_id=scoped_payload.tenant_id or "",
        source_id=scoped_payload.source_id,
        text=scoped_payload.text,
    )
    container.knowledge_store.add_chunks(chunks)
    return {"accepted": True, "chunks": len(chunks)}


