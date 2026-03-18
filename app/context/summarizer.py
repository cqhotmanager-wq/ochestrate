"""摘要器：在超预算场景下压缩长文本上下文。"""

from __future__ import annotations

class Summarizer:
    def summarize(self, text: str, max_words: int = 120) -> str:
        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]) + " ..."


