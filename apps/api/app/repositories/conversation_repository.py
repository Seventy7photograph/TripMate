# 文件说明：数据访问仓储：conversation_repository。
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation as ConversationModel


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, model: ConversationModel) -> None:
        self._session.add(model)

    async def list_for_owner(
        self,
        *,
        owner_id: UUID,
        limit: int = 50,
    ) -> list[ConversationModel]:
        result = await self._session.execute(
            select(ConversationModel)
            .where(ConversationModel.owner_id == owner_id)
            .order_by(ConversationModel.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def get_for_owner(
        self,
        *,
        owner_id: UUID,
        conversation_id: UUID,
        for_update: bool = False,
    ) -> ConversationModel | None:
        statement = select(ConversationModel).where(
            ConversationModel.id == conversation_id,
            ConversationModel.owner_id == owner_id,
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()
