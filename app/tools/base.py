"""工具基础协议：定义工具载荷、调用上下文与返回结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolPayload:
    operation: str
    resource_type: str
    resource_path: str | None = None
    url: str | None = None
    sql: str | None = None
    options: dict[str, Any] = field(default_factory=dict)
    content: Any = None


@dataclass
class ToolCall:
    tool_name: str
    user_role: str
    idempotency_key: str
    trace_id: str
    tenant_id: str
    user_id: str
    params: dict[str, Any]


@dataclass
class ToolInvokeResult:
    output: dict[str, Any]
    audit_ref: str
    policy_applied: dict[str, Any]
    cache_hit: bool = False


class Tool(Protocol):
    name: str
    description: str
    required_roles: list[str]
    idempotent: bool

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        # 步骤：执行 `run` 的核心处理逻辑。
        ...



