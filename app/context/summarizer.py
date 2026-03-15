from __future__ import annotations

"""摘要器：在上下文超预算时进行简化压缩。"""


class Summarizer:
    def summarize(self, text: str, max_words: int = 120) -> str:
        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]) + " ..."
