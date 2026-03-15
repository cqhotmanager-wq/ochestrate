from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.request_context import bind_unified_request_auth
from app.auth.deps import require_auth_context
from app.auth.schemas import AuthContext
from app.core.dependencies import ServiceContainer, get_container
from app.schemas.api import SubmitTaskRequest, TaskStatusResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/submit")
async def submit_task(
    payload: SubmitTaskRequest,
    auth: AuthContext = Depends(require_auth_context),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, str]:
    scoped_request = bind_unified_request_auth(payload.request, auth)
    task_id = await container.task_manager.submit(scoped_request)
    return {"task_id": task_id}


@router.get("/{task_id}", response_model=TaskStatusResponse)
def get_task_status(
    task_id: str,
    auth: AuthContext = Depends(require_auth_context),
    container: ServiceContainer = Depends(get_container),
) -> TaskStatusResponse:
    status = container.task_manager.get_status(task_id)
    record = container.task_repository.get(task_id)
    if record is None:
        return status
    if record.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cross-tenant task access denied")
    return status
