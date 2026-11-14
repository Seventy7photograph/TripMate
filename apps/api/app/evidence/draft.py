# 文件说明：Evidence 事实层：待持久化草稿。
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.evidence.models import EvidenceFactType, EvidenceRecord


class EvidenceDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fact_type: EvidenceFactType
    provider: str = Field(min_length=1, max_length=80)
    provider_record_id: str | None = Field(default=None, max_length=255)
    source_url: str | None = Field(default=None, max_length=2048)
    fetched_at: datetime
    valid_until: datetime | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: Literal["live", "cached", "stale", "mock", "unknown"]
    license_scope: str | None = Field(default=None, max_length=120)
    raw_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    value: dict[str, object]

    def to_record(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID | None = None,
    ) -> EvidenceRecord:
        return EvidenceRecord(
            owner_id=owner_id,
            trip_id=trip_id,
            fact_type=self.fact_type,
            provider=self.provider,
            provider_record_id=self.provider_record_id,
            source_url=self.source_url,
            fetched_at=self.fetched_at,
            valid_until=self.valid_until,
            confidence=self.confidence,
            freshness=self.freshness,
            license_scope=self.license_scope,
            raw_hash=self.raw_hash,
            value=self.value,
        )
