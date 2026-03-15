from __future__ import annotations

"""MySQL 适配器：封装连接与健康检查。"""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


class MySQLAdapter:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._engine: Engine | None = None

    def engine(self) -> Engine:
        # 延迟初始化连接引擎，避免进程启动时硬依赖数据库可达。
        if self._engine is None:
            self._engine = create_engine(self._dsn, pool_pre_ping=True)
        return self._engine

    def healthcheck(self) -> bool:
        try:
            with self.engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
