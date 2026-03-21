from __future__ import annotations

import pytest

from app.core.dependencies import ServiceContainer


def test_dev_allows_mysql_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_ENV", "dev")
    monkeypatch.setenv("AGENT_TASK_QUEUE_BACKEND", "memory")
    monkeypatch.setenv("AGENT_MYSQL_DSN", "mysql+pymysql://invalid:invalid@127.0.0.1:65003/missing")

    container = ServiceContainer()
    assert container.mysql_engine is None


def test_prod_requires_mysql(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_ENV", "prod")
    monkeypatch.setenv("AGENT_TASK_QUEUE_BACKEND", "memory")
    monkeypatch.setenv("AGENT_MYSQL_DSN", "mysql+pymysql://invalid:invalid@127.0.0.1:65004/missing")

    with pytest.raises(RuntimeError, match="mysql unavailable in prod"):
        ServiceContainer()


def test_prod_requires_redis_when_backend_is_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_ENV", "prod")
    monkeypatch.setenv("AGENT_MYSQL_DSN", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("AGENT_EMBEDDING_URL", "http://127.0.0.1:11434/v1/embeddings")
    monkeypatch.setenv("AGENT_TASK_QUEUE_BACKEND", "redis")
    monkeypatch.setenv("AGENT_REDIS_URL", "redis://127.0.0.1:65005/0")

    with pytest.raises(RuntimeError, match="redis backend required in prod"):
        ServiceContainer()
