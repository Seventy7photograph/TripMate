# 文件说明：后端自动化测试：test_itinerary_crud。
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
    date: str,
    theme: str | None = None,
) -> dict[str, object]:
    response = await api_client.post(
        f"/api/v1/trips/{trip_id}/days",
        headers=auth_headers(token),
        json={
            "date": date,
            "theme": theme,
            "expected_version": expected_version,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_stop(
    api_client: httpx.AsyncClient,
    token: str,
    day_id: str,
    *,
    place_id: str,
    place_name: str,
    start_at: str,
    expected_version: int,
) -> dict[str, object]:
    response = await api_client.post(
        f"/api/v1/days/{day_id}/stops",
        headers=auth_headers(token),
        json={
            "place_id": place_id,
            "place_name": place_name,
            "start_at": start_at,
            "duration_minutes": 90,
            "estimated_cost_minor": 0,
            "expected_version": expected_version,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_days_and_read_sorted_itinerary(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = await create_trip(api_client, token)
    trip_id = str(trip["id"])

    day_three = await create_day(
        api_client,
        token,
        trip_id,
        expected_version=1,
        date="2026-12-03",
        theme="Departure",
    )
    day_one = await create_day(
        api_client,
        token,
        trip_id,
        expected_version=2,
        date="2026-12-01",
        theme="Arrival",
    )
    day_two = await create_day(
        api_client,
        token,
        trip_id,
        expected_version=3,
        date="2026-12-02",
    )

    assert day_one["day_index"] == 1
    assert day_two["day_index"] == 2
    assert day_three["day_index"] == 3

    itinerary = await api_client.get(
        f"/api/v1/trips/{trip_id}/itinerary",
        headers=auth_headers(token),
    )
    assert itinerary.status_code == 200, itinerary.text
    payload = itinerary.json()
    assert payload["trip_id"] == trip_id
    assert [day["date"] for day in payload["days"]] == [
        "2026-12-01",
        "2026-12-02",
        "2026-12-03",
    ]
    assert [day["day_index"] for day in payload["days"]] == [1, 2, 3]
    assert payload["days"][0]["theme"] == "Arrival"

    repeated = await api_client.post(
        f"/api/v1/trips/{trip_id}/days",
        headers=auth_headers(token),
        json={
            "date": "2026-12-01",
            "theme": "Duplicate",
            "expected_version": 4,
        },
    )
    assert repeated.status_code == 409


async def test_add_update_delete_and_reorder_stops(
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
        date="2026-12-01",
        theme="City walk",
    )

    first = await create_stop(
        api_client,
        token,
        str(day["id"]),
        place_id="manual-hongya",
        place_name="Hongya Cave",
        start_at="2026-12-01T09:00:00",
        expected_version=2,
    )
    second = await create_stop(
        api_client,
        token,
        str(day["id"]),
        place_id="manual-jiefangbei",
        place_name="Jiefangbei",
        start_at="2026-12-01T13:00:00",
        expected_version=3,
    )

    assert first["order_index"] == 0
    assert second["order_index"] == 1
    assert first["source"]["provider"] == "manual"

    updated = await api_client.patch(
        f"/api/v1/stops/{second['id']}",
        headers=auth_headers(token),
        json={
            "expected_version": 4,
            "start_at": "2026-12-01T14:30:00",
            "duration_minutes": 45,
            "estimated_cost_minor": 3200,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["start_at"] == "2026-12-01T14:30:00"
    assert updated.json()["duration_minutes"] == 45
    assert updated.json()["estimated_cost_minor"] == 3200

    reordered = await api_client.put(
        f"/api/v1/days/{day['id']}/stops/reorder",
        headers=auth_headers(token),
        json={"expected_version": 5, "stop_ids": [second["id"], first["id"]]},
    )
    assert reordered.status_code == 200, reordered.text
    assert [stop["id"] for stop in reordered.json()["stops"]] == [
        second["id"],
        first["id"],
    ]
    assert [stop["order_index"] for stop in reordered.json()["stops"]] == [0, 1]

    itinerary = await api_client.get(
        f"/api/v1/trips/{trip['id']}/itinerary",
        headers=auth_headers(token),
    )
    stops = itinerary.json()["days"][0]["stops"]
    assert [stop["place_name"] for stop in stops] == ["Jiefangbei", "Hongya Cave"]

    deleted = await api_client.delete(
        f"/api/v1/stops/{second['id']}?expected_version=6",
        headers=auth_headers(token),
    )
    assert deleted.status_code == 204
    refreshed = await api_client.get(
        f"/api/v1/trips/{trip['id']}/itinerary",
        headers=auth_headers(token),
    )
    remaining = refreshed.json()["days"][0]["stops"]
    assert [stop["id"] for stop in remaining] == [first["id"]]
    assert remaining[0]["order_index"] == 0


async def test_invalid_itinerary_rules_return_422(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = await create_trip(api_client, token)

    outside_range = await api_client.post(
        f"/api/v1/trips/{trip['id']}/days",
        headers=auth_headers(token),
        json={"date": "2026-12-04", "expected_version": 1},
    )
    assert outside_range.status_code == 422

    day = await create_day(
        api_client,
        token,
        str(trip["id"]),
        expected_version=1,
        date="2026-12-01",
    )
    wrong_date = await api_client.post(
        f"/api/v1/days/{day['id']}/stops",
        headers=auth_headers(token),
        json={
            "place_id": "manual-wrong-day",
            "place_name": "Wrong day",
            "start_at": "2026-12-02T09:00:00",
            "duration_minutes": 60,
            "estimated_cost_minor": 0,
            "expected_version": 2,
        },
    )
    assert wrong_date.status_code == 422

    unsafe_source = await api_client.post(
        f"/api/v1/days/{day['id']}/stops",
        headers=auth_headers(token),
        json={
            "place_id": "manual-unsafe-source",
            "place_name": "Unsafe source",
            "start_at": "2026-12-01T09:00:00",
            "duration_minutes": 60,
            "estimated_cost_minor": 0,
            "expected_version": 2,
            "source": {
                "provider": "manual",
                "provider_place_id": "manual-unsafe-source",
                "source_url": "javascript:alert(1)",
                "queried_at": "2026-11-14T00:00:00Z",
                "freshness": "unknown",
                "confidence": 1,
            },
        },
    )
    assert unsafe_source.status_code == 422

    first = await create_stop(
        api_client,
        token,
        str(day["id"]),
        place_id="manual-one",
        place_name="One",
        start_at="2026-12-01T09:00:00",
        expected_version=2,
    )
    await create_stop(
        api_client,
        token,
        str(day["id"]),
        place_id="manual-two",
        place_name="Two",
        start_at="2026-12-01T11:00:00",
        expected_version=3,
    )

    incomplete = await api_client.put(
        f"/api/v1/days/{day['id']}/stops/reorder",
        headers=auth_headers(token),
        json={"expected_version": 4, "stop_ids": [first["id"]]},
    )
    assert incomplete.status_code == 422

    duplicate = await api_client.put(
        f"/api/v1/days/{day['id']}/stops/reorder",
        headers=auth_headers(token),
        json={"expected_version": 4, "stop_ids": [first["id"], first["id"]]},
    )
    assert duplicate.status_code == 422

    foreign_id = await api_client.put(
        f"/api/v1/days/{day['id']}/stops/reorder",
        headers=auth_headers(token),
        json={"expected_version": 4, "stop_ids": [first["id"], str(uuid4())]},
    )
    assert foreign_id.status_code == 422


async def test_itinerary_access_is_isolated_by_trip_owner(
    api_client: httpx.AsyncClient,
) -> None:
    user_a = await register_user(
        api_client,
        email=f"itinerary-a-{uuid4().hex}@example.com",
    )
    user_b = await register_user(
        api_client,
        email=f"itinerary-b-{uuid4().hex}@example.com",
    )
    token_a = str(user_a["access_token"])
    token_b = str(user_b["access_token"])
    trip = await create_trip(api_client, token_a)
    day = await create_day(
        api_client,
        token_a,
        str(trip["id"]),
        expected_version=1,
        date="2026-12-01",
    )
    stop = await create_stop(
        api_client,
        token_a,
        str(day["id"]),
        place_id="manual-private",
        place_name="Private stop",
        start_at="2026-12-01T09:00:00",
        expected_version=2,
    )

    read = await api_client.get(
        f"/api/v1/trips/{trip['id']}/itinerary",
        headers=auth_headers(token_b),
    )
    assert read.status_code == 404

    create = await api_client.post(
        f"/api/v1/trips/{trip['id']}/days",
        headers=auth_headers(token_b),
        json={"date": "2026-12-02", "expected_version": 1},
    )
    assert create.status_code == 404

    update = await api_client.patch(
        f"/api/v1/stops/{stop['id']}",
        headers=auth_headers(token_b),
        json={"duration_minutes": 30, "expected_version": 1},
    )
    assert update.status_code == 404

    reorder = await api_client.put(
        f"/api/v1/days/{day['id']}/stops/reorder",
        headers=auth_headers(token_b),
        json={"stop_ids": [stop["id"]], "expected_version": 1},
    )
    assert reorder.status_code == 404

    delete = await api_client.delete(
        f"/api/v1/stops/{stop['id']}?expected_version=1",
        headers=auth_headers(token_b),
    )
    assert delete.status_code == 404


async def test_stop_can_keep_provider_location_and_source_metadata(
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
        date="2026-12-01",
    )
    source = {
        "provider": "amap",
        "provider_place_id": "B001",
        "source_url": "https://www.amap.com/place/B001",
        "queried_at": "2026-11-14T00:00:00Z",
        "freshness": "live",
        "confidence": 0.95,
    }
    created = await api_client.post(
        f"/api/v1/days/{day['id']}/stops",
        headers=auth_headers(token),
        json={
            "expected_version": 2,
            "place_id": "B001",
            "place_name": "洪崖洞民俗风貌区",
            "start_at": "2026-12-01T09:00:00",
            "duration_minutes": 90,
            "estimated_cost_minor": 0,
            "location": {
                "longitude": 106.579109,
                "latitude": 29.562819,
                "coordinate_system": "GCJ-02",
            },
            "source": source,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["source"]["provider"] == "amap"
    assert created.json()["location"]["coordinate_system"] == "GCJ-02"
