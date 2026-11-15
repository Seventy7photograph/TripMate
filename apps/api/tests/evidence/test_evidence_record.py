# 文件说明：后端自动化测试：test_evidence_record。
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.domain.itinerary import SourceMetadata
from app.evidence.models import EvidenceRecord
from app.evidence.repository import EvidenceRepository
from app.evidence.service import EvidenceService, EvidenceTripNotFoundError
from app.main import app
from tests.test_auth import auth_headers, register_user
from tests.test_trips_crud import trip_payload


def test_evidence_requires_source_and_validity() -> None:
    with pytest.raises(ValidationError):
        EvidenceRecord(
            owner_id="f32ef1e2-97d4-4b67-a847-1e2a4a3f55a1",
            fact_type="weather",
            provider="",
            fetched_at=datetime.now(UTC),
            confidence=1.1,
            freshness="live",
            value={},
        )


def test_evidence_record_preserves_traceability_fields() -> None:
    fetched_at = datetime(2026, 11, 14, 8, 0, tzinfo=UTC)
    valid_until = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)

    record = EvidenceRecord(
        owner_id="f32ef1e2-97d4-4b67-a847-1e2a4a3f55a1",
        fact_type="place_fact",
        provider="amap",
        provider_record_id="B000A8UIN8",
        source_url="https://example.com/place/B000A8UIN8",
        fetched_at=fetched_at,
        valid_until=valid_until,
        confidence=0.92,
        freshness="live",
        license_scope="amap-terms",
        raw_hash="a" * 64,
        value={"name": "开元寺", "opening_hours": "08:00-17:30"},
    )

    assert record.provider == "amap"
    assert record.fetched_at == fetched_at
    assert record.valid_until == valid_until
    assert record.value["name"] == "开元寺"


def test_evidence_rejects_validity_before_fetch_time() -> None:
    with pytest.raises(ValidationError):
        EvidenceRecord(
            owner_id="f32ef1e2-97d4-4b67-a847-1e2a4a3f55a1",
            fact_type="weather",
            provider="amap-weather",
            fetched_at=datetime(2026, 11, 14, 9, 0, tzinfo=UTC),
            valid_until=datetime(2026, 11, 14, 8, 0, tzinfo=UTC),
            confidence=0.8,
            freshness="live",
            value={"temperature_c": 18},
        )


async def test_evidence_is_owner_isolated(api_client: httpx.AsyncClient) -> None:
    owner = await register_user(api_client)
    outsider = await register_user(api_client)
    owner_id = UUID(str(owner["user"]["id"]))
    outsider_id = UUID(str(outsider["user"]["id"]))
    service = EvidenceService(app.state.test_session)

    record = await service.upsert_fact(
        owner_id=owner_id,
        trip_id=None,
        fact_type="weather",
        value={"temperature_c": 18, "condition": "clear"},
        source=_source(owner_id),
        valid_until=datetime.now(UTC) + timedelta(hours=1),
    )

    repository = EvidenceRepository(app.state.test_session)
    assert await repository.get_for_owner(
        owner_id=outsider_id,
        evidence_id=record.id,
    ) is None
    assert await repository.get_for_owner(
        owner_id=owner_id,
        evidence_id=record.id,
    ) == record


async def test_evidence_rejects_trip_owned_by_another_user(
    api_client: httpx.AsyncClient,
) -> None:
    owner = await register_user(api_client)
    outsider = await register_user(api_client)
    owner_id = UUID(str(owner["user"]["id"]))
    outsider_id = UUID(str(outsider["user"]["id"]))
    trip = await api_client.post(
        "/api/v1/trips",
        headers=auth_headers(str(owner["access_token"])),
        json=trip_payload(destination="泉州"),
    )
    assert trip.status_code == 201, trip.text
    service = EvidenceService(app.state.test_session)

    with pytest.raises(EvidenceTripNotFoundError):
        await service.upsert_fact(
            owner_id=outsider_id,
            trip_id=UUID(str(trip.json()["id"])),
            fact_type="place_fact",
            value={"name": "开元寺"},
            source=_source(outsider_id),
            valid_until=None,
        )

    assert owner_id != outsider_id


async def test_evidence_upsert_reuses_provider_record(
    api_client: httpx.AsyncClient,
) -> None:
    owner = await register_user(api_client)
    owner_id = UUID(str(owner["user"]["id"]))
    service = EvidenceService(app.state.test_session)
    first_fetched_at = datetime.now(UTC)

    first = await service.upsert_fact(
        owner_id=owner_id,
        trip_id=None,
        fact_type="place_fact",
        value={"name": "开元寺", "opening_hours_status": "unknown"},
        source=_source(owner_id, queried_at=first_fetched_at),
        valid_until=first_fetched_at + timedelta(hours=24),
    )
    second = await service.upsert_fact(
        owner_id=owner_id,
        trip_id=None,
        fact_type="place_fact",
        value={"name": "开元寺", "opening_hours_status": "known"},
        source=_source(
            owner_id,
            queried_at=first_fetched_at + timedelta(minutes=5),
        ),
        valid_until=first_fetched_at + timedelta(hours=25),
    )

    assert second.id == first.id
    assert second.value["opening_hours_status"] == "known"
    assert second.fetched_at > first.fetched_at


async def test_evidence_service_marks_expired_record_stale(
    api_client: httpx.AsyncClient,
) -> None:
    fetched_at = datetime(2026, 11, 14, 8, 0, tzinfo=UTC)
    record = EvidenceRecord(
        owner_id=uuid4(),
        fact_type="weather",
        provider="amap-weather",
        fetched_at=fetched_at,
        valid_until=fetched_at + timedelta(hours=1),
        confidence=0.9,
        freshness="live",
        value={"temperature_c": 18},
    )
    service = EvidenceService(app.state.test_session)

    assert service.is_stale(
        record,
        now=datetime(2026, 11, 14, 8, 59, tzinfo=UTC),
    ) is False
    assert service.is_stale(
        record,
        now=datetime(2026, 11, 14, 9, 0, tzinfo=UTC),
    ) is True


def _source(
    owner_id: UUID,
    *,
    queried_at: datetime | None = None,
) -> SourceMetadata:
    return SourceMetadata(
        provider="amap",
        provider_place_id=f"place-{owner_id}",
        source_url=f"https://example.com/places/{owner_id}",
        queried_at=queried_at or datetime.now(UTC),
        freshness="live",
        confidence=0.9,
    )
