"""模型提供方抽象：定义本地与云端模型调用协议。"""

from __future__ import annotations
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
        # 步骤：执行 `generate` 的核心处理逻辑。
        ...


class LocalModelClient:
    """本地模型客户端示例。"""

    def generate(self, prompt: str, config: ModelConfig) -> str:
        # 步骤：执行 `generate` 的核心处理逻辑。
        return f"[local:{config.name}] {prompt[: config.max_tokens]}"


class CloudModelClient:
    """云模型客户端示例。"""

    def generate(self, prompt: str, config: ModelConfig) -> str:
        # 步骤：执行 `generate` 的核心处理逻辑。
        return f"[cloud:{config.name}] {prompt[: config.max_tokens]}"


