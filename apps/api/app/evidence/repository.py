# 文件说明：Evidence 事实层：repository。
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.evidence.models import EvidenceFactType, EvidenceFreshness, EvidenceRecord
from app.models.evidence import EvidenceRecord as EvidenceRecordModel


class EvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_owner(
        self,
        *,
        owner_id: UUID,
        evidence_id: UUID,
    ) -> EvidenceRecord | None:
        result = await self._session.execute(
            select(EvidenceRecordModel).where(
                EvidenceRecordModel.id == evidence_id,
                EvidenceRecordModel.owner_id == owner_id,
            )
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def list_for_owner(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID | None = None,
        evidence_ids: set[UUID] | None = None,
    ) -> list[EvidenceRecord]:
        statement = select(EvidenceRecordModel).where(
            EvidenceRecordModel.owner_id == owner_id,
        )
        if trip_id is not None:
            statement = statement.where(
                EvidenceRecordModel.trip_id == trip_id
            )
        if evidence_ids:
            statement = statement.where(
                EvidenceRecordModel.id.in_(evidence_ids)
            )
        result = await self._session.execute(statement)
        return [
            self._to_domain(model)
            for model in result.scalars()
        ]

    async def upsert(self, record: EvidenceRecord) -> EvidenceRecord:
        model = await self._find_upsert_target(record)
        if model is None:
            model = EvidenceRecordModel(
                id=record.id,
                owner_id=record.owner_id,
                trip_id=record.trip_id,
                fact_type=record.fact_type,
                provider=record.provider,
                provider_record_id=record.provider_record_id,
                fetched_at=record.fetched_at,
                value=record.value,
            )
            self._session.add(model)

        model.source_url = record.source_url
        model.fetched_at = record.fetched_at
        model.valid_until = record.valid_until
        model.confidence = Decimal(str(record.confidence))
        model.freshness = record.freshness
        model.license_scope = record.license_scope
        model.raw_hash = record.raw_hash
        model.value = record.value

        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def _find_upsert_target(
        self,
        record: EvidenceRecord,
    ) -> EvidenceRecordModel | None:
        if record.provider_record_id is None:
            return None
        statement = select(EvidenceRecordModel).where(
            EvidenceRecordModel.owner_id == record.owner_id,
            EvidenceRecordModel.fact_type == record.fact_type,
            EvidenceRecordModel.provider == record.provider,
            EvidenceRecordModel.provider_record_id == record.provider_record_id,
        )
        if record.trip_id is None:
            statement = statement.where(EvidenceRecordModel.trip_id.is_(None))
        else:
            statement = statement.where(EvidenceRecordModel.trip_id == record.trip_id)
        result = await self._session.execute(statement)
        return cast(EvidenceRecordModel | None, result.scalar_one_or_none())

    @staticmethod
    def _to_domain(model: EvidenceRecordModel) -> EvidenceRecord:
        return EvidenceRecord(
            id=model.id,
            owner_id=model.owner_id,
            trip_id=model.trip_id,
            fact_type=cast(EvidenceFactType, model.fact_type),
            provider=model.provider,
            provider_record_id=model.provider_record_id,
            source_url=model.source_url,
            fetched_at=model.fetched_at,
            valid_until=model.valid_until,
            confidence=float(model.confidence),
            freshness=cast(EvidenceFreshness, model.freshness),
            license_scope=model.license_scope,
            raw_hash=model.raw_hash,
            value=model.value,
        )
