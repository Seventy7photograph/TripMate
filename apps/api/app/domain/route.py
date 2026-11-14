# 文件说明：领域对象：route。
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.itinerary import SourceMetadata
from app.providers.base import RouteMode


@dataclass(frozen=True, slots=True)
class RouteLeg:
    id: UUID
    day_id: UUID
    from_stop_id: UUID
    to_stop_id: UUID
    mode: RouteMode
    distance_m: int
    duration_s: int
    polyline: str | None
    source: SourceMetadata

    @property
    def provider(self) -> str:
        return self.source.provider

    @property
    def fetched_at(self) -> datetime:
        return self.source.queried_at
