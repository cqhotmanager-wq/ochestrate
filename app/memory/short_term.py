"""短期记忆存储：按会话保留固定窗口的最近对话。"""

from __future__ import annotations
from collections import defaultdict, deque


class ShortTermMemoryStore:
    def __init__(self, max_turns: int) -> None:
        self._max_turns = max_turns
        # 每个会话只保留最近 N 轮，防止上下文无限增长。
        self._sessions: dict[str, deque[str]] = defaultdict(lambda: deque(maxlen=max_turns))

    def add_turn(self, session_key: str, text: str) -> None:
        # 步骤：执行 `add_turn` 的核心处理逻辑。
        self._sessions[session_key].append(text)

    def window(self, session_key: str) -> list[str]:
        # 步骤：执行 `window` 的核心处理逻辑。
        return list(self._sessions.get(session_key, []))


