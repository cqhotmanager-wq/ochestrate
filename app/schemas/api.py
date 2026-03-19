"""API schemas for request/response payloads and orchestration reports."""

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
    tenant_id: str | None = Field(default=None, description="Injected from auth context.")
    user_id: str | None = Field(default=None, description="Injected from auth context.")
    session_id: str
    task_type: Literal["qa", "automation", "analysis"] = "qa"
    input: str = Field(min_length=1)
    context_refs: list[str] = Field(default_factory=list)
    policy: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tool_payload: ToolPayload | None = None
    tool_overrides: dict[str, Any] = Field(default_factory=dict)
    skill_context_mode: Literal["auto", "force_all"] = "auto"


class IntentSummary(BaseModel):
    goal: str
    constraints: list[str] = Field(default_factory=list)
    expected_output: list[str] = Field(default_factory=list)
    assumption_flags: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarifications: list[str] = Field(default_factory=list)


class TaskNodeSpec(BaseModel):
    node_id: str
    title: str
    description: str
    node_type: Literal["memory", "skill", "tool", "model", "verify", "report"]
    depends_on: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskDependency(BaseModel):
    from_node: str
    to_node: str


class TaskGraphSpec(BaseModel):
    nodes: list[TaskNodeSpec] = Field(default_factory=list)
    dependencies: list[TaskDependency] = Field(default_factory=list)
    parallel_groups: list[list[str]] = Field(default_factory=list)


class SkillMatch(BaseModel):
    name: str
    description: str
    score: float
    skill_path: str
    tools: list[str] = Field(default_factory=list)


class SkillSelection(BaseModel):
    task_node_id: str
    query: str
    skills: list[SkillMatch] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)


class ReflectionRecord(BaseModel):
    node_id: str
    decision: Literal["accept", "retry", "fail"]
    reason: str
    retry_count: int = 0


class ExecutionTraceRecord(BaseModel):
    node_id: str
    status: Literal["success", "failed", "skipped"]
    result: dict[str, Any] = Field(default_factory=dict)
    reflection: ReflectionRecord | None = None
    retry_count: int = 0
    error: str | None = None


class VerificationReport(BaseModel):
    all_tasks_completed: bool
    outputs_consistent: bool
    missing_nodes: list[str] = Field(default_factory=list)
    checks: list[str] = Field(default_factory=list)


class FinalResult(BaseModel):
    summary: str
    outputs: dict[str, Any] = Field(default_factory=dict)
    success: bool


class MemoryUpdate(BaseModel):
    memory_type: Literal["short", "long"]
    content: str


class Citation(BaseModel):
    source_id: str
    chunk_id: str
    snippet: str
    score: float


class Action(BaseModel):
    tool_name: str
    status: Literal["success", "skipped", "failed"]
    output: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    audit_ref: str | None = None
    policy_applied: dict[str, Any] = Field(default_factory=dict)


class UnifiedResponse(BaseModel):
    status: Literal["completed", "needs_clarification", "failed"]
    intent: IntentSummary
    task_graph: TaskGraphSpec | None = None
    skill_mapping: list[SkillSelection] = Field(default_factory=list)
    execution_trace: list[ExecutionTraceRecord] = Field(default_factory=list)
    verification: VerificationReport | None = None
    final_result: FinalResult | None = None
    trace_id: str
    clarifications: list[str] = Field(default_factory=list)


class SubmitTaskRequest(BaseModel):
    request: UnifiedRequest


class TaskStatusResponse(BaseModel):
    task_id: str
    status: Literal["queued", "running", "completed", "failed"]
    trace_id: str | None = None
    result: UnifiedResponse | None = None
    error: str | None = None


class FeedbackRequest(BaseModel):
    tenant_id: str | None = None
    user_id: str | None = None
    trace_id: str
    is_correct: bool
    score: float = Field(ge=0.0, le=1.0)
    user_edit: str | None = None
    tags: list[str] = Field(default_factory=list)


class IngestTextRequest(BaseModel):
    tenant_id: str | None = None
    source_id: str
    text: str = Field(min_length=1)


class CreateSkillRequest(BaseModel):
    skill_id: str
    version: str = "1.0.0"
    name: str
    prompt_template: str
    config: dict[str, Any] = Field(default_factory=dict)
