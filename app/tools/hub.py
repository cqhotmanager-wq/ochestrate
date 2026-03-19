"""工具中心：执行注册、权限校验、幂等缓存与审计记录。"""

from __future__ import annotations

from typing import Any

from app.observability.audit import AuditLogger
from app.observability.metrics import MetricsRegistry
from app.tools.base import Tool, ToolCall, ToolInvokeResult


class ToolHub:
    """工具中心。

    统一负责：
    - 工具注册与能力发现
    - 角色权限校验
    - 幂等调用缓存
    - 审计与指标记录
    """

    def __init__(self, metrics: MetricsRegistry, audit: AuditLogger) -> None:
        # 步骤：执行 `__init__` 的核心处理逻辑。
        self._metrics = metrics
        self._audit = audit
        self._registry: dict[str, Tool] = {}
        self._idempotency_cache: dict[str, ToolInvokeResult] = {}

    def register(self, tool: Tool) -> None:
        """注册工具到中心。"""
        # 步骤：执行 `register` 的核心处理逻辑。
        self._registry[tool.name] = tool

    def list_capabilities(self) -> list[dict[str, Any]]:
        """输出工具能力清单，供提示词注入与调试使用。"""
        # 步骤：执行 `list_capabilities` 的核心处理逻辑。
        return [
            {
                "name": tool.name,
                "description": getattr(tool, "description", ""),
                "required_roles": tool.required_roles,
                "idempotent": tool.idempotent,
            }
            for tool in self._registry.values()
        ]

    def invoke(self, call: ToolCall) -> ToolInvokeResult:
        """执行工具调用并返回标准化结果。"""
        tool = self._registry.get(call.tool_name)
        if tool is None:
            raise ValueError(f"tool '{call.tool_name}' is not registered")

        # 先做角色鉴权，拒绝未授权工具访问。
        if call.user_role not in tool.required_roles:
            self._metrics.inc("tool.permission_denied")
            raise PermissionError(f"role '{call.user_role}' cannot invoke '{call.tool_name}'")

        # 幂等工具命中缓存时直接返回，避免重复执行外部副作用。
        if tool.idempotent and call.idempotency_key in self._idempotency_cache:
            self._metrics.inc("tool.idempotency_hit")
            cached = self._idempotency_cache[call.idempotency_key]
            return ToolInvokeResult(
                output=cached.output,
                audit_ref=cached.audit_ref,
                policy_applied={**cached.policy_applied, "idempotency_cache_hit": True},
                cache_hit=True,
            )

        # 在参数中注入租户/用户上下文，给工具策略校验与审计使用。
        params = dict(call.params)
        params.setdefault("_tenant_id", call.tenant_id)
        params.setdefault("_user_id", call.user_id)
        params.setdefault("_user_role", call.user_role)

        output = tool.run(params)
        self._metrics.inc("tool.success")
        audit_ref = self._audit.record(
            "tool_invoke",
            {
                "trace_id": call.trace_id,
                "tenant_id": call.tenant_id,
                "user_id": call.user_id,
                "tool_name": call.tool_name,
                "user_role": call.user_role,
                "idempotency_key": call.idempotency_key,
                "params": params,
            },
        )
        result = ToolInvokeResult(
            output=output,
            audit_ref=audit_ref,
            policy_applied={"role_checked": True, "idempotency_cache_hit": False},
        )
        if tool.idempotent:
            self._idempotency_cache[call.idempotency_key] = result
        return result


