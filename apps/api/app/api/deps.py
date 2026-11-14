# 文件说明：后端应用模块：deps。
import hashlib
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.rate_limit import (
    RateLimiter,
    RateLimitExceeded,
    get_redis_client,
)
from app.db.session import get_db_session
from app.domain.user import User
from app.services.auth_service import AuthService, InvalidTokenError
from app.services.feature_service import FeatureDisabledError, FeatureFlagService

bearer_scheme = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_rate_limiter(settings: SettingsDep) -> RateLimiter:
    return RateLimiter(get_redis_client(settings.redis_url))


RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]


def get_auth_service(session: SessionDep, settings: SettingsDep) -> AuthService:
    return AuthService(session, settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_bearer_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


BearerTokenDep = Annotated[str, Depends(get_bearer_token)]


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    service: AuthServiceDep,
) -> User:
    # HTTPBearer 使用 auto_error=False，让缺失与格式错误的凭证
    # 统一返回受控的 401。
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return await service.get_user_from_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def get_current_admin(current_user: CurrentUserDep) -> User:
    # 角色校验必须在服务端完成，前端路由不能作为授权依据。
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "admin_required",
                "message": "Administrator role is required",
            },
        )
    return current_user


AdminUserDep = Annotated[User, Depends(get_current_admin)]


def require_feature(
    key: str,
) -> Callable[..., Awaitable[None]]:
    """创建功能开关依赖，开关关闭时按失败关闭原则拒绝请求。"""
    async def dependency(session: SessionDep) -> None:
        try:
            await FeatureFlagService(session).require_enabled(key)
        except FeatureDisabledError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "feature_disabled",
                    "feature": key,
                    "message": "该功能已由管理员暂时关闭",
                },
            ) from exc

    return dependency


def rate_limit(
    *,
    scope: str,
    limit_attribute: str,
) -> Callable[..., Awaitable[None]]:
    async def dependency(
        current_user: CurrentUserDep,
        settings: SettingsDep,
        limiter: RateLimiterDep,
    ) -> None:
        if not settings.rate_limit_enabled:
            return
        limit = int(getattr(settings, limit_attribute))
        # 用户 ID 哈希后再作为 Redis Key，避免直接暴露内部标识。
        digest = hashlib.sha256(str(current_user.id).encode()).hexdigest()[:24]
        try:
            await limiter.check(
                f"tripmate:rate:{scope}:{digest}",
                limit=limit,
                window_seconds=60,
            )
        except RateLimitExceeded as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "rate_limit_exceeded",
                    "scope": scope,
                    "message": "请求过于频繁，请稍后重试",
                },
                headers={"Retry-After": str(exc.retry_after_seconds)},
            ) from exc

    return dependency
