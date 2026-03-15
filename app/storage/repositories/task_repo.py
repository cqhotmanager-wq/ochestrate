from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


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
    def __init__(self, engine: Engine | None) -> None:
        self._engine = engine
        self._mem: dict[str, TaskRecord] = {}
        if self._engine is not None:
            self._init_tables()

    def _init_tables(self) -> None:
        sql = [
            """
            CREATE TABLE IF NOT EXISTS task_queue_status (
              id BIGINT PRIMARY KEY AUTO_INCREMENT,
              task_id VARCHAR(64) NOT NULL UNIQUE,
              tenant_id VARCHAR(64) NOT NULL,
              user_id VARCHAR(64) NOT NULL,
              session_id VARCHAR(64) NOT NULL,
              task_type VARCHAR(32) NOT NULL,
              status VARCHAR(32) NOT NULL,
              trace_id VARCHAR(64) DEFAULT NULL,
              request_json JSON NOT NULL,
              result_json JSON NULL,
              error_message TEXT NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              KEY idx_task_queue_status (tenant_id, status),
              KEY idx_task_queue_trace (trace_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS audit_events (
              id BIGINT PRIMARY KEY AUTO_INCREMENT,
              event_id VARCHAR(64) NOT NULL UNIQUE,
              event_type VARCHAR(64) NOT NULL,
              trace_id VARCHAR(64) DEFAULT NULL,
              tenant_id VARCHAR(64) DEFAULT NULL,
              payload_json JSON NOT NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              KEY idx_audit_event_trace (trace_id),
              KEY idx_audit_event_type (event_type, created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ]
        with self._engine.begin() as conn:
            for stmt in sql:
                conn.execute(text(stmt))

    def create(self, task: TaskRecord) -> None:
        if self._engine is None:
            self._mem[task.task_id] = task
            return
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO task_queue_status(
                      task_id, tenant_id, user_id, session_id, task_type, status, trace_id, request_json, result_json, error_message
                    )
                    VALUES(
                      :task_id, :tenant_id, :user_id, :session_id, :task_type, :status, :trace_id, :request_json, :result_json, :error_message
                    )
                    """
                ),
                {
                    "task_id": task.task_id,
                    "tenant_id": task.tenant_id,
                    "user_id": task.user_id,
                    "session_id": task.session_id,
                    "task_type": task.task_type,
                    "status": task.status,
                    "trace_id": task.trace_id,
                    "request_json": task.request_json or {},
                    "result_json": task.result_json,
                    "error_message": task.error_message,
                },
            )

    def update_status(
        self,
        task_id: str,
        status: str,
        trace_id: str | None = None,
        result_json: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        if self._engine is None:
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
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE task_queue_status
                    SET status=:status, trace_id=:trace_id, result_json=:result_json, error_message=:error_message
                    WHERE task_id=:task_id
                    """
                ),
                {
                    "task_id": task_id,
                    "status": status,
                    "trace_id": trace_id,
                    "result_json": result_json,
                    "error_message": error_message,
                },
            )

    def get(self, task_id: str) -> TaskRecord | None:
        if self._engine is None:
            return self._mem.get(task_id)
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT task_id, tenant_id, user_id, session_id, task_type, status, trace_id, request_json, result_json, error_message
                    FROM task_queue_status
                    WHERE task_id=:task_id
                    LIMIT 1
                    """
                ),
                {"task_id": task_id},
            ).mappings().first()
        if row is None:
            return None
        return TaskRecord(
            task_id=row["task_id"],
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            task_type=row["task_type"],
            status=row["status"],
            trace_id=row["trace_id"],
            request_json=row["request_json"],
            result_json=row["result_json"],
            error_message=row["error_message"],
        )

    def append_audit_event(
        self,
        event_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        if self._engine is None:
            return
        trace_id = payload.get("trace_id")
        tenant_id = payload.get("tenant_id")
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO audit_events(event_id, event_type, trace_id, tenant_id, payload_json)
                    VALUES (:event_id, :event_type, :trace_id, :tenant_id, :payload_json)
                    """
                ),
                {
                    "event_id": event_id,
                    "event_type": event_type,
                    "trace_id": trace_id,
                    "tenant_id": tenant_id,
                    "payload_json": payload,
                },
            )

    def list_recoverable_tasks(self) -> list[TaskRecord]:
        """
        返回可恢复任务（queued/running），用于服务重启后的任务恢复。
        """
        if self._engine is None:
            return [item for item in self._mem.values() if item.status in {"queued", "running"}]
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT task_id, tenant_id, user_id, session_id, task_type, status, trace_id, request_json, result_json, error_message
                    FROM task_queue_status
                    WHERE status IN ('queued', 'running')
                    ORDER BY created_at ASC
                    """
                )
            ).mappings().all()
        return [
            TaskRecord(
                task_id=row["task_id"],
                tenant_id=row["tenant_id"],
                user_id=row["user_id"],
                session_id=row["session_id"],
                task_type=row["task_type"],
                status=row["status"],
                trace_id=row["trace_id"],
                request_json=row["request_json"],
                result_json=row["result_json"],
                error_message=row["error_message"],
            )
            for row in rows
        ]

    @staticmethod
    def now_utc() -> datetime:
        return datetime.now(timezone.utc)
