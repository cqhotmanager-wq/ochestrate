from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine

from app.schemas.api import FeedbackRequest
from app.schemas.specs import KnowledgeChunk
from app.storage.models import Base
from app.storage.orm import create_session_factory
from app.storage.repositories.auth_repo import AuthRepository
from app.storage.repositories.feedback_repo import FeedbackRepository
from app.storage.repositories.knowledge_repo import KnowledgeRepository
from app.storage.repositories.task_repo import TaskRecord, TaskRepository


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return create_session_factory(engine)


def test_auth_repository_crud_with_orm() -> None:
    repo = AuthRepository(_session_factory())

    user = repo.create_user(
        tenant_id="t1",
        username="alice",
        password_hash="h1",
        role="admin",
        status="active",
    )
    assert user.username == "alice"

    fetched = repo.get_user_by_username("t1", "alice")
    assert fetched is not None
    assert fetched.user_id == user.user_id

    updated = repo.update_user("t1", user.user_id, role="manager", status="disabled", password_hash="h2")
    assert updated is not None
    assert updated.role == "manager"
    assert updated.status == "disabled"

    repo.store_refresh_token(
        token_id="tok-1",
        tenant_id="t1",
        user_id=user.user_id,
        session_id="s1",
        refresh_token_hash="hash-1",
        expires_at=datetime.now(timezone.utc),
    )
    token = repo.get_refresh_token("tok-1")
    assert token is not None
    assert token["token_id"] == "tok-1"
    repo.revoke_refresh_token("tok-1")
    revoked = repo.get_refresh_token("tok-1")
    assert revoked is not None and revoked["revoked"] is True


def test_task_repository_crud_with_orm() -> None:
    repo = TaskRepository(_session_factory())

    record = TaskRecord(
        task_id="task-1",
        tenant_id="t1",
        user_id="u1",
        session_id="s1",
        task_type="qa",
        status="queued",
        request_json={"input": "hello"},
    )
    repo.create(record)
    repo.update_status("task-1", status="completed", trace_id="tr-1", result_json={"answer": "ok"})

    row = repo.get("task-1")
    assert row is not None
    assert row.status == "completed"
    assert row.trace_id == "tr-1"

    recoverable = repo.list_recoverable_tasks()
    assert recoverable == []


def test_feedback_repository_stats_with_tenant_scope() -> None:
    repo = FeedbackRepository(_session_factory())
    repo.record(FeedbackRequest(tenant_id="t1", user_id="u1", trace_id="tr1", is_correct=True, score=1.0, tags=[]))
    repo.record(FeedbackRequest(tenant_id="t1", user_id="u2", trace_id="tr2", is_correct=False, score=0.2, tags=[]))
    repo.record(FeedbackRequest(tenant_id="t2", user_id="u3", trace_id="tr3", is_correct=True, score=0.9, tags=[]))

    stats_t1 = repo.stats("t1")
    assert stats_t1.total == 2
    assert stats_t1.correct_ratio == 0.5

    stats_all = repo.stats()
    assert stats_all.total == 3


def test_knowledge_repository_search_is_tenant_isolated() -> None:
    repo = KnowledgeRepository(_session_factory())
    repo.add_chunks(
        [
            KnowledgeChunk(tenant_id="t1", source_id="doc1", chunk_id="c1", content="milvus vector retrieval", metadata={}),
            KnowledgeChunk(tenant_id="t1", source_id="doc1", chunk_id="c2", content="mysql transaction", metadata={}),
            KnowledgeChunk(tenant_id="t2", source_id="doc2", chunk_id="c1", content="secret tenant data", metadata={}),
        ]
    )

    hits = repo.search("t1", "milvus retrieval", limit=5)
    assert hits
    assert all(item.tenant_id == "t1" for item in hits)
    assert hits[0].content.startswith("milvus")
