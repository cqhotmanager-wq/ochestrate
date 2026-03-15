from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.core.dependencies import ServiceContainer, get_container

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/tool-callback")
def tool_callback(
    payload: dict[str, Any],
    container: ServiceContainer = Depends(get_container),
) -> dict[str, str]:
    container.audit.record("webhook.tool_callback", payload)
    return {"status": "ok"}

