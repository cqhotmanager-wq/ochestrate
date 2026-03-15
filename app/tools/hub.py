from __future__ import annotations

from typing import Any

from app.observability.audit import AuditLogger
from app.observability.metrics import MetricsRegistry
from app.tools.base import Tool, ToolCall, ToolInvokeResult


class ToolHub:
    def __init__(self, metrics: MetricsRegistry, audit: AuditLogger) -> None:
        self._metrics = metrics
        self._audit = audit
        self._registry: dict[str, Tool] = {}
        self._idempotency_cache: dict[str, ToolInvokeResult] = {}

    def register(self, tool: Tool) -> None:
        self._registry[tool.name] = tool

    def list_capabilities(self) -> list[dict[str, Any]]:
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
        tool = self._registry.get(call.tool_name)
        if tool is None:
            raise ValueError(f"tool '{call.tool_name}' is not registered")

        if call.user_role not in tool.required_roles:
            self._metrics.inc("tool.permission_denied")
            raise PermissionError(f"role '{call.user_role}' cannot invoke '{call.tool_name}'")

        if tool.idempotent and call.idempotency_key in self._idempotency_cache:
            self._metrics.inc("tool.idempotency_hit")
            cached = self._idempotency_cache[call.idempotency_key]
            return ToolInvokeResult(
                output=cached.output,
                audit_ref=cached.audit_ref,
                policy_applied={**cached.policy_applied, "idempotency_cache_hit": True},
                cache_hit=True,
            )

        output = tool.run(call.params)
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
                "params": call.params,
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

