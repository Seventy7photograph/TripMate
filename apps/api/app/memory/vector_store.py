# 文件说明：旅行记忆检索：vector_store。
import hashlib
import math
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_memory import UserMemory

EMBEDDING_DIMENSIONS = 64


def embed_text(text: str) -> list[float]:
    """Create a deterministic local embedding without sending memory off-site."""
    normalized = text.casefold().strip()
    words = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", normalized)
    chinese = re.sub(r"[^\u4e00-\u9fff]", "", normalized)
    tokens = [*words, *(chinese[index : index + 2] for index in range(len(chinese) - 1))]
    if not tokens:
        tokens = [normalized]

    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in tokens:
        if not token:
            continue
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "little") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


class MemoryVectorStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(
        self,
        *,
        owner_id: UUID,
        query: str,
        limit: int = 8,
    ) -> list[UserMemory]:
        statement = (
            select(UserMemory)
            .where(
                UserMemory.owner_id == owner_id,
                UserMemory.enabled.is_(True),
                UserMemory.consent_at.is_not(None),
            )
            .order_by(UserMemory.embedding.cosine_distance(embed_text(query)))
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return list(result.scalars())
