from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.storage.models import RefreshTokenORM, UserCredentialORM


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
    def __init__(self, session_factory: sessionmaker[Session] | None) -> None:
        self._session_factory = session_factory
        self._users_mem: dict[tuple[str, str], UserRecord] = {}
        self._refresh_mem: dict[str, dict[str, Any]] = {}

    def is_empty(self) -> bool:
        if self._session_factory is None:
            return len(self._users_mem) == 0
        with self._session_factory() as session:
            count = session.query(UserCredentialORM.id).count()
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
        if self._session_factory is None:
            self._users_mem[(tenant_id, username)] = record
            return record

        with self._session_factory() as session:
            row = UserCredentialORM(
                tenant_id=tenant_id,
                user_id=user_id,
                username=username,
                password_hash=password_hash,
                role=role,
                status=status,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._as_user_record(row)

    def get_user_by_username(self, tenant_id: str, username: str) -> UserRecord | None:
        if self._session_factory is None:
            return self._users_mem.get((tenant_id, username))
        with self._session_factory() as session:
            row = session.scalar(
                select(UserCredentialORM).where(
                    UserCredentialORM.tenant_id == tenant_id,
                    UserCredentialORM.username == username,
                )
            )
            return None if row is None else self._as_user_record(row)

    def get_user_by_id(self, tenant_id: str, user_id: str) -> UserRecord | None:
        if self._session_factory is None:
            for rec in self._users_mem.values():
                if rec.tenant_id == tenant_id and rec.user_id == user_id:
                    return rec
            return None
        with self._session_factory() as session:
            row = session.scalar(
                select(UserCredentialORM).where(
                    UserCredentialORM.tenant_id == tenant_id,
                    UserCredentialORM.user_id == user_id,
                )
            )
            return None if row is None else self._as_user_record(row)

    def list_users(self, tenant_id: str) -> list[UserRecord]:
        if self._session_factory is None:
            return [r for r in self._users_mem.values() if r.tenant_id == tenant_id]

        with self._session_factory() as session:
            rows = (
                session.query(UserCredentialORM)
                .filter(UserCredentialORM.tenant_id == tenant_id)
                .order_by(UserCredentialORM.created_at.desc())
                .all()
            )
        return [self._as_user_record(row) for row in rows]

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

        if self._session_factory is None:
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

        with self._session_factory() as session:
            row = session.scalar(
                select(UserCredentialORM).where(
                    UserCredentialORM.tenant_id == tenant_id,
                    UserCredentialORM.user_id == user_id,
                )
            )
            if row is None:
                return None
            row.role = next_role
            row.status = next_status
            row.password_hash = next_hash
            session.commit()
            session.refresh(row)
            return self._as_user_record(row)

    def store_refresh_token(
        self,
        token_id: str,
        tenant_id: str,
        user_id: str,
        session_id: str,
        refresh_token_hash: str,
        expires_at: datetime,
    ) -> None:
        if self._session_factory is None:
            self._refresh_mem[token_id] = {
                "token_id": token_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "session_id": session_id,
                "refresh_token_hash": refresh_token_hash,
                "expires_at": expires_at,
                "revoked": False,
            }
            return

        with self._session_factory() as session:
            session.add(
                RefreshTokenORM(
                    token_id=token_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    session_id=session_id,
                    refresh_token_hash=refresh_token_hash,
                    expires_at=expires_at.replace(tzinfo=None),
                    revoked=False,
                )
            )
            session.commit()

    def get_refresh_token(self, token_id: str) -> dict[str, Any] | None:
        if self._session_factory is None:
            return self._refresh_mem.get(token_id)

        with self._session_factory() as session:
            row = session.scalar(select(RefreshTokenORM).where(RefreshTokenORM.token_id == token_id))
            if row is None:
                return None
            expires = row.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            return {
                "token_id": row.token_id,
                "tenant_id": row.tenant_id,
                "user_id": row.user_id,
                "session_id": row.session_id,
                "refresh_token_hash": row.refresh_token_hash,
                "expires_at": expires,
                "revoked": bool(row.revoked),
            }

    def revoke_refresh_token(self, token_id: str) -> None:
        if self._session_factory is None:
            if token_id in self._refresh_mem:
                self._refresh_mem[token_id]["revoked"] = True
            return

        with self._session_factory() as session:
            row = session.scalar(select(RefreshTokenORM).where(RefreshTokenORM.token_id == token_id))
            if row is not None:
                row.revoked = True
                session.commit()

    def cleanup_expired_refresh_tokens(self) -> None:
        now = datetime.now(timezone.utc)
        if self._session_factory is None:
            for token_id in list(self._refresh_mem.keys()):
                item = self._refresh_mem[token_id]
                if item["expires_at"] <= now:
                    del self._refresh_mem[token_id]
            return

        with self._session_factory() as session:
            (
                session.query(RefreshTokenORM)
                .filter(RefreshTokenORM.expires_at <= now.replace(tzinfo=None))
                .delete(synchronize_session=False)
            )
            session.commit()

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

    @staticmethod
    def _as_user_record(row: UserCredentialORM) -> UserRecord:
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return UserRecord(
            tenant_id=row.tenant_id,
            user_id=row.user_id,
            username=row.username,
            role=row.role,
            status=row.status,
            password_hash=row.password_hash,
            created_at=created,
        )
