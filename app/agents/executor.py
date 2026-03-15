from __future__ import annotations

import hashlib
from typing import Any

from app.schemas.api import Action, ExecutionPolicy
from app.tools.base import ToolCall
from app.tools.hub import ToolHub


class ExecutorAgent:
    def __init__(self, tool_hub: ToolHub) -> None:
        self._tool_hub = tool_hub

    def execute(
        self,
        steps: list[dict[str, Any]],
        user_role: str,
        trace_id: str,
        tenant_id: str,
        user_id: str,
        policy: ExecutionPolicy,
        tool_overrides: dict[str, Any] | None = None,
    ) -> list[Action]:
        actions: list[Action] = []
        if not policy.auto_execute:
            return [
                Action(
                    tool_name="policy_gate",
                    status="skipped",
                    output={"reason": "auto_execute_disabled"},
                    policy_applied={"auto_execute": False},
                )
            ]

        for step in steps:
            if step.get("kind") != "tool":
                continue
            tool_name = step["tool_name"]
            params = dict(step.get("params", {}))
            params.update((tool_overrides or {}).get(tool_name, {}))

            if tool_name == "database_tool":
                confirm_key = str(params.get("confirm_field", "confirm_write"))
                if confirm_key not in params:
                    params[confirm_key] = policy.confirm_write

            raw_key = f"{trace_id}:{tool_name}:{params}"
            idempotency_key = hashlib.sha1(raw_key.encode("utf-8")).hexdigest()
            try:
                result = self._tool_hub.invoke(
                    ToolCall(
                        tool_name=tool_name,
                        user_role=user_role,
                        idempotency_key=idempotency_key,
                        trace_id=trace_id,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        params=params,
                    )
                )
                actions.append(
                    Action(
                        tool_name=tool_name,
                        status="success",
                        output=result.output,
                        audit_ref=result.audit_ref,
                        policy_applied=result.policy_applied,
                    )
                )
            except PermissionError as exc:
                actions.append(
                    Action(
                        tool_name=tool_name,
                        status="failed",
                        output={"error": str(exc)},
                        policy_applied={"permission": "denied"},
                    )
                )
            except Exception as exc:
                actions.append(
                    Action(
                        tool_name=tool_name,
                        status="failed",
                        output={"error": str(exc)},
                    )
                )
        return actions

