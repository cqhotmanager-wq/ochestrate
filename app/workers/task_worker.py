from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass

from app.orchestration.service import OrchestratorService
from app.schemas.api import TaskStatusResponse, UnifiedRequest, UnifiedResponse
from app.storage.repositories.task_repo import TaskRecord, TaskRepository
from app.workers.queue_backend import QueueBackend

logger = logging.getLogger(__name__)


@dataclass
class TaskEnvelope:
    task_id: str
    request: UnifiedRequest
    status: str = "queued"
    result: UnifiedResponse | None = None
    error: str | None = None


class TaskManager:
    def __init__(
        self,
        orchestrator: OrchestratorService,
        queue_backend: QueueBackend,
        task_repository: TaskRepository,
        poll_interval_seconds: float = 0.2,
    ) -> None:
        self._orchestrator = orchestrator
        self._queue_backend = queue_backend
        self._task_repo = task_repository
        self._poll_interval_seconds = poll_interval_seconds
        self._tasks: dict[str, TaskEnvelope] = {}
        self._worker_task: asyncio.Task[None] | None = None
        self._stopped = False

    async def start(self) -> None:
        if self._worker_task is None:
            self._stopped = False
            await self._recover_pending_tasks()
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        self._stopped = True
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

    async def submit(self, request: UnifiedRequest) -> str:
        task_id = str(uuid.uuid4())
        envelope = TaskEnvelope(task_id=task_id, request=request)
        self._tasks[task_id] = envelope

        self._task_repo.create(
            TaskRecord(
                task_id=task_id,
                tenant_id=request.tenant_id or "",
                user_id=request.user_id or "",
                session_id=request.session_id,
                task_type=request.task_type,
                status="queued",
                request_json=request.model_dump(),
            )
        )
        await self._queue_backend.enqueue(task_id)
        return task_id

    def get_status(self, task_id: str) -> TaskStatusResponse:
        task = self._tasks.get(task_id)
        if task is not None:
            trace_id = task.result.trace_id if task.result else None
            return TaskStatusResponse(
                task_id=task.task_id,
                status=task.status,  # type: ignore[arg-type]
                trace_id=trace_id,
                result=task.result,
                error=task.error,
            )

        persistent = self._task_repo.get(task_id)
        if persistent is None:
            return TaskStatusResponse(task_id=task_id, status="failed", error="task_not_found")

        result = UnifiedResponse(**persistent.result_json) if persistent.result_json else None
        return TaskStatusResponse(
            task_id=persistent.task_id,
            status=persistent.status,  # type: ignore[arg-type]
            trace_id=persistent.trace_id,
            result=result,
            error=persistent.error_message,
        )

    async def _worker_loop(self) -> None:
        while not self._stopped:
            try:
                task_id = await self._queue_backend.dequeue(self._poll_interval_seconds)
            except Exception:
                logger.exception("queue dequeue failed")
                await asyncio.sleep(self._poll_interval_seconds)
                continue
            if task_id is None:
                await asyncio.sleep(self._poll_interval_seconds)
                continue

            envelope = self._tasks.get(task_id)
            if envelope is None:
                continue
            envelope.status = "running"
            self._task_repo.update_status(task_id=task_id, status="running")
            try:
                envelope.result = self._orchestrator.run(envelope.request)
                envelope.status = "completed"
                self._task_repo.update_status(
                    task_id=task_id,
                    status="completed",
                    trace_id=envelope.result.trace_id,
                    result_json=envelope.result.model_dump(),
                )
            except Exception as exc:
                logger.exception("task execution failed")
                envelope.status = "failed"
                envelope.error = str(exc)
                self._task_repo.update_status(
                    task_id=task_id,
                    status="failed",
                    error_message=str(exc),
                )

    async def _recover_pending_tasks(self) -> None:
        for record in self._task_repo.list_recoverable_tasks():
            if not record.request_json:
                continue
            try:
                request = UnifiedRequest(**record.request_json)
            except Exception:
                logger.exception("skip invalid recoverable task: %s", record.task_id)
                continue
            self._tasks[record.task_id] = TaskEnvelope(
                task_id=record.task_id,
                request=request,
                status="queued",
            )
            try:
                await self._queue_backend.enqueue(record.task_id)
            except Exception:
                logger.exception("recover task enqueue failed: %s", record.task_id)
