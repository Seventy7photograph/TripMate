# 文件说明：路线缓存坐标失效回归测试。

from uuid import uuid4

import httpx

from app.api.v1.routes import get_route_service
from app.core.config import get_settings
from app.main import app
from app.providers.base import RouteRequest, RouteResult, fresh_source
from app.services.route_service import RouteService
from tests.test_auth import auth_headers, register_user
from tests.test_routes import create_day, create_stop, create_trip


class RecordingRouteProvider:
    name = "recording-map"

    def __init__(self) -> None:
        self.calls = 0

    async def get_route(self, request: RouteRequest) -> RouteResult:
        del request
        self.calls += 1
        return RouteResult(
            distance_m=100 + self.calls,
            duration_s=60,
            polyline=(
                "106.570000,29.550000;"
                "106.580000,29.560000"
            ),
            source=fresh_source(
                provider=self.name,
                provider_place_id=None,
                source_url=None,
                freshness="live",
                confidence=0.9,
            ),
        )


async def test_route_cache_invalidates_when_stop_coordinates_change(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(
        api_client,
        email=f"route-cache-{uuid4().hex}@example.com",
    )
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
        name="起点",
        expected_version=2,
        longitude=106.570,
        latitude=29.550,
    )
    second = await create_stop(
        api_client,
        token,
        str(day["id"]),
        name="终点",
        expected_version=3,
        longitude=106.580,
        latitude=29.560,
    )
    provider = RecordingRouteProvider()

    async def recording_service():
        yield RouteService(
            app.state.test_session,
            get_settings(),
            provider=provider,  # type: ignore[arg-type]
        )

    app.dependency_overrides[get_route_service] = recording_service
    try:
        first_route = await api_client.post(
            f"/api/v1/trips/{trip['id']}/days/{day['id']}/routes",
            headers=auth_headers(token),
            json={
                "expected_version": 4,
                "stop_ids": [first["id"], second["id"]],
                "mode": "driving",
            },
        )
        assert first_route.status_code == 200, first_route.text

        moved = await api_client.patch(
            f"/api/v1/stops/{first['id']}",
            headers=auth_headers(token),
            json={
                "expected_version": 4,
                "location": {
                    "longitude": 106.575,
                    "latitude": 29.555,
                    "coordinate_system": "GCJ-02",
                },
            },
        )
        assert moved.status_code == 200, moved.text

        second_route = await api_client.post(
            f"/api/v1/trips/{trip['id']}/days/{day['id']}/routes",
            headers=auth_headers(token),
            json={
                "expected_version": 5,
                "stop_ids": [first["id"], second["id"]],
                "mode": "driving",
            },
        )
    finally:
        app.dependency_overrides.pop(get_route_service, None)

    assert second_route.status_code == 200, second_route.text
    assert provider.calls == 2
    assert second_route.json()["legs"][0]["source"]["freshness"] == "live"
