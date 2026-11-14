# 文件说明：外部 Provider 适配：base。
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, cast

from app.domain.itinerary import SourceMetadata
from app.domain.location import GeoPoint

RouteMode = Literal[
    "driving",
    "walking",
    "bicycling",
    "transit",
    "bus",
    "subway",
    "high_speed_rail",
    "train",
    "flight",
]


class ProviderError(Exception):
    code = "provider_error"


class ProviderConfigurationError(ProviderError):
    code = "provider_configuration_error"


class ProviderTimeoutError(ProviderError):
    code = "provider_timeout"


class ProviderRateLimitError(ProviderError):
    code = "provider_rate_limited"


class ProviderUnavailableError(ProviderError):
    code = "provider_unavailable"


class ProviderResponseError(ProviderError):
    code = "provider_response_invalid"


class ProviderModeUnsupportedError(ProviderError):
    code = "provider_mode_unsupported"


@dataclass(frozen=True, slots=True)
class PlaceQuery:
    keyword: str
    city: str | None = None
    types: str | None = None
    limit: int = 10


@dataclass(frozen=True, slots=True)
class PlaceResult:
    provider_place_id: str
    name: str
    category: str | None
    address: str | None
    location: GeoPoint | None
    tel: str | None
    opening_hours: list[str]
    source: SourceMetadata
    reference_price: str | None = None


class NearbyPlaceProvider(Protocol):
    name: str

    async def search_nearby(
        self,
        *,
        location: GeoPoint,
        radius_m: int,
        types: list[str],
        limit: int,
    ) -> list[PlaceResult]: ...


@dataclass(frozen=True, slots=True)
class RouteRequest:
    origin: GeoPoint
    destination: GeoPoint
    mode: RouteMode
    city: str | None = None


@dataclass(frozen=True, slots=True)
class RouteResult:
    distance_m: int
    duration_s: int
    polyline: str | None
    source: SourceMetadata


@dataclass(frozen=True, slots=True)
class StaticMapMarker:
    label: str
    name: str
    point: GeoPoint


@dataclass(frozen=True, slots=True)
class StaticMapRequest:
    markers: list[StaticMapMarker]
    paths: list[list[GeoPoint]]
    center: GeoPoint
    zoom: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class StaticMapImage:
    content: bytes
    media_type: str


class MapProvider(Protocol):
    name: str

    async def search_places(self, query: PlaceQuery) -> list[PlaceResult]: ...

    async def get_place(self, provider_place_id: str) -> PlaceResult: ...

    async def geocode(self, address: str) -> GeoPoint: ...

    async def get_route(self, request: RouteRequest) -> RouteResult: ...

    async def render_static_map(self, request: StaticMapRequest) -> StaticMapImage: ...


def point_to_record(point: GeoPoint | None) -> dict[str, object] | None:
    if point is None:
        return None
    return {
        "longitude": point.longitude,
        "latitude": point.latitude,
        "coordinate_system": point.coordinate_system,
    }


def normalize_category_text(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    parts = [
        part.strip()
        for part in value.replace("|", ";").split(";")
        if part.strip()
    ]
    return " / ".join(dict.fromkeys(parts)) or None


def point_from_record(record: object) -> GeoPoint | None:
    if not isinstance(record, dict):
        return None
    coordinate_system = str(record.get("coordinate_system", "GCJ-02"))
    if coordinate_system not in {"GCJ-02", "WGS84"}:
        coordinate_system = "GCJ-02"
    coordinate = cast(Literal["GCJ-02", "WGS84"], coordinate_system)
    return GeoPoint(
        longitude=float(record["longitude"]),
        latitude=float(record["latitude"]),
        coordinate_system=coordinate,
    )


def place_to_record(place: PlaceResult) -> dict[str, object]:
    return {
        "provider_place_id": place.provider_place_id,
        "name": place.name,
        "category": place.category,
        "address": place.address,
        "location": point_to_record(place.location),
        "tel": place.tel,
        "opening_hours": place.opening_hours,
        "source": place.source.to_record(),
        "reference_price": place.reference_price,
    }


def place_from_record(record: dict[str, object]) -> PlaceResult:
    raw_hours = record.get("opening_hours")
    opening_hours = (
        [str(item) for item in raw_hours if str(item)]
        if isinstance(raw_hours, list)
        else []
    )
    source_record = record.get("source")
    if not isinstance(source_record, dict):
        raise ValueError("place source metadata is missing")
    return PlaceResult(
        provider_place_id=str(record["provider_place_id"]),
        name=str(record["name"]),
        category=str(record["category"]) if record.get("category") is not None else None,
        address=str(record["address"]) if record.get("address") is not None else None,
        location=point_from_record(record.get("location")),
        tel=str(record["tel"]) if record.get("tel") is not None else None,
        opening_hours=opening_hours,
        source=SourceMetadata.from_record(source_record),
        reference_price=(
            str(record["reference_price"])
            if record.get("reference_price") is not None
            else None
        ),
    )


def fresh_source(
    *,
    provider: str,
    provider_place_id: str | None,
    source_url: str | None,
    freshness: Literal["live", "cached", "mock", "unknown"],
    confidence: float,
    queried_at: datetime | None = None,
) -> SourceMetadata:
    from datetime import UTC

    return SourceMetadata(
        provider=provider,
        provider_place_id=provider_place_id,
        source_url=source_url,
        queried_at=queried_at or datetime.now(UTC),
        freshness=freshness,
        confidence=max(0.0, min(1.0, confidence)),
    )
