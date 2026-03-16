from __future__ import annotations

import os

# Ensure tests do not depend on local MySQL/Redis availability.
os.environ.setdefault("AGENT_ENV", "test")
os.environ.setdefault("AGENT_TASK_QUEUE_BACKEND", "memory")
os.environ.setdefault("AGENT_MYSQL_DSN", "mysql+pymysql://invalid:invalid@127.0.0.1:65001/unavailable")

import pytest

from app.core.dependencies import get_container


@pytest.fixture(autouse=True)
def _reset_container_cache() -> None:
    get_container.cache_clear()
    yield
    get_container.cache_clear()
