from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import ServiceContainer, get_container
from app.schemas.api import UnifiedRequest, UnifiedResponse

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/run", response_model=UnifiedResponse)
def run_agent(
    request: UnifiedRequest,
    container: ServiceContainer = Depends(get_container),
) -> UnifiedResponse:
    return container.orchestrator.run(request)

