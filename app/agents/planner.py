"""规划智能体：根据任务类型和工具负载生成可执行步骤。"""

from __future__ import annotations

from typing import Any

from app.schemas.api import ToolPayload, UnifiedRequest


class PlannerAgent:
    def plan(self, request: UnifiedRequest) -> list[dict[str, Any]]:
        explicit_tool_step = self._step_from_payload(request.tool_payload)
        if explicit_tool_step is not None:
            return [{"kind": "validate_permissions"}, explicit_tool_step]

        if request.task_type != "automation":
            return [{"kind": "respond", "instruction": "answer user question"}]

        steps: list[dict[str, Any]] = [{"kind": "validate_permissions"}]
        raw = request.input.lower()
        if "email" in raw:
            steps.append(
                {
                    "kind": "tool",
                    "tool_name": "send_email",
                    "params": {"to": "unknown@company.com", "subject": "Automated message"},
                }
            )
        if "calendar" in raw or "meeting" in raw:
            steps.append(
                {
                    "kind": "tool",
                    "tool_name": "create_calendar_event",
                    "params": {"title": "Automated Event", "when": "tomorrow 10:00"},
                }
            )
        if "search" in raw or "web" in raw:
            steps.append(
                {
                    "kind": "tool",
                    "tool_name": "web_search_tool",
                    "params": {"query": request.input, "max_results": 5, "include_fetch": True},
                }
            )
        if len(steps) == 1:
            steps.append({"kind": "respond", "instruction": "no matching automation tool"})
        return steps

    @staticmethod
    def _step_from_payload(payload: ToolPayload | None) -> dict[str, Any] | None:
        if payload is None:
            return None
        resource_type = payload.resource_type.lower()
        operation = payload.operation.lower()
        params = {
            "operation": operation,
            "resource_type": resource_type,
            "resource_path": payload.resource_path,
            "url": payload.url,
            "sql": payload.sql,
            "options": payload.options,
            "content": payload.content,
        }
        if resource_type in {"file", "json", "doc", "docx", "excel", "xlsx", "pdf", "txt", "csv"}:
            return {"kind": "tool", "tool_name": "file_tool", "params": params}
        if resource_type in {"web", "url"}:
            tool_name = "web_search_tool" if operation == "search" else "web_fetch_tool"
            return {"kind": "tool", "tool_name": tool_name, "params": params}
        if resource_type in {"database", "sql"}:
            return {"kind": "tool", "tool_name": "database_tool", "params": params}
        return None



