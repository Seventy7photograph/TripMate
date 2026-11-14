# 文件说明：Agent 受控工具：context。
from collections.abc import Collection
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.evidence.models import EvidenceRecord
from app.tools.base import ToolRunner


class EvidenceWriter(Protocol):
    async def upsert(self, record: EvidenceRecord) -> EvidenceRecord: ...


@dataclass(frozen=True, slots=True)
class ToolContext:
    runner: ToolRunner
    allowed_tools: Collection[str]
    provider_permissions: Collection[str]
    owner_id: UUID | None
    evidence_writer: EvidenceWriter | None = None
    allowed_mcp_connectors: Collection[str] = ()
