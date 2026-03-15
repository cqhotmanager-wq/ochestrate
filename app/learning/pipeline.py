from __future__ import annotations

"""企业学习管线：收集反馈并输出基础统计，供离线优化使用。"""

from collections import defaultdict

from app.schemas.api import FeedbackRequest


class EnterpriseLearningPipeline:
    def __init__(self) -> None:
        self._feedback_buffer: list[FeedbackRequest] = []
        self._stats: dict[str, float] = defaultdict(float)

    def submit_feedback(self, item: FeedbackRequest) -> None:
        """写入反馈缓冲区。"""
        self._feedback_buffer.append(item)

    def process_batch(self) -> dict[str, float]:
        """处理当前批次反馈并更新统计指标。"""
        if not self._feedback_buffer:
            return dict(self._stats)
        total = len(self._feedback_buffer)
        correct = sum(1 for x in self._feedback_buffer if x.is_correct)
        self._stats["feedback.total"] += total
        self._stats["feedback.correct_ratio"] = correct / total
        self._feedback_buffer.clear()
        return dict(self._stats)
