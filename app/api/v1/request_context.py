from __future__ import annotations

from app.auth.schemas import AuthContext
from app.schemas.api import FeedbackRequest, IngestTextRequest, UnifiedRequest


def bind_unified_request_auth(request: UnifiedRequest, auth: AuthContext) -> UnifiedRequest:
    """将 token 上下文绑定到统一请求，忽略请求体内同名字段。"""
    metadata = dict(request.metadata)
    metadata["role"] = auth.role
    metadata["session_id"] = auth.session_id
    return request.model_copy(
        update={
            "tenant_id": auth.tenant_id,
            "user_id": auth.user_id,
            "session_id": auth.session_id,
            "metadata": metadata,
        }
    )


def bind_feedback_auth(request: FeedbackRequest, auth: AuthContext) -> FeedbackRequest:
    return request.model_copy(update={"tenant_id": auth.tenant_id, "user_id": auth.user_id})


def bind_ingest_auth(request: IngestTextRequest, auth: AuthContext) -> IngestTextRequest:
    return request.model_copy(update={"tenant_id": auth.tenant_id})
