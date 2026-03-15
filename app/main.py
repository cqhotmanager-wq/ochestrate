from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_container
from app.core.logging import configure_logging

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = get_container()
    await container.task_manager.start()
    try:
        yield
    finally:
        await container.task_manager.stop()


app = FastAPI(title="Enterprise Agent Platform", version="0.2.0", lifespan=lifespan)
app.include_router(v1_router, prefix="/v1")


@app.get("/health")
def health() -> dict[str, object]:
    container = get_container()
    return {"status": "ok", "metrics": container.metrics.snapshot()}

