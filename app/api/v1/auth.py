"""认证接口：提供登录、刷新、退出与管理员初始化能力。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.schemas import LoginRequest, LoginResponse, RefreshRequest, UserCreateRequest, UserResponse
from app.core.dependencies import ServiceContainer, get_container

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, container: ServiceContainer = Depends(get_container)) -> LoginResponse:
    """用户名密码登录，返回 Access/Refresh Token。"""
    try:
        return container.auth_service.login(
            tenant_id=payload.tenant_id,
            username=payload.username,
            password=payload.password,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/refresh", response_model=LoginResponse)
def refresh(payload: RefreshRequest, container: ServiceContainer = Depends(get_container)) -> LoginResponse:
    """使用 Refresh Token 换发新令牌对。"""
    try:
        return container.auth_service.refresh(payload.refresh_token)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/logout")
def logout(payload: RefreshRequest, container: ServiceContainer = Depends(get_container)) -> dict[str, bool]:
    """登出并吊销 Refresh Token。"""
    container.auth_service.logout(payload.refresh_token)
    return {"success": True}


@router.post("/bootstrap-admin", response_model=UserResponse)
def bootstrap_admin(
    payload: UserCreateRequest,
    container: ServiceContainer = Depends(get_container),
) -> UserResponse:
    """初始化管理员账号，仅在显式配置开启时允许。"""
    if not container.settings.auth_bootstrap_admin_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="bootstrap admin is disabled")
    if not payload.tenant_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="tenant_id is required")
    try:
        record = container.auth_service.bootstrap_admin_if_needed(
            tenant_id=payload.tenant_id,
            username=payload.username,
            password=payload.password,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return UserResponse(
        tenant_id=record.tenant_id,
        user_id=record.user_id,
        username=record.username,
        role=record.role,
        status=record.status,
        created_at=record.created_at,
    )


