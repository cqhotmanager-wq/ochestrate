from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.request_context import bind_unified_request_auth
from app.auth.deps import require_auth_context
from app.auth.schemas import AuthContext
from app.core.dependencies import ServiceContainer, get_container
from app.schemas.api import UnifiedRequest, UnifiedResponse

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/run", response_model=UnifiedResponse)
def run_agent(
    request: UnifiedRequest,
    auth: AuthContext = Depends(require_auth_context),
    container: ServiceContainer = Depends(get_container),
) -> UnifiedResponse:
    scoped_request = bind_unified_request_auth(request, auth)
    return container.orchestrator.run(scoped_request)
