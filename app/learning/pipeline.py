"""学习管线：记录反馈数据并计算正确率等指标。"""

from __future__ import annotations
from collections import defaultdict

from app.schemas.api import FeedbackRequest
from app.storage.repositories.feedback_repo import FeedbackRepository


class EnterpriseLearningPipeline:
    def __init__(self, repository: FeedbackRepository | None = None) -> None:
        # 步骤：执行 `__init__` 的核心处理逻辑。
        self._repository = repository
        self._feedback_buffer: list[FeedbackRequest] = []
        self._stats: dict[str, float] = defaultdict(float)
        self._last_tenant_id: str | None = None

    def submit_feedback(self, item: FeedbackRequest) -> None:
        # 步骤：执行 `submit_feedback` 的核心处理逻辑。
        self._last_tenant_id = item.tenant_id
        if self._repository is not None:
            self._repository.record(item)
            return
        self._feedback_buffer.append(item)

    def process_batch(self) -> dict[str, float]:
        # 步骤：执行 `process_batch` 的核心处理逻辑。
        if self._repository is not None:
            stats = self._repository.stats(self._last_tenant_id)
            return {
                "feedback.total": float(stats.total),
                "feedback.correct_ratio": float(stats.correct_ratio),
            }

        if not self._feedback_buffer:
            return dict(self._stats)

        total = len(self._feedback_buffer)
        correct = sum(1 for x in self._feedback_buffer if x.is_correct)
        self._stats["feedback.total"] += total
        self._stats["feedback.correct_ratio"] = correct / total
        self._feedback_buffer.clear()
        return dict(self._stats)



