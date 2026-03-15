from __future__ import annotations

from collections import Counter


class MetricsRegistry:
    def __init__(self) -> None:
        self._counter: Counter[str] = Counter()

    def inc(self, metric_name: str, value: int = 1) -> None:
        self._counter[metric_name] += value

    def snapshot(self) -> dict[str, int]:
        return dict(self._counter)

