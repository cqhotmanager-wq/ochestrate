"""异步任务接口：提交任务、查询状态并通过 SSE 推送进度。"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Request
from fastapi.responses import StreamingResponse

from app.api.v1.request_context import bind_unified_request_auth
from app.auth.deps import require_auth_context
from app.auth.schemas import AuthContext
from app.core.dependencies import ServiceContainer, get_container
from app.schemas.api import SubmitTaskRequest, TaskStatusResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _assert_task_tenant_access(task_id: str, auth: AuthContext, container: ServiceContainer) -> None:
    """任务租户隔离校验。

    说明：
    - 只有同租户用户才允许读取任务状态与事件流。
    - 当任务不存在时不在此处抛 404，由后续状态查询统一返回语义化错误。
    """
    record = container.task_repository.get(task_id)
    if record is None:
        return
    if record.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cross-tenant task access denied")


def _format_sse(event: str, payload: str) -> str:
    """格式化 SSE 消息帧。"""
    return f"event: {event}\ndata: {payload}\n\n"


@router.post("/submit")
async def submit_task(
    payload: SubmitTaskRequest,
    auth: AuthContext = Depends(require_auth_context),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, str]:
    """提交异步任务并返回任务 ID。"""
    # 不信任请求体中的 tenant/user 字段，统一使用鉴权上下文覆盖。
    scoped_request = bind_unified_request_auth(payload.request, auth)
    task_id = await container.task_manager.submit(scoped_request)
    return {"task_id": task_id}


@router.get("/{task_id}", response_model=TaskStatusResponse)
def get_task_status(
    task_id: str,
    auth: AuthContext = Depends(require_auth_context),
    container: ServiceContainer = Depends(get_container),
) -> TaskStatusResponse:
    """查询任务状态。"""
    _assert_task_tenant_access(task_id, auth, container)
    task_status = container.task_manager.get_status(task_id)
    return task_status


@router.get("/{task_id}/events")
async def stream_task_status(
    task_id: str,
    request: Request,
    auth: AuthContext = Depends(require_auth_context),
    container: ServiceContainer = Depends(get_container),
) -> StreamingResponse:
    """订阅任务状态事件流（SSE）。"""
    _assert_task_tenant_access(task_id, auth, container)

    async def event_stream() -> AsyncIterator[str]:
        # 任务管理器在订阅建立时会先投递当前快照，这里可直接透传给客户端。
        async for current in container.task_manager.subscribe_status(task_id):
            if await request.is_disconnected():
                break
            yield _format_sse("task_status", current.model_dump_json())
            if current.status in {"completed", "failed"}:
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


