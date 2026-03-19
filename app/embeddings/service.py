"""Embedding service with configurable cloud providers and mock fallback."""

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
    provider: str
    model: str
    timeout_seconds: int = 15
    openai_api_key: str | None = None
    azure_api_key: str | None = None
    azure_endpoint: str | None = None
    azure_api_version: str = "2024-02-01"
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


class OpenAIEmbeddingClient:
    def __init__(self, api_key: str, model: str, timeout_seconds: int) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    def embed(self, text: str) -> list[float]:
        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            timeout=self._timeout_seconds,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self._model, "input": text},
        )
        response.raise_for_status()
        payload = response.json()
        return payload["data"][0]["embedding"]


class AzureOpenAIEmbeddingClient:
    def __init__(
        self,
        api_key: str,
        endpoint: str,
        deployment: str,
        timeout_seconds: int,
        api_version: str,
    ) -> None:
        self._api_key = api_key
        self._endpoint = endpoint.rstrip("/")
        self._deployment = deployment
        self._timeout_seconds = timeout_seconds
        self._api_version = api_version

    def embed(self, text: str) -> list[float]:
        url = (
            f"{self._endpoint}/openai/deployments/{self._deployment}/embeddings"
            f"?api-version={self._api_version}"
        )
        response = requests.post(
            url,
            timeout=self._timeout_seconds,
            headers={
                "api-key": self._api_key,
                "Content-Type": "application/json",
            },
            json={"input": text},
        )
        response.raise_for_status()
        payload = response.json()
        return payload["data"][0]["embedding"]


class EmbeddingService:
    def __init__(self, config: EmbeddingConfig, env: str = "dev") -> None:
        self._config = config
        self._env = (env or "dev").strip().lower()
        self._mock = MockEmbeddingClient()
        self._client = self._build_client(config)

    def _build_client(self, config: EmbeddingConfig) -> EmbeddingClient:
        provider = (config.provider or "mock").strip().lower()
        if provider == "mock":
            return self._mock

        if provider == "openai":
            if not config.openai_api_key:
                return self._fallback_or_raise("openai api key missing")
            return OpenAIEmbeddingClient(
                api_key=config.openai_api_key,
                model=config.model,
                timeout_seconds=config.timeout_seconds,
            )

        if provider in {"azure", "azure_openai"}:
            if not config.azure_api_key or not config.azure_endpoint:
                return self._fallback_or_raise("azure embedding config missing")
            return AzureOpenAIEmbeddingClient(
                api_key=config.azure_api_key,
                endpoint=config.azure_endpoint,
                deployment=config.model,
                timeout_seconds=config.timeout_seconds,
                api_version=config.azure_api_version,
            )

        return self._fallback_or_raise(f"unknown embedding provider: {provider}")

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
