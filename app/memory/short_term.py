from __future__ import annotations

"""短期记忆：按会话维护滚动窗口。"""

from collections import defaultdict, deque


class ShortTermMemoryStore:
    def __init__(self, max_turns: int) -> None:
        self._max_turns = max_turns
        # 每个会话只保留最近 N 轮，防止上下文无限增长。
        self._sessions: dict[str, deque[str]] = defaultdict(lambda: deque(maxlen=max_turns))

    def add_turn(self, session_key: str, text: str) -> None:
        self._sessions[session_key].append(text)

    def window(self, session_key: str) -> list[str]:
        return list(self._sessions.get(session_key, []))
