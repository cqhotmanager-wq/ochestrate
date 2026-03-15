from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.auth.schemas import AuthContext


def optional_auth_context(request: Request) -> AuthContext | None:
    value = getattr(request.state, "auth_context", None)
    if value is None:
        return None
    return value


def require_auth_context(
    request: Request,
) -> AuthContext:
    value = getattr(request.state, "auth_context", None)
    if value is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    return value
