"""鉴权依赖：从请求上下文读取或强制校验认证信息。"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.auth.schemas import AuthContext


def optional_auth_context(request: Request) -> AuthContext | None:
    """可选鉴权依赖：存在上下文则返回，不存在则返回 `None`。"""
    value = getattr(request.state, "auth_context", None)
    if value is None:
        return None
    return value


def require_auth_context(
    request: Request,
) -> AuthContext:
    """强制鉴权依赖：无认证上下文时返回 401。"""
    value = getattr(request.state, "auth_context", None)
    if value is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    return value


