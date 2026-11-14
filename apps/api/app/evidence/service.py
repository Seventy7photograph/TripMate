# 文件说明：Evidence 事实层：service。
import hashlib
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.itinerary import SourceMetadata
from app.evidence.freshness import resolve_freshness
from app.evidence.models import EvidenceRecord
from app.evidence.repository import EvidenceRepository
from app.repositories.trip_repository import TripRepository


class EvidenceTripNotFoundError(Exception):
    pass


class EvidenceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._evidence = EvidenceRepository(session)
        self._trips = TripRepository(session)

    async def upsert(
        self,
        owner_id: UUID,
        trip_id: UUID | None,
        fact_type: str,
        value: dict[str, object],
        source: SourceMetadata,
        valid_until: datetime | None,
    ) -> EvidenceRecord:
        if trip_id is not None:
            trip = await self._trips.get_for_owner(owner_id=owner_id, trip_id=trip_id)
            if trip is None:
                raise EvidenceTripNotFoundError

        record = EvidenceRecord(
            owner_id=owner_id,
            trip_id=trip_id,
            fact_type=fact_type,  # type: ignore[arg-type]
            provider=source.provider,
            provider_record_id=source.provider_place_id,
            source_url=source.source_url,
            fetched_at=source.queried_at,
            valid_until=valid_until,
            confidence=source.confidence,
            freshness=resolve_freshness(
                source_freshness=source.freshness,
                valid_until=valid_until,
                now=source.queried_at,
            ),
            license_scope=None,
            raw_hash=_value_hash(value),
            value=value,
        )
        stored = await self._evidence.upsert(record)
        await self._session.commit()
        return stored

    def is_stale(self, record: EvidenceRecord, now: datetime) -> bool:
        return (
            resolve_freshness(
                source_freshness=record.freshness,
                valid_until=record.valid_until,
                now=now,
            )
            == "stale"
        )


def _value_hash(value: dict[str, object]) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
