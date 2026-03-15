from __future__ import annotations

import re
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.tools.security import ToolSecurityConfig


class DatabaseTool:
    name = "database_tool"
    description = "Run SQL query/execute with confirm-write policy controls."
    required_roles = ["employee", "manager", "admin"]
    idempotent = False

    def __init__(self, dsn: str, security: ToolSecurityConfig) -> None:
        self._dsn = dsn
        self._security = security
        self._engine: Engine | None = None

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        operation = str(params.get("operation", "query")).lower()
        sql = str(params.get("sql") or "").strip()
        if not sql:
            raise ValueError("sql is required")

        if self._security.db_write_protection_enabled and self._is_write_sql(sql):
            confirm = bool(params.get(self._security.db_confirm_field, False))
            if not confirm:
                raise PermissionError(
                    f"write SQL requires explicit '{self._security.db_confirm_field}=true'"
                )

        engine = self._get_engine()
        if operation == "query":
            with engine.connect() as conn:
                rows = conn.execute(text(sql))
                result = [dict(row._mapping) for row in rows]
            return {"operation": "query", "rows": result, "count": len(result)}
        if operation == "execute":
            with engine.begin() as conn:
                result = conn.execute(text(sql))
                rowcount = int(result.rowcount if result.rowcount is not None else 0)
            return {"operation": "execute", "affected_rows": rowcount}
        raise ValueError(f"unsupported operation '{operation}'")

    def _get_engine(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(self._dsn, pool_pre_ping=True)
        return self._engine

    @staticmethod
    def _is_write_sql(sql: str) -> bool:
        match = re.match(r"^\s*([a-zA-Z]+)", sql)
        keyword = (match.group(1).upper() if match else "")
        return keyword in {
            "INSERT",
            "UPDATE",
            "DELETE",
            "REPLACE",
            "MERGE",
            "CREATE",
            "ALTER",
            "DROP",
            "TRUNCATE",
            "GRANT",
            "REVOKE",
        }

