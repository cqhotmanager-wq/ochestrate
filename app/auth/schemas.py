from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AuthContext(BaseModel):
    tenant_id: str
    user_id: str
    role: str
    session_id: str
    token_exp: int


class LoginRequest(BaseModel):
    tenant_id: str
    username: str
    password: str = Field(min_length=6)


class RefreshRequest(BaseModel):
    refresh_token: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    tenant_id: str
    user_id: str
    role: str
    session_id: str


class UserCreateRequest(BaseModel):
    tenant_id: str | None = None
    username: str
    password: str = Field(min_length=6)
    role: str = "employee"
    status: str = "active"


class UserUpdateRequest(BaseModel):
    role: str | None = None
    status: str | None = None
    password: str | None = Field(default=None, min_length=6)


class UserResponse(BaseModel):
    tenant_id: str
    user_id: str
    username: str
    role: str
    status: str
    created_at: datetime
