# 文件说明：后端自动化测试：test_trips_crud。
from uuid import uuid4

import httpx

from tests.test_auth import auth_headers, register_user


def trip_payload(**overrides: object) -> dict[str, object]:
    brief: dict[str, object] = {
        "destination": "Chongqing",
        "origin": "Shanghai",
        "start_date": "2026-12-01",
        "end_date": "2026-12-03",
        "party_size": 2,
        "budget_minor": 500_000,
        "currency": "CNY",
        "interests": ["food", "citywalk"],
        "pace": "balanced",
        "transport_preferences": ["public_transit"],
        "transport_strategy": {
            "strategy": "single",
            "segments": [
                {
                    "mode": "public_transit",
                    "coverage": "whole_trip",
                    "days": None,
                    "parking_required": None,
                    "description": "全程公共交通",
                }
            ],
            "constraints": [],
        },
        "lodging_preferences": ["central"],
        "must_visit": ["Hongya Cave"],
        "avoid": ["crowded"],
        "constraints": ["no spicy food"],
    }
    brief.update(overrides)
    return {"brief": brief}


async def test_create_list_and_read_trip(api_client: httpx.AsyncClient) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])

    created = await api_client.post(
        "/api/v1/trips",
        headers=auth_headers(token),
        json=trip_payload(),
    )

    assert created.status_code == 201, created.text
    trip = created.json()
    assert trip["owner_id"] == registration["user"]["id"]
    assert trip["status"] == "draft"
    assert trip["version"] == 1
    assert trip["brief"]["destination"] == "Chongqing"
    assert trip["brief"]["budget_minor"] == 500_000
    assert trip["brief"]["transport_strategy"]["strategy"] == "single"

    listed = await api_client.get("/api/v1/trips", headers=auth_headers(token))
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [trip["id"]]

    detail = await api_client.get(
        f"/api/v1/trips/{trip['id']}",
        headers=auth_headers(token),
    )
    assert detail.status_code == 200
    assert detail.json() == trip

    unauthenticated = await api_client.get("/api/v1/trips")
    assert unauthenticated.status_code == 401


async def test_update_and_archive_trip(api_client: httpx.AsyncClient) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    created = await api_client.post(
        "/api/v1/trips",
        headers=auth_headers(token),
        json=trip_payload(),
    )
    trip_id = created.json()["id"]

    updated = await api_client.patch(
        f"/api/v1/trips/{trip_id}",
        headers=auth_headers(token),
        json={
            "expected_version": 1,
            "brief": {
                **trip_payload(destination="Chengdu")["brief"],
                "end_date": "2026-12-04",
            },
            "status": "planning",
        },
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert updated.json()["status"] == "planning"
    assert updated.json()["brief"]["destination"] == "Chengdu"

    archived = await api_client.delete(
        f"/api/v1/trips/{trip_id}?expected_version=2",
        headers=auth_headers(token),
    )
    assert archived.status_code == 204

    detail = await api_client.get(
        f"/api/v1/trips/{trip_id}",
        headers=auth_headers(token),
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "archived"
    assert detail.json()["version"] == 3

    active = await api_client.get("/api/v1/trips", headers=auth_headers(token))
    assert active.json() == []

    with_archived = await api_client.get(
        "/api/v1/trips?include_archived=true",
        headers=auth_headers(token),
    )
    assert [item["id"] for item in with_archived.json()] == [trip_id]


async def test_trip_access_is_isolated_by_owner(api_client: httpx.AsyncClient) -> None:
    user_a = await register_user(
        api_client,
        email=f"trip-a-{uuid4().hex}@example.com",
    )
    user_b = await register_user(
        api_client,
        email=f"trip-b-{uuid4().hex}@example.com",
    )
    token_a = str(user_a["access_token"])
    token_b = str(user_b["access_token"])

    trip_a = await api_client.post(
        "/api/v1/trips",
        headers=auth_headers(token_a),
        json=trip_payload(),
    )
    trip_b = await api_client.post(
        "/api/v1/trips",
        headers=auth_headers(token_b),
        json=trip_payload(destination="Beijing"),
    )
    trip_a_id = trip_a.json()["id"]

    list_b = await api_client.get("/api/v1/trips", headers=auth_headers(token_b))
    assert [item["id"] for item in list_b.json()] == [trip_b.json()["id"]]

    read_a = await api_client.get(
        f"/api/v1/trips/{trip_a_id}",
        headers=auth_headers(token_b),
    )
    assert read_a.status_code == 404

    update_a = await api_client.patch(
        f"/api/v1/trips/{trip_a_id}",
        headers=auth_headers(token_b),
        json={"status": "ready", "expected_version": 1},
    )
    assert update_a.status_code == 404

    delete_a = await api_client.delete(
        f"/api/v1/trips/{trip_a_id}?expected_version=1",
        headers=auth_headers(token_b),
    )
    assert delete_a.status_code == 404


async def test_invalid_trip_dates_and_party_size_return_422(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])

    invalid_dates = await api_client.post(
        "/api/v1/trips",
        headers=auth_headers(token),
        json=trip_payload(start_date="2026-12-05"),
    )
    assert invalid_dates.status_code == 422

    invalid_party = await api_client.post(
        "/api/v1/trips",
        headers=auth_headers(token),
        json=trip_payload(party_size=21),
    )
    assert invalid_party.status_code == 422

    created = await api_client.post(
        "/api/v1/trips",
        headers=auth_headers(token),
        json=trip_payload(),
    )
    trip_id = created.json()["id"]
    invalid_update = await api_client.patch(
        f"/api/v1/trips/{trip_id}",
        headers=auth_headers(token),
        json={
            "expected_version": 1,
            "brief": {
                **trip_payload()["brief"],
                "end_date": "2026-11-30",
            }
        },
    )
    assert invalid_update.status_code == 422
