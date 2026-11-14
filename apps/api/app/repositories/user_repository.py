# 文件说明：数据访问仓储：user_repository。
from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.user import ProfileChanges, User, UserRole
from app.models.user import User as UserModel


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        model = await self._session.get(UserModel, user_id)
        return self._to_domain(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email.lower())
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str,
    ) -> User:
        model = UserModel(
            email=email.lower(),
            password_hash=password_hash,
            display_name=display_name,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def update_profile(self, user_id: UUID, changes: ProfileChanges) -> User | None:
        model = await self._session.get(UserModel, user_id)
        if model is None:
            return None

        if changes.display_name is not None:
            model.display_name = changes.display_name
        if changes.default_origin is not None:
            model.default_origin = changes.default_origin
        elif changes.clear_default_origin:
            model.default_origin = None
        if changes.currency is not None:
            model.currency = changes.currency
        if changes.language is not None:
            model.language = changes.language

        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def revoke_tokens(self, user_id: UUID) -> bool:
        result = await self._session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(token_version=UserModel.token_version + 1)
            .returning(UserModel.id)
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            password_hash=model.password_hash,
            display_name=model.display_name,
            default_origin=model.default_origin,
            currency=model.currency,
            language=model.language,
            role=cast(UserRole, model.role),
            token_version=model.token_version,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
