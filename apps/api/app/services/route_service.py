# 文件说明：业务服务：route_service。
from dataclasses import dataclass, replace
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.itinerary import ItineraryStop, TripDay
from app.domain.location import GeoPoint
from app.domain.route import RouteLeg
from app.providers.base import (
    MapProvider,
    ProviderError,
    RouteMode,
    RouteRequest,
    StaticMapImage,
    StaticMapMarker,
    StaticMapRequest,
)
from app.repositories.itinerary_repository import ItineraryRepository
from app.repositories.route_repository import RouteRepository
from app.services.place_service import create_map_provider
from app.services.version_service import VersionService, VersionTripNotFoundError


class RouteNotFoundError(Exception):
    pass


class InvalidRouteRequestError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class MapRenderOutcome:
    image: StaticMapImage
    route_available: bool


@dataclass(frozen=True, slots=True)
class RouteLegError:
    from_stop_id: UUID
    to_stop_id: UUID
    mode: RouteMode
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class RouteCalculationOutcome:
    legs: list[RouteLeg]
    errors: list[RouteLegError]
    modes: list[RouteMode]


class RouteService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        provider: MapProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._provider = provider or create_map_provider(settings)
        self._routes = RouteRepository(session)
        self._itinerary = ItineraryRepository(session)
        self._versions = VersionService(session)

    async def calculate(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        day_id: UUID,
        expected_version: int,
        stop_ids: list[UUID],
        mode: RouteMode,
        modes: list[RouteMode] | None,
    ) -> RouteCalculationOutcome:
        day, city = await self._day_for_write(
            owner_id=owner_id,
            trip_id=trip_id,
            day_id=day_id,
            expected_version=expected_version,
        )
        self._validate_order(day=day, stop_ids=stop_ids)
        leg_modes = modes or [mode] * max(len(stop_ids) - 1, 0)
        if len(leg_modes) != max(len(stop_ids) - 1, 0):
            raise InvalidRouteRequestError(
                "modes must match the number of adjacent stop pairs"
            )
        await self._itinerary.set_leg_modes(
            day_id=day.id,
            modes=[str(mode) for mode in leg_modes],
        )

        by_id = {stop.id: stop for stop in day.stops}
        legs: list[RouteLeg] = []
        errors: list[RouteLegError] = []
        for index in range(len(stop_ids) - 1):
            origin = by_id[stop_ids[index]]
            destination = by_id[stop_ids[index + 1]]
            if origin.location is None or destination.location is None:
                continue

            leg_mode = leg_modes[index]
            try:
                cached = await self._routes.get_cached(
                    day_id=day.id,
                    from_stop_id=origin.id,
                    to_stop_id=destination.id,
                    mode=leg_mode,
                    ttl_seconds=(
                        self._settings.route_cache_ttl_seconds
                        if self._provider.name != "mock"
                        else 0
                    ),
                )
                if cached is not None:
                    legs.append(
                        replace(
                            cached,
                            source=replace(cached.source, freshness="cached"),
                        )
                    )
                    continue

                route = await self._provider.get_route(
                    RouteRequest(
                        origin=origin.location,
                        destination=destination.location,
                        mode=leg_mode,
                        city=city,
                    )
                )
                legs.append(
                    await self._routes.upsert(
                        day_id=day.id,
                        from_stop_id=origin.id,
                        to_stop_id=destination.id,
                        mode=leg_mode,
                        route=route,
                    )
                )
            except ProviderError as exc:
                errors.append(
                    RouteLegError(
                        from_stop_id=origin.id,
                        to_stop_id=destination.id,
                        mode=leg_mode,
                        code=exc.code,
                        message=str(exc),
                    )
                )
        await self._session.commit()
        return RouteCalculationOutcome(
            legs=legs,
            errors=errors,
            modes=leg_modes,
        )

    async def render_map(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        day_id: UUID,
        expected_version: int,
        mode: RouteMode,
        zoom: int,
        include_route: bool,
    ) -> MapRenderOutcome:
        day, _ = await self._day_for_write(
            owner_id=owner_id,
            trip_id=trip_id,
            day_id=day_id,
            expected_version=expected_version,
        )
        located_stops = [stop for stop in day.stops if stop.location is not None]
        if not located_stops:
            return MapRenderOutcome(
                image=self._empty_map_image(),
                route_available=False,
            )

        legs: list[RouteLeg] = []
        route_available = False
        if include_route and len(located_stops) >= 2:
            try:
                calculation = await self.calculate(
                    owner_id=owner_id,
                    trip_id=trip_id,
                    day_id=day_id,
                    expected_version=expected_version,
                    stop_ids=[stop.id for stop in day.stops],
                    mode=mode,
                    modes=None,
                )
                legs = calculation.legs
                route_available = bool(legs)
            except ProviderError:
                route_available = False

        markers = [
            StaticMapMarker(
                label=_marker_label(index),
                name=stop.place_name or stop.place_id,
                point=stop.location,
            )
            for index, stop in enumerate(located_stops)
            if stop.location is not None
        ]
        paths = self._route_paths(legs=legs, stops=located_stops)
        center = GeoPoint(
            longitude=sum(marker.point.longitude for marker in markers) / len(markers),
            latitude=sum(marker.point.latitude for marker in markers) / len(markers),
        )
        image = await self._provider.render_static_map(
            StaticMapRequest(
                markers=markers,
                paths=paths,
                center=center,
                zoom=zoom,
                width=900,
                height=520,
            )
        )
        return MapRenderOutcome(image=image, route_available=route_available)

    async def _day_for_write(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        day_id: UUID,
        expected_version: int,
    ) -> tuple[TripDay, str | None]:
        try:
            trip = await self._versions.lock_trip(
                owner_id=owner_id,
                trip_id=trip_id,
                expected_version=expected_version,
            )
        except VersionTripNotFoundError as exc:
            raise RouteNotFoundError from exc
        day = await self._itinerary.get_day_for_owner(
            owner_id=owner_id,
            day_id=day_id,
        )
        if day is None or day.trip_id != trip_id:
            raise RouteNotFoundError
        destination = trip.brief.get("destination")
        city = (
            str(destination).strip()
            if isinstance(destination, str) and destination.strip()
            else None
        )
        return day, city

    @staticmethod
    def _validate_order(*, day: TripDay, stop_ids: list[UUID]) -> None:
        current_ids = [stop.id for stop in day.stops]
        if (
            len(stop_ids) != len(current_ids)
            or len(set(stop_ids)) != len(stop_ids)
            or set(stop_ids) != set(current_ids)
        ):
            raise InvalidRouteRequestError(
                "stop_ids must contain every day stop exactly once"
            )

    def _route_paths(
        self,
        *,
        legs: list[RouteLeg],
        stops: list[ItineraryStop],
    ) -> list[list[GeoPoint]]:
        paths: list[list[GeoPoint]] = []
        for leg in legs:
            if leg.polyline:
                points = self._parse_polyline(leg.polyline)
                if len(points) >= 2:
                    paths.append(points)
                    continue
            if self._provider.name == "mock":
                origin = next(
                    (stop.location for stop in stops if stop.id == leg.from_stop_id),
                    None,
                )
                destination = next(
                    (stop.location for stop in stops if stop.id == leg.to_stop_id),
                    None,
                )
                if origin is not None and destination is not None:
                    paths.append([origin, destination])
        return paths

    @staticmethod
    def _parse_polyline(polyline: str) -> list[GeoPoint]:
        points: list[GeoPoint] = []
        for raw_point in polyline.split(";"):
            if "," not in raw_point:
                continue
            longitude, latitude = raw_point.split(",", maxsplit=1)
            try:
                points.append(
                    GeoPoint(longitude=float(longitude), latitude=float(latitude))
                )
            except ValueError:
                continue
        return points

    @staticmethod
    def _empty_map_image() -> StaticMapImage:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="520" '
            'viewBox="0 0 900 520" role="img" aria-label="No coordinates">'
            '<rect width="900" height="520" fill="#ece8de"/>'
            '<text x="450" y="250" text-anchor="middle" '
            'font-family="Manrope, sans-serif" font-size="22" fill="#52634b">'
            "无法计算路线</text>"
            '<text x="450" y="280" text-anchor="middle" '
            'font-family="Manrope, sans-serif" font-size="12" fill="#68706a">'
            "请为地点补充经纬度后再试</text></svg>"
        )
        return StaticMapImage(content=svg.encode(), media_type="image/svg+xml")


def _marker_label(index: int) -> str:
    if index < 26:
        return chr(65 + index)
    return str(index + 1)
