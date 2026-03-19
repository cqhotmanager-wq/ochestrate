"""反馈仓储：记录反馈并提供租户维度统计。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.schemas.api import FeedbackRequest
from app.storage.models import FeedbackRecordORM


@dataclass
class FeedbackStats:
    total: int
    correct_ratio: float


class FeedbackRepository:
    def __init__(self, session_factory: sessionmaker[Session] | None) -> None:
        # 步骤：执行 `__init__` 的核心处理逻辑。
        self._session_factory = session_factory
        self._mem: list[FeedbackRequest] = []

    def record(self, item: FeedbackRequest) -> None:
        # 步骤：执行 `record` 的核心处理逻辑。
        if self._session_factory is None:
            self._mem.append(item)
            return

        with self._session_factory() as session:
            session.add(
                FeedbackRecordORM(
                    tenant_id=item.tenant_id or "",
                    user_id=item.user_id or "",
                    trace_id=item.trace_id,
                    is_correct=item.is_correct,
                    score=item.score,
                    user_edit=item.user_edit,
                    tags_json=item.tags,
                )
            )
            session.commit()

    def stats(self, tenant_id: str | None = None) -> FeedbackStats:
        # 步骤：执行 `stats` 的核心处理逻辑。
        if self._session_factory is None:
            records = [x for x in self._mem if tenant_id is None or x.tenant_id == tenant_id]
            total = len(records)
            if total == 0:
                return FeedbackStats(total=0, correct_ratio=0.0)
            correct = sum(1 for item in records if item.is_correct)
            return FeedbackStats(total=total, correct_ratio=correct / total)

        with self._session_factory() as session:
            stmt = select(func.count(FeedbackRecordORM.id), func.sum(FeedbackRecordORM.is_correct))
            if tenant_id is not None:
                stmt = stmt.where(FeedbackRecordORM.tenant_id == tenant_id)
            total, correct = session.execute(stmt).one()
            total_v = int(total or 0)
            if total_v == 0:
                return FeedbackStats(total=0, correct_ratio=0.0)
            correct_v = int(correct or 0)
            return FeedbackStats(total=total_v, correct_ratio=correct_v / total_v)


