"""Lang 运行时兼容层：统一获取 LangChain/LangGraph 类型。"""

from __future__ import annotations

from typing import Any


def get_prompt_template_cls() -> Any:
    # 步骤：执行 `get_prompt_template_cls` 的核心处理逻辑。
    try:
        from langchain_core.prompts import PromptTemplate
    except Exception:
        return None
    return PromptTemplate


def get_langgraph_types() -> tuple[Any, Any]:
    # 步骤：执行 `get_langgraph_types` 的核心处理逻辑。
    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return "__end__", None
    return END, StateGraph



