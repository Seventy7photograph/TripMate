# 文件说明：业务服务：auth_service。
import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.user import ProfileChanges, User
from app.repositories.user_repository import UserRepository


class AuthError(Exception):
    pass


class EmailAlreadyExistsError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


class InvalidTokenError(AuthError):
    pass


class UserNotFoundError(AuthError):
    pass


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._users = UserRepository(session)
        self._password_hash = PasswordHash.recommended()

    async def register(
        self,
        *,
        email: str,
        password: str,
        display_name: str,
    ) -> User:
        # 邮箱是唯一登录标识，先统一格式再检查重复。
        normalized_email = email.strip().lower()
        if await self._users.get_by_email(normalized_email):
            raise EmailAlreadyExistsError

        # Argon2 计算开销较高，放到线程中避免阻塞异步事件循环。
        password_hash = await asyncio.to_thread(self._password_hash.hash, password)
        try:
            user = await self._users.create(
                email=normalized_email,
                password_hash=password_hash,
                display_name=display_name,
            )
            await self._session.commit()
        except IntegrityError as exc:
            # 并发注册可能在预检查后被另一个请求抢先提交。
            await self._session.rollback()
            raise EmailAlreadyExistsError from exc
        return user

    async def authenticate(self, *, email: str, password: str) -> User:
        user = await self._users.get_by_email(email.strip().lower())
        if user is None:
            raise InvalidCredentialsError

        try:
            # 历史脏哈希只能判定认证失败，不能让 API 直接崩溃。
            verified = await asyncio.to_thread(
                self._password_hash.verify,
                password,
                user.password_hash,
            )
        except Exception:
            verified = False
        if not verified:
            raise InvalidCredentialsError
        return user

    def issue_token(self, user: User) -> tuple[str, int]:
        now = datetime.now(UTC)
        expires_in = self._settings.access_token_expire_minutes * 60
        # JWT 只信任用户标识、签发方和有效期等声明。
        token = jwt.encode(
            {
                "sub": str(user.id),
                "ver": user.token_version,
                "iss": self._settings.jwt_issuer,
                "iat": now,
                "exp": now + timedelta(seconds=expires_in),
            },
            self._settings.jwt_secret.get_secret_value(),
            algorithm=self._settings.jwt_algorithm,
        )
        return token, expires_in

    async def get_user_from_token(self, token: str) -> User:
        try:
            payload = self._decode_token(token)
            user_id = UUID(str(payload["sub"]))
        except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
            raise InvalidTokenError from exc

        user = await self._users.get_by_id(user_id)
        if user is None or user.token_version != int(str(payload["ver"])):
            raise InvalidTokenError
        return user

    async def revoke_token(self, token: str) -> None:
        try:
            payload = self._decode_token(token)
            user_id = UUID(str(payload["sub"]))
        except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
            raise InvalidTokenError from exc
        if not await self._users.revoke_tokens(user_id):
            raise InvalidTokenError
        await self._session.commit()

    async def update_profile(
        self,
        *,
        user_id: UUID,
        changes: ProfileChanges,
    ) -> User:
        user = await self._users.update_profile(user_id, changes)
        if user is None:
            raise UserNotFoundError
        await self._session.commit()
        return user

    async def get_visible_user(self, *, requested_id: UUID, current_user: User) -> User:
        if requested_id != current_user.id:
            raise UserNotFoundError
        return current_user

    def _decode_token(self, token: str) -> dict[str, object]:
        return jwt.decode(
            token,
            self._settings.jwt_secret.get_secret_value(),
            algorithms=[self._settings.jwt_algorithm],
            issuer=self._settings.jwt_issuer,
            options={"require": ["sub", "ver", "iat", "exp", "iss"]},
        )
