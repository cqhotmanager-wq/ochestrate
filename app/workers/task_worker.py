from __future__ import annotations

"""异步任务管理：提供提交任务、后台执行和状态查询能力。"""

import asyncio
import logging
import uuid
from dataclasses import dataclass

from app.orchestration.service import OrchestratorService
from app.schemas.api import TaskStatusResponse, UnifiedRequest, UnifiedResponse

logger = logging.getLogger(__name__)


@dataclass
class TaskEnvelope:
    """任务实体：保存请求、状态、结果和错误信息。"""

    task_id: str
    request: UnifiedRequest
    status: str = "queued"
    result: UnifiedResponse | None = None
    error: str | None = None


class TaskManager:
    def __init__(self, orchestrator: OrchestratorService, poll_interval_seconds: float = 0.2) -> None:
        self._orchestrator = orchestrator
        self._poll_interval_seconds = poll_interval_seconds
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._tasks: dict[str, TaskEnvelope] = {}
        self._worker_task: asyncio.Task[None] | None = None
        self._stopped = False

    async def start(self) -> None:
        """启动后台 worker。"""
        if self._worker_task is None:
            self._stopped = False
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        """停止后台 worker，进行取消与回收。"""
        self._stopped = True
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

    async def submit(self, request: UnifiedRequest) -> str:
        """提交异步任务，返回 task_id。"""
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = TaskEnvelope(task_id=task_id, request=request)
        await self._queue.put(task_id)
        return task_id

    def get_status(self, task_id: str) -> TaskStatusResponse:
        """查询异步任务状态。"""
        task = self._tasks.get(task_id)
        if task is None:
            return TaskStatusResponse(task_id=task_id, status="failed", error="task_not_found")
        trace_id = task.result.trace_id if task.result else None
        return TaskStatusResponse(
            task_id=task.task_id,
            status=task.status,  # type: ignore[arg-type]
            trace_id=trace_id,
            result=task.result,
            error=task.error,
        )

    async def _worker_loop(self) -> None:
        # 常驻循环：从队列取任务并调用编排服务执行。
        while not self._stopped:
            try:
                task_id = await asyncio.wait_for(self._queue.get(), timeout=self._poll_interval_seconds)
            except asyncio.TimeoutError:
                continue

            envelope = self._tasks.get(task_id)
            if envelope is None:
                continue
            envelope.status = "running"
            try:
                envelope.result = self._orchestrator.run(envelope.request)
                envelope.status = "completed"
            except Exception as e:
                logger.exception("task execution failed")
                envelope.status = "failed"
                envelope.error = str(e)
            finally:
                self._queue.task_done()
