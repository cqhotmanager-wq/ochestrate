"""Webhook 接口：记录外部工具回调并沉淀审计事件。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.auth.deps import require_auth_context
from app.auth.schemas import AuthContext
from app.core.dependencies import ServiceContainer, get_container

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/tool-callback")
def tool_callback(
    payload: dict[str, Any],
    auth: AuthContext = Depends(require_auth_context),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, str]:
    container.audit.record(
        "webhook.tool_callback",
        {
            "tenant_id": auth.tenant_id,
            "user_id": auth.user_id,
            "role": auth.role,
            "payload": payload,
        },
    )
    return {"status": "ok"}


