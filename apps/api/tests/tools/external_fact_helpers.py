# 文件说明：后端自动化测试辅助：外部事实 Tool。
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.evidence.models import EvidenceRecord
from app.tools.base import ToolRunner
from app.tools.context import ToolContext


class MemoryEvidenceWriter:
    def __init__(self) -> None:
        self.records: dict[UUID, EvidenceRecord] = {}

    async def upsert(self, record: EvidenceRecord) -> EvidenceRecord:
        self.records[record.id] = record
        return record


def evidence_context(
    *,
    allowed_tools: set[str],
    provider_permissions: set[str],
    max_calls: int = 12,
) -> tuple[ToolContext, MemoryEvidenceWriter]:
    writer = MemoryEvidenceWriter()
    return (
        ToolContext(
            runner=ToolRunner(
                max_calls=max_calls,
                deadline=datetime.now(UTC) + timedelta(seconds=30),
            ),
            allowed_tools=allowed_tools,
            provider_permissions=provider_permissions,
            owner_id=uuid4(),
            evidence_writer=writer,
        ),
        writer,
    )
