"""Planner agent that decomposes requests into a DAG task graph."""

from __future__ import annotations

from typing import Any

from app.schemas.api import IntentSummary, TaskDependency, TaskGraphSpec, TaskNodeSpec, ToolPayload, UnifiedRequest


class PlannerAgent:
    def plan(self, request: UnifiedRequest, intent: IntentSummary) -> TaskGraphSpec:
        execution_nodes = self._build_execution_nodes(request)

        memory_node = TaskNodeSpec(
            node_id="memory_retrieval",
            title="Retrieve Memory",
            description="Load short-term and long-term memory relevant to this request.",
            node_type="memory",
        )
        skill_node = TaskNodeSpec(
            node_id="skill_retrieval",
            title="Retrieve Skills",
            description="Retrieve top-k matching skills from skill registry.",
            node_type="skill",
        )

        for node in execution_nodes:
            node.depends_on = [memory_node.node_id, skill_node.node_id]

        verify_node = TaskNodeSpec(
            node_id="verify_output",
            title="Verify Output",
            description="Verify completion and consistency across node outputs.",
            node_type="verify",
            depends_on=[n.node_id for n in execution_nodes],
        )
        report_node = TaskNodeSpec(
            node_id="report_result",
            title="Report Result",
            description="Compose final response report.",
            node_type="report",
            depends_on=[verify_node.node_id],
            metadata={"goal": intent.goal},
        )

        nodes = [memory_node, skill_node, *execution_nodes, verify_node, report_node]
        dependencies = self._dependencies_from_nodes(nodes)
        parallel_groups = [
            [memory_node.node_id, skill_node.node_id],
            [n.node_id for n in execution_nodes],
            [verify_node.node_id],
            [report_node.node_id],
        ]
        return TaskGraphSpec(nodes=nodes, dependencies=dependencies, parallel_groups=parallel_groups)

    def replan(self, request: UnifiedRequest, intent: IntentSummary, failed_node_id: str) -> TaskGraphSpec:
        fallback_model = TaskNodeSpec(
            node_id="fallback_resolution",
            title="Fallback Resolution",
            description=f"Recover from failed node {failed_node_id} and produce best-effort output.",
            node_type="model",
            metadata={"mode": "replan", "failed_node": failed_node_id, "input": request.input},
        )
        verify_node = TaskNodeSpec(
            node_id="verify_output",
            title="Verify Output",
            description="Verify completion and consistency across node outputs.",
            node_type="verify",
            depends_on=[fallback_model.node_id],
        )
        report_node = TaskNodeSpec(
            node_id="report_result",
            title="Report Result",
            description="Compose final response report.",
            node_type="report",
            depends_on=[verify_node.node_id],
            metadata={"goal": intent.goal, "replanned": True},
        )
        nodes = [fallback_model, verify_node, report_node]
        return TaskGraphSpec(
            nodes=nodes,
            dependencies=self._dependencies_from_nodes(nodes),
            parallel_groups=[[fallback_model.node_id], [verify_node.node_id], [report_node.node_id]],
        )

    def _build_execution_nodes(self, request: UnifiedRequest) -> list[TaskNodeSpec]:
        explicit = self._node_from_payload(request.tool_payload)
        if explicit is not None:
            return [explicit]

        if request.task_type != "automation":
            return [
                TaskNodeSpec(
                    node_id="execute_model",
                    title="Execute Model",
                    description="Generate answer using model synthesis.",
                    node_type="model",
                    metadata={"input": request.input},
                )
            ]

        nodes: list[TaskNodeSpec] = []
        raw = request.input.lower()
        if "email" in raw:
            nodes.append(
                TaskNodeSpec(
                    node_id="tool_send_email",
                    title="Send Email",
                    description="Use send_email tool for automation request.",
                    node_type="tool",
                    metadata={
                        "tool_name": "send_email",
                        "params": {"to": "unknown@company.com", "subject": "Automated message"},
                    },
                )
            )
        if "calendar" in raw or "meeting" in raw:
            nodes.append(
                TaskNodeSpec(
                    node_id="tool_calendar",
                    title="Create Calendar Event",
                    description="Use create_calendar_event tool for automation request.",
                    node_type="tool",
                    metadata={
                        "tool_name": "create_calendar_event",
                        "params": {"title": "Automated Event", "when": "tomorrow 10:00"},
                    },
                )
            )
        if "search" in raw or "web" in raw:
            nodes.append(
                TaskNodeSpec(
                    node_id="tool_web_search",
                    title="Web Search",
                    description="Use web_search_tool to gather evidence.",
                    node_type="tool",
                    metadata={
                        "tool_name": "web_search_tool",
                        "params": {"query": request.input, "max_results": 5, "include_fetch": True},
                    },
                )
            )
        if not nodes:
            nodes.append(
                TaskNodeSpec(
                    node_id="execute_model",
                    title="Execute Model",
                    description="Generate answer using model synthesis.",
                    node_type="model",
                    metadata={"input": request.input},
                )
            )
        return nodes

    @staticmethod
    def _dependencies_from_nodes(nodes: list[TaskNodeSpec]) -> list[TaskDependency]:
        dependencies: list[TaskDependency] = []
        for node in nodes:
            for dep in node.depends_on:
                dependencies.append(TaskDependency(from_node=dep, to_node=node.node_id))
        return dependencies

    @staticmethod
    def _node_from_payload(payload: ToolPayload | None) -> TaskNodeSpec | None:
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
        tool_name: str | None = None
        if resource_type in {"file", "json", "doc", "docx", "excel", "xlsx", "pdf", "txt", "csv"}:
            tool_name = "file_tool"
        elif resource_type in {"web", "url"}:
            tool_name = "web_search_tool" if operation == "search" else "web_fetch_tool"
        elif resource_type in {"database", "sql"}:
            tool_name = "database_tool"

        if tool_name is None:
            return None
        return TaskNodeSpec(
            node_id=f"tool_{tool_name}",
            title=f"Invoke {tool_name}",
            description=f"Run {tool_name} from explicit payload.",
            node_type="tool",
            metadata={"tool_name": tool_name, "params": params},
        )
