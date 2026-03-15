from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from app.tools.database_tool import DatabaseTool
from app.tools.security import ToolSecurityConfig


def _security() -> ToolSecurityConfig:
    return ToolSecurityConfig(
        allowed_directories=[],
        allowed_domains=["*"],
        fetch_timeout_seconds=10,
        max_fetch_chars=1000,
        search_provider="duckduckgo",
        search_result_limit=5,
        db_write_protection_enabled=True,
        db_confirm_field="confirm_write",
        max_file_size_mb=10,
    )


def test_database_tool_query_and_write_guard(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    dsn = f"sqlite+pysqlite:///{db_path}"
    engine = create_engine(dsn)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY, tenant_id TEXT, name TEXT)"))
        conn.execute(text("INSERT INTO items (tenant_id, name) VALUES ('acme', 'a')"))

    tool = DatabaseTool(dsn=dsn, security=_security())
    query_result = tool.run(
        {"operation": "query", "sql": "SELECT id, name FROM items WHERE tenant_id='acme'", "_tenant_id": "acme"}
    )
    assert query_result["count"] == 1

    with pytest.raises(PermissionError):
        tool.run({"operation": "execute", "sql": "DELETE FROM items WHERE tenant_id='acme'", "_tenant_id": "acme"})

    exec_result = tool.run(
        {
            "operation": "execute",
            "sql": "DELETE FROM items WHERE tenant_id='acme'",
            "confirm_write": True,
            "_tenant_id": "acme",
        }
    )
    assert exec_result["affected_rows"] >= 1
