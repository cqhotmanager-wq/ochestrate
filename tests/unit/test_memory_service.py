from __future__ import annotations

import time

from app.memory.service import MemoryService


def test_memory_service_short_and_long_term() -> None:
    memory = MemoryService(short_turns=2, long_ttl_days=1)
    memory.write_short("t1", "u1", "s1", "turn1")
    memory.write_short("t1", "u1", "s1", "turn2")
    memory.write_short("t1", "u1", "s1", "turn3")

    short_window = memory.read_short("t1", "u1", "s1")
    assert short_window == ["turn2", "turn3"]

    memory.write_long("t1", "u1", "enterprise glossary", tags=["glossary"])
    long_items = memory.read_long("t1", "u1", query="glossary")
    assert long_items


def test_memory_long_ttl_override() -> None:
    memory = MemoryService(short_turns=2, long_ttl_days=1)
    memory.write_long("t1", "u1", "temporary", ttl_days=0)
    time.sleep(0.01)
    items = memory.read_long("t1", "u1", query="temporary")
    assert not items

