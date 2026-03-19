"""用户管理接口：管理员可创建、查询、更新租户用户。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.deps import require_auth_context
from app.auth.schemas import AuthContext, UserCreateRequest, UserResponse, UserUpdateRequest
from app.core.dependencies import ServiceContainer, get_container

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse)
def create_user(
    payload: UserCreateRequest,
    auth: AuthContext = Depends(require_auth_context),
    container: ServiceContainer = Depends(get_container),
) -> UserResponse:
    """管理员创建租户用户。"""
    # 步骤：执行 `create_user` 的核心处理逻辑。
    _ensure_admin(auth)
    record = container.auth_service.create_user(
        tenant_id=auth.tenant_id,
        username=payload.username,
        password=payload.password,
        role=payload.role,
        status=payload.status,
    )
    return UserResponse(
        tenant_id=record.tenant_id,
        user_id=record.user_id,
        username=record.username,
        role=record.role,
        status=record.status,
        created_at=record.created_at,
    )


@router.get("", response_model=list[UserResponse])
def list_users(
    auth: AuthContext = Depends(require_auth_context),
    container: ServiceContainer = Depends(get_container),
) -> list[UserResponse]:
    """管理员查询当前租户用户列表。"""
    # 步骤：执行 `list_users` 的核心处理逻辑。
    _ensure_admin(auth)
    users = container.auth_service.list_users(auth.tenant_id)
    return [
        UserResponse(
            tenant_id=u.tenant_id,
            user_id=u.user_id,
            username=u.username,
            role=u.role,
            status=u.status,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    auth: AuthContext = Depends(require_auth_context),
    container: ServiceContainer = Depends(get_container),
) -> UserResponse:
    """管理员更新用户角色、状态或密码。"""
    # 步骤：执行 `update_user` 的核心处理逻辑。
    _ensure_admin(auth)
    user = container.auth_service.update_user(
        tenant_id=auth.tenant_id,
        user_id=user_id,
        role=payload.role,
        status=payload.status,
        password=payload.password,
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return UserResponse(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        username=user.username,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
    )


def _ensure_admin(auth: AuthContext) -> None:
    """统一管理员权限校验。"""
    # 步骤：执行 `_ensure_admin` 的核心处理逻辑。
    if auth.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin role required")


