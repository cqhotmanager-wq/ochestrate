"""上下文管理器：按固定层次拼装提示上下文并控制长度。"""

from __future__ import annotations
from app.context.summarizer import Summarizer
from app.context.token_budget import TokenBudgetManager


class ContextManager:
    def __init__(self, max_tokens: int) -> None:
        # 步骤：执行 `__init__` 的核心处理逻辑。
        self._budget = TokenBudgetManager(max_tokens=max_tokens)
        self._summarizer = Summarizer()

    def build_context(
        self,
        system_policy: str,
        task_context: str,
        retrieval_evidence: str,
        short_memory: str,
        long_memory: str,
    ) -> str:
        # 分层上下文拼接顺序固定，便于稳定提示词效果。
        sections = [
            f"[SYSTEM]\n{system_policy}",
            f"[TASK]\n{task_context}",
            f"[EVIDENCE]\n{retrieval_evidence}",
            f"[SHORT_MEMORY]\n{short_memory}",
            f"[LONG_MEMORY]\n{long_memory}",
        ]
        composed = "\n\n".join(sections)
        if self._budget.estimate_tokens(composed) <= self._budget.max_tokens:
            return composed
        return self._summarizer.summarize(composed, max_words=self._budget.max_tokens)


