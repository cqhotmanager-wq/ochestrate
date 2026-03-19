"""认证服务：处理密码校验、Token 签发刷新和用户管理。"""

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
    """认证领域服务。

    主要职责：
    - 管理用户密码散列与校验
    - 签发/刷新/吊销 Access 与 Refresh Token
    - 为中间件提供 Access Token 解码能力
    """

    def __init__(
        self,
        repository: AuthRepository,
        jwt_secret: str,
        jwt_algorithm: str,
        access_token_ttl_minutes: int,
        refresh_token_ttl_days: int,
    ) -> None:
        # 步骤：执行 `__init__` 的核心处理逻辑。
        self._repo = repository
        self._jwt_secret = jwt_secret
        self._jwt_algorithm = jwt_algorithm
        self._access_ttl = access_token_ttl_minutes
        self._refresh_ttl = refresh_token_ttl_days

    def hash_password(self, password: str) -> str:
        """使用 PBKDF2-SHA256 生成密码散列。"""
        # 步骤：执行 `hash_password` 的核心处理逻辑。
        salt = os.urandom(16)
        rounds = 120000
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
        return f"pbkdf2_sha256${rounds}${salt.hex()}${digest.hex()}"

    def verify_password(self, password: str, encoded: str) -> bool:
        """校验输入密码是否与存储散列匹配。"""
        # 步骤：执行 `verify_password` 的核心处理逻辑。
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
        """创建用户并写入散列后的密码。"""
        # 步骤：执行 `create_user` 的核心处理逻辑。
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
        """更新用户角色、状态或密码。"""
        # 步骤：执行 `update_user` 的核心处理逻辑。
        password_hash = self.hash_password(password) if password else None
        return self._repo.update_user(
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            status=status,
            password_hash=password_hash,
        )

    def list_users(self, tenant_id: str) -> list[UserRecord]:
        """按租户列出用户。"""
        # 步骤：执行 `list_users` 的核心处理逻辑。
        return self._repo.list_users(tenant_id)

    def bootstrap_admin_if_needed(self, tenant_id: str, username: str, password: str) -> UserRecord:
        """初始化第一个管理员用户。"""
        # 步骤：执行 `bootstrap_admin_if_needed` 的核心处理逻辑。
        return self._repo.create_bootstrap_admin_if_needed(
            tenant_id=tenant_id,
            username=username,
            password_hash=self.hash_password(password),
        )

    def login(self, tenant_id: str, username: str, password: str) -> LoginResponse:
        """登录流程：校验身份后签发 Access/Refresh Token。"""
        # 步骤：执行 `login` 的核心处理逻辑。
        user = self._repo.get_user_by_username(tenant_id=tenant_id, username=username)
        if user is None:
            raise PermissionError("invalid username or password")
        if user.status != "active":
            raise PermissionError("user is disabled")
        if not self.verify_password(password, user.password_hash):
            raise PermissionError("invalid username or password")
        return self._issue_tokens(user, session_id=str(uuid.uuid4()))

    def refresh(self, refresh_token: str) -> LoginResponse:
        """刷新流程：校验 Refresh Token 并轮换新令牌。"""
        payload = self._decode_token(refresh_token)
        if payload.get("typ") != "refresh":
            raise PermissionError("invalid refresh token type")

        # `jti` 是 refresh token 的唯一 ID，用于服务端状态校验与吊销。
        token_id = str(payload.get("jti") or "")
        if not token_id:
            raise PermissionError("refresh token missing token id")

        # 服务端多重校验：是否存在、是否吊销、是否过期、哈希是否匹配。
        token_row = self._repo.get_refresh_token(token_id)
        if token_row is None:
            raise PermissionError("refresh token not found")
        if token_row["revoked"]:
            raise PermissionError("refresh token revoked")
        if self._repo.refresh_token_expired(token_row["expires_at"]):
            raise PermissionError("refresh token expired")
        if not hmac.compare_digest(self._hash_token(refresh_token), token_row["refresh_token_hash"]):
            raise PermissionError("refresh token mismatch")

        # 令牌对应用户仍需处于可用状态。
        user = self._repo.get_user_by_id(tenant_id=token_row["tenant_id"], user_id=token_row["user_id"])
        if user is None or user.status != "active":
            raise PermissionError("user unavailable")

        # 轮换策略：旧 refresh token 立即吊销，减少重放风险。
        self._repo.revoke_refresh_token(token_id)
        return self._issue_tokens(user, session_id=token_row["session_id"])

    def logout(self, refresh_token: str) -> None:
        """退出登录：吊销指定 refresh token。"""
        # 步骤：执行 `logout` 的核心处理逻辑。
        payload = self._decode_token(refresh_token)
        token_id = str(payload.get("jti") or "")
        if token_id:
            self._repo.revoke_refresh_token(token_id)

    def decode_access_token(self, token: str) -> AuthContext:
        """解析并校验 Access Token，返回请求鉴权上下文。"""
        # 步骤：执行 `decode_access_token` 的核心处理逻辑。
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
        """签发 Access/Refresh Token 并持久化 Refresh Token 哈希。"""
        token_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        access_exp = now + timedelta(minutes=self._access_ttl)
        refresh_exp = now + timedelta(days=self._refresh_ttl)

        # Access Token 携带最小必要身份信息，用于请求级鉴权。
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

        # Refresh Token 仅用于换新 Access Token，并携带 `jti` 供服务端校验。
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

        # 服务端只存 refresh token 的哈希值，不直接落明文 token。
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
        """统一解码 JWT；异常统一转换为 PermissionError。"""
        # 步骤：执行 `_decode_token` 的核心处理逻辑。
        try:
            return jwt.decode(token, self._jwt_secret, algorithms=[self._jwt_algorithm])
        except jwt.PyJWTError as exc:
            raise PermissionError("invalid or expired token") from exc

    @staticmethod
    def _hash_token(token: str) -> str:
        """对 Refresh Token 做哈希用于服务端比对。"""
        # 步骤：执行 `_hash_token` 的核心处理逻辑。
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


