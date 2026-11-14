# 文件说明：后端自动化测试：test_routes。
from uuid import uuid4

import httpx
import pytest

from app.main import app
from app.providers.base import (
    ProviderTimeoutError,
    RouteRequest,
    RouteResult,
    fresh_source,
)
from tests.test_auth import auth_headers, register_user
from tests.test_trips_crud import trip_payload


async def create_trip(api_client: httpx.AsyncClient, token: str) -> dict[str, object]:
    response = await api_client.post(
        "/api/v1/trips",
        headers=auth_headers(token),
        json=trip_payload(),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_trip_with_destination(
    api_client: httpx.AsyncClient,
    token: str,
    destination: str,
) -> dict[str, object]:
    response = await api_client.post(
        "/api/v1/trips",
        headers=auth_headers(token),
        json=trip_payload(destination=destination),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_day(
    api_client: httpx.AsyncClient,
    token: str,
    trip_id: str,
    *,
    expected_version: int,
) -> dict[str, object]:
    response = await api_client.post(
        f"/api/v1/trips/{trip_id}/days",
        headers=auth_headers(token),
        json={"date": "2026-12-01", "expected_version": expected_version},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_stop(
    api_client: httpx.AsyncClient,
    token: str,
    day_id: str,
    *,
    name: str,
    expected_version: int,
    longitude: float | None,
    latitude: float | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "place_id": f"manual-{uuid4().hex}",
        "place_name": name,
        "start_at": "2026-12-01T09:00:00",
        "duration_minutes": 60,
        "estimated_cost_minor": 0,
        "expected_version": expected_version,
    }
    if longitude is not None and latitude is not None:
        payload["location"] = {
            "longitude": longitude,
            "latitude": latitude,
            "coordinate_system": "GCJ-02",
        }
    response = await api_client.post(
        f"/api/v1/days/{day_id}/stops",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def setup_day_with_stops(
    api_client: httpx.AsyncClient,
) -> tuple[str, str, dict[str, object], list[dict[str, object]], int]:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = await create_trip(api_client, token)
    day = await create_day(
        api_client,
        token,
        str(trip["id"]),
        expected_version=1,
    )
    first = await create_stop(
        api_client,
        token,
        str(day["id"]),
        name="洪崖洞",
        expected_version=2,
        longitude=106.579109,
        latitude=29.562819,
    )
    second = await create_stop(
        api_client,
        token,
        str(day["id"]),
        name="解放碑",
        expected_version=3,
        longitude=106.577178,
        latitude=29.557456,
    )
    third = await create_stop(
        api_client,
        token,
        str(day["id"]),
        name="无坐标地点",
        expected_version=4,
        longitude=None,
        latitude=None,
    )
    return token, str(trip["id"]), day, [first, second, third], 5


async def test_route_legs_follow_order_and_skip_missing_coordinates(
    api_client: httpx.AsyncClient,
) -> None:
    token, trip_id, day, stops, expected_version = await setup_day_with_stops(api_client)

    response = await api_client.post(
        f"/api/v1/trips/{trip_id}/days/{day['id']}/routes",
        headers=auth_headers(token),
        json={
            "expected_version": expected_version,
            "stop_ids": [stop["id"] for stop in stops],
            "mode": "driving",
            "modes": ["walking", "driving"],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    legs = payload["legs"]
    assert payload["errors"] == []
    assert payload["modes"] == ["walking", "driving"]
    assert len(legs) == 1
    assert legs[0]["from_stop_id"] == stops[0]["id"]
    assert legs[0]["to_stop_id"] == stops[1]["id"]
    assert legs[0]["mode"] == "walking"
    assert legs[0]["distance_m"] > 0
    assert legs[0]["duration_s"] > 0
    assert legs[0]["provider"] == "mock"
    assert legs[0]["polyline"]
    assert legs[0]["fetched_at"]

    itinerary = await api_client.get(
        f"/api/v1/trips/{trip_id}/itinerary",
        headers=auth_headers(token),
    )
    assert itinerary.status_code == 200, itinerary.text
    assert itinerary.json()["days"][0]["leg_modes"] == ["walking", "driving"]


async def test_transit_route_receives_trip_destination_city(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = await create_trip_with_destination(api_client, token, "泉州")
    day = await create_day(
        api_client,
        token,
        str(trip["id"]),
        expected_version=1,
    )
    first = await create_stop(
        api_client,
        token,
        str(day["id"]),
        name="开元寺",
        expected_version=2,
        longitude=118.583,
        latitude=24.913,
    )
    second = await create_stop(
        api_client,
        token,
        str(day["id"]),
        name="西街",
        expected_version=3,
        longitude=118.585,
        latitude=24.914,
    )

    captured: list[str | None] = []

    class RecordingProvider:
        name = "mock"

        async def get_route(self, request: RouteRequest) -> RouteResult:
            captured.append(request.city)
            return RouteResult(
                distance_m=500,
                duration_s=300,
                polyline="118.583,24.913;118.585,24.914",
                source=fresh_source(
                    provider="mock",
                    provider_place_id=None,
                    source_url=None,
                    freshness="mock",
                    confidence=1.0,
                ),
            )

    from app.api.v1.routes import get_route_service
    from app.core.config import get_settings
    from app.services.route_service import RouteService

    async def recording_service():
        yield RouteService(
            app.state.test_session,
            get_settings(),
            provider=RecordingProvider(),  # type: ignore[arg-type]
        )

    app.dependency_overrides[get_route_service] = recording_service
    try:
        response = await api_client.post(
            f"/api/v1/trips/{trip['id']}/days/{day['id']}/routes",
            headers=auth_headers(token),
            json={
                "expected_version": 4,
                "stop_ids": [first["id"], second["id"]],
                "mode": "transit",
            },
        )
    finally:
        app.dependency_overrides.pop(get_route_service, None)

    assert response.status_code == 200, response.text
    assert captured == ["泉州"]


async def test_route_modes_and_versions_are_validated(
    api_client: httpx.AsyncClient,
) -> None:
    token, trip_id, day, stops, _ = await setup_day_with_stops(api_client)

    wrong_mode_count = await api_client.post(
        f"/api/v1/trips/{trip_id}/days/{day['id']}/routes",
        headers=auth_headers(token),
        json={
            "expected_version": 5,
            "stop_ids": [stop["id"] for stop in stops],
            "mode": "driving",
            "modes": ["walking"],
        },
    )
    assert wrong_mode_count.status_code == 422

    stale = await api_client.post(
        f"/api/v1/trips/{trip_id}/days/{day['id']}/routes",
        headers=auth_headers(token),
        json={
            "expected_version": 4,
            "stop_ids": [stop["id"] for stop in stops],
            "mode": "driving",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["current_version"] == 5


async def test_route_provider_timeout_returns_per_leg_error(
    api_client: httpx.AsyncClient,
) -> None:
    token, trip_id, day, stops, expected_version = await setup_day_with_stops(api_client)

    class TimeoutProvider:
        name = "mock"

        async def get_route(self, request: RouteRequest) -> RouteResult:
            raise ProviderTimeoutError("route timed out")

    session = app.state.test_session

    from app.api.v1.routes import get_route_service
    from app.core.config import get_settings
    from app.services.route_service import RouteService

    async def broken_service():
        yield RouteService(session, get_settings(), provider=TimeoutProvider())

    app.dependency_overrides[get_route_service] = broken_service
    try:
        response = await api_client.post(
            f"/api/v1/trips/{trip_id}/days/{day['id']}/routes",
            headers=auth_headers(token),
            json={
                "expected_version": expected_version,
                "stop_ids": [stop["id"] for stop in stops],
                "mode": "driving",
            },
        )
    finally:
        app.dependency_overrides.pop(get_route_service, None)
    assert response.status_code == 200
    assert response.json()["legs"] == []
    assert response.json()["errors"][0]["code"] == "provider_timeout"


async def test_mixed_route_modes_keep_successful_legs(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = await create_trip(api_client, token)
    day = await create_day(
        api_client,
        token,
        str(trip["id"]),
        expected_version=1,
    )
    stops = []
    for index, (name, longitude, latitude) in enumerate(
        (
            ("洪崖洞", 106.579109, 29.562819),
            ("解放碑", 106.577178, 29.557456),
            ("李子坝", 106.532124, 29.550071),
        ),
        start=2,
    ):
        stops.append(
            await create_stop(
                api_client,
                token,
                str(day["id"]),
                name=name,
                expected_version=index,
                longitude=longitude,
                latitude=latitude,
            )
        )

    class PartiallyFailingProvider:
        name = "mock"

        def __init__(self) -> None:
            self.calls = 0

        async def get_route(self, request: RouteRequest) -> RouteResult:
            del request
            self.calls += 1
            if self.calls == 2:
                raise ProviderTimeoutError("walking segment timed out")
            return RouteResult(
                distance_m=500,
                duration_s=300,
                polyline="106.579109,29.562819;106.577178,29.557456",
                source=fresh_source(
                    provider="mock",
                    provider_place_id=None,
                    source_url=None,
                    freshness="mock",
                    confidence=1.0,
                ),
            )

    from app.api.v1.routes import get_route_service
    from app.core.config import get_settings
    from app.services.route_service import RouteService

    async def partial_service():
        yield RouteService(
            app.state.test_session,
            get_settings(),
            provider=PartiallyFailingProvider(),  # type: ignore[arg-type]
        )

    app.dependency_overrides[get_route_service] = partial_service
    try:
        response = await api_client.post(
            f"/api/v1/trips/{trip['id']}/days/{day['id']}/routes",
            headers=auth_headers(token),
            json={
                "expected_version": 5,
                "stop_ids": [stop["id"] for stop in stops],
                "mode": "driving",
                "modes": ["driving", "walking"],
            },
        )
    finally:
        app.dependency_overrides.pop(get_route_service, None)

    assert response.status_code == 200, response.text
    assert len(response.json()["legs"]) == 1
    assert len(response.json()["errors"]) == 1
    assert response.json()["errors"][0]["mode"] == "walking"


async def test_mock_static_map_and_route_access_isolation(
    api_client: httpx.AsyncClient,
) -> None:
    owner = await register_user(
        api_client,
        email=f"route-owner-{uuid4().hex}@example.com",
    )
    outsider = await register_user(
        api_client,
        email=f"route-outsider-{uuid4().hex}@example.com",
    )
    owner_token = str(owner["access_token"])
    outsider_token = str(outsider["access_token"])
    trip = await create_trip(api_client, owner_token)
    day = await create_day(
        api_client,
        owner_token,
        str(trip["id"]),
        expected_version=1,
    )
    first = await create_stop(
        api_client,
        owner_token,
        str(day["id"]),
        name="洪崖洞",
        expected_version=2,
        longitude=106.579109,
        latitude=29.562819,
    )
    second = await create_stop(
        api_client,
        owner_token,
        str(day["id"]),
        name="解放碑",
        expected_version=3,
        longitude=106.577178,
        latitude=29.557456,
    )

    map_response = await api_client.get(
        f"/api/v1/trips/{trip['id']}/days/{day['id']}/map",
        headers=auth_headers(owner_token),
        params={
            "expected_version": 4,
            "mode": "walking",
            "zoom": 14,
            "include_route": "true",
        },
    )
    assert map_response.status_code == 200, map_response.text
    assert map_response.headers["content-type"].startswith("image/svg+xml")
    assert "TripMate Mock Map" in map_response.text
    assert first["place_name"] in map_response.text
    assert second["place_name"] in map_response.text

    outsider_route = await api_client.post(
        f"/api/v1/trips/{trip['id']}/days/{day['id']}/routes",
        headers=auth_headers(outsider_token),
        json={
            "expected_version": 4,
            "stop_ids": [first["id"], second["id"]],
            "mode": "walking",
        },
    )
    assert outsider_route.status_code == 404


def test_route_requires_mixed_mode_length() -> None:
    from app.schemas.route import RouteCalculateRequest

    with pytest.raises(ValueError):
        RouteCalculateRequest(
            expected_version=1,
            stop_ids=[uuid4(), uuid4(), uuid4()],
            mode="driving",
            modes=["walking"],
        )
