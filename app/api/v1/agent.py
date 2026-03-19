"""智能体同步接口：接收统一请求并触发编排执行。"""

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
    """同步执行智能体请求。

    说明：
    - 请求体中的租户与用户字段会被鉴权上下文覆盖。
    - 最终返回统一响应结构，包含答案、证据、动作与追踪信息。
    """
    # 步骤：执行 `run_agent` 的核心处理逻辑。
    scoped_request = bind_unified_request_auth(request, auth)
    return container.orchestrator.run(scoped_request)


