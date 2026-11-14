# 文件说明：后端自动化测试：test_trip_versions。
from uuid import uuid4

import httpx

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
    expected_version: int,
) -> dict[str, object]:
    response = await api_client.post(
        f"/api/v1/days/{day_id}/stops",
        headers=auth_headers(token),
        json={
            "place_id": "manual-versioned",
            "place_name": "Versioned stop",
            "start_at": "2026-12-01T09:00:00",
            "duration_minutes": 60,
            "estimated_cost_minor": 0,
            "expected_version": expected_version,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_stale_trip_update_returns_conflict_and_preserves_server_data(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = await create_trip(api_client, token)
    trip_id = str(trip["id"])

    initial_history = await api_client.get(
        f"/api/v1/trips/{trip_id}/versions",
        headers=auth_headers(token),
    )
    assert initial_history.status_code == 200
    assert initial_history.json()["current_version"] == 1
    assert [item["version"] for item in initial_history.json()["versions"]] == [1]
    assert initial_history.json()["versions"][0]["snapshot"]["days"] == []

    first_update = await api_client.patch(
        f"/api/v1/trips/{trip_id}",
        headers=auth_headers(token),
        json={
            "expected_version": 1,
            "brief": trip_payload(destination="Chengdu")["brief"],
        },
    )
    assert first_update.status_code == 200, first_update.text
    assert first_update.json()["version"] == 2

    stale_update = await api_client.patch(
        f"/api/v1/trips/{trip_id}",
        headers=auth_headers(token),
        json={
            "expected_version": 1,
            "status": "ready",
        },
    )
    assert stale_update.status_code == 409
    conflict = stale_update.json()["detail"]
    assert conflict["code"] == "version_conflict"
    assert conflict["current_version"] == 2

    current = await api_client.get(
        f"/api/v1/trips/{trip_id}",
        headers=auth_headers(token),
    )
    assert current.json()["brief"]["destination"] == "Chengdu"
    assert current.json()["status"] == "draft"
    assert current.json()["version"] == 2

    history = await api_client.get(
        f"/api/v1/trips/{trip_id}/versions",
        headers=auth_headers(token),
    )
    assert [item["version"] for item in history.json()["versions"]] == [1, 2]
    assert history.json()["versions"][1]["snapshot"]["trip"]["brief"]["destination"] == "Chengdu"


async def test_itinerary_writes_require_current_version(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = await create_trip(api_client, token)
    trip_id = str(trip["id"])

    day = await create_day(
        api_client,
        token,
        trip_id,
        expected_version=1,
    )

    stale_stop = await api_client.post(
        f"/api/v1/days/{day['id']}/stops",
        headers=auth_headers(token),
        json={
            "place_id": "manual-stale",
            "place_name": "Stale",
            "start_at": "2026-12-01T09:00:00",
            "duration_minutes": 60,
            "estimated_cost_minor": 0,
            "expected_version": 1,
        },
    )
    assert stale_stop.status_code == 409
    assert stale_stop.json()["detail"]["current_version"] == 2

    stop = await create_stop(
        api_client,
        token,
        str(day["id"]),
        expected_version=2,
    )
    updated = await api_client.patch(
        f"/api/v1/stops/{stop['id']}",
        headers=auth_headers(token),
        json={
            "expected_version": 3,
            "duration_minutes": 90,
        },
    )
    assert updated.status_code == 200, updated.text

    itinerary = await api_client.get(
        f"/api/v1/trips/{trip_id}/itinerary",
        headers=auth_headers(token),
    )
    assert itinerary.json()["version"] == 4
    assert itinerary.json()["days"][0]["stops"][0]["duration_minutes"] == 90

    stale_delete = await api_client.delete(
        f"/api/v1/stops/{stop['id']}?expected_version=3",
        headers=auth_headers(token),
    )
    assert stale_delete.status_code == 409
    assert stale_delete.json()["detail"]["current_version"] == 4


async def test_restore_creates_new_version_without_rewriting_history(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = await create_trip(api_client, token)
    trip_id = str(trip["id"])
    day = await create_day(
        api_client,
        token,
        trip_id,
        expected_version=1,
    )
    stop = await create_stop(
        api_client,
        token,
        str(day["id"]),
        expected_version=2,
    )
    updated = await api_client.patch(
        f"/api/v1/stops/{stop['id']}",
        headers=auth_headers(token),
        json={
            "expected_version": 3,
            "duration_minutes": 120,
        },
    )
    assert updated.status_code == 200

    restored = await api_client.post(
        f"/api/v1/trips/{trip_id}/versions/2/restore",
        headers=auth_headers(token),
        json={"expected_version": 4},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["version"] == 5

    itinerary = await api_client.get(
        f"/api/v1/trips/{trip_id}/itinerary",
        headers=auth_headers(token),
    )
    assert itinerary.json()["version"] == 5
    assert itinerary.json()["days"][0]["stops"] == []

    history = await api_client.get(
        f"/api/v1/trips/{trip_id}/versions",
        headers=auth_headers(token),
    )
    versions = history.json()["versions"]
    assert [item["version"] for item in versions] == [1, 2, 3, 4, 5]
    assert versions[3]["snapshot"]["days"][0]["stops"][0]["duration_minutes"] == 120
    assert versions[4]["snapshot"]["days"][0]["stops"] == []

    stale_restore = await api_client.post(
        f"/api/v1/trips/{trip_id}/versions/2/restore",
        headers=auth_headers(token),
        json={"expected_version": 4},
    )
    assert stale_restore.status_code == 409
    assert stale_restore.json()["detail"]["current_version"] == 5


async def test_missing_expected_version_and_version_access_are_safe(
    api_client: httpx.AsyncClient,
) -> None:
    user_a = await register_user(
        api_client,
        email=f"versions-a-{uuid4().hex}@example.com",
    )
    user_b = await register_user(
        api_client,
        email=f"versions-b-{uuid4().hex}@example.com",
    )
    token_a = str(user_a["access_token"])
    token_b = str(user_b["access_token"])
    trip = await create_trip(api_client, token_a)

    missing = await api_client.post(
        f"/api/v1/trips/{trip['id']}/days",
        headers=auth_headers(token_a),
        json={"date": "2026-12-01"},
    )
    assert missing.status_code == 422

    read_history = await api_client.get(
        f"/api/v1/trips/{trip['id']}/versions",
        headers=auth_headers(token_b),
    )
    assert read_history.status_code == 404

    restore = await api_client.post(
        f"/api/v1/trips/{trip['id']}/versions/1/restore",
        headers=auth_headers(token_b),
        json={"expected_version": 1},
    )
    assert restore.status_code == 404
