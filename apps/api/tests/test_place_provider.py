# 文件说明：后端自动化测试：test_place_provider。
import httpx

from app.api.deps import get_settings
from app.core.config import Settings
from app.main import app
from tests.test_auth import auth_headers, register_user


async def test_mock_place_search_is_labeled_and_hides_provider_key(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])

    status_response = await api_client.get(
        "/api/v1/providers/map/status",
        headers=auth_headers(token),
    )
    assert status_response.status_code == 200
    assert status_response.json()["profile"] == "mock"
    assert status_response.json()["provider"] == "mock"

    search = await api_client.get(
        "/api/v1/places/search",
        headers=auth_headers(token),
        params={"q": "重庆", "city": "重庆", "limit": 5},
    )
    assert search.status_code == 200, search.text
    payload = search.json()
    assert payload["provider"] == "mock"
    assert payload["results"]
    assert payload["results"][0]["source"]["freshness"] == "mock"
    assert payload["results"][0]["location"]["coordinate_system"] == "GCJ-02"
    assert "amap" not in search.text.lower()

    detail = await api_client.get(
        f"/api/v1/places/{payload['results'][0]['provider_place_id']}",
        headers=auth_headers(token),
    )
    assert detail.status_code == 200
    assert detail.json()["name"] == payload["results"][0]["name"]

    geocode = await api_client.get(
        "/api/v1/places/geocode",
        headers=auth_headers(token),
        params={"address": "重庆市渝中区"},
    )
    assert geocode.status_code == 200
    assert geocode.json()["coordinate_system"] == "GCJ-02"


async def test_mock_place_search_respects_quanzhou_destination(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])

    search = await api_client.get(
        "/api/v1/places/search",
        headers=auth_headers(token),
        params={"q": "泉州 景点", "city": "泉州", "limit": 5},
    )

    assert search.status_code == 200, search.text
    names = [item["name"] for item in search.json()["results"]]
    assert names
    assert "洪崖洞民俗风貌区" not in names
    assert any("开元寺" in name for name in names)

    detail = await api_client.get(
        f"/api/v1/places/{search.json()['results'][0]['provider_place_id']}",
        headers=auth_headers(token),
    )
    assert detail.status_code == 200
    assert detail.json()["name"] == search.json()["results"][0]["name"]


async def test_mock_place_search_finds_known_place_without_city(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])

    search = await api_client.get(
        "/api/v1/places/search",
        headers=auth_headers(token),
        params={"q": "洪崖洞", "limit": 5},
    )

    assert search.status_code == 200, search.text
    names = [item["name"] for item in search.json()["results"]]
    assert names == ["洪崖洞民俗风貌区"]


async def test_map_status_uses_effective_map_profile(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="test",
        provider_profile="mock",
        map_provider_profile="live",
        amap_web_service_key="test-amap-key",
    )
    try:
        response = await api_client.get(
            "/api/v1/providers/map/status",
            headers=auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200, response.text
    assert response.json()["profile"] == "live"
    assert response.json()["provider"] == "amap"
    assert "weather" not in response.json()["capabilities"]


async def test_place_search_requires_authentication(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get(
        "/api/v1/places/search",
        params={"q": "洪崖洞"},
    )
    assert response.status_code == 401
