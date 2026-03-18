"""领域规格模型：定义技能、路由规则、记忆与知识结构。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentSpec(BaseModel):
    name: str
    role: str
    description: str
    enabled: bool = True


class ToolSpec(BaseModel):
    name: str
    description: str
    required_roles: list[str] = Field(default_factory=list)
    idempotent: bool = True


class SkillSpec(BaseModel):
    skill_id: str
    version: str
    name: str
    prompt_template: str
    config: dict[str, Any] = Field(default_factory=dict)


class ModelRouteRule(BaseModel):
    task_type: str
    sensitivity: str
    provider: str


class MemoryRecord(BaseModel):
    tenant_id: str
    user_id: str
    content: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    expires_at: datetime


class KnowledgeChunk(BaseModel):
    tenant_id: str
    source_id: str
    chunk_id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None



