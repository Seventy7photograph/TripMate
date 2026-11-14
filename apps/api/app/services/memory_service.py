# 文件说明：业务服务：memory_service。
from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.vector_store import MemoryVectorStore, embed_text
from app.models.user_memory import UserMemory
from app.repositories.memory_repository import MemoryRepository
from app.schemas.memory import (
    MemoryCategory,
    MemoryCreateRequest,
    MemoryUpdateRequest,
)


class MemoryConsentRequired(Exception):
    pass


class MemoryNotFound(Exception):
    pass


class MemoryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._memories = MemoryRepository(session)
        self._vectors = MemoryVectorStore(session)

    async def list_memories(self, *, owner_id: UUID) -> list[UserMemory]:
        return await self._memories.list_for_owner(owner_id)

    async def create(
        self,
        *,
        owner_id: UUID,
        payload: MemoryCreateRequest,
    ) -> UserMemory:
        if not payload.consent:
            raise MemoryConsentRequired
        memory = UserMemory(
            owner_id=owner_id,
            category=payload.category,
            content=payload.content,
            embedding=embed_text(payload.content),
            enabled=True,
            source="user",
            consent_at=datetime.now(UTC),
        )
        await self._memories.add(memory)
        await self._session.commit()
        return memory

    async def update(
        self,
        *,
        owner_id: UUID,
        memory_id: UUID,
        payload: MemoryUpdateRequest,
    ) -> UserMemory:
        memory = await self._get(owner_id=owner_id, memory_id=memory_id)
        if payload.category is not None:
            memory.category = payload.category
        if payload.content is not None:
            memory.content = payload.content
            memory.embedding = embed_text(payload.content)
        if payload.enabled is not None:
            memory.enabled = payload.enabled
        await self._session.flush()
        await self._session.refresh(memory)
        await self._session.commit()
        return memory

    async def delete(
        self,
        *,
        owner_id: UUID,
        memory_id: UUID,
    ) -> None:
        memory = await self._get(owner_id=owner_id, memory_id=memory_id)
        await self._memories.delete(memory)
        await self._session.commit()

    async def delete_all(self, *, owner_id: UUID) -> None:
        await self._memories.delete_all(owner_id)
        await self._session.commit()

    async def retrieval_constraints(
        self,
        *,
        owner_id: UUID,
        query: str,
        limit: int = 8,
    ) -> list[str]:
        memories = await self._vectors.search(
            owner_id=owner_id,
            query=query,
            limit=max(1, min(limit, 20)),
        )
        labels: dict[MemoryCategory, str] = {
            "preference": "偏好",
            "food": "饮食",
            "mobility": "行动",
            "lodging": "住宿",
            "budget": "预算",
            "avoid": "避开",
            "other": "其他",
        }
        return [
            f"用户已授权旅行记忆（"
            f"{labels[cast(MemoryCategory, memory.category)]}）：{memory.content}"
            for memory in memories
        ]

    async def authorized_items(
        self,
        *,
        owner_id: UUID,
        query: str,
        limit: int = 8,
    ) -> list[UserMemory]:
        """Return enabled, consented memories for the matching owner only."""
        return await self._vectors.search(
            owner_id=owner_id,
            query=query,
            limit=max(1, min(limit, 20)),
        )

    async def _get(self, *, owner_id: UUID, memory_id: UUID) -> UserMemory:
        memory = await self._memories.get_for_owner(
            owner_id=owner_id,
            memory_id=memory_id,
        )
        if memory is None:
            raise MemoryNotFound
        return memory
