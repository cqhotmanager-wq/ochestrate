from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.storage.models import AuditEventORM, TaskQueueStatusORM


@dataclass
class TaskRecord:
    task_id: str
    tenant_id: str
    user_id: str
    session_id: str
    task_type: str
    status: str
    trace_id: str | None = None
    request_json: dict[str, Any] | None = None
    result_json: dict[str, Any] | None = None
    error_message: str | None = None


class TaskRepository:
    def __init__(self, session_factory: sessionmaker[Session] | None) -> None:
        self._session_factory = session_factory
        self._mem: dict[str, TaskRecord] = {}

    def create(self, task: TaskRecord) -> None:
        if self._session_factory is None:
            self._mem[task.task_id] = task
            return

        with self._session_factory() as session:
            session.add(
                TaskQueueStatusORM(
                    task_id=task.task_id,
                    tenant_id=task.tenant_id,
                    user_id=task.user_id,
                    session_id=task.session_id,
                    task_type=task.task_type,
                    status=task.status,
                    trace_id=task.trace_id,
                    request_json=task.request_json or {},
                    result_json=task.result_json,
                    error_message=task.error_message,
                )
            )
            session.commit()

    def update_status(
        self,
        task_id: str,
        status: str,
        trace_id: str | None = None,
        result_json: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        if self._session_factory is None:
            item = self._mem.get(task_id)
            if item is None:
                return
            item.status = status
            if trace_id is not None:
                item.trace_id = trace_id
            if result_json is not None:
                item.result_json = result_json
            if error_message is not None:
                item.error_message = error_message
            return

        with self._session_factory() as session:
            row = session.scalar(select(TaskQueueStatusORM).where(TaskQueueStatusORM.task_id == task_id))
            if row is None:
                return
            row.status = status
            row.trace_id = trace_id
            row.result_json = result_json
            row.error_message = error_message
            session.commit()

    def get(self, task_id: str) -> TaskRecord | None:
        if self._session_factory is None:
            return self._mem.get(task_id)

        with self._session_factory() as session:
            row = session.scalar(select(TaskQueueStatusORM).where(TaskQueueStatusORM.task_id == task_id))
            return None if row is None else self._to_record(row)

    def append_audit_event(
        self,
        event_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        if self._session_factory is None:
            return
        with self._session_factory() as session:
            session.add(
                AuditEventORM(
                    event_id=event_id,
                    event_type=event_type,
                    trace_id=payload.get("trace_id"),
                    tenant_id=payload.get("tenant_id"),
                    payload_json=payload,
                )
            )
            session.commit()

    def list_recoverable_tasks(self) -> list[TaskRecord]:
        if self._session_factory is None:
            return [item for item in self._mem.values() if item.status in {"queued", "running"}]

        with self._session_factory() as session:
            rows = (
                session.query(TaskQueueStatusORM)
                .filter(TaskQueueStatusORM.status.in_(["queued", "running"]))
                .order_by(TaskQueueStatusORM.created_at.asc())
                .all()
            )
            return [self._to_record(row) for row in rows]

    @staticmethod
    def now_utc() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _to_record(row: TaskQueueStatusORM) -> TaskRecord:
        return TaskRecord(
            task_id=row.task_id,
            tenant_id=row.tenant_id,
            user_id=row.user_id,
            session_id=row.session_id,
            task_type=row.task_type,
            status=row.status,
            trace_id=row.trace_id,
            request_json=row.request_json,
            result_json=row.result_json,
            error_message=row.error_message,
        )
