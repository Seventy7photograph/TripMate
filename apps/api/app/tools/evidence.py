# 文件说明：Agent 受控工具：Evidence 持久化边界。
from uuid import UUID

from app.evidence.draft import EvidenceDraft
from app.tools.context import ToolContext


class EvidenceWriteError(RuntimeError):
    pass


async def write_evidence(
    context: ToolContext,
    draft: EvidenceDraft,
) -> UUID:
    if context.owner_id is None or context.evidence_writer is None:
        raise EvidenceWriteError(
            "owner-scoped evidence writer is required for external facts"
        )
    record = await context.evidence_writer.upsert(
        draft.to_record(owner_id=context.owner_id)
    )
    return record.id
