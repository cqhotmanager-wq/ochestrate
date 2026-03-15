from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass
class UserRecord:
    tenant_id: str
    user_id: str
    username: str
    role: str
    status: str
    password_hash: str
    created_at: datetime


class AuthRepository:
    def __init__(self, mysql_engine: Engine | None) -> None:
        self._engine = mysql_engine
        self._users_mem: dict[tuple[str, str], UserRecord] = {}
        self._refresh_mem: dict[str, dict[str, Any]] = {}
        if self._engine is not None:
            self._init_tables()

    def _init_tables(self) -> None:
        ddl = [
            """
            CREATE TABLE IF NOT EXISTS user_credentials (
              id BIGINT PRIMARY KEY AUTO_INCREMENT,
              tenant_id VARCHAR(64) NOT NULL,
              user_id VARCHAR(64) NOT NULL,
              username VARCHAR(128) NOT NULL,
              password_hash TEXT NOT NULL,
              role VARCHAR(32) NOT NULL DEFAULT 'employee',
              status VARCHAR(32) NOT NULL DEFAULT 'active',
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              UNIQUE KEY uk_user_credentials (tenant_id, username),
              UNIQUE KEY uk_user_credentials_user_id (tenant_id, user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS refresh_tokens (
              id BIGINT PRIMARY KEY AUTO_INCREMENT,
              token_id VARCHAR(64) NOT NULL UNIQUE,
              tenant_id VARCHAR(64) NOT NULL,
              user_id VARCHAR(64) NOT NULL,
              session_id VARCHAR(64) NOT NULL,
              refresh_token_hash TEXT NOT NULL,
              expires_at DATETIME NOT NULL,
              revoked TINYINT(1) NOT NULL DEFAULT 0,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              KEY idx_refresh_lookup (tenant_id, user_id, session_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ]
        with self._engine.begin() as conn:
            for sql in ddl:
                conn.execute(text(sql))

    def is_empty(self) -> bool:
        if self._engine is None:
            return len(self._users_mem) == 0
        with self._engine.connect() as conn:
            count = int(conn.execute(text("SELECT COUNT(1) AS c FROM user_credentials")).scalar_one())
        return count == 0

    def create_user(
        self,
        tenant_id: str,
        username: str,
        password_hash: str,
        role: str,
        status: str = "active",
    ) -> UserRecord:
        user_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)
        record = UserRecord(
            tenant_id=tenant_id,
            user_id=user_id,
            username=username,
            role=role,
            status=status,
            password_hash=password_hash,
            created_at=created_at,
        )
        if self._engine is None:
            self._users_mem[(tenant_id, username)] = record
            return record
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO user_credentials(tenant_id, user_id, username, password_hash, role, status)
                    VALUES (:tenant_id, :user_id, :username, :password_hash, :role, :status)
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "username": username,
                    "password_hash": password_hash,
                    "role": role,
                    "status": status,
                },
            )
        return record

    def get_user_by_username(self, tenant_id: str, username: str) -> UserRecord | None:
        if self._engine is None:
            return self._users_mem.get((tenant_id, username))
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT tenant_id, user_id, username, role, status, password_hash, created_at
                    FROM user_credentials
                    WHERE tenant_id=:tenant_id AND username=:username
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant_id, "username": username},
            ).mappings().first()
        if row is None:
            return None
        created = row["created_at"]
        if isinstance(created, str):
            created = datetime.fromisoformat(created)
        return UserRecord(
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            username=row["username"],
            role=row["role"],
            status=row["status"],
            password_hash=row["password_hash"],
            created_at=created,
        )

    def get_user_by_id(self, tenant_id: str, user_id: str) -> UserRecord | None:
        if self._engine is None:
            for rec in self._users_mem.values():
                if rec.tenant_id == tenant_id and rec.user_id == user_id:
                    return rec
            return None
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT tenant_id, user_id, username, role, status, password_hash, created_at
                    FROM user_credentials
                    WHERE tenant_id=:tenant_id AND user_id=:user_id
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant_id, "user_id": user_id},
            ).mappings().first()
        if row is None:
            return None
        created = row["created_at"]
        if isinstance(created, str):
            created = datetime.fromisoformat(created)
        return UserRecord(
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            username=row["username"],
            role=row["role"],
            status=row["status"],
            password_hash=row["password_hash"],
            created_at=created,
        )

    def list_users(self, tenant_id: str) -> list[UserRecord]:
        if self._engine is None:
            return [r for r in self._users_mem.values() if r.tenant_id == tenant_id]
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT tenant_id, user_id, username, role, status, password_hash, created_at
                    FROM user_credentials
                    WHERE tenant_id=:tenant_id
                    ORDER BY created_at DESC
                    """
                ),
                {"tenant_id": tenant_id},
            ).mappings().all()
        result: list[UserRecord] = []
        for row in rows:
            created = row["created_at"]
            if isinstance(created, str):
                created = datetime.fromisoformat(created)
            result.append(
                UserRecord(
                    tenant_id=row["tenant_id"],
                    user_id=row["user_id"],
                    username=row["username"],
                    role=row["role"],
                    status=row["status"],
                    password_hash=row["password_hash"],
                    created_at=created,
                )
            )
        return result

    def update_user(
        self,
        tenant_id: str,
        user_id: str,
        role: str | None = None,
        status: str | None = None,
        password_hash: str | None = None,
    ) -> UserRecord | None:
        current = self.get_user_by_id(tenant_id, user_id)
        if current is None:
            return None
        next_role = role or current.role
        next_status = status or current.status
        next_hash = password_hash or current.password_hash
        if self._engine is None:
            for key, rec in list(self._users_mem.items()):
                if rec.tenant_id == tenant_id and rec.user_id == user_id:
                    self._users_mem[key] = UserRecord(
                        tenant_id=rec.tenant_id,
                        user_id=rec.user_id,
                        username=rec.username,
                        role=next_role,
                        status=next_status,
                        password_hash=next_hash,
                        created_at=rec.created_at,
                    )
                    return self._users_mem[key]
            return None
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE user_credentials
                    SET role=:role, status=:status, password_hash=:password_hash
                    WHERE tenant_id=:tenant_id AND user_id=:user_id
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "role": next_role,
                    "status": next_status,
                    "password_hash": next_hash,
                },
            )
        return self.get_user_by_id(tenant_id, user_id)

    def store_refresh_token(
        self,
        token_id: str,
        tenant_id: str,
        user_id: str,
        session_id: str,
        refresh_token_hash: str,
        expires_at: datetime,
    ) -> None:
        if self._engine is None:
            self._refresh_mem[token_id] = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "session_id": session_id,
                "refresh_token_hash": refresh_token_hash,
                "expires_at": expires_at,
                "revoked": False,
            }
            return
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO refresh_tokens(token_id, tenant_id, user_id, session_id, refresh_token_hash, expires_at, revoked)
                    VALUES (:token_id, :tenant_id, :user_id, :session_id, :refresh_token_hash, :expires_at, 0)
                    """
                ),
                {
                    "token_id": token_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "refresh_token_hash": refresh_token_hash,
                    "expires_at": expires_at.replace(tzinfo=None),
                },
            )

    def get_refresh_token(self, token_id: str) -> dict[str, Any] | None:
        if self._engine is None:
            return self._refresh_mem.get(token_id)
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT token_id, tenant_id, user_id, session_id, refresh_token_hash, expires_at, revoked
                    FROM refresh_tokens
                    WHERE token_id=:token_id
                    LIMIT 1
                    """
                ),
                {"token_id": token_id},
            ).mappings().first()
        if row is None:
            return None
        expires = row["expires_at"]
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return {
            "token_id": row["token_id"],
            "tenant_id": row["tenant_id"],
            "user_id": row["user_id"],
            "session_id": row["session_id"],
            "refresh_token_hash": row["refresh_token_hash"],
            "expires_at": expires,
            "revoked": bool(row["revoked"]),
        }

    def revoke_refresh_token(self, token_id: str) -> None:
        if self._engine is None:
            if token_id in self._refresh_mem:
                self._refresh_mem[token_id]["revoked"] = True
            return
        with self._engine.begin() as conn:
            conn.execute(
                text("UPDATE refresh_tokens SET revoked=1 WHERE token_id=:token_id"),
                {"token_id": token_id},
            )

    def cleanup_expired_refresh_tokens(self) -> None:
        now = datetime.now(timezone.utc)
        if self._engine is None:
            for token_id in list(self._refresh_mem.keys()):
                item = self._refresh_mem[token_id]
                if item["expires_at"] <= now:
                    del self._refresh_mem[token_id]
            return
        with self._engine.begin() as conn:
            conn.execute(
                text("DELETE FROM refresh_tokens WHERE expires_at <= :now"),
                {"now": now.replace(tzinfo=None)},
            )

    def create_bootstrap_admin_if_needed(self, tenant_id: str, username: str, password_hash: str) -> UserRecord:
        existing = self.get_user_by_username(tenant_id, username)
        if existing is not None:
            return existing
        if self.is_empty():
            return self.create_user(
                tenant_id=tenant_id,
                username=username,
                password_hash=password_hash,
                role="admin",
                status="active",
            )
        raise PermissionError("bootstrap admin disabled because users already exist")

    @staticmethod
    def refresh_token_expired(expires_at: datetime) -> bool:
        return expires_at <= datetime.now(timezone.utc)

    @staticmethod
    def refresh_token_expiry(days: int) -> datetime:
        return datetime.now(timezone.utc) + timedelta(days=days)

