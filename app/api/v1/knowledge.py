from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import ServiceContainer, get_container
from app.schemas.api import IngestTextRequest

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/ingest-text")
def ingest_text(
    payload: IngestTextRequest,
    container: ServiceContainer = Depends(get_container),
) -> dict[str, object]:
    chunks = container.ingestion_pipeline.ingest_text(
        tenant_id=payload.tenant_id,
        source_id=payload.source_id,
        text=payload.text,
    )
    container.knowledge_store.add_chunks(chunks)
    return {"accepted": True, "chunks": len(chunks)}

