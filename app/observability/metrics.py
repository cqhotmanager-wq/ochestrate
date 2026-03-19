"""指标注册器：维护运行时计数指标快照。"""

from __future__ import annotations

from collections import Counter


class MetricsRegistry:
    def __init__(self) -> None:
        # 步骤：执行 `__init__` 的核心处理逻辑。
        self._counter: Counter[str] = Counter()

    def inc(self, metric_name: str, value: int = 1) -> None:
        # 步骤：执行 `inc` 的核心处理逻辑。
        self._counter[metric_name] += value

    def snapshot(self) -> dict[str, int]:
        # 步骤：执行 `snapshot` 的核心处理逻辑。
        return dict(self._counter)



