from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.auth.schemas import AuthContext, LoginResponse
from app.storage.repositories.auth_repo import AuthRepository, UserRecord


class AuthService:
    def __init__(
        self,
        repository: AuthRepository,
        jwt_secret: str,
        jwt_algorithm: str,
        access_token_ttl_minutes: int,
        refresh_token_ttl_days: int,
    ) -> None:
        self._repo = repository
        self._jwt_secret = jwt_secret
        self._jwt_algorithm = jwt_algorithm
        self._access_ttl = access_token_ttl_minutes
        self._refresh_ttl = refresh_token_ttl_days

    def hash_password(self, password: str) -> str:
        salt = os.urandom(16)
        rounds = 120000
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
        return f"pbkdf2_sha256${rounds}${salt.hex()}${digest.hex()}"

    def verify_password(self, password: str, encoded: str) -> bool:
        try:
            method, rounds_str, salt_hex, digest_hex = encoded.split("$", 3)
            if method != "pbkdf2_sha256":
                return False
            rounds = int(rounds_str)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
        except Exception:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
        return hmac.compare_digest(actual, expected)

    def create_user(self, tenant_id: str, username: str, password: str, role: str, status: str) -> UserRecord:
        return self._repo.create_user(
            tenant_id=tenant_id,
            username=username,
            password_hash=self.hash_password(password),
            role=role,
            status=status,
        )

    def update_user(
        self,
        tenant_id: str,
        user_id: str,
        role: str | None = None,
        status: str | None = None,
        password: str | None = None,
    ) -> UserRecord | None:
        password_hash = self.hash_password(password) if password else None
        return self._repo.update_user(
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            status=status,
            password_hash=password_hash,
        )

    def list_users(self, tenant_id: str) -> list[UserRecord]:
        return self._repo.list_users(tenant_id)

    def bootstrap_admin_if_needed(self, tenant_id: str, username: str, password: str) -> UserRecord:
        return self._repo.create_bootstrap_admin_if_needed(
            tenant_id=tenant_id,
            username=username,
            password_hash=self.hash_password(password),
        )

    def login(self, tenant_id: str, username: str, password: str) -> LoginResponse:
        user = self._repo.get_user_by_username(tenant_id=tenant_id, username=username)
        if user is None:
            raise PermissionError("invalid username or password")
        if user.status != "active":
            raise PermissionError("user is disabled")
        if not self.verify_password(password, user.password_hash):
            raise PermissionError("invalid username or password")
        return self._issue_tokens(user, session_id=str(uuid.uuid4()))

    def refresh(self, refresh_token: str) -> LoginResponse:
        payload = self._decode_token(refresh_token)
        if payload.get("typ") != "refresh":
            raise PermissionError("invalid refresh token type")
        token_id = str(payload.get("jti") or "")
        if not token_id:
            raise PermissionError("refresh token missing token id")
        token_row = self._repo.get_refresh_token(token_id)
        if token_row is None:
            raise PermissionError("refresh token not found")
        if token_row["revoked"]:
            raise PermissionError("refresh token revoked")
        if self._repo.refresh_token_expired(token_row["expires_at"]):
            raise PermissionError("refresh token expired")
        if not hmac.compare_digest(self._hash_token(refresh_token), token_row["refresh_token_hash"]):
            raise PermissionError("refresh token mismatch")

        user = self._repo.get_user_by_id(tenant_id=token_row["tenant_id"], user_id=token_row["user_id"])
        if user is None or user.status != "active":
            raise PermissionError("user unavailable")

        self._repo.revoke_refresh_token(token_id)
        return self._issue_tokens(user, session_id=token_row["session_id"])

    def logout(self, refresh_token: str) -> None:
        payload = self._decode_token(refresh_token)
        token_id = str(payload.get("jti") or "")
        if token_id:
            self._repo.revoke_refresh_token(token_id)

    def decode_access_token(self, token: str) -> AuthContext:
        payload = self._decode_token(token)
        if payload.get("typ") != "access":
            raise PermissionError("invalid token type")
        required = ["tenant_id", "user_id", "role", "session_id", "exp"]
        for key in required:
            if key not in payload:
                raise PermissionError(f"token missing field '{key}'")
        return AuthContext(
            tenant_id=str(payload["tenant_id"]),
            user_id=str(payload["user_id"]),
            role=str(payload["role"]),
            session_id=str(payload["session_id"]),
            token_exp=int(payload["exp"]),
        )

    def _issue_tokens(self, user: UserRecord, session_id: str) -> LoginResponse:
        token_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        access_exp = now + timedelta(minutes=self._access_ttl)
        refresh_exp = now + timedelta(days=self._refresh_ttl)

        access_token = jwt.encode(
            {
                "typ": "access",
                "tenant_id": user.tenant_id,
                "user_id": user.user_id,
                "role": user.role,
                "session_id": session_id,
                "exp": int(access_exp.timestamp()),
            },
            self._jwt_secret,
            algorithm=self._jwt_algorithm,
        )
        refresh_token = jwt.encode(
            {
                "typ": "refresh",
                "jti": token_id,
                "tenant_id": user.tenant_id,
                "user_id": user.user_id,
                "session_id": session_id,
                "exp": int(refresh_exp.timestamp()),
            },
            self._jwt_secret,
            algorithm=self._jwt_algorithm,
        )

        self._repo.store_refresh_token(
            token_id=token_id,
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            session_id=session_id,
            refresh_token_hash=self._hash_token(refresh_token),
            expires_at=refresh_exp,
        )

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self._access_ttl * 60,
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            role=user.role,
            session_id=session_id,
        )

    def _decode_token(self, token: str) -> dict:
        try:
            return jwt.decode(token, self._jwt_secret, algorithms=[self._jwt_algorithm])
        except jwt.PyJWTError as exc:
            raise PermissionError("invalid or expired token") from exc

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
