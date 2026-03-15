from __future__ import annotations

from typing import Any


def get_prompt_template_cls() -> Any:
    try:
        from langchain_core.prompts import PromptTemplate
    except Exception:
        return None
    return PromptTemplate


def get_langgraph_types() -> tuple[Any, Any]:
    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return "__end__", None
    return END, StateGraph

