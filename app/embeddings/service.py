"""Embedding service with configurable HTTP endpoint and mock fallback."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Protocol

import requests


class EmbeddingClient(Protocol):
    def embed(self, text: str) -> list[float]:
        ...


@dataclass
class EmbeddingConfig:
    url: str | None = None
    model: str = ""
    timeout_seconds: int = 15
    api_key: str | None = None
    api_key_header: str = "Authorization"
    api_key_prefix: str = "Bearer"
    allow_mock_fallback: bool = True


class MockEmbeddingClient:
    def __init__(self, dimension: int = 64) -> None:
        self._dimension = dimension

    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vector: list[float] = []
        for i in range(self._dimension):
            byte = digest[i % len(digest)]
            vector.append((byte / 127.5) - 1.0)
        return vector


class HttpEmbeddingClient:
    def __init__(
        self,
        url: str,
        model: str,
        timeout_seconds: int,
        api_key: str | None = None,
        api_key_header: str = "Authorization",
        api_key_prefix: str = "Bearer",
    ) -> None:
        self._url = url
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._api_key = api_key
        self._api_key_header = api_key_header
        self._api_key_prefix = api_key_prefix

    def embed(self, text: str) -> list[float]:
        payload: dict[str, str] = {"input": text}
        if self._model:
            payload["model"] = self._model

        headers = {"Content-Type": "application/json"}
        key_header = (self._api_key_header or "").strip()
        if self._api_key and key_header:
            if key_header.lower() == "authorization":
                prefix = (self._api_key_prefix or "").strip()
                headers[key_header] = f"{prefix} {self._api_key}" if prefix else self._api_key
            else:
                headers[key_header] = self._api_key

        response = requests.post(
            self._url,
            timeout=self._timeout_seconds,
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        response_payload = response.json()
        return response_payload["data"][0]["embedding"]


class EmbeddingService:
    def __init__(self, config: EmbeddingConfig, env: str = "dev") -> None:
        self._config = config
        self._env = (env or "dev").strip().lower()
        self._mock = MockEmbeddingClient()
        self._client = self._build_client(config)

    def _build_client(self, config: EmbeddingConfig) -> EmbeddingClient:
        url = (config.url or "").strip()
        if not url:
            return self._fallback_or_raise("embedding url missing")

        return HttpEmbeddingClient(
            url=url,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            api_key=config.api_key,
            api_key_header=config.api_key_header,
            api_key_prefix=config.api_key_prefix,
        )

    def _fallback_or_raise(self, reason: str) -> EmbeddingClient:
        if self._env in {"prod", "production"} and not self._config.allow_mock_fallback:
            raise RuntimeError(f"embedding provider unavailable in prod: {reason}")
        return self._mock

    def embed_text(self, text: str) -> list[float]:
        try:
            return self._client.embed(text)
        except Exception as exc:
            if self._env in {"prod", "production"} and not self._config.allow_mock_fallback:
                raise RuntimeError(f"embedding request failed: {exc}") from exc
            return self._mock.embed(text)

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        size = min(len(a), len(b))
        if size == 0:
            return 0.0
        dot = sum(a[i] * b[i] for i in range(size))
        na = math.sqrt(sum(a[i] * a[i] for i in range(size)))
        nb = math.sqrt(sum(b[i] * b[i] for i in range(size)))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)
