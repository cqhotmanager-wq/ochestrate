from __future__ import annotations

import pytest

from app.embeddings.service import EmbeddingConfig, EmbeddingService


class _ResponseStub:
    def __init__(self, payload: dict[str, object], raise_error: Exception | None = None) -> None:
        self._payload = payload
        self._raise_error = raise_error

    def raise_for_status(self) -> None:
        if self._raise_error is not None:
            raise self._raise_error

    def json(self) -> dict[str, object]:
        return self._payload


def test_embed_without_url_uses_deterministic_mock_vector() -> None:
    service = EmbeddingService(config=EmbeddingConfig(model="text-embedding-3-small"), env="test")

    vector_1 = service.embed_text("hello world")
    vector_2 = service.embed_text("hello world")

    assert len(vector_1) == 64
    assert vector_1 == vector_2


def test_http_embedding_uses_authorization_bearer_header(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _fake_post(url: str, *, timeout: int, headers: dict[str, str], json: dict[str, str]) -> _ResponseStub:
        captured["url"] = url
        captured["timeout"] = timeout
        captured["headers"] = headers
        captured["json"] = json
        return _ResponseStub({"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    monkeypatch.setattr("app.embeddings.service.requests.post", _fake_post)

    service = EmbeddingService(
        config=EmbeddingConfig(
            url="http://127.0.0.1:11434/v1/embeddings",
            model="test-model",
            timeout_seconds=30,
            api_key="test-key",
            api_key_header="Authorization",
            api_key_prefix="Bearer",
        ),
        env="test",
    )

    vector = service.embed_text("hello")

    assert vector == [0.1, 0.2, 0.3]
    assert captured["url"] == "http://127.0.0.1:11434/v1/embeddings"
    assert captured["timeout"] == 30
    assert captured["headers"] == {
        "Content-Type": "application/json",
        "Authorization": "Bearer test-key",
    }
    assert captured["json"] == {"input": "hello", "model": "test-model"}


def test_http_embedding_uses_custom_header_without_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _fake_post(url: str, *, timeout: int, headers: dict[str, str], json: dict[str, str]) -> _ResponseStub:
        captured["url"] = url
        captured["timeout"] = timeout
        captured["headers"] = headers
        captured["json"] = json
        return _ResponseStub({"data": [{"embedding": [1.0]}]})

    monkeypatch.setattr("app.embeddings.service.requests.post", _fake_post)

    service = EmbeddingService(
        config=EmbeddingConfig(
            url="http://127.0.0.1:8000/v1/embeddings",
            model="",
            timeout_seconds=10,
            api_key="raw-key",
            api_key_header="x-api-key",
            api_key_prefix="ignored-prefix",
        ),
        env="test",
    )

    vector = service.embed_text("ping")

    assert vector == [1.0]
    assert captured["headers"] == {
        "Content-Type": "application/json",
        "x-api-key": "raw-key",
    }
    assert captured["json"] == {"input": "ping"}


def test_http_exception_falls_back_to_mock_when_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _failing_post(
        url: str, *, timeout: int, headers: dict[str, str], json: dict[str, str]
    ) -> _ResponseStub:
        raise RuntimeError("network down")

    monkeypatch.setattr("app.embeddings.service.requests.post", _failing_post)

    service = EmbeddingService(
        config=EmbeddingConfig(
            url="http://127.0.0.1:9000/v1/embeddings",
            model="test-model",
            allow_mock_fallback=True,
        ),
        env="dev",
    )

    vector = service.embed_text("fallback me")

    assert len(vector) == 64
    assert vector == EmbeddingService(EmbeddingConfig(model="mock"), env="test").embed_text("fallback me")


def test_http_exception_raises_in_prod_when_mock_fallback_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _failing_post(
        url: str, *, timeout: int, headers: dict[str, str], json: dict[str, str]
    ) -> _ResponseStub:
        raise RuntimeError("network down")

    monkeypatch.setattr("app.embeddings.service.requests.post", _failing_post)

    service = EmbeddingService(
        config=EmbeddingConfig(
            url="http://127.0.0.1:9000/v1/embeddings",
            model="test-model",
            allow_mock_fallback=False,
        ),
        env="prod",
    )

    with pytest.raises(RuntimeError, match="embedding request failed"):
        service.embed_text("should fail")
