from __future__ import annotations

import pytest

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None

from app.main import app


@pytest.mark.skipif(TestClient is None, reason="fastapi test client unavailable")
def test_agent_run_and_feedback_flow() -> None:
    client = TestClient(app)
    tenant_id = "acme"

    bootstrap_resp = client.post(
        "/v1/auth/bootstrap-admin",
        json={
            "tenant_id": tenant_id,
            "username": "admin",
            "password": "admin123",
            "role": "admin",
            "status": "active",
        },
    )
    assert bootstrap_resp.status_code == 200

    login_resp = client.post(
        "/v1/auth/login",
        json={
            "tenant_id": tenant_id,
            "username": "admin",
            "password": "admin123",
        },
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    ingest_resp = client.post(
        "/v1/knowledge/ingest-text",
        json={
            "tenant_id": "fake_tenant",
            "source_id": "doc-1",
            "text": "Milvus is used for vector retrieval in enterprise RAG systems.",
        },
        headers=headers,
    )
    assert ingest_resp.status_code == 200

    run_resp = client.post(
        "/v1/agent/run",
        json={
            "tenant_id": "fake_tenant",
            "user_id": "fake_user",
            "session_id": "s001",
            "task_type": "qa",
            "input": "What is Milvus used for?",
            "context_refs": [],
            "policy": {
                "sensitivity": "low",
                "max_cost_usd": 0.5,
                "auto_execute": True,
                "require_human_review": False,
                "timeout_seconds": 60,
            },
            "metadata": {"role": "employee"},
        },
        headers=headers,
    )
    assert run_resp.status_code == 200
    payload = run_resp.json()
    assert "answer" in payload
    assert "trace_id" in payload

    feedback_resp = client.post(
        "/v1/feedback",
        json={
            "tenant_id": "fake_tenant",
            "user_id": "fake_user",
            "trace_id": payload["trace_id"],
            "is_correct": True,
            "score": 0.95,
            "tags": ["qa"],
        },
        headers=headers,
    )
    assert feedback_resp.status_code == 200
    assert feedback_resp.json()["accepted"] is True
