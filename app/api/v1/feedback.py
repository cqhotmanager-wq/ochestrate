from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import ServiceContainer, get_container
from app.schemas.api import FeedbackRequest

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("")
def submit_feedback(
    request: FeedbackRequest,
    container: ServiceContainer = Depends(get_container),
) -> dict[str, object]:
    container.learning_pipeline.submit_feedback(request)
    stats = container.learning_pipeline.process_batch()
    return {"accepted": True, "stats": stats}

