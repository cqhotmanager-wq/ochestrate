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

    ingest_resp = client.post(
        "/v1/knowledge/ingest-text",
        json={
            "tenant_id": "acme",
            "source_id": "doc-1",
            "text": "Milvus is used for vector retrieval in enterprise RAG systems.",
        },
    )
    assert ingest_resp.status_code == 200

    run_resp = client.post(
        "/v1/agent/run",
        json={
            "tenant_id": "acme",
            "user_id": "u001",
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
    )
    assert run_resp.status_code == 200
    payload = run_resp.json()
    assert "answer" in payload
    assert "trace_id" in payload

    feedback_resp = client.post(
        "/v1/feedback",
        json={
            "tenant_id": "acme",
            "user_id": "u001",
            "trace_id": payload["trace_id"],
            "is_correct": True,
            "score": 0.95,
            "tags": ["qa"],
        },
    )
    assert feedback_resp.status_code == 200
    assert feedback_resp.json()["accepted"] is True

