# 文件说明：数据访问仓储：memory_repository。
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_memory import UserMemory


class MemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, memory: UserMemory) -> UserMemory:
        self._session.add(memory)
        await self._session.flush()
        await self._session.refresh(memory)
        return memory

    async def list_for_owner(self, owner_id: UUID) -> list[UserMemory]:
        result = await self._session.execute(
            select(UserMemory)
            .where(UserMemory.owner_id == owner_id)
            .order_by(UserMemory.updated_at.desc(), UserMemory.created_at.desc())
        )
        return list(result.scalars())

    async def get_for_owner(
        self,
        *,
        owner_id: UUID,
        memory_id: UUID,
    ) -> UserMemory | None:
        result = await self._session.execute(
            select(UserMemory).where(
                UserMemory.id == memory_id,
                UserMemory.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete(self, memory: UserMemory) -> None:
        await self._session.delete(memory)

    async def delete_all(self, owner_id: UUID) -> None:
        await self._session.execute(
            delete(UserMemory).where(UserMemory.owner_id == owner_id)
        )
