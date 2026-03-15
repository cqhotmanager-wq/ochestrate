from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import ServiceContainer, get_container
from app.schemas.api import SubmitTaskRequest, TaskStatusResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/submit")
async def submit_task(
    payload: SubmitTaskRequest,
    container: ServiceContainer = Depends(get_container),
) -> dict[str, str]:
    task_id = await container.task_manager.submit(payload.request)
    return {"task_id": task_id}


@router.get("/{task_id}", response_model=TaskStatusResponse)
def get_task_status(
    task_id: str,
    container: ServiceContainer = Depends(get_container),
) -> TaskStatusResponse:
    return container.task_manager.get_status(task_id)

