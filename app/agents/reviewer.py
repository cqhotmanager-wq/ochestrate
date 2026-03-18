"""评审智能体：对答案进行复核并给出置信度评估。"""

from __future__ import annotations
from app.schemas.api import Citation


class ReviewerAgent:
    def review(
        self,
        answer: str,
        citations: list[Citation],
        actions_count: int,
    ) -> tuple[str, float]:
        # 一期置信度策略：基于引用数量、动作数量和答案长度打分。
        if not answer:
            return "I do not have enough evidence to answer reliably.", 0.1
        base_confidence = 0.5
        if citations:
            base_confidence += min(0.4, len(citations) * 0.08)
        if actions_count > 0:
            base_confidence += 0.05
        if len(answer) < 20:
            base_confidence -= 0.1
        return answer, max(0.0, min(base_confidence, 1.0))


