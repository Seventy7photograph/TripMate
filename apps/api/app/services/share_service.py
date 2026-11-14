# 文件说明：业务服务：share_service。
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.share_link import ShareLink as ShareLinkModel
from app.repositories.itinerary_repository import ItineraryRepository
from app.repositories.trip_repository import TripRepository


class ShareNotFoundError(Exception):
    pass


class ShareTripNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ShareCreated:
    id: UUID
    token: str
    expires_at: datetime
    created_at: datetime


class ShareService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._trips = TripRepository(session)
        self._itineraries = ItineraryRepository(session)

    async def create(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        expires_in_days: int,
    ) -> ShareCreated:
        snapshot = await self._snapshot(owner_id=owner_id, trip_id=trip_id)
        token = secrets.token_urlsafe(32)
        model = ShareLinkModel(
            trip_id=trip_id,
            created_by=owner_id,
            token_hash=self._hash_token(token),
            snapshot=snapshot,
            expires_at=datetime.now(UTC) + timedelta(days=expires_in_days),
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        await self._session.commit()
        return ShareCreated(
            id=model.id,
            token=token,
            expires_at=model.expires_at,
            created_at=model.created_at,
        )

    async def list(self, *, owner_id: UUID, trip_id: UUID) -> list[ShareLinkModel]:
        trip = await self._trips.get_for_owner(owner_id=owner_id, trip_id=trip_id)
        if trip is None:
            raise ShareTripNotFoundError
        result = await self._session.execute(
            select(ShareLinkModel)
            .where(
                ShareLinkModel.trip_id == trip_id,
                ShareLinkModel.created_by == owner_id,
            )
            .order_by(ShareLinkModel.created_at.desc())
        )
        return list(result.scalars())

    async def revoke(self, *, owner_id: UUID, share_id: UUID) -> None:
        result = await self._session.execute(
            select(ShareLinkModel).where(
                ShareLinkModel.id == share_id,
                ShareLinkModel.created_by == owner_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ShareNotFoundError
        model.revoked_at = model.revoked_at or datetime.now(UTC)
        await self._session.flush()
        await self._session.commit()

    async def public_snapshot(self, *, token: str) -> dict[str, object]:
        result = await self._session.execute(
            select(ShareLinkModel).where(
                ShareLinkModel.token_hash == self._hash_token(token),
                ShareLinkModel.revoked_at.is_(None),
                ShareLinkModel.expires_at > datetime.now(UTC),
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ShareNotFoundError
        return model.snapshot

    async def export_document(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
    ) -> dict[str, object]:
        snapshot = await self._snapshot(owner_id=owner_id, trip_id=trip_id)
        slug = "".join(
            character.lower() if character.isalnum() else "-"
            for character in str(snapshot["destination"])
        ).strip("-")
        snapshot["filename"] = f"tripmate-{slug or 'trip'}-{snapshot['version']}"
        return snapshot

    async def _snapshot(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
    ) -> dict[str, object]:
        trip = await self._trips.get_for_owner(owner_id=owner_id, trip_id=trip_id)
        if trip is None:
            raise ShareTripNotFoundError
        days = await self._itineraries.list_days(trip_id=trip.id)
        return {
            "version": trip.version,
            "destination": trip.brief.destination,
            "origin": trip.brief.origin,
            "start_date": trip.brief.start_date.isoformat(),
            "end_date": trip.brief.end_date.isoformat(),
            "party_size": trip.brief.party_size,
            "currency": trip.brief.currency,
            "generated_at": datetime.now(UTC).isoformat(),
            "days": [
                {
                    "date": day.date.isoformat(),
                    "day_index": day.day_index,
                    "theme": day.theme,
                    "stops": [
                        {
                            "place_id": stop.place_id,
                            "place_name": stop.place_name,
                            "start_at": stop.start_at.isoformat(),
                            "duration_minutes": stop.duration_minutes,
                            "location": (
                                {
                                    "longitude": stop.location.longitude,
                                    "latitude": stop.location.latitude,
                                    "coordinate_system": stop.location.coordinate_system,
                                }
                                if stop.location is not None
                                else None
                            ),
                        }
                        for stop in day.stops
                    ],
                }
                for day in days
            ],
        }

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def status(model: ShareLinkModel) -> str:
        if model.revoked_at is not None:
            return "revoked"
        if model.expires_at <= datetime.now(UTC):
            return "expired"
        return "active"
