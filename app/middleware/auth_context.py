"""认证上下文中间件：解析 Bearer Token 并写入 request.state。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.dependencies import get_container


class AuthContextMiddleware(BaseHTTPMiddleware):
    """认证上下文中间件。

    行为：
    - 从 `Authorization: Bearer <token>` 解析 Access Token；
    - 成功时把 `AuthContext` 写入 `request.state.auth_context`；
    - 失败时不抛异常，交给路由层依赖决定是否强制鉴权。
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 默认无认证上下文，保证未携带 Token 的请求也可继续进入后续链路。
        request.state.auth_context = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            if token:
                container = get_container()
                try:
                    context = container.auth_service.decode_access_token(token)
                    request.state.auth_context = context
                except Exception:
                    # 鉴权失败仅清空上下文，不在中间件阶段提前返回错误。
                    request.state.auth_context = None
        return await call_next(request)



