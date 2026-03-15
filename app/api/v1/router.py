from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.agent import router as agent_router
from app.api.v1.feedback import router as feedback_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.skills import router as skills_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.webhook import router as webhook_router

router = APIRouter()
router.include_router(agent_router)
router.include_router(tasks_router)
router.include_router(feedback_router)
router.include_router(knowledge_router)
router.include_router(skills_router)
router.include_router(webhook_router)

