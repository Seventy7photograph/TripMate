# 文件说明：后端自动化测试：test_patch_apply。
from dataclasses import dataclass
from uuid import uuid4

import httpx

from tests.test_auth import auth_headers, register_user
from tests.test_trips_crud import trip_payload


@dataclass(frozen=True, slots=True)
class PatchFixture:
    token: str
    trip_id: str
    first_day_id: str
    second_day_id: str
    first_day_stop_ids: list[str]
    second_day_stop_ids: list[str]
    version: int


async def create_patch_fixture(api_client: httpx.AsyncClient) -> PatchFixture:
    registration = await register_user(
        api_client,
        email=f"patch-{uuid4().hex}@example.com",
    )
    token = str(registration["access_token"])
    headers = auth_headers(token)
    trip = (
        await api_client.post(
            "/api/v1/trips",
            headers=headers,
            json=trip_payload(
                destination="重庆",
                start_date="2026-12-01",
                end_date="2026-12-02",
            ),
        )
    ).json()

    version = 1
    first_day_id = ""
    second_day_id = ""
    first_day_stop_ids: list[str] = []
    second_day_stop_ids: list[str] = []
    for day_date in ("2026-12-01", "2026-12-02"):
        day = await api_client.post(
            f"/api/v1/trips/{trip['id']}/days",
            headers=headers,
            json={"expected_version": version, "date": day_date},
        )
        assert day.status_code == 201, day.text
        version += 1
        day_id = day.json()["id"]
        if day_date == "2026-12-01":
            first_day_id = day_id
        else:
            second_day_id = day_id

        stop_names = (
            ("洪崖洞", "解放碑")
            if day_date.endswith("01")
            else ("磁器口",)
        )
        for index, name in enumerate(stop_names):
            stop = await api_client.post(
                f"/api/v1/days/{day_id}/stops",
                headers=headers,
                json={
                    "expected_version": version,
                    "place_id": f"{day_date}-{index}",
                    "place_name": name,
                    "start_at": f"{day_date}T{9 + index * 3:02d}:00:00",
                    "duration_minutes": 90,
                    "estimated_cost_minor": 0,
                },
            )
            assert stop.status_code == 201, stop.text
            version += 1
            if day_date == "2026-12-01":
                first_day_stop_ids.append(stop.json()["id"])
            else:
                second_day_stop_ids.append(stop.json()["id"])

    itinerary = await api_client.get(
        f"/api/v1/trips/{trip['id']}/itinerary",
        headers=headers,
    )
    assert itinerary.status_code == 200, itinerary.text
    return PatchFixture(
        token=token,
        trip_id=trip["id"],
        first_day_id=first_day_id,
        second_day_id=second_day_id,
        first_day_stop_ids=first_day_stop_ids,
        second_day_stop_ids=second_day_stop_ids,
        version=itinerary.json()["version"],
    )


async def test_replan_creates_pending_patch_without_changing_itinerary(
    api_client: httpx.AsyncClient,
) -> None:
    fixture = await create_patch_fixture(api_client)
    response = await api_client.post(
        f"/api/v1/trips/{fixture.trip_id}/replan",
        headers=auth_headers(fixture.token),
        json={
            "expected_version": fixture.version,
            "day_id": fixture.first_day_id,
            "instruction": "减少一个景点",
        },
    )
    assert response.status_code == 201, response.text
    patch = response.json()
    assert patch["status"] == "pending"
    assert patch["base_version"] == fixture.version
    assert len(patch["changes"]["removed_stop_ids"]) == 1
    assert patch["changes"]["before_stop_count"] == 2
    assert patch["changes"]["after_stop_count"] == 1

    itinerary = await api_client.get(
        f"/api/v1/trips/{fixture.trip_id}/itinerary",
        headers=auth_headers(fixture.token),
    )
    first_day = next(
        day for day in itinerary.json()["days"] if day["id"] == fixture.first_day_id
    )
    assert [stop["id"] for stop in first_day["stops"]] == fixture.first_day_stop_ids


async def test_patch_apply_changes_only_target_day_and_creates_version(
    api_client: httpx.AsyncClient,
) -> None:
    fixture = await create_patch_fixture(api_client)
    patch = (
        await api_client.post(
            f"/api/v1/trips/{fixture.trip_id}/replan",
            headers=auth_headers(fixture.token),
            json={
                "expected_version": fixture.version,
                "day_id": fixture.first_day_id,
                "instruction": "减少一个景点",
            },
        )
    ).json()

    applied = await api_client.post(
        f"/api/v1/trips/{fixture.trip_id}/patches/{patch['id']}/apply",
        headers=auth_headers(fixture.token),
        json={"expected_version": fixture.version},
    )
    assert applied.status_code == 200, applied.text
    result = applied.json()
    assert result["status"] == "applied"
    assert result["applied_version"] == fixture.version + 1
    assert result["itinerary"]["version"] == fixture.version + 1

    first_day = next(
        day for day in result["itinerary"]["days"] if day["id"] == fixture.first_day_id
    )
    second_day = next(
        day for day in result["itinerary"]["days"] if day["id"] == fixture.second_day_id
    )
    assert len(first_day["stops"]) == 1
    assert [stop["id"] for stop in second_day["stops"]] == fixture.second_day_stop_ids


async def test_stale_patch_and_discard_do_not_change_itinerary(
    api_client: httpx.AsyncClient,
) -> None:
    fixture = await create_patch_fixture(api_client)
    patch = (
        await api_client.post(
            f"/api/v1/trips/{fixture.trip_id}/replan",
            headers=auth_headers(fixture.token),
            json={
                "expected_version": fixture.version,
                "day_id": fixture.first_day_id,
                "instruction": "减少一个景点",
            },
        )
    ).json()
    bumped = await api_client.patch(
        f"/api/v1/stops/{fixture.second_day_stop_ids[0]}",
        headers=auth_headers(fixture.token),
        json={
            "expected_version": fixture.version,
            "duration_minutes": 120,
        },
    )
    assert bumped.status_code == 200, bumped.text

    stale = await api_client.post(
        f"/api/v1/trips/{fixture.trip_id}/patches/{patch['id']}/apply",
        headers=auth_headers(fixture.token),
        json={"expected_version": fixture.version + 1},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "patch_stale"

    discarded = await api_client.post(
        f"/api/v1/trips/{fixture.trip_id}/patches/{patch['id']}/discard",
        headers=auth_headers(fixture.token),
        json={"expected_version": fixture.version + 1},
    )
    assert discarded.status_code == 200, discarded.text
    assert discarded.json()["status"] == "discarded"
    itinerary = await api_client.get(
        f"/api/v1/trips/{fixture.trip_id}/itinerary",
        headers=auth_headers(fixture.token),
    )
    first_day = next(
        day for day in itinerary.json()["days"] if day["id"] == fixture.first_day_id
    )
    assert [stop["id"] for stop in first_day["stops"]] == fixture.first_day_stop_ids


async def test_patch_access_is_owner_isolated(
    api_client: httpx.AsyncClient,
) -> None:
    fixture = await create_patch_fixture(api_client)
    patch = (
        await api_client.post(
            f"/api/v1/trips/{fixture.trip_id}/replan",
            headers=auth_headers(fixture.token),
            json={
                "expected_version": fixture.version,
                "day_id": fixture.first_day_id,
                "instruction": "减少一个景点",
            },
        )
    ).json()
    outsider = await register_user(
        api_client,
        email=f"patch-outsider-{uuid4().hex}@example.com",
    )
    response = await api_client.get(
        f"/api/v1/trips/{fixture.trip_id}/patches/{patch['id']}",
        headers=auth_headers(str(outsider["access_token"])),
    )
    assert response.status_code == 404
