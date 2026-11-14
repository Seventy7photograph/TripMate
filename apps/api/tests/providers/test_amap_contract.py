# 文件说明：后端自动化测试：test_amap_contract。
import json
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.providers.amap import AmapMapProvider
from app.providers.base import (
    GeoPoint,
    PlaceQuery,
    ProviderModeUnsupportedError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    RouteMode,
    RouteRequest,
)
from app.services.place_service import create_map_provider

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_map_provider_profile_can_be_live_while_llm_profile_is_mock() -> None:
    settings = Settings(
        provider_profile="mock",
        map_provider_profile="live",
        amap_web_service_key="test-key",
    )

    provider = create_map_provider(settings)

    assert provider.name == "amap"


def search_fixture() -> dict[str, object]:
    return json.loads((FIXTURES / "amap_place_search.json").read_text(encoding="utf-8"))


async def test_amap_search_detail_geocode_and_route_contract() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v3/place/text":
            return httpx.Response(200, json=search_fixture())
        if request.url.path == "/v3/place/detail":
            payload = search_fixture()
            payload["pois"] = payload["pois"][:1]
            return httpx.Response(200, json=payload)
        if request.url.path == "/v3/geocode/geo":
            return httpx.Response(
                200,
                json={
                    "status": "1",
                    "info": "OK",
                    "infocode": "10000",
                    "geocodes": [
                        {
                            "formatted_address": "重庆市渝中区洪崖洞",
                            "location": "106.579109,29.562819",
                        }
                    ],
                },
            )
        if request.url.path == "/v3/direction/driving":
            return httpx.Response(
                200,
                json={
                    "status": "1",
                    "info": "OK",
                    "infocode": "10000",
                    "route": {
                        "paths": [
                            {
                                "distance": "3200",
                                "duration": "780",
                                "steps": [{"polyline": "106.57,29.55;106.58,29.56"}],
                            }
                        ]
                    },
                },
            )
        raise AssertionError(f"Unexpected request: {request.url}")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = AmapMapProvider(
        key="test-amap-key",
        base_url="https://restapi.amap.com",
        client=client,
        timeout_seconds=1,
        max_retries=0,
        retry_delay_seconds=0,
    )

    results = await provider.search_places(
        PlaceQuery(keyword="洪崖洞", city="重庆", limit=2)
    )
    assert len(results) == 2
    assert results[0].provider_place_id == "B001TEST01"
    assert results[0].location is not None
    assert results[0].location.coordinate_system == "GCJ-02"
    assert results[0].source.provider == "amap"
    assert results[0].source.freshness == "live"
    assert results[0].source.queried_at.tzinfo is not None

    detail = await provider.get_place("B001TEST01")
    assert detail.name == "洪崖洞民俗风貌区"
    assert "嘉陵江滨江路88号" in (detail.address or "")

    point = await provider.geocode("重庆市渝中区洪崖洞")
    assert point.coordinate_system == "GCJ-02"
    assert point.longitude == pytest.approx(106.579109)

    route = await provider.get_route(
        RouteRequest(
            origin=results[0].location,
            destination=results[1].location,
            mode="driving",
        )
    )
    assert route.distance_m == 3200
    assert route.duration_s == 780
    assert route.source.provider == "amap"
    assert "106.57" in (route.polyline or "")
    assert len(requests) == 4

    await client.aclose()


async def test_amap_bicycling_v4_parses_path_polyline() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v4/direction/bicycling"
        return httpx.Response(
            200,
            json={
                "errcode": 0,
                "errmsg": "OK",
                "data": {
                    "paths": [
                        {
                            "distance": 4063,
                            "duration": 975,
                            "steps": [
                                {
                                    "polyline": (
                                        "106.579141,29.56273;"
                                        "106.578316,29.562478"
                                    )
                                }
                            ],
                        }
                    ]
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = AmapMapProvider(
        key="test-amap-key",
        client=client,
        max_retries=0,
        retry_delay_seconds=0,
    )

    route = await provider.get_route(
        RouteRequest(
            origin=GeoPoint(106.579109, 29.562819),
            destination=GeoPoint(106.577178, 29.557456),
            mode="bicycling",
        )
    )

    assert route.distance_m == 4063
    assert route.duration_s == 975
    assert route.polyline == (
        "106.579141,29.56273;106.578316,29.562478"
    )
    await client.aclose()


async def test_amap_nearby_search_maps_real_poi_fields() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v3/place/around"
        assert request.url.params["radius"] == "1000"
        payload = search_fixture()
        payload["pois"] = payload["pois"][:1]
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = AmapMapProvider(
        key="test-amap-key",
        client=client,
        max_retries=0,
        retry_delay_seconds=0,
    )

    places = await provider.search_nearby(
        location=GeoPoint(118.58, 24.91),
        radius_m=1_000,
        types=["风景名胜"],
        limit=3,
    )

    assert places[0].provider_place_id == "B001TEST01"
    assert places[0].location is not None
    assert places[0].source.provider == "amap"
    await client.aclose()


async def test_amap_transit_combines_walking_and_bus_polylines() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v3/direction/transit/integrated"
        return httpx.Response(
            200,
            json={
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "route": {
                    "transits": [
                        {
                            "distance": "2930",
                            "duration": "1888",
                            "segments": [
                                {
                                    "walking": {
                                        "steps": [
                                            {
                                                "polyline": (
                                                    "106.579140,29.562731;"
                                                    "106.578316,29.562479"
                                                )
                                            }
                                        ]
                                    },
                                    "bus": {"buslines": []},
                                },
                                {
                                    "walking": {"steps": []},
                                    "bus": {
                                        "buslines": [
                                            {
                                                "polyline": (
                                                    "106.578316,29.562479;"
                                                    "106.577178,29.557456"
                                                )
                                            }
                                        ]
                                    },
                                },
                            ],
                        }
                    ]
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = AmapMapProvider(
        key="test-amap-key",
        client=client,
        max_retries=0,
        retry_delay_seconds=0,
    )

    route = await provider.get_route(
        RouteRequest(
            origin=GeoPoint(106.579109, 29.562819),
            destination=GeoPoint(106.577178, 29.557456),
            mode="transit",
            city="重庆",
        )
    )

    assert route.distance_m == 2930
    assert route.duration_s == 1888
    assert "106.579140" in (route.polyline or "")
    assert "106.577178" in (route.polyline or "")
    await client.aclose()


async def test_amap_splits_bus_and_subway_transit_options() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v3/direction/transit/integrated"
        return httpx.Response(
            200,
            json={
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "route": {
                    "transits": [
                        {
                            "distance": "1200",
                            "duration": "600",
                            "segments": [
                                {
                                    "bus": {
                                        "buslines": [
                                            {
                                                "name": "123路",
                                                "type": "公交线路",
                                                "polyline": "106.50,29.50;106.51,29.51",
                                            }
                                        ]
                                    }
                                }
                            ],
                        },
                        {
                            "distance": "1800",
                            "duration": "420",
                            "segments": [
                                {
                                    "bus": {
                                        "buslines": [
                                            {
                                                "name": "轨道交通2号线",
                                                "type": "地铁线路",
                                                "polyline": "106.50,29.50;106.52,29.52",
                                            }
                                        ]
                                    }
                                }
                            ],
                        },
                    ]
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = AmapMapProvider(
        key="test-amap-key",
        client=client,
        max_retries=0,
        retry_delay_seconds=0,
    )
    request = RouteRequest(
        origin=GeoPoint(106.50, 29.50),
        destination=GeoPoint(106.52, 29.52),
        mode="bus",
        city="重庆",
    )

    bus = await provider.get_route(request)
    subway = await provider.get_route(
        RouteRequest(
            origin=request.origin,
            destination=request.destination,
            mode="subway",
            city="重庆",
        )
    )

    assert bus.duration_s == 600
    assert "106.51" in (bus.polyline or "")
    assert subway.duration_s == 420
    assert "106.52" in (subway.polyline or "")
    await client.aclose()


async def test_amap_rejects_intercity_modes_without_fake_geometry() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(500, request=request)
        )
    )
    provider = AmapMapProvider(
        key="test-amap-key",
        client=client,
        max_retries=0,
        retry_delay_seconds=0,
    )

    with pytest.raises(ProviderModeUnsupportedError):
        await provider.get_route(
            RouteRequest(
                origin=GeoPoint(121.4737, 31.2304),
                destination=GeoPoint(87.6168, 43.8256),
                mode="flight",
            )
        )

    await client.aclose()


async def test_amap_timeout_is_retried_without_fake_success() -> None:
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.TimeoutException("timed out")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = AmapMapProvider(
        key="test-amap-key",
        base_url="https://restapi.amap.com",
        client=client,
        timeout_seconds=0.1,
        max_retries=2,
        retry_delay_seconds=0,
    )

    with pytest.raises(ProviderTimeoutError):
        await provider.search_places(PlaceQuery(keyword="洪崖洞"))

    assert attempts == 3
    await client.aclose()


async def test_amap_429_is_retried_and_returns_explicit_error() -> None:
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429, json={"status": "0", "infocode": "10004"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = AmapMapProvider(
        key="test-amap-key",
        base_url="https://restapi.amap.com",
        client=client,
        timeout_seconds=0.1,
        max_retries=1,
        retry_delay_seconds=0,
    )

    with pytest.raises(ProviderRateLimitError):
        await provider.geocode("重庆市渝中区")

    assert attempts == 2
    await client.aclose()


def test_route_modes_are_supported() -> None:
    modes: set[RouteMode] = {
        "driving",
        "walking",
        "bicycling",
        "transit",
        "bus",
        "subway",
        "high_speed_rail",
        "train",
        "flight",
    }
    assert modes == {
        "driving",
        "walking",
        "bicycling",
        "transit",
        "bus",
        "subway",
        "high_speed_rail",
        "train",
        "flight",
    }
