# 文件说明：Agent 受控工具：attachment_tools。
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.evidence.draft import EvidenceDraft
from app.services.prompt_safety import PromptSafetyService
from app.services.upload_service import UploadContext
from app.tools.context import ToolContext
from app.tools.contracts import ToolSpec
from app.tools.evidence import write_evidence


class AttachmentService(Protocol):
    async def context_for_message(
        self,
        *,
        owner_id: UUID,
        asset_ids: list[UUID],
    ) -> UploadContext: ...


class ExtractAttachmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_ids: list[UUID] = Field(min_length=1, max_length=3)


class AttachmentFactOutput(BaseModel):
    asset_id: UUID
    name: str
    kind: str
    summary: str


class AttachmentUnderstandingOutput(BaseModel):
    facts: list[AttachmentFactOutput]
    risk_flags: list[str]
    missing_fields: list[str]
    evidence_ids: list[UUID]


_EXTRACT_ATTACHMENT_SPEC = ToolSpec(
    name="extract_attachment",
    description="Extract bounded facts and risks from owner-scoped attachments.",
    input_model=ExtractAttachmentInput,
    output_model=AttachmentUnderstandingOutput,
    provider_type="attachment",
    risk="read",
    timeout_seconds=15,
    max_retries=0,
)


class AttachmentTool:
    name = _EXTRACT_ATTACHMENT_SPEC.name

    def __init__(
        self,
        service: AttachmentService,
        context: ToolContext,
    ) -> None:
        self._service = service
        self._context = context
        self._safety = PromptSafetyService()

    async def invoke(
        self,
        context: ToolContext,
        payload: BaseModel,
    ) -> BaseModel:
        if context.owner_id is None:
            raise ValueError("owner_id is required for attachment reads")
        owner_id = context.owner_id
        request = ExtractAttachmentInput.model_validate(payload)
        upload_context = await context.runner.call(
            tool_name=self.name,
            provider="attachment-service",
            input_payload=request.model_dump(mode="json"),
            operation=lambda: self._service.context_for_message(
                owner_id=owner_id,
                asset_ids=request.asset_ids,
            ),
            timeout_seconds=_EXTRACT_ATTACHMENT_SPEC.timeout_seconds,
            max_retries=_EXTRACT_ATTACHMENT_SPEC.max_retries,
        )
        document_by_name = dict(upload_context.documents)
        facts: list[AttachmentFactOutput] = []
        risk_flags: list[str] = []
        missing_fields: list[str] = []
        evidence_ids: list[UUID] = []
        for asset in upload_context.assets:
            text = document_by_name.get(asset.original_name, "")
            assessment = self._safety.assess(f"{asset.original_name}\n{text}")
            risk_flags.extend(assessment.codes)
            if asset.kind == "image":
                missing_fields.append(
                    f"{asset.original_name}: image content requires vision model"
                )
            summary = (
                f"{len(text)} 字符文本，已按不可信附件数据处理"
                if text
                else f"{asset.mime_type} 附件，未提取正文"
            )
            facts.append(
                AttachmentFactOutput(
                    asset_id=asset.id,
                    name=asset.original_name,
                    kind=asset.kind,
                    summary=summary,
                )
            )
            evidence_ids.append(
                await write_evidence(
                    context,
                    EvidenceDraft(
                        fact_type="attachment",
                        provider="attachment-extractor",
                        provider_record_id=str(asset.id),
                        source_url=None,
                        fetched_at=datetime.now(UTC),
                        confidence=0.9 if text else 0.5,
                        freshness="live" if text else "unknown",
                        value={
                            "name": asset.original_name,
                            "kind": asset.kind,
                            "mime_type": asset.mime_type,
                            "text_length": len(text),
                            "excerpt": text[:300],
                            "risk_codes": assessment.codes,
                            "risk": assessment.risk.value,
                        },
                    ),
                )
            )
        return AttachmentUnderstandingOutput(
            facts=facts,
            risk_flags=list(dict.fromkeys(risk_flags)),
            missing_fields=missing_fields,
            evidence_ids=evidence_ids,
        )

    @staticmethod
    def spec() -> ToolSpec:
        return _EXTRACT_ATTACHMENT_SPEC
