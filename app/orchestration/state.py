"""Orchestration state declaration for graph execution."""

from __future__ import annotations

from typing import TypedDict

from app.schemas.api import ExecutionTraceRecord, IntentSummary, SkillSelection, TaskGraphSpec, VerificationReport


class OrchestrationState(TypedDict, total=False):
    trace_id: str
    intent: IntentSummary
    task_graph: TaskGraphSpec
    skill_mapping: list[SkillSelection]
    execution_trace: list[ExecutionTraceRecord]
    verification: VerificationReport
    status: str
