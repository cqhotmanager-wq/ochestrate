from __future__ import annotations

from typing import Any, TypedDict

from app.schemas.api import Action, Citation


class OrchestrationState(TypedDict, total=False):
    trace_id: str
    prompt: str
    task_type: str
    sensitivity: str
    planner_steps: list[dict[str, Any]]
    citations: list[Citation]
    actions: list[Action]
    answer: str
    confidence: float
    fallback_triggered: bool

