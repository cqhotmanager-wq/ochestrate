from __future__ import annotations

"""模型 provider 抽象与示例实现。"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ModelConfig:
    """单次模型调用配置。"""

    name: str
    timeout_seconds: int
    max_tokens: int
    provider: str


class ModelClient(Protocol):
    def generate(self, prompt: str, config: ModelConfig) -> str:
        ...


class LocalModelClient:
    """本地模型客户端示例。"""

    def generate(self, prompt: str, config: ModelConfig) -> str:
        return f"[local:{config.name}] {prompt[: config.max_tokens]}"


class CloudModelClient:
    """云模型客户端示例。"""

    def generate(self, prompt: str, config: ModelConfig) -> str:
        return f"[cloud:{config.name}] {prompt[: config.max_tokens]}"
