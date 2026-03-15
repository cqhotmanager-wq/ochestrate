from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolPayload(BaseModel):
    operation: str
    resource_type: str
    resource_path: str | None = None
    url: str | None = None
    sql: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    content: Any = None


class ExecutionPolicy(BaseModel):
    sensitivity: Literal["low", "medium", "high"] = "medium"
    max_cost_usd: float = 0.5
    auto_execute: bool = True
    require_human_review: bool = False
    timeout_seconds: int = 60
    confirm_write: bool = False


class UnifiedRequest(BaseModel):
    tenant_id: str
    user_id: str
    session_id: str
    task_type: Literal["qa", "automation", "analysis"] = "qa"
    input: str = Field(min_length=1)
    context_refs: list[str] = Field(default_factory=list)
    policy: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tool_payload: ToolPayload | None = None
    tool_overrides: dict[str, Any] = Field(default_factory=dict)
    skill_context_mode: Literal["auto", "force_all"] = "auto"


class Citation(BaseModel):
    source_id: str
    chunk_id: str
    snippet: str
    score: float


class Action(BaseModel):
    tool_name: str
    status: Literal["success", "skipped", "failed"]
    output: dict[str, Any] = Field(default_factory=dict)
    audit_ref: str | None = None
    policy_applied: dict[str, Any] = Field(default_factory=dict)


class MemoryUpdate(BaseModel):
    memory_type: Literal["short", "long"]
    content: str


class UnifiedResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    confidence: float = 0.0
    trace_id: str
    memory_updates: list[MemoryUpdate] = Field(default_factory=list)
    fallback_triggered: bool = False


class SubmitTaskRequest(BaseModel):
    request: UnifiedRequest


class TaskStatusResponse(BaseModel):
    task_id: str
    status: Literal["queued", "running", "completed", "failed"]
    trace_id: str | None = None
    result: UnifiedResponse | None = None
    error: str | None = None


class FeedbackRequest(BaseModel):
    tenant_id: str
    user_id: str
    trace_id: str
    is_correct: bool
    score: float = Field(ge=0.0, le=1.0)
    user_edit: str | None = None
    tags: list[str] = Field(default_factory=list)


class IngestTextRequest(BaseModel):
    tenant_id: str
    source_id: str
    text: str = Field(min_length=1)


class CreateSkillRequest(BaseModel):
    skill_id: str
    version: str = "1.0.0"
    name: str
    prompt_template: str
    config: dict[str, Any] = Field(default_factory=dict)

