"""ORM 基础设施：定义 Base 与会话工厂。"""

from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    # 步骤：执行 `create_session_factory` 的核心处理逻辑。
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


