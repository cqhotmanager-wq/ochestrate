from __future__ import annotations

"""Token 预算器：估算并裁剪上下文长度。"""


class TokenBudgetManager:
    def __init__(self, max_tokens: int) -> None:
        self.max_tokens = max_tokens

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, len(text.split()))

    def truncate(self, text: str, remaining_tokens: int) -> str:
        if self.estimate_tokens(text) <= remaining_tokens:
            return text
        words = text.split()
        return " ".join(words[: max(remaining_tokens, 1)])
