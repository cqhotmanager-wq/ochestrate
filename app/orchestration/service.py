from __future__ import annotations

import logging
from typing import Any

from app.agents.executor import ExecutorAgent
from app.agents.planner import PlannerAgent
from app.agents.retriever import RetrieverAgent
from app.agents.reviewer import ReviewerAgent
from app.compat.lang_runtime import get_langgraph_types
from app.context.manager import ContextManager
from app.memory.service import MemoryService
from app.models.router import ModelRouter
from app.observability.audit import AuditLogger
from app.observability.metrics import MetricsRegistry
from app.observability.tracing import TraceService
from app.prompts.assembly import PromptAssemblyInput, PromptAssemblyService
from app.schemas.api import UnifiedRequest, UnifiedResponse
from app.skills.context import SkillContextService
from app.tools.hub import ToolHub

logger = logging.getLogger(__name__)


class OrchestratorService:
    def __init__(
        self,
        planner: PlannerAgent,
        retriever: RetrieverAgent,
        executor: ExecutorAgent,
        reviewer: ReviewerAgent,
        model_router: ModelRouter,
        memory: MemoryService,
        context_manager: ContextManager,
        prompt_assembly: PromptAssemblyService,
        skill_context: SkillContextService,
        tool_hub: ToolHub,
        trace: TraceService,
        metrics: MetricsRegistry,
        audit: AuditLogger,
        max_skill_items: int = 100,
    ) -> None:
        self._planner = planner
        self._retriever = retriever
        self._executor = executor
        self._reviewer = reviewer
        self._model_router = model_router
        self._memory = memory
        self._context_manager = context_manager
        self._prompt_assembly = prompt_assembly
        self._skill_context = skill_context
        self._tool_hub = tool_hub
        self._trace = trace
        self._metrics = metrics
        self._audit = audit
        self._max_skill_items = max_skill_items
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        end_symbol, state_graph_cls = get_langgraph_types()
        if state_graph_cls is None:
            return None

        def planner_node(state: dict[str, Any]) -> dict[str, Any]:
            request: UnifiedRequest = state["request"]
            state["planner_steps"] = self._planner.plan(request)
            return state

        def retriever_node(state: dict[str, Any]) -> dict[str, Any]:
            request: UnifiedRequest = state["request"]
            state["citations"] = self._retriever.retrieve(request)
            return state

        def executor_node(state: dict[str, Any]) -> dict[str, Any]:
            request: UnifiedRequest = state["request"]
            state["actions"] = self._executor.execute(
                steps=state.get("planner_steps", []),
                user_role=request.metadata.get("role", "employee"),
                trace_id=state["trace_id"],
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                policy=request.policy,
                tool_overrides=request.tool_overrides,
            )
            return state

        def reviewer_node(state: dict[str, Any]) -> dict[str, Any]:
            request: UnifiedRequest = state["request"]
            prompt = self._compose_prompt(request=request, citations=state.get("citations", []))
            answer, fallback = self._model_router.generate(
                prompt=prompt,
                task_type=request.task_type,
                sensitivity=request.policy.sensitivity,
            )
            reviewed_answer, confidence = self._reviewer.review(
                answer=answer,
                citations=state.get("citations", []),
                actions_count=len(state.get("actions", [])),
            )
            state["answer"] = reviewed_answer
            state["confidence"] = confidence
            state["fallback_triggered"] = fallback
            return state

        graph = state_graph_cls(dict)
        graph.add_node("planner", planner_node)
        graph.add_node("retriever", retriever_node)
        graph.add_node("executor", executor_node)
        graph.add_node("reviewer", reviewer_node)
        graph.set_entry_point("planner")
        graph.add_edge("planner", "retriever")
        graph.add_edge("retriever", "executor")
        graph.add_edge("executor", "reviewer")
        graph.add_edge("reviewer", end_symbol)
        return graph.compile()

    def run(self, request: UnifiedRequest) -> UnifiedResponse:
        trace_id = self._trace.new_trace_id()
        self._metrics.inc("request.total")
        state: dict[str, Any] = {
            "request": request,
            "trace_id": trace_id,
            "planner_steps": [],
            "citations": [],
            "actions": [],
            "answer": "",
            "confidence": 0.0,
            "fallback_triggered": False,
        }

        if self._graph is not None:
            state = self._graph.invoke(state)
        else:
            state = self._run_without_graph(state)

        citations = state.get("citations", [])
        actions = state.get("actions", [])
        reviewed_answer = state.get("answer", "")
        confidence = state.get("confidence", 0.0)
        fallback_triggered = state.get("fallback_triggered", False)

        short_update = self._memory.write_short(
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            session_id=request.session_id,
            content=f"Q:{request.input}\nA:{reviewed_answer[:300]}",
        )
        long_update = self._memory.write_long(
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            content=f"Preferred context from trace {trace_id}",
            tags=["auto-summary"],
        )

        self._audit.record(
            "orchestration.completed",
            {
                "trace_id": trace_id,
                "tenant_id": request.tenant_id,
                "task_type": request.task_type,
                "confidence": confidence,
                "citations": len(citations),
                "actions": len(actions),
                "skills_loaded": len(self._skill_context.load()),
            },
        )
        if confidence < 0.4:
            self._metrics.inc("response.low_confidence")

        return UnifiedResponse(
            answer=reviewed_answer,
            citations=citations,
            actions=actions,
            confidence=confidence,
            trace_id=trace_id,
            memory_updates=[short_update, long_update],
            fallback_triggered=fallback_triggered,
        )

    def _run_without_graph(self, state: dict[str, Any]) -> dict[str, Any]:
        request: UnifiedRequest = state["request"]
        planner_steps = self._planner.plan(request)
        citations = self._retriever.retrieve(request)
        actions = self._executor.execute(
            steps=planner_steps,
            user_role=request.metadata.get("role", "employee"),
            trace_id=state["trace_id"],
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            policy=request.policy,
            tool_overrides=request.tool_overrides,
        )
        prompt = self._compose_prompt(request=request, citations=citations)
        answer, fallback = self._model_router.generate(
            prompt=prompt,
            task_type=request.task_type,
            sensitivity=request.policy.sensitivity,
        )
        reviewed_answer, confidence = self._reviewer.review(
            answer=answer,
            citations=citations,
            actions_count=len(actions),
        )
        state["planner_steps"] = planner_steps
        state["citations"] = citations
        state["actions"] = actions
        state["answer"] = reviewed_answer
        state["confidence"] = confidence
        state["fallback_triggered"] = fallback
        return state

    def _compose_prompt(self, request: UnifiedRequest, citations: list[Any]) -> str:
        short_ctx = "\n".join(self._memory.read_short(request.tenant_id, request.user_id, request.session_id))
        long_ctx = "\n".join(self._memory.read_long(request.tenant_id, request.user_id, request.input))
        evidence = "\n".join(c.snippet for c in citations)

        prompt = self._prompt_assembly.assemble(
            PromptAssemblyInput(
                system_policy="Enterprise assistant with high-accuracy and citation requirements.",
                task=request.input,
                evidence=evidence,
                short_memory=short_ctx,
                long_memory=long_ctx,
                tools=self._tool_hub.list_capabilities(),
                skills=self._skill_context.load(),
                max_skill_items=self._max_skill_items,
                skill_context_mode=request.skill_context_mode,
            )
        )

        # Keep compatibility with existing context manager behavior.
        return self._context_manager.build_context(
            system_policy="Use the assembled prompt content as the task context.",
            task_context=prompt,
            retrieval_evidence=evidence,
            short_memory=short_ctx,
            long_memory=long_ctx,
        )

