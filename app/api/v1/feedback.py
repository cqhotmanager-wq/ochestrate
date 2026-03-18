"""反馈接口：接收人工反馈并驱动学习管线统计更新。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.request_context import bind_feedback_auth
from app.auth.deps import require_auth_context
from app.auth.schemas import AuthContext
from app.core.dependencies import ServiceContainer, get_container
from app.schemas.api import FeedbackRequest

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("")
def submit_feedback(
    request: FeedbackRequest,
    auth: AuthContext = Depends(require_auth_context),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, object]:
    """提交反馈并返回即时统计。"""
    scoped_request = bind_feedback_auth(request, auth)
    container.learning_pipeline.submit_feedback(scoped_request)
    stats = container.learning_pipeline.process_batch()
    return {"accepted": True, "stats": stats}


