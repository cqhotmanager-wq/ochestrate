"""Orchestration service implementing PLAN->EXECUTE->REFLECT->VERIFY->REPORT graph workflow."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.agents.executor import ExecutorAgent
from app.agents.intent import IntentAnalyzer
from app.agents.planner import PlannerAgent
from app.agents.reviewer import ReflectionEngine
from app.context.manager import ContextManager
from app.memory.service import MemoryService
from app.models.router import ModelRouter
from app.observability.audit import AuditLogger
from app.observability.metrics import MetricsRegistry
from app.observability.tracing import TraceService
from app.orchestration.graph_executor import GraphExecutor, NodeRunResult
from app.prompts.assembly import PromptAssemblyInput, PromptAssemblyService
from app.schemas.api import (
    ExecutionTraceRecord,
    FinalResult,
    ReflectionRecord,
    SkillSelection,
    TaskGraphSpec,
    TaskNodeSpec,
    UnifiedRequest,
    UnifiedResponse,
)
from app.skills.context import SkillContextItem
from app.skills.registry import SkillRegistryService
from app.tools.hub import ToolHub

logger = logging.getLogger(__name__)


class OrchestratorService:
    """Main runtime orchestration service."""

    def __init__(
        self,
        planner: PlannerAgent,
        executor: ExecutorAgent,
        reviewer: ReflectionEngine,
        model_router: ModelRouter,
        memory: MemoryService,
        context_manager: ContextManager,
        prompt_assembly: PromptAssemblyService,
        skill_registry: SkillRegistryService,
        tool_hub: ToolHub,
        trace: TraceService,
        metrics: MetricsRegistry,
        audit: AuditLogger,
        intent_analyzer: IntentAnalyzer,
        max_skill_items: int = 100,
        top_k_skills: int = 5,
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._reviewer = reviewer
        self._model_router = model_router
        self._memory = memory
        self._context_manager = context_manager
        self._prompt_assembly = prompt_assembly
        self._skill_registry = skill_registry
        self._tool_hub = tool_hub
        self._trace = trace
        self._metrics = metrics
        self._audit = audit
        self._intent = intent_analyzer
        self._max_skill_items = max_skill_items
        self._top_k_skills = top_k_skills
        self._graph_executor = GraphExecutor(max_workers=4)

    def run(self, request: UnifiedRequest) -> UnifiedResponse:
        tenant_id = request.tenant_id or ""
        user_id = request.user_id or ""
        trace_id = self._trace.new_trace_id()
        self._metrics.inc("request.total")

        intent = self._intent.analyze(request)
        if intent.needs_clarification:
            self._metrics.inc("intent.needs_clarification")
            self._audit.record(
                "orchestration.needs_clarification",
                {"trace_id": trace_id, "tenant_id": tenant_id, "clarifications": intent.clarifications},
            )
            return UnifiedResponse(
                status="needs_clarification",
                intent=intent,
                trace_id=trace_id,
                clarifications=intent.clarifications,
            )

        known_tools = [item["name"] for item in self._tool_hub.list_capabilities()]
        self._skill_registry.sync(tenant_id=tenant_id, known_tools=known_tools)

        graph = self._planner.plan(request=request, intent=intent)
        self._metrics.inc("dag.depth_total", value=len(graph.parallel_groups))
        self._metrics.inc("dag.parallel_groups_total", value=sum(1 for group in graph.parallel_groups if len(group) > 1))
        traces, skill_mapping, outputs, failed_node = self._execute_graph(graph=graph, request=request, trace_id=trace_id)

        if failed_node is not None:
            self._metrics.inc("orchestration.replan")
            self._audit.record(
                "orchestration.replan",
                {
                    "trace_id": trace_id,
                    "tenant_id": tenant_id,
                    "failed_node": failed_node,
                },
            )
            replan_graph = self._planner.replan(request=request, intent=intent, failed_node_id=failed_node)
            re_traces, re_skills, re_outputs, failed_node = self._execute_graph(
                graph=replan_graph,
                request=request,
                trace_id=trace_id,
            )
            graph = replan_graph
            traces.extend(re_traces)
            skill_mapping.extend(re_skills)
            outputs.update(re_outputs)

        final_node_ids = {node.node_id for node in graph.nodes}
        final_trace = [item for item in traces if item.node_id in final_node_ids]
        verification = self._reviewer.verify(graph=graph, trace=final_trace)
        status = "completed" if failed_node is None and verification.all_tasks_completed else "failed"
        final_result = self._build_final_result(outputs=outputs, success=status == "completed")

        self._memory.write_short(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=request.session_id,
            content=f"Q:{request.input}\nstatus:{status}",
        )
        self._memory.record_outcome(
            tenant_id=tenant_id,
            user_id=user_id,
            task=request.input,
            solution=final_result.summary,
            success=status == "completed",
            lessons_learned="replan_triggered" if status == "failed" else "completed_without_global_failure",
            tags=[status, request.task_type],
        )

        self._audit.record(
            "orchestration.completed",
            {
                "trace_id": trace_id,
                "tenant_id": tenant_id,
                "status": status,
                "nodes": len(graph.nodes),
                "trace_items": len(traces),
            },
        )

        return UnifiedResponse(
            status=status,
            intent=intent,
            task_graph=graph,
            skill_mapping=skill_mapping,
            execution_trace=traces,
            verification=verification,
            final_result=final_result,
            trace_id=trace_id,
        )

    def _execute_graph(
        self,
        graph: TaskGraphSpec,
        request: UnifiedRequest,
        trace_id: str,
    ) -> tuple[list[ExecutionTraceRecord], list[SkillSelection], dict[str, dict[str, object]], str | None]:
        return self._graph_executor.run(
            graph=graph,
            execute_node=lambda node, deps: self._execute_node(
                node=node,
                dependency_outputs=deps,
                request=request,
                trace_id=trace_id,
            ),
        )

    def _execute_node(
        self,
        node: TaskNodeSpec,
        dependency_outputs: dict[str, dict[str, object]],
        request: UnifiedRequest,
        trace_id: str,
    ) -> NodeRunResult:
        tenant_id = request.tenant_id or ""
        user_id = request.user_id or ""
        user_role = str(request.metadata.get("role", "employee"))

        skill_selection = self._select_skills_for_node(tenant_id=tenant_id, node=node, request=request)
        retry_count = 0

        while True:
            result: dict[str, object] = {}
            error: str | None = None
            try:
                result = self._run_node_once(
                    node=node,
                    dependency_outputs=dependency_outputs,
                    request=request,
                    trace_id=trace_id,
                    user_role=user_role,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    skill_selection=skill_selection,
                )
            except Exception as exc:
                error = str(exc)

            reflection: ReflectionRecord = self._reviewer.reflect(
                node_id=node.node_id,
                result=result,
                error=error,
                retry_count=retry_count,
            )

            if reflection.decision == "accept":
                trace = ExecutionTraceRecord(
                    node_id=node.node_id,
                    status="success",
                    result=result,
                    reflection=reflection,
                    retry_count=retry_count,
                )
                return NodeRunResult(trace=trace, skill_selection=skill_selection, output=result)

            if reflection.decision == "retry":
                self._metrics.inc("reflection.retry")
                retry_count += 1
                continue

            trace = ExecutionTraceRecord(
                node_id=node.node_id,
                status="failed",
                result=result,
                reflection=reflection,
                retry_count=retry_count,
                error=error or reflection.reason,
            )
            return NodeRunResult(trace=trace, skill_selection=skill_selection, output=result)

    def _run_node_once(
        self,
        node: TaskNodeSpec,
        dependency_outputs: dict[str, dict[str, object]],
        request: UnifiedRequest,
        trace_id: str,
        user_role: str,
        tenant_id: str,
        user_id: str,
        skill_selection: SkillSelection,
    ) -> dict[str, object]:
        if node.node_type == "memory":
            return {
                "short_memory": self._memory.read_short(tenant_id, user_id, request.session_id),
                "long_memory": self._memory.read_long(tenant_id, user_id, request.input),
            }

        if node.node_type == "skill":
            return {
                "selected_skills": [item.name for item in skill_selection.skills],
                "selected_tools": skill_selection.tools,
            }

        if node.node_type == "tool":
            tool_name = str(node.metadata.get("tool_name"))
            params = dict(node.metadata.get("params", {}))
            actions = self._executor.execute(
                steps=[{"kind": "tool", "tool_name": tool_name, "params": params}],
                user_role=user_role,
                trace_id=trace_id,
                tenant_id=tenant_id,
                user_id=user_id,
                policy=request.policy,
                tool_overrides=request.tool_overrides,
            )
            payload = [item.model_dump() for item in actions]
            if any(item.get("status") == "failed" for item in payload):
                raise RuntimeError(f"tool node failed: {tool_name}")
            return {"actions": payload}

        if node.node_type == "model":
            prompt = self._compose_prompt(
                request=request,
                node=node,
                dependency_outputs=dependency_outputs,
                selected_skills=skill_selection,
            )
            answer, fallback = self._model_router.generate(
                prompt=prompt,
                task_type=request.task_type,
                sensitivity=request.policy.sensitivity,
            )
            return {"answer": answer, "fallback_triggered": fallback}

        if node.node_type == "verify":
            return {
                "dependencies_checked": list(dependency_outputs.keys()),
                "dependency_count": len(dependency_outputs),
            }

        if node.node_type == "report":
            summary = self._summarize_dependencies(dependency_outputs)
            return {
                "summary": summary,
                "dependency_outputs": dependency_outputs,
            }

        return {}

    def _select_skills_for_node(self, tenant_id: str, node: TaskNodeSpec, request: UnifiedRequest) -> SkillSelection:
        query = f"{node.title}\n{node.description}\n{request.input}".strip()
        skills = self._skill_registry.retrieve(
            tenant_id=tenant_id,
            query=query,
            top_k=self._top_k_skills,
        )
        tools = sorted({tool for item in skills for tool in item.tools})
        return SkillSelection(task_node_id=node.node_id, query=query, skills=skills, tools=tools)

    def _compose_prompt(
        self,
        request: UnifiedRequest,
        node: TaskNodeSpec,
        dependency_outputs: dict[str, dict[str, object]],
        selected_skills: SkillSelection,
    ) -> str:
        memory_output = dependency_outputs.get("memory_retrieval", {})
        short_memory = "\n".join(memory_output.get("short_memory", [])) if memory_output else ""
        long_memory = "\n".join(memory_output.get("long_memory", [])) if memory_output else ""

        skill_items = [
            SkillContextItem(name=s.name, description=s.description, skill_path=s.skill_path)
            for s in selected_skills.skills
        ]

        prompt = self._prompt_assembly.assemble(
            PromptAssemblyInput(
                system_policy="Follow PLAN/EXECUTE/REFLECT/VERIFY/REPORT discipline and do not hallucinate tools.",
                task=f"{request.input}\nNode: {node.title} ({node.description})",
                evidence=json.dumps(dependency_outputs, ensure_ascii=True),
                short_memory=short_memory,
                long_memory=long_memory,
                tools=self._tool_hub.list_capabilities(),
                skills=skill_items,
                max_skill_items=self._max_skill_items,
                skill_context_mode=request.skill_context_mode,
            )
        )

        return self._context_manager.build_context(
            system_policy="Use provided context and dependency outputs only.",
            task_context=prompt,
            retrieval_evidence=json.dumps(dependency_outputs, ensure_ascii=True),
            short_memory=short_memory,
            long_memory=long_memory,
        )

    @staticmethod
    def _summarize_dependencies(dependency_outputs: dict[str, dict[str, object]]) -> str:
        if not dependency_outputs:
            return "No dependency outputs were produced."

        for output in dependency_outputs.values():
            answer = output.get("answer")
            if isinstance(answer, str) and answer.strip():
                return answer.strip()

        return json.dumps(dependency_outputs, ensure_ascii=True)[:500]

    @staticmethod
    def _build_final_result(outputs: dict[str, dict[str, object]], success: bool) -> FinalResult:
        report = outputs.get("report_result")
        if report and isinstance(report.get("summary"), str):
            summary = str(report.get("summary"))
        else:
            summary = "Execution completed." if success else "Execution failed after reflection/replan."
        return FinalResult(summary=summary, outputs=outputs, success=success)
