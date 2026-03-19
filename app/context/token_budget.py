"""Token 预算管理：估算文本规模并在超限时截断。"""

from __future__ import annotations

class TokenBudgetManager:
    def __init__(self, max_tokens: int) -> None:
        # 步骤：执行 `__init__` 的核心处理逻辑。
        self.max_tokens = max_tokens

    def estimate_tokens(self, text: str) -> int:
        # 步骤：执行 `estimate_tokens` 的核心处理逻辑。
        if not text:
            return 0
        return max(1, len(text.split()))

    def truncate(self, text: str, remaining_tokens: int) -> str:
        # 步骤：执行 `truncate` 的核心处理逻辑。
        if self.estimate_tokens(text) <= remaining_tokens:
            return text
        words = text.split()
        return " ".join(words[: max(remaining_tokens, 1)])


