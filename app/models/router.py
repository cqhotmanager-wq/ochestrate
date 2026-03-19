"""模型路由器：按任务类型与敏感度选择模型并支持回退。"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.models.providers import CloudModelClient, LocalModelClient, ModelClient, ModelConfig
from app.schemas.specs import ModelRouteRule


@dataclass
class RoutedModel:
    """路由结果：返回选中的 provider 与模型参数。"""

    provider: str
    config: ModelConfig


class ModelRouter:
    def __init__(
        self,
        default_provider: str,
        provider_configs: dict[str, dict[str, Any]],
        rules: list[ModelRouteRule],
        fallback_order: list[str],
    ) -> None:
        # provider_configs 与 rules 均来自外部 YAML，支持运行时调整。
        self.default_provider = default_provider
        self.provider_configs = provider_configs
        self.rules = rules
        self.fallback_order = fallback_order
        self.clients: dict[str, ModelClient] = {
            "local": LocalModelClient(),
            "cloud": CloudModelClient(),
        }

    @classmethod
    def from_file(cls, config_path: Path) -> "ModelRouter":
        """从 YAML 加载路由规则。"""
        # 步骤：执行 `from_file` 的核心处理逻辑。
        with config_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        rules = [ModelRouteRule(**r) for r in raw.get("rules", [])]
        return cls(
            default_provider=raw.get("default_provider", "cloud"),
            provider_configs=raw.get("providers", {}),
            rules=rules,
            fallback_order=raw.get("fallback_order", ["cloud"]),
        )

    def route(self, task_type: str, sensitivity: str) -> RoutedModel:
        # 优先匹配显式规则，未命中时回落到 default_provider。
        for rule in self.rules:
            if rule.task_type == task_type and rule.sensitivity == sensitivity:
                return self._make_routed(rule.provider)
        return self._make_routed(self.default_provider)

    def _make_routed(self, provider: str) -> RoutedModel:
        # 步骤：执行 `_make_routed` 的核心处理逻辑。
        cfg = self.provider_configs.get(provider, {})
        model_cfg = ModelConfig(
            name=cfg.get("model", "unknown-model"),
            timeout_seconds=cfg.get("timeout_seconds", 20),
            max_tokens=cfg.get("max_tokens", 1024),
            provider=provider,
        )
        return RoutedModel(provider=provider, config=model_cfg)

    def generate(self, prompt: str, task_type: str, sensitivity: str) -> tuple[str, bool]:
        """统一生成入口。

        返回 `(model_output, fallback_triggered)`。
        """
        routed = self.route(task_type=task_type, sensitivity=sensitivity)
        primary_client = self.clients.get(routed.provider)
        if primary_client is None:
            return prompt, True
        try:
            return primary_client.generate(prompt, routed.config), False
        except Exception:
            # 主路由失败后按 fallback_order 依次重试。
            for fallback in self.fallback_order:
                client = self.clients.get(fallback)
                if client is None:
                    continue
                fallback_cfg = self._make_routed(fallback).config
                try:
                    return client.generate(prompt, fallback_cfg), True
                except Exception:
                    continue
        return prompt, True


