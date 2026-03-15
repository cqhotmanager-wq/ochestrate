from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_container
from app.core.logging import configure_logging
from app.middleware.auth_context import AuthContextMiddleware

try:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
except Exception:  # pragma: no cover
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

    def generate_latest() -> bytes:
        container = get_container()
        lines = [f"{key} {value}" for key, value in container.metrics.snapshot().items()]
        return ("\n".join(lines) + "\n").encode("utf-8")

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
app.add_middleware(AuthContextMiddleware)
app.include_router(v1_router, prefix="/v1")


@app.get("/health")
def health() -> dict[str, object]:
    container = get_container()
    return {"status": "ok", "metrics": container.metrics.snapshot()}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
