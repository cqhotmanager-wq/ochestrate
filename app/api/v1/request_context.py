"""请求上下文绑定器：将鉴权上下文覆盖到业务请求字段。"""

from __future__ import annotations

from app.auth.schemas import AuthContext
from app.schemas.api import FeedbackRequest, IngestTextRequest, UnifiedRequest


def bind_unified_request_auth(request: UnifiedRequest, auth: AuthContext) -> UnifiedRequest:
    """把 Token 身份上下文绑定到统一请求对象。

    设计要点：
    - 请求体里的 tenant/user/session 字段不可信，统一由鉴权上下文覆盖。
    - 同时把角色与会话写入 metadata，供执行器做权限与审计增强。
    """
    # 步骤：执行 `bind_unified_request_auth` 的核心处理逻辑。
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
    """将反馈请求绑定为当前登录用户身份。"""
    # 步骤：执行 `bind_feedback_auth` 的核心处理逻辑。
    return request.model_copy(update={"tenant_id": auth.tenant_id, "user_id": auth.user_id})


def bind_ingest_auth(request: IngestTextRequest, auth: AuthContext) -> IngestTextRequest:
    """将知识摄取请求绑定为当前租户。"""
    # 步骤：执行 `bind_ingest_auth` 的核心处理逻辑。
    return request.model_copy(update={"tenant_id": auth.tenant_id})

